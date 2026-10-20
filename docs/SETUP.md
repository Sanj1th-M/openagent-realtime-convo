# Setup

Install and run the merged Phase 2 package. Phase 3's `openagent-realtime-stt`
command is not part of this branch. Its status is in
[Project status](PROJECT_STATUS.md).

## Prerequisites

- Python 3.12, the interpreter documented by the README and used in CI.
  `requires-python` is `>=3.12`.
- `pip` for that interpreter.

The configuration command does not open a microphone and does not call a
network service.

## Install

From the repository root, create a virtual environment. `.venv/` and `venv/`
are gitignored.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pip install -e .
```

The same `pip` commands are what CI runs on `ubuntu-latest` after
`actions/setup-python` selects Python 3.12. On a POSIX shell the virtual
environment activate script is `.venv/bin/activate`.

`python -m pip install -e .` installs the console script
`openagent-realtime-config`.

## Configure

The program reads the process environment. It does not load a `.env` file.
Putting values in `.env` has no effect unless something else exports them into
the environment first. `.env` and `.env.*` are gitignored. `!.env.example` is
allowed by `.gitignore`, and no `.env.example` is committed.

| Variable | Required | Default |
| --- | --- | --- |
| `OPENAGENT_PROVIDER` | yes | — |
| `OPENAGENT_PROVIDER_API_KEY` | yes | — |
| `OPENAGENT_AUDIO_SAMPLE_RATE_HZ` | no | `16000` |
| `OPENAGENT_AUDIO_CHANNELS` | no | `1` |
| `OPENAGENT_AUDIO_CHUNK_SIZE` | no | `320` |

Required values must contain a non-whitespace character. Optional audio values,
when set, must be positive integers.

PowerShell, matching the repository's local example:

```powershell
$env:OPENAGENT_PROVIDER = "example"
$env:OPENAGENT_PROVIDER_API_KEY = "your-local-secret"
openagent-realtime-config
```

POSIX equivalent for the same variables:

```sh
export OPENAGENT_PROVIDER=example
export OPENAGENT_PROVIDER_API_KEY=your-local-secret
openagent-realtime-config
```

Use a local secret only in the current process. Do not commit it, pass it as a
logged argument, or paste it into docs.

## Expected results

Success logs one JSON object to stderr and exits `0`. For provider `example`
the record is:

```json
{"event": "configuration_loaded", "level": "INFO", "logger": "openagent_realtime_convo", "provider": "example"}
```

Invalid configuration logs `configuration_invalid`, prints
`Configuration error: ...` to stderr, and exits `2`.

Field rules and the log schema are in [Architecture](ARCHITECTURE.md).
Credential handling is in [Security](SECURITY.md).

## Related documents

- [README](../README.md)
- [Architecture](ARCHITECTURE.md)
- [Project status](PROJECT_STATUS.md)
- [Security](SECURITY.md)
- [Testing](TESTING.md)
- [Agent guide](../AGENTS.md)
