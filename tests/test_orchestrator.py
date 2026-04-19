from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from easyatcal.backends.base import Changes
from easyatcal.models import Shift
from easyatcal.orchestrator import run_sync
from easyatcal.state import load_state


def _shift(id_: str) -> Shift:
    return Shift(
        id=id_,
        start=datetime(2026, 4, 20, 9, tzinfo=timezone.utc),
        end=datetime(2026, 4, 20, 17, tzinfo=timezone.utc),
        title=f"t{id_}",
        location=None,
        notes=None,
        updated_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
    )


def test_run_sync_applies_changes_and_persists_state(tmp_path: Path):
    state_path = tmp_path / "state.json"

    api = MagicMock()
    api.fetch_shifts.return_value = [_shift("s1"), _shift("s2")]

    backend = MagicMock()
    backend.apply.return_value = {"s1": "evt-1", "s2": "evt-2"}

    run_sync(
        api=api,
        backend=backend,
        state_path=state_path,
        lookback_days=1,
        lookahead_days=1,
        now=datetime(2026, 4, 19, 12, tzinfo=timezone.utc),
    )

    changes = backend.apply.call_args.args[0]
    assert isinstance(changes, Changes)
    assert [s.id for s in changes.adds] == ["s1", "s2"]

    saved = load_state(state_path)
    assert saved.shift_to_event == {"s1": "evt-1", "s2": "evt-2"}
    assert saved.shift_updated_at["s1"] == "2026-04-18T00:00:00+00:00"
    assert saved.last_sync == "2026-04-19T12:00:00+00:00"
