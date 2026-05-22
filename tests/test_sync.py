from datetime import UTC, date, datetime

from easyatcal.models import Shift
from easyatcal.state import State
from easyatcal.sync import compute_changes

# Window wide enough to contain the _shift() start date below.
WINDOW_FROM = date(2026, 4, 1)
WINDOW_TO = date(2026, 12, 31)


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

    changes = compute_changes(
        shifts, state, known_updated_at={},
        from_date=WINDOW_FROM, to_date=WINDOW_TO, known_start={},
    )

    assert [s.id for s in changes.adds] == ["a", "b"]
    assert changes.updates == []
    assert changes.deletes == []


def test_known_shifts_unchanged_do_nothing():
    state = State(shift_to_event={"a": "evt-a"})
    shifts = [_shift("a", "2026-04-18T10:00:00+00:00")]
    known_updated = {"a": "2026-04-18T10:00:00+00:00"}

    changes = compute_changes(
        shifts, state, known_updated_at=known_updated,
        from_date=WINDOW_FROM, to_date=WINDOW_TO, known_start={},
    )

    assert changes.is_empty()


def test_known_shift_with_new_updated_at_is_update():
    state = State(shift_to_event={"a": "evt-a"})
    shifts = [_shift("a", "2026-04-19T10:00:00+00:00")]
    known_updated = {"a": "2026-04-18T10:00:00+00:00"}

    changes = compute_changes(
        shifts, state, known_updated_at=known_updated,
        from_date=WINDOW_FROM, to_date=WINDOW_TO, known_start={},
    )

    assert len(changes.updates) == 1
    shift, event_uid = changes.updates[0]
    assert shift.id == "a"
    assert event_uid == "evt-a"


def test_in_window_shift_missing_from_remote_is_delete():
    state = State(
        shift_to_event={"a": "evt-a", "b": "evt-b"},
        shift_start={
            "a": "2026-04-20T09:00:00+00:00",
            "b": "2026-04-20T09:00:00+00:00",
        },
    )
    shifts = [_shift("a")]
    known_updated = {"a": "2026-04-18T10:00:00+00:00",
                     "b": "2026-04-18T10:00:00+00:00"}

    changes = compute_changes(
        shifts, state, known_updated_at=known_updated,
        from_date=WINDOW_FROM, to_date=WINDOW_TO,
        known_start=state.shift_start,
    )

    assert changes.deletes == ["evt-b"]


def test_past_shift_outside_window_is_preserved():
    # "old" sits before the lookback window; the API no longer returns it.
    # It must NOT be deleted just because it fell out of the fetch range.
    state = State(
        shift_to_event={"old": "evt-old", "b": "evt-b"},
        shift_start={
            "old": "2026-01-01T09:00:00+00:00",
            "b": "2026-04-20T09:00:00+00:00",
        },
    )
    remote = []  # nothing returned this window

    changes = compute_changes(
        remote, state, known_updated_at={},
        from_date=WINDOW_FROM, to_date=WINDOW_TO,
        known_start=state.shift_start,
    )

    # In-window "b" is a real cancellation -> delete. Past "old" -> preserved.
    assert changes.deletes == ["evt-b"]


def test_missing_shift_with_unknown_start_is_preserved():
    state = State(shift_to_event={"x": "evt-x"})  # no start recorded

    changes = compute_changes(
        [], state, known_updated_at={},
        from_date=WINDOW_FROM, to_date=WINDOW_TO, known_start={},
    )

    assert changes.deletes == []
