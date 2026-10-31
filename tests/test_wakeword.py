"""Tests for the Phase-4 wake-word coordinator.

All tests use injected fakes — no openagent-wakeword installation, no physical
microphone, and no live Deepgram credentials are required.
"""

from __future__ import annotations

import asyncio
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from openagent_realtime_convo.config import AudioSettings
from openagent_realtime_convo.speech import SpeechConfig, SpeechRuntimeError
from openagent_realtime_convo.wakeword import (
    WakeWordCoordinator,
    WakeWordCoordinatorError,
    coordinator_config_from_environment,
)

# ---------------------------------------------------------------------------
# Fake detector
# ---------------------------------------------------------------------------


class FakeDetector:
    """Synchronous test double for WakeWordDetector.

    Records every method call and exposes a helper to fire a fake wake event.
    """

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._callback: Any = None

    def add_callback(self, cb: Any) -> None:
        self.calls.append("add_callback")
        self._callback = cb

    def start(self) -> None:
        self.calls.append("start")

    def stop(self) -> None:
        self.calls.append("stop")

    def pause(self) -> None:
        self.calls.append("pause")

    def resume(self) -> None:
        self.calls.append("resume")

    def fire_wake(self) -> None:
        """Simulate the audio thread firing a WakeWordEvent."""
        if self._callback is not None:
            self._callback(MagicMock())  # event object doesn't matter for these tests


def _speech_config() -> SpeechConfig:
    return SpeechConfig(api_key="not-a-real-key", audio=AudioSettings())


def _make_coordinator(
    detector: FakeDetector,
    stt_coro: Any,
    *,
    stt_timeout: float = 30.0,
    stream: StringIO | None = None,
) -> WakeWordCoordinator:
    """Build a coordinator whose STT call is replaced by stt_coro."""
    coord = WakeWordCoordinator(
        detector,
        _speech_config(),
        stt_timeout_seconds=stt_timeout,
        transcript_stream=stream or StringIO(),
    )
    # Inject STT coroutine; replace internal _run_stt_with_timeout.
    coord._stt_override = stt_coro  # type: ignore[attr-defined]
    return coord


# ---------------------------------------------------------------------------
# Helpers to run one cycle of the loop with an external cancellation
# ---------------------------------------------------------------------------


async def _run_one_cycle(
    detector: FakeDetector,
    stt_coro: Any,
    *,
    stt_timeout: float = 30.0,
    stream: StringIO | None = None,
) -> WakeWordCoordinator:
    """Run the coordinator for exactly one wake+STT cycle, then cancel."""
    coord = WakeWordCoordinator(
        detector,
        _speech_config(),
        stt_timeout_seconds=stt_timeout,
        transcript_stream=stream or StringIO(),
    )

    stt_calls: list[int] = []

    # Patch run_speech_to_text inside the wakeword module.
    async def fake_stt(*_a: Any, **_kw: Any) -> None:
        stt_calls.append(1)
        await stt_coro()

    async def drive() -> None:
        task = asyncio.create_task(coord.run())
        # Wait until the coordinator is waiting in standby.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        # Fire wake from the "audio thread" (same thread is fine in tests).
        detector.fire_wake()
        # Let the active phase run.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await asyncio.sleep(0.05)
        # Cancel after one cycle.
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    with patch(
        "openagent_realtime_convo.wakeword.run_speech_to_text",
        side_effect=fake_stt,
    ):
        await drive()

    return coord


# ---------------------------------------------------------------------------
# Tests: state machine transitions
# ---------------------------------------------------------------------------


def test_coordinator_calls_start_and_stop_on_detector() -> None:
    """detector.start() is called on run(); detector.stop() is called in finally."""

    detector = FakeDetector()

    async def run() -> None:
        task = asyncio.create_task(
            WakeWordCoordinator(
                detector,
                _speech_config(),
                transcript_stream=StringIO(),
            ).run()
        )
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    with patch("openagent_realtime_convo.wakeword.run_speech_to_text"):
        asyncio.run(run())

    assert "start" in detector.calls
    assert "stop" in detector.calls
    # stop must come after start
    assert detector.calls.index("stop") > detector.calls.index("start")


def test_coordinator_pauses_detector_before_stt() -> None:
    """detector.pause() must be called before the STT coroutine runs."""
    detector = FakeDetector()
    pause_before_stt: list[bool] = []

    async def stt_coro() -> None:
        pause_before_stt.append("pause" in detector.calls)

    asyncio.run(_run_one_cycle(detector, stt_coro))

    assert pause_before_stt == [True], "pause() must be called before STT starts"


def test_coordinator_resumes_detector_after_stt_completes() -> None:
    """detector.resume() is called after a successful STT run."""
    detector = FakeDetector()

    async def stt_coro() -> None:
        pass  # completes normally

    asyncio.run(_run_one_cycle(detector, stt_coro))

    assert "resume" in detector.calls
    # resume must come after pause
    assert detector.calls.index("resume") > detector.calls.index("pause")


