#!/usr/bin/env bash
# One-shot I2C setup. Prefer: monitorcontrol (first-run dialog) or
# pkexec monitorcontrol --privileged-setup --setup-user "$USER"
set -euo pipefail

if [[ $EUID -eq 0 && -z "${SUDO_USER:-}" ]]; then
  echo "Run this as a regular user with sudo, not as root login." >&2
  exit 1
fi

USER_NAME="${SUDO_USER:-$USER}"
if command -v python3 >/dev/null 2>&1; then
  root="$(cd "$(dirname "$0")/.." && pwd)"
  exec sudo PYTHONPATH="$root/src" python3 -m monitorcontrol \
    --privileged-setup --setup-user "$USER_NAME"
fi

RULE='/etc/udev/rules.d/90-monitorcontrol-i2c.rules'
sudo groupadd -f i2c
sudo usermod -aG i2c "$USER_NAME"
echo 'KERNEL=="i2c-[0-9]*", GROUP="i2c", MODE="0660", TAG+="uaccess"' | sudo tee "$RULE" >/dev/null
echo i2c-dev | sudo tee /etc/modules-load.d/i2c-dev.conf >/dev/null
sudo modprobe i2c-dev || true
sudo udevadm control --reload-rules
sudo udevadm trigger
sudo setfacl -m "u:${USER_NAME}:rw" /dev/i2c-* 2>/dev/null || sudo chmod 0666 /dev/i2c-*
echo "I2C access configured for $USER_NAME for this session."
