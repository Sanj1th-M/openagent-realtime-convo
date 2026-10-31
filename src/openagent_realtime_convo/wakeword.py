"""Wake-word coordinator: bridges WakeWordDetector (threading) with the STT pipeline (asyncio).

Design constraints honoured here
---------------------------------
* Single microphone owner at any instant.  WakeWordDetector holds the mic
  during STANDBY; it is paused (mic released, model kept) before the Pipecat
  STT pipeline opens the same device during ACTIVE.  The detector is resumed
  (mic reclaimed) after every STT cycle regardless of outcome.
* Thread-safety.  WakeWordDetector callbacks fire on PortAudio's background
  thread.  This module bridges to asyncio with call_soon_threadsafe; it never
  calls detector methods from inside the callback itself.
* Optional dependency.  openagent-wakeword is a private local package that is
  not declared in pyproject.toml.  The import is guarded so that CI tests
  (which mock the detector) can run without it installed.
* No secrets in logs.  The Deepgram API key is never written to any log field
  or printed to any stream.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

from .config import AudioSettings, ConfigurationError
from .speech import (
    SpeechConfig,
    SpeechConfigurationError,
    SpeechRuntimeError,
    run_speech_to_text,
)

if TYPE_CHECKING:  # pragma: no cover
    from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams

logger = logging.getLogger(__name__)

# Default values documented in ARCHITECTURE.md (Phase 4).
_DEFAULT_THRESHOLD: float = 0.4
_DEFAULT_COOLDOWN: float = 2.0
_DEFAULT_STT_TIMEOUT: float = 30.0
_DEFAULT_ACKNOWLEDGEMENT: str = "Yes sir, what can I help you with?"


class WakeWordCoordinatorError(RuntimeError):
    """Raised when the wake-word coordinator cannot start or configure itself."""


def _load_detector(model_dir: Path, threshold: float, cooldown: float) -> Any:
    """Import and construct a WakeWordDetector; raise WakeWordCoordinatorError when unavailable."""
    try:
        from openagent_wakeword import WakeWordConfig, WakeWordDetector  # type: ignore[import-not-found]
    except ImportError as exc:
        raise WakeWordCoordinatorError(
            "openagent-wakeword is not installed in this environment. "
            "Install it from its local repository: "
            "pip install -e /path/to/openagent-wakeword"
        ) from exc
    config = WakeWordConfig(
        model_dir=model_dir,
        threshold=threshold,
        cooldown_seconds=cooldown,
    )
    return WakeWordDetector(config)


class WakeWordCoordinator:
    """Coordinates a single-process STANDBY → ACTIVE → STANDBY loop.

    STANDBY: WakeWordDetector holds the microphone; coordinator awaits detection.
    ACTIVE:  Detector is paused (mic released); Pipecat STT pipeline captures audio.

    The coordinator is constructed with an already-built detector so that tests
    can inject fakes without importing openagent-wakeword.
    """

    def __init__(
        self,
        detector: Any,
        speech_config: SpeechConfig,
        *,
        acknowledgement: str = _DEFAULT_ACKNOWLEDGEMENT,
        stt_timeout_seconds: float = _DEFAULT_STT_TIMEOUT,
        transcript_stream: TextIO | None = None,
        transport_factory: (
            Callable[["LocalAudioTransportParams"], "LocalAudioTransport"] | None
        ) = None,
    ) -> None:
        self._detector = detector
        self._speech_config = speech_config
        self._acknowledgement = acknowledgement
        self._stt_timeout = stt_timeout_seconds
        self._stream: TextIO = transcript_stream if transcript_stream is not None else sys.stdout
        self._transport_factory = transport_factory
        self._wake_event: asyncio.Event | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Run the coordinator loop until cancelled or interrupted.

        Always calls detector.stop() in its finally block.
        """
        self._loop = asyncio.get_running_loop()
        self._wake_event = asyncio.Event()

        self._detector.add_callback(self._on_wake_detected)
        try:
            self._start_detector()
            while True:
                await self._standby()
                await self._active()
        finally:
            self._detector.stop()
            logger.info("event=coordinator_stopped")

    # ------------------------------------------------------------------
    # Internal phases
    # ------------------------------------------------------------------

    def _start_detector(self) -> None:
        """Start the wake-word detector; translate its errors to coordinator errors."""
        try:
            self._detector.start()
            logger.info("event=standby_started")
        except Exception as exc:
            raise WakeWordCoordinatorError(
                f"Wake-word detector failed to start: {exc}. "
                "Check that no other process holds the microphone "
                "(e.g. the openagent-wakeword-listener scheduled task)."
            ) from exc

    async def _standby(self) -> None:
        """Wait (asleep) until a wake-word event is signalled from the audio thread."""
        if self._wake_event is None:
            raise WakeWordCoordinatorError(
                "Coordinator must be started via run() before entering standby."
            )
        self._wake_event.clear()
        logger.info("event=standby phase=waiting")
        await self._wake_event.wait()
        logger.info("event=wake_word_received")

    async def _active(self) -> None:
        """Pause the detector, run STT, then resume the detector regardless of outcome."""
        self._detector.pause()
        logger.info("event=detector_paused phase=active")
        try:
            print(self._acknowledgement, file=self._stream, flush=True)
            await self._run_stt_with_timeout()
        finally:
            # Resume is always called so the mic is never abandoned.
            try:
                self._detector.resume()
                logger.info("event=detector_resumed phase=standby")
            except Exception as resume_exc:
                logger.error(
                    "event=detector_resume_failed error=%s",
                    type(resume_exc).__name__,
                )
                raise WakeWordCoordinatorError(
                    "Failed to resume wake-word detector after STT; cannot return to standby."
                ) from resume_exc

    async def _run_stt_with_timeout(self) -> None:
        """Run STT with a deadline; always return (never raise) so the finally block runs."""
        kwargs: dict[str, Any] = {"transcript_stream": self._stream}
        if self._transport_factory is not None:
            kwargs["transport_factory"] = self._transport_factory

        try:
            await asyncio.wait_for(
                run_speech_to_text(self._speech_config, **kwargs),
                timeout=self._stt_timeout,
            )
            logger.info("event=stt_completed")
        except asyncio.TimeoutError:
            logger.warning("event=stt_timeout timeout_seconds=%s", self._stt_timeout)
        except SpeechRuntimeError as exc:
            logger.error("event=stt_runtime_error error=%s", type(exc).__name__)
        except asyncio.CancelledError:
            # Propagate cancellation so run()'s finally block still executes.
            raise

    # ------------------------------------------------------------------
    # Thread-safe callback (called on PortAudio's audio thread)
    # ------------------------------------------------------------------

    def _on_wake_detected(self, event: Any) -> None:
        """Signal the asyncio event loop from PortAudio's background thread."""
        loop = self._loop
        wake_event = self._wake_event
        if loop is None or wake_event is None:
            return
        if wake_event.is_set():
            # Already active; ignore duplicate detections during ACTIVE phase.
            return
        loop.call_soon_threadsafe(wake_event.set)


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def coordinator_config_from_environment(
    environ: Mapping[str, str] | None = None,
) -> tuple[SpeechConfig, Path, float, float, float]:
    """Read all Phase-4 coordinator settings from the environment.

    Required variables
    ------------------
    DEEPGRAM_API_KEY              Deepgram API credential (reused from Phase 3).
    OPENAGENT_WAKEWORD_MODEL_DIR  Absolute path to the ONNX model directory.

    Optional variables
    ------------------
    OPENAGENT_WAKEWORD_THRESHOLD  Detection threshold; default 0.4.
    OPENAGENT_WAKEWORD_COOLDOWN   Cooldown seconds; default 2.0.
    OPENAGENT_STT_TIMEOUT         Max seconds for one STT capture; default 30.

    Returns
    -------
    (SpeechConfig, model_dir, threshold, cooldown, stt_timeout)
    """
    import os

    env: Mapping[str, str] = os.environ if environ is None else environ

    # Speech config (reuses existing Phase-3 path).
    try:
        speech_config = _speech_config_from_env(env)
    except SpeechConfigurationError as exc:
        raise WakeWordCoordinatorError(str(exc)) from exc

    # Model dir — required.
    raw_model_dir = env.get("OPENAGENT_WAKEWORD_MODEL_DIR", "").strip()
    if not raw_model_dir:
        raise WakeWordCoordinatorError(
            "OPENAGENT_WAKEWORD_MODEL_DIR must be set to the ONNX model directory."
        )
    model_dir = Path(raw_model_dir)

    # Optional floats.
    threshold = _positive_float_from_env(env, "OPENAGENT_WAKEWORD_THRESHOLD", _DEFAULT_THRESHOLD)
    cooldown = _non_negative_float_from_env(env, "OPENAGENT_WAKEWORD_COOLDOWN", _DEFAULT_COOLDOWN)
    stt_timeout = _positive_float_from_env(env, "OPENAGENT_STT_TIMEOUT", _DEFAULT_STT_TIMEOUT)

    return speech_config, model_dir, threshold, cooldown, stt_timeout


