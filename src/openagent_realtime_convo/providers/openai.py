"""OpenAI adapter for the provider-independent AI brain interface.

This adapter calls OpenAI's non-streaming chat completions REST endpoint with
``httpx``. It does not log API credentials, authorization headers, request
messages, or response bodies.
"""

from __future__ import annotations

import json

import httpx

from openagent_realtime_convo.brain import BrainError, BrainRequest, BrainResponse
from openagent_realtime_convo.config import AppConfig, ProviderSettings

OPENAI_API_URL: str = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL: str = "gpt-4o-mini"


def _safe_error_details(response: httpx.Response) -> str:
    """Safely extract sanitized error code or message from response JSON.

    Never extracts headers, secrets, or prompt contents.
    """
    try:
        data = response.json()
    except (ValueError, json.JSONDecodeError):
        return ""

    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message")
            code_str = str(code).strip() if code is not None else ""
            msg_str = str(message).strip() if message is not None else ""
            if code_str and msg_str:
                return f" ({code_str}: {msg_str})"
            if msg_str:
                return f" ({msg_str})"
            if code_str:
                return f" ({code_str})"
        elif isinstance(error, str) and error.strip():
            return f" ({error.strip()})"
    return ""


class OpenAIError(BrainError):
    """Raised when OpenAI API communication, configuration, or parsing fails."""


class OpenAIBrainProvider:
    """Asynchronous OpenAI adapter satisfying the ``BrainProvider`` protocol."""

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
            raise OpenAIError("api_key must be a non-empty string")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise OpenAIError("model must be a non-empty string when provided")

        self._api_key = api_key.strip()
        self.model = model.strip() if model is not None else DEFAULT_MODEL
        self._http_client = http_client
        self._timeout = timeout

    def __repr__(self) -> str:
        """Return a safe representation that excludes credentials."""
        return f"OpenAIBrainProvider(model={self.model!r})"

    @classmethod
    def from_settings(
        cls,
        settings: ProviderSettings,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> OpenAIBrainProvider:
        """Construct an OpenAI adapter from validated provider settings."""
        if settings.name.lower() != "openai":
            raise OpenAIError(f"Expected provider 'openai', got '{settings.name}'")
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
    ) -> OpenAIBrainProvider:
        """Construct an OpenAI adapter from application configuration."""
        return cls.from_settings(config.provider, http_client=http_client, timeout=timeout)

    async def generate_response(self, request: BrainRequest) -> BrainResponse:
        """Generate a single-turn text reply through OpenAI chat completions."""
        if not isinstance(request, BrainRequest):
            raise OpenAIError("request must be an instance of BrainRequest")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": request.message}],
        }

        try:
            if self._http_client is not None:
                response = await self._http_client.post(
                    OPENAI_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=self._timeout,
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(OPENAI_API_URL, headers=headers, json=payload)
        except httpx.HTTPStatusError as exc:
            details = _safe_error_details(exc.response)
            raise OpenAIError(
                f"OpenAI request failed with HTTP {exc.response.status_code}{details}"
            ) from exc
        except httpx.RequestError as exc:
            raise OpenAIError(
                f"OpenAI network communication error: {exc.__class__.__name__}"
            ) from exc

        if response.is_error:
            details = _safe_error_details(response)
            raise OpenAIError(f"OpenAI request failed with HTTP {response.status_code}{details}")

        try:
            data = response.json()
        except Exception as exc:
            raise OpenAIError("OpenAI returned invalid JSON") from exc

        if not isinstance(data, dict):
            raise OpenAIError("OpenAI response is not a JSON object")
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise OpenAIError("OpenAI response missing valid choices")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise OpenAIError("OpenAI response choice is invalid")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise OpenAIError("OpenAI response choice missing message object")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise OpenAIError("OpenAI response contained empty or missing reply content")

        response_model = data.get("model")
        model_name = (
            response_model.strip()
            if isinstance(response_model, str) and response_model.strip()
            else self.model
        )
        try:
            return BrainResponse(reply=content.strip(), model=model_name)
        except BrainError as exc:
            raise OpenAIError(f"Failed to create BrainResponse: {exc}") from exc


__all__ = [
    "DEFAULT_MODEL",
    "OPENAI_API_URL",
    "OpenAIBrainProvider",
    "OpenAIError",
]
