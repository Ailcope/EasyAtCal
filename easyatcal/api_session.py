from __future__ import annotations

import contextlib
import time
from datetime import UTC, date, datetime
from typing import Any

import httpx

from easyatcal.api import ApiError, AuthError
from easyatcal.models import Shift
from easyatcal.session import SessionStore


class SessionEawClient:
    """Fetches shifts against the regional easy@work API using the JWT
    the SPA obtains at login.

    URL shape observed in the wild (EU-West-3 tenant)::

        GET https://eu-west-3.api.easyatwork.com
            /customers/{customer_id}/employees/{employee_id}/shifts
            ?from=YYYY-MM-DD HH:MM:SS
            &order_by=from&direction=asc
            &with[]=schedule.customer
        Authorization: Bearer <JWT>
        Origin: https://app.easyatwork.com

    The JWT is extracted from the Playwright ``storage_state``'s
    localStorage (populated by ``eaw-sync login``).
    """

    _MAX_RETRIES = 5

    def __init__(
        self,
        *,
        shifts_url: str,
        session_store: SessionStore,
        origin: str = "https://app.easyatwork.com",
        ui_version: str = "2.313.0",
        timeout: float = 30.0,
    ) -> None:
        self.shifts_url = shifts_url
        self.session_store = session_store
        self.origin = origin.rstrip("/")
        self.ui_version = ui_version
        self._http = httpx.Client(timeout=timeout)
        self._token: str | None = None

    def authenticate(self) -> None:
        token = self.session_store.access_token()
        if token is None:
            raise AuthError(
                "No access token in stored session. Run `eaw-sync login`."
            )
        self._token = token
        self._http.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json, text/plain, */*",
                "Origin": self.origin,
                "Referer": f"{self.origin}/",
                "X-Ui-Version": self.ui_version,
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            }
        )

    def fetch_shifts(
        self,
        from_date: date,
        to_date: date,
        user_id: str | None = None,  # kept for ShiftFetcher protocol
    ) -> list[Shift]:
        self.authenticate()

        # easy@work wants space-separated "YYYY-MM-DD HH:MM:SS". httpx
        # URL-encodes the space as %20 automatically.
        from_str = f"{from_date.isoformat()} 00:00:00"
        to_str = f"{to_date.isoformat()} 23:59:59"

        # httpx accepts sequences for repeated params: `with[]=schedule.customer`
        params: list[tuple[str, str | int | float | bool | None]] = [
            ("from", from_str),
            ("to", to_str),
            ("order_by", "from"),
            ("direction", "asc"),
            ("with[]", "schedule.customer"),
        ]

        url: str | None = self.shifts_url
        first = True
        out: list[Shift] = []
        while url is not None:
            r = self._retry_get(url, params if first else None)
            first = False
            try:
                payload = r.json()
                for raw in _iter_rows(payload):
                    out.append(_parse_shift(raw))
                url = _next_url(payload)
            except (KeyError, TypeError, ValueError) as e:
                raise ApiError(
                    f"Unexpected session API response shape. Parse error: {e}. "
                    f"Top-level keys: "
                    f"{list(payload.keys()) if isinstance(payload, dict) else 'not a dict'}"
                ) from e
        return out

    def _retry_get(
        self,
        url: str,
        params: list[tuple[str, str | int | float | bool | None]] | None,
    ) -> httpx.Response:
        attempts = 0
        while True:
            r = self._http.get(url, params=params)
            if r.status_code == 200:
                return r
            if r.status_code == 401:
                raise AuthError(
                    "Access token rejected (HTTP 401). "
                    "Token probably expired — run `eaw-sync login`."
                )
            if r.status_code in (429, 500, 502, 503, 504):
                attempts += 1
                if attempts > self._MAX_RETRIES:
                    raise ApiError(
                        f"rate limit / server errors exceeded retries "
                        f"({r.status_code})"
                    )
                delay = 2 ** (attempts - 1)
                retry_after = r.headers.get("Retry-After")
                if retry_after is not None:
                    with contextlib.suppress(ValueError):
                        delay = max(delay, int(retry_after))
                time.sleep(delay)
                continue
            raise ApiError(f"GET {url} -> {r.status_code} {r.text[:300]}")


def _iter_rows(payload: Any) -> list[dict[str, Any]]:
    """Accept common Laravel/DRF paginated shapes until we pin the real
    one:

    - ``{"data": [...], "next_page_url": ...}``   (Laravel paginator)
    - ``{"data": [...], "meta": {...}}``          (Laravel resource)
    - ``{"results": [...], "next": ...}``          (DRF)
    - ``{"items": [...]}`` / ``{"shifts": [...]}``
    - ``[...]``  (bare list)
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "results", "items", "shifts"):
            v = payload.get(key)
            if isinstance(v, list):
                return v
    return []


def _next_url(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    # Laravel paginator
    v = payload.get("next_page_url")
    if isinstance(v, str) and v:
        return v
    for key in ("next", "next_url", "nextPage"):
        v = payload.get(key)
        if isinstance(v, str) and v:
            return v
    links = payload.get("links")
    if isinstance(links, dict):
        v = links.get("next")
        if isinstance(v, str) and v:
            return v
    return None


def _parse_shift(raw: dict[str, Any]) -> Shift:
    """Best-effort mapping. Accepts a handful of common field spellings.

    Observed so far (will expand once a response body is available):
    - id: ``id`` / ``uuid`` / ``shiftId``
    - start: ``start`` / ``starts_at`` / ``from`` / ``start_date``
    - end: ``end`` / ``ends_at`` / ``to`` / ``end_date``
    - updated_at: ``updated_at`` / ``updatedAt`` / ``modified_at``
    - title: ``title`` / ``name`` / ``label`` / nested
             ``schedule.customer.name`` (via `with[]=schedule.customer`)
    - location: ``location`` / ``place`` / ``site``
    """

    def pick(*keys: str) -> Any:
        for k in keys:
            if k in raw and raw[k] is not None:
                return raw[k]
        return None

    id_val = pick("id", "uuid", "shiftId")
    start_val = pick("start", "starts_at", "from", "start_date", "startTime")
    end_val = pick("end", "ends_at", "to", "end_date", "endTime")
    updated_val = pick("updated_at", "updatedAt", "modified_at", "modifiedAt")

    if id_val is None or start_val is None or end_val is None:
        raise ValueError(
            f"shift row missing id/start/end; keys present: {list(raw)}"
        )

    # Title: prefer schedule.customer.name if included (matches `with[]`)
    title = pick("title", "name", "label")
    location = pick("location", "place", "site")
    notes = pick("notes", "description", "comments")
    
    schedule = raw.get("schedule")
    if isinstance(schedule, dict):
        customer = schedule.get("customer")
        if isinstance(customer, dict):
            if title is None:
                title = customer.get("name")
            
            # If no direct location, try to extract address from customer
            if location is None:
                addr_parts = []
                for k in ("address1", "address2", "postal_code", "city"):
                    val = customer.get(k)
                    if val and str(val).strip():
                        addr_parts.append(str(val).strip())
                if addr_parts:
                    location = ", ".join(addr_parts)

    if not title:
        title = "Shift"

    return Shift(
        id=str(id_val),
        start=_parse_dt(start_val),
        end=_parse_dt(end_val),
        title=str(title),
        location=str(location) if location else None,
        notes=str(notes) if notes else None,
        updated_at=_parse_dt(updated_val) if updated_val else datetime.now(UTC),
    )


def _parse_dt(s: str) -> datetime:
    """Accept both ISO-8601 (``2026-04-20T09:00:00+00:00``) and
    Laravel-style (``2026-04-20 09:00:00``) timestamps. Naive values
    are treated as UTC — the easy@work API sends tenant-local
    timestamps without an offset.
    """
    from datetime import UTC

    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        dt = datetime.fromisoformat(s.replace(" ", "T"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt
