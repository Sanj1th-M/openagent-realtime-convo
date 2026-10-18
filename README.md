# OpenAgent Realtime Conversation

This repository is the future real-time voice-conversation component of OpenAgent. It is
currently a development foundation with a speech-to-text-only local microphone command. It has
no wake-word integration, AI response generation, text-to-speech, or Windows automation.

## Current functionality

The original configuration command validates generic provider settings without creating a device
or provider client. The separate speech command captures local microphone audio through Pipecat
and sends it to Deepgram Flux for transcription.

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

## Speech-to-text (Phase 3)

Install the project into the repository virtual environment, then set the documented Deepgram
credential in the current PowerShell session. Do not pass the key as a command-line argument.

```powershell
.venv\Scripts\python.exe -m pip install -e .
$env:DEEPGRAM_API_KEY = "your-deepgram-key"
openagent-realtime-stt
```

The command validates the key exists before opening the microphone. It prints `[INTERIM]` for
partial recognition and `[FINAL]` for completed transcript results. Press `Ctrl+C` to stop it.

During a live session, microphone audio is transmitted to Deepgram's cloud service for speech
recognition. Ensure Windows microphone access is enabled and stop any wake-word or other program
that owns the microphone first. This milestone does not make a live request during automated tests.

The runtime dependency set includes Pipecat's documented Deepgram and local-audio extras. Future
milestones may add wake-word coordination after microphone ownership is designed explicitly.

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
