# Computer-Use Automation System

A focused end-to-end take-home for interface.ai: one `lookup_member_balance` capability, a hostile legacy-style back-office sandbox, deterministic replay, safety guardrails, human handoff, and multi-tenant reuse.

## Setup

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
export OPENAI_API_KEY="..."
```

## Run the sandbox

Base tenant:

```bash
cd app
python app.py
```

Tenant B (for multi-tenant demo):

```bash
cd app
python tenant_b.py
```

## Discovery

```bash
python discover_member.py
```

## Replays

Happy path:

```bash
python replay_member.py
```

Member not found (business outcome):

```bash
python replay_not_found.py
```

Failure with debug report:

```bash
python test_hard_failure.py
```

## Escalation

```bash
python discover_escalation.py
# then create evidence/interventions/resume_escalation-demo.json to simulate human completion
```

## Multi-tenant

```bash
python test_multi_tenant.py
```

## Safety

```bash
python test_safety.py
python test_redaction.py
```

## Stability

```bash
python test_stability.py
```

## Evidence

All run outputs are in `evidence/`.

- `evidence/artifact_lookup-member-balance.json` — the single capability.
- `evidence/replay/` — replay logs, failure reports, screenshots, DOM snapshots.
- `evidence/interventions/` — human handoff requests.
- `evidence/multi-tenant/` — Tenant B before/after override logs.
- `evidence/safety/` — guardrail and redaction proof.
- `evidence/stability/` — 5-run report.

See `REPORT.md` for the design write-up.
