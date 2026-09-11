# MonitorControl for Linux

[![CI](https://github.com/jaimehisao/monitorcontrol/actions/workflows/ci.yml/badge.svg)](https://github.com/jaimehisao/monitorcontrol/actions/workflows/ci.yml)
[![Release](https://github.com/jaimehisao/monitorcontrol/actions/workflows/release.yml/badge.svg)](https://github.com/jaimehisao/monitorcontrol/releases)

Control brightness, contrast, and volume on **whatever is plugged in** —
the way [MonitorControl](https://github.com/MonitorControl/MonitorControl)
does on macOS: keys, an on-screen HUD, and a slider where the desktop
already puts brightness.

It does not have a per-model database. External monitors use standard
DDC/CI (VESA MCCS). Laptop panels use `/sys/class/backlight`. NVIDIA,
AMD, and Intel are all fine; the app matches each cable to its I2C bus
by EDID.

## Install (GNOME)

You need GTK 4 and libadwaita (Fedora Workstation already has them).

```bash
# Fedora
sudo dnf install gtk4 libadwaita
# Debian / Ubuntu
sudo apt install gir1.2-gtk-4.0 gir1.2-adw-1
```

Download `monitorcontrol-*-linux` from
[Releases](https://github.com/jaimehisao/monitorcontrol/releases):

```bash
chmod +x monitorcontrol-*-linux
./monitorcontrol-*-linux
```

Click **Continue** on first launch. One admin prompt grants display
control for this session (no log out). Brightness keys and autostart
turn on immediately. The GNOME Quick Settings slider appears after you
**log out once**.

If the sliders stay empty, enable **DDC/CI** in the monitor's own OSD.
Some brands ship with it off.

## Other desktops

First launch still copies a `monitorcontrol` binary to `~/.local/bin`
and grants I2C. Bind the keys yourself:

```
# Hyprland / Sway
bindel = , XF86MonBrightnessUp, exec, monitorcontrol brightness up
bindel = , XF86MonBrightnessDown, exec, monitorcontrol brightness down
```

## From a checkout

```bash
PYTHONPATH=src python3 -m monitorcontrol                 # window
PYTHONPATH=src python3 -m monitorcontrol --background    # daemon only
PYTHONPATH=src python3 -m monitorcontrol list
PYTHONPATH=src python3 -m monitorcontrol brightness up
PYTHONPATH=src python3 -m monitorcontrol brightness 40
PYTHONPATH=src python3 -m monitorcontrol --display HDMI volume down
```

`--display` matches a substring of the name, identity, or connector.
If the daemon is already running, the CLI talks to it over D-Bus so the
OSD can show.

## Uninstall

```bash
monitorcontrol uninstall
```

That removes keybindings (and gives GNOME its brightness keys back),
autostart, the app-menu launcher, the GNOME extension, `~/.local/bin/monitorcontrol`,
and config. The I2C udev rule stays so a later install (or ddcutil) still
works. Delete `/etc/udev/rules.d/90-monitorcontrol-i2c.rules` with sudo
if you want that gone too.

## If you skipped first-run

```bash
monitorcontrol shortcuts install
monitorcontrol extension install
# then log out once so GNOME loads the Quick Settings slider
```

On a laptop, GNOME's own slider still works. We watch Mutter's
`Backlight` property and copy that percent onto every DDC display.

## I2C permissions

The first-run dialog requests this via `pkexec` and applies ACLs so the
**current session** can talk to `/dev/i2c-*` immediately. The fallback
script is `scripts/install-i2c-permissions.sh`.

## Publish a release

Push a version tag that matches `pyproject.toml` from a PR, not from a
direct push to `main`:

```bash
git tag v0.1.0
git push origin v0.1.0
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
