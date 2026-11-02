"""Unit tests for the Google Gemini AI brain provider adapter."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from openagent_realtime_convo.brain import BrainError, BrainProvider, BrainRequest, BrainResponse
from openagent_realtime_convo.config import AppConfig, ConfigurationError, ProviderSettings
from openagent_realtime_convo.providers import (
    GeminiBrainProvider,
    GeminiError,
    create_brain_provider,
)
from openagent_realtime_convo.providers.gemini import DEFAULT_MODEL, GEMINI_API_URL


def test_gemini_provider_conforms_to_brain_protocol() -> None:
    assert isinstance(GeminiBrainProvider(api_key="test-gemini-key"), BrainProvider)


def test_gemini_provider_defaults_and_redacts_api_key() -> None:
    secret = "gemini-secret-for-redaction-test"
    provider = GeminiBrainProvider(api_key=secret)

    assert provider.model == DEFAULT_MODEL
    assert provider.model == "gemini-2.0-flash"
    assert secret not in repr(provider)
    assert repr(provider) == "GeminiBrainProvider(model='gemini-2.0-flash')"


@pytest.mark.parametrize("invalid_key", ["", "   ", "\t\n"])
def test_gemini_provider_invalid_api_key_raises(invalid_key: str) -> None:
    with pytest.raises(GeminiError, match="api_key must be a non-empty string"):
        GeminiBrainProvider(api_key=invalid_key)


@pytest.mark.parametrize("invalid_model", ["", "   ", "\t\n"])
def test_gemini_provider_invalid_model_raises(invalid_model: str) -> None:
    with pytest.raises(GeminiError, match="model must be a non-empty string when provided"):
        GeminiBrainProvider(api_key="test-gemini-key", model=invalid_model)


@pytest.mark.anyio
async def test_gemini_successful_response_and_payload() -> None:
    recorded_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(
            status_code=200,
            json={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": "Hello from Gemini."}],
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiBrainProvider(
            api_key="test-gemini-key", model="gemini-2.0-flash", http_client=client
        )
        response = await provider.generate_response(BrainRequest(message="Hello Gemini"))

    assert response == BrainResponse(reply="Hello from Gemini.", model="gemini-2.0-flash")
    assert len(recorded_requests) == 1
    sent_request = recorded_requests[0]
    assert str(sent_request.url) == f"{GEMINI_API_URL}/gemini-2.0-flash:generateContent"
    assert sent_request.method == "POST"
    assert sent_request.headers["x-goog-api-key"] == "test-gemini-key"
    assert sent_request.headers["Content-Type"] == "application/json"
    assert json.loads(sent_request.content.decode("utf-8")) == {
        "contents": [{"role": "user", "parts": [{"text": "Hello Gemini"}]}]
    }


@pytest.mark.anyio
async def test_gemini_joins_text_parts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "candidates": [{"content": {"parts": [{"text": "First "}, {"text": "second."}]}}]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await GeminiBrainProvider(
            api_key="test-gemini-key", http_client=client
        ).generate_response(BrainRequest(message="test"))

    assert response.reply == "First second."


@pytest.mark.parametrize("status_code", [401, 429, 500])
@pytest.mark.anyio
async def test_gemini_http_errors_do_not_expose_credentials_or_prompts(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=status_code, json={"error": {"message": "details"}})

    secret = "gemini-secret-that-must-not-leak"
    prompt = "private prompt that must not appear in errors"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GeminiError) as exc_info:
            await GeminiBrainProvider(api_key=secret, http_client=client).generate_response(
                BrainRequest(message=prompt)
            )

    error_message = str(exc_info.value)
    assert error_message == f"Gemini request failed with HTTP {status_code}"
    assert secret not in error_message
    assert prompt not in error_message


@pytest.mark.anyio
async def test_gemini_network_error_is_sanitized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GeminiError, match="Gemini network communication error: ConnectError"):
            await GeminiBrainProvider(
                api_key="test-gemini-key", http_client=client
            ).generate_response(BrainRequest(message="hello"))


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"candidates": "not-a-list"},
        {"candidates": []},
        {"candidates": ["not-a-dict"]},
        {"candidates": [{}]},
        {"candidates": [{"content": "not-an-object"}]},
        {"candidates": [{"content": {}}]},
        {"candidates": [{"content": {"parts": []}}]},
        {"candidates": [{"content": {"parts": [{"text": "  "}]}}]},
    ],
)
@pytest.mark.anyio
async def test_gemini_malformed_response_raises(payload: Any) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GeminiError):
            await GeminiBrainProvider(
                api_key="test-gemini-key", http_client=client
            ).generate_response(BrainRequest(message="hello"))


@pytest.mark.anyio
async def test_gemini_invalid_json_and_request_raise() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, text="not json")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiBrainProvider(api_key="test-gemini-key", http_client=client)
        with pytest.raises(GeminiError, match="Gemini returned invalid JSON"):
            await provider.generate_response(BrainRequest(message="hello"))

    with pytest.raises(GeminiError, match="request must be an instance of BrainRequest"):
        await GeminiBrainProvider(api_key="test-gemini-key").generate_response(
            "not a request"  # type: ignore[arg-type]
        )


def test_gemini_factory_and_configuration() -> None:
    settings = ProviderSettings(name="gemini", api_key="test-gemini-key", model="gemini-2.5-flash")
    provider = create_brain_provider(settings)
    assert isinstance(provider, GeminiBrainProvider)
    assert provider.model == "gemini-2.5-flash"

    config = AppConfig.from_gemini_environment(
        {"GEMINI_API_KEY": "test-gemini-key", "GEMINI_MODEL": "gemini-2.5-flash"}
    )
    assert config.provider == settings
    assert GeminiBrainProvider.from_config(config).model == "gemini-2.5-flash"


def test_gemini_configuration_fallback_and_validation() -> None:
    config = AppConfig.from_gemini_environment({"OPENAGENT_PROVIDER_API_KEY": "fallback-key"})
    assert config.provider.name == "gemini"
    assert config.provider.model is None

    with pytest.raises(
        ConfigurationError, match="GEMINI_API_KEY or OPENAGENT_PROVIDER_API_KEY must be set"
    ):
        AppConfig.from_gemini_environment({})


def test_gemini_from_settings_rejects_another_provider() -> None:
    with pytest.raises(GeminiError, match="Expected provider 'gemini'"):
        GeminiBrainProvider.from_settings(ProviderSettings(name="openrouter", api_key="test-key"))


def test_gemini_error_is_a_brain_error() -> None:
    assert issubclass(GeminiError, BrainError)
