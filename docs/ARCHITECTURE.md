# Architecture

This document describes the package extended through Phase 4. Phase 2 established the
configuration foundation; Phase 3 added the speech-input pipeline; Phase 4 adds the
wake-word coordinator. Later conversation capabilities are outside this architecture.
Their status is in [Project status](PROJECT_STATUS.md).

## Component boundaries

```mermaid
flowchart TB
  subgraph merged["Merged in openagent-realtime-convo"]
    env["Process environment"]
    config["AppConfig"]
    cli["openagent-realtime-config"]
    stt["speech.py (LocalAudioTransport -> DeepgramFluxSTTService -> TranscriptPrinter)"]
    sttCli["openagent-realtime-stt"]
    coord["wakeword.py (WakeWordCoordinator)"]
    jarvisCli["openagent-jarvis"]
    env --> config --> cli
    env --> config --> stt --> sttCli
    env --> config --> coord --> jarvisCli
  end

  subgraph separate["Separate repository"]
    wake["openagent-wakeword (WakeWordDetector)"]
  end

  wake -- "pause/resume handoff (imported optionally)" --> coord

  subgraph namedLater["Named later work, no design recorded here"]
    replies["AI responses"]
    speechOut["Speech output"]
    coordinator["openagent coordinator"]
    ufo["UFO² desktop automation"]
  end
```

`openagent-wakeword` is a separate repository for wake-word detection. The
`WakeWordCoordinator` in `wakeword.py` imports it optionally and coordinates the
microphone handoff: the detector is paused before STT and resumed after. UFO² is a future assistant
integration with no type, module, or protocol in this tree. The intended
boundaries and explicitly planned connections are in
[Integration map](INTEGRATION_MAP.md).

The public GitHub description names Pipecat, Deepgram Flux, and speech
synthesis. Pipecat and Deepgram Flux are integrated in the merged speech-input
pipeline. Speech synthesis and assistant responses remain future product direction.

## Package layout

The installable distribution is `openagent-realtime-convo` `0.1.0`. The import
package is `openagent_realtime_convo`, discovered from `src` by setuptools.
`requires-python` is `>=3.12`. Runtime `dependencies` declares
`pipecat-ai[deepgram,local]>=1.12.0,<2`. License metadata is the SPDX string `MIT`.

| Module | Responsibility |
| --- | --- |
| `config.py` | Validate environment-backed settings |
| `logging.py` | Emit a fixed set of JSON log fields |
| `__main__.py` | Configuration validation command |
| `speech.py` | Local microphone capture and Deepgram Flux speech-to-text pipeline |
| `__init__.py` | Export `AppConfig`, `AudioSettings`, `ProviderSettings`, and `ConfigurationError` |

The console scripts on this branch are:

```text
openagent-realtime-config = openagent_realtime_convo.__main__:main
openagent-realtime-stt = openagent_realtime_convo.speech:main
```

## Configuration flow

`AppConfig.from_environment` reads a mapping. When the caller omits that
mapping, it reads `os.environ`. There is no `.env` loader and no provider SDK.

```text
OPENAGENT_PROVIDER
OPENAGENT_PROVIDER_API_KEY
OPENAGENT_AUDIO_SAMPLE_RATE_HZ
OPENAGENT_AUDIO_CHANNELS
OPENAGENT_AUDIO_CHUNK_SIZE
        |
        v
AppConfig.from_environment()
        |
        +-- AudioSettings
        +-- ProviderSettings
        |
        v
openagent-realtime-config
        |
        +-- success: JSON event configuration_loaded, exit 0
        +-- ConfigurationError: JSON event configuration_invalid,
            plain-text error on stderr, exit 2
```

### Audio settings

`AudioSettings` is a frozen slotted dataclass. Defaults are `16000` Hz, `1`
channel, and `320` samples per chunk. Each field must be an `int` greater than
zero. `bool` is rejected because it is a subclass of `int`.

