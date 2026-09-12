import json
from pathlib import Path
from typing import Optional

from .models import Capability


def save_artifact(capability: Capability, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(capability.model_dump_json(indent=2))


def load_artifact(path: Path) -> Capability:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Capability(**data)


def find_latest_artifact(pattern: str = "artifact_*.json") -> Optional[Path]:
    evidence = Path("evidence")
    files = sorted(evidence.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None
