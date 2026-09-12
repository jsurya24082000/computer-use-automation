# Computer-Use Automation System

This is a small end-to-end take-home project for interface.ai: an LLM-driven browser agent that discovers how to complete a task in a legacy-style back-office web app, records the result as a typed artifact (a reusable capability), and can replay that artifact deterministically with safety guardrails and a human-escalation path.

## What it does

1. **Discovery** — an LLM agent observes the UI, chooses actions, and records a successful flow as a `Capability` artifact.
2. **Replay** — the same artifact is re-run without the model, using stable locators and checkpoints.
3. **Guardrails** — an allowlist, redaction, and policy checks on every action.
4. **Human handoff** — the agent can pause and request operator intervention.
5. **Evidence** — logs and screenshots are written to `evidence/`.

## Architecture

- `app/` — a local Flask credit-union sandbox with a multi-step member lookup / account-opening flow.
- `agent/` — LLM client, page-control extraction, and discovery runner.
- `artifact/` — Pydantic models for the typed capability artifact and storage utilities.
- `replay/` — deterministic replay engine with business-outcome and failure handling.
- `guardrails/` — action allowlist, domain allowlist, PII redaction, and irreversible-action checks.
- `human_operator/` — file-based pause / resume / handoff helpers.
- `evidence/` — generated artifacts, logs, and screenshots from runs.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

Set the OpenAI key:

```bash
export OPENAI_API_KEY="..."
```

## Run the demo

1. Start the sandbox application:

```bash
cd app
python app.py
```

2. In another shell, run a discovery for a successful balance lookup:

```bash
python discover_member.py
```

3. Replay the resulting artifact:

```bash
python replay_member.py
```

4. Discover a known business outcome (member not found):

```bash
python discover_bad.py
```

5. Replay the not-found artifact:

```bash
python replay_not_found.py
```

Evidence of the runs is saved under `evidence/`.

## Notes

- The target app intentionally uses table-based HTML with no test IDs.
- The artifact schema decouples the recorded flow from the raw LLM transcript.
- "Member not found" is treated as a business outcome, not a crash.
- This is a focused vertical slice; see `REPORT.md` for design trade-offs and cut lines.
