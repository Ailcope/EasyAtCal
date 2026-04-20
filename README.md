<div align="center" markdown="1">

# EasyAtCal

[![CI](https://img.shields.io/github/actions/workflow/status/Ailcope/EasyAtCal/ci.yml?branch=main&label=CI&logo=github&logoColor=white&color=brightgreen)](https://github.com/Ailcope/EasyAtCal/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/Coverage-90%25-brightgreen.svg?logo=codecov&logoColor=white)](https://github.com/Ailcope/EasyAtCal)
[![Release](https://img.shields.io/github/v/release/Ailcope/EasyAtCal?label=Release&logo=github&logoColor=white&color=blue)](https://github.com/Ailcope/EasyAtCal/releases)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?logo=opensourceinitiative&logoColor=white)](./LICENSE)

**One-way sync of easy@work shifts into Apple Calendar, Google Calendar, or standard ICS files.**

Works with **macOS EventKit** &bull; **Google Calendar** &bull; **Windows Outlook**

[Quickstart](#quickstart) &bull; [Configuration](#configuration) &bull; [Backends](#backends) &bull; [Commands](#cli-commands)

</div>

---

## Overview

**EasyAtCal** is a CLI tool designed to automatically synchronize your [easy@work](https://www.easyatwork.com) work schedule directly into Apple Calendar, Google Calendar, or standard ICS files. It runs locally, fetches your upcoming shifts, and pushes them to your preferred personal calendar app. It can even be run as a background daemon to keep your calendar up to date continuously!

### What is easy@work?
**easy@work** is a popular workforce management, timesheet, and employee scheduling platform used by major global brands, retail stores, and fast-food chains—most notably **McDonald's**. If you work at a McDonald's restaurant or any other company that uses the easy@work employee portal to handle your shift planning and rotas, **EasyAtCal** is the perfect companion to automate your personal schedule management.

### Features

- **Automated Login & Discovery.** No public API required. It uses Playwright to securely log in via a headless browser, extracting both your session token and your unique account IDs (`customer_id`, `employee_id`) automatically.
- **Secure Session.** Your JWT is securely cached in your OS's native credential store (Keychain on macOS, Credential Locker on Windows) via the `keyring` library.
- **Background Sync.** Includes a built-in `schedule` command to easily install an auto-updating background daemon (macOS `launchd`, Linux `cron`, or Windows Task Scheduler).
- **Customizable Events.** Configure your own event titles (e.g. `[Work] {title} at {location}`) and add automatic alarms/reminders for your shifts.
- **Two Backends.** Native macOS **EventKit** integration (pushes directly to Apple Calendar) or portable **ICS** file generation (supports interactive import prompts for Google Calendar and Windows Outlook).
- **Idempotent.** State-tracked logic means unchanged shifts are skipped, while schedule updates and cancellations propagate automatically.
- **Bilingual CLI.** Automatically detects English or French system locales and adjusts interactive prompts.

## Quickstart

### 1. Install

Install the core application and the Playwright browser dependencies (required for headless login).

```bash
pip install 'easyatcal[playwright]'
playwright install chromium
```

*(If you are on macOS and want native Apple Calendar integration, use `pip install 'easyatcal[eventkit,playwright]'`)*

### 2. Configure

Scaffold the default configuration file:

```bash
eaw-sync config init
```

Now, open the configuration file (located at `~/.config/easyatcal/config.yaml` on Linux or `~/Library/Application Support/easyatcal/config.yaml` on macOS) and fill in your details:

```yaml
easyatwork:
  email: "your.email@example.com"
  # Optional: api_url, customer_id, and employee_id are now automatically discovered!
```

You can optionally configure event titles and alarms:

```yaml
sync:
  event_title_format: "EasyAtWork: {title}"
  alarm_minutes_before: 60  # Remind me 1 hour before my shift
```

### 3. Log In

Run the interactive login command. It prompts securely for your password, launches a headless Chromium browser, logs you in, automatically discovers your account IDs (`customer_id`/`employee_id`), and saves your session token securely using your OS keyring.

```bash
eaw-sync login
```

### 4. Sync Your Calendar

Run the sync command. If you are using the default `.ics` backend, it will download your shifts and interactively ask if you want to open Apple Calendar, Windows Outlook, or Google Calendar to complete the import.

```bash
eaw-sync sync
```

## Background Sync

To keep your calendar up to date continuously, EasyAtCal can run in the background.

Use the `schedule` command to set up an OS-level background task (macOS `launchd`, Linux `crontab`, or Windows Task Scheduler). The background job will run `eaw-sync sync` silently every few hours.

```bash
# Display the necessary configuration to set up background sync
eaw-sync schedule --interval-hours 6

# Alternatively, have it install automatically on macOS/Linux
eaw-sync schedule --install --interval-hours 6
```

Alternatively, run EasyAtCal in daemon loop mode manually:

```bash
eaw-sync watch --interval-seconds 900   # Syncs every 15 minutes
```

*Note: Your login token expires roughly once a year. If the daemon starts failing with authentication errors, simply run `eaw-sync login` again.*

## Backends

### 1. ICS (Cross-platform)
Generates a portable `.ics` file locally. When you run `eaw-sync sync`, the CLI interactively offers to open your local calendar app or open the Google Calendar import page.

### 2. EventKit (macOS Only)
Writes directly to a dedicated calendar in the macOS Calendar.app via native APIs.

**IMPORTANT:** You must create the target calendar manually *before* your first sync.
1. Open **Calendar.app**.
2. Go to **File → New Calendar** and choose the source (e.g., `iCloud`).
3. Name it exactly what you put in your config (e.g., `EasyAtWork`).
4. Update your config: set `backend: eventkit`.
5. Run `eaw-sync sync`.
6. Grant calendar access when macOS prompts you.

## CLI Commands

| Command | Description |
|---------|------|
| `eaw-sync config init` | Scaffold the configuration file. |
| `eaw-sync config show` | Print active configuration (secrets redacted). |
| `eaw-sync login` | Opens a headless browser to log in and save your session token. |
| `eaw-sync doctor` | Checks config validity, token liveliness, and API reachability. |
| `eaw-sync sync` | Run a single sync pass. |
| `eaw-sync sync --dry-run` | Diff remote shifts against local state without writing. |
| `eaw-sync watch` | Run the sync in an infinite loop. |
| `eaw-sync schedule` | Generate or install OS-level background sync (`launchd`, `cron`). |
| `eaw-sync --install-completion` | Install shell autocomplete (bash/zsh/fish). |

### Exit codes (`sync`)

| Code | Meaning |
|------|---------|
| 0 | All changes applied successfully. |
| 1 | Partial failure (some changes applied, backend error on others). |
| 2 | Fatal (config/auth/network failed before writing). |

## Security

Your easy@work password is **never stored on disk**. The configuration file only stores your email. When you run `eaw-sync login`, the password is used once to drive the browser, and the resulting JSON Web Token (JWT) is extracted and saved securely in your OS's native credential store using `keyring` (macOS Keychain, Windows Credential Locker, Linux Secret Service). Non-sensitive session data (like your `customer_id` and UI state) is saved in `~/.local/state/easyatcal` with strict `0600` permissions.

## License

MIT — see `LICENSE`.
