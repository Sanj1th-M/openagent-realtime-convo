# Security

Security behavior of the merged tree at commit `b589041`. Scan workflows are
defined in `.github/workflows/security.yml` and `.github/dependabot.yml`.

## Credentials in the merged program

The merged program reads two credentials from the process environment:
1. `OPENAGENT_PROVIDER_API_KEY`: used by `openagent-realtime-config` (and `AppConfig.from_environment`).
2. `DEEPGRAM_API_KEY`: used by `openagent-realtime-stt` (via `AppConfig.from_deepgram_environment()`).

| Control | Behavior |
| --- | --- |
| Storage in `ProviderSettings` | `ProviderSettings.api_key` uses `field(repr=False)` to omit the key |
| Storage in `SpeechConfig` | `SpeechConfig.__repr__` explicitly prints `api_key=<redacted>` |
| Structured logs | `JsonFormatter` emits only `event`, `level`, `logger`, and `provider` |
| Error text | `ConfigurationError` and `SpeechConfigurationError` name the variable |
| Transcripts | `TranscriptPrinter` prints to stdout; transcripts are not written to logger |

The formatter includes `provider` only when that log attribute is set.
`log_configuration_loaded` sets it to the provider name. The failure event
does not set it. Application logs do not pass the API key into the formatter.

The keys remain available in object instances and in the process environment.
Hiding `repr` does not encrypt them or remove them from memory.

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

`pip-audit` checks `requirements-dev.txt` and does not receive a lockfile.
Runtime dependencies are declared in `pyproject.toml` (`pipecat-ai[deepgram,local]`).
`requirements-dev.txt` is the file Dependabot's pip ecosystem reads from
the repository root on a weekly schedule. GitHub Actions updates are weekly
as well.

Third-party action commits are pinned. Dependabot maintains those pins.
CodeQL stays on the `v4` major tag so GitHub can update the analysis engine.
The workflow comments still name older action releases (`actions/checkout` v4.2.2
and `actions/setup-python` v5.6.0), while the pinned commits correspond to
checkout `7.0.1` and setup-python `7.0.0`.

The README notes that CodeQL may require GitHub code scanning to be
available for the repository.

## Cloud speech recognition and microphone privacy

The `openagent-realtime-stt` command transmits captured microphone audio to
Deepgram's cloud service for speech recognition. Users must be aware of audio
transmission to a third-party cloud service. The `DEEPGRAM_API_KEY` credential
is read from the process environment, validated before opening the microphone,
and kept private in memory. Transcript text is displayed to stdout and is
not forwarded to log sinks.

## Related documents

- [README](../README.md)
- [Architecture](ARCHITECTURE.md)
- [Project status](PROJECT_STATUS.md)
- [Setup](SETUP.md)
- [Testing](TESTING.md)
- [Decisions](DECISIONS.md)
- [Agent guide](../AGENTS.md)
