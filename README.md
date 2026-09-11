<p align="center">
  <img src="docs/logo.png" width="168" height="168" alt="MonitorControl">
</p>

<h1 align="center">MonitorControl for Linux</h1>

<p align="center">
  Brightness, contrast, and volume on <strong>whatever is plugged in</strong> —
  keys, an on-screen HUD, and a slider where the desktop already puts brightness.
  The Linux counterpart to
  <a href="https://github.com/MonitorControl/MonitorControl">MonitorControl for macOS</a>.
</p>

<p align="center">
  <a href="https://github.com/jaimehisao/monitorcontrol/actions/workflows/ci.yml"><img src="https://github.com/jaimehisao/monitorcontrol/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/jaimehisao/monitorcontrol/releases"><img src="https://github.com/jaimehisao/monitorcontrol/actions/workflows/release.yml/badge.svg" alt="Release"></a>
</p>

There is no per-model database. External monitors speak standard DDC/CI
(VESA MCCS). Laptop panels use `/sys/class/backlight`. NVIDIA, AMD, and
Intel all work: each cable is matched to its I2C bus by EDID.

## Features

- **First launch sets it up.** One admin prompt grants I2C for this
  session. Brightness keys and autostart turn on immediately.
- **GNOME.** A panel brightness icon and Quick Settings sliders (log out
  once after install). On a laptop, GNOME's own slider still works; we
  copy that percent onto every DDC display.
- **OSD.** Key presses show a compact overlay, like the macOS app.
- **CLI.** `list`, `brightness`, `contrast`, `volume` talk to the
  running daemon so the OSD still appears.

## Install

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

Click **Continue**. If the sliders stay empty, enable **DDC/CI** in the
monitor's own OSD — some brands ship with it off.

### Other desktops

First launch still copies a binary to `~/.local/bin` and grants I2C.
Bind the keys yourself:

```
# Hyprland / Sway
bindel = , XF86MonBrightnessUp, exec, monitorcontrol brightness up
bindel = , XF86MonBrightnessDown, exec, monitorcontrol brightness down
```

## Use

```bash
monitorcontrol                 # window
monitorcontrol --background    # daemon only
monitorcontrol list
monitorcontrol brightness up
monitorcontrol brightness 40
monitorcontrol --display HDMI volume down
```

`--display` matches a substring of the name, identity, or connector.

If you skipped first-run:

```bash
monitorcontrol shortcuts install
monitorcontrol extension install
# then log out once so GNOME loads the panel icon and slider
```

## Uninstall

```bash
monitorcontrol uninstall
```

Removes keybindings (GNOME gets its brightness keys back), autostart,
the app-menu launcher, the GNOME extension, `~/.local/bin/monitorcontrol`,
and config. The I2C udev rule stays so a later install (or ddcutil) still
works. Delete `/etc/udev/rules.d/90-monitorcontrol-i2c.rules` with sudo
if you want that gone too.

`--keep-config` leaves `~/.config/monitorcontrol`.

## From a checkout

```bash
PYTHONPATH=src python3 -m monitorcontrol
PYTHONPATH=src python3 -m monitorcontrol list
```

I2C grant from a git tree uses `PYTHONPATH` automatically. The fallback
script is `scripts/install-i2c-permissions.sh`.

## Releases

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
