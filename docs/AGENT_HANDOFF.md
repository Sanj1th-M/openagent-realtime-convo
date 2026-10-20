# Agent handoff

Use this page to orient the next coding agent without treating a stale handoff
as source of truth. Read [Project status](PROJECT_STATUS.md), the working
tree, source, tests, and `pyproject.toml` before changing behavior.

## Current documentation state

- Merged branch state: Phase 2 configuration foundation at `47ecc5a`.
- In-progress proposal: Phase 3 pull request #10 is unmerged; transcript
  output is not verified.
- This documentation pass adds the Jarvis vision, planned integration map,
  status-based roadmap, and this handoff page. It does not change application
  code, dependencies, tests, or workflows.

## Handoff template

Copy and complete this section for a later task:

```text
Task:
Scope and boundaries:
Working-tree changes already present:
Completed work:
Evidence / validation run:
Next smallest task:
Unresolved questions or blockers:
Files intentionally not changed:
```

Record only checks actually run and behavior verified from source, tests, or
execution. Do not include secrets, credentials, or copied environment values.
Do not call an unmerged proposal implemented.

## Starting points

- [README](../README.md) for the short project overview.
- [Architecture](ARCHITECTURE.md) for the merged package behavior.
- [Project status](PROJECT_STATUS.md) for implemented, in-progress, planned,
  and unknown work.
- [Integration map](INTEGRATION_MAP.md) and [Jarvis vision](JARVIS_VISION.md)
  for future intent and boundaries.
- [Testing](TESTING.md) and [Security](SECURITY.md) for the declared checks
  and their limits.
- [Agent guide](../AGENTS.md) for repository rules.
