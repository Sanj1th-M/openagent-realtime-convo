"""Integration tests for the finalized-STT-text to brain-provider boundary."""

from __future__ import annotations

import asyncio

import pytest

from openagent_realtime_convo.brain import BrainError, BrainRequest, BrainResponse
from openagent_realtime_convo.conversation import (
    TranscriptBrainCoordinator,
    TranscriptHandlingError,
)


class RecordingProvider:
    def __init__(self, response: BrainResponse | object | None = None) -> None:
        self.requests: list[BrainRequest] = []
        self.response = response if response is not None else BrainResponse(reply="Brain reply")

    async def generate_response(self, request: BrainRequest) -> BrainResponse:
        self.requests.append(request)
        return self.response  # type: ignore[return-value]


class FailingProvider:
    async def generate_response(self, request: BrainRequest) -> BrainResponse:
        raise BrainError("provider unavailable")


class SlowProvider:
    async def generate_response(self, request: BrainRequest) -> BrainResponse:
        await asyncio.sleep(1)
        return BrainResponse(reply="late")


@pytest.mark.anyio
async def test_finalized_transcript_is_sent_to_provider_and_reply_is_returned() -> None:
    provider = RecordingProvider(BrainResponse(reply="The answer", model="test-model"))
    coordinator = TranscriptBrainCoordinator(provider)

    response = await coordinator.respond_to_transcript("What time is it?", session_id="session-1")

    assert response == BrainResponse(reply="The answer", model="test-model")
    assert provider.requests == [BrainRequest(message="What time is it?", session_id="session-1")]


@pytest.mark.anyio
async def test_empty_transcript_is_rejected_without_calling_provider() -> None:
    provider = RecordingProvider()
    coordinator = TranscriptBrainCoordinator(provider)

    with pytest.raises(TranscriptHandlingError, match="finalized transcript"):
        await coordinator.respond_to_transcript(" \t")

    assert provider.requests == []


@pytest.mark.anyio
async def test_provider_error_is_returned_without_hiding_actionable_error() -> None:
    coordinator = TranscriptBrainCoordinator(FailingProvider())

    with pytest.raises(BrainError, match="provider unavailable"):
        await coordinator.respond_to_transcript("Hello")


@pytest.mark.anyio
async def test_provider_timeout_is_safe_and_actionable() -> None:
    coordinator = TranscriptBrainCoordinator(SlowProvider(), timeout_seconds=0.01)

    with pytest.raises(TranscriptHandlingError, match="timed out"):
        await coordinator.respond_to_transcript("Hello")


@pytest.mark.anyio
async def test_malformed_provider_response_is_rejected() -> None:
    coordinator = TranscriptBrainCoordinator(RecordingProvider(response="not a response"))

    with pytest.raises(TranscriptHandlingError, match="invalid response"):
        await coordinator.respond_to_transcript("Hello")
