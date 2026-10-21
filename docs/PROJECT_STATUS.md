# Project status

Status of `openagent-realtime-convo` as inspected on 2026-10-22.

The documented tree is branch `main` at commit `b589041`. Package version `0.1.0`. Runtime
dependencies: `pipecat-ai[deepgram,local]>=1.12.0,<2`.

Categories below are exhaustive for this inspection. A capability listed in one
category is not implied in another.

## Implemented

Merged Phase 2 (PR #8 and housekeeping PR #9) and Phase 3 (PR #10).

- An installable src-layout package, `openagent-realtime-convo`, built with
  setuptools.
- Typed configuration: `AudioSettings`, `ProviderSettings`, `AppConfig`, and
  `ConfigurationError`.
- Environment variables `OPENAGENT_PROVIDER`, `OPENAGENT_PROVIDER_API_KEY`,
  `OPENAGENT_AUDIO_SAMPLE_RATE_HZ`, `OPENAGENT_AUDIO_CHANNELS`, and
  `OPENAGENT_AUDIO_CHUNK_SIZE`.
- Environment variable `DEEPGRAM_API_KEY` for speech-to-text configuration via
  `AppConfig.from_deepgram_environment()`.
- Validation of required provider settings and positive integer audio settings.
- API-key exclusion from `repr` and from the JSON log schema.
- Console scripts `openagent-realtime-config` and `openagent-realtime-stt`.
- Speech-to-text pipeline in `speech.py` using Pipecat and Deepgram Flux:
  `LocalAudioTransport → DeepgramFluxSTTService → TranscriptPrinter`.
- Unit tests: 10 in `tests/test_config.py`, 2 in `tests/test_repository_configuration.py`,
  and 6 in `tests/test_speech.py` (18 total).
- Development tools in `requirements-dev.txt`: `build`, `pytest`, `ruff`,
  `mypy`, `bandit`, and `pip-audit`.
- CI workflow: PortAudio header installation, lint, format check, pytest, mypy,
  and a no-deps wheel build on Python 3.12 (`ubuntu-latest`).
- Security workflow: `pip-audit` of development requirements, Bandit on tracked
  production Python, and CodeQL for Python.
- Dependabot weekly updates for pip and GitHub Actions.
- `.gitignore` coverage for environments, build output, `.env` files, `*.pem`,
  and `*.key`.

The commit before the package, `1d2a273`, adds CI, security automation,
`.gitignore`, the first README, tool configuration, and
`tests/test_repository_configuration.py`.

On 2026-10-22, `pytest` collected 18 tests from this tree and all 18 passed
under Python 3.12.10 in the project virtual environment. See [Testing](TESTING.md).

## In progress

None. Phase 3 is merged into `main` at commit `b589041`. No other pull requests
or feature branches are currently open against `main`.

## Planned

The following items are named in the README or architecture documents. None of
them has a design, interface, or acceptance criterion in this repository.

- Verification of end-to-end transcript output from a live microphone session
  against Deepgram Flux (unit tests and event wiring are verified; live end-to-end
  audio flow has not been verified in CI).
- Verified text-to-speech. No provider is named in the merged tree.
- Later integration with `openagent-wakeword`. Microphone ownership must be
  designed before wake-word coordination.
- An openagent coordinator. Named but not defined in the merged tree.
- AI-generated responses during a conversation.
- UFO², or another desktop-automation integration, as a future part of the
  wider assistant. This repository does not own that integration.

## Unknown

- A phase number or acceptance criterion for the CI foundation in `1d2a273`.
- Any phase number after Phase 3.
- The speech-output provider and library.
- The conversation model and how `OPENAGENT_PROVIDER` relates to `DEEPGRAM_API_KEY`.
- The wake-word handoff: event payload, process model, and microphone owner.
- The openagent coordinator interface.
- Whether UFO² will be called from this repository.
- The Windows audio host API for future capture paths.
- The deployment model: foreground command, background process, or service.
- Whether CI should include a Windows runner. Current workflows use
  `ubuntu-latest`.
- Whether a `LICENSE` file should accompany the MIT metadata. No license file
  is in the tree, and the GitHub license field was empty at inspection.
- Whether the `build` requirement should be invoked. It is declared.
  [Testing](TESTING.md) records that CI and the documented wheel command use
  `python -m pip wheel`.
- Whether workflow comments should be updated. They still name
  `actions/checkout` 4.2.2 and `actions/setup-python` 5.6.0. Dependabot pull
  requests #6 and #7 identify the pinned commits as checkout `7.0.1`
  (`3d3c42e5aac5ba805825da76410c181273ba90b1`) and setup-python `7.0.0`
  (`5fda3b95a4ea91299a34e894583c3862153e4b97`).
- Direct test coverage for `__main__.main()`, `JsonFormatter`, and `configure_logging`.
- Python 3.13 compatibility given `audioop` deprecation in `pipecat.audio.utils`.

## Related documents

- [README](../README.md)
- [Architecture](ARCHITECTURE.md)
- [Setup](SETUP.md)
- [Security](SECURITY.md)
- [Testing](TESTING.md)
- [Decisions](DECISIONS.md)
- [Jarvis vision](JARVIS_VISION.md)
- [Integration map](INTEGRATION_MAP.md)
- [Roadmap](ROADMAP.md)
- [Agent handoff](AGENT_HANDOFF.md)
- [Agent guide](../AGENTS.md)
