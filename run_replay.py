import argparse
import json

from artifact.store import find_latest_artifact, load_artifact
from replay.replay import replay_capability


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", default=None, help="Path to artifact JSON")
    parser.add_argument("--params", default="{}", help="JSON parameter values")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    artifact_path = args.artifact or find_latest_artifact()
    if not artifact_path:
        print("No artifact found in evidence/")
        return

    capability = load_artifact(artifact_path)
    params = json.loads(args.params)
    result = replay_capability(capability, params, headless=args.headless)

    print(f"Outcome: {result.outcome}")
    if not result.success:
        print(f"Failed at step {result.error_step}: {result.error_message}")
    else:
        print(f"Outputs: {result.outputs}")


if __name__ == "__main__":
    main()
