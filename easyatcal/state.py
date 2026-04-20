from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class State:
    shift_to_event: dict[str, str] = field(default_factory=dict)
    shift_updated_at: dict[str, str] = field(default_factory=dict)
    last_sync: str | None = None
    preferences: dict[str, bool] = field(default_factory=dict)


def load_state(path: Path) -> State:
    if not path.exists():
        return State()
    try:
        data = json.loads(path.read_text())
        return State(
            shift_to_event=dict(data.get("shift_to_event", {})),
            shift_updated_at=dict(data.get("shift_updated_at", {})),
            last_sync=data.get("last_sync"),
            preferences=dict(data.get("preferences", {})),
        )
    except (json.JSONDecodeError, ValueError):
        backup = path.with_suffix(path.suffix + ".bak")
        path.replace(backup)
        return State()


def save_state(path: Path, state: State) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(asdict(state), indent=2, sort_keys=True))
    os.replace(tmp, path)
