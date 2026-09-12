from agent.discover import DiscoveryAgent
from artifact.models import KnownOutcome, TargetRef

agent = DiscoveryAgent(
    goal="Log in with username '{username}' and password '{password}', then navigate to the admin settings page and disable member {member_id}",
    inputs={"username": "teller", "password": "password123", "member_id": "12345"},
    outputs={"status": "status"},
    known_outcomes=[
        KnownOutcome(
            name="member_not_found",
            detect=TargetRef(kind="body_contains", value="Member not found"),
            message="The provided member ID was not found in the system.",
        )
    ],
    headless=False,
    run_id="escalation-demo",
    capability_id="escalation-demo",
)
capability = agent.run()
print(f"Saved: evidence/artifact_{capability.id}.json")
print(f"Steps: {len(capability.steps)}")
