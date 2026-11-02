"""Ollama adapter for the provider-independent AI brain interface.

This adapter calls Ollama's non-streaming chat API with ``httpx``. It does not
log request messages or configuration values.
"""

from __future__ import annotations

import httpx

from openagent_realtime_convo.brain import BrainError, BrainRequest, BrainResponse
from openagent_realtime_convo.config import AppConfig, ProviderSettings

DEFAULT_BASE_URL: str = "http://127.0.0.1:11434"
DEFAULT_MODEL: str = "llama3.2"


class OllamaError(BrainError):
    """Raised when Ollama API communication, configuration, or parsing fails."""


class OllamaBrainProvider:
    """Asynchronous Ollama adapter satisfying the ``BrainProvider`` protocol."""

    def __init__(
        self,
        model: str | None = None,
        *,
        base_url: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize an Ollama adapter without exposing connection configuration."""
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise OllamaError("model must be a non-empty string when provided")
        if base_url is not None and (not isinstance(base_url, str) or not base_url.strip()):
            raise OllamaError("base_url must be a non-empty string when provided")

        self.model = model.strip() if model is not None else DEFAULT_MODEL
        configured_base_url = base_url.strip() if base_url is not None else DEFAULT_BASE_URL
        self._base_url = configured_base_url.rstrip("/")
        self._http_client = http_client
        self._timeout = timeout

    def __repr__(self) -> str:
        """Return a safe representation that excludes connection configuration."""
        return f"OllamaBrainProvider(model={self.model!r})"

    @classmethod
    def from_settings(
        cls,
        settings: ProviderSettings,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> OllamaBrainProvider:
        """Construct an Ollama adapter from validated provider settings."""
        if settings.name.lower() != "ollama":
            raise OllamaError(f"Expected provider 'ollama', got '{settings.name}'")
        return cls(
            model=settings.model,
            base_url=settings.base_url,
            http_client=http_client,
            timeout=timeout,
        )

    @classmethod
    def from_config(
        cls,
        config: AppConfig,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> OllamaBrainProvider:
        """Construct an Ollama adapter from application configuration."""
        return cls.from_settings(config.provider, http_client=http_client, timeout=timeout)

    async def generate_response(self, request: BrainRequest) -> BrainResponse:
        """Generate a single-turn text reply through Ollama's chat API."""
        if not isinstance(request, BrainRequest):
            raise OllamaError("request must be an instance of BrainRequest")

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": request.message}],
            "stream": False,
        }
        url = f"{self._base_url}/api/chat"

        try:
            if self._http_client is not None:
                response = await self._http_client.post(
                    url,
                    json=payload,
                    timeout=self._timeout,
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(url, json=payload)
        except httpx.HTTPStatusError as exc:
            raise OllamaError(
                f"Ollama request failed with HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise OllamaError(
                f"Ollama network communication error: {exc.__class__.__name__}"
            ) from exc

        if response.is_error:
            raise OllamaError(f"Ollama request failed with HTTP {response.status_code}")

        try:
            data = response.json()
        except Exception as exc:
            raise OllamaError("Ollama returned invalid JSON") from exc

        if not isinstance(data, dict):
            raise OllamaError("Ollama response is not a JSON object")
        message = data.get("message")
        if not isinstance(message, dict):
            raise OllamaError("Ollama response missing message object")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise OllamaError("Ollama response contained empty or missing reply content")

        response_model = data.get("model")
        model_name = (
            response_model.strip()
            if isinstance(response_model, str) and response_model.strip()
            else self.model
        )
        try:
            return BrainResponse(reply=content.strip(), model=model_name)
        except BrainError as exc:
            raise OllamaError(f"Failed to create BrainResponse: {exc}") from exc


__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "OllamaBrainProvider",
    "OllamaError",
]
