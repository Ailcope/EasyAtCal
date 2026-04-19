from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator


class EasyAtWorkAuth(BaseModel):
    auth_mode: Literal["client", "user"]
    client_id: str
    client_secret: str
    base_url: str = "https://api.easyatwork.com"


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


_ENV_OVERRIDES = {
    "EAW_CLIENT_ID": ("easyatwork", "client_id"),
    "EAW_CLIENT_SECRET": ("easyatwork", "client_secret"),
    "EAW_BASE_URL": ("easyatwork", "base_url"),
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
