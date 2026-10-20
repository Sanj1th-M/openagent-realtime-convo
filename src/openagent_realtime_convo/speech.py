"""Local microphone to Deepgram Flux speech-to-text command."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TextIO

from pipecat.frames.frames import Frame, InterimTranscriptionFrame, TranscriptionFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.deepgram.flux.stt import DeepgramFluxSTTService
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
from pipecat.workers.runner import WorkerRunner

from .config import AppConfig, AudioSettings, ConfigurationError


class SpeechConfigurationError(ConfigurationError):
    """Raised when the speech-to-text command cannot be configured safely."""


class SpeechRuntimeError(RuntimeError):
    """Raised when speech-to-text cannot start or complete safely."""


@dataclass(frozen=True, slots=True)
class SpeechConfig:
    """Speech-specific configuration, intentionally excluding device selection."""

    api_key: str
    audio: AudioSettings

    def __repr__(self) -> str:
        return f"SpeechConfig(api_key=<redacted>, audio={self.audio!r})"


def speech_config_from_environment(environ: Mapping[str, str] | None = None) -> SpeechConfig:
    """Read the documented Deepgram key and existing audio settings from the environment."""
    try:
        configuration = AppConfig.from_deepgram_environment(environ)
    except ConfigurationError as error:
        raise SpeechConfigurationError(str(error)) from error
    return SpeechConfig(
        api_key=configuration.provider.api_key,
        audio=configuration.audio,
    )


class TranscriptPrinter(FrameProcessor):
    """Write transcript frames to a terminal without logging their contents."""

    def __init__(self, stream: TextIO) -> None:
        super().__init__()
        self._stream = stream

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        if isinstance(frame, InterimTranscriptionFrame):
            _write_transcript(self._stream, "INTERIM", frame.text)
        elif isinstance(frame, TranscriptionFrame):
            label = "FINAL" if frame.finalized else "TRANSCRIPT"
            _write_transcript(self._stream, label, frame.text)
        await self.push_frame(frame, direction)


def _write_transcript(stream: TextIO, label: str, text: str) -> None:
    """Emit non-empty transcript text with an explicit result state."""
    normalized = text.strip()
    if normalized:
        print(f"[{label}] {normalized}", file=stream, flush=True)


def register_flux_transcript_handler(stt: DeepgramFluxSTTService, stream: TextIO) -> None:
    """Display Flux Update events, which Pipecat does not wrap in interim frames."""

    @stt.event_handler("on_update")  # type: ignore[untyped-decorator]
    async def on_update(_: DeepgramFluxSTTService, transcript: str) -> None:
        _write_transcript(stream, "INTERIM", transcript)


async def run_speech_to_text(
    configuration: SpeechConfig,
    *,
    transcript_stream: TextIO,
    transport_factory: Callable[
        [LocalAudioTransportParams], LocalAudioTransport
    ] = LocalAudioTransport,
) -> None:
    """Run the local microphone to Flux pipeline until it is interrupted or ends."""
    transport = create_local_transport(configuration, transport_factory)

    stt = DeepgramFluxSTTService(
        api_key=configuration.api_key,
        sample_rate=configuration.audio.sample_rate_hz,
    )
    register_flux_transcript_handler(stt, transcript_stream)
    pipeline = Pipeline([transport.input(), stt, TranscriptPrinter(transcript_stream)])
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(audio_in_sample_rate=configuration.audio.sample_rate_hz),
    )
    runner = WorkerRunner()
    await runner.add_workers(worker)
    try:
        await runner.run()
    except asyncio.CancelledError:
        raise
    except Exception as error:
        raise SpeechRuntimeError(
            "Speech-to-text stopped because the microphone or Deepgram connection failed."
        ) from error


def create_local_transport(
    configuration: SpeechConfig,
    transport_factory: Callable[
        [LocalAudioTransportParams], LocalAudioTransport
    ] = LocalAudioTransport,
) -> LocalAudioTransport:
    """Create the microphone transport and turn device errors into user guidance."""
    try:
        return transport_factory(
            LocalAudioTransportParams(
                audio_in_enabled=True,
                audio_in_sample_rate=configuration.audio.sample_rate_hz,
                audio_in_channels=configuration.audio.channels,
            )
        )
    except Exception as error:
        raise SpeechRuntimeError(
            "Unable to open the microphone. Check Windows microphone permission and make sure "
            "another application has released the device."
        ) from error


def main() -> int:
    """Start the explicit speech-to-text command without exposing credentials."""
    try:
        configuration = speech_config_from_environment()
    except SpeechConfigurationError as error:
        print(f"Speech configuration error: {error}", file=sys.stderr)
        return 2

    print("Listening. Press Ctrl+C to stop.", file=sys.stderr, flush=True)
    try:
        asyncio.run(run_speech_to_text(configuration, transcript_stream=sys.stdout))
    except KeyboardInterrupt:
        print("Speech-to-text stopped.", file=sys.stderr)
        return 0
    except SpeechRuntimeError as error:
        print(f"Speech-to-text error: {error}", file=sys.stderr)
        return 1
    return 0
