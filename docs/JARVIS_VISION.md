# Jarvis vision

OpenAgent is intended to become a personal Windows assistant with a
voice-oriented experience. "Jarvis" is the product goal, not the name of a
currently implemented end-to-end feature.

The intended assistant experience includes detecting a wake phrase, holding a
real-time conversation, producing responses, speaking them, and eventually
supporting desktop automation. The merged code in this repository does none of
those end-to-end tasks: it validates configuration and writes safe status
logs. The distinction matters because the product direction must not be read
as a promise about the current package.

## Current boundary

This repository owns the future real-time conversation component. Wake-word
detection belongs to the separate `openagent-wakeword` repository. UFO² is a
future desktop-automation direction, outside this repository until an
integration is defined. No merged source establishes an end-to-end assistant,
a coordinator, or a contract between these components.

The implemented package and the status of the unmerged Phase 3 proposal are
recorded in [Project status](PROJECT_STATUS.md). The component relationships
are deliberately limited to the planned connections shown in the
[Integration map](INTEGRATION_MAP.md).

## What remains to be decided

The repository does not record a wake-word handoff, microphone-ownership
model, conversation-model selection, speech-output provider, coordinator
interface, or UFO² invocation contract. These are undecided design questions,
not implied implementation work. See [Roadmap](ROADMAP.md) for the status
categories used across the project.

## Related documents

- [README](../README.md)
- [Project status](PROJECT_STATUS.md)
- [Integration map](INTEGRATION_MAP.md)
- [Roadmap](ROADMAP.md)
- [Decisions](DECISIONS.md)
