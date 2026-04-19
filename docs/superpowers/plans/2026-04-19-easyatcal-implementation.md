# EasyAtCal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI (`eaw-sync`) that fetches shifts from the easy@work REST API and writes them to Apple Calendar (via EventKit on macOS) or a portable `.ics` file, with one-way sync and a daemon mode.

**Architecture:** Single Python package `easyatcal` with a pluggable `CalendarBackend` interface. Core modules (`api`, `sync`, `models`, `config`, `cli`) are platform-agnostic. Backends live in `easyatcal/backends/` — `ics.py` is portable, `eventkit.py` is macOS-only via pyobjc. Local state file (`state.json`) maps easy@work shift IDs to calendar event UIDs for idempotent re-runs.

**Tech Stack:** Python 3.11+, `httpx` (HTTP), `pydantic` (config), `icalendar` (ICS backend), `pyobjc-framework-EventKit` (EventKit backend, macOS extra), `typer` (CLI), `pytest` + `responses` (tests).

Spec: `docs/superpowers/specs/2026-04-19-easyatcal-design.md`

---

## Task 1: Project scaffolding and tooling

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `easyatcal/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `config.example.yaml`
- Create: `README.md` (replace existing empty file)

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "easyatcal"
version = "0.1.0"
description = "One-way sync of easy@work shifts to Apple Calendar."
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [{name = "Ailcope"}]
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.6",
    "pyyaml>=6.0",
    "icalendar>=5.0",
    "typer>=0.12",
    "platformdirs>=4.0",
]

[project.optional-dependencies]
eventkit = ["pyobjc-framework-EventKit>=10.0; sys_platform == 'darwin'"]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "responses>=0.25",
    "freezegun>=1.4",
]

[project.scripts]
eaw-sync = "easyatcal.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["easyatcal"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --strict-markers"
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
# Secrets & user data
config.yaml
.env
*.ics
state.json
token.json
.cache/

# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.coverage
htmlcov/
dist/
build/

# Editors / OS
.vscode/
.idea/
.DS_Store
```

- [ ] **Step 3: Create package and test skeletons**

`easyatcal/__init__.py`:
```python
"""EasyAtCal — one-way sync of easy@work shifts to Apple Calendar."""

__version__ = "0.1.0"
```

`tests/__init__.py`: empty file.

`tests/conftest.py`:
```python
import pytest
```

- [ ] **Step 4: Create `config.example.yaml`**

```yaml
easyatwork:
  auth_mode: client            # "client" or "user"
  client_id: "REPLACE_ME"
  client_secret: "REPLACE_ME"  # or set EAW_CLIENT_SECRET env var
  base_url: "https://api.easyatwork.com"

sync:
  lookback_days: 7
  lookahead_days: 90
  user_id: null                # null = self

backend: eventkit              # "eventkit" or "ics"

backends:
  eventkit:
    calendar_name: "Work Shifts"
    calendar_source: "iCloud"
  ics:
    output_path: "~/Documents/easyatwork-shifts.ics"

logging:
  level: INFO
```

- [ ] **Step 5: Create `README.md`**

```markdown
# EasyAtCal

One-way sync of [easy@work](https://www.easyatwork.com) shifts into Apple Calendar.

## Install

```bash
pip install easyatcal                   # core + ICS backend
pip install 'easyatcal[eventkit]'       # add macOS EventKit backend
```

## Configure

```bash
eaw-sync config init
# edit ~/.config/easyatcal/config.yaml
```

## Run

```bash
eaw-sync sync                           # one-shot
eaw-sync watch --interval 15m           # daemon mode
```

See `docs/superpowers/specs/2026-04-19-easyatcal-design.md` for full design.
```

- [ ] **Step 6: Install in editable mode and verify pytest runs**

Run: `pip install -e '.[dev]' && pytest`
Expected: `collected 0 items` — no failure.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore easyatcal/ tests/ config.example.yaml README.md
git commit -m "scaffold: project layout, pyproject, gitignore, readme"
```

---

## Task 2: Shift model

**Files:**
- Create: `easyatcal/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing test**

`tests/test_models.py`:
```python
from datetime import datetime, timezone

from easyatcal.models import Shift


def test_shift_is_frozen_dataclass():
    shift = Shift(
        id="abc",
        start=datetime(2026, 4, 20, 9, 0, tzinfo=timezone.utc),
        end=datetime(2026, 4, 20, 17, 0, tzinfo=timezone.utc),
        title="Morning",
        location=None,
        notes=None,
        updated_at=datetime(2026, 4, 18, 10, 0, tzinfo=timezone.utc),
    )
    assert shift.id == "abc"
    assert shift.duration_hours == 8.0


def test_shift_requires_tz_aware_datetimes():
    import pytest

    with pytest.raises(ValueError, match="tz-aware"):
        Shift(
            id="abc",
            start=datetime(2026, 4, 20, 9, 0),  # naive
            end=datetime(2026, 4, 20, 17, 0, tzinfo=timezone.utc),
            title="t",
            location=None,
            notes=None,
            updated_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: easyatcal.models`.

- [ ] **Step 3: Implement `easyatcal/models.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add easyatcal/models.py tests/test_models.py
git commit -m "feat(models): Shift dataclass with tz-aware validation"
```

---

## Task 3: Config loader

**Files:**
- Create: `easyatcal/config.py`
- Create: `tests/test_config.py`
- Create: `tests/fixtures/config_valid.yaml`

- [ ] **Step 1: Create test fixture**

`tests/fixtures/config_valid.yaml`:
```yaml
easyatwork:
  auth_mode: client
  client_id: "cid"
  client_secret: "csecret"
  base_url: "https://api.easyatwork.com"
sync:
  lookback_days: 7
  lookahead_days: 90
  user_id: null
backend: ics
backends:
  eventkit:
    calendar_name: "Work Shifts"
    calendar_source: "iCloud"
  ics:
    output_path: "~/Documents/shifts.ics"
logging:
  level: INFO
```

- [ ] **Step 2: Write failing tests**

`tests/test_config.py`:
```python
from pathlib import Path

import pytest

from easyatcal.config import Config, load_config


FIXTURE = Path(__file__).parent / "fixtures" / "config_valid.yaml"


def test_load_config_from_file():
    cfg = load_config(FIXTURE)
    assert isinstance(cfg, Config)
    assert cfg.easyatwork.client_id == "cid"
    assert cfg.backend == "ics"
    assert cfg.sync.lookback_days == 7


def test_env_override_for_secret(monkeypatch):
    monkeypatch.setenv("EAW_CLIENT_SECRET", "from-env")
    cfg = load_config(FIXTURE)
    assert cfg.easyatwork.client_secret == "from-env"


def test_invalid_backend_rejected(tmp_path):
    bad = tmp_path / "c.yaml"
    bad.write_text(FIXTURE.read_text().replace("backend: ics", "backend: nonsense"))
    with pytest.raises(ValueError):
        load_config(bad)


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "missing.yaml")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement `easyatcal/config.py`**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add easyatcal/config.py tests/test_config.py tests/fixtures/config_valid.yaml
git commit -m "feat(config): pydantic config loader with env overrides"
```

