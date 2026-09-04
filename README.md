# MonitorControl for Linux

[![CI](https://github.com/jaimehisao/monitorcontrol/actions/workflows/ci.yml/badge.svg)](https://github.com/jaimehisao/monitorcontrol/actions/workflows/ci.yml)
[![Release](https://github.com/jaimehisao/monitorcontrol/actions/workflows/release.yml/badge.svg)](https://github.com/jaimehisao/monitorcontrol/releases)

Control brightness, contrast, and volume on **whatever is plugged in** —
the way [MonitorControl](https://github.com/MonitorControl/MonitorControl)
does on macOS: keys, an on-screen HUD, and a slider where the desktop
already puts brightness.

## Downloads

Binaries and pip packages are attached to [GitHub Releases](https://github.com/jaimehisao/monitorcontrol/releases).

```bash
chmod +x monitorcontrol-*-linux
./monitorcontrol-*-linux
```

First launch is meant to just work: one admin prompt grants display
control for this session (no log out), then brightness keys, autostart,
and the GNOME Quick Settings slider are turned on.

Publish a release by pushing a version tag that matches `pyproject.toml`
from a PR, not from a direct push to `main`:

```bash
git tag v0.1.0
git push origin v0.1.0
```

It does not have a per-model database. External monitors are driven with
standard DDC/CI (VESA MCCS VCP codes) and probed for the features they
actually implement. Laptop panels use `/sys/class/backlight`.

## Fedora / GNOME

On GNOME 49+, the Quick Settings brightness slider is backed by Mutter.
A desktop with only an HDMI/DP monitor has **no kernel backlight**, so
that slider is missing. This app fills the same slot:

On first run the app does this itself (Continue in the setup dialog).
If you skipped that, use Settings or:

```bash
monitorcontrol shortcuts install
monitorcontrol extension install
gnome-extensions enable monitorcontrol@monitorcontrol.dev
```

If you *do* have a laptop panel, GNOME's own slider still works. We
watch Mutter's `Backlight` property and copy that percent onto every
DDC display (the macOS "sync from the built-in panel" behaviour).

## Requirements

- Linux, Python 3.11+
- GTK 4 and libadwaita (Fedora Workstation already has these)
- I2C access for external monitors (`i2c-dev`, user in the `i2c` group)

```bash
# Fedora
sudo dnf install python3-gobject gtk4 libadwaita i2c-tools
# Debian/Ubuntu
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 i2c-tools
```

## Run

From a checkout:

```bash
PYTHONPATH=src python3 -m monitorcontrol                 # window
PYTHONPATH=src python3 -m monitorcontrol --background    # daemon only
PYTHONPATH=src python3 -m monitorcontrol list
PYTHONPATH=src python3 -m monitorcontrol brightness up
PYTHONPATH=src python3 -m monitorcontrol brightness 40
PYTHONPATH=src python3 -m monitorcontrol --display HDMI volume down
PYTHONPATH=src python3 -m monitorcontrol shortcuts install
PYTHONPATH=src python3 -m monitorcontrol extension install
```

`--display` matches a substring of the name, identity, or connector.
If the daemon is already running, the CLI talks to it over D-Bus so the
OSD can show.

## I2C permissions

The first-run dialog requests this via `pkexec` and applies ACLs so the
**current session** can talk to `/dev/i2c-*` immediately. The fallback
script is `scripts/install-i2c-permissions.sh`. Enable DDC/CI in the
monitor's own OSD if the brand ships with it off.

## Keyboard

`shortcuts install` writes GNOME custom keybindings for
`XF86MonBrightnessUp` / `Down`. Volume keys stay with PipeWire unless
you pass `--volume`.

Hyprland / Sway:

```
bindel = , XF86MonBrightnessUp, exec, monitorcontrol brightness up
bindel = , XF86MonBrightnessDown, exec, monitorcontrol brightness down
```

## Tests

```bash
uv venv --system-site-packages
uv pip install coverage
PYTHONPATH=src .venv/bin/coverage run --source=src/monitorcontrol -m unittest discover -s tests
PYTHONPATH=src .venv/bin/coverage report
```

The suite is expected to stay at **80%+** line coverage (`fail_under = 80`
in `pyproject.toml`).
