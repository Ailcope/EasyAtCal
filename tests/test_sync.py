from datetime import UTC, datetime

from easyatcal.models import Shift
from easyatcal.state import State
from easyatcal.sync import compute_changes


def _shift(id_: str, updated: str = "2026-04-18T10:00:00+00:00") -> Shift:
    return Shift(
        id=id_,
        start=datetime(2026, 4, 20, 9, tzinfo=UTC),
        end=datetime(2026, 4, 20, 17, tzinfo=UTC),
        title="t",
        location=None,
        notes=None,
        updated_at=datetime.fromisoformat(updated),
    )


def test_new_shifts_are_adds():
    state = State(shift_to_event={})
    shifts = [_shift("a"), _shift("b")]

    changes = compute_changes(shifts, state, known_updated_at={})

    assert [s.id for s in changes.adds] == ["a", "b"]
    assert changes.updates == []
    assert changes.deletes == []


def test_known_shifts_unchanged_do_nothing():
    state = State(shift_to_event={"a": "evt-a"})
    shifts = [_shift("a", "2026-04-18T10:00:00+00:00")]
    known_updated = {"a": "2026-04-18T10:00:00+00:00"}

    changes = compute_changes(shifts, state, known_updated_at=known_updated)

    assert changes.is_empty()


def test_known_shift_with_new_updated_at_is_update():
    state = State(shift_to_event={"a": "evt-a"})
    shifts = [_shift("a", "2026-04-19T10:00:00+00:00")]
    known_updated = {"a": "2026-04-18T10:00:00+00:00"}

    changes = compute_changes(shifts, state, known_updated_at=known_updated)

    assert len(changes.updates) == 1
    shift, event_uid = changes.updates[0]
    assert shift.id == "a"
    assert event_uid == "evt-a"


def test_shift_missing_from_remote_is_delete():
    state = State(shift_to_event={"a": "evt-a", "b": "evt-b"})
    shifts = [_shift("a")]
    known_updated = {"a": "2026-04-18T10:00:00+00:00",
                     "b": "2026-04-18T10:00:00+00:00"}

    changes = compute_changes(shifts, state, known_updated_at=known_updated)

    assert changes.deletes == ["evt-b"]
