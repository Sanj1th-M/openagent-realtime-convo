"""Provider-independent AI brain interface and conversation data models.

Phase 4, Step 1: Defines typed request and response models along with an
asynchronous provider interface protocol. This module does not implement API
clients, does not depend on external AI SDKs, and does not log message
contents or credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class BrainError(ValueError):
    """Raised when brain request/response models are invalid or brain processing fails."""


@dataclass(frozen=True, slots=True)
class BrainRequest:
    """Typed request model representing a user message to an AI provider.

    Attributes:
        message: The user's input message text.
        session_id: Optional identifier for conversation session tracking.
    """

    message: str
    session_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.message, str) or not self.message.strip():
            raise BrainError("message must be a non-empty string")
        if self.session_id is not None and (
            not isinstance(self.session_id, str) or not self.session_id.strip()
        ):
            raise BrainError("session_id must be a non-empty string when provided")

    @property
    def text(self) -> str:
        """Convenience alias for message."""
        return self.message


@dataclass(frozen=True, slots=True)
class BrainResponse:
    """Typed response model representing an assistant reply from an AI provider.

    Attributes:
        reply: The assistant's reply text.
        model: Optional provider model name that generated the response.
    """

    reply: str
    model: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.reply, str) or not self.reply.strip():
            raise BrainError("reply must be a non-empty string")
        if self.model is not None and (not isinstance(self.model, str) or not self.model.strip()):
            raise BrainError("model must be a non-empty string when provided")

    @property
    def text(self) -> str:
        """Convenience alias for reply."""
        return self.reply

    @property
    def message(self) -> str:
        """Convenience alias for reply."""
        return self.reply


@runtime_checkable
class BrainProvider(Protocol):
    """Asynchronous provider interface for AI brain implementations.

    Implementations can integrate with any provider (OpenAI, Gemini, Anthropic,
    local LLM) without coupling callers to a specific SDK.
    """

    async def generate_response(self, request: BrainRequest) -> BrainResponse:
        """Generate an assistant response asynchronously for the provided user request.

        Args:
            request: Validated user request model.

        Returns:
            Validated assistant response model.

        Raises:
            BrainError: When generation fails or inputs/outputs are invalid.
        """
        ...


# Aliases for flexibility across conversation coordinator call sites
Brain = BrainProvider
AIBrain = BrainProvider
UserMessage = BrainRequest
AssistantReply = BrainResponse

__all__ = [
    "AIBrain",
    "AssistantReply",
    "Brain",
    "BrainError",
    "BrainProvider",
    "BrainRequest",
    "BrainResponse",
    "UserMessage",
]
