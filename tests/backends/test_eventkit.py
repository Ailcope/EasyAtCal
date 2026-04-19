import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from easyatcal.backends.base import Changes
from easyatcal.models import Shift

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="EventKit backend is macOS only"
)


def _shift(id_: str) -> Shift:
    return Shift(
        id=id_,
        start=datetime(2026, 4, 20, 9, tzinfo=UTC),
        end=datetime(2026, 4, 20, 17, tzinfo=UTC),
        title=f"Shift {id_}",
        location=None,
        notes=None,
        updated_at=datetime(2026, 4, 18, tzinfo=UTC),
    )


@patch("easyatcal.backends.eventkit._event_store")
def test_apply_adds_creates_events(mock_store_factory):
    store = MagicMock()
    calendar = MagicMock()
    store.calendarsForEntityType_.return_value = [calendar]
    calendar.title.return_value = "Work Shifts"
    calendar.source.return_value.title.return_value = "iCloud"
    mock_store_factory.return_value = store

    created_event = MagicMock()
    created_event.calendarItemExternalIdentifier.return_value = "evt-1"
    store.saveEvent_span_error_.return_value = (True, None)

    from easyatcal.backends.eventkit import EventKitBackend

    with patch(
        "easyatcal.backends.eventkit._new_event", return_value=created_event
    ):
        backend = EventKitBackend(
            calendar_name="Work Shifts", calendar_source="iCloud"
        )
        result = backend.apply(Changes(adds=[_shift("s1")]))

    assert result.mapping == {"s1": "evt-1"}
    store.saveEvent_span_error_.assert_called()


@patch("easyatcal.backends.eventkit._event_store")
def test_apply_deletes_removes_events(mock_store_factory):
    store = MagicMock()
    calendar = MagicMock()
    calendar.title.return_value = "Work Shifts"
    calendar.source.return_value.title.return_value = "iCloud"
    store.calendarsForEntityType_.return_value = [calendar]

    existing = MagicMock()
    existing.calendarItemExternalIdentifier.return_value = "evt-1"
    store.calendarItemWithIdentifier_.return_value = existing
    store.removeEvent_span_error_.return_value = (True, None)
    mock_store_factory.return_value = store

    from easyatcal.backends.eventkit import EventKitBackend
    backend = EventKitBackend(
        calendar_name="Work Shifts", calendar_source="iCloud"
    )

    backend.apply(Changes(deletes=["evt-1"]))

    store.removeEvent_span_error_.assert_called()
