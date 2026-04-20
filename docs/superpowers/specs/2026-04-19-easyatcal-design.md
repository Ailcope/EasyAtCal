# EasyAtCal — Design Spec

**Date:** 2026-04-19
**Status:** Draft
**Author:** Ailcope

## Purpose

One-way sync of shifts from [easy@work](https://www.easyatwork.com) into Apple Calendar. The user's Mac runs the sync; iCloud propagates events to all their Apple devices (iPhone, iPad, Watch). The project is open-source and cross-platform-friendly (the core runs anywhere Python runs; the Apple-specific backend is pluggable).

## Goals

- Fetch shifts from the easy@work REST API.
- Create, update, and delete corresponding events in the user's Apple Calendar (via EventKit on macOS) or in a portable `.ics` file (any OS).
- Run manually (`--once`) or as a daemon (`--watch`).
- Keep user credentials and shift data out of the public repo.
- Be easily installable: `pip install easyatcal` exposes an `eaw-sync` CLI.

## Non-Goals

- Bi-directional sync (edits in Apple Calendar do not flow back to easy@work).
- A GUI.
- Hosting a shared `.ics` feed for others.
- Supporting non-Apple calendar destinations in v1 (CalDAV/Google reserved for future).

## Architecture

Single Python package with pluggable calendar backends.

```
[easy@work API] → [Python core] → [backend]
                      ↑               ├── eventkit (macOS → iCloud → all devices)
                   config.yaml        └── ics (portable file)
                  (gitignored)
```

### Repo layout

```
EasyAtCal/
├── README.md
├── pyproject.toml
├── .gitignore               # excludes config.yaml, .env, *.ics, state.json
├── config.example.yaml
├── easyatcal/
│   ├── __init__.py
│   ├── api.py               # easy@work REST client
│   ├── models.py            # Shift dataclass
│   ├── sync.py              # diff + orchestration
│   ├── config.py            # YAML + env loader
│   ├── cli.py               # typer entrypoint
│   └── backends/
│       ├── __init__.py
│       ├── base.py          # CalendarBackend interface
│       ├── ics.py           # writes .ics file
│       └── eventkit.py      # pyobjc EKEventStore
└── tests/
    ├── test_api.py
    ├── test_sync.py
    ├── test_cli.py
    └── backends/
        ├── test_ics.py
        └── test_eventkit.py
```

## Components

### `api.py` — easy@work client
- JWT Bearer token auth via UI automation. Playwright headless login extracts JWT from `localStorage`. Replays token against `<region>.api.easyatwork.com/customers/{cid}/employees/{eid}/shifts`.
- Caches access token at `~/.cache/easyatcal/token.json`.
- `fetch_shifts(user_id, from_date, to_date) -> list[Shift]`.
- Handles pagination.
- Retries on 429/5xx with exponential backoff (max 5 attempts).

### `models.py`
```python
@dataclass
class Shift:
    id: str                  # stable id from easy@work
    start: datetime          # tz-aware
    end: datetime
    title: str
    location: str | None
    notes: str | None
    updated_at: datetime     # used to detect server-side edits
```

### `sync.py`
- Reads local state (`~/.local/share/easyatcal/state.json`: `{shift_id: event_uid}`).
- Computes `{add, update, delete}` diff between remote shifts and state.
- `update` triggered when `shift.updated_at` changed since last sync.
- `delete` triggered for shifts present in state but absent from remote window.
- Calls `backend.apply(changes)` then persists new state.

### `backends/base.py`
```python
class CalendarBackend(Protocol):
    def apply(self, adds: list[Shift], updates: list[tuple[Shift, str]],
              deletes: list[str]) -> dict[str, str]: ...
    # Returns new mapping shift_id -> event_uid for adds/updates.
```

### `backends/ics.py`
- Uses `icalendar` lib to regenerate a full `.ics` file each sync.
- Output path configurable; default `~/Documents/easyatwork-shifts.ics`.
- Stable `UID` derived from `shift.id` so re-imports update in place.

### `backends/eventkit.py`
- macOS-only; import guarded.
- Uses `pyobjc-framework-EventKit` to access `EKEventStore`.
- Target calendar: configurable name + source (`iCloud`). Creates calendar if missing.
- Requests `EKAuthorizationStatusFullAccess` permission on first run.
- Mapping: `Shift.id` → `EKEvent.externalIdentifier` (stored) + `EKEvent.calendarItemExternalIdentifier` (for lookup).

### `cli.py`
`typer` app. Commands:
- `eaw-sync sync` — one-shot sync, exits after run.
- `eaw-sync watch --interval 15m` — daemon loop.
- `eaw-sync config init` — scaffold `~/.config/easyatcal/config.yaml` from template.
- `eaw-sync config show` — print effective config (redact secrets).
- `eaw-sync auth test` — verify creds + list calendars.

## Data flow

1. CLI parses args → loads `config.yaml` + env overrides.
2. `api.authenticate()` → access token (cached).
3. `api.fetch_shifts(from=today - lookback, to=today + lookahead)` → `list[Shift]`.
4. `sync.diff(remote, state)` → `{adds, updates, deletes}`.
5. `backend.apply(changes)` → mutates calendar, returns event-id mapping.
6. State persisted atomically (write-temp-then-rename).
7. Logs flushed to `~/.local/share/easyatcal/logs/eaw-sync.log`.

## Config schema

`~/.config/easyatcal/config.yaml` (gitignored; `config.example.yaml` committed):

```yaml
easyatwork:
  api_url: "https://eu-west-3.api.easyatwork.com"
  customer_id: 0
  employee_id: 0
  ui_version: "v3.0.0"
  
  # Auth configuration for Playwright UI login
  email: "user@example.com"
  password: "..."              # env EAW_PASSWORD overrides
  login_url: "https://app.easyatwork.com/login"
  app_url: "https://app.easyatwork.com"
  login_selectors:
    email_input: "input[type='email']"
    password_input: "input[type='password']"
    submit_button: "button[type='submit']"
    post_login_wait: ".dashboard"
  headless: true
  login_timeout_ms: 30000

sync:
  lookback_days: 7
  lookahead_days: 90

backend: eventkit              # or "ics"

backends:
  eventkit:
    calendar_name: "Work Shifts"
    calendar_source: "iCloud"
  ics:
    output_path: "~/Documents/easyatwork-shifts.ics"

logging:
  level: INFO
```

Env vars override YAML: `EAW_PASSWORD`.

## Error handling

| Failure | Behavior |
|---|---|
| Auth failure | Exit 2, message "check credentials". |
| Rate limit (429) | Exponential backoff, max 5 retries. |
| Network down (one-shot) | Exit 3. |
| Network down (watch) | Log warning, retry at next interval. |
| EventKit permission denied | Exit 4 + instructions to grant access in System Settings → Privacy. |
| Malformed shift | Log warning, skip shift, continue. |
| Corrupt state file | Back up to `state.json.bak`, reset, do full re-sync. |

Logs rotate daily, retained 7 days.

## Testing

- `test_api.py`: mock HTTP with `responses` — covers auth, fetch, pagination, retry, rate-limit.
- `test_sync.py`: unit tests on diff matrix (add/update/delete permutations, tz edge cases).
- `test_backends/test_ics.py`: snapshot-compare generated `.ics` against fixture.
- `test_backends/test_eventkit.py`: skipped on non-macOS; uses mock `EKEventStore` otherwise.
- `test_cli.py`: `typer.testing.CliRunner` against each subcommand.
- CI: GitHub Actions, matrix Python 3.11/3.12 × {Linux, macOS}.

## Open questions / deferred

- Tenant-specific IDs required (`customer_id`, `employee_id`), which the user must extract from DevTools before first sync or the URL constructor raises an error.
- Whether to support multi-user sync in v1 — deferred; single user only.
- Whether to publish to PyPI — yes once v0.1 ships, but not blocking first release.

## Security

- `config.yaml` lives outside the repo (`~/.config/easyatcal/`). `.gitignore` in the repo also blocks any stray copy.
- Secrets can be provided via environment variables instead of YAML for CI/container use.
- Token cache file permissions set to `0600`.
- No shift data ever written to the repo.