def _speech_config_from_env(env: Mapping[str, str]) -> SpeechConfig:
    """Delegate to the Phase-3 configuration path."""
    from .config import AppConfig

    try:
        configuration = AppConfig.from_deepgram_environment(env)
    except ConfigurationError as exc:
        raise SpeechConfigurationError(str(exc)) from exc
    return SpeechConfig(
        api_key=configuration.provider.api_key,
        audio=AudioSettings(
            sample_rate_hz=configuration.audio.sample_rate_hz,
            channels=configuration.audio.channels,
            chunk_size=configuration.audio.chunk_size,
        ),
    )


def _positive_float_from_env(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise WakeWordCoordinatorError(f"{name} must be a positive number") from exc
    if value <= 0:
        raise WakeWordCoordinatorError(f"{name} must be a positive number")
    return value


def _non_negative_float_from_env(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise WakeWordCoordinatorError(f"{name} must be a non-negative number") from exc
    if value < 0:
        raise WakeWordCoordinatorError(f"{name} must be a non-negative number")
    return value


# ---------------------------------------------------------------------------
# Console entry point
# ---------------------------------------------------------------------------


def main() -> int:  # pragma: no cover
    """Start the wake-word coordinator without exposing credentials."""
    from .logging import configure_logging

    configure_logging()

    try:
        speech_config, model_dir, threshold, cooldown, stt_timeout = (
            coordinator_config_from_environment()
        )
    except WakeWordCoordinatorError as exc:
        print(f"Wake-word coordinator configuration error: {exc}", file=sys.stderr)
        return 2

    try:
        detector = _load_detector(model_dir, threshold, cooldown)
    except WakeWordCoordinatorError as exc:
        print(f"Wake-word coordinator startup error: {exc}", file=sys.stderr)
        return 1

    coordinator = WakeWordCoordinator(
        detector,
        speech_config,
        stt_timeout_seconds=stt_timeout,
    )
    print("Listening for 'Hey Jarvis'. Press Ctrl+C to stop.", file=sys.stderr, flush=True)
    try:
        asyncio.run(coordinator.run())
    except KeyboardInterrupt:
        print("Wake-word coordinator stopped.", file=sys.stderr)
        return 0
    except WakeWordCoordinatorError as exc:
        print(f"Wake-word coordinator error: {exc}", file=sys.stderr)
        return 1
    return 0
