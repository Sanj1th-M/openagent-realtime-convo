from __future__ import annotations

from io import StringIO
from typing import cast

import pytest
from pipecat.services.deepgram.flux.stt import DeepgramFluxSTTService

from openagent_realtime_convo.config import AudioSettings
from openagent_realtime_convo.speech import (
    SpeechConfig,
    SpeechConfigurationError,
    SpeechRuntimeError,
    _write_transcript,
    create_local_transport,
    register_flux_transcript_handler,
    speech_config_from_environment,
)


class FluxEventSource:
    """Minimal stand-in for Pipecat's documented event-handler interface."""

    def __init__(self) -> None:
        self.handlers: dict[str, object] = {}

    def event_handler(self, event_name: str):  # type: ignore[no-untyped-def]
        def register(handler: object) -> object:
            self.handlers[event_name] = handler
            return handler

        return register


def test_speech_configuration_requires_documented_deepgram_key() -> None:
    with pytest.raises(SpeechConfigurationError, match="DEEPGRAM_API_KEY"):
        speech_config_from_environment({})


def test_speech_configuration_uses_existing_audio_environment_settings() -> None:
    configuration = speech_config_from_environment(
        {
            "DEEPGRAM_API_KEY": "not-a-real-key",
            "OPENAGENT_AUDIO_SAMPLE_RATE_HZ": "48000",
            "OPENAGENT_AUDIO_CHANNELS": "2",
            "OPENAGENT_AUDIO_CHUNK_SIZE": "960",
        }
    )

    assert configuration.audio == AudioSettings(sample_rate_hz=48_000, channels=2, chunk_size=960)
    assert "not-a-real-key" not in repr(configuration)


def test_transcript_printer_distinguishes_interim_and_final_results() -> None:
    stream = StringIO()

    _write_transcript(stream, "INTERIM", "still speaking")
    _write_transcript(stream, "FINAL", "complete sentence")

    assert stream.getvalue().splitlines() == [
        "[INTERIM] still speaking",
        "[FINAL] complete sentence",
    ]


def test_flux_update_event_prints_an_interim_transcript() -> None:
    stream = StringIO()
    stt = FluxEventSource()
    register_flux_transcript_handler(cast(DeepgramFluxSTTService, stt), stream)

    handler = stt.handlers["on_update"]
    assert callable(handler)
    with pytest.raises(StopIteration):
        handler(stt, "partial result").send(None)

    assert stream.getvalue() == "[INTERIM] partial result\n"


def test_speech_config_keeps_key_private() -> None:
    configuration = SpeechConfig(api_key="not-a-real-key", audio=AudioSettings())

    assert "not-a-real-key" not in repr(configuration)


def test_microphone_startup_failure_is_safe_and_actionable() -> None:
    def unavailable_transport(_: object) -> object:
        raise OSError("device is busy")

    with pytest.raises(SpeechRuntimeError, match="another application has released the device"):
        create_local_transport(
            SpeechConfig(api_key="not-a-real-key", audio=AudioSettings()),
            transport_factory=unavailable_transport,  # type: ignore[arg-type]
        )
