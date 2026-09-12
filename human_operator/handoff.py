import json
from datetime import datetime
from pathlib import Path

HANDOFF_DIR = Path("evidence")
HANDOFF_DIR.mkdir(exist_ok=True)


def request_handoff(run_id: str, step: int, reason: str, page=None) -> Path:
    path = HANDOFF_DIR / f"handoff_{run_id}.json"
    payload = {
        "run_id": run_id,
        "step": step,
        "reason": reason,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "url": page.url if page else None,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Handoff requested: {path}")
    return path


def check_handoff_or_pause() -> None:
    """If the operator has raised a pause flag, stop until it is cleared."""
    pause = HANDOFF_DIR / "pause"
    if pause.exists():
        raise RuntimeError("Automation paused by operator. Remove evidence/pause to resume.")


def resume(run_id: str) -> None:
    path = HANDOFF_DIR / f"handoff_{run_id}.json"
    if path.exists():
        path.unlink()
    pause = HANDOFF_DIR / "pause"
    if pause.exists():
        pause.unlink()
