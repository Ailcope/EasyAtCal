from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Any

import httpx


class SessionStore:
    """Persists Playwright ``storage_state`` (cookies + localStorage)
    on disk with 0600 perms.

    Playwright storage_state shape::

        {"cookies": [{"name": ..., "value": ..., "domain": ...,
                       "path": ..., "expires": ..., "httpOnly": ...,
                       "secure": ..., "sameSite": ...}, ...],
         "origins": [...]}

    We only need the cookies for httpx replay — localStorage is kept
    so a future reuse with Playwright can restore full UI state.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def save(self, storage_state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(storage_state))
        os.replace(tmp, self.path)
        with contextlib.suppress(OSError):
            os.chmod(self.path, 0o600)

    def load(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text())
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        return data

    def cookies(self) -> httpx.Cookies | None:
        """Convert the persisted cookies to an httpx.Cookies jar.
        Returns None if no session is stored.
        """
        state = self.load()
        if state is None:
            return None
        jar = httpx.Cookies()
        for c in state.get("cookies", []):
            name = c.get("name")
            value = c.get("value")
            if not name or value is None:
                continue
            jar.set(
                name=name,
                value=value,
                domain=c.get("domain", ""),
                path=c.get("path", "/"),
            )
        return jar

    def clear(self) -> None:
        with contextlib.suppress(FileNotFoundError):
            self.path.unlink()

    def access_token(self) -> str | None:
        """Scan persisted localStorage for a JWT-looking value.

        easy@work's Angular SPA puts the bearer token in localStorage
        under a key like ``access_token`` or ``token``. We accept any
        value that looks like a JWT (three dot-separated segments).
        """
        state = self.load()
        if state is None:
            return None
        for origin in state.get("origins", []):
            for entry in origin.get("localStorage", []):
                name = entry.get("name") or ""
                value = entry.get("value") or ""
                if not isinstance(value, str):
                    continue
                # Prefer keys whose names smell like a token.
                name_hints = ("access_token", "token", "jwt", "bearer")
                looks_like_jwt = value.count(".") == 2 and len(value) > 40
                if looks_like_jwt and (
                    any(h in name.lower() for h in name_hints)
                    or value.startswith("ey")
                ):
                    return value
        return None
