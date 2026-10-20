# OpenAgent Realtime Conversation

Real-time voice-conversation component of OpenAgent, a personal Windows assistant.

This repository is one component of that assistant. Wake-word detection lives in
[`openagent-wakeword`](https://github.com/Sanj1th-M/openagent-wakeword). Desktop
automation through UFO² is future work and has no implementation in this repository.

`main` contains the Phase 2 configuration foundation: package version `0.1.0` validates
settings and prints a safe status event. It does not capture audio, call a speech service,
generate replies, or play speech. This feature branch proposes Phase 3 speech input; it is
not merged into `main`. Phase 3 adds a local microphone command that uses Pipecat and
Deepgram Flux for speech-to-text, but does not add wake-word integration, AI responses,
text-to-speech, or Windows automation.

See [Project status](docs/PROJECT_STATUS.md) for the implemented, in-progress, planned,
and unknown lists. The documentation files describe the merged `main` state unless they
explicitly identify an open Phase 3 proposal.

## Documentation

| Document | Contents |
| --- | --- |
| [Architecture](docs/ARCHITECTURE.md) | Merged package structure and configuration flow |
| [Project status](docs/PROJECT_STATUS.md) | Implemented, in-progress, planned, and unknown work |
| [Setup](docs/SETUP.md) | Local install and the configuration command |
| [Security](docs/SECURITY.md) | Credentials, logging, and automated scans |
| [Testing](docs/TESTING.md) | Test inventory and check commands |
| [Decisions](docs/DECISIONS.md) | Decisions recorded by the merged tree and open proposals |
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

```powershell
$env:OPENAGENT_PROVIDER = "example"
$env:OPENAGENT_PROVIDER_API_KEY = "your-local-secret"
openagent-realtime-config
```

On success the process logs a JSON event containing the provider name and exits `0`. On
invalid configuration it logs `configuration_invalid`, prints a plain-text error to stderr,
and exits `2`. Keep credentials out of source, logs, and committed `.env` files. Install
steps for the merged configuration command are in [Setup](docs/SETUP.md).

## Phase 3 speech-to-text proposal

This feature branch adds the proposed `openagent-realtime-stt` command. Install the project
into the repository virtual environment, then set the Deepgram credential in the current
PowerShell session. Do not pass the key as a command-line argument.

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
program that owns the microphone first. The runtime dependency set on this branch includes
Pipecat's documented Deepgram and local-audio extras. Future milestones may add wake-word
coordination only after microphone ownership is designed explicitly.

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
PyAudio before installing the Phase 3 local-audio dependency. Security scans and their limits
are documented in [Security](docs/SECURITY.md); check details are in [Testing](docs/TESTING.md).

## Intended direction

The merged README history records the intended direction as Python, Pipecat, verified
speech-recognition and text-to-speech providers, and later integration with
`openagent-wakeword` and an OpenAgent coordinator. The feature branch's Phase 3 dependency
does not make those later integrations implemented. The GitHub repository description names
Pipecat, Deepgram Flux, and speech synthesis as product direction, not as an end-to-end
capability already merged into `main`.
