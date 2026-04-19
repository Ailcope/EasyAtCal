from datetime import datetime, timezone

import pytest

from easyatcal.models import Shift


def test_shift_is_frozen_dataclass():
    shift = Shift(
        id="abc",
        start=datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
        end=datetime(2026, 4, 20, 17, 0, tzinfo=timezone.utc),
        title="Morning",
        location=None,
        notes=None,
        updated_at=datetime(2026, 4, 18, 10, 0, tzinfo=timezone.utc),
    )
    assert shift.id == "abc"
    assert shift.duration_hours == 8.0


def test_shift_requires_tz_aware_datetimes():
    with pytest.raises(ValueError, match="tz-aware"):
        Shift(
            id="abc",
            start=datetime(2026, 4, 20, 9, 0),  # naive
            end=datetime(2026, 4, 20, 17, 0, tzinfo=timezone.utc),
            title="t",
            location=None,
            notes=None,
            updated_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        )
