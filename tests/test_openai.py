"""Unit tests for the OpenAI AI brain provider adapter."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from openagent_realtime_convo.brain import BrainError, BrainProvider, BrainRequest, BrainResponse
from openagent_realtime_convo.config import AppConfig, ConfigurationError, ProviderSettings
from openagent_realtime_convo.providers import (
    OpenAIBrainProvider,
    OpenAIError,
    create_brain_provider,
)
from openagent_realtime_convo.providers.openai import DEFAULT_MODEL, OPENAI_API_URL


def test_openai_provider_conforms_to_brain_protocol() -> None:
    assert isinstance(OpenAIBrainProvider(api_key="test-openai-key"), BrainProvider)


def test_openai_provider_defaults_and_redacts_api_key() -> None:
    secret = "openai-secret-for-redaction-test"
    provider = OpenAIBrainProvider(api_key=secret)

    assert provider.model == DEFAULT_MODEL
    assert provider.model == "gpt-4o-mini"
    assert secret not in repr(provider)
    assert repr(provider) == "OpenAIBrainProvider(model='gpt-4o-mini')"


@pytest.mark.parametrize("invalid_key", ["", "   ", "\t\n"])
def test_openai_provider_invalid_api_key_raises(invalid_key: str) -> None:
    with pytest.raises(OpenAIError, match="api_key must be a non-empty string"):
        OpenAIBrainProvider(api_key=invalid_key)


@pytest.mark.parametrize("invalid_model", ["", "   ", "\t\n"])
def test_openai_provider_invalid_model_raises(invalid_model: str) -> None:
    with pytest.raises(OpenAIError, match="model must be a non-empty string when provided"):
        OpenAIBrainProvider(api_key="test-openai-key", model=invalid_model)


@pytest.mark.anyio
async def test_openai_successful_response_and_payload() -> None:
    recorded_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(
            status_code=200,
            json={
                "model": "gpt-4o-mini-2024-07-18",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Hello from OpenAI.",
                        }
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAIBrainProvider(
            api_key="test-openai-key", model="gpt-4o-mini", http_client=client
        )
        response = await provider.generate_response(BrainRequest(message="Hello OpenAI"))

    assert response == BrainResponse(reply="Hello from OpenAI.", model="gpt-4o-mini-2024-07-18")
    assert len(recorded_requests) == 1
    sent_request = recorded_requests[0]
    assert str(sent_request.url) == OPENAI_API_URL
    assert sent_request.method == "POST"
    assert sent_request.headers["Authorization"] == "Bearer test-openai-key"
    assert sent_request.headers["Content-Type"] == "application/json"
    assert json.loads(sent_request.content.decode("utf-8")) == {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Hello OpenAI"}],
    }


@pytest.mark.anyio
async def test_openai_uses_configured_model_when_response_omits_one() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": "Configured-model reply."}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await OpenAIBrainProvider(
            api_key="test-openai-key", model="gpt-4.1-mini", http_client=client
        ).generate_response(BrainRequest(message="test"))

    assert response.reply == "Configured-model reply."
    assert response.model == "gpt-4.1-mini"


@pytest.mark.parametrize("status_code", [401, 429, 500])
@pytest.mark.anyio
async def test_openai_http_errors_do_not_expose_credentials_or_prompts(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=status_code, json={"error": {"message": "details"}})

    secret = "openai-secret-that-must-not-leak"
    prompt = "private prompt that must not appear in errors"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OpenAIError) as exc_info:
            await OpenAIBrainProvider(api_key=secret, http_client=client).generate_response(
                BrainRequest(message=prompt)
            )

    error_message = str(exc_info.value)
    assert error_message == f"OpenAI request failed with HTTP {status_code} (details)"
    assert secret not in error_message
    assert prompt not in error_message


@pytest.mark.parametrize(
    ("response_json", "expected_suffix"),
    [
        (
            {"error": {"code": "invalid_api_key", "message": "Incorrect API key provided"}},
            " (invalid_api_key: Incorrect API key provided)",
        ),
        (
            {"error": {"code": "model_not_found", "message": ""}},
            " (model_not_found)",
        ),
        (
            {"error": {"message": "Invalid model identifier"}},
            " (Invalid model identifier)",
        ),
        (
            {"error": "string error message"},
            " (string error message)",
        ),
        (
            {},
            "",
        ),
        (
            "not a dict error",
            "",
        ),
    ],
)
@pytest.mark.anyio
async def test_openai_http_error_sanitization_formats(
    response_json: Any, expected_suffix: str
) -> None:
    secret = "secret-key-12345"
    prompt = "super-secret-user-prompt"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=400, json=response_json)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OpenAIError) as exc_info:
            await OpenAIBrainProvider(api_key=secret, http_client=client).generate_response(
                BrainRequest(message=prompt)
            )

    msg = str(exc_info.value)
    assert msg == f"OpenAI request failed with HTTP 400{expected_suffix}"
    assert secret not in msg
    assert prompt not in msg


@pytest.mark.anyio
async def test_openai_http_error_sanitization_handles_invalid_json() -> None:
    secret = "secret-key-12345"
    prompt = "super-secret-user-prompt"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=502, text="<html>502 Bad Gateway</html>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OpenAIError) as exc_info:
            await OpenAIBrainProvider(api_key=secret, http_client=client).generate_response(
                BrainRequest(message=prompt)
            )

    msg = str(exc_info.value)
    assert msg == "OpenAI request failed with HTTP 502"
    assert secret not in msg
    assert prompt not in msg


@pytest.mark.anyio
async def test_openai_network_error_is_sanitized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OpenAIError, match="OpenAI network communication error: ConnectError"):
            await OpenAIBrainProvider(
                api_key="test-openai-key", http_client=client
            ).generate_response(BrainRequest(message="hello"))


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"choices": "not-a-list"},
        {"choices": []},
        {"choices": ["not-a-dict"]},
        {"choices": [{}]},
        {"choices": [{"message": "not-an-object"}]},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": "  "}}]},
    ],
)
@pytest.mark.anyio
async def test_openai_malformed_response_raises(payload: Any) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OpenAIError):
            await OpenAIBrainProvider(
                api_key="test-openai-key", http_client=client
            ).generate_response(BrainRequest(message="hello"))


@pytest.mark.anyio
async def test_openai_invalid_json_and_request_raise() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, text="not json")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAIBrainProvider(api_key="test-openai-key", http_client=client)
        with pytest.raises(OpenAIError, match="OpenAI returned invalid JSON"):
            await provider.generate_response(BrainRequest(message="hello"))

    with pytest.raises(OpenAIError, match="request must be an instance of BrainRequest"):
        await OpenAIBrainProvider(api_key="test-openai-key").generate_response(
            "not a request"  # type: ignore[arg-type]
        )


def test_openai_factory_and_configuration() -> None:
    settings = ProviderSettings(name="openai", api_key="test-openai-key", model="gpt-4.1-mini")
    provider = create_brain_provider(settings)
    assert isinstance(provider, OpenAIBrainProvider)
    assert provider.model == "gpt-4.1-mini"

    config = AppConfig.from_openai_environment(
        {"OPENAI_API_KEY": "test-openai-key", "OPENAI_MODEL": "gpt-4.1-mini"}
    )
    assert config.provider == settings
    assert OpenAIBrainProvider.from_config(config).model == "gpt-4.1-mini"


def test_openai_configuration_fallback_and_validation() -> None:
    config = AppConfig.from_openai_environment({"OPENAGENT_PROVIDER_API_KEY": "fallback-key"})
    assert config.provider.name == "openai"
    assert config.provider.model is None

    with pytest.raises(
        ConfigurationError, match="OPENAI_API_KEY or OPENAGENT_PROVIDER_API_KEY must be set"
    ):
        AppConfig.from_openai_environment({})


def test_openai_from_settings_rejects_another_provider() -> None:
    with pytest.raises(OpenAIError, match="Expected provider 'openai'"):
        OpenAIBrainProvider.from_settings(ProviderSettings(name="gemini", api_key="test-key"))


def test_openai_error_is_a_brain_error() -> None:
    assert issubclass(OpenAIError, BrainError)
