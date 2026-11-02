from __future__ import annotations

import pytest

from openagent_realtime_convo.brain import BrainProvider
from openagent_realtime_convo.config import (
    AppConfig,
    AudioSettings,
    ConfigurationError,
    ProviderSettings,
    load_environment,
)
from openagent_realtime_convo.providers import create_brain_provider


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


def test_load_environment_missing_file(tmp_path: pytest.TempPathFactory) -> None:
    from pathlib import Path

    non_existent = Path(str(tmp_path)) / ".env.doesnotexist"
    assert not load_environment(non_existent)


def test_load_environment_populates_os_environ(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os
    from pathlib import Path

    env_file = Path(str(tmp_path)) / ".env"
    env_file.write_text("TEST_OPENAGENT_VAR=test_val\n", encoding="utf-8")
    monkeypatch.delenv("TEST_OPENAGENT_VAR", raising=False)

    loaded = load_environment(env_file)
    assert loaded is True
    assert os.environ.get("TEST_OPENAGENT_VAR") == "test_val"


def test_load_environment_preserves_existing_os_precedence(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os
    from pathlib import Path

    env_file = Path(str(tmp_path)) / ".env"
    env_file.write_text("TEST_OPENAGENT_VAR=file_val\n", encoding="utf-8")
    monkeypatch.setenv("TEST_OPENAGENT_VAR", "os_val")

    load_environment(env_file)
    assert os.environ.get("TEST_OPENAGENT_VAR") == "os_val"


def test_app_config_from_environment_loads_dotenv(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathlib import Path

    env_file = Path(str(tmp_path)) / ".env"
    env_file.write_text(
        "OPENAGENT_PROVIDER=test_provider\nOPENAGENT_PROVIDER_API_KEY=test_key_fake\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAGENT_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAGENT_PROVIDER_API_KEY", raising=False)

    config = AppConfig.from_environment(dotenv_path=env_file)
    assert config.provider.name == "test_provider"
    assert config.provider.api_key == "test_key_fake"


def test_app_config_from_environment_respects_os_override(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathlib import Path

    env_file = Path(str(tmp_path)) / ".env"
    env_file.write_text(
        "OPENAGENT_PROVIDER=file_provider\nOPENAGENT_PROVIDER_API_KEY=file_key_fake\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAGENT_PROVIDER", "os_provider")
    monkeypatch.setenv("OPENAGENT_PROVIDER_API_KEY", "os_key_fake")

    config = AppConfig.from_environment(dotenv_path=env_file)
    assert config.provider.name == "os_provider"
    assert config.provider.api_key == "os_key_fake"


def test_app_config_from_deepgram_environment_loads_dotenv(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathlib import Path

    env_file = Path(str(tmp_path)) / ".env"
    env_file.write_text("DEEPGRAM_API_KEY=fake_deepgram_key\n", encoding="utf-8")
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)

    config = AppConfig.from_deepgram_environment(dotenv_path=env_file)
    assert config.provider.name == "deepgram"
    assert config.provider.api_key == "fake_deepgram_key"


def test_app_config_from_openrouter_environment_loads_dotenv(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathlib import Path

    env_file = Path(str(tmp_path)) / ".env"
    env_file.write_text(
        "OPENROUTER_API_KEY=fake_or_key\nOPENROUTER_MODEL=test/model\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAGENT_PROVIDER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

    config = AppConfig.from_openrouter_environment(dotenv_path=env_file)
    assert config.provider.name == "openrouter"
    assert config.provider.api_key == "fake_or_key"
    assert config.provider.model == "test/model"


@pytest.mark.parametrize(
    ("provider", "key_name"),
    [
        ("openrouter", "OPENROUTER_API_KEY"),
        ("gemini", "GEMINI_API_KEY"),
        ("openai", "OPENAI_API_KEY"),
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("ollama", None),
    ],
)
def test_from_brain_environment_selects_each_supported_provider(
    provider: str, key_name: str | None
) -> None:
    environment = {"OPENAGENT_PROVIDER": provider, "OPENAGENT_PROVIDER_MODEL": "test-model"}
    if key_name is not None:
        environment[key_name] = "provider-key"

    config = AppConfig.from_brain_environment(environment)

    assert config.provider.name == provider
    assert config.provider.model == "test-model"


def test_from_brain_environment_uses_generic_key_for_selected_provider() -> None:
    config = AppConfig.from_brain_environment(
        {"OPENAGENT_PROVIDER": "openai", "OPENAGENT_PROVIDER_API_KEY": "generic-key"}
    )
    assert config.provider.name == "openai"
    assert config.provider.api_key == "generic-key"


def test_from_brain_environment_rejects_unknown_provider() -> None:
    with pytest.raises(ConfigurationError, match="must be one of"):
        AppConfig.from_brain_environment(
            {"OPENAGENT_PROVIDER": "unknown", "OPENAGENT_PROVIDER_API_KEY": "key"}
        )


@pytest.mark.parametrize(
    ("provider", "key_name"),
    [
        ("openrouter", "OPENROUTER_API_KEY"),
        ("gemini", "GEMINI_API_KEY"),
        ("openai", "OPENAI_API_KEY"),
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("ollama", None),
    ],
)
def test_common_brain_configuration_selects_a_factory_provider(
    provider: str, key_name: str | None
) -> None:
    environment = {"OPENAGENT_PROVIDER": provider}
    if key_name is not None:
        environment[key_name] = "provider-key"

    configuration = AppConfig.from_brain_environment(environment)

    assert isinstance(create_brain_provider(configuration.provider), BrainProvider)


def test_from_brain_environment_loads_dotenv_without_overriding_process_environment(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathlib import Path

    env_file = Path(str(tmp_path)) / ".env"
    env_file.write_text("OPENAGENT_PROVIDER=openai\nOPENAI_API_KEY=file-key\n", encoding="utf-8")
    monkeypatch.setenv("OPENAGENT_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "process-key")

    config = AppConfig.from_brain_environment(dotenv_path=env_file)

    assert config.provider.name == "gemini"
    assert config.provider.api_key == "process-key"
