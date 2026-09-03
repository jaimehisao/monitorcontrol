"""Install the GNOME Shell extension that hosts Quick Settings sliders."""

from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path

UUID = "monitorcontrol@monitorcontrol.dev"
DEFAULT_ROOT = Path.home() / ".local" / "share" / "gnome-shell" / "extensions"


def bundled_dir() -> Path:
    return Path(resources.files("monitorcontrol")).joinpath("data", "gnome-extension")


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
