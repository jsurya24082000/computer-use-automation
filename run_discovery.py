import argparse
import json
import os
import sys

from agent.discover import DiscoveryAgent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--goal", required=True, help="Natural language goal for the agent")
    parser.add_argument("--inputs", default="{}", help="JSON inputs for the goal")
    parser.add_argument("--outputs", default="{}", help="JSON output names/descriptions")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    args = parser.parse_args()

    inputs = json.loads(args.inputs)
    outputs = json.loads(args.outputs)

    agent = DiscoveryAgent(
        goal=args.goal,
        inputs=inputs,
        outputs=outputs,
        headless=args.headless,
    )
    capability = agent.run()
    print(f"Capability saved: evidence/artifact_{capability.id}.json")
    print(f"Steps: {len(capability.steps)}")


if __name__ == "__main__":
    main()
