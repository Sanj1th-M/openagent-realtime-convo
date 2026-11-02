"""Unit tests for the live brain smoke testing utility."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from openagent_realtime_convo.brain import BrainResponse
from openagent_realtime_convo.brain_smoke import (
    _configuration_for,
    _configured_providers,
    smoke_test,
)


def test_configured_providers_detects_explicit_keys_and_selected() -> None:
    env = {
        "OPENAI_API_KEY": "test-openai-key",
        "OPENROUTER_API_KEY": "test-or-key",
        "OPENAGENT_PROVIDER": "openrouter",
    }
    providers = _configured_providers(env)
    assert "openai" in providers
    assert "openrouter" in providers
    assert "gemini" not in providers
    assert "anthropic" not in providers
    assert "ollama" not in providers


def test_configured_providers_detects_generic_key_for_selected() -> None:
    env = {
        "OPENAGENT_PROVIDER": "anthropic",
        "OPENAGENT_PROVIDER_API_KEY": "generic-key",
    }
    providers = _configured_providers(env)
    assert providers == ["anthropic"]


def test_configuration_for_isolates_unselected_provider_model() -> None:
    env = {
        "OPENAGENT_PROVIDER": "openrouter",
        "OPENAGENT_PROVIDER_MODEL": "openrouter/free",
        "OPENROUTER_API_KEY": "or-key",
        "OPENAI_API_KEY": "openai-key",
    }
    # For openrouter (selected), OPENAGENT_PROVIDER_MODEL is preserved
    or_config = _configuration_for("openrouter", env)
    assert or_config.provider.model == "openrouter/free"

    # For openai (not selected), OPENAGENT_PROVIDER_MODEL is NOT leaked
    openai_config = _configuration_for("openai", env)
    assert openai_config.provider.model is None


def test_configuration_for_respects_provider_specific_model() -> None:
    env = {
        "OPENAGENT_PROVIDER": "openrouter",
        "OPENAGENT_PROVIDER_MODEL": "openrouter/free",
        "OPENROUTER_API_KEY": "or-key",
        "OPENAI_API_KEY": "openai-key",
        "OPENAI_MODEL": "gpt-4o",
    }
    openai_config = _configuration_for("openai", env)
    assert openai_config.provider.model == "gpt-4o"


@pytest.mark.anyio
async def test_smoke_test_defaults_to_selected_provider_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("OPENAGENT_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "mock-or-key")
    monkeypatch.setenv("OPENAI_API_KEY", "mock-openai-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": "ready"}}], "model": "mock-or-model"},
        )

    # Mock create_brain_provider or HTTP calls
    mock_provider = AsyncMock()
    mock_provider.generate_response.return_value = BrainResponse(reply="ready", model="mock-model")

    with patch(
        "openagent_realtime_convo.brain_smoke.create_brain_provider",
        return_value=mock_provider,
    ):
        code = await smoke_test()

    assert code == 0
    captured = capsys.readouterr()
    assert "PASS openrouter" in captured.out
    # openai should NOT have run in default mode
    assert "openai" not in captured.out


@pytest.mark.anyio
async def test_smoke_test_all_flag_runs_all_configured(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("OPENAGENT_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "mock-or-key")
    monkeypatch.setenv("OPENAI_API_KEY", "mock-openai-key")

    mock_provider = AsyncMock()
    mock_provider.generate_response.return_value = BrainResponse(reply="ready", model="mock-model")

    with patch(
        "openagent_realtime_convo.brain_smoke.create_brain_provider",
        return_value=mock_provider,
    ):
        code = await smoke_test(test_all=True)

    assert code == 0
    captured = capsys.readouterr()
    assert "PASS openrouter" in captured.out
    assert "PASS openai" in captured.out
    assert "SKIP gemini" in captured.out
