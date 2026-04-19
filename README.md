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
eaw-sync watch --interval-seconds 900   # daemon mode (15 min)
```

See `docs/superpowers/specs/2026-04-19-easyatcal-design.md` for the full design,
and `docs/superpowers/plans/2026-04-19-easyatcal-implementation.md` for the
implementation plan.
