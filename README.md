# OpenAgent Realtime Conversation

This repository is the future real-time voice-conversation component of OpenAgent. It is
currently a development foundation only: no voice pipeline, wake-word integration, audio
device integration, API client, or text-to-speech provider has been implemented yet.

The intended direction is Python, Pipecat, verified speech recognition and text-to-speech
providers, and later integration with `openagent-wakeword` and the OpenAgent coordinator.
Those dependencies are intentionally not declared until their compatibility and integration
requirements are established.

## Development checks

The baseline is Python 3.12, matching the locally verified interpreter and CI runtime.

```powershell
python -m pip install -r requirements-dev.txt
ruff check .
ruff format --check .
pytest
mypy
bandit -ll tests
pip-audit -r requirements-dev.txt
```

`pip-audit` checks the declared development dependencies. Bandit scans tracked production
Python files in GitHub Actions when they exist; there are none yet. CodeQL is included for
future Python source and may require GitHub code scanning to be available for this repository.

## Automation

CI runs on pushes to `main`, pull requests targeting `main`, and manual dispatch. Security
scans run on the same events plus a weekly schedule. Workflow permissions are read-only except
for the CodeQL job's required `security-events: write` permission. Third-party action commits
are pinned and maintained by Dependabot; CodeQL follows GitHub's recommended `v4` major tag so
analysis engine updates remain available.
