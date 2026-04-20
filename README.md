# EasyAtCal

[![CI](https://github.com/Ailcope/EasyAtCal/actions/workflows/ci.yml/badge.svg)](https://github.com/Ailcope/EasyAtCal/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen.svg)](https://github.com/Ailcope/EasyAtCal)
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
pip install 'easyatcal[eventkit]'       # + macOS EventKit backend
pip install 'easyatcal[playwright]'     # + headless-browser login (default auth)
playwright install chromium             # one-time ~200 MB browser download
```

Python 3.11+. macOS for EventKit; any OS for ICS.

## Authentication

easy@work has no public developer API. The default auth mode (`user`) logs
a headless Chromium instance into `app.easyatwork.com` with your real
credentials, captures the session cookies, and reuses them for all
subsequent HTTP calls. Your password is never stored on disk — it lives
only in the `EAW_PASSWORD` env var (or is prompted interactively).

```bash
EAW_PASSWORD='...' eaw-sync login       # persists cookies; do once, or when expired
eaw-sync logout                          # wipe cookies
```

Cookies are written to `~/.cache/easyatcal/session.json` (0600) via
Playwright's `storage_state`.

An alternate `client` mode (OAuth client_credentials) is scaffolded in
the code for forward-compat — if easy@work ever publishes an API, flip
`auth_mode: client` and fill in the OAuth creds.

## Quickstart

```bash
eaw-sync config init                    # scaffold config
$EDITOR ~/.config/easyatcal/config.yaml # set email, app_url, shifts_endpoint
EAW_PASSWORD='...' eaw-sync login       # one-time headless login
eaw-sync doctor                         # check config + session + backend
eaw-sync sync                           # one shot
eaw-sync watch --interval-seconds 900   # loop every 15 min
```

## Configure

Minimal `config.yaml` (user mode):

```yaml
easyatwork:
  auth_mode: user
  email: "me@example.com"
  login_url: "https://app.easyatwork.com/"
  app_url: "https://app.easyatwork.com"
  shifts_endpoint: "/api/v1/shifts"   # capture from DevTools → Network

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

**IMPORTANT:** You must create the target calendar manually *before* your first sync!
1. Open **Calendar.app**
2. Go to **File → New Calendar** and choose the source (e.g., `iCloud`)
3. Name it exactly what you put in your config (e.g., "Work Shifts")
4. Run `eaw-sync sync`. It will trigger a macOS permission prompt.
5. Grant access when prompted (or in *System Settings → Privacy & Security → Calendars*).

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

## Known limitations

- **No public API.** easy@work does not publish developer docs. The
  default `user` auth mode scrapes the web app via Playwright and reuses
  its session cookies, which works against the real tenant but depends
  on the SPA's private endpoints.
- **`shifts_endpoint` is tenant-specific.** Open
  `app.easyatwork.com` in a browser, DevTools → Network, filter `XHR`,
  open your schedule view, find the JSON request that returns your
  shifts, copy its path to `easyatwork.shifts_endpoint`. Session-mode
  parsing auto-detects common shapes (`{"data": [...]}`,
  `{"results": [...]}`, bare list, `id`/`uuid`/`shiftId`,
  `start`/`starts_at`/`from`, etc) — unexpected shapes raise `ApiError`
  with the observed top-level keys.
- **OAuth (`client` mode) is unverified.** Kept in-tree for forward-compat
  should easy@work publish a developer API, but there is no public
  reference client (`php-eaw-client` does not exist as a public repo).

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

## Contributing

If you fork and want to publish your own PyPI package via GitHub Actions:
1. Ensure you have claimed your project name on PyPI.
2. Go to **PyPI -> Manage -> Publishing**.
3. Add a "Trusted Publisher" configured for your GitHub repository (e.g. `Ailcope/EasyAtCal`) pointing to the `publish.yml` workflow and the `pypi` environment.

## Design

- `docs/superpowers/specs/2026-04-19-easyatcal-design.md` — full design.
- `docs/superpowers/plans/2026-04-19-easyatcal-implementation.md` — build plan.

## License

MIT — see `LICENSE`.
