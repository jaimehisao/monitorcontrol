"""I2C permission checks and the commands to fix them.

DDC/CI needs read/write on /dev/i2c-*. Distros leave those nodes root-only
until the user is in the `i2c` group. This is the same for every vendor.
"""

from __future__ import annotations

from monitorcontrol.i2c import permission_status

SETUP_COMMANDS = """sudo groupadd -f i2c
sudo usermod -aG i2c "$USER"
echo 'KERNEL=="i2c-[0-9]*", GROUP="i2c", MODE="0660"' | sudo tee /etc/udev/rules.d/90-monitorcontrol-i2c.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
"""


def i2c_ready() -> bool:
    ready, _blocked = permission_status()
    return ready


def permission_message() -> str | None:
    if i2c_ready():
        return None
    return (
        "Display control needs a one-time admin approval so this user can "
        "open /dev/i2c-*. Use Set up now if the first-run prompt was skipped."
    )
