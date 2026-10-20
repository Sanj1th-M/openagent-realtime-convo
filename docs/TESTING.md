# Testing

Checks for the merged tree. Commands below match `.github/workflows/ci.yml`,
`.github/workflows/security.yml`, and the development section of the README.

## Install the tools

CI installs `requirements-dev.txt`, then installs the package editable, on
Python 3.12:

```powershell
python -m pip install -r requirements-dev.txt
python -m pip install -e .
```

Declared development dependencies:

| Package | Constraint in `requirements-dev.txt` |
| --- | --- |
| `build` | `>=1.2.2,<2.0` |
| `pytest` | `>=9.1.1,<10.0` |
| `ruff` | `>=0.17.0,<1.0` |
| `mypy` | `>=2.4.0,<3.0` |
| `bandit[toml]` | `>=1.9.4,<2.0` |
| `pip-audit` | `>=2.10.1,<3.0` |

## Local and CI commands

```powershell
ruff check .
ruff format --check .
pytest
mypy
python -m pip wheel --no-deps . --wheel-dir dist
bandit -ll -r src
pip-audit -r requirements-dev.txt
```

CI runs the first five of those after the install steps. `ruff` selects rules
`E`, `F`, `I`, and `B`, with a line length of 100 and target `py312`. `mypy`
is strict and checks `src` and `tests`. The wheel build uses
`python -m pip wheel --no-deps`. The `build` package is declared and is not
the command CI invokes.

Bandit and `pip-audit` run in the security workflow. CI's Bandit invocation
is `bandit -ll` on tracked production Python files. `-ll` reports medium
severity and higher. Security-scan limits are in [Security](SECURITY.md).

Pytest options in `pyproject.toml` are `-ra --strict-config --strict-markers`,
with `testpaths = ["tests"]`.

## Merged test inventory

Eight test functions collect 12 tests.

`tests/test_config.py`:

| Test | Cases | What it checks |
| --- | --- | --- |
| `test_environment_configuration_uses_audio_defaults` | 1 | Default `AudioSettings` and the provider name |
| `test_environment_configuration_accepts_valid_values` | 1 | Custom sample rate, channels, and chunk size |
| `test_audio_settings_reject_invalid_values` | 3 | `sample_rate_hz=0`, `channels=-1`, `chunk_size=True` |
| `test_environment_configuration_rejects_invalid_audio_value` | 1 | `OPENAGENT_AUDIO_CHANNELS=two` |
| `test_environment_configuration_requires_provider_settings` | 3 | Empty mapping, provider only, and API key only |
| `test_provider_settings_hides_api_key_in_representation` | 1 | The key string is absent from `repr` |

`tests/test_repository_configuration.py`:

| Test | What it checks |
| --- | --- |
| `test_pytest_configuration_is_strict_and_scoped_to_tests` | `testpaths` and strict pytest flags in `pyproject.toml` |
| `test_gitignore_excludes_local_credentials` | `.env`, `*.pem`, and `*.key` are ignore lines |

On 2026-10-19 these 12 tests passed in 0.35 seconds. The run used a temporary
virtual environment on Python 3.12.3 with `pytest` and an editable install of
this commit. That run did not execute Ruff, mypy, Bandit, `pip-audit`, or the
wheel build.

## Coverage gaps in the merged suite

The tests above do not exercise:

- `__main__.main` or the process exit codes
- `JsonFormatter` or `configure_logging`
- blank provider names, blank API keys, or whitespace-only required values
- negative integers supplied through environment variables
- a microphone, an audio device, a network call, or a provider SDK

Phase 2 has no speech tests because the merged package has no speech code.

## Phase 3 claims

Pull request #10 says its author ran automated tests and static checks on
that branch, and that manual microphone testing showed speech activity while
transcript output still needs verification. Those results were not reproduced
for this documentation. The merged suite remains the 12 tests listed above.

## Related documents

- [README](../README.md)
- [Architecture](ARCHITECTURE.md)
- [Project status](PROJECT_STATUS.md)
- [Setup](SETUP.md)
- [Security](SECURITY.md)
- [Agent guide](../AGENTS.md)
