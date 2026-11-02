"""Google Gemini adapter for the provider-independent AI brain interface.

This adapter calls Gemini's ``generateContent`` REST endpoint with ``httpx``.
It deliberately does not log API credentials, request messages, or API response
bodies, which can contain user content.
"""

from __future__ import annotations

import httpx

from openagent_realtime_convo.brain import BrainError, BrainRequest, BrainResponse
from openagent_realtime_convo.config import AppConfig, ProviderSettings

GEMINI_API_URL: str = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL: str = "gemini-2.0-flash"


class GeminiError(BrainError):
    """Raised when Gemini API communication, configuration, or parsing fails."""


class GeminiBrainProvider:
    """Asynchronous Google Gemini adapter satisfying the ``BrainProvider`` protocol."""

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
            raise GeminiError("api_key must be a non-empty string")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise GeminiError("model must be a non-empty string when provided")

        self._api_key = api_key.strip()
        self.model = model.strip() if model is not None else DEFAULT_MODEL
        self._http_client = http_client
        self._timeout = timeout

    def __repr__(self) -> str:
        """Return a safe representation that excludes credentials."""
        return f"GeminiBrainProvider(model={self.model!r})"

    @classmethod
    def from_settings(
        cls,
        settings: ProviderSettings,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> GeminiBrainProvider:
        """Construct a Gemini adapter from validated provider settings."""
        if settings.name.lower() != "gemini":
            raise GeminiError(f"Expected provider 'gemini', got '{settings.name}'")
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
    ) -> GeminiBrainProvider:
        """Construct a Gemini adapter from application configuration."""
        return cls.from_settings(config.provider, http_client=http_client, timeout=timeout)

    async def generate_response(self, request: BrainRequest) -> BrainResponse:
        """Generate a single-turn text reply through Gemini's REST API."""
        if not isinstance(request, BrainRequest):
            raise GeminiError("request must be an instance of BrainRequest")

        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": request.message}],
                }
            ]
        }
        url = f"{GEMINI_API_URL}/{self.model}:generateContent"

        try:
            if self._http_client is not None:
                response = await self._http_client.post(
                    url, headers=headers, json=payload, timeout=self._timeout
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPStatusError as exc:
            raise GeminiError(
                f"Gemini request failed with HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise GeminiError(
                f"Gemini network communication error: {exc.__class__.__name__}"
            ) from exc

        if response.is_error:
            raise GeminiError(f"Gemini request failed with HTTP {response.status_code}")

        try:
            data = response.json()
        except Exception as exc:
            raise GeminiError("Gemini returned invalid JSON") from exc

        if not isinstance(data, dict):
            raise GeminiError("Gemini response is not a JSON object")

        candidates = data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise GeminiError("Gemini response missing valid candidates")
        first_candidate = candidates[0]
        if not isinstance(first_candidate, dict):
            raise GeminiError("Gemini response candidate is invalid")
        content = first_candidate.get("content")
        if not isinstance(content, dict):
            raise GeminiError("Gemini response candidate missing content object")
        parts = content.get("parts")
        if not isinstance(parts, list) or not parts:
            raise GeminiError("Gemini response content missing valid parts")

        text_parts = [
            part["text"]
            for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
        reply = "".join(text_parts).strip()
        if not reply:
            raise GeminiError("Gemini response contained empty or missing reply content")

        try:
            return BrainResponse(reply=reply, model=self.model)
        except BrainError as exc:
            raise GeminiError(f"Failed to create BrainResponse: {exc}") from exc


__all__ = [
    "DEFAULT_MODEL",
    "GEMINI_API_URL",
    "GeminiBrainProvider",
    "GeminiError",
]
