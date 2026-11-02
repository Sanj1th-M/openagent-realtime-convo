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

## Current branch test inventory

The current Phase 4 branch collects **260 tests** across brain, provider, config,
repository, speech, and wake-word coordinator suites. Running tests requires
the project virtual environment (`.venv`) where the package dependencies
(`pipecat-ai[deepgram,local]`) are installed. Always prefix check commands
with `.\.venv\Scripts\` on Windows (or `.venv/bin/` on POSIX):

```powershell
.\.venv\Scripts\ruff.exe check src tests
.\.venv\Scripts\ruff.exe format --check src tests
.\.venv\Scripts\mypy.exe src
.\.venv\Scripts\pytest.exe
.\.venv\Scripts\bandit.exe -r src
.\.venv\Scripts\pip-audit.exe -r requirements-dev.txt
.\.venv\Scripts\python.exe -m build
```

Running any of these from the **global Python interpreter** (without activating
`.venv`) will fail because `pipecat-ai` and other runtime dependencies are only
installed in the virtual environment. The CI workflow activates the environment
via `pip install -r requirements-dev.txt` and `pip install -e .` into a clean
Ubuntu runner, so the tools are on PATH and no prefix is needed there.

`openagent-wakeword` is a private local package not declared in `pyproject.toml`.
It is **not** installed in `.venv` for local development. The coordinator module
guards its import, so all 260 tests run without it.

`tests/test_brain.py`, `tests/test_openrouter.py`, `tests/test_gemini.py`,
`tests/test_openai.py`, `tests/test_anthropic.py`, and `tests/test_ollama.py` cover the
provider-independent data models plus mocked HTTP success, error, and
malformed-response handling for the OpenRouter, Google Gemini, OpenAI,
Anthropic Claude, and Ollama adapters. No provider test needs a real API key or
network request.

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

`tests/test_speech.py`:

| Test | What it checks |
| --- | --- |
| `test_speech_configuration_requires_documented_deepgram_key` | Missing `DEEPGRAM_API_KEY` raises `SpeechConfigurationError` |
| `test_speech_configuration_uses_existing_audio_environment_settings` | Reads audio env vars; API key omitted from `SpeechConfig` repr |
| `test_transcript_printer_distinguishes_interim_and_final_results` | `[INTERIM]` and `[FINAL]` formatting in `TranscriptPrinter` |
| `test_flux_update_event_prints_an_interim_transcript` | `on_update` event handler emits `[INTERIM]` transcript |
| `test_speech_config_keeps_key_private` | `SpeechConfig` repr redacts `api_key` |
| `test_microphone_startup_failure_is_safe_and_actionable` | Microphone failure wraps into `SpeechRuntimeError` with user message |


`tests/test_wakeword.py`:

| Test | What it checks |
| --- | --- |
| `test_coordinator_calls_start_and_stop_on_detector` | `detector.start()` called on startup, `stop()` in `finally` |
| `test_coordinator_pauses_detector_before_stt` | `detector.pause()` called before STT opens the mic |
| `test_coordinator_resumes_detector_after_stt_completes` | `detector.resume()` called after STT completes |
| `test_coordinator_resumes_after_stt_timeout` | STT timeout resumes detector and does not crash |
| `test_coordinator_resumes_after_stt_runtime_error` | `SpeechRuntimeError` during STT resumes detector |
| `test_coordinator_stops_detector_on_cancel` | Task cancellation calls `detector.stop()` |
| `test_coordinator_prints_acknowledgement_before_stt` | Acknowledgement text printed before STT capture starts |
| `test_wake_callback_uses_call_soon_threadsafe` | Thread-safe loop signalling from audio thread |
| `test_wake_callback_ignores_duplicate_during_active` | Duplicate detection while active is ignored |
| `test_wake_callback_is_noop_before_run` | Callback is safe if fired before run loop begins |
| `test_coordinator_config_reads_required_environment` | Parses `DEEPGRAM_API_KEY` and `OPENAGENT_WAKEWORD_MODEL_DIR` |
| `test_coordinator_config_reads_optional_overrides` | Reads threshold, cooldown, and STT timeout overrides |
| `test_coordinator_config_requires_deepgram_key` | Missing Deepgram key raises `WakeWordCoordinatorError` |
| `test_coordinator_config_requires_model_dir` | Missing model dir raises `WakeWordCoordinatorError` |
| `test_coordinator_config_rejects_invalid_threshold` | Non-positive threshold rejected |
| `test_coordinator_config_rejects_invalid_stt_timeout` | Non-positive STT timeout rejected |
| `test_coordinator_config_rejects_non_numeric_cooldown` | Non-numeric cooldown rejected |
| `test_coordinator_config_allows_zero_cooldown` | Zero cooldown permitted |
| `test_coordinator_raises_on_detector_start_failure` | Startup error converted to actionable user message |
| `test_coordinator_stop_called_even_when_start_fails` | `detector.stop()` guaranteed even on start failure |
| `test_standby_without_initialization_raises_error` | Calling `_standby()` without `run()` raises coordinator error |

On 2026-11-02, all 260 tests passed in the project virtual environment
(`.venv`, pipecat-ai 1.15.0, Pillow 13.0.0) on Python 3.12.10.

## Coverage gaps in the merged suite

The tests above do not exercise:

- `__main__.main` or its process exit codes
- `JsonFormatter` or `configure_logging`
- `speech.main` or its process exit codes
- blank provider names, blank API keys, or whitespace-only required values
- negative integers supplied through environment variables
- live microphone capture or actual network communication with Deepgram Flux

## Verification status of speech pipeline

Automated unit tests cover event wiring, transcript formatting, error handling,
and configuration parsing. Live microphone capture and end-to-end transcription
against Deepgram Flux are not verifiable in headless CI. Verifying end-to-end
recognition requires a manual run on a machine with a working microphone and
an active Deepgram API key.

## Related documents

- [README](../README.md)
- [Architecture](ARCHITECTURE.md)
- [Project status](PROJECT_STATUS.md)
- [Setup](SETUP.md)
- [Security](SECURITY.md)
- [Agent guide](../AGENTS.md)
