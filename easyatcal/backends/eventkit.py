"""macOS EventKit calendar backend.

Only usable on macOS. Requires `pyobjc-framework-EventKit` (install the
`eventkit` extra).
"""
from __future__ import annotations

import sys
from typing import Any

from easyatcal.backends.base import ApplyResult, BackendError, Changes
from easyatcal.models import Shift


class EventKitUnavailableError(RuntimeError):
    pass


class EventKitPermissionError(RuntimeError):
    pass


def _import_eventkit():  # pragma: no cover — platform guard
    if sys.platform != "darwin":
        raise EventKitUnavailableError("EventKit backend requires macOS")
    try:
        import EventKit  # type: ignore[import-not-found]
    except ImportError as e:
        raise EventKitUnavailableError(
            "pyobjc-framework-EventKit not installed; "
            "pip install 'easyatcal[eventkit]'"
        ) from e
    return EventKit


def _event_store() -> Any:  # pragma: no cover — exercised via mocks in tests
    EventKit = _import_eventkit()
    store = EventKit.EKEventStore.alloc().init()
    from threading import Event as _E
    granted = {"ok": False, "err": None}
    done = _E()

    def _cb(ok, err):
        granted["ok"] = bool(ok)
        granted["err"] = err
        done.set()

    try:
        store.requestFullAccessToEventsWithCompletion_(_cb)
    except AttributeError:
        store.requestAccessToEntityType_completion_(0, _cb)  # 0 = EKEntityTypeEvent

    done.wait(timeout=30)
    if not granted["ok"]:
        raise EventKitPermissionError(
            "Calendar access denied — grant access in System Settings → "
            "Privacy & Security → Calendars."
        )
    return store


def _new_event(store, calendar, shift: Shift):  # pragma: no cover
    EventKit = _import_eventkit()
    import Foundation  # type: ignore[import-not-found]

    event = EventKit.EKEvent.eventWithEventStore_(store)
    event.setCalendar_(calendar)
    event.setTitle_(shift.title)
    event.setStartDate_(
        Foundation.NSDate.dateWithTimeIntervalSince1970_(shift.start.timestamp())
    )
    event.setEndDate_(
        Foundation.NSDate.dateWithTimeIntervalSince1970_(shift.end.timestamp())
    )
    if shift.location:
        event.setLocation_(shift.location)
    if shift.notes:
        event.setNotes_(shift.notes)
    return event


class EventKitBackend:
    def __init__(self, calendar_name: str, calendar_source: str) -> None:
        self.calendar_name = calendar_name
        self.calendar_source = calendar_source
        self._store = _event_store()
        self._calendar = self._resolve_calendar()

    def _resolve_calendar(self):
        calendars = self._store.calendarsForEntityType_(0)
        for cal in calendars:
            if (
                cal.title() == self.calendar_name
                and cal.source().title() == self.calendar_source
            ):
                return cal
        raise RuntimeError(
            f"Calendar {self.calendar_name!r} not found in source "
            f"{self.calendar_source!r}. Create it in Calendar.app first."
        )

    def apply(self, changes: Changes) -> ApplyResult:
        result = ApplyResult()
        try:
            for shift in changes.adds:
                event = _new_event(self._store, self._calendar, shift)
                ok, err = self._store.saveEvent_span_error_(event, 0, None)
                if not ok:
                    raise BackendError(f"saveEvent failed for {shift.id}: {err}", result)
                result.mapping[shift.id] = event.calendarItemExternalIdentifier()

            for shift, event_uid in changes.updates:
                existing = self._store.calendarItemWithIdentifier_(event_uid)
                if existing is None:
                    event = _new_event(self._store, self._calendar, shift)
                    ok, err = self._store.saveEvent_span_error_(event, 0, None)
                    if not ok:
                        raise BackendError(
                            f"saveEvent (replacement) failed for {shift.id}: {err}",
                            result,
                        )
                    result.mapping[shift.id] = event.calendarItemExternalIdentifier()
                    continue
                existing.setTitle_(shift.title)
                import Foundation  # type: ignore[import-not-found]
                existing.setStartDate_(
                    Foundation.NSDate.dateWithTimeIntervalSince1970_(
                        shift.start.timestamp()
                    )
                )
                existing.setEndDate_(
                    Foundation.NSDate.dateWithTimeIntervalSince1970_(
                        shift.end.timestamp()
                    )
                )
                if shift.location is not None:
                    existing.setLocation_(shift.location)
                if shift.notes is not None:
                    existing.setNotes_(shift.notes)
                ok, err = self._store.saveEvent_span_error_(existing, 0, None)
                if not ok:
                    raise BackendError(
                        f"saveEvent (update) failed for {shift.id}: {err}", result
                    )
                result.mapping[shift.id] = event_uid

            for event_uid in changes.deletes:
                existing = self._store.calendarItemWithIdentifier_(event_uid)
                if existing is None:
                    # Treat as already-deleted so state stays clean.
                    result.deleted_uids.append(event_uid)
                    continue
                ok, err = self._store.removeEvent_span_error_(existing, 0, None)
                if not ok:
                    raise BackendError(
                        f"removeEvent failed for {event_uid}: {err}", result
                    )
                result.deleted_uids.append(event_uid)
        except BackendError:
            raise
        return result
