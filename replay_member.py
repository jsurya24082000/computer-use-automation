import json
from pathlib import Path
from artifact.store import load_artifact
from replay.replay import replay_capability

artifact_path = Path("evidence/artifact_lookup-member-balance.json")
print(f"Replaying {artifact_path}")
capability = load_artifact(artifact_path)

# Happy path
result = replay_capability(
    capability,
    {"username": "teller", "password": "password123", "member_id": "12345"},
    headless=True,
    save_to=Path("evidence/replay/replay_12345_success.jsonl"),
)
print(json.dumps({"status": result.status, "outputs": result.outputs}, indent=2))