def test_coordinator_resumes_after_stt_timeout() -> None:
    """When STT times out, the coordinator resumes the detector and does not crash."""
    detector = FakeDetector()

    async def stt_coro() -> None:
        await asyncio.sleep(999)  # never finishes within short timeout

    asyncio.run(_run_one_cycle(detector, stt_coro, stt_timeout=0.02))

    assert "resume" in detector.calls


def test_coordinator_resumes_after_stt_runtime_error() -> None:
    """When STT raises SpeechRuntimeError, the coordinator resumes and does not crash."""
    detector = FakeDetector()

    async def stt_coro() -> None:
        raise SpeechRuntimeError("microphone failed")

    asyncio.run(_run_one_cycle(detector, stt_coro))

    assert "resume" in detector.calls


def test_coordinator_stops_detector_on_cancel() -> None:
    """detector.stop() is called even when the task is cancelled before any wake."""
    detector = FakeDetector()

    async def run() -> None:
        task = asyncio.create_task(
            WakeWordCoordinator(
                detector,
                _speech_config(),
                transcript_stream=StringIO(),
            ).run()
        )
        # Cancel immediately, before any wake event.
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    with patch("openagent_realtime_convo.wakeword.run_speech_to_text"):
        asyncio.run(run())

    assert "stop" in detector.calls


def test_coordinator_prints_acknowledgement_before_stt() -> None:
    """The acknowledgement message is printed to the transcript stream before STT runs."""
    detector = FakeDetector()
    output = StringIO()
    stt_saw_ack: list[bool] = []

    async def stt_coro() -> None:
        stt_saw_ack.append("Yes sir" in output.getvalue())

    asyncio.run(_run_one_cycle(detector, stt_coro, stream=output))

    assert stt_saw_ack == [True], "Acknowledgement must be printed before STT"


# ---------------------------------------------------------------------------
# Tests: thread-safe callback
# ---------------------------------------------------------------------------


def test_wake_callback_uses_call_soon_threadsafe() -> None:
    """_on_wake_detected schedules the event.set via call_soon_threadsafe."""
    detector = FakeDetector()
    coord = WakeWordCoordinator(
        detector,
        _speech_config(),
        transcript_stream=StringIO(),
    )

    mock_loop = MagicMock()
    mock_event = MagicMock()
    mock_event.is_set.return_value = False
    coord._loop = mock_loop
    coord._wake_event = mock_event

    coord._on_wake_detected(MagicMock())

    mock_loop.call_soon_threadsafe.assert_called_once_with(mock_event.set)


def test_wake_callback_ignores_duplicate_during_active() -> None:
    """When _wake_event is already set, a second detection is silently ignored."""
    detector = FakeDetector()
    coord = WakeWordCoordinator(
        detector,
        _speech_config(),
        transcript_stream=StringIO(),
    )

    mock_loop = MagicMock()
    mock_event = MagicMock()
    mock_event.is_set.return_value = True  # already active
    coord._loop = mock_loop
    coord._wake_event = mock_event

    coord._on_wake_detected(MagicMock())

    mock_loop.call_soon_threadsafe.assert_not_called()


def test_wake_callback_is_noop_before_run() -> None:
    """Callback does nothing if run() has not been called (loop and event not set)."""
    detector = FakeDetector()
    coord = WakeWordCoordinator(
        detector,
        _speech_config(),
        transcript_stream=StringIO(),
    )
    # _loop and _wake_event are None — must not raise.
    coord._on_wake_detected(MagicMock())  # no assertion; must not raise


def test_standby_without_initialization_raises_error() -> None:
    """Calling _standby directly without run() raises WakeWordCoordinatorError."""
    detector = FakeDetector()
    coord = WakeWordCoordinator(
        detector,
        _speech_config(),
        transcript_stream=StringIO(),
    )
    with pytest.raises(WakeWordCoordinatorError, match="must be started via run"):
        asyncio.run(coord._standby())


# ---------------------------------------------------------------------------
# Tests: environment configuration
# ---------------------------------------------------------------------------


def test_coordinator_config_reads_required_environment() -> None:
    """coordinator_config_from_environment returns correct values from env dict."""
    env = {
        "DEEPGRAM_API_KEY": "dg-test-key",
        "OPENAGENT_WAKEWORD_MODEL_DIR": "/models/openwakeword",
    }
    speech_config, model_dir, threshold, cooldown, stt_timeout = (
        coordinator_config_from_environment(env)
    )
    assert model_dir == Path("/models/openwakeword")
    assert threshold == pytest.approx(0.4)
    assert cooldown == pytest.approx(2.0)
    assert stt_timeout == pytest.approx(30.0)
    assert "dg-test-key" not in repr(speech_config)


