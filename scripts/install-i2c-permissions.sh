#!/usr/bin/env bash
# Give the current user access to /dev/i2c-* so DDC/CI works for any
# GPU vendor. Requires sudo. Log out after this for the group to apply.
set -euo pipefail

if [[ $EUID -eq 0 && -z "${SUDO_USER:-}" ]]; then
  echo "Run this as a regular user with sudo, not as root login." >&2
  exit 1
fi

USER_NAME="${SUDO_USER:-$USER}"
RULE='/etc/udev/rules.d/90-monitorcontrol-i2c.rules'

sudo groupadd -f i2c
sudo usermod -aG i2c "$USER_NAME"
echo 'KERNEL=="i2c-[0-9]*", GROUP="i2c", MODE="0660"' | sudo tee "$RULE" >/dev/null
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "I2C access configured for $USER_NAME."
echo "Log out and back in (or reboot), then run: python3 -m monitorcontrol list"
