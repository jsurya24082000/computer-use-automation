# Design Report

## 1. Architecture

The system is a single Python project split into four bounded subsystems:

- **Sandbox (`app/`)** — a tiny Flask credit-union back office with table-based markup, no test IDs, and a login/search/detail/confirmation flow. It is the proxy target.
- **Discovery (`agent/`)** — an LLM-driven `observe → decide → act` loop using Playwright, an accessibility- and attribute-derived control list, and OpenAI `gpt-4o` structured JSON output.
- **Artifact (`artifact/`)** — a Pydantic `Capability` schema that captures the goal, typed inputs/outputs, ordered steps, locators, checkpoints, and version.
- **Replay (`replay/`)** — a deterministic runner that executes the artifact without the LLM, checks checkpoints, distinguishes business outcomes from failures, and applies guardrails.
- **Guardrails (`guardrails/`)** — action and domain allowlist, redaction, and irreversible-action tagging.
- **Handoff (`human_operator/`)** — a file-based pause / resume seam for human intervention.

We run everything in one process for the take-home; the boundaries are clean enough that each could become a service later.

## 2. Artifact schema

A `Capability` is a versioned, reviewable contract:

- `id`, `name`, `goal`, `version` — identity and purpose.
- `inputs` / `outputs` — typed parameters and expected return values.
- `entry_url` — where replay starts.
- `steps` — each step has `step_number`, `action`, `target` (locator by `name` or `text`), `value`, `expected_url`, `checkpoint`, `output`, and `notes`.
- `success_condition` — human- and agent-readable definition of done.

The schema deliberately separates *what* the capability needs, *what* it does, and *what* it returns. That makes it possible for a calling agent to discover and invoke it by name with typed args.

## 3. Determinism & error handling

- **Locators** — the artifact records `name` attributes or visible text rather than generated CSS selectors. This is a compromise: stable enough for this sandbox, but the `target` schema is designed to accept a list of fallbacks (e.g., `aria-label`, role+name, nearest label text) in a production version.
- **Checkpoints** — each `done` step carries a `checkpoint` string that replay verifies is present in the page body. For example, the successful flow asserts the detail page contains the savings balance; the not-found flow asserts the page contains "Member not found".
- **Runtime error taxonomy**:
  - `business_outcome` — a legitimate result the caller needs (e.g., "Member not found").
  - `recoverable` — a transient or known condition (e.g., a slow load handled by `wait`).
  - `failure` — an unexpected condition (locator not found, checkpoint missing, policy block).
- **Exceptional states** — the replay engine explicitly checks for "Member not found" before treating it as a locator error, and the checkpoint mechanism guards against silent UI drift.

## 4. Heterogeneity & multi-tenant

The current implementation uses web DOM. To extend to a legacy desktop app or a frameset-driven web app, the seam would be a `SurfaceAdapter` interface:

```python
class SurfaceAdapter(Protocol):
    def get_controls(self) -> List[Control]: ...
    def perform(self, action: Action) -> Result: ...
    def get_body_text(self) -> str: ...
    def screenshot(self) -> Path: ...
```

A desktop adapter would use the OS accessibility tree or MSAA/UI Automation. A frameset web adapter would enter frames before extracting controls. The `Capability` would still store `surface_type` and per-surface locators, so the same logical flow can run on different surfaces.

For multi-tenant reuse, an artifact would have a base `tenant_invariant` form plus per-tenant `overrides` (e.g., route prefixes, field labels, branding strings). A `drift_detector` would periodically replay the capability across tenants and flag pages where the checkpoint fails, prompting re-recording of the affected step.

## 5. Escalation & handoff

- **Detect** — the agent can raise `escalate` when it has no safe action. A `handoff_{run_id}.json` file is written with the current step, URL, and reason.
- **Pause/resume** — an operator can create `evidence/pause` to stop all runs, or remove the handoff file to resume.
- **Control transfer** — the same live Playwright browser session is left open. A minimal console (or a real operator UI) would let the human click/type, then signal `evidence/resume` so the automation continues. For this take-home the operator surface is a file seam; the design is real but the UI is stubbed.

## 6. Safety

- **Allowlist** — only `localhost:5000` and allowed actions (`click`, `fill`, `submit`, `navigate`, `wait`, `done`, `escalate`) are permitted.
- **Irreversible actions** — `submit` is tagged as risky and can be gated behind confirmation in a production version.
- **Redaction** — `password`, `token`, `ssn`, and 9-digit SSN patterns are masked in logs. The artifact still contains the demo sandbox password because the replay needs it; in a real environment the artifact would store a placeholder and the replay would receive the credential from a vault.
- **No secrets in README / source** — the real `OPENAI_API_KEY` is read from the environment.

## 7. Cuts

- **No real desktop app or frameset target** — the design has a `SurfaceAdapter` seam, but only the Playwright web adapter is implemented.
- **No full operator UI** — handoff is file-based. A real deployment needs a WebSocket/SSE co-browse console.
- **No persistent drift detection** — only checkpoint verification on replay.
- **No multi-run stability metric** — the `Multi-run stability` stretch goal is not implemented.
- **No real model recovery on replay** — a bounded LLM fallback step would be the next defensive feature.

The focus is a working vertical slice: one successful discovery, one successful replay, one business-outcome replay, one hard-failure replay, one guardrail-block replay, one redaction proof, and one escalation handoff, plus clean abstractions for the rest.


## 8. Evidence

The evidence/ directory contains:
- rtifact_capability-167f2522.json � successful balance-lookup artifact.
- rtifact_capability-6a9f2a5d.json � member-not-found business-outcome artifact.
- rtifact_capability-hard-failure.json � deliberately broken locator for replay failure testing.
- rtifact_capability-guardrail-test.json � off-allowlist navigation for guardrail testing.
- handoff_ddfd25f3.json � agent intervention request (escalation).
- edaction_proof.json � log showing password value redacted.
- eplay_log_*.jsonl and discovery_log_*.jsonl � per-run logs.
- eplay_screenshots_* � failure screenshots for hard failure and guardrail blocks.

