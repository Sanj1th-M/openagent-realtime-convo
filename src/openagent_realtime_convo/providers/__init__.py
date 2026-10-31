"""AI brain provider adapters and factory."""

from __future__ import annotations

from openagent_realtime_convo.brain import BrainError, BrainProvider
from openagent_realtime_convo.config import ProviderSettings
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
    if provider_name == "openrouter":
        return OpenRouterBrainProvider.from_settings(settings)
    raise BrainError(f"Unsupported brain provider: {settings.name}")


__all__ = [
    "OpenRouterBrainProvider",
    "OpenRouterError",
    "create_brain_provider",
]
