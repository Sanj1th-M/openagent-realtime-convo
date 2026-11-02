"""AI brain provider adapters and factory."""

from __future__ import annotations

from openagent_realtime_convo.brain import BrainError, BrainProvider
from openagent_realtime_convo.config import ProviderSettings
from openagent_realtime_convo.providers.anthropic import AnthropicBrainProvider, AnthropicError
from openagent_realtime_convo.providers.gemini import GeminiBrainProvider, GeminiError
from openagent_realtime_convo.providers.ollama import OllamaBrainProvider, OllamaError
from openagent_realtime_convo.providers.openai import OpenAIBrainProvider, OpenAIError
from openagent_realtime_convo.providers.openrouter import (
    OpenRouterBrainProvider,
    OpenRouterError,
)


def create_brain_provider(settings: ProviderSettings) -> BrainProvider:
    """Instantiate a BrainProvider adapter matching the given settings.

    Args:
        settings: Validated provider settings containing provider name, api_key, and model.

    Returns:
        BrainProvider: Initialized provider instance.

    Raises:
        BrainError: If the provider is unsupported or cannot be constructed.
    """
    provider_name = settings.name.strip().lower()
    if provider_name == "anthropic":
        return AnthropicBrainProvider.from_settings(settings)
    if provider_name == "gemini":
        return GeminiBrainProvider.from_settings(settings)
    if provider_name == "openrouter":
        return OpenRouterBrainProvider.from_settings(settings)
    if provider_name == "openai":
        return OpenAIBrainProvider.from_settings(settings)
    if provider_name == "ollama":
        return OllamaBrainProvider.from_settings(settings)
    raise BrainError(f"Unsupported brain provider: {settings.name}")


__all__ = [
    "AnthropicBrainProvider",
    "AnthropicError",
    "GeminiBrainProvider",
    "GeminiError",
    "OpenRouterBrainProvider",
    "OpenRouterError",
    "OpenAIBrainProvider",
    "OpenAIError",
    "OllamaBrainProvider",
    "OllamaError",
    "create_brain_provider",
]
