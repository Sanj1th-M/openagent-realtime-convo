"""Unit tests for the Ollama AI brain provider adapter."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from openagent_realtime_convo.brain import BrainError, BrainProvider, BrainRequest, BrainResponse
from openagent_realtime_convo.config import AppConfig, ConfigurationError, ProviderSettings
from openagent_realtime_convo.providers import (
    OllamaBrainProvider,
    OllamaError,
    create_brain_provider,
)
from openagent_realtime_convo.providers.ollama import DEFAULT_BASE_URL, DEFAULT_MODEL


def test_ollama_provider_conforms_to_brain_protocol() -> None:
    assert isinstance(OllamaBrainProvider(), BrainProvider)


def test_ollama_provider_defaults_and_redacts_connection_configuration() -> None:
    provider = OllamaBrainProvider(base_url="http://private-ollama-host:11434")

    assert provider.model == DEFAULT_MODEL
    assert provider.model == "llama3.2"
    assert DEFAULT_BASE_URL == "http://127.0.0.1:11434"
    assert "private-ollama-host" not in repr(provider)
    assert repr(provider) == "OllamaBrainProvider(model='llama3.2')"


@pytest.mark.parametrize("invalid_model", ["", "   ", "\t\n"])
def test_ollama_provider_invalid_model_raises(invalid_model: str) -> None:
    with pytest.raises(OllamaError, match="model must be a non-empty string when provided"):
        OllamaBrainProvider(model=invalid_model)


@pytest.mark.parametrize("invalid_base_url", ["", "   ", "\t\n"])
def test_ollama_provider_invalid_base_url_raises(invalid_base_url: str) -> None:
    with pytest.raises(OllamaError, match="base_url must be a non-empty string when provided"):
        OllamaBrainProvider(base_url=invalid_base_url)


@pytest.mark.anyio
async def test_ollama_successful_response_and_payload() -> None:
    recorded_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(
            status_code=200,
            json={
                "model": "llama3.2:3b-instruct-q4_K_M",
                "message": {"role": "assistant", "content": "Hello from Ollama."},
                "done": True,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OllamaBrainProvider(
            model="llama3.2:3b-instruct-q4_K_M",
            base_url="http://127.0.0.1:11434/",
            http_client=client,
        )
        response = await provider.generate_response(BrainRequest(message="Hello Ollama"))

    assert response == BrainResponse(
        reply="Hello from Ollama.", model="llama3.2:3b-instruct-q4_K_M"
    )
    assert len(recorded_requests) == 1
    sent_request = recorded_requests[0]
    assert str(sent_request.url) == "http://127.0.0.1:11434/api/chat"
    assert sent_request.method == "POST"
    assert json.loads(sent_request.content.decode("utf-8")) == {
        "model": "llama3.2:3b-instruct-q4_K_M",
        "messages": [{"role": "user", "content": "Hello Ollama"}],
        "stream": False,
    }


@pytest.mark.anyio
async def test_ollama_uses_configured_model_when_response_omits_one() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={"message": {"role": "assistant", "content": "Configured-model reply."}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        response = await OllamaBrainProvider(model="mistral", http_client=client).generate_response(
            BrainRequest(message="test")
        )

    assert response.reply == "Configured-model reply."
    assert response.model == "mistral"


@pytest.mark.parametrize("status_code", [400, 404, 500])
@pytest.mark.anyio
async def test_ollama_http_errors_do_not_expose_prompts_or_connection_details(
    status_code: int,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=status_code, json={"error": "details"})

    prompt = "private prompt that must not appear in errors"
    base_url = "http://private-ollama-host:11434"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OllamaError) as exc_info:
            await OllamaBrainProvider(base_url=base_url, http_client=client).generate_response(
                BrainRequest(message=prompt)
            )

    error_message = str(exc_info.value)
    assert error_message == f"Ollama request failed with HTTP {status_code}"
    assert prompt not in error_message
    assert base_url not in error_message


@pytest.mark.anyio
async def test_ollama_network_error_is_sanitized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OllamaError, match="Ollama network communication error: ConnectError"):
            await OllamaBrainProvider(http_client=client).generate_response(
                BrainRequest(message="hello")
            )


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"message": "not-an-object"},
        {"message": {}},
        {"message": {"content": None}},
        {"message": {"content": "  "}},
    ],
)
@pytest.mark.anyio
async def test_ollama_malformed_response_raises(payload: Any) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(OllamaError):
            await OllamaBrainProvider(http_client=client).generate_response(
                BrainRequest(message="hello")
            )


@pytest.mark.anyio
async def test_ollama_invalid_json_and_request_raise() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, text="not json")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OllamaBrainProvider(http_client=client)
        with pytest.raises(OllamaError, match="Ollama returned invalid JSON"):
            await provider.generate_response(BrainRequest(message="hello"))

    with pytest.raises(OllamaError, match="request must be an instance of BrainRequest"):
        await OllamaBrainProvider().generate_response("not a request")  # type: ignore[arg-type]


def test_ollama_factory_and_configuration() -> None:
    settings = ProviderSettings(
        name="ollama",
        api_key="ollama-local",
        model="mistral",
        base_url="http://localhost:12000",
    )
    provider = create_brain_provider(settings)
    assert isinstance(provider, OllamaBrainProvider)
    assert provider.model == "mistral"
    assert "localhost:12000" not in repr(provider)

    config = AppConfig.from_ollama_environment(
        {"OLLAMA_BASE_URL": "http://localhost:12000", "OLLAMA_MODEL": "mistral"}
    )
    assert config.provider.name == "ollama"
    assert config.provider.model == "mistral"
    assert config.provider.base_url == "http://localhost:12000"
    assert OllamaBrainProvider.from_config(config).model == "mistral"


def test_ollama_configuration_uses_defaults_and_generic_model_fallback() -> None:
    default_config = AppConfig.from_ollama_environment({})
    assert default_config.provider.model is None
    assert default_config.provider.base_url is None

    fallback_config = AppConfig.from_ollama_environment({"OPENAGENT_PROVIDER_MODEL": "qwen2.5"})
    assert fallback_config.provider.model == "qwen2.5"


def test_ollama_configuration_rejects_invalid_base_url() -> None:
    with pytest.raises(ConfigurationError, match="provider base URL must not be empty"):
        ProviderSettings(name="ollama", api_key="ollama-local", base_url="   ")


def test_ollama_from_settings_rejects_another_provider() -> None:
    with pytest.raises(OllamaError, match="Expected provider 'ollama'"):
        OllamaBrainProvider.from_settings(ProviderSettings(name="openai", api_key="test-key"))


def test_ollama_error_is_a_brain_error() -> None:
    assert issubclass(OllamaError, BrainError)
