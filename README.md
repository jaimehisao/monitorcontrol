# MonitorControl for Linux

Control brightness, contrast, and volume on **whatever is plugged in** —
the way [MonitorControl](https://github.com/MonitorControl/MonitorControl)
does on macOS: keys, an on-screen HUD, and a slider where the desktop
already puts brightness.

It does not have a per-model database. External monitors are driven with
standard DDC/CI (VESA MCCS VCP codes) and probed for the features they
actually implement. Laptop panels use `/sys/class/backlight`.

## Fedora / GNOME

On GNOME 49+, the Quick Settings brightness slider is backed by Mutter.
A desktop with only an HDMI/DP monitor has **no kernel backlight**, so
that slider is missing. This app fills the same slot:

1. Run the daemon at login (`Launch at login` in Settings, or
   `monitorcontrol --background`).
2. Bind the hardware brightness keys:
   `PYTHONPATH=src python3 -m monitorcontrol shortcuts install`
3. Install the Shell extension so a `QuickSlider` shows up in the same
   Quick Settings menu Fedora already uses:
   `PYTHONPATH=src python3 -m monitorcontrol extension install`
   then `gnome-extensions enable monitorcontrol@monitorcontrol.dev`
   (Wayland usually wants a log out).

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

Without this, the app still lists connected monitors but cannot change
them:

```bash
./scripts/install-i2c-permissions.sh
```

Then log out and back in. Enable DDC/CI in the monitor's own OSD if the
brand ships with it off.

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
