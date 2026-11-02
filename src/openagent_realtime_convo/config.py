"""Validated, environment-backed application configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_ENV_PATH: Path = Path(__file__).resolve().parent.parent.parent / ".env"


def load_environment(dotenv_path: Path | str | None = None) -> bool:
    """Load environment variables from a .env file without overriding existing variables.

    When `dotenv_path` is None, defaults to `.env` located at the repository root.
    Existing operating-system / shell environment variables take precedence.
    Does not log or expose secret values.
    """
    path = Path(dotenv_path) if dotenv_path is not None else DEFAULT_ENV_PATH
    if not path.is_file():
        return False
    return bool(load_dotenv(dotenv_path=path, override=False))


class ConfigurationError(ValueError):
    """Raised when application configuration is absent or invalid."""


@dataclass(frozen=True, slots=True)
class AudioSettings:
    """Audio capture parameters, independent of any audio-device implementation."""

    sample_rate_hz: int = 16_000
    channels: int = 1
    chunk_size: int = 320

    def __post_init__(self) -> None:
        for name, value in (
            ("sample_rate_hz", self.sample_rate_hz),
            ("channels", self.channels),
            ("chunk_size", self.chunk_size),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ConfigurationError(f"{name} must be a positive integer")


@dataclass(frozen=True, slots=True)
class ProviderSettings:
    """Provider identity and its credential, without implementing a provider client."""

    name: str
    api_key: str = field(repr=False)
    model: str | None = None
    base_url: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ConfigurationError("provider name must not be empty")
        if not self.api_key.strip():
            raise ConfigurationError("provider API key must not be empty")
        if self.model is not None and (not isinstance(self.model, str) or not self.model.strip()):
            raise ConfigurationError("provider model must not be empty when provided")
        if self.base_url is not None and (
            not isinstance(self.base_url, str) or not self.base_url.strip()
        ):
            raise ConfigurationError("provider base URL must not be empty when provided")


@dataclass(frozen=True, slots=True)
class AppConfig:
    """All configuration needed by the minimal application foundation."""

    audio: AudioSettings
    provider: ProviderSettings

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        load_env: bool = True,
        dotenv_path: Path | str | None = None,
    ) -> AppConfig:
        """Build configuration from environment variables without logging credentials.

        Required variables are ``OPENAGENT_PROVIDER`` and
        ``OPENAGENT_PROVIDER_API_KEY``. Optional variables are
        ``OPENAGENT_PROVIDER_MODEL``, ``OPENAGENT_AUDIO_SAMPLE_RATE_HZ``,
        ``OPENAGENT_AUDIO_CHANNELS``, and ``OPENAGENT_AUDIO_CHUNK_SIZE``.

        If ``environ`` is None and ``load_env`` is True, loads ``.env`` into ``os.environ``
        without overriding existing environment variables.
        """
        if environ is None:
            if load_env:
                load_environment(dotenv_path=dotenv_path)
            environment: Mapping[str, str] = os.environ
        else:
            environment = environ
        model_name = environment.get("OPENAGENT_PROVIDER_MODEL")
        if model_name is not None:
            model_name = model_name.strip()
            if not model_name:
                raise ConfigurationError("OPENAGENT_PROVIDER_MODEL must not be empty when set")

        return cls(
            audio=AudioSettings(
                sample_rate_hz=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_SAMPLE_RATE_HZ", 16_000
                ),
                channels=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_CHANNELS", 1
                ),
                chunk_size=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_CHUNK_SIZE", 320
                ),
            ),
            provider=ProviderSettings(
                name=_required_environment_value(environment, "OPENAGENT_PROVIDER"),
                api_key=_required_environment_value(environment, "OPENAGENT_PROVIDER_API_KEY"),
                model=model_name,
            ),
        )

    @classmethod
    def from_brain_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        load_env: bool = True,
        dotenv_path: Path | str | None = None,
    ) -> AppConfig:
        """Build configuration for the brain provider selected by ``OPENAGENT_PROVIDER``.

        The selected provider determines which provider-specific credential and
        model variables are considered before the generic fallbacks.  This is
        the common configuration path for callers that should not need to know
        a provider's individual environment-variable names.
        """
        if environ is None:
            if load_env:
                load_environment(dotenv_path=dotenv_path)
            environment: Mapping[str, str] = os.environ
        else:
            environment = environ

        provider = _required_environment_value(environment, "OPENAGENT_PROVIDER").strip().lower()
        constructors = {
            "openrouter": cls.from_openrouter_environment,
            "gemini": cls.from_gemini_environment,
            "openai": cls.from_openai_environment,
            "anthropic": cls.from_anthropic_environment,
            "ollama": cls.from_ollama_environment,
        }
        constructor = constructors.get(provider)
        if constructor is None:
            supported = ", ".join(sorted(constructors))
            raise ConfigurationError(
                f"OPENAGENT_PROVIDER must be one of: {supported}; got {provider!r}"
            )
        return constructor(environment, load_env=False)

    @classmethod
    def from_deepgram_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        load_env: bool = True,
        dotenv_path: Path | str | None = None,
    ) -> AppConfig:
        """Build speech-to-text configuration from Deepgram's documented key variable.

        This leaves the generic provider configuration unchanged while giving the
        explicit speech command one unambiguous credential source.
        """
        if environ is None:
            if load_env:
                load_environment(dotenv_path=dotenv_path)
            environment: Mapping[str, str] = os.environ
        else:
            environment = environ
        return cls(
            audio=AudioSettings(
                sample_rate_hz=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_SAMPLE_RATE_HZ", 16_000
                ),
                channels=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_CHANNELS", 1
                ),
                chunk_size=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_CHUNK_SIZE", 320
                ),
            ),
            provider=ProviderSettings(
                name="deepgram",
                api_key=_required_environment_value(environment, "DEEPGRAM_API_KEY"),
            ),
        )

    @classmethod
    def from_openrouter_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        load_env: bool = True,
        dotenv_path: Path | str | None = None,
    ) -> AppConfig:
        """Build OpenRouter brain configuration from environment variables.

        Accepts ``OPENROUTER_API_KEY`` or ``OPENAGENT_PROVIDER_API_KEY``, with
        optional ``OPENROUTER_MODEL`` or ``OPENAGENT_PROVIDER_MODEL``.
        """
        if environ is None:
            if load_env:
                load_environment(dotenv_path=dotenv_path)
            environment: Mapping[str, str] = os.environ
        else:
            environment = environ
        api_key = environment.get("OPENROUTER_API_KEY") or environment.get(
            "OPENAGENT_PROVIDER_API_KEY"
        )
        if api_key is None or not api_key.strip():
            raise ConfigurationError("OPENROUTER_API_KEY or OPENAGENT_PROVIDER_API_KEY must be set")
        model = environment.get("OPENROUTER_MODEL") or environment.get("OPENAGENT_PROVIDER_MODEL")
        if model is not None:
            model = model.strip()
            if not model:
                model = None

        return cls(
            audio=AudioSettings(
                sample_rate_hz=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_SAMPLE_RATE_HZ", 16_000
                ),
                channels=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_CHANNELS", 1
                ),
                chunk_size=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_CHUNK_SIZE", 320
                ),
            ),
            provider=ProviderSettings(
                name="openrouter",
                api_key=api_key.strip(),
                model=model,
            ),
        )

    @classmethod
    def from_gemini_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        load_env: bool = True,
        dotenv_path: Path | str | None = None,
    ) -> AppConfig:
        """Build Gemini brain configuration from environment variables.

        Accepts ``GEMINI_API_KEY`` or ``OPENAGENT_PROVIDER_API_KEY``, with
        optional ``GEMINI_MODEL`` or ``OPENAGENT_PROVIDER_MODEL``.
        """
        if environ is None:
            if load_env:
                load_environment(dotenv_path=dotenv_path)
            environment: Mapping[str, str] = os.environ
        else:
            environment = environ
        api_key = environment.get("GEMINI_API_KEY") or environment.get("OPENAGENT_PROVIDER_API_KEY")
        if api_key is None or not api_key.strip():
            raise ConfigurationError("GEMINI_API_KEY or OPENAGENT_PROVIDER_API_KEY must be set")
        model = environment.get("GEMINI_MODEL") or environment.get("OPENAGENT_PROVIDER_MODEL")
        if model is not None:
            model = model.strip()
            if not model:
                model = None

        return cls(
            audio=AudioSettings(
                sample_rate_hz=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_SAMPLE_RATE_HZ", 16_000
                ),
                channels=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_CHANNELS", 1
                ),
                chunk_size=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_CHUNK_SIZE", 320
                ),
            ),
            provider=ProviderSettings(
                name="gemini",
                api_key=api_key.strip(),
                model=model,
            ),
        )

    @classmethod
    def from_openai_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        load_env: bool = True,
        dotenv_path: Path | str | None = None,
    ) -> AppConfig:
        """Build OpenAI brain configuration from environment variables.

        Accepts ``OPENAI_API_KEY`` or ``OPENAGENT_PROVIDER_API_KEY``, with
        optional ``OPENAI_MODEL`` or ``OPENAGENT_PROVIDER_MODEL``.
        """
        if environ is None:
            if load_env:
                load_environment(dotenv_path=dotenv_path)
            environment: Mapping[str, str] = os.environ
        else:
            environment = environ
        api_key = environment.get("OPENAI_API_KEY") or environment.get("OPENAGENT_PROVIDER_API_KEY")
        if api_key is None or not api_key.strip():
            raise ConfigurationError("OPENAI_API_KEY or OPENAGENT_PROVIDER_API_KEY must be set")
        model = environment.get("OPENAI_MODEL") or environment.get("OPENAGENT_PROVIDER_MODEL")
        if model is not None:
            model = model.strip()
            if not model:
                model = None

        return cls(
            audio=AudioSettings(
                sample_rate_hz=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_SAMPLE_RATE_HZ", 16_000
                ),
                channels=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_CHANNELS", 1
                ),
                chunk_size=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_CHUNK_SIZE", 320
                ),
            ),
            provider=ProviderSettings(
                name="openai",
                api_key=api_key.strip(),
                model=model,
            ),
        )

    @classmethod
    def from_anthropic_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        load_env: bool = True,
        dotenv_path: Path | str | None = None,
    ) -> AppConfig:
        """Build Anthropic brain configuration from environment variables.

        Accepts ``ANTHROPIC_API_KEY`` or ``OPENAGENT_PROVIDER_API_KEY``, with
        optional ``ANTHROPIC_MODEL`` or ``OPENAGENT_PROVIDER_MODEL``.
        """
        if environ is None:
            if load_env:
                load_environment(dotenv_path=dotenv_path)
            environment: Mapping[str, str] = os.environ
        else:
            environment = environ
        api_key = environment.get("ANTHROPIC_API_KEY") or environment.get(
            "OPENAGENT_PROVIDER_API_KEY"
        )
        if api_key is None or not api_key.strip():
            raise ConfigurationError("ANTHROPIC_API_KEY or OPENAGENT_PROVIDER_API_KEY must be set")
        model = environment.get("ANTHROPIC_MODEL") or environment.get("OPENAGENT_PROVIDER_MODEL")
        if model is not None:
            model = model.strip()
            if not model:
                model = None

        return cls(
            audio=AudioSettings(
                sample_rate_hz=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_SAMPLE_RATE_HZ", 16_000
                ),
                channels=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_CHANNELS", 1
                ),
                chunk_size=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_CHUNK_SIZE", 320
                ),
            ),
            provider=ProviderSettings(
                name="anthropic",
                api_key=api_key.strip(),
                model=model,
            ),
        )

    @classmethod
    def from_ollama_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        load_env: bool = True,
        dotenv_path: Path | str | None = None,
    ) -> AppConfig:
        """Build local Ollama brain configuration from environment variables.

        Reads optional ``OLLAMA_BASE_URL`` and ``OLLAMA_MODEL`` values, falling
        back to ``OPENAGENT_PROVIDER_MODEL`` for the model. Ollama does not
        require a credential for its standard local API, so this constructor
        supplies an internal marker required by the generic settings contract.
        """
        if environ is None:
            if load_env:
                load_environment(dotenv_path=dotenv_path)
            environment: Mapping[str, str] = os.environ
        else:
            environment = environ
        base_url = environment.get("OLLAMA_BASE_URL")
        if base_url is not None:
            base_url = base_url.strip()
            if not base_url:
                base_url = None
        model = environment.get("OLLAMA_MODEL") or environment.get("OPENAGENT_PROVIDER_MODEL")
        if model is not None:
            model = model.strip()
            if not model:
                model = None

        return cls(
            audio=AudioSettings(
                sample_rate_hz=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_SAMPLE_RATE_HZ", 16_000
                ),
                channels=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_CHANNELS", 1
                ),
                chunk_size=_positive_integer_from_environment(
                    environment, "OPENAGENT_AUDIO_CHUNK_SIZE", 320
                ),
            ),
            provider=ProviderSettings(
                name="ollama",
                api_key="ollama-local",
                model=model,
                base_url=base_url,
            ),
        )


def _required_environment_value(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if value is None or not value.strip():
        raise ConfigurationError(f"{name} must be set")
    return value


def _positive_integer_from_environment(
    environment: Mapping[str, str], name: str, default: int
) -> int:
    value = environment.get(name)
    if value is None:
        return default
    try:
        parsed_value = int(value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be a positive integer") from error
    if parsed_value <= 0:
        raise ConfigurationError(f"{name} must be a positive integer")
    return parsed_value
