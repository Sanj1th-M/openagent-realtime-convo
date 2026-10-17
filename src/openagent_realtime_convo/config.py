"""Validated, environment-backed application configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field


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

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ConfigurationError("provider name must not be empty")
        if not self.api_key.strip():
            raise ConfigurationError("provider API key must not be empty")


@dataclass(frozen=True, slots=True)
class AppConfig:
    """All configuration needed by the minimal application foundation."""

    audio: AudioSettings
    provider: ProviderSettings

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> AppConfig:
        """Build configuration from environment variables without logging credentials.

        Required variables are ``OPENAGENT_PROVIDER`` and
        ``OPENAGENT_PROVIDER_API_KEY``. Optional audio variables are
        ``OPENAGENT_AUDIO_SAMPLE_RATE_HZ``, ``OPENAGENT_AUDIO_CHANNELS``, and
        ``OPENAGENT_AUDIO_CHUNK_SIZE``.
        """
        environment = os.environ if environ is None else environ
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
