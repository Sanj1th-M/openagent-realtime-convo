# openagent Realtime Conversation

Real-time voice-conversation component of openagent, a personal Windows assistant.

This repository is one component of that assistant. Wake-word detection lives in
[`openagent-wakeword`](https://github.com/Sanj1th-M/openagent-wakeword). Desktop
automation through UFO² is future work and has no implementation in this repository.

`main` contains the Phase 2 configuration foundation and the Phase 3 speech-input
pipeline. Package version `0.1.0` validates settings, prints a safe status event, and
runs local microphone capture through Deepgram Flux speech-to-text. The pipeline prints
transcript lines to stdout but does not generate AI replies, produce speech output, or
integrate with the wake-word component.

See [Project status](docs/PROJECT_STATUS.md) for the implemented, planned, and unknown
lists.

## Documentation

| Document | Contents |
| --- | --- |
| [Architecture](docs/ARCHITECTURE.md) | Merged package structure and configuration flow |
| [Project status](docs/PROJECT_STATUS.md) | Implemented, in-progress, planned, and unknown work |
| [Setup](docs/SETUP.md) | Local install and the configuration command |
| [Security](docs/SECURITY.md) | Credentials, logging, and automated scans |
| [Testing](docs/TESTING.md) | Test inventory and check commands |
| [Decisions](docs/DECISIONS.md) | Decisions recorded by the merged tree |
| [Jarvis vision](docs/JARVIS_VISION.md) | Long-term assistant goal, separate from current capabilities |
| [Integration map](docs/INTEGRATION_MAP.md) | Repository boundaries and planned connections |
| [Roadmap](docs/ROADMAP.md) | Implemented, in-progress, planned, and undecided work |
| [Agent handoff](docs/AGENT_HANDOFF.md) | Concise context and template for the next coding agent |
| [AGENTS.md](AGENTS.md) | Working rules for coding agents |

## Current configuration command

The Phase 2 configuration command reads the process environment:

| Variable | Required | Default |
| --- | --- | --- |
| `OPENAGENT_PROVIDER` | yes | — |
| `OPENAGENT_PROVIDER_API_KEY` | yes | — |
| `OPENAGENT_AUDIO_SAMPLE_RATE_HZ` | no | `16000` |
| `OPENAGENT_AUDIO_CHANNELS` | no | `1` |
| `OPENAGENT_AUDIO_CHUNK_SIZE` | no | `320` |

Audio values must be positive integers. The API key is omitted from object
representations and structured log records.

## Brain providers (Phase 4 in progress)

The provider-independent brain interface currently has asynchronous OpenRouter,
Google Gemini, OpenAI, Anthropic Claude, and Ollama adapters. They are library
components only: the conversation coordinator does not yet call them, so they
do not produce replies in the current microphone pipeline.

For Gemini, set `GEMINI_API_KEY` (or the shared
`OPENAGENT_PROVIDER_API_KEY`) and optionally `GEMINI_MODEL` (or
`OPENAGENT_PROVIDER_MODEL`), then build configuration with
`AppConfig.from_gemini_environment()`. The default model is
`gemini-2.0-flash`. Copy [.env.example](.env.example) to a local `.env` file;
it is loaded without overriding values already present in the process
environment. Never commit the local `.env` file.

For OpenAI, use `OPENAI_API_KEY` (or `OPENAGENT_PROVIDER_API_KEY`) and
optionally `OPENAI_MODEL` (or `OPENAGENT_PROVIDER_MODEL`) with
`AppConfig.from_openai_environment()`. Its default model is `gpt-4o-mini`.

For Claude, use `ANTHROPIC_API_KEY` (or `OPENAGENT_PROVIDER_API_KEY`) and
optionally `ANTHROPIC_MODEL` (or `OPENAGENT_PROVIDER_MODEL`) with
`AppConfig.from_anthropic_environment()`. Its default model is
`claude-3-5-haiku-latest`.

For Ollama, use `OLLAMA_BASE_URL` and `OLLAMA_MODEL` with
`AppConfig.from_ollama_environment()`. It defaults to the local Ollama API at
`http://127.0.0.1:11434` and model `llama3.2`; no API key is required for the
standard local API.

`AppConfig.from_brain_environment()` selects any of the five adapters from
`OPENAGENT_PROVIDER`, preferring that provider's API key and model variables
over the generic fallbacks. A local `.env` is loaded without replacing process
environment values. `TranscriptBrainCoordinator` accepts one non-empty,
finalized STT transcript and returns the selected provider's `BrainResponse`;
it has no TTS dependency and is not yet wired into the live microphone command.

### Optional live brain smoke test

After configuring a local `.env`, run `openagent-realtime-brain-smoke`. It
uses a fixed non-sensitive prompt, prints only PASS/FAIL/SKIP status (never
keys or response text), and skips remote providers without a provider-specific
key unless that provider is the selected generic-key provider. Use
`--provider openai` (or another listed provider) to limit the run. Before an
Ollama request, it checks that the local service responds and the configured
model is installed.

```powershell
$env:OPENAGENT_PROVIDER = "example"
$env:OPENAGENT_PROVIDER_API_KEY = "your-local-secret"
openagent-realtime-config
```

On success the process logs a JSON event containing the provider name and exits `0`. On
invalid configuration it logs `configuration_invalid`, prints a plain-text error to stderr,
and exits `2`. Keep credentials out of source, logs, and committed `.env` files. Install
steps for the merged configuration command are in [Setup](docs/SETUP.md).

## Speech-to-text command

The `openagent-realtime-stt` command is merged into `main`. Install the project into the
repository virtual environment, then set the Deepgram credential in the current PowerShell
session. Do not pass the key as a command-line argument.

```powershell
.venv\Scripts\python.exe -m pip install -e .
$env:DEEPGRAM_API_KEY = "your-deepgram-key"
openagent-realtime-stt
```

The command validates that `DEEPGRAM_API_KEY` is present before opening the microphone. When
Deepgram Flux provides a non-empty incremental update, the command writes `[INTERIM]`; when
the service emits a non-empty finalized transcription frame, it writes `[FINAL]`. Press
`Ctrl+C` to stop it. Automated tests cover the event and output wiring, but a live microphone
session is still required to verify end-to-end recognition for a particular device and account.

During a live session, microphone audio is transmitted to Deepgram's cloud service for speech
recognition. Ensure Windows microphone access is enabled and stop any wake-word or other
program that owns the microphone first. The runtime dependency `pipecat-ai[deepgram,local]`
provides Pipecat's Deepgram and local-audio extras. Wake-word coordination is a future
milestone, pending a microphone-ownership design.

## Development and CI checks

The baseline is Python 3.12, matching the CI runtime. The package accepts Python `>=3.12`.

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

CI runs lint, formatting, tests, type checking, and a no-dependency wheel build on
`ubuntu-latest`. The Ubuntu job installs the PortAudio development headers required by
PyAudio before installing the package. Security scans and their limits are documented in
[Security](docs/SECURITY.md); check details are in [Testing](docs/TESTING.md).

## Intended direction

The intended direction is Python, Pipecat, verified speech-recognition and text-to-speech
providers, and later integration with `openagent-wakeword` and an openagent coordinator.
The merged Phase 3 pipeline captures audio and produces transcript lines but does not
generate AI replies, produce speech output, or coordinate with the wake-word component.
Those integrations remain planned. The GitHub repository description names Pipecat, Deepgram
Flux, and speech synthesis as product direction, not as an end-to-end capability.
