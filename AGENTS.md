# Agent guide

Rules for coding agents working in `openagent-realtime-convo`. Read
[Project status](docs/PROJECT_STATUS.md) before changing code or docs. When the
status document and the GitHub repository description disagree, trust the
merged source, `pyproject.toml`, and tests.

## Repository boundaries

openagent is a personal Windows assistant split across separate projects.

| Project | Responsibility |
| --- | --- |
| `openagent-wakeword` | Idle detection of the wake phrase "Hey Jarvis" |
| `openagent-realtime-convo` (this repository) | Real-time voice conversation |
| UFO² integration | Future desktop automation |

Keep wake-word detection in its own repository. Keep UFO² work out of this
repository until the maintainer defines an integration. Duplicate neither
component here.

The merged conversation code is a configuration foundation. Microphone capture,
speech recognition, model replies, and speech output are later work.

## Status categories

Use these categories in documentation and in change descriptions.

| Category | Meaning in this repository |
| --- | --- |
| Implemented | Present on the merged branch this document describes |
| In progress | Proposed in an open pull request, still unmerged |
| Planned | Named as future work, with no design recorded here |
| Unknown | No recorded decision or contract |

Phase numbers that appear in the repository record:

- Phase 2 is the configuration foundation, merged at commit `96eb109` (pull request #8) and
  refined at `47ecc5a` (pull request #9).
- Phase 3 is the speech-input pipeline, merged at commit `b589041` (pull request #10).

Do not assign numbers to the earlier CI foundation or to later ideas. The Phase 3 merge
adds a Pipecat pipeline and Deepgram Flux speech-to-text, but end-to-end transcript output
from a live microphone session has not been verified in CI. Do not describe it as confirmed
working without evidence from a manual run.

## Working rules

- Verify a dependency in `pyproject.toml` or `requirements-dev.txt` before
  calling it an implemented feature. The runtime dependency is
  `pipecat-ai[deepgram,local]>=1.12.0,<2`, declared on the merged `main` branch.
- Protect secrets. Do not print `OPENAGENT_PROVIDER_API_KEY`, commit `.env`
  files, or add credentials to logs, tests, or docs.
- Keep changes modular and covered by tests when behavior changes.
- Leave application code, dependency files, and CI workflows unchanged during
  documentation-only tasks.
- Do not commit, push, merge, or switch branches unless the maintainer asks.
- Preserve user changes outside the requested edit.

## Checks

The baseline interpreter is Python 3.12. After installing the development
requirements and the editable package, the merged tree uses:

```powershell
ruff check .
ruff format --check .
pytest
mypy
python -m pip wheel --no-deps . --wheel-dir dist
bandit -ll -r src
pip-audit -r requirements-dev.txt
```

Details and the limits of each check are in [Testing](docs/TESTING.md) and
[Security](docs/SECURITY.md).

## Related documents

- [README](README.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Project status](docs/PROJECT_STATUS.md)
- [Setup](docs/SETUP.md)
- [Security](docs/SECURITY.md)
- [Testing](docs/TESTING.md)
- [Decisions](docs/DECISIONS.md)
- [Jarvis vision](docs/JARVIS_VISION.md)
- [Integration map](docs/INTEGRATION_MAP.md)
- [Roadmap](docs/ROADMAP.md)
- [Agent handoff](docs/AGENT_HANDOFF.md)
