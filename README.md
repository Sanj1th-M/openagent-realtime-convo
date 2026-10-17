# OpenAgent Realtime Conversation

This repository is the future real-time voice-conversation component of OpenAgent. It is
currently a development foundation only: no voice pipeline, wake-word integration, audio
device integration, API client, or text-to-speech provider has been implemented yet.

## Current functionality

Phase 2 provides an installable Python package with a small, typed configuration boundary.
It validates audio capture settings and a generic future-provider identity; it does not create
an audio device or a provider client.

Configuration is read only from environment variables:

- `OPENAGENT_PROVIDER` (required): a provider identifier.
- `OPENAGENT_PROVIDER_API_KEY` (required): its credential. This is never logged and is hidden
  from the configuration object's representation.
- `OPENAGENT_AUDIO_SAMPLE_RATE_HZ` (optional, default `16000`)
- `OPENAGENT_AUDIO_CHANNELS` (optional, default `1`)
- `OPENAGENT_AUDIO_CHUNK_SIZE` (optional, default `320`)

All audio values must be positive integers. To validate a local configuration without starting
any voice service:

```powershell
$env:OPENAGENT_PROVIDER = "example"
$env:OPENAGENT_PROVIDER_API_KEY = "your-local-secret"
openagent-realtime-config
```

The command writes a structured JSON status event containing the provider name only. Do not put
credentials in source code, logs, or committed `.env` files.

The intended direction is Python, Pipecat, verified speech recognition and text-to-speech
providers, and later integration with `openagent-wakeword` and the OpenAgent coordinator.
Those dependencies are intentionally not declared until their compatibility and integration
requirements are established.

## Development checks

The baseline is Python 3.12, matching the locally verified interpreter and CI runtime.

```powershell
python -m pip install -r requirements-dev.txt
python -m pip install -e .
ruff check .
ruff format --check .
pytest
mypy
python -m pip wheel --no-deps . --wheel-dir dist
bandit -ll -r src
pip-audit -r requirements-dev.txt
```

`pip-audit` checks the declared development dependencies. Bandit scans tracked production
Python files in GitHub Actions. CodeQL is included for future Python source and may require
GitHub code scanning to be available for this repository.

## Automation

CI runs on pushes to `main`, pull requests targeting `main`, and manual dispatch. Security
scans run on the same events plus a weekly schedule. Workflow permissions are read-only except
for the CodeQL job's required `security-events: write` permission. Third-party action commits
are pinned and maintained by Dependabot; CodeQL follows GitHub's recommended `v4` major tag so
analysis engine updates remain available.
