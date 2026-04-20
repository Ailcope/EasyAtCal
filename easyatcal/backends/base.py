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


@dataclass
class ApplyResult:
    """Outcome of a backend.apply call.

    `mapping` is shift_id -> event_uid for every add/update that succeeded.
    `deleted_uids` is the subset of `Changes.deletes` that the backend
    confirms were removed from the underlying calendar.
    """
    mapping: dict[str, str] = field(default_factory=dict)
    deleted_uids: list[str] = field(default_factory=list)


class BackendError(RuntimeError):
    """Raised by a backend when apply fails partway through.

    Carries whatever progress was made so the orchestrator can persist it
    before re-raising.
    """
    def __init__(self, message: str, partial: ApplyResult) -> None:
        super().__init__(message)
        self.partial = partial


class CalendarBackend(Protocol):
    def set_all_shifts(self, shifts: list[Shift]) -> None:
        """Provide the backend with the complete list of known valid shifts."""
        ...

    def apply(self, changes: Changes) -> ApplyResult:
        """Apply the given changes and return an ApplyResult.

        On partial failure, raise BackendError with a populated .partial."""
        ...
