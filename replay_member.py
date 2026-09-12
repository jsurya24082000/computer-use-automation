from artifact.store import find_latest_artifact, load_artifact
from replay.replay import replay_capability

artifact_path = find_latest_artifact()
print(f"Replaying {artifact_path}")
capability = load_artifact(artifact_path)
result = replay_capability(capability, {"member_id": "12345"}, headless=True)
print(f"Outcome: {result.outcome}")
if not result.success:
    print(f"Failed at step {result.error_step}: {result.error_message}")
else:
    print(f"Outputs: {result.outputs}")
