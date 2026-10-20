# OpenAgent Realtime Conversation

Real-time voice conversation component of OpenAgent, a personal Windows assistant.

This repository is one component of that assistant. Wake-word detection lives in
[`openagent-wakeword`](https://github.com/Sanj1th-M/openagent-wakeword). Desktop
automation through UFO² is future work and has no implementation in this repository.

The merged code on this branch is the Phase 2 configuration foundation, package
version `0.1.0`, commit `47ecc5a`. It validates settings and prints a safe status
event. It does not capture audio, call a speech service, generate replies, or
play speech.

Phase 3 speech input is an open, unmerged proposal in
[pull request #10](https://github.com/Sanj1th-M/openagent-realtime-convo/pull/10).
See [Project status](docs/PROJECT_STATUS.md) for the implemented, in-progress,
planned, and unknown lists.

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

## Current command

Configuration is read from the process environment:

| Variable | Required | Default |
| --- | --- | --- |
| `OPENAGENT_PROVIDER` | yes | — |
| `OPENAGENT_PROVIDER_API_KEY` | yes | — |
| `OPENAGENT_AUDIO_SAMPLE_RATE_HZ` | no | `16000` |
| `OPENAGENT_AUDIO_CHANNELS` | no | `1` |
| `OPENAGENT_AUDIO_CHUNK_SIZE` | no | `320` |

Audio values must be positive integers. The API key is omitted from object
representations and from the structured log record.

```powershell
$env:OPENAGENT_PROVIDER = "example"
$env:OPENAGENT_PROVIDER_API_KEY = "your-local-secret"
openagent-realtime-config
```

On success the process logs a JSON event that contains the provider name, then
exits `0`. On invalid configuration it logs `configuration_invalid`, prints a
plain-text error to stderr, and exits `2`. Keep credentials out of source,
logs, and committed `.env` files. Install steps are in [Setup](docs/SETUP.md).

## Intended direction

The merged README history records the intended direction as Python, Pipecat,
verified speech-recognition and text-to-speech providers, and later integration
with `openagent-wakeword` and an OpenAgent coordinator. Those voice dependencies
are absent from the merged `pyproject.toml`. The dependency list stays empty
until compatibility and integration requirements are established.

The GitHub repository description names Pipecat, Deepgram Flux, and speech
synthesis. That description matches the intended product direction. It does not
describe the merged implementation.

## Development baseline

The documented interpreter and the CI runtime are Python 3.12. The package
accepts `>=3.12`. Local check commands are in [Testing](docs/TESTING.md).
