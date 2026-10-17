from __future__ import annotations

import pytest

from openagent_realtime_convo.config import (
    AppConfig,
    AudioSettings,
    ConfigurationError,
    ProviderSettings,
)


def test_environment_configuration_uses_audio_defaults() -> None:
    configuration = AppConfig.from_environment(
        {"OPENAGENT_PROVIDER": "example", "OPENAGENT_PROVIDER_API_KEY": "not-a-real-key"}
    )

    assert configuration.audio == AudioSettings()
    assert configuration.provider.name == "example"


def test_environment_configuration_accepts_valid_values() -> None:
    configuration = AppConfig.from_environment(
        {
            "OPENAGENT_PROVIDER": "example",
            "OPENAGENT_PROVIDER_API_KEY": "not-a-real-key",
            "OPENAGENT_AUDIO_SAMPLE_RATE_HZ": "48000",
            "OPENAGENT_AUDIO_CHANNELS": "2",
            "OPENAGENT_AUDIO_CHUNK_SIZE": "960",
        }
    )

    assert configuration.audio == AudioSettings(sample_rate_hz=48_000, channels=2, chunk_size=960)


@pytest.mark.parametrize(
    ("setting", "value"),
    [("sample_rate_hz", 0), ("channels", -1), ("chunk_size", True)],
)
def test_audio_settings_reject_invalid_values(setting: str, value: int | bool) -> None:
    with pytest.raises(ConfigurationError, match=setting):
        AudioSettings(**{setting: value})


def test_environment_configuration_rejects_invalid_audio_value() -> None:
    with pytest.raises(ConfigurationError, match="OPENAGENT_AUDIO_CHANNELS"):
        AppConfig.from_environment(
            {
                "OPENAGENT_PROVIDER": "example",
                "OPENAGENT_PROVIDER_API_KEY": "not-a-real-key",
                "OPENAGENT_AUDIO_CHANNELS": "two",
            }
        )


@pytest.mark.parametrize(
    "environment",
    [{}, {"OPENAGENT_PROVIDER": "example"}, {"OPENAGENT_PROVIDER_API_KEY": "key"}],
)
def test_environment_configuration_requires_provider_settings(environment: dict[str, str]) -> None:
    with pytest.raises(ConfigurationError, match="must be set"):
        AppConfig.from_environment(environment)


def test_provider_settings_hides_api_key_in_representation() -> None:
    settings = ProviderSettings(name="example", api_key="not-a-real-key")

    assert "not-a-real-key" not in repr(settings)
