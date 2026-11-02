"""Unit tests for the Anthropic Claude brain provider adapter."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from openagent_realtime_convo.brain import BrainError, BrainProvider, BrainRequest, BrainResponse
from openagent_realtime_convo.config import AppConfig, ConfigurationError, ProviderSettings
from openagent_realtime_convo.providers import (
    AnthropicBrainProvider,
    AnthropicError,
    create_brain_provider,
)
from openagent_realtime_convo.providers.anthropic import (
    ANTHROPIC_API_URL,
    ANTHROPIC_VERSION,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
)


def test_anthropic_provider_conforms_to_brain_protocol() -> None:
    assert isinstance(AnthropicBrainProvider(api_key="test-anthropic-key"), BrainProvider)


def test_anthropic_provider_defaults_and_redacts_api_key() -> None:
    secret = "anthropic-secret-for-redaction-test"
    provider = AnthropicBrainProvider(api_key=secret)

    assert provider.model == DEFAULT_MODEL
    assert provider.model == "claude-3-5-haiku-latest"
    assert secret not in repr(provider)
    assert repr(provider) == "AnthropicBrainProvider(model='claude-3-5-haiku-latest')"


@pytest.mark.parametrize("invalid_key", ["", "   ", "\t\n"])
def test_anthropic_provider_invalid_api_key_raises(invalid_key: str) -> None:
    with pytest.raises(AnthropicError, match="api_key must be a non-empty string"):
        AnthropicBrainProvider(api_key=invalid_key)


@pytest.mark.parametrize("invalid_model", ["", "   ", "\t\n"])
def test_anthropic_provider_invalid_model_raises(invalid_model: str) -> None:
    with pytest.raises(AnthropicError, match="model must be a non-empty string when provided"):
        AnthropicBrainProvider(api_key="test-anthropic-key", model=invalid_model)


@pytest.mark.anyio
async def test_anthropic_successful_response_and_payload() -> None:
    recorded_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(
            status_code=200,
            json={
                "model": "claude-3-5-haiku-20241022",
                "content": [{"type": "text", "text": "Hello from Claude."}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = AnthropicBrainProvider(
            api_key="test-anthropic-key", model="claude-3-5-haiku-latest", http_client=client
        )
        response = await provider.generate_response(BrainRequest(message="Hello Claude"))

    assert response == BrainResponse(reply="Hello from Claude.", model="claude-3-5-haiku-20241022")
    assert len(recorded_requests) == 1
    sent_request = recorded_requests[0]
    assert str(sent_request.url) == ANTHROPIC_API_URL
    assert sent_request.method == "POST"
    assert sent_request.headers["x-api-key"] == "test-anthropic-key"
    assert sent_request.headers["anthropic-version"] == ANTHROPIC_VERSION
    assert sent_request.headers["Content-Type"] == "application/json"
    assert json.loads(sent_request.content.decode("utf-8")) == {
        "model": "claude-3-5-haiku-latest",
        "max_tokens": DEFAULT_MAX_TOKENS,
        "messages": [{"role": "user", "content": "Hello Claude"}],
    }


@pytest.mark.anyio
async def test_anthropic_joins_text_blocks_and_ignores_non_text_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "content": [
                    {"type": "thinking", "thinking": "internal reasoning"},
                    {"type": "text", "text": "First "},
                    {"type": "text", "text": "second."},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await AnthropicBrainProvider(
            api_key="test-anthropic-key", model="claude-3-5-haiku-latest", http_client=client
        ).generate_response(BrainRequest(message="test"))

    assert response.reply == "First second."
    assert response.model == "claude-3-5-haiku-latest"


@pytest.mark.parametrize("status_code", [401, 429, 500])
@pytest.mark.anyio
async def test_anthropic_http_errors_do_not_expose_credentials_or_prompts(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=status_code, json={"error": {"message": "details"}})

    secret = "anthropic-secret-that-must-not-leak"
    prompt = "private prompt that must not appear in errors"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AnthropicError) as exc_info:
            await AnthropicBrainProvider(api_key=secret, http_client=client).generate_response(
                BrainRequest(message=prompt)
            )

    error_message = str(exc_info.value)
    assert error_message == f"Anthropic request failed with HTTP {status_code}"
    assert secret not in error_message
    assert prompt not in error_message


@pytest.mark.anyio
async def test_anthropic_network_error_is_sanitized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(
            AnthropicError, match="Anthropic network communication error: ConnectError"
        ):
            await AnthropicBrainProvider(
                api_key="test-anthropic-key", http_client=client
            ).generate_response(BrainRequest(message="hello"))


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"content": "not-a-list"},
        {"content": []},
        {"content": ["not-an-object"]},
        {"content": [{"type": "text"}]},
        {"content": [{"type": "text", "text": "  "}]},
        {"content": [{"type": "tool_use", "name": "search"}]},
    ],
)
@pytest.mark.anyio
async def test_anthropic_malformed_response_raises(payload: Any) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AnthropicError):
            await AnthropicBrainProvider(
                api_key="test-anthropic-key", http_client=client
            ).generate_response(BrainRequest(message="hello"))


@pytest.mark.anyio
async def test_anthropic_invalid_json_and_request_raise() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, text="not json")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = AnthropicBrainProvider(api_key="test-anthropic-key", http_client=client)
        with pytest.raises(AnthropicError, match="Anthropic returned invalid JSON"):
            await provider.generate_response(BrainRequest(message="hello"))

    with pytest.raises(AnthropicError, match="request must be an instance of BrainRequest"):
        await AnthropicBrainProvider(api_key="test-anthropic-key").generate_response(
            "not a request"  # type: ignore[arg-type]
        )


def test_anthropic_factory_and_configuration() -> None:
    settings = ProviderSettings(
        name="anthropic", api_key="test-anthropic-key", model="claude-3-5-haiku-latest"
    )
    provider = create_brain_provider(settings)
    assert isinstance(provider, AnthropicBrainProvider)
    assert provider.model == "claude-3-5-haiku-latest"

    config = AppConfig.from_anthropic_environment(
        {
            "ANTHROPIC_API_KEY": "test-anthropic-key",
            "ANTHROPIC_MODEL": "claude-3-5-haiku-latest",
        }
    )
    assert config.provider == settings
    assert AnthropicBrainProvider.from_config(config).model == "claude-3-5-haiku-latest"


def test_anthropic_configuration_fallback_and_validation() -> None:
    config = AppConfig.from_anthropic_environment({"OPENAGENT_PROVIDER_API_KEY": "fallback-key"})
    assert config.provider.name == "anthropic"
    assert config.provider.model is None

    with pytest.raises(
        ConfigurationError, match="ANTHROPIC_API_KEY or OPENAGENT_PROVIDER_API_KEY must be set"
    ):
        AppConfig.from_anthropic_environment({})


def test_anthropic_from_settings_rejects_another_provider() -> None:
    with pytest.raises(AnthropicError, match="Expected provider 'anthropic'"):
        AnthropicBrainProvider.from_settings(ProviderSettings(name="openai", api_key="test-key"))


def test_anthropic_error_is_a_brain_error() -> None:
    assert issubclass(AnthropicError, BrainError)
