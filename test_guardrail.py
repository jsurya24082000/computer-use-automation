from artifact.models import Capability, InputParameter, OutputParameter, Step
from artifact.store import save_artifact
from pathlib import Path
from replay.replay import replay_capability

guardrail_test = Capability(
    id="capability-guardrail-test",
    name="Guardrail test",
    goal="Attempt to navigate to an off-allowlist domain",
    entry_url="http://localhost:5000",
    inputs=[],
    outputs=[],
    steps=[
        Step(step_number=1, action="navigate", value="http://evil.com", expected_url="http://evil.com"),
    ],
    success_condition="Should be blocked by guardrails",
)

artifact_path = Path("evidence/artifact_capability-guardrail-test.json")
save_artifact(guardrail_test, artifact_path)

result = replay_capability(guardrail_test, {}, headless=True)
print(f"Outcome: {result.outcome}")
print(f"Failed at step: {result.error_step}")
print(f"Error: {result.error_message}")
print(f"Screenshot: {result.screenshot_path}")
