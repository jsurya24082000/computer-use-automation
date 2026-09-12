from agent.discover import DiscoveryAgent

agent = DiscoveryAgent(
    goal="Log in with username 'teller' and password 'password123', then look up member 99999 and read their current savings balance",
    inputs={"member_id": "99999"},
    outputs={"savings_balance": "savings-balance"},
    headless=True,
)
capability = agent.run()
print(f"Saved: evidence/artifact_{capability.id}.json")
print(f"Steps: {len(capability.steps)}")
