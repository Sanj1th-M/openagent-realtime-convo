# Project status

Status of `openagent-realtime-convo` as inspected on 2026-10-19.

The documented tree is branch `docs/project-documentation` at commit
`47ecc5a`, the same commit as `main`. Package version `0.1.0`. Runtime
dependencies: none.

Categories below are exhaustive for this inspection. A capability listed in one
category is not implied in another.

## Implemented

Merged Phase 2, from pull request #8 and the housekeeping in pull request #9.

- An installable src-layout package, `openagent-realtime-convo`, built with
  setuptools.
- Typed configuration: `AudioSettings`, `ProviderSettings`, `AppConfig`, and
  `ConfigurationError`.
- Environment variables `OPENAGENT_PROVIDER`, `OPENAGENT_PROVIDER_API_KEY`,
  `OPENAGENT_AUDIO_SAMPLE_RATE_HZ`, `OPENAGENT_AUDIO_CHANNELS`, and
  `OPENAGENT_AUDIO_CHUNK_SIZE`.
- Validation of required provider settings and positive integer audio settings.
- API-key exclusion from `repr` and from the JSON log schema.
- Console script `openagent-realtime-config`.
- Unit tests for configuration and for two repository-policy checks.
- Development tools in `requirements-dev.txt`: `build`, `pytest`, `ruff`,
  `mypy`, `bandit`, and `pip-audit`.
- CI workflow: lint, format check, pytest, mypy, and a no-deps wheel build on
  Python 3.12.
- Security workflow: `pip-audit` of development requirements, Bandit on tracked
  production Python, and CodeQL for Python.
- Dependabot weekly updates for pip and GitHub Actions.
- `.gitignore` coverage for environments, build output, `.env` files, `*.pem`,
  and `*.key`.

The commit before the package, `1d2a273`, adds CI, security automation,
`.gitignore`, the first README, tool configuration, and
`tests/test_repository_configuration.py`. That commit has no phase number in
the repository record.

On 2026-10-19, `pytest` collected 12 tests from this tree and all 12 passed
under Python 3.12.3. See [Testing](TESTING.md).

## In progress

Phase 3 is open
[pull request #10](https://github.com/Sanj1th-M/openagent-realtime-convo/pull/10),
branch `feat/phase3-speech-input` at `9e328575` when inspected. It is not
merged. It is not the tree documented as implemented above.

The pull request states this scope:

- Speech input and Deepgram Flux speech-to-text.
- Environment-based Deepgram API key configuration.
- Console script `openagent-realtime-stt`.
- Speech-related tests and documentation updates.

The pull request's testing note says automated tests and static checks were
run during development, manual microphone testing showed speech activity
detection, and successful transcript output still needs verification. This
documentation pass did not check out that branch, did not install it, and did
not confirm transcript output.

The unmerged `pyproject.toml` on that branch, as read remotely on 2026-10-19,
declares:

```text
dependencies = ["pipecat-ai[deepgram,local]>=1.12.0,<2"]
openagent-realtime-stt = "openagent_realtime_convo.speech:main"
```

That branch's README describes a local microphone command, Pipecat transport,
Deepgram Flux, the variable `DEEPGRAM_API_KEY`, interim and final transcript
lines, and transmission of microphone audio to Deepgram. Those statements
belong to the proposal. They are not verified behavior of the merged package,
and this pass did not review `speech.py`.

The pull request says wake-word integration, AI responses, text-to-speech, and
UFO² are outside Phase 3.

## Planned

The following items are named in the merged README or in the Phase 3 pull
request. None of them has a design, interface, or acceptance criterion in this
repository.

- Pipecat as the intended real-time pipeline, once compatibility is settled.
  The merged dependency list does not include it. The Phase 3 branch proposes
  a Pipecat extra for speech input only.
- Verified speech-to-text beyond the unverified Phase 3 proposal.
- Verified text-to-speech. No provider is named in the merged tree.
- Later integration with `openagent-wakeword`. The Phase 3 branch README says
  microphone ownership has to be designed before wake-word coordination, and
  that a wake-word process using the microphone would be stopped before the
  proposed speech command runs.
- An OpenAgent coordinator. The merged README names it and does not define it.
- AI-generated responses during a conversation.
- UFO², or another desktop-automation integration, as a future part of the
  wider assistant. Pull request #10 leaves it out of Phase 3. This repository
  does not own that integration.

## Unknown

- A phase number or acceptance criterion for the CI foundation in `1d2a273`.
- Any phase number after Phase 3.
- The speech-output provider and library.
- The conversation model and how `OPENAGENT_PROVIDER` relates to a future
  Deepgram credential. Phase 3 proposes a separate `DEEPGRAM_API_KEY` on its
  own branch.
- The wake-word handoff: event payload, process model, and microphone owner.
- The OpenAgent coordinator interface.
- Whether UFO² will be called from this repository.
- The Windows audio host API for a future capture path.
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
- Whether GitHub code scanning is enabled for this repository. The README
  states that CodeQL may require it. This inspection did not query scan
  results.
- End-to-end behavior of Phase 3, including whether transcripts are produced.

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
