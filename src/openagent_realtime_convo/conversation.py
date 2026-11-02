"""Provider-neutral boundary between finalized STT text and the AI brain.

This module deliberately has no microphone, Pipecat, or text-to-speech
dependency.  The caller supplies finalized transcript text and receives a
validated ``BrainResponse`` to decide how it should be displayed or spoken.
"""

from __future__ import annotations

import asyncio

from .brain import BrainError, BrainProvider, BrainRequest, BrainResponse


class TranscriptHandlingError(BrainError):
    """Raised when a finalized transcript cannot safely be processed."""


class TranscriptBrainCoordinator:
    """Turn one finalized STT transcript into one provider response."""

    def __init__(self, provider: BrainProvider, *, timeout_seconds: float = 30.0) -> None:
        if not isinstance(provider, BrainProvider):
            raise TranscriptHandlingError("provider must implement BrainProvider")
        if isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise TranscriptHandlingError("timeout_seconds must be a positive number")
        self._provider = provider
        self._timeout_seconds = timeout_seconds

    async def respond_to_transcript(
        self, transcript: str, *, session_id: str | None = None
    ) -> BrainResponse:
        """Pass non-empty finalized STT text to the provider and return its reply."""
        try:
            request = BrainRequest(message=transcript, session_id=session_id)
        except BrainError as exc:
            raise TranscriptHandlingError(
                "finalized transcript must be a non-empty string"
            ) from exc

        try:
            response = await asyncio.wait_for(
                self._provider.generate_response(request), timeout=self._timeout_seconds
            )
        except asyncio.TimeoutError as exc:
            raise TranscriptHandlingError(
                "Brain provider timed out while generating a response"
            ) from exc
        except BrainError:
            raise
        except Exception as exc:
            raise TranscriptHandlingError(
                "Brain provider failed while generating a response"
            ) from exc

        if not isinstance(response, BrainResponse):
            raise TranscriptHandlingError("Brain provider returned an invalid response")
        return response


__all__ = ["TranscriptBrainCoordinator", "TranscriptHandlingError"]
