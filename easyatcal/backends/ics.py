from __future__ import annotations

from pathlib import Path
from typing import Any

from icalendar import Calendar, Event

from easyatcal.backends.base import ApplyResult, Changes
from easyatcal.models import Shift

UID_PREFIX = "easyatcal-"


def _uid_for(shift_id: str) -> str:
    return f"{UID_PREFIX}{shift_id}"


def _to_event(
    shift: Shift,
    uid: str,
    event_title_format: str = "{title}",
    alarm_minutes_before: int | None = None,
) -> Any:
    from datetime import timedelta

    from icalendar import Alarm
    ev = Event()  # type: ignore[no-untyped-call]
    ev.add("uid", uid)
    
    # Format the title
    title = event_title_format.format(
        title=shift.title,
        location=shift.location or "",
        notes=shift.notes or "",
    ).strip()
    
    ev.add("summary", title)
    ev.add("dtstart", shift.start)
    ev.add("dtend", shift.end)
    ev.add("last-modified", shift.updated_at)
    if shift.location:
        ev.add("location", shift.location)
    if shift.notes:
        ev.add("description", shift.notes)
        
    if alarm_minutes_before is not None:
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", "Shift Reminder")
        alarm.add("trigger", timedelta(minutes=-alarm_minutes_before))
        ev.add_component(alarm)
        
    return ev


class IcsBackend:
    """File-based calendar backend that regenerates the .ics on each apply.

    `known_shifts` is the previous set of shifts the caller knows about — used
    so we can rewrite the file without losing events unrelated to the current
    change set.
    """

    def __init__(
        self,
        output_path: Path,
        known_shifts: list[Shift],
        event_title_format: str = "{title}",
        alarm_minutes_before: int | None = None,
    ) -> None:
        self.output_path = Path(output_path).expanduser()
        self._current: dict[str, Shift] = {s.id: s for s in known_shifts}
        self.event_title_format = event_title_format
        self.alarm_minutes_before = alarm_minutes_before

    def apply(self, changes: Changes) -> ApplyResult:
        mapping: dict[str, str] = {}

        for shift in changes.adds:
            self._current[shift.id] = shift
            mapping[shift.id] = _uid_for(shift.id)

        for shift, _event_uid in changes.updates:
            self._current[shift.id] = shift
            mapping[shift.id] = _uid_for(shift.id)

        delete_uids = set(changes.deletes)
        to_drop = [
            sid for sid in self._current
            if _uid_for(sid) in delete_uids
        ]
        confirmed_deletes: list[str] = []
        for sid in to_drop:
            self._current.pop(sid, None)
            confirmed_deletes.append(_uid_for(sid))
        # Any requested delete for a uid we never knew about is treated as
        # "already gone" — surface it so the orchestrator prunes state.
        for uid in delete_uids - set(confirmed_deletes):
            confirmed_deletes.append(uid)

        self._write()
        return ApplyResult(mapping=mapping, deleted_uids=confirmed_deletes)

    def _write(self) -> None:
        cal = Calendar()  # type: ignore[no-untyped-call]
        cal.add("prodid", "-//EasyAtCal//EN")
        cal.add("version", "2.0")
        for shift in self._current.values():
            cal.add_component(_to_event(
                shift,
                _uid_for(shift.id),
                self.event_title_format,
                self.alarm_minutes_before,
            ))

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.output_path.with_suffix(self.output_path.suffix + ".tmp")
        tmp.write_bytes(cal.to_ical())
        tmp.replace(self.output_path)
