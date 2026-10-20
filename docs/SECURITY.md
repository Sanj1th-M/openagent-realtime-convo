# Security

Security behavior of the merged tree at commit `47ecc5a`. Scan workflows are
defined in `.github/workflows/security.yml` and `.github/dependabot.yml`.

## Credentials in the merged program

The only credential the merged program reads is `OPENAGENT_PROVIDER_API_KEY`,
from the process environment.

| Control | Behavior |
| --- | --- |
| Storage in the object | `ProviderSettings.api_key` is a normal attribute |
| `repr` | `field(repr=False)` omits the key |
| Structured logs | `JsonFormatter` can emit `event`, `level`, `logger`, and `provider` |
| Error text | `ConfigurationError` messages name the variable or field |

The formatter includes `provider` only when that log attribute is set.
`log_configuration_loaded` sets it to the provider name. The failure event
does not set it. Application logs do not pass the API key into the formatter.

The key remains available on the `ProviderSettings` instance and in the
process environment. Hiding `repr` does not encrypt it or remove it from
memory.

There is no keyring integration and no Windows Credential Manager integration
in this tree.

## Files that must stay untracked

`.gitignore` excludes:

- `.env` and `.env.*`, with an exception for a future `.env.example`
- `*.pem` and `*.key`
- virtual environments and build outputs (`.venv/`, `venv/`, `build/`,
  `dist/`, `*.egg-info`)

`tests/test_repository_configuration.py` asserts that `.env`, `*.pem`, and
`*.key` are present as ignore lines. No `.env.example` is committed. Do not
add real credentials to examples, tests, or history.

## Automated scans

The security workflow runs on pushes to `main`, pull requests targeting
`main`, a weekly schedule (`23 4 * * 1`), and manual dispatch.

Default workflow permissions are `contents: read`. The CodeQL job adds
`security-events: write`.

| Check | Command or action | Scope on this branch |
| --- | --- | --- |
| Dependency audit | `pip-audit -r requirements-dev.txt` | Declared development requirements |
| Bandit | `bandit -ll` on `git ls-files '*.py' ':!tests/**'` | Medium severity and higher, tracked production Python |
| CodeQL | `github/codeql-action/init@v4` and `analyze@v4`, language `python`, `build-mode: none` | Python sources CodeQL can analyze without a build |

Local development documents `bandit -ll -r src`. With the current layout that
is the same production tree CI scans. CI's file list is the tracked production
Python files, not a recursive `src` argument.

`pip-audit` does not receive a lockfile. The merged runtime dependency list is
empty, so this audit does not represent a future voice-pipeline dependency
set. `requirements-dev.txt` is the file Dependabot's pip ecosystem reads from
the repository root on a weekly schedule. GitHub Actions updates are weekly
as well.

Third-party action commits are pinned. Dependabot maintains those pins.
CodeQL stays on the `v4` major tag so GitHub can update the analysis engine.
The workflow comments still name older action releases. The pinned commits
and that comment drift are recorded in [Project status](PROJECT_STATUS.md).
This document does not change the workflows.

The merged README notes that CodeQL may require GitHub code scanning to be
available for the repository. This inspection did not confirm that scans have
run.

## Phase 3 proposal

The unmerged Phase 3 branch describes a separate `DEEPGRAM_API_KEY` and says
microphone audio would be sent to Deepgram's cloud service. That behavior is
not in the merged program. Transcript output on that branch is unverified.
Details and the verification limit are in [Project status](PROJECT_STATUS.md).

## Related documents

- [README](../README.md)
- [Architecture](ARCHITECTURE.md)
- [Project status](PROJECT_STATUS.md)
- [Setup](SETUP.md)
- [Testing](TESTING.md)
- [Decisions](DECISIONS.md)
- [Agent guide](../AGENTS.md)
