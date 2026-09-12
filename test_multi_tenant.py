import json
from pathlib import Path
from artifact.models import TargetRef, TenantOverride
from artifact.store import load_artifact, save_artifact
from replay.replay import replay_capability

# 1. Replay the SAME artifact against Tenant B with no changes.
artifact = load_artifact(Path("evidence/artifact_lookup-member-balance.json"))
artifact.entry_url = "http://localhost:5001"  # Tenant B

print("--- Tenant B before override ---")
before = replay_capability(
    artifact,
    {"username": "teller", "password": "password123", "member_id": "12345"},
    headless=True,
    tenant_id="tenant-b",
    save_to=Path("evidence/multi-tenant/before_override.jsonl"),
)
print(json.dumps({"status": before.status, "step_id": before.step_id, "error": before.error_message, "locator_attempts": before.locator_attempts}, indent=2))

# 2. Add a TenantOverride for step 4 (member lookup field on Tenant B is f4 / Account Number).
artifact.tenant_overrides.append(
    TenantOverride(
        tenant_id="tenant-b",
        step_number=4,
        target=TargetRef(kind="name", value="f4"),
        notes="Tenant B renamed the field and the name attribute from f3 to f4",
    )
)
save_artifact(artifact, Path("evidence/multi-tenant/artifact_tenant_b.json"))

print("--- Tenant B after override ---")
after = replay_capability(
    artifact,
    {"username": "teller", "password": "password123", "member_id": "12345"},
    headless=True,
    tenant_id="tenant-b",
    save_to=Path("evidence/multi-tenant/after_override.jsonl"),
)
print(json.dumps({"status": after.status, "outputs": after.outputs}, indent=2))

# 3. Drift warning: warn if more than 1 override per tenant.
per_tenant = {}
for o in artifact.tenant_overrides:
    per_tenant[o.tenant_id] = per_tenant.get(o.tenant_id, 0) + 1
for t, n in per_tenant.items():
    if n > 1:
        print(f"DRIFT WARNING: {t} has {n} overrides. Consider a dedicated recording if this grows.")
