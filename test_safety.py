import json
from pathlib import Path
from artifact.models import Capability, Step, TargetRef
from artifact.store import save_artifact
from replay.replay import replay_capability

# 1. Off-allowlist navigation
nav_guard = Capability(
    id="guardrail-nav",
    name="guardrail_nav",
    goal="Attempt to navigate to an off-allowlist domain",
    entry_url="http://localhost:5000",
    inputs=[],
    outputs=[],
    steps=[
        Step(step_number=1, action="navigate", target=TargetRef(kind="unknown", value=""), value="http://evil.com", expected_url="http://evil.com"),
    ],
    success_condition="Should be blocked by guardrails",
)
nav_path = Path("evidence/safety/artifact_guardrail_nav.json")
nav_path.parent.mkdir(parents=True, exist_ok=True)
save_artifact(nav_guard, nav_path)

r1 = replay_capability(nav_guard, {}, headless=True, save_to=Path("evidence/safety/replay_guardrail_nav.jsonl"))

# 2. Off-allowlist action type
action_guard = Capability(
    id="guardrail-action",
    name="guardrail_action",
    goal="Attempt an action type not in the allowlist",
    entry_url="http://localhost:5000",
    inputs=[],
    outputs=[],
    steps=[
        Step(step_number=1, action="delete_file", target=TargetRef(kind="unknown", value=""), value="C:\\Windows\\system.ini"),
    ],
    success_condition="Should be blocked by guardrails",
)
action_path = Path("evidence/safety/artifact_guardrail_action.json")
save_artifact(action_guard, action_path)

r2 = replay_capability(action_guard, {}, headless=True, save_to=Path("evidence/safety/replay_guardrail_action.jsonl"))

report = {
    "off_allowlist_navigation": {"status": r1.status, "error": r1.error_message},
    "off_allowlist_action": {"status": r2.status, "error": r2.error_message},
}
with open("evidence/safety/guardrail_report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print(json.dumps(report, indent=2))