---

## Task 4: State persistence

**Files:**
- Create: `easyatcal/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write failing tests**

`tests/test_state.py`:
```python
import json
from pathlib import Path

from easyatcal.state import State, load_state, save_state


def test_save_then_load_roundtrip(tmp_path: Path):
    path = tmp_path / "state.json"
    s = State(shift_to_event={"shift-1": "evt-1", "shift-2": "evt-2"},
              last_sync="2026-04-19T12:00:00+00:00")
    save_state(path, s)

    loaded = load_state(path)
    assert loaded.shift_to_event == s.shift_to_event
    assert loaded.last_sync == s.last_sync


def test_load_missing_returns_empty(tmp_path: Path):
    s = load_state(tmp_path / "missing.json")
    assert s.shift_to_event == {}
    assert s.last_sync is None


def test_load_corrupt_backs_up_and_returns_empty(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text("not valid json{{{")

    s = load_state(path)

    assert s.shift_to_event == {}
    assert (tmp_path / "state.json.bak").exists()


def test_save_is_atomic(tmp_path: Path):
    path = tmp_path / "state.json"
    save_state(path, State(shift_to_event={"a": "b"}, last_sync=None))
    # No temp file left behind
    assert not any(p.name.endswith(".tmp") for p in tmp_path.iterdir())
    assert json.loads(path.read_text())["shift_to_event"] == {"a": "b"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_state.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `easyatcal/state.py`**

```python
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class State:
    shift_to_event: dict[str, str] = field(default_factory=dict)
    last_sync: str | None = None


def load_state(path: Path) -> State:
    if not path.exists():
        return State()
    try:
        data = json.loads(path.read_text())
        return State(
            shift_to_event=dict(data.get("shift_to_event", {})),
            last_sync=data.get("last_sync"),
        )
    except (json.JSONDecodeError, ValueError):
        backup = path.with_suffix(path.suffix + ".bak")
        path.replace(backup)
        return State()


def save_state(path: Path, state: State) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(asdict(state), indent=2, sort_keys=True))
    os.replace(tmp, path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_state.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add easyatcal/state.py tests/test_state.py
git commit -m "feat(state): atomic json state with corrupt-file recovery"
```

---

## Task 5: easy@work API client — auth and token cache

**Files:**
- Create: `easyatcal/api.py`
- Create: `tests/test_api_auth.py`

- [ ] **Step 1: Write failing tests**

`tests/test_api_auth.py`:
```python
import json
from pathlib import Path

import pytest
import responses

from easyatcal.api import EawClient, AuthError


@responses.activate
def test_client_credentials_fetch_token(tmp_path: Path):
    responses.add(
        responses.POST,
        "https://api.easyatwork.com/oauth/token",
        json={"access_token": "tok-123", "expires_in": 3600, "token_type": "Bearer"},
        status=200,
    )
    client = EawClient(
        client_id="cid",
        client_secret="csecret",
        base_url="https://api.easyatwork.com",
        token_cache=tmp_path / "token.json",
    )

    token = client.authenticate()

    assert token == "tok-123"
    cached = json.loads((tmp_path / "token.json").read_text())
    assert cached["access_token"] == "tok-123"


@responses.activate
def test_cached_token_reused(tmp_path: Path):
    cache = tmp_path / "token.json"
    # Write a cache entry valid for 1 hour.
    cache.write_text(json.dumps({
        "access_token": "cached-tok",
        "expires_at": "2099-01-01T00:00:00+00:00",
    }))

    client = EawClient(
        client_id="cid",
        client_secret="csecret",
        base_url="https://api.easyatwork.com",
        token_cache=cache,
    )
    token = client.authenticate()

    assert token == "cached-tok"
    assert len(responses.calls) == 0


@responses.activate
def test_auth_failure_raises(tmp_path: Path):
    responses.add(
        responses.POST,
        "https://api.easyatwork.com/oauth/token",
        json={"error": "invalid_client"},
        status=401,
    )
    client = EawClient(
        client_id="bad",
        client_secret="bad",
        base_url="https://api.easyatwork.com",
        token_cache=tmp_path / "token.json",
    )
    with pytest.raises(AuthError):
        client.authenticate()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api_auth.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement auth section of `easyatcal/api.py`**

```python
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx


class AuthError(Exception):
    pass


class ApiError(Exception):
    pass


class EawClient:
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
        self.token_cache = token_cache
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
        if expires_at <= datetime.now(timezone.utc):
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
        expires_at = datetime.now(timezone.utc) + timedelta(
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
        try:
            os.chmod(self.token_cache, 0o600)
        except OSError:
            pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api_auth.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add easyatcal/api.py tests/test_api_auth.py
git commit -m "feat(api): OAuth client_credentials auth with cached token"
```

---

## Task 6: easy@work API client — fetch shifts with retry

**Files:**
- Modify: `easyatcal/api.py` (add methods)
- Create: `tests/test_api_fetch.py`

- [ ] **Step 1: Write failing tests**

`tests/test_api_fetch.py`:
```python
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import responses

from easyatcal.api import ApiError, EawClient
from easyatcal.models import Shift


def _fresh_client(tmp_path: Path) -> EawClient:
    # Pre-seed a valid token so authenticate() short-circuits.
    cache = tmp_path / "token.json"
    cache.write_text(
        '{"access_token":"tok","expires_at":"2099-01-01T00:00:00+00:00"}'
    )
    return EawClient(
        client_id="cid",
        client_secret="csecret",
        base_url="https://api.easyatwork.com",
        token_cache=cache,
    )


@responses.activate
def test_fetch_shifts_single_page(tmp_path: Path):
    responses.add(
        responses.GET,
        "https://api.easyatwork.com/v1/shifts",
        json={
            "data": [
                {
                    "id": "s1",
                    "start": "2026-04-20T09:00:00+00:00",
                    "end": "2026-04-20T17:00:00+00:00",
                    "title": "Morning",
                    "location": "Oslo",
                    "notes": None,
                    "updated_at": "2026-04-18T10:00:00+00:00",
                }
            ],
            "next": None,
        },
        status=200,
    )
    client = _fresh_client(tmp_path)

    shifts = client.fetch_shifts(
        from_date=date(2026, 4, 19), to_date=date(2026, 4, 21)
    )

    assert len(shifts) == 1
    s = shifts[0]
    assert isinstance(s, Shift)
    assert s.id == "s1"
    assert s.location == "Oslo"


@responses.activate
def test_fetch_shifts_follows_pagination(tmp_path: Path):
    responses.add(
        responses.GET,
        "https://api.easyatwork.com/v1/shifts",
        json={
            "data": [{
                "id": "s1",
                "start": "2026-04-20T09:00:00+00:00",
                "end": "2026-04-20T17:00:00+00:00",
                "title": "A", "location": None, "notes": None,
                "updated_at": "2026-04-18T10:00:00+00:00",
            }],
            "next": "https://api.easyatwork.com/v1/shifts?cursor=abc",
        },
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.easyatwork.com/v1/shifts?cursor=abc",
        json={
            "data": [{
                "id": "s2",
                "start": "2026-04-21T09:00:00+00:00",
                "end": "2026-04-21T17:00:00+00:00",
                "title": "B", "location": None, "notes": None,
                "updated_at": "2026-04-18T10:00:00+00:00",
            }],
            "next": None,
        },
        status=200,
        match_querystring=True,
    )
    client = _fresh_client(tmp_path)

    shifts = client.fetch_shifts(
        from_date=date(2026, 4, 19), to_date=date(2026, 4, 22)
    )
    ids = [s.id for s in shifts]
    assert ids == ["s1", "s2"]


@responses.activate
def test_fetch_shifts_retries_on_429(tmp_path: Path, monkeypatch):
    sleeps = []
    monkeypatch.setattr("time.sleep", lambda s: sleeps.append(s))
    responses.add(
        responses.GET,
        "https://api.easyatwork.com/v1/shifts",
        status=429,
    )
    responses.add(
        responses.GET,
        "https://api.easyatwork.com/v1/shifts",
        json={"data": [], "next": None},
        status=200,
    )
    client = _fresh_client(tmp_path)

    shifts = client.fetch_shifts(
        from_date=date(2026, 4, 19), to_date=date(2026, 4, 22)
    )

    assert shifts == []
    assert len(sleeps) == 1
    assert sleeps[0] >= 1  # backed off at least 1s


@responses.activate
def test_fetch_shifts_gives_up_after_5_retries(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    for _ in range(6):
        responses.add(
            responses.GET,
            "https://api.easyatwork.com/v1/shifts",
            status=429,
        )
    client = _fresh_client(tmp_path)

    with pytest.raises(ApiError, match="rate limit"):
        client.fetch_shifts(
            from_date=date(2026, 4, 19), to_date=date(2026, 4, 22)
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api_fetch.py -v`
Expected: FAIL — `fetch_shifts` not defined.

- [ ] **Step 3: Extend `easyatcal/api.py`**

Append these methods to the `EawClient` class (after `_write_cache`):

```python
    # ----- shifts -----

    _MAX_RETRIES = 5

    def fetch_shifts(self, from_date, to_date):
        """Return list[Shift] between from_date (inclusive) and to_date (exclusive)."""
        import time
        from datetime import datetime

        from easyatcal.models import Shift

        token = self.authenticate()
        url = f"{self.base_url}/v1/shifts"
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
                    time.sleep(2 ** (attempts - 1))
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api_fetch.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add easyatcal/api.py tests/test_api_fetch.py
git commit -m "feat(api): fetch_shifts with pagination and backoff"
```

---

## Task 7: Backend interface

**Files:**
- Create: `easyatcal/backends/__init__.py`
- Create: `easyatcal/backends/base.py`
- Create: `tests/backends/__init__.py`
- Create: `tests/backends/test_base.py`

- [ ] **Step 1: Create empty `__init__.py` files**

`easyatcal/backends/__init__.py`: empty.
`tests/backends/__init__.py`: empty.

- [ ] **Step 2: Write failing test**

`tests/backends/test_base.py`:
```python
from easyatcal.backends.base import CalendarBackend, Changes


def test_changes_is_dataclass():
    c = Changes(adds=[], updates=[], deletes=[])
    assert c.adds == []
    assert c.is_empty()


def test_backend_is_protocol_with_apply():
    # Protocol sanity check — any object with .apply() satisfies CalendarBackend
    class Dummy:
        def apply(self, changes: Changes) -> dict[str, str]:
            return {}

    d: CalendarBackend = Dummy()
    assert d.apply(Changes([], [], [])) == {}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/backends/test_base.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement `easyatcal/backends/base.py`**

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/backends/test_base.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add easyatcal/backends/ tests/backends/__init__.py tests/backends/test_base.py
git commit -m "feat(backends): Changes dataclass and CalendarBackend protocol"
```

---

## Task 8: Sync diff engine

**Files:**
- Create: `easyatcal/sync.py`
- Create: `tests/test_sync.py`

- [ ] **Step 1: Write failing tests**

`tests/test_sync.py`:
```python
from datetime import datetime, timezone

from easyatcal.models import Shift
from easyatcal.state import State
from easyatcal.sync import compute_changes


def _shift(id_: str, updated: str = "2026-04-18T10:00:00+00:00") -> Shift:
    return Shift(
        id=id_,
        start=datetime(2026, 4, 20, 9, tzinfo=timezone.utc),
        end=datetime(2026, 4, 20, 17, tzinfo=timezone.utc),
        title="t",
        location=None,
        notes=None,
        updated_at=datetime.fromisoformat(updated),
    )


def test_new_shifts_are_adds():
    state = State(shift_to_event={})
    shifts = [_shift("a"), _shift("b")]

    changes = compute_changes(shifts, state, known_updated_at={})

    assert [s.id for s in changes.adds] == ["a", "b"]
    assert changes.updates == []
    assert changes.deletes == []


def test_known_shifts_unchanged_do_nothing():
    state = State(shift_to_event={"a": "evt-a"})
    shifts = [_shift("a", "2026-04-18T10:00:00+00:00")]
    known_updated = {"a": "2026-04-18T10:00:00+00:00"}

    changes = compute_changes(shifts, state, known_updated_at=known_updated)

    assert changes.is_empty()


def test_known_shift_with_new_updated_at_is_update():
    state = State(shift_to_event={"a": "evt-a"})
    shifts = [_shift("a", "2026-04-19T10:00:00+00:00")]
    known_updated = {"a": "2026-04-18T10:00:00+00:00"}

    changes = compute_changes(shifts, state, known_updated_at=known_updated)

    assert len(changes.updates) == 1
    shift, event_uid = changes.updates[0]
    assert shift.id == "a"
    assert event_uid == "evt-a"


def test_shift_missing_from_remote_is_delete():
    state = State(shift_to_event={"a": "evt-a", "b": "evt-b"})
    shifts = [_shift("a")]
    known_updated = {"a": "2026-04-18T10:00:00+00:00",
                     "b": "2026-04-18T10:00:00+00:00"}

    changes = compute_changes(shifts, state, known_updated_at=known_updated)

    assert changes.deletes == ["evt-b"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sync.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `easyatcal/sync.py`**

```python
from __future__ import annotations

from easyatcal.backends.base import Changes
from easyatcal.models import Shift
from easyatcal.state import State


def compute_changes(
    remote_shifts: list[Shift],
    state: State,
    known_updated_at: dict[str, str],
) -> Changes:
    """Diff remote shifts against the last-known state.

    known_updated_at maps shift_id -> ISO-formatted updated_at recorded at last sync.
    """
    remote_by_id = {s.id: s for s in remote_shifts}
    adds: list[Shift] = []
    updates: list[tuple[Shift, str]] = []
    deletes: list[str] = []

    for shift in remote_shifts:
        event_uid = state.shift_to_event.get(shift.id)
        if event_uid is None:
            adds.append(shift)
            continue
        last_updated = known_updated_at.get(shift.id)
        if last_updated != shift.updated_at.isoformat():
            updates.append((shift, event_uid))

    for shift_id, event_uid in state.shift_to_event.items():
        if shift_id not in remote_by_id:
            deletes.append(event_uid)

    return Changes(adds=adds, updates=updates, deletes=deletes)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sync.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add easyatcal/sync.py tests/test_sync.py
git commit -m "feat(sync): diff engine for adds/updates/deletes"
```

---

## Task 9: Extend State to track `updated_at`

**Files:**
- Modify: `easyatcal/state.py`
- Modify: `tests/test_state.py`

- [ ] **Step 1: Add test for new field**

Append to `tests/test_state.py`:
```python
def test_state_roundtrip_with_updated_at(tmp_path):
    from easyatcal.state import State, load_state, save_state

    path = tmp_path / "state.json"
    s = State(
        shift_to_event={"s1": "e1"},
        shift_updated_at={"s1": "2026-04-18T10:00:00+00:00"},
        last_sync="2026-04-19T12:00:00+00:00",
    )
    save_state(path, s)
    loaded = load_state(path)
    assert loaded.shift_updated_at == {"s1": "2026-04-18T10:00:00+00:00"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_state.py::test_state_roundtrip_with_updated_at -v`
Expected: FAIL — field not defined.

- [ ] **Step 3: Add field to `easyatcal/state.py`**

Modify the `State` dataclass:
```python
@dataclass
class State:
    shift_to_event: dict[str, str] = field(default_factory=dict)
    shift_updated_at: dict[str, str] = field(default_factory=dict)
    last_sync: str | None = None
```

Update `load_state` body so the constructor call includes the new field:
```python
        return State(
            shift_to_event=dict(data.get("shift_to_event", {})),
            shift_updated_at=dict(data.get("shift_updated_at", {})),
            last_sync=data.get("last_sync"),
        )
```

- [ ] **Step 4: Run all state tests to verify they pass**

Run: `pytest tests/test_state.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add easyatcal/state.py tests/test_state.py
git commit -m "feat(state): track shift_updated_at per shift"
```

---

## Task 10: ICS backend

**Files:**
- Create: `easyatcal/backends/ics.py`
- Create: `tests/backends/test_ics.py`

- [ ] **Step 1: Write failing tests**

`tests/backends/test_ics.py`:
```python
from datetime import datetime, timezone
from pathlib import Path

from easyatcal.backends.base import Changes
from easyatcal.backends.ics import IcsBackend
from easyatcal.models import Shift


def _shift(id_: str) -> Shift:
    return Shift(
        id=id_,
        start=datetime(2026, 4, 20, 9, tzinfo=timezone.utc),
        end=datetime(2026, 4, 20, 17, tzinfo=timezone.utc),
        title=f"Shift {id_}",
        location="Oslo",
        notes=None,
        updated_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
    )


def test_adds_produce_events_in_file(tmp_path: Path):
    out = tmp_path / "shifts.ics"
    backend = IcsBackend(output_path=out, known_shifts=[])
    changes = Changes(adds=[_shift("s1"), _shift("s2")])

    mapping = backend.apply(changes)

    body = out.read_text()
    assert "BEGIN:VCALENDAR" in body
    assert "SUMMARY:Shift s1" in body
    assert "SUMMARY:Shift s2" in body
    assert mapping["s1"].startswith("easyatcal-s1")
    assert mapping["s2"].startswith("easyatcal-s2")


def test_deletes_remove_events(tmp_path: Path):
    out = tmp_path / "shifts.ics"
    # First write with 2 shifts
    backend1 = IcsBackend(output_path=out, known_shifts=[])
    backend1.apply(Changes(adds=[_shift("s1"), _shift("s2")]))

    # Now apply a delete of s2's event
    backend2 = IcsBackend(
        output_path=out,
        known_shifts=[_shift("s1"), _shift("s2")],
    )
    uid_s2 = "easyatcal-s2"
    backend2.apply(Changes(deletes=[uid_s2]))

    body = out.read_text()
    assert "SUMMARY:Shift s1" in body
    assert "SUMMARY:Shift s2" not in body


def test_updates_replace_event(tmp_path: Path):
    out = tmp_path / "shifts.ics"
    s = _shift("s1")
    IcsBackend(output_path=out, known_shifts=[]).apply(Changes(adds=[s]))

    # Produce an updated shift with a new title
    s_new = Shift(
        id=s.id, start=s.start, end=s.end, title="New Title",
        location=s.location, notes=s.notes, updated_at=s.updated_at,
    )
    backend = IcsBackend(output_path=out, known_shifts=[s])
    backend.apply(Changes(updates=[(s_new, "easyatcal-s1")]))

    body = out.read_text()
    assert "SUMMARY:New Title" in body
    assert "SUMMARY:Shift s1" not in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/backends/test_ics.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `easyatcal/backends/ics.py`**

```python
from __future__ import annotations

from pathlib import Path

from icalendar import Calendar, Event

from easyatcal.backends.base import Changes
from easyatcal.models import Shift

UID_PREFIX = "easyatcal-"


def _uid_for(shift_id: str) -> str:
    return f"{UID_PREFIX}{shift_id}"


def _to_event(shift: Shift, uid: str) -> Event:
    ev = Event()
    ev.add("uid", uid)
    ev.add("summary", shift.title)
    ev.add("dtstart", shift.start)
    ev.add("dtend", shift.end)
    ev.add("last-modified", shift.updated_at)
    if shift.location:
        ev.add("location", shift.location)
    if shift.notes:
        ev.add("description", shift.notes)
    return ev


class IcsBackend:
    """File-based calendar backend that regenerates the .ics on each apply.

    `known_shifts` is the previous set of shifts the caller knows about — used
    so we can rewrite the file without losing events unrelated to the current
    change set.
    """

    def __init__(self, output_path: Path, known_shifts: list[Shift]) -> None:
        self.output_path = Path(output_path).expanduser()
        self._current: dict[str, Shift] = {s.id: s for s in known_shifts}

    def apply(self, changes: Changes) -> dict[str, str]:
        mapping: dict[str, str] = {}

        for shift in changes.adds:
            self._current[shift.id] = shift
            mapping[shift.id] = _uid_for(shift.id)

        for shift, _event_uid in changes.updates:
            self._current[shift.id] = shift
            mapping[shift.id] = _uid_for(shift.id)

        delete_uids = set(changes.deletes)
        # Map uids back to shift ids and drop them
        to_drop = [
            sid for sid in self._current
            if _uid_for(sid) in delete_uids
        ]
        for sid in to_drop:
            self._current.pop(sid, None)

        self._write()
        return mapping

    def _write(self) -> None:
        cal = Calendar()
        cal.add("prodid", "-//EasyAtCal//EN")
        cal.add("version", "2.0")
        for shift in self._current.values():
            cal.add_component(_to_event(shift, _uid_for(shift.id)))

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.output_path.with_suffix(self.output_path.suffix + ".tmp")
        tmp.write_bytes(cal.to_ical())
        tmp.replace(self.output_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/backends/test_ics.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add easyatcal/backends/ics.py tests/backends/test_ics.py
git commit -m "feat(backends): ICS file backend with add/update/delete"
```

---

## Task 11: EventKit backend (macOS only)

**Files:**
- Create: `easyatcal/backends/eventkit.py`
- Create: `tests/backends/test_eventkit.py`

- [ ] **Step 1: Write failing tests**

`tests/backends/test_eventkit.py`:
```python
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from easyatcal.backends.base import Changes
from easyatcal.models import Shift

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="EventKit backend is macOS only"
)


def _shift(id_: str) -> Shift:
    return Shift(
        id=id_,
        start=datetime(2026, 4, 20, 9, tzinfo=timezone.utc),
        end=datetime(2026, 4, 20, 17, tzinfo=timezone.utc),
        title=f"Shift {id_}",
        location=None,
        notes=None,
        updated_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
    )


@patch("easyatcal.backends.eventkit._event_store")
def test_apply_adds_creates_events(mock_store_factory):
    store = MagicMock()
    calendar = MagicMock()
    store.calendarsForEntityType_.return_value = [calendar]
    calendar.title.return_value = "Work Shifts"
    calendar.source.return_value.title.return_value = "iCloud"
    mock_store_factory.return_value = store

    created_event = MagicMock()
    created_event.calendarItemExternalIdentifier.return_value = "evt-1"

    from easyatcal.backends.eventkit import EventKitBackend

    with patch(
        "easyatcal.backends.eventkit._new_event", return_value=created_event
    ):
        backend = EventKitBackend(
            calendar_name="Work Shifts", calendar_source="iCloud"
        )
        mapping = backend.apply(Changes(adds=[_shift("s1")]))

    assert mapping == {"s1": "evt-1"}
    store.saveEvent_span_error_.assert_called()


@patch("easyatcal.backends.eventkit._event_store")
def test_apply_deletes_removes_events(mock_store_factory):
    store = MagicMock()
    calendar = MagicMock()
    calendar.title.return_value = "Work Shifts"
    calendar.source.return_value.title.return_value = "iCloud"
    store.calendarsForEntityType_.return_value = [calendar]

    existing = MagicMock()
    existing.calendarItemExternalIdentifier.return_value = "evt-1"
    store.calendarItemWithIdentifier_.return_value = existing
    mock_store_factory.return_value = store

    from easyatcal.backends.eventkit import EventKitBackend
    backend = EventKitBackend(
        calendar_name="Work Shifts", calendar_source="iCloud"
    )

    backend.apply(Changes(deletes=["evt-1"]))

    store.removeEvent_span_error_.assert_called()
```

- [ ] **Step 2: Run tests to verify they fail (macOS only)**

Run: `pytest tests/backends/test_eventkit.py -v`
Expected on macOS: FAIL — module not found. On Linux: skipped.

- [ ] **Step 3: Implement `easyatcal/backends/eventkit.py`**

```python
"""macOS EventKit calendar backend.

Only usable on macOS. Requires `pyobjc-framework-EventKit` (install the
`eventkit` extra).
"""
from __future__ import annotations

import sys
from typing import Any

from easyatcal.backends.base import Changes
from easyatcal.models import Shift


class EventKitUnavailableError(RuntimeError):
    pass


class EventKitPermissionError(RuntimeError):
    pass


def _import_eventkit():  # pragma: no cover — platform guard
    if sys.platform != "darwin":
        raise EventKitUnavailableError("EventKit backend requires macOS")
    try:
        import EventKit  # type: ignore[import-not-found]
    except ImportError as e:
        raise EventKitUnavailableError(
            "pyobjc-framework-EventKit not installed; "
            "pip install 'easyatcal[eventkit]'"
        ) from e
    return EventKit


def _event_store() -> Any:  # pragma: no cover — exercised via mocks in tests
    EventKit = _import_eventkit()
    store = EventKit.EKEventStore.alloc().init()
    # Request permission (synchronous wait via semaphore).
    import Foundation  # type: ignore[import-not-found]
    from threading import Event as _E
    granted = {"ok": False, "err": None}
    done = _E()

    def _cb(ok, err):
        granted["ok"] = bool(ok)
        granted["err"] = err
        done.set()

    try:
        # macOS 14+
        store.requestFullAccessToEventsWithCompletion_(_cb)
    except AttributeError:
        store.requestAccessToEntityType_completion_(0, _cb)  # 0 = EKEntityTypeEvent

    done.wait(timeout=30)
    if not granted["ok"]:
        raise EventKitPermissionError(
            "Calendar access denied — grant access in System Settings → "
            "Privacy & Security → Calendars."
        )
    return store


def _new_event(store, calendar, shift: Shift):  # pragma: no cover
    EventKit = _import_eventkit()
    import Foundation  # type: ignore[import-not-found]

    event = EventKit.EKEvent.eventWithEventStore_(store)
    event.setCalendar_(calendar)
    event.setTitle_(shift.title)
    event.setStartDate_(
        Foundation.NSDate.dateWithTimeIntervalSince1970_(shift.start.timestamp())
    )
    event.setEndDate_(
        Foundation.NSDate.dateWithTimeIntervalSince1970_(shift.end.timestamp())
    )
    if shift.location:
        event.setLocation_(shift.location)
    if shift.notes:
        event.setNotes_(shift.notes)
    return event


class EventKitBackend:
    def __init__(self, calendar_name: str, calendar_source: str) -> None:
        self.calendar_name = calendar_name
        self.calendar_source = calendar_source
        self._store = _event_store()
        self._calendar = self._resolve_calendar()

    def _resolve_calendar(self):
        calendars = self._store.calendarsForEntityType_(0)
        for cal in calendars:
            if (
                cal.title() == self.calendar_name
                and cal.source().title() == self.calendar_source
            ):
                return cal
        raise RuntimeError(
            f"Calendar {self.calendar_name!r} not found in source "
            f"{self.calendar_source!r}. Create it in Calendar.app first."
        )

    def apply(self, changes: Changes) -> dict[str, str]:
        mapping: dict[str, str] = {}

        for shift in changes.adds:
            event = _new_event(self._store, self._calendar, shift)
            err = None
            self._store.saveEvent_span_error_(event, 0, err)  # 0 = EKSpanThisEvent
            mapping[shift.id] = event.calendarItemExternalIdentifier()

        for shift, event_uid in changes.updates:
            existing = self._store.calendarItemWithIdentifier_(event_uid)
            if existing is None:
                # Fall through to recreate
                event = _new_event(self._store, self._calendar, shift)
                err = None
                self._store.saveEvent_span_error_(event, 0, err)
                mapping[shift.id] = event.calendarItemExternalIdentifier()
                continue
            existing.setTitle_(shift.title)
            # Re-set start/end/location/notes
            import Foundation  # type: ignore[import-not-found]
            existing.setStartDate_(
                Foundation.NSDate.dateWithTimeIntervalSince1970_(shift.start.timestamp())
            )
            existing.setEndDate_(
                Foundation.NSDate.dateWithTimeIntervalSince1970_(shift.end.timestamp())
            )
            if shift.location is not None:
                existing.setLocation_(shift.location)
            if shift.notes is not None:
                existing.setNotes_(shift.notes)
            err = None
            self._store.saveEvent_span_error_(existing, 0, err)
            mapping[shift.id] = event_uid

        for event_uid in changes.deletes:
            existing = self._store.calendarItemWithIdentifier_(event_uid)
            if existing is None:
                continue
            err = None
            self._store.removeEvent_span_error_(existing, 0, err)

        return mapping
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/backends/test_eventkit.py -v`
Expected on macOS: 2 passed. On Linux: skipped.

- [ ] **Step 5: Commit**

```bash
git add easyatcal/backends/eventkit.py tests/backends/test_eventkit.py
git commit -m "feat(backends): macOS EventKit backend via pyobjc"
```

---

## Task 12: Orchestrator (ties API + sync + state + backend together)

**Files:**
- Create: `easyatcal/orchestrator.py`
- Create: `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing test**

`tests/test_orchestrator.py`:
```python
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from easyatcal.backends.base import Changes
from easyatcal.models import Shift
from easyatcal.orchestrator import run_sync
from easyatcal.state import load_state


def _shift(id_: str) -> Shift:
    return Shift(
        id=id_,
        start=datetime(2026, 4, 20, 9, tzinfo=timezone.utc),
        end=datetime(2026, 4, 20, 17, tzinfo=timezone.utc),
        title=f"t{id_}",
        location=None,
        notes=None,
        updated_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
    )


def test_run_sync_applies_changes_and_persists_state(tmp_path: Path):
    state_path = tmp_path / "state.json"

    api = MagicMock()
    api.fetch_shifts.return_value = [_shift("s1"), _shift("s2")]

    backend = MagicMock()
    backend.apply.return_value = {"s1": "evt-1", "s2": "evt-2"}

    run_sync(
        api=api,
        backend=backend,
        state_path=state_path,
        lookback_days=1,
        lookahead_days=1,
        now=datetime(2026, 4, 19, 12, tzinfo=timezone.utc),
    )

    # backend.apply was called with 2 adds
    changes = backend.apply.call_args.args[0]
    assert isinstance(changes, Changes)
    assert [s.id for s in changes.adds] == ["s1", "s2"]

    # State persisted
    saved = load_state(state_path)
    assert saved.shift_to_event == {"s1": "evt-1", "s2": "evt-2"}
    assert saved.shift_updated_at["s1"] == "2026-04-18T00:00:00+00:00"
    assert saved.last_sync == "2026-04-19T12:00:00+00:00"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_orchestrator.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `easyatcal/orchestrator.py`**

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from easyatcal.backends.base import CalendarBackend
from easyatcal.models import Shift
from easyatcal.state import State, load_state, save_state
from easyatcal.sync import compute_changes


class ShiftFetcher(Protocol):
    def fetch_shifts(self, from_date, to_date) -> list[Shift]: ...


def run_sync(
    api: ShiftFetcher,
    backend: CalendarBackend,
    state_path: Path,
    lookback_days: int,
    lookahead_days: int,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(timezone.utc)
    from_date = (now - timedelta(days=lookback_days)).date()
    to_date = (now + timedelta(days=lookahead_days)).date()

    remote_shifts = api.fetch_shifts(from_date=from_date, to_date=to_date)
    state = load_state(state_path)
    changes = compute_changes(
        remote_shifts, state, known_updated_at=state.shift_updated_at
    )
    mapping = backend.apply(changes)

    # Merge new mapping into state; prune deleted entries.
    new_shift_to_event = dict(state.shift_to_event)
    new_updated_at = dict(state.shift_updated_at)
    for shift_id, event_uid in mapping.items():
        new_shift_to_event[shift_id] = event_uid
    for shift in remote_shifts:
        new_updated_at[shift.id] = shift.updated_at.isoformat()

    remote_ids = {s.id for s in remote_shifts}
    new_shift_to_event = {
        sid: evt for sid, evt in new_shift_to_event.items() if sid in remote_ids
    }
    new_updated_at = {
        sid: ts for sid, ts in new_updated_at.items() if sid in remote_ids
    }

    save_state(
        state_path,
        State(
            shift_to_event=new_shift_to_event,
            shift_updated_at=new_updated_at,
            last_sync=now.isoformat(),
        ),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_orchestrator.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add easyatcal/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): tie api + sync + backend + state together"
```

---

## Task 13: CLI — `config init` and `config show`

**Files:**
- Create: `easyatcal/cli.py`
- Create: `easyatcal/paths.py`
- Create: `tests/test_cli_config.py`

- [ ] **Step 1: Create helper for platform paths**

`easyatcal/paths.py`:
```python
from __future__ import annotations

from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir, user_data_dir

APP = "easyatcal"


def config_path() -> Path:
    return Path(user_config_dir(APP)) / "config.yaml"


def state_path() -> Path:
    return Path(user_data_dir(APP)) / "state.json"


def token_cache_path() -> Path:
    return Path(user_cache_dir(APP)) / "token.json"


def log_path() -> Path:
    return Path(user_data_dir(APP)) / "logs" / "eaw-sync.log"
```

- [ ] **Step 2: Write failing tests**

`tests/test_cli_config.py`:
```python
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from easyatcal.cli import app

runner = CliRunner()


def test_config_init_creates_file(tmp_path: Path):
    target = tmp_path / "config.yaml"
    with patch("easyatcal.cli.config_path", return_value=target):
        result = runner.invoke(app, ["config", "init"])

    assert result.exit_code == 0
    assert target.exists()
    assert "easyatwork:" in target.read_text()


def test_config_init_does_not_overwrite(tmp_path: Path):
    target = tmp_path / "config.yaml"
    target.write_text("existing: yes\n")
    with patch("easyatcal.cli.config_path", return_value=target):
        result = runner.invoke(app, ["config", "init"])

    assert result.exit_code != 0
    assert "already exists" in result.stdout


def test_config_show_redacts_secret(tmp_path: Path):
    target = tmp_path / "config.yaml"
    target.write_text(
        "easyatwork:\n"
        "  auth_mode: client\n"
        "  client_id: cid\n"
        "  client_secret: supersecret\n"
        "  base_url: https://api.easyatwork.com\n"
        "backend: ics\n"
    )
    with patch("easyatcal.cli.config_path", return_value=target):
        result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0
    assert "supersecret" not in result.stdout
    assert "***" in result.stdout
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_cli_config.py -v`
Expected: FAIL — cli module missing.

- [ ] **Step 4: Implement `easyatcal/cli.py`**

```python
from __future__ import annotations

import shutil
from pathlib import Path

import typer
import yaml

from easyatcal.config import load_config
from easyatcal.paths import config_path

app = typer.Typer(help="EasyAtCal — sync easy@work shifts to Apple Calendar.")
config_app = typer.Typer(help="Manage the config file.")
app.add_typer(config_app, name="config")

EXAMPLE_CONFIG = Path(__file__).parent.parent / "config.example.yaml"


@config_app.command("init")
def config_init() -> None:
    """Scaffold a config file at the user config dir."""
    target = config_path()
    if target.exists():
        typer.echo(f"Config already exists at {target}", err=True)
        raise typer.Exit(code=1)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(EXAMPLE_CONFIG, target)
    typer.echo(f"Wrote {target}. Edit it before running `eaw-sync sync`.")


@config_app.command("show")
def config_show() -> None:
    """Print the effective config with secrets redacted."""
    cfg = load_config(config_path())
    dumped = cfg.model_dump()
    dumped["easyatwork"]["client_secret"] = "***"
    typer.echo(yaml.safe_dump(dumped, sort_keys=False))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_cli_config.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add easyatcal/cli.py easyatcal/paths.py tests/test_cli_config.py
git commit -m "feat(cli): config init and config show with secret redaction"
```

---

## Task 14: CLI — `sync` and `watch`

**Files:**
- Modify: `easyatcal/cli.py`
- Create: `tests/test_cli_sync.py`

- [ ] **Step 1: Write failing tests**

`tests/test_cli_sync.py`:
```python
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from easyatcal.cli import app

runner = CliRunner()


@patch("easyatcal.cli.run_sync")
@patch("easyatcal.cli._build_backend")
@patch("easyatcal.cli._build_api_client")
@patch("easyatcal.cli.load_config")
def test_sync_once_invokes_run_sync(mock_cfg, mock_api, mock_back, mock_run, tmp_path):
    mock_cfg.return_value = MagicMock(
        sync=MagicMock(lookback_days=7, lookahead_days=90),
    )
    result = runner.invoke(app, ["sync"])

    assert result.exit_code == 0
    mock_run.assert_called_once()


@patch("easyatcal.cli.time.sleep", side_effect=KeyboardInterrupt)
@patch("easyatcal.cli.run_sync")
@patch("easyatcal.cli._build_backend")
@patch("easyatcal.cli._build_api_client")
@patch("easyatcal.cli.load_config")
def test_watch_loops_until_interrupt(mock_cfg, mock_api, mock_back, mock_run, mock_sleep):
    mock_cfg.return_value = MagicMock(
        sync=MagicMock(lookback_days=7, lookahead_days=90),
    )
    result = runner.invoke(app, ["watch", "--interval-seconds", "60"])

    # Should run once, then be interrupted by the patched sleep
    assert mock_run.call_count == 1
    assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_sync.py -v`
Expected: FAIL — `sync` / `watch` commands not registered.

- [ ] **Step 3: Extend `easyatcal/cli.py`**

Add to `easyatcal/cli.py` (after existing imports):

```python
import time

from easyatcal.api import EawClient
from easyatcal.backends.ics import IcsBackend
from easyatcal.orchestrator import run_sync
from easyatcal.paths import state_path, token_cache_path
from easyatcal.state import load_state


def _build_api_client(cfg):
    return EawClient(
        client_id=cfg.easyatwork.client_id,
        client_secret=cfg.easyatwork.client_secret,
        base_url=cfg.easyatwork.base_url,
        token_cache=token_cache_path(),
    )


def _build_backend(cfg):
    if cfg.backend == "ics":
        state = load_state(state_path())
        # Known shifts list is empty here; IcsBackend rewrites from current
        # in-memory map on each apply, so the next run re-uses state anyway.
        return IcsBackend(
            output_path=Path(cfg.backends.ics.output_path).expanduser(),
            known_shifts=[],
        )
    if cfg.backend == "eventkit":
        from easyatcal.backends.eventkit import EventKitBackend
        return EventKitBackend(
            calendar_name=cfg.backends.eventkit.calendar_name,
            calendar_source=cfg.backends.eventkit.calendar_source,
        )
    raise RuntimeError(f"Unknown backend: {cfg.backend}")


@app.command("sync")
def sync_cmd() -> None:
    """Run one sync pass and exit."""
    cfg = load_config(config_path())
    api = _build_api_client(cfg)
    backend = _build_backend(cfg)
    run_sync(
        api=api,
        backend=backend,
        state_path=state_path(),
        lookback_days=cfg.sync.lookback_days,
        lookahead_days=cfg.sync.lookahead_days,
    )
    typer.echo("Sync complete.")


@app.command("watch")
def watch_cmd(
    interval_seconds: int = typer.Option(
        900, "--interval-seconds", help="Seconds between sync passes."
    ),
) -> None:
    """Run sync on a loop until Ctrl-C."""
    cfg = load_config(config_path())
    api = _build_api_client(cfg)
    backend = _build_backend(cfg)
    try:
        while True:
            run_sync(
                api=api,
                backend=backend,
                state_path=state_path(),
                lookback_days=cfg.sync.lookback_days,
                lookahead_days=cfg.sync.lookahead_days,
            )
            typer.echo(f"Sleeping {interval_seconds}s…")
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        typer.echo("\nStopped.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_sync.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add easyatcal/cli.py tests/test_cli_sync.py
git commit -m "feat(cli): sync one-shot and watch daemon commands"
```

---

## Task 15: CLI — `auth test`

**Files:**
- Modify: `easyatcal/cli.py`
- Create: `tests/test_cli_auth.py`

- [ ] **Step 1: Write failing test**

`tests/test_cli_auth.py`:
```python
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from easyatcal.cli import app

runner = CliRunner()


@patch("easyatcal.cli._build_api_client")
@patch("easyatcal.cli.load_config")
def test_auth_test_success(mock_cfg, mock_build):
    api = MagicMock()
    api.authenticate.return_value = "tok"
    mock_build.return_value = api
    mock_cfg.return_value = MagicMock()

    result = runner.invoke(app, ["auth", "test"])
    assert result.exit_code == 0
    assert "OK" in result.stdout


@patch("easyatcal.cli._build_api_client")
@patch("easyatcal.cli.load_config")
def test_auth_test_failure(mock_cfg, mock_build):
    from easyatcal.api import AuthError
    api = MagicMock()
    api.authenticate.side_effect = AuthError("bad creds")
    mock_build.return_value = api
    mock_cfg.return_value = MagicMock()

    result = runner.invoke(app, ["auth", "test"])
    assert result.exit_code == 2
    assert "bad creds" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_auth.py -v`
Expected: FAIL — `auth test` not registered.

- [ ] **Step 3: Add `auth test` to `easyatcal/cli.py`**

Append:
```python
auth_app = typer.Typer(help="Credential checks.")
app.add_typer(auth_app, name="auth")


@auth_app.command("test")
def auth_test() -> None:
    """Verify that the configured credentials can obtain a token."""
    from easyatcal.api import AuthError

    cfg = load_config(config_path())
    api = _build_api_client(cfg)
    try:
        api.authenticate()
    except AuthError as e:
        typer.echo(f"Auth failed: {e}")
        raise typer.Exit(code=2)
    typer.echo("OK — credentials work.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_auth.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add easyatcal/cli.py tests/test_cli_auth.py
git commit -m "feat(cli): auth test subcommand"
```

---

## Task 16: Logging setup

**Files:**
- Create: `easyatcal/logging_setup.py`
- Modify: `easyatcal/cli.py` (call setup at entry)
- Create: `tests/test_logging_setup.py`

- [ ] **Step 1: Write failing test**

`tests/test_logging_setup.py`:
```python
import logging
from pathlib import Path

from easyatcal.logging_setup import configure_logging


def test_configure_logging_writes_to_file(tmp_path: Path):
    log_file = tmp_path / "eaw-sync.log"
    configure_logging(level="INFO", log_file=log_file)

    logging.getLogger("easyatcal").info("hello world")

    # Force handler flush
    for h in logging.getLogger().handlers:
        h.flush()

    assert log_file.exists()
    assert "hello world" in log_file.read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_logging_setup.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `easyatcal/logging_setup.py`**

```python
from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def configure_logging(level: str, log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    # Reset any prior handlers (idempotent across watch-mode iterations)
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(level)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_h = TimedRotatingFileHandler(
        log_file, when="midnight", backupCount=7, encoding="utf-8"
    )
    file_h.setFormatter(fmt)
    root.addHandler(file_h)

    console_h = logging.StreamHandler()
    console_h.setFormatter(fmt)
    root.addHandler(console_h)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_logging_setup.py -v`
Expected: 1 passed.

- [ ] **Step 5: Wire into CLI**

At the top of `easyatcal/cli.py`, add:

```python
from easyatcal.logging_setup import configure_logging
from easyatcal.paths import log_path
```

Inside each of `sync_cmd`, `watch_cmd`, `auth_test`, insert as the very first line after loading the config:

```python
configure_logging(level=cfg.logging.level, log_file=log_path())
```

- [ ] **Step 6: Re-run full test suite**

Run: `pytest`
Expected: all tests pass (EventKit tests skipped on non-macOS).

- [ ] **Step 7: Commit**

```bash
git add easyatcal/logging_setup.py easyatcal/cli.py tests/test_logging_setup.py
git commit -m "feat(logging): rotating file + console handlers"
```

---

## Task 17: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create CI workflow**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        python: ["3.11", "3.12"]
        os: [ubuntu-latest, macos-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
          cache: pip
      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install -e '.[dev]'
      - name: Install eventkit extra (macOS only)
        if: runner.os == 'macOS'
        run: pip install -e '.[eventkit]'
      - name: Test
        run: pytest --cov=easyatcal
```

- [ ] **Step 2: Run pytest locally one more time before commit**

Run: `pytest --cov=easyatcal`
Expected: all pass, coverage reported.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: test matrix on Linux + macOS, Python 3.11 and 3.12"
```

---

## Task 18: End-to-end smoke test

**Files:**
- Create: `tests/test_e2e_ics.py`

- [ ] **Step 1: Write the e2e test**

`tests/test_e2e_ics.py`:
```python
"""End-to-end test using the ICS backend and a mocked easy@work API."""
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import responses

from easyatcal.api import EawClient
from easyatcal.backends.ics import IcsBackend
from easyatcal.orchestrator import run_sync


@responses.activate
def test_end_to_end_ics(tmp_path: Path):
    # Seed token cache so auth is cheap
    token_cache = tmp_path / "token.json"
    token_cache.write_text(
        '{"access_token":"tok","expires_at":"2099-01-01T00:00:00+00:00"}'
    )
    responses.add(
        responses.GET,
        "https://api.easyatwork.com/v1/shifts",
        json={
            "data": [
                {
                    "id": "s1",
                    "start": "2026-04-20T09:00:00+00:00",
                    "end": "2026-04-20T17:00:00+00:00",
                    "title": "Morning", "location": "Oslo", "notes": None,
                    "updated_at": "2026-04-18T10:00:00+00:00",
                }
            ],
            "next": None,
        },
        status=200,
    )
    api = EawClient(
        client_id="cid", client_secret="csecret",
        base_url="https://api.easyatwork.com", token_cache=token_cache,
    )
    ics_out = tmp_path / "shifts.ics"
    backend = IcsBackend(output_path=ics_out, known_shifts=[])

    run_sync(
        api=api,
        backend=backend,
        state_path=tmp_path / "state.json",
        lookback_days=1,
        lookahead_days=7,
    )

    body = ics_out.read_text()
    assert "SUMMARY:Morning" in body
    assert "LOCATION:Oslo" in body
    # State file was written
    assert (tmp_path / "state.json").exists()
```

- [ ] **Step 2: Run the e2e test**

Run: `pytest tests/test_e2e_ics.py -v`
Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_e2e_ics.py
git commit -m "test(e2e): ICS backend end-to-end with mocked API"
```

---

## Task 19: Push to origin

- [ ] **Step 1: Push all commits**

Run: `git push origin main`
Expected: branch updated.

- [ ] **Step 2: Tag v0.1.0**

```bash
git tag -a v0.1.0 -m "Initial release: easy@work → Apple Calendar sync"
git push origin v0.1.0
```

---

## Self-review notes

- Spec coverage: every section of the spec maps to a task (scaffold → T1, models → T2, config → T3, state → T4/T9, api → T5/T6, backend base → T7, sync → T8, ics → T10, eventkit → T11, orchestrator → T12, cli commands → T13/T14/T15, error handling → T5/T6/T11/T15 (exit codes) + T16 (logging), testing → every task has TDD, CI → T17, e2e → T18, security → T1 gitignore + T5 token cache 0600 + T13 redaction).
- Placeholder scan: no TBD/TODO. Every step has concrete code or a concrete command.
- Type consistency: `Shift` fields, `Changes` fields, `State` fields, `EawClient` constructor signature, and CLI command names are used consistently across tasks.
