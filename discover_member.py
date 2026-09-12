from agent.discover import DiscoveryAgent
from artifact.models import KnownOutcome, TargetRef

agent = DiscoveryAgent(
    goal="Log in with username '{username}' and password '{password}', then look up member {member_id} and read their current savings balance",
    inputs={"username": "teller", "password": "password123", "member_id": "12345"},
    outputs={"savings_balance": "current savings balance"},
    known_outcomes=[
        KnownOutcome(
            name="member_not_found",
            detect=TargetRef(kind="body_contains", value="Member not found"),
            message="The provided member ID was not found in the system.",
        )
    ],
    headless=True,
)
capability = agent.run()
print(f"Saved: evidence/artifact_{capability.id}.json")
print(f"Steps: {len(capability.steps)}")
