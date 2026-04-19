from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Shift:
    id: str
    start: datetime
    end: datetime
    title: str
    location: str | None
    notes: str | None
    updated_at: datetime

    def __post_init__(self) -> None:
        for field_name in ("start", "end", "updated_at"):
            value = getattr(self, field_name)
            if value.tzinfo is None:
                raise ValueError(f"{field_name} must be tz-aware")

    @property
    def duration_hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600.0
