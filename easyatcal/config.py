from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class EasyAtWorkAuth(BaseModel):
    """Credentials + endpoint config.

    Two modes:
    - ``client``: OAuth2 client_credentials against a (hypothetical) public
      API. Kept for forward-compat; not used against the real tenant.
    - ``user``: Scrape the web SPA via Playwright. The user logs in once
      (``eaw-sync login``) and cookies are persisted. All shift requests
      go through the same web origin with those cookies.
    """

    auth_mode: Literal["client", "user"] = "user"

    # client mode
    client_id: str | None = None
    client_secret: str | None = None
    base_url: str = "https://api.easyatwork.com"

    # user mode
    email: str | None = None
    login_url: str = "https://app.easyatwork.com/"
    app_url: str = "https://app.easyatwork.com"
    # Which endpoint to hit for shifts once logged in.
    # Blank → client raises on sync, prompting HAR inspection.
    shifts_endpoint: str = ""
    # Playwright login form selectors (override per tenant if the form
    # layout differs).
    email_selector: str = "input[type='email'], input[name='email'], input[name='username']"
    password_selector: str = "input[type='password']"
    submit_selector: str = "button[type='submit'], input[type='submit']"
    # Browser headless by default; set false for first-run debug.
    headless: bool = True
    # Max wait after submit for navigation to finish (ms).
    login_timeout_ms: int = 20000

    @model_validator(mode="after")
    def _check_mode_fields(self) -> EasyAtWorkAuth:
        if self.auth_mode == "client" and (
            not self.client_id or not self.client_secret
        ):
            raise ValueError(
                "auth_mode=client requires client_id and client_secret"
            )
        if self.auth_mode == "user" and not self.email:
            raise ValueError("auth_mode=user requires email")
        return self


class SyncSettings(BaseModel):
    lookback_days: int = Field(ge=0, default=7)
    lookahead_days: int = Field(ge=1, default=90)
    user_id: str | None = None


class EventKitSettings(BaseModel):
    calendar_name: str = "Work Shifts"
    calendar_source: str = "iCloud"


class IcsSettings(BaseModel):
    output_path: str = "~/Documents/easyatwork-shifts.ics"


class BackendsSettings(BaseModel):
    eventkit: EventKitSettings = EventKitSettings()
    ics: IcsSettings = IcsSettings()


class LoggingSettings(BaseModel):
    level: str = "INFO"
    format: Literal["text", "json"] = "text"


class Config(BaseModel):
    easyatwork: EasyAtWorkAuth
    sync: SyncSettings = SyncSettings()
    backend: Literal["eventkit", "ics"]
    backends: BackendsSettings = BackendsSettings()
    logging: LoggingSettings = LoggingSettings()

    @field_validator("backend")
    @classmethod
    def validate_backend(cls, v: str) -> str:
        if v not in ("eventkit", "ics"):
            raise ValueError(f"Unknown backend: {v}")
        return v


_ENV_OVERRIDES: dict[str, tuple[str, str]] = {
    "EAW_CLIENT_ID": ("easyatwork", "client_id"),
    "EAW_CLIENT_SECRET": ("easyatwork", "client_secret"),
    "EAW_BASE_URL": ("easyatwork", "base_url"),
    "EAW_EMAIL": ("easyatwork", "email"),
    "EAW_LOGIN_URL": ("easyatwork", "login_url"),
    "EAW_APP_URL": ("easyatwork", "app_url"),
    "EAW_SHIFTS_ENDPOINT": ("easyatwork", "shifts_endpoint"),
}


def load_config(path: Path) -> Config:
    if not path.exists():
        raise FileNotFoundError(path)
    raw = yaml.safe_load(path.read_text())
    for env_var, (section, key) in _ENV_OVERRIDES.items():
        value = os.environ.get(env_var)
        if value is not None:
            raw.setdefault(section, {})[key] = value
    return Config.model_validate(raw)
