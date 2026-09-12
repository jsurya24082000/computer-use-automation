import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

INTERV_DIR = Path("evidence/interventions")
INTERV_DIR.mkdir(parents=True, exist_ok=True)


def check_handoff_or_pause() -> None:
    """If the operator has raised a pause flag, stop until it is cleared."""
    pause = Path("evidence/pause")
    if pause.exists():
        raise RuntimeError("Automation paused by operator. Remove evidence/pause to resume.")


def resume(run_id: str) -> None:
    path = INTERV_DIR / f"{run_id}.json"
    if path.exists():
        path.unlink()
    pause = Path("evidence/pause")
    if pause.exists():
        pause.unlink()


class ControlState(str, Enum):
    AUTOMATION = "AUTOMATION"
    PENDING_HUMAN = "PENDING_HUMAN"
    HUMAN = "HUMAN"
    RESUMING = "RESUMING"


class Intervention(BaseModel):
    intervention_id: str
    capability_id: str
    run_id: str
    step_id: int
    goal: str
    reason: str
    current_url: Optional[str]
    screenshot_path: Optional[str]
    what_to_do: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class ControlTransition(BaseModel):
    from_state: str
    to_state: str
    timestamp: str
    reason: Optional[str] = None


class StateMachine:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.state = ControlState.AUTOMATION
        self.transitions: List[ControlTransition] = []
        self.log = Path("evidence") / f"control_log_{run_id}.jsonl"
        self.log.parent.mkdir(parents=True, exist_ok=True)
        self._transition_to(ControlState.AUTOMATION, "initial")

    def _transition_to(self, new_state: ControlState, reason: Optional[str] = None):
        old = self.state
        self.state = new_state
        t = ControlTransition(from_state=old, to_state=new_state, timestamp=datetime.utcnow().isoformat() + "Z", reason=reason)
        self.transitions.append(t)
        with open(self.log, "a", encoding="utf-8") as f:
            f.write(t.model_dump_json() + "\n")
        print(f"[control] {old} -> {new_state}: {reason}")

    def request_intervention(self, intervention: Intervention) -> Path:
        self._transition_to(ControlState.PENDING_HUMAN, f"intervention {intervention.intervention_id}")
        path = INTERV_DIR / f"{intervention.intervention_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            f.write(intervention.model_dump_json(indent=2))
        print(f"Intervention requested: {path}")
        return path

    def wait_for_resume(self, timeout: float = 60.0) -> Optional[Path]:
        self._transition_to(ControlState.HUMAN, "awaiting human")
        resume_file = INTERV_DIR / f"resume_{self.run_id}.json"
        start = time.time()
        while not resume_file.exists():
            if time.time() - start > timeout:
                self._transition_to(ControlState.AUTOMATION, "resume timeout")
                raise TimeoutError("Human did not resume within timeout")
            time.sleep(0.5)
        self._transition_to(ControlState.RESUMING, "resume signal received")
        return resume_file

    def complete(self):
        self._transition_to(ControlState.AUTOMATION, "run complete")


class HumanActions:
    def capture(pre: Dict[str, Any], post: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "pre_handoff": pre,
            "post_handoff": post,
            "changes": {
                "url_changed": pre.get("url") != post.get("url"),
                "title_changed": pre.get("title") != post.get("title"),
                "field_values_changed": pre.get("fields") != post.get("fields"),
            },
        }