The class stores capture parameters only. It does not open a device, choose a
host API, or document a frame duration. At the default rate, `320` samples span
20 ms. That duration is arithmetic from the defaults. The source does not
record it as a design rule.

Environment parsing uses the same defaults when a variable is absent. A present
value must parse as a positive integer. The environment path does not accept
boolean text.

### Provider settings

`ProviderSettings` stores a generic `name` and an `api_key`. Both must contain
non-whitespace characters. The stored strings are the raw environment values.
The key uses `field(repr=False)`, so `repr` omits it.

`AppConfig.from_environment()` reads the generic `OPENAGENT_PROVIDER` and
`OPENAGENT_PROVIDER_API_KEY` variables. `AppConfig.from_deepgram_environment()`
reads `DEEPGRAM_API_KEY` directly and sets the provider name to `"deepgram"`.

`ConfigurationError` subclasses `ValueError`.

## Speech-to-text pipeline

`openagent_realtime_convo.speech` implements a real-time speech input pipeline
using Pipecat and Deepgram Flux:

- `SpeechConfig`: Slotted frozen dataclass storing `api_key` and `AudioSettings`,
  with a custom `__repr__` that redacts `api_key`.
- `speech_config_from_environment()`: Reads `DEEPGRAM_API_KEY` and audio settings,
  raising `SpeechConfigurationError` on validation failure.
- `create_local_transport()`: Builds Pipecat's `LocalAudioTransport` for microphone
  input with `LocalAudioTransportParams`. Device acquisition errors raise
  `SpeechRuntimeError` with user guidance.
- `DeepgramFluxSTTService`: Connects to Deepgram Flux speech-to-text service.
  `register_flux_transcript_handler()` registers an `on_update` handler to emit
  `[INTERIM]` results.
- `TranscriptPrinter`: A `FrameProcessor` that pushes frames down the pipeline and
  prints `[INTERIM]` or `[FINAL]` transcript text to the given output stream without
  logging transcript contents to system logs.
- `openagent-realtime-stt`: Console entry point executing the async pipeline.
  Exit code `0` on success or `KeyboardInterrupt`, `1` on `SpeechRuntimeError`,
  and `2` on `SpeechConfigurationError`.

End-to-end transcript output from a live microphone session requires a manual run
with a valid Deepgram account and local microphone access.

## Logging

`configure_logging` attaches one `StreamHandler` to the logger
`openagent_realtime_convo` when the logger has no handlers. Propagation is
disabled. The handler uses `JsonFormatter`, which writes compact JSON with
`sort_keys=True`.

The formatter emits only:

| Field | Source |
| --- | --- |
| `event` | `record.event` when present, otherwise the log message |
| `level` | `record.levelname` |
| `logger` | `record.name` |
| `provider` | `record.provider`, included only when it is not `None` |

`log_configuration_loaded` records `configuration_loaded` and the provider
name. A failed load records `configuration_invalid` and does not attach the
provider or the exception text. The command also prints
`Configuration error: ...` to stderr. Those configuration messages name the
invalid field or variable. They do not include the API key.

`StreamHandler()` writes to stderr.

A successful run for provider `example` produces this record:

```json
{"event": "configuration_loaded", "level": "INFO", "logger": "openagent_realtime_convo", "provider": "example"}
```

## What this architecture includes

The merged behavior includes:
1. Configuration validation and safe structured logging (`openagent-realtime-config`).
2. Local microphone capture and Deepgram Flux speech-to-text pipeline (`openagent-realtime-stt`).

Quality gates around that package are documented in [Testing](TESTING.md) and
[Security](SECURITY.md).

## Related documents

- [README](../README.md)
- [Project status](PROJECT_STATUS.md)
- [Setup](SETUP.md)
- [Security](SECURITY.md)
- [Decisions](DECISIONS.md)
- [Integration map](INTEGRATION_MAP.md)
- [Roadmap](ROADMAP.md)
- [Agent guide](../AGENTS.md)
