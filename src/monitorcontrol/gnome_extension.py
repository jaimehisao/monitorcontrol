"""Install the GNOME Shell extension that hosts Quick Settings sliders."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from monitorcontrol.assetlib import package_data

UUID = "monitorcontrol@monitorcontrol.dev"
DEFAULT_ROOT = Path.home() / ".local" / "share" / "gnome-shell" / "extensions"


def bundled_dir() -> Path:
    return package_data("data", "gnome-extension")


def install(dest_root: Path = DEFAULT_ROOT) -> Path:
    dest = dest_root / UUID
    src = bundled_dir()
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return dest


def uninstall(dest_root: Path = DEFAULT_ROOT) -> bool:
    dest = dest_root / UUID
    if not dest.exists():
        return False
    shutil.rmtree(dest)
    return True


def is_installed(dest_root: Path = DEFAULT_ROOT) -> bool:
    return (dest_root / UUID / "metadata.json").is_file()


def enable(*, runner=subprocess.run) -> bool:
    """Ask gnome-extensions to turn it on. May still need a session restart."""
    try:
        proc = runner(
            ["gnome-extensions", "enable", UUID],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0
