from pathlib import Path
from artifact.store import load_artifact
from replay.replay import replay_capability

artifact_path = Path("evidence/artifact_capability-6a9f2a5d.json")
print(f"Replaying {artifact_path}")
capability = load_artifact(artifact_path)
result = replay_capability(capability, {"member_id": "99999"}, headless=True)
print(f"Outcome: {result.outcome}")
if not result.success:
    print(f"Failed at step {result.error_step}: {result.error_message}")
else:
    print(f"Outputs: {result.outputs}")
