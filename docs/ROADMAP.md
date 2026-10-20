# Roadmap

This is a status-based roadmap, not a schedule or a set of invented
milestones. The authoritative detailed record is [Project
status](PROJECT_STATUS.md); this page provides a short navigation view.

## Implemented

- Phase 2 configuration foundation: typed environment-backed settings, safe
  structured logging, and `openagent-realtime-config`.
- Package, tests, CI, security automation, and dependency-update configuration
  present on the merged branch.

## In progress

- Phase 3 speech input is open pull request #10 on
  `feat/phase3-speech-input`; it is unmerged. Its proposal includes Pipecat,
  Deepgram Flux, a `DEEPGRAM_API_KEY`, and `openagent-realtime-stt`.
- The pull request reports speech-activity detection, but successful transcript
  output remains unverified. It must not be described as working on the merged
  package.

## Planned

- A compatible real-time voice pipeline.
- Verified speech-to-text and text-to-speech.
- Later coordination with `openagent-wakeword`.
- AI-generated conversation responses and an OpenAgent coordinator.
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
