from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Any

import httpx
import keyring


class SessionStore:
    """Persists Playwright ``storage_state`` (cookies + localStorage)
    on disk with 0600 perms. Securely stores JWT in OS keyring.

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
        try:
            import keyring
            keyring.delete_password("easyatcal", "jwt")
        except Exception:
            pass

    def eaw_meta(self) -> dict[str, Any] | None:
        """Returns the extracted eaw_meta (api_url, customer_id, employee_id)
        if it was intercepted during login.
        """
        state = self.load()
        if state is None:
            return None
        return state.get("eaw_meta")

    def access_token(self) -> str | None:
        """Get the JWT access token from the OS keyring, falling back to scanning
        persisted localStorage (and upgrading it to keyring if found).
        """
        try:
            token = keyring.get_password("easyatcal", "jwt")
            if token:
                return token
        except Exception:
            pass  # keyring backend might be unavailable or locked

        state = self.load()
        if state is None:
            return None
        
        found_token = None
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
                    found_token = value
                    break
            if found_token:
                break
        
        if found_token:
            with contextlib.suppress(Exception):
                keyring.set_password("easyatcal", "jwt", found_token)
            return found_token
        return None
