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

A CLI tool for syncing your [easy@work](https://www.easyatwork.com) shifts into Apple Calendar, Google Calendar, or standard ICS files. It runs locally, fetches your upcoming shifts, and pushes them to your preferred calendar app. It can also be run as a daemon to keep your calendar up to date in the background.

- **Automated Login.** No public API required. It uses Playwright to securely log in via a headless browser and extract a session token.
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
  api_url: "https://eu-west-3.api.easyatwork.com"   # Check your DevTools for your specific region
  customer_id: 1234                                 # Found in DevTools URL
  employee_id: 1234567                              # Found in DevTools URL
```

> **How to find your `customer_id` and `employee_id`:**
> 1. Open your browser and log in to [app.easyatwork.com](https://app.easyatwork.com).
> 2. Open Developer Tools (F12) -> Go to the **Network** tab.
> 3. Click on your schedule. Look for a network request starting with `shifts?from=...`
> 4. Look at the URL of that request: `https://eu-west-3.api.easyatwork.com/customers/<customer_id>/employees/<employee_id>/shifts`

### 3. Log In

Run the interactive login command. It prompts securely for your password, launches a headless Chromium browser, logs you in, and saves your session token securely.

```bash
eaw-sync login
```

### 4. Sync Your Calendar

Run the sync command. If you are using the default `.ics` backend, it will download your shifts and interactively ask if you want to open Apple Calendar, Windows Outlook, or Google Calendar to complete the import.

```bash
eaw-sync sync
```

## Background Sync

To keep your calendar up to date continuously, run EasyAtCal in daemon mode:

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
| `eaw-sync --install-completion` | Install shell autocomplete (bash/zsh/fish). |

### Exit codes (`sync`)

| Code | Meaning |
|------|---------|
| 0 | All changes applied successfully. |
| 1 | Partial failure (some changes applied, backend error on others). |
| 2 | Fatal (config/auth/network failed before writing). |

## Security

Your easy@work password is **never stored on disk**. The configuration file only stores your email. When you run `eaw-sync login`, the password is used once to drive the browser, and only the resulting JSON Web Token (JWT) is saved locally in `~/.cache/easyatcal/session.json` (with strict `0600` permissions).

## License

MIT — see `LICENSE`.
