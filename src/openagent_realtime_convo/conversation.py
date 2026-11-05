"""Provider-neutral boundary between finalized STT text, AI brain, and speech output.

This module coordinates passing finalized transcript text to the selected
AI brain provider and optionally dispatching the validated ``BrainResponse`` to
speech output for audio playback.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from .brain import BrainError, BrainProvider, BrainRequest, BrainResponse
from .config import AppConfig, ConfigurationError
from .providers import create_brain_provider

logger = logging.getLogger(__name__)


class TranscriptHandlingError(BrainError):
    """Raised when a finalized transcript cannot safely be processed."""


@runtime_checkable
class SpeechService(Protocol):
    """Protocol for speech output services capable of speaking a BrainResponse."""

    async def speak(self, response: BrainResponse) -> None: ...

    async def aclose(self) -> None: ...


class TranscriptBrainCoordinator:
    """Turn one finalized STT transcript into one provider response, and optionally speak it."""

    def __init__(
        self,
        provider: BrainProvider,
        *,
        timeout_seconds: float = 30.0,
        speech_output: SpeechService | None = None,
    ) -> None:
        if not isinstance(provider, BrainProvider):
            raise TranscriptHandlingError("provider must implement BrainProvider")
        if isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise TranscriptHandlingError("timeout_seconds must be a positive number")
        if speech_output is not None and not isinstance(speech_output, SpeechService):
            raise TranscriptHandlingError("speech_output must implement SpeechService")
        self._provider = provider
        self._timeout_seconds = timeout_seconds
        self._speech_output = speech_output

    async def respond_to_transcript(
        self, transcript: str, *, session_id: str | None = None
    ) -> BrainResponse:
        """Pass non-empty finalized STT text to the provider, optionally speak, and return reply."""
        try:
            request = BrainRequest(message=transcript, session_id=session_id)
        except BrainError as exc:
            raise TranscriptHandlingError(
                "finalized transcript must be a non-empty string"
            ) from exc

        try:
            response = await asyncio.wait_for(
                self._provider.generate_response(request), timeout=self._timeout_seconds
            )
        except asyncio.TimeoutError as exc:
            raise TranscriptHandlingError(
                "Brain provider timed out while generating a response"
            ) from exc
        except BrainError:
            raise
        except Exception as exc:
            raise TranscriptHandlingError(
                "Brain provider failed while generating a response"
            ) from exc

        if not isinstance(response, BrainResponse):
            raise TranscriptHandlingError("Brain provider returned an invalid response")

        if self._speech_output is not None:
            reply_text = response.reply.strip() if isinstance(response.reply, str) else ""
            if reply_text:
                try:
                    await self._speech_output.speak(response)
                except Exception as exc:
                    logger.warning("event=tts_output_failed error=%s", type(exc).__name__)

        return response

    async def aclose(self) -> None:
        """Release underlying provider and speech output resources."""
        tts_error: BaseException | None = None
        if self._speech_output is not None:
            close = getattr(self._speech_output, "aclose", None)
            if callable(close):
                try:
                    await close()
                except Exception as exc:
                    tts_error = exc
                    logger.warning("event=tts_close_failed error=%s", type(exc).__name__)

        close_provider = getattr(self._provider, "aclose", None)
        if callable(close_provider):
            await close_provider()

        if tts_error is not None:
            raise tts_error

    async def __aenter__(self) -> TranscriptBrainCoordinator:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()


def transcript_coordinator_from_environment(
    environ: Mapping[str, str] | None = None,
    *,
    load_env: bool = True,
    dotenv_path: Path | str | None = None,
    timeout_seconds: float = 30.0,
    enable_tts: bool = False,
    speech_output: SpeechService | None = None,
) -> TranscriptBrainCoordinator:
    """Build a TranscriptBrainCoordinator configured from environment variables.

    Reads ``OPENAGENT_PROVIDER`` and the selected provider's credentials (e.g.
    ``GEMINI_API_KEY`` and ``GEMINI_MODEL``). When ``enable_tts`` is True and
    ``speech_output`` is None, initializes speech output using
    :func:`speech_output_from_environment`. Credentials are never logged.
    """
    config = AppConfig.from_brain_environment(environ, load_env=load_env, dotenv_path=dotenv_path)
    provider = create_brain_provider(config.provider)

    resolved_speech_output = speech_output
    if resolved_speech_output is None and enable_tts:
        from .tts import speech_output_from_environment

        resolved_speech_output = speech_output_from_environment(environ, load_env=load_env)

    return TranscriptBrainCoordinator(
        provider,
        timeout_seconds=timeout_seconds,
        speech_output=resolved_speech_output,
    )


async def _run_coordinator(
    coordinator: TranscriptBrainCoordinator,
    transcript: str,
    *,
    session_id: str | None,
) -> BrainResponse:
    try:
        return await coordinator.respond_to_transcript(transcript, session_id=session_id)
    finally:
        await coordinator.aclose()


def main(argv: Sequence[str] | None = None) -> int:
    """Send a transcript to the configured brain provider and display/speak the response safely."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Send a finalized transcript to the configured AI brain provider."
    )
    parser.add_argument(
        "transcript",
        nargs="?",
        default="Hello Jarvis, this is a test transcript. Respond in 5 words or less.",
        help="Transcript text to process (default: short test phrase)",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Optional session ID for conversation tracking",
    )
    parser.add_argument(
        "--tts",
        action="store_true",
        default=False,
        help="Enable text-to-speech audio playback of the response",
    )
    args = parser.parse_args(argv)

    try:
        coordinator = transcript_coordinator_from_environment(enable_tts=args.tts)
    except ConfigurationError as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2
    except BrainError as error:
        print(f"Brain configuration error: {error}", file=sys.stderr)
        return 2

    print(f"Provider: {coordinator._provider!r}")
    if coordinator._speech_output is not None:
        print("Speech output: enabled")
    print(f"Transcript: {args.transcript}")
    try:
        response = asyncio.run(
            _run_coordinator(coordinator, args.transcript, session_id=args.session_id)
        )
    except TranscriptHandlingError as error:
        print(f"Transcript handling error: {error}", file=sys.stderr)
        return 1
    except BrainError as error:
        print(f"Brain error: {error}", file=sys.stderr)
        return 1

    print(f"Response: {response.reply}")
    if response.model:
        print(f"Model: {response.model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "SpeechService",
    "TranscriptBrainCoordinator",
    "TranscriptHandlingError",
    "main",
    "transcript_coordinator_from_environment",
]
