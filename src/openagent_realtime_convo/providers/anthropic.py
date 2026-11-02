"""Anthropic Claude adapter for the provider-independent AI brain interface.

This adapter calls Anthropic's Messages API with ``httpx``. It does not log API
credentials, request messages, or response bodies.
"""

from __future__ import annotations

import httpx

from openagent_realtime_convo.brain import BrainError, BrainRequest, BrainResponse
from openagent_realtime_convo.config import AppConfig, ProviderSettings

ANTHROPIC_API_URL: str = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION: str = "2023-06-01"
DEFAULT_MODEL: str = "claude-3-5-haiku-latest"
DEFAULT_MAX_TOKENS: int = 1_024


class AnthropicError(BrainError):
    """Raised when Anthropic API communication, configuration, or parsing fails."""


class AnthropicBrainProvider:
    """Asynchronous Claude adapter satisfying the ``BrainProvider`` protocol."""

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize the adapter without exposing the API key in representations."""
        if not isinstance(api_key, str) or not api_key.strip():
            raise AnthropicError("api_key must be a non-empty string")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise AnthropicError("model must be a non-empty string when provided")

        self._api_key = api_key.strip()
        self.model = model.strip() if model is not None else DEFAULT_MODEL
        self._http_client = http_client
        self._timeout = timeout

    def __repr__(self) -> str:
        """Return a safe representation that excludes credentials."""
        return f"AnthropicBrainProvider(model={self.model!r})"

    @classmethod
    def from_settings(
        cls,
        settings: ProviderSettings,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> AnthropicBrainProvider:
        """Construct an Anthropic adapter from validated provider settings."""
        if settings.name.lower() != "anthropic":
            raise AnthropicError(f"Expected provider 'anthropic', got '{settings.name}'")
        return cls(
            api_key=settings.api_key,
            model=settings.model,
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
    ) -> AnthropicBrainProvider:
        """Construct an Anthropic adapter from application configuration."""
        return cls.from_settings(config.provider, http_client=http_client, timeout=timeout)

    async def generate_response(self, request: BrainRequest) -> BrainResponse:
        """Generate a single-turn text reply through Anthropic's Messages API."""
        if not isinstance(request, BrainRequest):
            raise AnthropicError("request must be an instance of BrainRequest")

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "messages": [{"role": "user", "content": request.message}],
        }

        try:
            if self._http_client is not None:
                response = await self._http_client.post(
                    ANTHROPIC_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=self._timeout,
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(ANTHROPIC_API_URL, headers=headers, json=payload)
        except httpx.HTTPStatusError as exc:
            raise AnthropicError(
                f"Anthropic request failed with HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise AnthropicError(
                f"Anthropic network communication error: {exc.__class__.__name__}"
            ) from exc

        if response.is_error:
            raise AnthropicError(f"Anthropic request failed with HTTP {response.status_code}")

        try:
            data = response.json()
        except Exception as exc:
            raise AnthropicError("Anthropic returned invalid JSON") from exc

        if not isinstance(data, dict):
            raise AnthropicError("Anthropic response is not a JSON object")
        content = data.get("content")
        if not isinstance(content, list) or not content:
            raise AnthropicError("Anthropic response missing valid content blocks")

        text_parts = [
            block["text"]
            for block in content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ]
        reply = "".join(text_parts).strip()
        if not reply:
            raise AnthropicError("Anthropic response contained empty or missing reply content")

        response_model = data.get("model")
        model_name = (
            response_model.strip()
            if isinstance(response_model, str) and response_model.strip()
            else self.model
        )
        try:
            return BrainResponse(reply=reply, model=model_name)
        except BrainError as exc:
            raise AnthropicError(f"Failed to create BrainResponse: {exc}") from exc


__all__ = [
    "ANTHROPIC_API_URL",
    "ANTHROPIC_VERSION",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_MODEL",
    "AnthropicBrainProvider",
    "AnthropicError",
]
