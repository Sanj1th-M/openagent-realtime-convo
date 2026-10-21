# Decisions

Decisions evidenced by the merged tree at commit `b589041`.
Items without a recorded choice are listed as unknown in
[Project status](PROJECT_STATUS.md). This file does not add acceptance
criteria or integration contracts.

## Accepted

### D-001. Wake-word detection stays in `openagent-wakeword`

This repository is the conversation component. The merged README names later
integration with `openagent-wakeword` and does not include a detector,
wake-phrase model, or wake-word handoff handler. The handoff contract remains
unknown; see [Integration map](INTEGRATION_MAP.md).

### D-002. Phase 2 configuration comes from the process environment

`AppConfig.from_environment` reads a mapping or `os.environ`. The implemented
variables are `OPENAGENT_PROVIDER`, `OPENAGENT_PROVIDER_API_KEY`,
`OPENAGENT_AUDIO_SAMPLE_RATE_HZ`, `OPENAGENT_AUDIO_CHANNELS`, and
`OPENAGENT_AUDIO_CHUNK_SIZE`. The package has no `.env` loader.

### D-003. Phase 2 provider settings are a generic name and credential

`ProviderSettings` validates a non-empty name and a non-empty API key. Pull
request #8 and the merged README describe this as a future-provider identity.
The merged code does not construct a provider client.

### D-004. Voice-pipeline dependencies declared via Pipecat

Phase 3 added `dependencies = ["pipecat-ai[deepgram,local]>=1.12.0,<2"]` to
`pyproject.toml` for Deepgram Flux speech-to-text and local microphone transport.
Additional voice-pipeline dependencies (text-to-speech, conversation models)
remain undeclared until those components are designed.

### D-005. Python 3.12 is the verified baseline

The README states that Python 3.12 matches the locally verified interpreter
and the CI runtime. CI selects `python-version: "3.12"`. The package
requirement is `>=3.12`, so the metadata also allows newer Python 3 versions.
CI does not matrix those versions.

### D-006. Structured output omits the API key

`ProviderSettings.api_key` uses `repr=False`. `JsonFormatter` writes `event`,
`level`, `logger`, and, when present, `provider`. The configuration command
logs the provider name on success. Configuration error messages identify the
invalid setting. `SpeechConfig` similarly redacts its `api_key` in `__repr__`.

### D-007. The package uses a src layout and setuptools

`pyproject.toml` sets `build-backend = "setuptools.build_meta"`, requires
`setuptools>=68`, and finds packages under `src`. The version is `0.1.0`.
The description is "Configuration foundation for openagent's future realtime
conversation service."

### D-008. License metadata is MIT

`pyproject.toml` sets `license = "MIT"`. Pull request #9 changed that field
from a `license = { text = "MIT" }` table to the SPDX string. The repository
has no `LICENSE` file. Adding one is an open question, not a second license
choice.

### D-009. CI permissions stay read-only, with pinned third-party actions

Workflow permissions are `contents: read`, except the CodeQL job's
`security-events: write`. `actions/checkout` and `actions/setup-python` are
pinned to commits. Dependabot updates pip and GitHub Actions weekly. The
comment text above those pins is stale. That drift is recorded in
[Project status](PROJECT_STATUS.md) and is not a decision to change the pin.

### D-010. CodeQL tracks the v4 major tag

The security workflow uses `github/codeql-action/init@v4` and
`github/codeql-action/analyze@v4`. The README says this follows GitHub's
recommended major tag so analysis engine updates remain available. Language
is `python` and `build-mode` is `none`.

### D-011. The merged quality gate is Ruff, strict pytest, strict mypy, Bandit, and pip-audit

Ruff selects `E`, `F`, `I`, and `B`. Pytest uses `--strict-config` and
`--strict-markers` and collects only `tests`. mypy is strict over `src` and
`tests`. Bandit is invoked at `-ll` (medium severity and higher). `pip-audit`
reads `requirements-dev.txt`.

### D-012. Phase 3 speech input through Pipecat and Deepgram Flux

Status: accepted via pull request #10 at commit `b589041`.

The pipeline connects `LocalAudioTransport → DeepgramFluxSTTService → TranscriptPrinter`
and provides the console script `openagent-realtime-stt`. Deepgram API key configuration
is read from `DEEPGRAM_API_KEY` via `AppConfig.from_deepgram_environment()`. Interim
and finalized transcripts are written to stdout. Wake-word integration, AI responses,
text-to-speech, and UFO² remain outside this milestone.

## Proposed

None currently open.

## Related documents

- [README](../README.md)
- [Architecture](ARCHITECTURE.md)
- [Project status](PROJECT_STATUS.md)
- [Security](SECURITY.md)
- [Testing](TESTING.md)
- [Integration map](INTEGRATION_MAP.md)
- [Roadmap](ROADMAP.md)
- [Agent guide](../AGENTS.md)
