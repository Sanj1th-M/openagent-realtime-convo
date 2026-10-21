# Roadmap

This is a status-based roadmap, not a schedule or a set of invented
milestones. The authoritative detailed record is [Project
status](PROJECT_STATUS.md); this page provides a short navigation view.

## Implemented

- Phase 2 configuration foundation: typed environment-backed settings, safe
  structured logging, and `openagent-realtime-config`.
- Phase 3 speech-input pipeline: Pipecat `LocalAudioTransport`, Deepgram Flux
  speech-to-text, `openagent-realtime-stt`, and 18 passing unit tests.
- Package, tests, CI, security automation, and dependency-update configuration
  present on the merged `main` branch.

## In progress

None. Phase 3 is merged into `main` at commit `b589041`.

## Planned

- End-to-end verification of live microphone capture and transcript output with Deepgram Flux.
- Verified text-to-speech pipeline.
- Later coordination with `openagent-wakeword`.
- AI-generated conversation responses and an openagent coordinator.
- Potential future UFO² desktop automation.

These are directions, not approved interfaces or delivery commitments. The
planned boundaries are illustrated in [Integration map](INTEGRATION_MAP.md).

## Undecided

- Wake-word handoff, microphone ownership, and process model.
- Conversation-model and speech-output provider choices.
- Coordinator and UFO² integration interfaces.
- Windows audio host API and deployment model.
- Any phase number after Phase 3.

See [Project status](PROJECT_STATUS.md) for the complete unknown list and
[Jarvis vision](JARVIS_VISION.md) for the product intent separated from the
merged implementation.

## Related documents

- [README](../README.md)
- [Project status](PROJECT_STATUS.md)
- [Jarvis vision](JARVIS_VISION.md)
- [Integration map](INTEGRATION_MAP.md)
- [Agent handoff](AGENT_HANDOFF.md)
