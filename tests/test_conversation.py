"""Integration tests for the finalized-STT-text, brain-provider, and TTS boundary."""

from __future__ import annotations

import asyncio
import json
import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from openagent_realtime_convo.brain import BrainError, BrainProvider, BrainRequest, BrainResponse
from openagent_realtime_convo.config import ConfigurationError
from openagent_realtime_convo.conversation import (
    SpeechService,
    TranscriptBrainCoordinator,
    TranscriptHandlingError,
    main,
    transcript_coordinator_from_environment,
)
from openagent_realtime_convo.providers import GeminiBrainProvider, GeminiError
from openagent_realtime_convo.providers.gemini import GEMINI_API_URL
from openagent_realtime_convo.tts import SpeechOutput, TTSError


class RecordingProvider:
    def __init__(self, response: BrainResponse | object | None = None) -> None:
        self.requests: list[BrainRequest] = []
        self.response = response if response is not None else BrainResponse(reply="Brain reply")
        self.closed = False

    async def generate_response(self, request: BrainRequest) -> BrainResponse:
        self.requests.append(request)
        return self.response  # type: ignore[return-value]

    async def aclose(self) -> None:
        self.closed = True


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


# ---------------------------------------------------------------------------
# Integration with GeminiBrainProvider (mocked HTTP transport)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_coordinator_sends_transcript_to_gemini_and_returns_response() -> None:
    """Transcript correctly flows through coordinator into GeminiBrainProvider and back."""
    recorded_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(
            status_code=200,
            json={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": "Loud and clear, sir."}],
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiBrainProvider(
            api_key="mock-gemini-secret-key",
            model="gemini-3.5-flash",
            http_client=client,
        )
        coordinator = TranscriptBrainCoordinator(provider)

        transcript = "Jarvis, can you hear me?"
        response = await coordinator.respond_to_transcript(transcript)

    assert response == BrainResponse(reply="Loud and clear, sir.", model="gemini-3.5-flash")
    assert response.reply == "Loud and clear, sir."
    assert response.model == "gemini-3.5-flash"

    # Verify Gemini request contract
    assert len(recorded_requests) == 1
    req = recorded_requests[0]
    assert req.method == "POST"
    assert str(req.url) == f"{GEMINI_API_URL}/gemini-3.5-flash:generateContent"
    assert req.headers["x-goog-api-key"] == "mock-gemini-secret-key"
    assert req.headers["Content-Type"] == "application/json"
    body = json.loads(req.content.decode("utf-8"))
    assert body == {"contents": [{"role": "user", "parts": [{"text": transcript}]}]}


@pytest.mark.anyio
async def test_coordinator_gemini_http_error_bubbles_safely() -> None:
    """HTTP errors from Gemini bubble through coordinator as GeminiError without leaking secrets."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=403, json={"error": {"message": "forbidden"}})

    secret = "mock-secret-must-not-leak"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiBrainProvider(api_key=secret, http_client=client)
        coordinator = TranscriptBrainCoordinator(provider)

        with pytest.raises(GeminiError) as exc_info:
            await coordinator.respond_to_transcript("Test prompt")

    assert "HTTP 403" in str(exc_info.value)
    assert secret not in str(exc_info.value)


@pytest.mark.anyio
async def test_coordinator_gemini_malformed_response_raises_safely() -> None:
    """Malformed Gemini payloads bubble as GeminiError."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json={"candidates": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiBrainProvider(api_key="mock-key", http_client=client)
        coordinator = TranscriptBrainCoordinator(provider)

        with pytest.raises(GeminiError, match="missing valid candidates"):
            await coordinator.respond_to_transcript("Test prompt")


# ---------------------------------------------------------------------------
# Integration with TTS / SpeechService
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_coordinator_speaks_successful_brain_response_exactly_once() -> None:
    """A successful AI response is forwarded to SpeechService.speak exactly once."""
    expected_response = BrainResponse(reply="Good day, sir.", model="test-model")
    provider = RecordingProvider(expected_response)
    mock_speech = AsyncMock(spec=SpeechService)

    coordinator = TranscriptBrainCoordinator(provider, speech_output=mock_speech)
    result = await coordinator.respond_to_transcript("Hello")

    assert result == expected_response
    mock_speech.speak.assert_awaited_once_with(expected_response)


@pytest.mark.anyio
async def test_coordinator_returns_response_when_speech_output_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The AI response is still returned even if speech synthesis or playback fails."""
    expected_response = BrainResponse(reply="System online.", model="test-model")
    provider = RecordingProvider(expected_response)
    mock_speech = AsyncMock(spec=SpeechService)
    mock_speech.speak.side_effect = TTSError("Local audio playback failed")

    coordinator = TranscriptBrainCoordinator(provider, speech_output=mock_speech)
    with caplog.at_level(logging.WARNING):
        result = await coordinator.respond_to_transcript("Status check")

    # The caller still receives the text response!
    assert result == expected_response
    mock_speech.speak.assert_awaited_once_with(expected_response)
    assert "event=tts_output_failed error=TTSError" in caplog.text


@pytest.mark.anyio
async def test_coordinator_does_not_call_speech_output_on_empty_reply() -> None:
    """If the response reply is somehow blank or whitespace, speak() is not called."""

    # Custom double to simulate edge case bypassing BrainResponse validation
    class BlankProvider:
        async def generate_response(self, request: BrainRequest) -> BrainResponse:
            # Subclass or mock object with blank text
            obj = object.__new__(BrainResponse)
            object.__setattr__(obj, "reply", "   ")
            object.__setattr__(obj, "model", "test")
            return obj

    mock_speech = AsyncMock(spec=SpeechService)
    coordinator = TranscriptBrainCoordinator(
        BlankProvider(),
        speech_output=mock_speech,
    )
    result = await coordinator.respond_to_transcript("ping")

    assert result.reply == "   "
    mock_speech.speak.assert_not_called()


@pytest.mark.anyio
async def test_coordinator_closes_speech_output_and_provider_resources() -> None:
    """aclose() correctly invokes aclose on both speech output and provider."""
    provider = RecordingProvider()
    mock_speech = AsyncMock(spec=SpeechService)
    mock_speech.aclose = AsyncMock()

    coordinator = TranscriptBrainCoordinator(provider, speech_output=mock_speech)
    await coordinator.aclose()

    assert provider.closed is True
    mock_speech.aclose.assert_awaited_once()


@pytest.mark.anyio
async def test_coordinator_aclose_error_in_speech_output_still_closes_provider() -> None:
    """Provider aclose is executed even if speech_output.aclose raises an error."""
    provider = RecordingProvider()
    mock_speech = AsyncMock(spec=SpeechService)
    mock_speech.aclose = AsyncMock(side_effect=RuntimeError("close failed"))

    coordinator = TranscriptBrainCoordinator(provider, speech_output=mock_speech)
    with pytest.raises(RuntimeError, match="close failed"):
        await coordinator.aclose()

    assert provider.closed is True


def test_coordinator_rejects_invalid_speech_output_type() -> None:
    """speech_output must conform to SpeechService protocol."""
    provider = RecordingProvider()
    with pytest.raises(TranscriptHandlingError, match="must implement SpeechService"):
        TranscriptBrainCoordinator(
            provider,
            speech_output="not_a_speech_service",  # type: ignore[arg-type]
        )


@pytest.mark.anyio
async def test_coordinator_async_context_manager() -> None:
    """TranscriptBrainCoordinator can be used as an async context manager."""
    provider = RecordingProvider()
    mock_speech = AsyncMock(spec=SpeechService)
    mock_speech.aclose = AsyncMock()

    async with TranscriptBrainCoordinator(provider, speech_output=mock_speech) as coord:
        assert isinstance(coord, TranscriptBrainCoordinator)

    assert provider.closed is True
    mock_speech.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# Factory: transcript_coordinator_from_environment
# ---------------------------------------------------------------------------


def test_transcript_coordinator_from_environment_builds_gemini() -> None:
    env = {
        "OPENAGENT_PROVIDER": "gemini",
        "GEMINI_API_KEY": "test-gemini-key",
        "GEMINI_MODEL": "gemini-3.5-flash",
    }
    coordinator = transcript_coordinator_from_environment(env, load_env=False)
    assert isinstance(coordinator, TranscriptBrainCoordinator)
    assert isinstance(coordinator._provider, GeminiBrainProvider)
    assert coordinator._provider.model == "gemini-3.5-flash"
    assert "test-gemini-key" not in repr(coordinator._provider)
    assert coordinator._speech_output is None


def test_transcript_coordinator_from_environment_requires_valid_config() -> None:
    with pytest.raises(ConfigurationError):
        transcript_coordinator_from_environment({"OPENAGENT_PROVIDER": "unknown"}, load_env=False)


def test_transcript_coordinator_from_environment_with_enable_tts() -> None:
    env = {
        "OPENAGENT_PROVIDER": "gemini",
        "GEMINI_API_KEY": "test-gemini-key",
        "DEEPGRAM_API_KEY": "test-dg-key",
    }
    coordinator = transcript_coordinator_from_environment(env, enable_tts=True, load_env=False)
    assert coordinator._speech_output is not None
    assert isinstance(coordinator._speech_output, SpeechOutput)


def test_transcript_coordinator_from_environment_with_custom_speech_output() -> None:
    mock_speech = AsyncMock(spec=SpeechService)
    env = {
        "OPENAGENT_PROVIDER": "gemini",
        "GEMINI_API_KEY": "test-gemini-key",
    }
    coordinator = transcript_coordinator_from_environment(
        env, speech_output=mock_speech, load_env=False
    )
    assert coordinator._speech_output is mock_speech


# ---------------------------------------------------------------------------
# CLI / Diagnostic Entry Point: main()
# ---------------------------------------------------------------------------


def test_conversation_main_success(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_provider = AsyncMock(spec=BrainProvider)
    mock_provider.generate_response.return_value = BrainResponse(
        reply="Ready to assist.", model="gemini-3.5-flash"
    )

    with patch(
        "openagent_realtime_convo.conversation.create_brain_provider",
        return_value=mock_provider,
    ):
        monkeypatch.setenv("OPENAGENT_PROVIDER", "gemini")
        monkeypatch.setenv("GEMINI_API_KEY", "mock-key")
        code = main(["Hello from test"])

    assert code == 0
    captured = capsys.readouterr()
    assert "Transcript: Hello from test" in captured.out
    assert "Response: Ready to assist." in captured.out
    assert "Model: gemini-3.5-flash" in captured.out


def test_conversation_main_missing_config(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAGENT_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAGENT_PROVIDER_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with patch(
        "openagent_realtime_convo.conversation.AppConfig.from_brain_environment"
    ) as mock_cfg:
        mock_cfg.side_effect = ConfigurationError("OPENAGENT_PROVIDER must be set")
        code = main([])

    assert code == 2
    captured = capsys.readouterr()
    assert "Configuration error" in captured.err


def test_conversation_main_handles_brain_error(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_provider = AsyncMock(spec=BrainProvider)
    mock_provider.generate_response.side_effect = GeminiError("Gemini request failed with HTTP 429")

    with patch(
        "openagent_realtime_convo.conversation.create_brain_provider",
        return_value=mock_provider,
    ):
        monkeypatch.setenv("OPENAGENT_PROVIDER", "gemini")
        monkeypatch.setenv("GEMINI_API_KEY", "mock-key")
        code = main(["Trigger rate limit"])

    assert code == 1
    captured = capsys.readouterr()
    assert "Brain error: Gemini request failed with HTTP 429" in captured.err


def test_conversation_main_with_tts_flag(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_provider = AsyncMock(spec=BrainProvider)
    mock_provider.generate_response.return_value = BrainResponse(
        reply="Vocal reply.", model="gemini-3.5-flash"
    )
    mock_speech = AsyncMock(spec=SpeechService)

    with (
        patch(
            "openagent_realtime_convo.conversation.create_brain_provider",
            return_value=mock_provider,
        ),
        patch(
            "openagent_realtime_convo.tts.speech_output_from_environment",
            return_value=mock_speech,
        ),
    ):
        monkeypatch.setenv("OPENAGENT_PROVIDER", "gemini")
        monkeypatch.setenv("GEMINI_API_KEY", "mock-key")
        code = main(["Hello with TTS", "--tts"])

    assert code == 0
    mock_speech.speak.assert_awaited_once_with(
        BrainResponse(reply="Vocal reply.", model="gemini-3.5-flash")
    )
    mock_speech.aclose.assert_awaited_once()
    captured = capsys.readouterr()
    assert "Speech output: enabled" in captured.out
    assert "Response: Vocal reply." in captured.out
