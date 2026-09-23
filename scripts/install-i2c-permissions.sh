#!/usr/bin/env bash
# One-shot I2C setup. The application and this wrapper share one entry point.
set -euo pipefail

if [[ $EUID -eq 0 && -z "${SUDO_USER:-}" ]]; then
  echo "Run this as a regular user with sudo, not as root login." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required; this wrapper does not change device permissions itself." >&2
  exit 1
fi

USER_NAME="${SUDO_USER:-$USER}"
root="$(cd "$(dirname "$0")/.." && pwd)"
exec sudo PYTHONPATH="$root/src" python3 -m monitorcontrol \
  --privileged-setup --setup-user "$USER_NAME"
