from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from easyatcal.backends.base import ApplyResult, BackendError, CalendarBackend
from easyatcal.models import Shift
from easyatcal.state import State, load_state, save_state
from easyatcal.sync import compute_changes


class ShiftFetcher(Protocol):
    def fetch_shifts(self, from_date, to_date) -> list[Shift]: ...


def run_sync(
    api: ShiftFetcher,
    backend: CalendarBackend,
    state_path: Path,
    lookback_days: int,
    lookahead_days: int,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(timezone.utc)
    from_date = (now - timedelta(days=lookback_days)).date()
    to_date = (now + timedelta(days=lookahead_days)).date()

    remote_shifts = api.fetch_shifts(from_date=from_date, to_date=to_date)
    state = load_state(state_path)
    changes = compute_changes(
        remote_shifts, state, known_updated_at=state.shift_updated_at
    )

    raised: BackendError | None = None
    try:
        result: ApplyResult = backend.apply(changes)
    except BackendError as e:
        result = e.partial
        raised = e

    _persist(
        state=state,
        state_path=state_path,
        remote_shifts=remote_shifts,
        result=result,
        now=now,
    )

    if raised is not None:
        raise raised


def _persist(
    *,
    state: State,
    state_path: Path,
    remote_shifts: list[Shift],
    result: ApplyResult,
    now: datetime,
) -> None:
    new_shift_to_event = dict(state.shift_to_event)
    new_updated_at = dict(state.shift_updated_at)

    for shift_id, event_uid in result.mapping.items():
        new_shift_to_event[shift_id] = event_uid

    # For every shift we successfully wrote, stamp the new updated_at.
    remote_by_id = {s.id: s for s in remote_shifts}
    for shift_id in result.mapping:
        shift = remote_by_id.get(shift_id)
        if shift is not None:
            new_updated_at[shift_id] = shift.updated_at.isoformat()

    # Prune confirmed deletions.
    deleted_uid_set = set(result.deleted_uids)
    new_shift_to_event = {
        sid: evt
        for sid, evt in new_shift_to_event.items()
        if evt not in deleted_uid_set
    }
    # Drop matching updated_at entries for any shift whose event we just
    # deleted (its shift_id no longer maps to an event in new_shift_to_event).
    new_updated_at = {
        sid: ts for sid, ts in new_updated_at.items() if sid in new_shift_to_event
    }

    save_state(
        state_path,
        State(
            shift_to_event=new_shift_to_event,
            shift_updated_at=new_updated_at,
            last_sync=now.isoformat(),
        ),
    )
