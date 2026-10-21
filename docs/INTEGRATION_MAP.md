# Integration map

This map describes repository boundaries and intended relationships. Arrows
marked **planned** are not implemented interfaces or verified runtime flows.

```text
openagent-wakeword                 openagent-realtime-convo
  wake-word detection       -- planned handoff -->  real-time conversation
                                                          |
                                                          | planned coordinator
                                                          v
                                                   assistant responses
                                                          |
                                                          | planned integration
                                                          v
                                                    future UFO² automation
```

## Components

| Component | Repository responsibility | State of the connection |
| --- | --- | --- |
| `openagent-wakeword` | Wake-word detection, kept outside this repository | Later integration is planned; no handoff event, payload, process model, or microphone ownership is recorded here. |
| `openagent-realtime-convo` | Future real-time voice conversation | Merged package provides configuration validation and speech-to-text input via Pipecat and Deepgram Flux. |
| UFO² integration | Future desktop automation for the wider assistant | Planned only; this repository contains no UFO² dependency, module, or invocation contract. |
| openagent coordinator | Named future assistant coordination role | Planned only; no interface or owner is defined in the merged tree. |

The diagram is a product-boundary view, not an architecture specification. It
does not establish ordering, data formats, API calls, or a guarantee that the
components will run in the same process.

## Evidence and limits

The merged package has no dependency on `openagent-wakeword` or UFO². It does
depend on Pipecat and connects to Deepgram for speech-to-text in `speech.py`.
It has no model-reply or speech-output code. Wake-word handoff and UFO² desktop
automation remain planned and are not implemented here. Its status and verification
limits are in [Project status](PROJECT_STATUS.md).

For the long-term intent, see [Jarvis vision](JARVIS_VISION.md). For the
implemented configuration architecture, see [Architecture](ARCHITECTURE.md).

## Related documents

- [README](../README.md)
- [Jarvis vision](JARVIS_VISION.md)
- [Project status](PROJECT_STATUS.md)
- [Roadmap](ROADMAP.md)
- [Decisions](DECISIONS.md)
