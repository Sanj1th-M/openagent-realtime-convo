"""Provider-independent speech synthesis and local audio playback."""

from __future__ import annotations

import asyncio
import os
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import httpx

from .brain import BrainResponse
from .config import ConfigurationError, load_environment

MAX_TEXT_CHARACTERS = 4096
MAX_AUDIO_BYTES = 20 * 1024 * 1024
PCM_SAMPLE_RATE_HZ = 24_000
PCM_CHANNELS = 1


class TTSError(RuntimeError):
    """Raised for synthesis or playback failures without exposing provider data."""


@dataclass(frozen=True, slots=True)
class SpeechRequest:
    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise TTSError("speech text must be a non-empty string")
        if len(self.text) > MAX_TEXT_CHARACTERS:
            raise TTSError(f"speech text must not exceed {MAX_TEXT_CHARACTERS} characters")


@dataclass(frozen=True, slots=True)
class AudioData:
    data: bytes = field(repr=False)
    sample_rate_hz: int = PCM_SAMPLE_RATE_HZ
    channels: int = PCM_CHANNELS
    sample_width_bytes: int = 2
    encoding: str = "pcm_s16le"

    def __post_init__(self) -> None:
        if not isinstance(self.data, bytes) or not self.data:
            raise TTSError("audio data must not be empty")
        if len(self.data) > MAX_AUDIO_BYTES:
            raise TTSError("audio data exceeds the maximum supported size")
        if self.sample_rate_hz != PCM_SAMPLE_RATE_HZ or self.channels != PCM_CHANNELS:
            raise TTSError("audio format is unsupported")
        if self.sample_width_bytes != 2 or self.encoding != "pcm_s16le":
            raise TTSError("audio encoding is unsupported")
        if len(self.data) % 2:
            raise TTSError("PCM audio data has an invalid byte length")


@runtime_checkable
class TTSProvider(Protocol):
    async def synthesize(self, request: SpeechRequest) -> AudioData: ...


@runtime_checkable
class AudioPlayer(Protocol):
    async def play(self, audio: AudioData) -> None: ...


class OpenAITTSProvider:
    """OpenAI Speech API adapter returning raw 24 kHz signed 16-bit PCM."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gpt-4o-mini-tts",
        voice: str = "marin",
        timeout_seconds: float = 30.0,
        client: Any | None = None,
    ) -> None:
        if not api_key.strip():
            raise TTSError("OpenAI API key must not be empty")
        if timeout_seconds <= 0:
            raise TTSError("timeout_seconds must be positive")
        self._api_key = api_key
        self._model = model
        self._voice = voice
        self._timeout = timeout_seconds
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_client = client is None

    async def synthesize(self, request: SpeechRequest) -> AudioData:
        try:
            async with self._client.stream(
                "POST",
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "voice": self._voice,
                    "input": request.text,
                    "response_format": "pcm",
                },
                timeout=self._timeout,
            ) as response:
                if response.status_code < 200 or response.status_code >= 300:
                    raise TTSError(f"Speech provider returned HTTP {response.status_code}")
                content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
                if content_type not in {"audio/pcm", "application/octet-stream"}:
                    raise TTSError("Speech provider returned an unsupported content type")
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_AUDIO_BYTES:
                    raise TTSError("Speech provider response exceeds the maximum size")
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_AUDIO_BYTES:
                        raise TTSError("Speech provider response exceeds the maximum size")
                    chunks.append(chunk)
        except asyncio.CancelledError:
            raise
        except TTSError:
            raise
        except httpx.TimeoutException as exc:
            raise TTSError("Speech provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise TTSError("Speech provider request failed") from exc
        except (ValueError, OverflowError) as exc:
            raise TTSError("Speech provider response was malformed") from exc
        return AudioData(data=b"".join(chunks))

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


class PyAudioPlayer:
    """Play PCM through the default output device using Pipecat's PyAudio dependency."""

    async def play(self, audio: AudioData) -> None:
        stop_requested = threading.Event()
        worker = asyncio.create_task(asyncio.to_thread(self._play_sync, audio, stop_requested))
        try:
            await asyncio.shield(worker)
        except asyncio.CancelledError:
            stop_requested.set()
            worker.add_done_callback(self._consume_worker_exception)
            raise
        except Exception as exc:
            raise TTSError("Local audio playback failed") from exc

    @staticmethod
    def _consume_worker_exception(worker: asyncio.Task[None]) -> None:
        """Retrieve a cancelled playback worker's exception after local cleanup completes."""
        if not worker.cancelled():
            try:
                worker.exception()
            except Exception:
                pass

    @staticmethod
    def _play_sync(audio: AudioData, stop_requested: threading.Event) -> None:
        import pyaudio  # type: ignore[import-untyped]

        if stop_requested.is_set():
            return
        engine = pyaudio.PyAudio()
        stream = None
        try:
            if stop_requested.is_set():
                return
            stream = engine.open(
                format=pyaudio.paInt16,
                channels=audio.channels,
                rate=audio.sample_rate_hz,
                output=True,
            )
            for offset in range(0, len(audio.data), 8192):
                if stop_requested.is_set():
                    break
                stream.write(audio.data[offset : offset + 8192])
        finally:
            try:
                if stream is not None:
                    try:
                        stream.stop_stream()
                    finally:
                        stream.close()
            finally:
                engine.terminate()


class SpeechOutput:
    """Synthesize and play an existing brain reply, without invoking a brain."""

    def __init__(self, provider: TTSProvider, player: AudioPlayer) -> None:
        self._provider = provider
        self._player = player

    async def speak(self, response: BrainResponse) -> None:
        if not isinstance(response, BrainResponse):
            raise TTSError("response must be a BrainResponse")
        audio = await self._provider.synthesize(SpeechRequest(response.reply))
        if not isinstance(audio, AudioData):
            raise TTSError("speech provider returned an invalid audio response")
        await self._player.play(audio)

    async def aclose(self) -> None:
        close = getattr(self._provider, "aclose", None)
        if close is not None:
            await close()


def speech_output_from_environment(
    environ: Mapping[str, str] | None = None,
    *,
    load_env: bool = True,
) -> SpeechOutput:
    if environ is None:
        if load_env:
            load_environment()
        environment: Mapping[str, str] = os.environ
    else:
        environment = environ
    api_key = environment.get("OPENAI_TTS_API_KEY") or environment.get("OPENAI_API_KEY")
    if api_key is None or not api_key.strip():
        raise ConfigurationError("OPENAI_TTS_API_KEY or OPENAI_API_KEY must be set")
    model = environment.get("OPENAGENT_TTS_MODEL", "gpt-4o-mini-tts")
    voice = environment.get("OPENAGENT_TTS_VOICE", "marin")
    return SpeechOutput(
        OpenAITTSProvider(api_key.strip(), model=model, voice=voice), PyAudioPlayer()
    )


__all__ = [
    "AudioData",
    "AudioPlayer",
    "OpenAITTSProvider",
    "PyAudioPlayer",
    "SpeechOutput",
    "SpeechRequest",
    "TTSProvider",
    "TTSError",
    "speech_output_from_environment",
]
