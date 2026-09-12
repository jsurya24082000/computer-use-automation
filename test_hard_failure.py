from artifact.models import Capability, InputParameter, OutputParameter, Step
from artifact.store import save_artifact
from pathlib import Path
from replay.replay import replay_capability

hard_failure = Capability(
    id="capability-hard-failure",
    name="Hard failure demo",
    goal="Log in with a broken submit locator",
    entry_url="http://localhost:5000",
    inputs=[],
    outputs=[],
    steps=[
        Step(step_number=1, action="fill", target={"name": "username"}, value="teller", expected_url="http://localhost:5000/"),
        Step(step_number=2, action="fill", target={"name": "password"}, value="password123", expected_url="http://localhost:5000/"),
        Step(step_number=3, action="click", target={"name": "does_not_exist"}, expected_url="http://localhost:5000/", checkpoint="Staff Login"),
    ],
    success_condition="Never expected to succeed",
)

artifact_path = Path("evidence/artifact_capability-hard-failure.json")
save_artifact(hard_failure, artifact_path)

result = replay_capability(hard_failure, {}, headless=True)
print(f"Outcome: {result.outcome}")
print(f"Failed at step: {result.error_step}")
print(f"Error: {result.error_message}")
print(f"Screenshot: {result.screenshot_path}")
