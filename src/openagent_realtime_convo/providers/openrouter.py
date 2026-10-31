"""OpenRouter provider adapter for the provider-independent AI brain interface.

Phase 4, Step 2: Implements OpenRouterBrainProvider adhering to the BrainProvider
protocol using asynchronous HTTP requests via httpx. Does not log API keys,
authorization headers, or message contents.
"""

from __future__ import annotations

import httpx

from openagent_realtime_convo.brain import BrainError, BrainRequest, BrainResponse
from openagent_realtime_convo.config import AppConfig, ProviderSettings

OPENROUTER_API_URL: str = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL: str = "openai/gpt-4o-mini"


class OpenRouterError(BrainError):
    """Raised when OpenRouter API communication, configuration, or parsing fails."""


class OpenRouterBrainProvider:
    """Asynchronous OpenRouter provider adapter satisfying the BrainProvider protocol.

    Communicates with OpenRouter's chat completions endpoint using httpx.AsyncClient.
    Keeps API credentials and message contents strictly out of logs and representations.
    """

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize OpenRouter provider adapter.

        Args:
            api_key: OpenRouter API key.
            model: Optional model identifier; defaults to 'openai/gpt-4o-mini'.
            http_client: Optional injected httpx.AsyncClient (useful for testing or shared pools).
            timeout: HTTP request timeout in seconds (default: 30.0).

        Raises:
            OpenRouterError: If api_key or model is empty or invalid.
        """
        if not isinstance(api_key, str) or not api_key.strip():
            raise OpenRouterError("api_key must be a non-empty string")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise OpenRouterError("model must be a non-empty string when provided")

        self._api_key = api_key.strip()
        self.model = model.strip() if model is not None else DEFAULT_MODEL
        self._http_client = http_client
        self._timeout = timeout

    def __repr__(self) -> str:
        """Safe representation hiding secrets."""
        return f"OpenRouterBrainProvider(model={self.model!r})"

    @classmethod
    def from_settings(
        cls,
        settings: ProviderSettings,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> OpenRouterBrainProvider:
        """Construct provider from ProviderSettings.

        Args:
            settings: Provider settings containing name, api_key, and optional model.
            http_client: Optional injected httpx.AsyncClient.
            timeout: HTTP request timeout in seconds.

        Raises:
            OpenRouterError: If settings are not for openrouter.
        """
        if settings.name.lower() != "openrouter":
            raise OpenRouterError(f"Expected provider 'openrouter', got '{settings.name}'")
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
    ) -> OpenRouterBrainProvider:
        """Construct provider from AppConfig."""
        return cls.from_settings(config.provider, http_client=http_client, timeout=timeout)

    async def generate_response(self, request: BrainRequest) -> BrainResponse:
        """Generate an assistant response asynchronously via OpenRouter chat completions.

        Args:
            request: Validated BrainRequest containing user message.

        Returns:
            BrainResponse with assistant reply and model identifier.

        Raises:
            OpenRouterError: On network errors, HTTP status errors, or invalid responses.
        """
        if not isinstance(request, BrainRequest):
            raise OpenRouterError("request must be an instance of BrainRequest")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": request.message,
                }
            ],
        }

        try:
            if self._http_client is not None:
                response = await self._http_client.post(
                    OPENROUTER_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=self._timeout,
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        OPENROUTER_API_URL,
                        headers=headers,
                        json=payload,
                    )
        except httpx.HTTPStatusError as exc:
            raise OpenRouterError(
                f"OpenRouter request failed with HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise OpenRouterError(
                f"OpenRouter network communication error: {exc.__class__.__name__}"
            ) from exc

        if response.is_error:
            raise OpenRouterError(f"OpenRouter request failed with HTTP {response.status_code}")

        try:
            data = response.json()
        except Exception as exc:
            raise OpenRouterError("OpenRouter returned invalid JSON") from exc

        if not isinstance(data, dict):
            raise OpenRouterError("OpenRouter response is not a JSON object")

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise OpenRouterError("OpenRouter response missing valid choices")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise OpenRouterError("OpenRouter response choice is invalid")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise OpenRouterError("OpenRouter response choice missing message object")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise OpenRouterError("OpenRouter response contained empty or missing reply content")

        response_model = data.get("model")
        model_name: str | None = None
        if isinstance(response_model, str) and response_model.strip():
            model_name = response_model.strip()
        else:
            model_name = self.model

        try:
            return BrainResponse(reply=content.strip(), model=model_name)
        except BrainError as exc:
            raise OpenRouterError(f"Failed to create BrainResponse: {exc}") from exc


__all__ = [
    "DEFAULT_MODEL",
    "OPENROUTER_API_URL",
    "OpenRouterBrainProvider",
    "OpenRouterError",
]
