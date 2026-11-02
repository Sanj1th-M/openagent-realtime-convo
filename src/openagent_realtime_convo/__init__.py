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
from .config import (
    AppConfig,
    AudioSettings,
    ConfigurationError,
    ProviderSettings,
    load_environment,
)
from .conversation import TranscriptBrainCoordinator, TranscriptHandlingError
from .providers import (
    AnthropicBrainProvider,
    AnthropicError,
    GeminiBrainProvider,
    GeminiError,
    OllamaBrainProvider,
    OllamaError,
    OpenAIBrainProvider,
    OpenAIError,
    OpenRouterBrainProvider,
    OpenRouterError,
    create_brain_provider,
)

__all__ = [
    "AIBrain",
    "AnthropicBrainProvider",
    "AnthropicError",
    "AppConfig",
    "AssistantReply",
    "AudioSettings",
    "Brain",
    "BrainError",
    "BrainProvider",
    "BrainRequest",
    "BrainResponse",
    "ConfigurationError",
    "TranscriptBrainCoordinator",
    "TranscriptHandlingError",
    "GeminiBrainProvider",
    "GeminiError",
    "OpenAIBrainProvider",
    "OpenAIError",
    "OllamaBrainProvider",
    "OllamaError",
    "OpenRouterBrainProvider",
    "OpenRouterError",
    "ProviderSettings",
    "UserMessage",
    "create_brain_provider",
    "load_environment",
]
