# Agent handoff

Use this page to orient the next coding agent without treating a stale handoff
as source of truth. Read [Project status](PROJECT_STATUS.md), the working
tree, source, tests, and `pyproject.toml` before changing behavior.

## Phase 4 handoff (2026-10-31)

```text
Task: Wake-word integration — WakeWordCoordinator bridging openagent-wakeword with the Phase 3 STT pipeline.
Scope and boundaries: openagent-realtime-convo only; openagent-wakeword is imported optionally.
Working-tree changes already present:
  src/openagent_realtime_convo/wakeword.py (new)
  tests/test_wakeword.py (new)
  pyproject.toml (added openagent-jarvis console script)
  docs/ARCHITECTURE.md, ROADMAP.md, PROJECT_STATUS.md, DECISIONS.md, INTEGRATION_MAP.md, TESTING.md (updated)
  docs/AGENT_HANDOFF.md (this file)
Completed work:
  WakeWordCoordinator with pause/resume mic handoff; 21 new unit tests (39 tests total).
  Bandit B101 resolved with explicit runtime guard.
  certifi and Pillow upgraded to patched versions, pip-audit clean.
Evidence / validation run:
  ruff check: pass (0 issues)
  ruff format --check: pass (22 files formatted)
  pytest: 39 passed, 0 failed
  mypy: 0 issues (10 source files)
  bandit -r src: no issues (0 issues across all severities)
  pip-audit: pass (0 vulnerabilities)
  pip wheel --no-deps: exit 0
Next smallest task: Live end-to-end manual test with a real microphone and Deepgram key.
Unresolved questions or blockers:
  - Windows Scheduled Task (openagent-wakeword-listener) must be stopped before running openagent-jarvis.
  - openagent-wakeword must be installed in this repo's venv for openagent-jarvis to function.
  - Speech output (TTS for the acknowledgement) is not implemented.
Files intentionally not changed: speech.py, config.py, logging.py, __init__.py, __main__.py
```

## Current documentation state

- Merged branch state: Phase 2 configuration foundation and Phase 3 speech-input
  pipeline merged at commit `b589041`.
- Phase 3 is merged: includes Pipecat local audio transport, Deepgram Flux STT,
  `openagent-realtime-stt`, and 18 passing unit tests. Live microphone end-to-end
  transcription output has not been verified in CI.
- No in-progress pull requests are currently open.

## Handoff template

Copy and complete this section for a later task:

```text
Task:
Scope and boundaries:
Working-tree changes already present:
Completed work:
Evidence / validation run:
Next smallest task:
Unresolved questions or blockers:
Files intentionally not changed:
```

Record only checks actually run and behavior verified from source, tests, or
execution. Do not include secrets, credentials, or copied environment values.
Do not call an unmerged proposal implemented.

## Starting points

- [README](../README.md) for the short project overview.
- [Architecture](ARCHITECTURE.md) for the merged package behavior.
- [Project status](PROJECT_STATUS.md) for implemented, in-progress, planned,
  and unknown work.
- [Integration map](INTEGRATION_MAP.md) and [Jarvis vision](JARVIS_VISION.md)
  for future intent and boundaries.
- [Testing](TESTING.md) and [Security](SECURITY.md) for the declared checks
  and their limits.
- [Agent guide](../AGENTS.md) for repository rules.
