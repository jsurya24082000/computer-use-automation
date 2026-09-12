import json
from pathlib import Path
from guardrails.policy import default_policy

policy = default_policy()

# Simulated LLM action log entry with a password and an account number.
raw = {
    "type": "llm_action",
    "data": {
        "action": "fill",
        "target": {"name": "password", "type": "password"},
        "value": "password123",
        "reason": "Filling the password field.",
    },
    "body": "Account 100-12345-0 has balance $5420.75. SSN 123-45-6789 on file.",
}

redacted = policy.redact(raw)
print(json.dumps(redacted, indent=2))

Path("evidence/safety").mkdir(parents=True, exist_ok=True)
with open("evidence/safety/redaction_proof.json", "w", encoding="utf-8") as f:
    json.dump(redacted, f, indent=2)
