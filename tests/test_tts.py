"""Mocked TTS provider, integration, configuration, and playback tests."""

from __future__ import annotations

import asyncio
import sys
import threading
from collections.abc import AsyncIterator
from types import SimpleNamespace

import httpx
import pytest

from openagent_realtime_convo.brain import BrainResponse
from openagent_realtime_convo.config import ConfigurationError
from openagent_realtime_convo.tts import (
    _DEEPGRAM_TTS_URL,
    MAX_AUDIO_BYTES,
    AudioData,
    DeepgramTTSProvider,
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
        content_type: str = "audio/l16;rate=24000",  # actual Deepgram content-type
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


# ---------------------------------------------------------------------------
# DeepgramTTSProvider – synthesis and credential handling
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_deepgram_provider_synthesizes_pcm_and_redacts_credentials() -> None:
    """Provider calls the Deepgram endpoint with correct params; key stays out of repr."""
    secret = "tts-deepgram-secret"
    client = FakeHTTPClient(FakeResponse())
    provider = DeepgramTTSProvider(secret, client=client)
    audio = await provider.synthesize(SpeechRequest("Hello"))

    assert audio == AudioData(b"\x01\x00")
    assert client.call is not None
    assert client.call[0:2] == ("POST", _DEEPGRAM_TTS_URL)
    kwargs = client.call[2]
    assert isinstance(kwargs, dict)

    # Authorization header must carry the key as a Token, not a Bearer
    headers = kwargs["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == f"Token {secret}"
    assert headers["Content-Type"] == "application/json"

    # Request body must be JSON {"text": ...}
    body = kwargs["json"]
    assert isinstance(body, dict)
    assert body["text"] == "Hello"

    # Query params must request raw linear16 PCM at 24 kHz
    params = kwargs["params"]
    assert isinstance(params, dict)
    assert params["encoding"] == "linear16"
    assert params["container"] == "none"
    assert params["sample_rate"] == "24000"

    # API key must not leak into repr
    assert secret not in repr(provider)


@pytest.mark.anyio
async def test_deepgram_provider_uses_configured_model() -> None:
    client = FakeHTTPClient(FakeResponse())
    provider = DeepgramTTSProvider("key", model="aura-2-zeus-en", client=client)
    await provider.synthesize(SpeechRequest("Test"))

    assert client.call is not None
    kwargs = client.call[2]
    assert isinstance(kwargs, dict)
    assert kwargs["params"]["model"] == "aura-2-zeus-en"
    assert "aura-2-zeus-en" in repr(provider)


@pytest.mark.anyio
async def test_deepgram_provider_accepts_audio_pcm_content_type() -> None:
    """audio/pcm is also an acceptable content-type from Deepgram."""
    client = FakeHTTPClient(FakeResponse(content_type="audio/pcm"))
    provider = DeepgramTTSProvider("key", client=client)
    audio = await provider.synthesize(SpeechRequest("Hello"))
    assert audio == AudioData(b"\x01\x00")


@pytest.mark.anyio
async def test_deepgram_provider_accepts_audio_l16_content_type() -> None:
    """audio/l16 (IANA L16) is the content-type Deepgram actually returns in production."""
    client = FakeHTTPClient(FakeResponse(content_type="audio/l16;rate=24000"))
    provider = DeepgramTTSProvider("key", client=client)
    audio = await provider.synthesize(SpeechRequest("Hello"))
    assert audio == AudioData(b"\x01\x00")


@pytest.mark.anyio
async def test_deepgram_provider_accepts_audio_l16_without_rate_param() -> None:
    """audio/l16 without a rate parameter is also accepted."""
    client = FakeHTTPClient(FakeResponse(content_type="audio/l16"))
    provider = DeepgramTTSProvider("key", client=client)
    audio = await provider.synthesize(SpeechRequest("Hello"))
    assert audio == AudioData(b"\x01\x00")


@pytest.mark.anyio
async def test_deepgram_provider_accepts_octet_stream_content_type() -> None:
    """application/octet-stream is also acceptable."""
    client = FakeHTTPClient(FakeResponse(content_type="application/octet-stream"))
    provider = DeepgramTTSProvider("key", client=client)
    audio = await provider.synthesize(SpeechRequest("Hello"))
    assert audio == AudioData(b"\x01\x00")


# ---------------------------------------------------------------------------
# SpeechOutput integration
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Error handling – HTTP errors, timeouts, bad content type, oversized body
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_provider_rejects_http_error_without_exposing_response_body() -> None:
    client = FakeHTTPClient(FakeResponse(status_code=401))
    provider = DeepgramTTSProvider("secret", client=client)
    with pytest.raises(TTSError, match="HTTP 401") as error:
        await provider.synthesize(SpeechRequest("hello"))
    assert "private provider detail" not in str(error.value)


@pytest.mark.anyio
async def test_provider_rejects_forbidden_without_key_in_message() -> None:
    client = FakeHTTPClient(FakeResponse(status_code=403))
    provider = DeepgramTTSProvider("super-secret-key", client=client)
    with pytest.raises(TTSError, match="HTTP 403") as error:
        await provider.synthesize(SpeechRequest("hello"))
    assert "super-secret-key" not in str(error.value)


@pytest.mark.anyio
async def test_provider_timeout_is_reported_without_details() -> None:
    client = FakeHTTPClient(error=httpx.ReadTimeout("sensitive request detail"))
    provider = DeepgramTTSProvider("secret", client=client)
    with pytest.raises(TTSError, match="timed out") as error:
        await provider.synthesize(SpeechRequest("hello"))
    assert "sensitive request detail" not in str(error.value)


@pytest.mark.anyio
async def test_provider_http_error_is_reported_safely() -> None:
    client = FakeHTTPClient(error=httpx.ConnectError("connection refused"))
    provider = DeepgramTTSProvider("secret", client=client)
    with pytest.raises(TTSError, match="request failed") as error:
        await provider.synthesize(SpeechRequest("hello"))
    assert "connection refused" not in str(error.value)


@pytest.mark.anyio
async def test_synthesis_cancellation_is_propagated() -> None:
    class WaitingResponse(FakeResponse):
        async def aiter_bytes(self) -> AsyncIterator[bytes]:
            await asyncio.Event().wait()
            yield b"\x00\x00"

    provider = DeepgramTTSProvider("secret", client=FakeHTTPClient(WaitingResponse()))
    task = asyncio.create_task(provider.synthesize(SpeechRequest("hello")))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.anyio
async def test_provider_rejects_invalid_content_type_and_odd_pcm() -> None:
    client = FakeHTTPClient(FakeResponse(content_type="text/html", body=b"x"))
    provider = DeepgramTTSProvider("secret", client=client)
    with pytest.raises(TTSError, match="content type"):
        await provider.synthesize(SpeechRequest("hello"))
    with pytest.raises(TTSError, match="byte length"):
        AudioData(b"x")


@pytest.mark.anyio
async def test_provider_rejects_oversized_audio_before_reading_body() -> None:
    client = FakeHTTPClient(FakeResponse(content_length=str(MAX_AUDIO_BYTES + 1)))
    provider = DeepgramTTSProvider("secret", client=client)

    with pytest.raises(TTSError, match="maximum size"):
        await provider.synthesize(SpeechRequest("hello"))


@pytest.mark.anyio
async def test_provider_rejects_malformed_content_length() -> None:
    """A non-integer content-length triggers the malformed-response error."""
    client = FakeHTTPClient(FakeResponse(content_length="not-a-number"))
    provider = DeepgramTTSProvider("secret", client=client)
    with pytest.raises(TTSError, match="malformed"):
        await provider.synthesize(SpeechRequest("hello"))


# ---------------------------------------------------------------------------
# Configuration validation
# ---------------------------------------------------------------------------


def test_provider_rejects_empty_api_key() -> None:
    with pytest.raises(TTSError, match="API key"):
        DeepgramTTSProvider("")


def test_provider_rejects_whitespace_api_key() -> None:
    with pytest.raises(TTSError, match="API key"):
        DeepgramTTSProvider("   ")


def test_provider_rejects_non_positive_timeout() -> None:
    with pytest.raises(TTSError, match="timeout_seconds"):
        DeepgramTTSProvider("key", timeout_seconds=0.0)


def test_request_and_audio_models_validate_input() -> None:
    with pytest.raises(TTSError, match="non-empty"):
        SpeechRequest("  ")
    with pytest.raises(TTSError, match="unsupported"):
        AudioData(b"\x00\x00", sample_rate_hz=16_000)


# ---------------------------------------------------------------------------
# Factory – reads DEEPGRAM_API_KEY and OPENAGENT_TTS_MODEL
# ---------------------------------------------------------------------------


def test_factory_requires_deepgram_api_key() -> None:
    with pytest.raises(ConfigurationError, match="DEEPGRAM_API_KEY"):
        speech_output_from_environment({}, load_env=False)


def test_factory_rejects_whitespace_deepgram_key() -> None:
    with pytest.raises(ConfigurationError, match="DEEPGRAM_API_KEY"):
        speech_output_from_environment({"DEEPGRAM_API_KEY": "   "}, load_env=False)


def test_factory_builds_speech_output_with_default_model() -> None:
    output = speech_output_from_environment({"DEEPGRAM_API_KEY": "dg-secret"}, load_env=False)
    assert isinstance(output, SpeechOutput)


def test_factory_accepts_custom_model_from_environment() -> None:
    output = speech_output_from_environment(
        {
            "DEEPGRAM_API_KEY": "dg-secret",
            "OPENAGENT_TTS_MODEL": "aura-2-zeus-en",
        },
        load_env=False,
    )
    assert isinstance(output, SpeechOutput)


# ---------------------------------------------------------------------------
# PyAudioPlayer – playback lifecycle, cancellation, and cleanup
# ---------------------------------------------------------------------------


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
