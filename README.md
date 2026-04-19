# EasyAtCal

[![CI](https://github.com/Ailcope/EasyAtCal/actions/workflows/ci.yml/badge.svg)](https://github.com/Ailcope/EasyAtCal/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/easyatcal.svg)](https://pypi.org/project/easyatcal/)
[![Python](https://img.shields.io/pypi/pyversions/easyatcal.svg)](https://pypi.org/project/easyatcal/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

One-way sync of [easy@work](https://www.easyatwork.com) shifts into Apple
Calendar. Run it on a Mac, iCloud fans out to iPhone/iPad/Watch.

- Read-only against easy@work; never writes back.
- Two backends: native macOS **EventKit** (recommended) or portable **ICS** file.
- State-tracked: unchanged shifts are skipped; edits and deletions propagate.
- Open-source friendly: code is public, your `config.yaml` / `state.json` stay
  local (see `.gitignore`).

## Install

```bash
pip install easyatcal                   # core + ICS backend
pip install 'easyatcal[eventkit]'       # add macOS EventKit backend
```

Python 3.11+. macOS for EventKit; any OS for ICS.

## Quickstart

```bash
eaw-sync config init                    # scaffold config
$EDITOR ~/.config/easyatcal/config.yaml
eaw-sync doctor                         # check config + auth + backend
eaw-sync sync                           # one shot
eaw-sync watch --interval-seconds 900   # loop every 15 min
```

## Configure

Minimal `config.yaml`:

```yaml
easyatwork:
  client_id: "REPLACE_ME"
  client_secret: "REPLACE_ME"     # or export EAW_CLIENT_SECRET
  base_url: "https://api.easyatwork.com"

sync:
  lookback_days: 7
  lookahead_days: 90

backend: eventkit                  # or "ics"

backends:
  eventkit:
    calendar_name: "Work Shifts"   # must exist in Calendar.app
    calendar_source: "iCloud"
  ics:
    output_path: "~/Documents/easyatwork-shifts.ics"

logging:
  level: INFO
```

Env overrides: any `easyatwork.*` field is overridable via `EAW_*` (e.g.
`EAW_CLIENT_SECRET`).

## Backends

**EventKit (macOS).** Writes directly to a dedicated calendar in Calendar.app.
Create the calendar manually once — e.g. "Work Shifts" under "iCloud" — then
point `calendar_name` / `calendar_source` at it. First run triggers a Calendar
permission prompt; grant access in *System Settings → Privacy & Security →
Calendars*.

**ICS.** Writes a single `.ics` file. Subscribe to it from Calendar.app (or any
calendar client) via `File → New Calendar Subscription`. Portable, no
permissions needed.

## Commands

| Command | What |
|---------|------|
| `eaw-sync config init` | Scaffold config file. |
| `eaw-sync config show` | Print effective config (secrets redacted). |
| `eaw-sync auth test` | Verify credentials can obtain a token. |
| `eaw-sync doctor` | Full preflight: config loads, auth works, backend reachable. |
| `eaw-sync state show` | Print local state path, tracked-shift count, last sync. |
| `eaw-sync sync [--dry-run]` | Run one sync pass and exit. |
| `eaw-sync watch --interval-seconds N` | Loop until Ctrl-C / SIGTERM. |

Global flag: `--config-path PATH` overrides the default config location.

### Exit codes (`sync`)

| Code | Meaning |
|------|---------|
| 0 | All changes applied. |
| 1 | Partial failure — some changes applied, state persisted, backend errored. |
| 2 | Fatal — config/auth/network failed before any change was written. |

### Shell completions

```bash
eaw-sync --install-completion        # bash / zsh / fish
```

## Troubleshooting

- **"Calendar 'Work Shifts' not found"** — create it in Calendar.app first;
  source name must match (`iCloud`, `On My Mac`, etc).
- **Calendar permission denied** — System Settings → Privacy & Security →
  Calendars → enable for your terminal / launchd agent.
- **`auth failed`** — run `eaw-sync doctor`, check `EAW_CLIENT_SECRET`, confirm
  `base_url`.
- **Stale events after delete** — state entries auto-prune once the backend
  confirms the delete. Corrupt `state.json` is quarantined and rebuilt.

## Auto-run on macOS

A sample launchd plist is in `examples/launchd/com.easyatcal.watch.plist`.
Load with:

```bash
cp examples/launchd/com.easyatcal.watch.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.easyatcal.watch.plist
```

## Design

- `docs/superpowers/specs/2026-04-19-easyatcal-design.md` — full design.
- `docs/superpowers/plans/2026-04-19-easyatcal-implementation.md` — build plan.

## License

MIT — see `LICENSE`.
