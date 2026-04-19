from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from easyatcal.models import Shift


@dataclass
class Changes:
    adds: list[Shift] = field(default_factory=list)
    updates: list[tuple[Shift, str]] = field(default_factory=list)
    # list of event uids to delete
    deletes: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.adds or self.updates or self.deletes)


class CalendarBackend(Protocol):
    def apply(self, changes: Changes) -> dict[str, str]:
        """Apply the given changes. Return mapping shift_id -> event_uid for
        all adds/updates."""
        ...
