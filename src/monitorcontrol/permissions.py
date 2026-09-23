"""I2C permission checks and the commands to fix them.

DDC/CI needs read/write on /dev/i2c-*. Distros leave those nodes root-only
until the user is in the `i2c` group. This is the same for every vendor.
"""

from __future__ import annotations

from monitorcontrol.i2c import permission_status
from monitorcontrol.i2c_setup import UDEV_RULE, UDEV_RULE_NAME

SETUP_COMMANDS = (
    "sudo groupadd -f i2c\n"
    'sudo usermod -aG i2c "$USER"\n'
    f"sudo tee /etc/udev/rules.d/{UDEV_RULE_NAME} >/dev/null <<'EOF'\n"
    f"{UDEV_RULE}"
    "EOF\n"
    "sudo udevadm control --reload-rules\n"
    "sudo udevadm trigger\n"
)


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
