# MonitorControl for Linux

Control brightness, contrast, and volume on **whatever is plugged in** —
Dell, LG, Lenovo, laptop eDP, several at once — the way
[MonitorControl](https://github.com/MonitorControl/MonitorControl) does on macOS.

It does not have a per-model database. External monitors are driven with
standard DDC/CI (VESA MCCS VCP codes). Each panel is probed for the
features it actually implements, so a TV with volume and a cheap panel
with only luminance both work. Laptop panels use `/sys/class/backlight`.

## Requirements

- Linux, Python 3.11+
- GTK 4 and libadwaita (Fedora: already on Workstation)
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
PYTHONPATH=src python3 -m monitorcontrol          # window
PYTHONPATH=src python3 -m monitorcontrol list
PYTHONPATH=src python3 -m monitorcontrol brightness up
PYTHONPATH=src python3 -m monitorcontrol brightness 40
PYTHONPATH=src python3 -m monitorcontrol --display HDMI volume down
```

`--display` matches a substring of the name, identity, or connector, so
`U2720Q`, `HDMI`, or `LEN:` all work.

## I2C permissions

Without this, the app still lists connected monitors but cannot change
them. It is the same for every GPU vendor:

```bash
./scripts/install-i2c-permissions.sh
```

Then log out and back in. The script creates the `i2c` group, adds your
user, and installs a udev rule so `/dev/i2c-*` is `0660`. Enable DDC/CI
in the monitor's own OSD if the brand ships with it off.

## Keyboard

The compositor owns the brightness keys on Linux. Bind them to the CLI:

**GNOME** (Settings → Keyboard → Custom Shortcuts):

| Shortcut | Command |
| --- | --- |
| Monitor brightness up | `python3 -m monitorcontrol brightness up` |
| Monitor brightness down | `python3 -m monitorcontrol brightness down` |

Put `PYTHONPATH=/path/to/monitorcontrol/src` in the command if you have
not installed the package.

**Hyprland / Sway:**

```
bindel = , XF86MonBrightnessUp, exec, monitorcontrol brightness up
bindel = , XF86MonBrightnessDown, exec, monitorcontrol brightness down
```

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Why Python

The interesting part of this app is DDC/CI and the desktop session, not
the language. Python is what can import GTK 4 / libadwaita on a stock
Fedora Workstation without `gtk4-devel`. A Rust port (ddc-hi + gtk-rs)
would be a better long-term binary, but it does not build here without
those -devel packages.
