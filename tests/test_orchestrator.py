from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from easyatcal.backends.base import ApplyResult, BackendError, Changes
from easyatcal.models import Shift
from easyatcal.orchestrator import run_sync
from easyatcal.state import load_state


def _shift(id_: str) -> Shift:
    return Shift(
        id=id_,
        start=datetime(2026, 4, 20, 9, tzinfo=UTC),
        end=datetime(2026, 4, 20, 17, tzinfo=UTC),
        title=f"t{id_}",
        location=None,
        notes=None,
        updated_at=datetime(2026, 4, 18, tzinfo=UTC),
    )


def test_run_sync_applies_changes_and_persists_state(tmp_path: Path):
    state_path = tmp_path / "state.json"

    api = MagicMock()
    api.fetch_shifts.return_value = [_shift("s1"), _shift("s2")]

    backend = MagicMock()
    backend.apply.return_value = ApplyResult(
        mapping={"s1": "evt-1", "s2": "evt-2"},
    )

    run_sync(
        api=api,
        backend=backend,
        state_path=state_path,
        lookback_days=1,
        lookahead_days=1,
        now=datetime(2026, 4, 19, 12, tzinfo=UTC),
    )

    changes = backend.apply.call_args.args[0]
    assert isinstance(changes, Changes)
    assert [s.id for s in changes.adds] == ["s1", "s2"]

    saved = load_state(state_path)
    assert saved.shift_to_event == {"s1": "evt-1", "s2": "evt-2"}
    assert saved.shift_updated_at["s1"] == "2026-04-18T00:00:00+00:00"
    assert saved.last_sync == "2026-04-19T12:00:00+00:00"


def test_run_sync_persists_partial_state_on_backend_error(tmp_path: Path):
    """If backend.apply half-succeeds, state records what did work, then re-raises."""
    state_path = tmp_path / "state.json"

    api = MagicMock()
    api.fetch_shifts.return_value = [_shift("s1"), _shift("s2")]

    backend = MagicMock()
    partial = ApplyResult(mapping={"s1": "evt-1"})
    backend.apply.side_effect = BackendError("boom after s1", partial)

    with pytest.raises(BackendError, match="boom after s1"):
        run_sync(
            api=api,
            backend=backend,
            state_path=state_path,
            lookback_days=1,
            lookahead_days=1,
            now=datetime(2026, 4, 19, 12, tzinfo=UTC),
        )

    # s1 WAS persisted; s2 was NOT.
    saved = load_state(state_path)
    assert saved.shift_to_event == {"s1": "evt-1"}
    assert "s2" not in saved.shift_to_event


def test_run_sync_prunes_deleted_uids(tmp_path: Path):
    """State entries whose event_uid is in deleted_uids are removed."""
    state_path = tmp_path / "state.json"

    # Pre-seed state with s_old -> evt-old
    from easyatcal.state import State, save_state
    save_state(state_path, State(
        shift_to_event={"s_old": "evt-old", "s_keep": "evt-keep"},
        shift_updated_at={
            "s_old": "2026-04-01T00:00:00+00:00",
            "s_keep": "2026-04-01T00:00:00+00:00",
        },
    ))

    api = MagicMock()
    # Remote no longer contains s_old
    api.fetch_shifts.return_value = [_shift("s_keep")]

    backend = MagicMock()
    backend.apply.return_value = ApplyResult(
        mapping={},  # s_keep wasn't changed -> no new mapping
        deleted_uids=["evt-old"],
    )

    run_sync(
        api=api,
        backend=backend,
        state_path=state_path,
        lookback_days=1,
        lookahead_days=1,
        now=datetime(2026, 4, 19, 12, tzinfo=UTC),
    )

    saved = load_state(state_path)
    assert "s_old" not in saved.shift_to_event
    assert saved.shift_to_event["s_keep"] == "evt-keep"
