"""Safe, opt-in live smoke tests for configured brain providers.

The command loads a local .env without overriding process settings and never
prints credentials, request headers, or response text.  It sends one fixed,
non-sensitive prompt only to providers explicitly configured for testing.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Mapping, Sequence

import httpx

from .brain import BrainError, BrainRequest
from .config import AppConfig, ConfigurationError, ProviderSettings, load_environment
from .providers import create_brain_provider

_PROVIDERS = ("openrouter", "gemini", "openai", "anthropic", "ollama")
_KEY_VARIABLES = {
    "openrouter": "OPENROUTER_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}
_PROMPT = "Reply with the single word: ready"


def _configured_providers(environment: dict[str, str]) -> list[str]:
    """Select explicit keys, Ollama, and the generic-key selected provider only."""
    selected = environment.get("OPENAGENT_PROVIDER", "").strip().lower()
    providers = [
        provider
        for provider, variable in _KEY_VARIABLES.items()
        if environment.get(variable, "").strip()
    ]
    if selected in _KEY_VARIABLES and environment.get("OPENAGENT_PROVIDER_API_KEY", "").strip():
        providers.append(selected)
    if (
        selected == "ollama"
        or environment.get("OLLAMA_MODEL", "").strip()
        or environment.get("OLLAMA_BASE_URL", "").strip()
    ):
        providers.append("ollama")
    return list(dict.fromkeys(providers))


def _configuration_for(provider: str, environment: dict[str, str]) -> AppConfig:
    selected = environment.get("OPENAGENT_PROVIDER", "").strip().lower()
    # If the requested provider is the globally selected provider, it should
    # inherit the generic OPENAGENT_PROVIDER_MODEL if no provider-specific model is set.
    # If it is NOT the selected provider, create an isolated environment view so that
    # OPENAGENT_PROVIDER_MODEL belonging to another provider does not leak into it.
    if provider == selected:
        provider_env = environment
    else:
        provider_env = dict(environment)
        provider_env.pop("OPENAGENT_PROVIDER_MODEL", None)

    if provider == "openrouter":
        return AppConfig.from_openrouter_environment(provider_env, load_env=False)
    if provider == "gemini":
        return AppConfig.from_gemini_environment(provider_env, load_env=False)
    if provider == "openai":
        return AppConfig.from_openai_environment(provider_env, load_env=False)
    if provider == "anthropic":
        return AppConfig.from_anthropic_environment(provider_env, load_env=False)
    return AppConfig.from_ollama_environment(provider_env, load_env=False)


async def _ollama_model_available(settings: ProviderSettings) -> tuple[bool, str]:
    base_url = (settings.base_url or "http://127.0.0.1:11434").rstrip("/")
    model = settings.model or "llama3.2"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}/api/tags")
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return False, "local Ollama service is unavailable"
    models = payload.get("models") if isinstance(payload, dict) else None
    names = {item.get("name") for item in models or [] if isinstance(item, dict)}
    if model not in names and f"{model}:latest" not in names:
        return False, f"configured Ollama model {model!r} is not installed"
    return True, ""


async def smoke_test(
    providers: Sequence[str] | None = None,
    *,
    test_all: bool = False,
    load_env: bool = True,
    environ: Mapping[str, str] | None = None,
) -> int:
    """Run requested configured providers and print only status-safe output.

    If neither providers nor test_all is specified, defaults to testing only
    the provider selected by OPENAGENT_PROVIDER (if configured).
    If test_all is True, tests all configured providers.
    """
    if load_env:
        load_environment()
    environment = dict(os.environ if environ is None else environ)
    selected = environment.get("OPENAGENT_PROVIDER", "").strip().lower()

    if providers:
        requested = list(providers)
    elif test_all:
        requested = list(_PROVIDERS)
    elif selected in _PROVIDERS:
        requested = [selected]
    else:
        requested = list(_PROVIDERS)

    exit_code = 0
    configured = set(_configured_providers(environment))
    for name in requested:
        if name not in configured:
            print(f"SKIP {name}: no provider-specific credential or selected generic configuration")
            continue
        try:
            configuration = _configuration_for(name, environment)
            if name == "ollama":
                available, reason = await _ollama_model_available(configuration.provider)
                if not available:
                    print(f"SKIP ollama: {reason}")
                    continue
            response = await create_brain_provider(configuration.provider).generate_response(
                BrainRequest(message=_PROMPT)
            )
        except (ConfigurationError, BrainError) as exc:
            print(f"FAIL {name}: {exc}", file=sys.stderr)
            exit_code = 1
        else:
            print(f"PASS {name}: response received from {response.model or 'configured model'}")
    return exit_code


def main(argv: Sequence[str] | None = None) -> int:
    """Run the smoke command; no credentials are accepted on the command line."""
    parser = argparse.ArgumentParser(description="Safely smoke-test configured brain providers.")
    parser.add_argument(
        "--provider",
        choices=_PROVIDERS,
        action="append",
        dest="providers",
        help="Specific provider(s) to test. Can be passed multiple times.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="test_all",
        help="Test all configured providers instead of only the selected OPENAGENT_PROVIDER.",
    )
    arguments = parser.parse_args(argv)
    return asyncio.run(smoke_test(arguments.providers, test_all=arguments.test_all))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
