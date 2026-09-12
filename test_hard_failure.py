import json
from pathlib import Path
from artifact.models import Capability, InputParameter, OutputParameter, Step, TargetRef
from artifact.store import save_artifact
from replay.replay import replay_capability

hard_failure = Capability(
    id="lookup-member-balance",
    name="lookup_member_balance",
    goal="Hard-failure replay with a broken submit locator",
    entry_url="http://localhost:5000",
    inputs=[],
    outputs=[],
    steps=[
        Step(step_number=1, action="fill", target=TargetRef(kind="name", value="username"), value="teller", expected_url="http://localhost:5000/"),
        Step(step_number=2, action="fill", target=TargetRef(kind="name", value="password"), value="password123", expected_url="http://localhost:5000/"),
        Step(step_number=3, action="click", target=TargetRef(kind="name", value="does_not_exist"), expected_url="http://localhost:5000/", checkpoint="Staff Login"),
    ],
    success_condition="Never expected to succeed",
)

artifact_path = Path("evidence/replay/artifact_hard_failure.json")
artifact_path.parent.mkdir(parents=True, exist_ok=True)
save_artifact(hard_failure, artifact_path)

result = replay_capability(hard_failure, {}, headless=True)
report = {
    "status": result.status,
    "step_id": result.step_id,
    "expected": result.expected,
    "observed": result.observed,
    "locator_attempts": result.locator_attempts,
    "screenshot_path": result.screenshot_path,
    "dom_snapshot_path": result.dom_snapshot_path,
    "error_message": result.error_message,
}
report_path = Path(f"evidence/replay/failure-{result.step_id}.json")
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print(json.dumps(report, indent=2))
