from agent.discover import DiscoveryAgent

agent = DiscoveryAgent(
    goal="Log in with username 'teller' and password 'password123', then look up member 12345 and read their current savings balance",
    inputs={"member_id": "12345"},
    outputs={"savings_balance": "savings-balance"},
    headless=True,
)
capability = agent.run()
print(f"Saved: evidence/artifact_{capability.id}.json")
print(f"Steps: {len(capability.steps)}")