def test_coordinator_config_reads_optional_overrides() -> None:
    """Optional env vars override the defaults correctly."""
    env = {
        "DEEPGRAM_API_KEY": "dg-test-key",
        "OPENAGENT_WAKEWORD_MODEL_DIR": "/models",
        "OPENAGENT_WAKEWORD_THRESHOLD": "0.7",
        "OPENAGENT_WAKEWORD_COOLDOWN": "5.0",
        "OPENAGENT_STT_TIMEOUT": "60.0",
    }
    _, _, threshold, cooldown, stt_timeout = coordinator_config_from_environment(env)
    assert threshold == pytest.approx(0.7)
    assert cooldown == pytest.approx(5.0)
    assert stt_timeout == pytest.approx(60.0)


def test_coordinator_config_requires_deepgram_key() -> None:
    """Missing DEEPGRAM_API_KEY raises WakeWordCoordinatorError."""
    env = {"OPENAGENT_WAKEWORD_MODEL_DIR": "/models"}
    with pytest.raises(WakeWordCoordinatorError, match="DEEPGRAM_API_KEY"):
        coordinator_config_from_environment(env)


def test_coordinator_config_requires_model_dir() -> None:
    """Missing OPENAGENT_WAKEWORD_MODEL_DIR raises WakeWordCoordinatorError."""
    env = {"DEEPGRAM_API_KEY": "dg-test-key"}
    with pytest.raises(WakeWordCoordinatorError, match="OPENAGENT_WAKEWORD_MODEL_DIR"):
        coordinator_config_from_environment(env)


def test_coordinator_config_rejects_invalid_threshold() -> None:
    """Non-positive threshold raises WakeWordCoordinatorError."""
    env = {
        "DEEPGRAM_API_KEY": "dg-test-key",
        "OPENAGENT_WAKEWORD_MODEL_DIR": "/models",
        "OPENAGENT_WAKEWORD_THRESHOLD": "0",
    }
    with pytest.raises(WakeWordCoordinatorError, match="OPENAGENT_WAKEWORD_THRESHOLD"):
        coordinator_config_from_environment(env)


def test_coordinator_config_rejects_invalid_stt_timeout() -> None:
    """Non-positive STT timeout raises WakeWordCoordinatorError."""
    env = {
        "DEEPGRAM_API_KEY": "dg-test-key",
        "OPENAGENT_WAKEWORD_MODEL_DIR": "/models",
        "OPENAGENT_STT_TIMEOUT": "-5",
    }
    with pytest.raises(WakeWordCoordinatorError, match="OPENAGENT_STT_TIMEOUT"):
        coordinator_config_from_environment(env)


def test_coordinator_config_rejects_non_numeric_cooldown() -> None:
    """Non-numeric cooldown raises WakeWordCoordinatorError."""
    env = {
        "DEEPGRAM_API_KEY": "dg-test-key",
        "OPENAGENT_WAKEWORD_MODEL_DIR": "/models",
        "OPENAGENT_WAKEWORD_COOLDOWN": "two",
    }
    with pytest.raises(WakeWordCoordinatorError, match="OPENAGENT_WAKEWORD_COOLDOWN"):
        coordinator_config_from_environment(env)


def test_coordinator_config_allows_zero_cooldown() -> None:
    """Zero cooldown is valid (no minimum gap between detections)."""
    env = {
        "DEEPGRAM_API_KEY": "dg-test-key",
        "OPENAGENT_WAKEWORD_MODEL_DIR": "/models",
        "OPENAGENT_WAKEWORD_COOLDOWN": "0",
    }
    _, _, _, cooldown, _ = coordinator_config_from_environment(env)
    assert cooldown == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests: detector startup failure
# ---------------------------------------------------------------------------


def test_coordinator_raises_on_detector_start_failure() -> None:
    """If detector.start() raises, WakeWordCoordinatorError surfaces a clear message."""

    class FailingDetector(FakeDetector):
        def start(self) -> None:
            raise OSError("device is busy")

    async def run() -> None:
        coord = WakeWordCoordinator(
            FailingDetector(),
            _speech_config(),
            transcript_stream=StringIO(),
        )
        with pytest.raises(WakeWordCoordinatorError, match="failed to start"):
            await coord.run()

    with patch("openagent_realtime_convo.wakeword.run_speech_to_text"):
        asyncio.run(run())


# ---------------------------------------------------------------------------
# Tests: detector.stop() is called even when start() fails
# ---------------------------------------------------------------------------


def test_coordinator_stop_called_even_when_start_fails() -> None:
    """detector.stop() is always called in the finally block, even after start failure."""

    class FailingDetector(FakeDetector):
        def start(self) -> None:
            raise OSError("no device")

    detector = FailingDetector()

    async def run() -> None:
        coord = WakeWordCoordinator(
            detector,
            _speech_config(),
            transcript_stream=StringIO(),
        )
        try:
            await coord.run()
        except WakeWordCoordinatorError:
            pass

    with patch("openagent_realtime_convo.wakeword.run_speech_to_text"):
        asyncio.run(run())

    assert "stop" in detector.calls
