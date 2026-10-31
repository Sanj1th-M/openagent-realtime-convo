"""Unit tests for the provider-independent AI brain interface and data models."""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from openagent_realtime_convo.brain import (
    AIBrain,
    AssistantReply,
    Brain,
    BrainError,
    BrainProvider,
    BrainRequest,
    BrainResponse,
    UserMessage,
)


class MockBrainProvider:
    """Mock implementation of the BrainProvider Protocol for testing."""

    def __init__(self, canned_reply: str = "Hello, how can I help you?") -> None:
        self.canned_reply = canned_reply
        self.received_requests: list[BrainRequest] = []

    async def generate_response(self, request: BrainRequest) -> BrainResponse:
        self.received_requests.append(request)
        if request.message == "trigger_error":
            raise BrainError("Simulated provider failure")
        return BrainResponse(reply=self.canned_reply, model="mock-model")


class IncompleteBrainProvider:
    """Class missing the generate_response method."""

    pass


# ---------------------------------------------------------------------------
# Tests: BrainRequest
# ---------------------------------------------------------------------------


def test_brain_request_valid_minimal() -> None:
    req = BrainRequest(message="What is the weather today?")
    assert req.message == "What is the weather today?"
    assert req.text == "What is the weather today?"
    assert req.session_id is None


def test_brain_request_valid_with_session() -> None:
    req = BrainRequest(message="Tell me a joke", session_id="session-123")
    assert req.message == "Tell me a joke"
    assert req.text == "Tell me a joke"
    assert req.session_id == "session-123"


def test_brain_request_immutability() -> None:
    req = BrainRequest(message="Original message")
    with pytest.raises(FrozenInstanceError):
        req.message = "New message"  # type: ignore[misc]


@pytest.mark.parametrize(
    "invalid_message",
    [
        "",
        "   ",
        "\t\n",
        123,
        None,
        [],
    ],
)
def test_brain_request_invalid_message_raises(invalid_message: Any) -> None:
    with pytest.raises(BrainError, match="message must be a non-empty string"):
        BrainRequest(message=invalid_message)


@pytest.mark.parametrize(
    "invalid_session_id",
    [
        "",
        "   ",
        "\t\n",
        123,
        [],
    ],
)
def test_brain_request_invalid_session_id_raises(invalid_session_id: Any) -> None:
    with pytest.raises(BrainError, match="session_id must be a non-empty string when provided"):
        BrainRequest(message="Valid message", session_id=invalid_session_id)


def test_brain_request_type_alias() -> None:
    req = UserMessage(message="Hello from alias")
    assert isinstance(req, BrainRequest)


# ---------------------------------------------------------------------------
# Tests: BrainResponse
# ---------------------------------------------------------------------------


def test_brain_response_valid_minimal() -> None:
    res = BrainResponse(reply="I am doing well, thank you.")
    assert res.reply == "I am doing well, thank you."
    assert res.text == "I am doing well, thank you."
    assert res.message == "I am doing well, thank you."
    assert res.model is None


def test_brain_response_valid_with_model() -> None:
    res = BrainResponse(reply="Confirmed.", model="gpt-4o")
    assert res.reply == "Confirmed."
    assert res.model == "gpt-4o"


def test_brain_response_immutability() -> None:
    res = BrainResponse(reply="Original reply")
    with pytest.raises(FrozenInstanceError):
        res.reply = "New reply"  # type: ignore[misc]


@pytest.mark.parametrize(
    "invalid_reply",
    [
        "",
        "   ",
        "\t\n",
        123,
        None,
        [],
    ],
)
def test_brain_response_invalid_reply_raises(invalid_reply: Any) -> None:
    with pytest.raises(BrainError, match="reply must be a non-empty string"):
        BrainResponse(reply=invalid_reply)


@pytest.mark.parametrize(
    "invalid_model",
    [
        "",
        "   ",
        "\t\n",
        123,
        [],
    ],
)
def test_brain_response_invalid_model_raises(invalid_model: Any) -> None:
    with pytest.raises(BrainError, match="model must be a non-empty string when provided"):
        BrainResponse(reply="Valid reply", model=invalid_model)


def test_brain_response_type_alias() -> None:
    res = AssistantReply(reply="Hello from alias")
    assert isinstance(res, BrainResponse)


# ---------------------------------------------------------------------------
# Tests: BrainProvider Protocol & Mock Provider
# ---------------------------------------------------------------------------


def test_mock_provider_conforms_to_protocol() -> None:
    provider = MockBrainProvider()
    assert isinstance(provider, BrainProvider)
    assert isinstance(provider, Brain)
    assert isinstance(provider, AIBrain)


def test_incomplete_provider_does_not_conform_to_protocol() -> None:
    incomplete = IncompleteBrainProvider()
    assert not isinstance(incomplete, BrainProvider)


def test_mock_provider_generates_response() -> None:
    provider = MockBrainProvider(canned_reply="42 is the answer.")
    request = BrainRequest(message="What is the answer?", session_id="ses-1")

    async def call_provider() -> BrainResponse:
        return await provider.generate_response(request)

    response = asyncio.run(call_provider())
    assert isinstance(response, BrainResponse)
    assert response.reply == "42 is the answer."
    assert response.model == "mock-model"
    assert len(provider.received_requests) == 1
    assert provider.received_requests[0] == request


def test_mock_provider_error_propagation() -> None:
    provider = MockBrainProvider()
    request = BrainRequest(message="trigger_error")

    async def call_provider() -> BrainResponse:
        return await provider.generate_response(request)

    with pytest.raises(BrainError, match="Simulated provider failure"):
        asyncio.run(call_provider())
