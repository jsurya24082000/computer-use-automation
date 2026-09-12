import json
import time
from pathlib import Path
from artifact.models import ApprovalState
from artifact.store import load_artifact, save_artifact
from replay.replay import replay_capability

capability = load_artifact(Path("evidence/artifact_lookup-member-balance.json"))
capability.approval_state = ApprovalState.DRAFT  # start from draft

count = 5
results = []
all_success = True

for i in range(1, count + 1):
    start = time.time()
    result = replay_capability(
        capability,
        {"username": "teller", "password": "password123", "member_id": "12345"},
        headless=True,
    )
    duration = time.time() - start
    results.append({"run": i, "status": result.status, "outputs": result.outputs, "duration_ms": round(duration * 1000, 2)})
    if result.status != "success":
        all_success = False

capability.stability.total_replays += count
success_count = sum(1 for r in results if r["status"] == "success")
capability.stability.successful_replays += success_count
capability.stability.consecutive_successes = success_count
capability.stability.last_runs = results

if all_success:
    capability.approval_state = ApprovalState.APPROVED
    print(f"Artifact promoted to {ApprovalState.APPROVED} after {count} consecutive successful replays.")
else:
    print(f"Artifact remains {ApprovalState.DRAFT}. Only {success_count}/{count} replays succeeded.")

save_artifact(capability, Path("evidence/artifact_lookup-member-balance.json"))

report = {
    "artifact_id": capability.id,
    "approval_state": capability.approval_state,
    "stability": capability.stability.model_dump(),
    "runs": results,
}
Path("evidence/stability").mkdir(parents=True, exist_ok=True)
with open("evidence/stability/5_run_report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print(json.dumps(report, indent=2))
