from agent.discover import DiscoveryAgent

agent = DiscoveryAgent(
    goal="Log in with username 'teller' and password 'password123', then navigate to the admin settings page and disable member 12345",
    inputs={"member_id": "12345"},
    outputs={"status": "status"},
    headless=True,
)
capability = agent.run()
print(f"Saved: evidence/artifact_{capability.id}.json")
print(f"Steps: {len(capability.steps)}")
