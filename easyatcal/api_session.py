from __future__ import annotations

import contextlib
import time
from datetime import date, datetime
from typing import Any

import httpx

from easyatcal.api import ApiError, AuthError
from easyatcal.models import Shift
from easyatcal.session import SessionStore


class SessionEawClient:
    """Fetches shifts against the easy@work web app using persisted
    browser cookies (from ``eaw-sync login``).

    Endpoint is tenant-specific. Set ``shifts_endpoint`` on the config
    to the path the web app hits (look in DevTools → Network).
    """

    _MAX_RETRIES = 5

    def __init__(
        self,
        *,
        app_url: str,
        shifts_endpoint: str,
        session_store: SessionStore,
        timeout: float = 30.0,
    ) -> None:
        self.app_url = app_url.rstrip("/")
        self.shifts_endpoint = shifts_endpoint
        self.session_store = session_store
        self._http = httpx.Client(timeout=timeout)

    def authenticate(self) -> None:
        cookies = self.session_store.cookies()
        if cookies is None:
            raise AuthError(
                "No session cookies found. Run `eaw-sync login` first."
            )
        self._http.cookies = cookies
        self._http.headers.update({
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        })

    def fetch_shifts(
        self,
        from_date: date,
        to_date: date,
        user_id: str | None = None,
    ) -> list[Shift]:
        if not self.shifts_endpoint:
            raise ApiError(
                "easyatwork.shifts_endpoint is blank. Capture a HAR from "
                "the web app schedule view, find the request that returns "
                "your shifts, and set that path (e.g. '/api/v1/shifts') "
                "in the config."
            )
        self.authenticate()

        url: str | None = self._absolute(self.shifts_endpoint)
        first_params: dict[str, str] = {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
        }
        if user_id is not None:
            first_params["user_id"] = user_id
        params: dict[str, str] | None = first_params

        out: list[Shift] = []
        while url is not None:
            r = self._retry_get(url, params)
            try:
                payload = r.json()
                for raw in _iter_rows(payload):
                    out.append(_parse_shift(raw))
                next_url = _next_url(payload)
                if next_url:
                    url = next_url if next_url.startswith("http") else self._absolute(next_url)
                    params = None
                else:
                    url = None
            except (KeyError, TypeError, ValueError) as e:
                raise ApiError(
                    f"Unexpected session API response shape. Parse error: {e}. "
                    f"Top-level keys: "
                    f"{list(payload.keys()) if isinstance(payload, dict) else 'not a dict'}"
                ) from e
        return out

    def _absolute(self, path: str) -> str:
        if path.startswith("http"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.app_url}{path}"

    def _retry_get(
        self,
        url: str,
        params: dict[str, str] | None,
    ) -> httpx.Response:
        attempts = 0
        while True:
            r = self._http.get(url, params=params)
            if r.status_code == 200:
                return r
            if r.status_code == 401:
                raise AuthError(
                    "Session cookies rejected (HTTP 401). "
                    "Run `eaw-sync login` to refresh."
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
    """Accept common paginated shapes until we pin the real one:
    - {"data": [...], "next": ...}
    - {"results": [...], "next": ...}
    - {"items": [...]}
    - [...]  (bare list)
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
    for key in ("next", "next_url", "nextPage"):
        v = payload.get(key)
        if isinstance(v, str) and v:
            return v
    # DRF-style nested
    links = payload.get("links")
    if isinstance(links, dict):
        v = links.get("next")
        if isinstance(v, str) and v:
            return v
    return None


def _parse_shift(raw: dict[str, Any]) -> Shift:
    """Best-effort mapping until we know the real field names.

    Tries a handful of common spellings. Override once HAR is captured.
    """
    def pick(*keys: str) -> Any:
        for k in keys:
            if k in raw and raw[k] is not None:
                return raw[k]
        return None

    id_val = pick("id", "uuid", "shiftId")
    start_val = pick("start", "starts_at", "startDate", "startTime", "from")
    end_val = pick("end", "ends_at", "endDate", "endTime", "to")
    updated_val = pick("updated_at", "updatedAt", "modified_at", "modifiedAt")

    if id_val is None or start_val is None or end_val is None:
        raise ValueError(
            f"shift row missing id/start/end; keys present: {list(raw)}"
        )

    return Shift(
        id=str(id_val),
        start=datetime.fromisoformat(str(start_val)),
        end=datetime.fromisoformat(str(end_val)),
        title=pick("title", "name", "label") or "Shift",
        location=pick("location", "place", "site"),
        notes=pick("notes", "note", "comment"),
        updated_at=datetime.fromisoformat(
            str(updated_val or start_val)
        ),
    )
