"""Configuration primitives and brain interfaces for OpenAgent's realtime conversation service."""

from .brain import (
    AIBrain,
    AssistantReply,
    Brain,
    BrainError,
    BrainProvider,
    BrainRequest,
    BrainResponse,
    UserMessage,
)
from .config import AppConfig, AudioSettings, ConfigurationError, ProviderSettings
from .providers import OpenRouterBrainProvider, OpenRouterError, create_brain_provider

__all__ = [
    "AIBrain",
    "AppConfig",
    "AssistantReply",
    "AudioSettings",
    "Brain",
    "BrainError",
    "BrainProvider",
    "BrainRequest",
    "BrainResponse",
    "ConfigurationError",
    "OpenRouterBrainProvider",
    "OpenRouterError",
    "ProviderSettings",
    "UserMessage",
    "create_brain_provider",
]
