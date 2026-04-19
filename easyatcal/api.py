from __future__ import annotations

import contextlib
import json
import os
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

from easyatcal.models import Shift


class AuthError(Exception):
    pass


class ApiError(Exception):
    pass


class EawClient:
    _MAX_RETRIES = 5

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str,
        token_cache: Path,
        timeout: float = 30.0,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.token_cache = Path(token_cache)
        self._http = httpx.Client(timeout=timeout)
        self._token: str | None = None

    # ----- auth -----

    def authenticate(self) -> str:
        cached = self._read_cache()
        if cached is not None:
            self._token = cached
            return cached
        return self._fetch_token()

    def _read_cache(self) -> str | None:
        if not self.token_cache.exists():
            return None
        try:
            data = json.loads(self.token_cache.read_text())
        except (json.JSONDecodeError, ValueError):
            return None
        expires_at = datetime.fromisoformat(data["expires_at"])
        if expires_at <= datetime.now(UTC):
            return None
        return data["access_token"]

    def _fetch_token(self) -> str:
        try:
            r = self._http.post(
                f"{self.base_url}/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
        except httpx.HTTPError as e:
            raise AuthError(f"network error during auth: {e}") from e
        if r.status_code != 200:
            raise AuthError(f"auth failed: {r.status_code} {r.text}")
        data = r.json()
        token = data["access_token"]
        expires_at = datetime.now(UTC) + timedelta(
            seconds=int(data.get("expires_in", 3600))
        )
        self._write_cache(token, expires_at)
        self._token = token
        return token

    def _write_cache(self, token: str, expires_at: datetime) -> None:
        self.token_cache.parent.mkdir(parents=True, exist_ok=True)
        payload = {"access_token": token, "expires_at": expires_at.isoformat()}
        tmp = self.token_cache.with_suffix(self.token_cache.suffix + ".tmp")
        tmp.write_text(json.dumps(payload))
        os.replace(tmp, self.token_cache)
        with contextlib.suppress(OSError):
            os.chmod(self.token_cache, 0o600)

    # ----- shifts -----

    def fetch_shifts(self, from_date: date, to_date: date) -> list[Shift]:
        """Return list[Shift] between from_date (inclusive) and to_date (exclusive)."""
        token = self.authenticate()
        url: str | None = f"{self.base_url}/v1/shifts"
        params: dict | None = {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
        }
        headers = {"Authorization": f"Bearer {token}"}

        out: list[Shift] = []
        while url is not None:
            attempts = 0
            while True:
                r = self._http.get(url, params=params, headers=headers)
                if r.status_code == 200:
                    break
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
                raise ApiError(f"GET {url} -> {r.status_code} {r.text}")

            payload = r.json()
            for raw in payload.get("data", []):
                out.append(
                    Shift(
                        id=raw["id"],
                        start=datetime.fromisoformat(raw["start"]),
                        end=datetime.fromisoformat(raw["end"]),
                        title=raw.get("title", "Shift"),
                        location=raw.get("location"),
                        notes=raw.get("notes"),
                        updated_at=datetime.fromisoformat(raw["updated_at"]),
                    )
                )
            url = payload.get("next")
            params = None  # next URL already includes cursor
        return out
