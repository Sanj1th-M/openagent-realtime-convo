"""Unit tests for the OpenRouter AI brain provider adapter."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from openagent_realtime_convo.brain import (
    BrainError,
    BrainProvider,
    BrainRequest,
    BrainResponse,
)
from openagent_realtime_convo.config import AppConfig, ConfigurationError, ProviderSettings
from openagent_realtime_convo.providers import (
    OpenRouterBrainProvider,
    OpenRouterError,
    create_brain_provider,
)
from openagent_realtime_convo.providers.openrouter import (
    DEFAULT_MODEL,
    OPENROUTER_API_URL,
)

# ---------------------------------------------------------------------------
# Protocol conformance & construction tests
# ---------------------------------------------------------------------------


def test_openrouter_provider_conforms_to_brain_protocol() -> None:
    provider = OpenRouterBrainProvider(api_key="sk-or-test-key")
    assert isinstance(provider, BrainProvider)


def test_openrouter_provider_default_model() -> None:
    provider = OpenRouterBrainProvider(api_key="sk-or-test-key")
    assert provider.model == DEFAULT_MODEL
    assert provider.model == "openai/gpt-4o-mini"


def test_openrouter_provider_custom_model() -> None:
    provider = OpenRouterBrainProvider(
        api_key="sk-or-test-key",
        model="anthropic/claude-3.5-sonnet",
    )
    assert provider.model == "anthropic/claude-3.5-sonnet"


@pytest.mark.parametrize("invalid_key", ["", "   ", "\t\n"])
def test_openrouter_provider_invalid_api_key_raises(invalid_key: str) -> None:
    with pytest.raises(OpenRouterError, match="api_key must be a non-empty string"):
        OpenRouterBrainProvider(api_key=invalid_key)


@pytest.mark.parametrize("invalid_model", ["", "   ", "\t\n"])
def test_openrouter_provider_invalid_model_raises(invalid_model: str) -> None:
    with pytest.raises(OpenRouterError, match="model must be a non-empty string when provided"):
        OpenRouterBrainProvider(api_key="sk-or-test-key", model=invalid_model)


def test_openrouter_repr_redacts_api_key() -> None:
    secret = "sk-or-super-confidential-secret-key"
    provider = OpenRouterBrainProvider(api_key=secret, model="meta-llama/llama-3.1-8b")
    provider_repr = repr(provider)

    assert secret not in provider_repr
    assert "OpenRouterBrainProvider(model='meta-llama/llama-3.1-8b')" in provider_repr


# ---------------------------------------------------------------------------
# Successful response and payload verification
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_openrouter_successful_response_and_payload() -> None:
    recorded_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(
            status_code=200,
            json={
                "id": "gen-12345",
                "model": "openai/gpt-4o-mini",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Hello! I am your AI assistant.",
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenRouterBrainProvider(
            api_key="sk-or-valid-test-key",
            model="openai/gpt-4o-mini",
            http_client=client,
        )
        request = BrainRequest(message="Hi there!", session_id="ses-1")
        response = await provider.generate_response(request)

    assert isinstance(response, BrainResponse)
    assert response.reply == "Hello! I am your AI assistant."
    assert response.model == "openai/gpt-4o-mini"

    # Verify request payload, headers, and endpoint
    assert len(recorded_requests) == 1
    req = recorded_requests[0]
    assert str(req.url) == OPENROUTER_API_URL
    assert req.method == "POST"
    assert req.headers["Authorization"] == "Bearer sk-or-valid-test-key"
    assert req.headers["Content-Type"] == "application/json"

    body = json.loads(req.content.decode("utf-8"))
    assert body["model"] == "openai/gpt-4o-mini"
    assert body["messages"] == [{"role": "user", "content": "Hi there!"}]


@pytest.mark.anyio
async def test_openrouter_uses_response_model_if_provided() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "model": "deepseek/deepseek-chat",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Deepseek response.",
                        }
                    }
                ],
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenRouterBrainProvider(
            api_key="test-key",
            model="openai/gpt-4o-mini",
            http_client=client,
        )
        response = await provider.generate_response(BrainRequest(message="test"))

    assert response.reply == "Deepseek response."
    assert response.model == "deepseek/deepseek-chat"


# ---------------------------------------------------------------------------
# HTTP error and network error handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status_code", "error_body"),
    [
        (401, {"error": {"message": "Invalid API key", "code": 401}}),
        (429, {"error": {"message": "Rate limit exceeded", "code": 429}}),
        (500, {"error": {"message": "Internal server error", "code": 500}}),
        (503, "Service Unavailable"),
    ],
)
@pytest.mark.anyio
async def test_openrouter_http_error_handling(status_code: int, error_body: Any) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(error_body, dict):
            return httpx.Response(status_code=status_code, json=error_body)
        return httpx.Response(status_code=status_code, text=str(error_body))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        secret_key = "sk-or-sensitive-key-never-leak"
        sensitive_message = "Confidential prompt content that must not be in error"
        provider = OpenRouterBrainProvider(api_key=secret_key, http_client=client)

        with pytest.raises(OpenRouterError) as exc_info:
            await provider.generate_response(BrainRequest(message=sensitive_message))

        error_message = str(exc_info.value)
        assert f"HTTP {status_code}" in error_message
        assert issubclass(OpenRouterError, BrainError)
        # Ensure credentials and prompt contents are never included in exception message
        assert secret_key not in error_message
        assert sensitive_message not in error_message


@pytest.mark.anyio
async def test_openrouter_network_error_handling() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenRouterBrainProvider(api_key="test-key", http_client=client)

        with pytest.raises(OpenRouterError, match="OpenRouter network communication error"):
            await provider.generate_response(BrainRequest(message="Hello"))


# ---------------------------------------------------------------------------
# Malformed and invalid response handling
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_openrouter_invalid_json_handling() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, text="<HTML>Not JSON</HTML>")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenRouterBrainProvider(api_key="test-key", http_client=client)

        with pytest.raises(OpenRouterError, match="OpenRouter returned invalid JSON"):
            await provider.generate_response(BrainRequest(message="Hello"))


@pytest.mark.parametrize(
    "malformed_payload",
    [
        [],  # JSON list instead of object
        {},  # Missing choices
        {"choices": "not-a-list"},
        {"choices": []},  # Empty choices
        {"choices": ["not-a-dict"]},
        {"choices": [{}]},  # Missing message
        {"choices": [{"message": "not-a-dict"}]},
        {"choices": [{"message": {}}]},  # Missing content
    ],
)
@pytest.mark.anyio
async def test_openrouter_malformed_structure_handling(malformed_payload: Any) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json=malformed_payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenRouterBrainProvider(api_key="test-key", http_client=client)

        with pytest.raises(OpenRouterError):
            await provider.generate_response(BrainRequest(message="Hello"))


@pytest.mark.parametrize("empty_content", ["", "   ", "\t\n"])
@pytest.mark.anyio
async def test_openrouter_empty_reply_handling(empty_content: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"role": "assistant", "content": empty_content}}]},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenRouterBrainProvider(api_key="test-key", http_client=client)

        with pytest.raises(
            OpenRouterError,
            match="OpenRouter response contained empty or missing reply content",
        ):
            await provider.generate_response(BrainRequest(message="Hello"))


@pytest.mark.anyio
async def test_openrouter_generate_response_rejects_invalid_request() -> None:
    provider = OpenRouterBrainProvider(api_key="test-key")
    with pytest.raises(OpenRouterError, match="request must be an instance of BrainRequest"):
        await provider.generate_response(
            "Not a BrainRequest"  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# Configuration and factory tests
# ---------------------------------------------------------------------------


def test_provider_factory_openrouter() -> None:
    settings = ProviderSettings(
        name="openrouter",
        api_key="sk-or-factory-key",
        model="google/gemini-2.0-flash",
    )
    provider = create_brain_provider(settings)
    assert isinstance(provider, OpenRouterBrainProvider)
    assert isinstance(provider, BrainProvider)
    assert provider.model == "google/gemini-2.0-flash"


def test_provider_factory_unsupported_provider() -> None:
    settings = ProviderSettings(name="unsupported-provider", api_key="key")
    with pytest.raises(BrainError, match="Unsupported brain provider"):
        create_brain_provider(settings)


def test_openrouter_from_settings_and_from_config() -> None:
    settings = ProviderSettings(
        name="openrouter",
        api_key="sk-or-conf-key",
        model="meta-llama/llama-3.1-70b",
    )
    provider_from_settings = OpenRouterBrainProvider.from_settings(settings)
    assert provider_from_settings.model == "meta-llama/llama-3.1-70b"

    config = AppConfig(
        audio=AppConfig.from_environment(
            {"OPENAGENT_PROVIDER": "openrouter", "OPENAGENT_PROVIDER_API_KEY": "dummy"}
        ).audio,
        provider=settings,
    )
    provider_from_config = OpenRouterBrainProvider.from_config(config)
    assert provider_from_config.model == "meta-llama/llama-3.1-70b"


def test_openrouter_from_settings_wrong_provider_name() -> None:
    settings = ProviderSettings(name="openai", api_key="sk-key")
    with pytest.raises(OpenRouterError, match="Expected provider 'openrouter'"):
        OpenRouterBrainProvider.from_settings(settings)


def test_app_config_from_openrouter_environment() -> None:
    config = AppConfig.from_openrouter_environment(
        {
            "OPENROUTER_API_KEY": "sk-or-env-key",
            "OPENROUTER_MODEL": "anthropic/claude-3-haiku",
        }
    )
    assert config.provider.name == "openrouter"
    assert config.provider.api_key == "sk-or-env-key"
    assert config.provider.model == "anthropic/claude-3-haiku"


def test_app_config_from_openrouter_environment_fallback_key() -> None:
    config = AppConfig.from_openrouter_environment(
        {
            "OPENAGENT_PROVIDER_API_KEY": "sk-or-fallback-key",
        }
    )
    assert config.provider.name == "openrouter"
    assert config.provider.api_key == "sk-or-fallback-key"
    assert config.provider.model is None


def test_app_config_from_openrouter_environment_missing_key_raises() -> None:
    with pytest.raises(
        ConfigurationError,
        match="OPENROUTER_API_KEY or OPENAGENT_PROVIDER_API_KEY must be set",
    ):
        AppConfig.from_openrouter_environment({})


def test_app_config_from_environment_with_optional_model() -> None:
    config = AppConfig.from_environment(
        {
            "OPENAGENT_PROVIDER": "openrouter",
            "OPENAGENT_PROVIDER_API_KEY": "sk-or-key",
            "OPENAGENT_PROVIDER_MODEL": "mistralai/mistral-large",
        }
    )
    assert config.provider.name == "openrouter"
    assert config.provider.api_key == "sk-or-key"
    assert config.provider.model == "mistralai/mistral-large"


def test_app_config_from_environment_empty_model_raises() -> None:
    with pytest.raises(ConfigurationError, match="OPENAGENT_PROVIDER_MODEL must not be empty"):
        AppConfig.from_environment(
            {
                "OPENAGENT_PROVIDER": "openrouter",
                "OPENAGENT_PROVIDER_API_KEY": "sk-or-key",
                "OPENAGENT_PROVIDER_MODEL": "   ",
            }
        )
