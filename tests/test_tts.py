"""Mocked TTS provider, integration, configuration, and playback tests."""

from __future__ import annotations

import asyncio
import json
import sys
import threading
from collections.abc import AsyncIterator
from types import SimpleNamespace

import httpx
import pytest

from openagent_realtime_convo.brain import BrainResponse
from openagent_realtime_convo.config import ConfigurationError
from openagent_realtime_convo.tts import (
    MAX_AUDIO_BYTES,
    AudioData,
    OpenAITTSProvider,
    PyAudioPlayer,
    SpeechOutput,
    SpeechRequest,
    TTSError,
    speech_output_from_environment,
)


class FakePlayer:
    def __init__(self, error: Exception | None = None) -> None:
        self.audio: AudioData | None = None
        self.error = error

    async def play(self, audio: AudioData) -> None:
        if self.error:
            raise self.error
        self.audio = audio


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        content_type: str = "audio/pcm",
        body: bytes = b"\x01\x00",
        content_length: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        if content_length is not None:
            self.headers["content-length"] = content_length
        self._body = body

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        yield self._body


class FakeStream:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    async def __aenter__(self) -> FakeResponse:
        return self.response

    async def __aexit__(self, *args: object) -> None:
        return None


class FakeHTTPClient:
    def __init__(
        self,
        response: FakeResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.call: tuple[object, ...] | None = None

    def stream(self, *args: object, **kwargs: object) -> FakeStream:
        self.call = (*args, kwargs)
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return FakeStream(self.response)


@pytest.mark.anyio
async def test_openai_provider_synthesizes_pcm_and_redacts_credentials() -> None:
    secret = "tts-secret-key"
    client = FakeHTTPClient(FakeResponse())
    provider = OpenAITTSProvider(secret, client=client)
    audio = await provider.synthesize(SpeechRequest("Hello"))

    assert audio == AudioData(b"\x01\x00")
    assert client.call is not None
    assert client.call[0:2] == ("POST", "https://api.openai.com/v1/audio/speech")
    kwargs = client.call[2]
    assert isinstance(kwargs, dict)
    headers = kwargs["headers"]
    body = kwargs["json"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == f"Bearer {secret}"
    assert json.loads(json.dumps(body))["response_format"] == "pcm"
    assert secret not in repr(provider)


@pytest.mark.anyio
async def test_speech_output_speaks_existing_brain_response() -> None:
    audio = AudioData(b"\x01\x00")

    class Provider:
        requests: list[SpeechRequest] = []

        async def synthesize(self, request: SpeechRequest) -> AudioData:
            self.requests.append(request)
            return audio

    provider = Provider()
    player = FakePlayer()
    await SpeechOutput(provider, player).speak(BrainResponse("Reply text"))

    assert provider.requests == [SpeechRequest("Reply text")]
    assert player.audio == audio


@pytest.mark.anyio
async def test_provider_rejects_http_error_without_exposing_response_body() -> None:
    client = FakeHTTPClient(FakeResponse(status_code=401))
    provider = OpenAITTSProvider("secret", client=client)
    with pytest.raises(TTSError, match="HTTP 401") as error:
        await provider.synthesize(SpeechRequest("hello"))
    assert "private provider detail" not in str(error.value)


@pytest.mark.anyio
async def test_provider_timeout_is_reported_without_details() -> None:
    client = FakeHTTPClient(error=httpx.ReadTimeout("sensitive request detail"))
    provider = OpenAITTSProvider("secret", client=client)
    with pytest.raises(TTSError, match="timed out") as error:
        await provider.synthesize(SpeechRequest("hello"))
    assert "sensitive request detail" not in str(error.value)


@pytest.mark.anyio
async def test_synthesis_cancellation_is_propagated() -> None:
    class WaitingResponse(FakeResponse):
        async def aiter_bytes(self) -> AsyncIterator[bytes]:
            await asyncio.Event().wait()
            yield b"\x00\x00"

    provider = OpenAITTSProvider("secret", client=FakeHTTPClient(WaitingResponse()))
    task = asyncio.create_task(provider.synthesize(SpeechRequest("hello")))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.anyio
async def test_provider_rejects_invalid_content_type_and_odd_pcm() -> None:
    client = FakeHTTPClient(FakeResponse(content_type="text/html", body=b"x"))
    provider = OpenAITTSProvider("secret", client=client)
    with pytest.raises(TTSError, match="content type"):
        await provider.synthesize(SpeechRequest("hello"))
    with pytest.raises(TTSError, match="byte length"):
        AudioData(b"x")


@pytest.mark.anyio
async def test_provider_rejects_oversized_audio_before_reading_body() -> None:
    client = FakeHTTPClient(FakeResponse(content_length=str(MAX_AUDIO_BYTES + 1)))
    provider = OpenAITTSProvider("secret", client=client)

    with pytest.raises(TTSError, match="maximum size"):
        await provider.synthesize(SpeechRequest("hello"))


@pytest.mark.anyio
async def test_playback_cancellation_returns_without_waiting_for_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = threading.Event()
    release = threading.Event()

    def blocking_playback(audio: AudioData, stop_requested: threading.Event) -> None:
        started.set()
        release.wait(timeout=1)

    monkeypatch.setattr(PyAudioPlayer, "_play_sync", staticmethod(blocking_playback))
    player = PyAudioPlayer()
    task = asyncio.create_task(player.play(AudioData(b"\x00\x00")))
    for _ in range(10):
        if started.is_set():
            break
        await asyncio.sleep(0)
    assert started.is_set()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    release.set()


def test_request_and_audio_models_validate_input() -> None:
    with pytest.raises(TTSError, match="non-empty"):
        SpeechRequest("  ")
    with pytest.raises(TTSError, match="unsupported"):
        AudioData(b"\x00\x00", sample_rate_hz=16_000)


def test_factory_reads_only_tts_credential_or_openai_key() -> None:
    with pytest.raises(ConfigurationError, match="OPENAI_TTS_API_KEY or OPENAI_API_KEY"):
        speech_output_from_environment({}, load_env=False)
    output = speech_output_from_environment(
        {"OPENAI_API_KEY": "secret", "OPENAGENT_TTS_VOICE": "nova"}, load_env=False
    )
    assert isinstance(output, SpeechOutput)


def test_local_player_closes_stream_and_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    class Stream:
        def write(self, data: bytes) -> None:
            events.append("write")

        def stop_stream(self) -> None:
            events.append("stop")

        def close(self) -> None:
            events.append("close")

    class Engine:
        def open(self, **kwargs: object) -> Stream:
            events.append("open")
            return Stream()

        def terminate(self) -> None:
            events.append("terminate")

    monkeypatch.setitem(sys.modules, "pyaudio", SimpleNamespace(PyAudio=Engine, paInt16=8))
    PyAudioPlayer._play_sync(AudioData(b"\x00\x00"), threading.Event())

    assert events == ["open", "write", "stop", "close", "terminate"]


def test_local_player_does_not_open_device_after_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Engine:
        def __init__(self) -> None:
            raise AssertionError("audio engine must not be initialized")

    monkeypatch.setitem(sys.modules, "pyaudio", SimpleNamespace(PyAudio=Engine, paInt16=8))
    stop_requested = threading.Event()
    stop_requested.set()

    PyAudioPlayer._play_sync(AudioData(b"\x00\x00"), stop_requested)


@pytest.mark.anyio
async def test_playback_error_is_propagated() -> None:
    class Provider:
        async def synthesize(self, request: SpeechRequest) -> AudioData:
            return AudioData(b"\x00\x00")

    output = SpeechOutput(Provider(), FakePlayer(TTSError("playback failed")))
    with pytest.raises(TTSError, match="playback failed"):
        await output.speak(BrainResponse("Reply"))
