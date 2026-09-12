import json
from guardrails.policy import default_policy
from pathlib import Path

policy = default_policy()

# Simulated LLM action log entry for a password fill.
raw = {
    "type": "llm_action",
    "data": {
        "action": "fill",
        "target": {"name": "password", "type": "password"},
        "value": "password123",
        "reason": "Filling in the password field to proceed with login.",
        "step_number": 2,
    },
}

redacted = policy.redact(raw)
print(json.dumps(redacted, indent=2))

Path("evidence").mkdir(exist_ok=True)
with open("evidence/redaction_proof.json", "w", encoding="utf-8") as f:
    json.dump(redacted, f, indent=2)
