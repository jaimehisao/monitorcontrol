"""Install a .desktop launcher and icon so the app shows up in the menu."""

from __future__ import annotations

import shutil
from pathlib import Path

from monitorcontrol.assetlib import package_data

DESKTOP_NAME = "dev.monitorcontrol.MonitorControl.desktop"
ICON_NAME = "dev.monitorcontrol.MonitorControl.svg"


def applications_dir() -> Path:
    return Path.home() / ".local" / "share" / "applications"


def icon_dir() -> Path:
    return Path.home() / ".local" / "share" / "icons" / "hicolor" / "scalable" / "apps"


def desktop_text(program: str) -> str:
    raw = package_data("data", DESKTOP_NAME).read_text(encoding="utf-8")
    lines = []
    for line in raw.splitlines():
        if line.startswith("Exec="):
            lines.append(f"Exec={program}")
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


def install(program: str, *, apps: Path | None = None, icons: Path | None = None) -> Path:
    dest_apps = apps if apps is not None else applications_dir()
    dest_icons = icons if icons is not None else icon_dir()
    dest_apps.mkdir(parents=True, exist_ok=True)
    dest_icons.mkdir(parents=True, exist_ok=True)
    desktop = dest_apps / DESKTOP_NAME
    desktop.write_text(desktop_text(program), encoding="utf-8")
    shutil.copy2(package_data("data", ICON_NAME), dest_icons / ICON_NAME)
    return desktop


def uninstall(*, apps: Path | None = None, icons: Path | None = None) -> bool:
    dest_apps = apps if apps is not None else applications_dir()
    dest_icons = icons if icons is not None else icon_dir()
    removed = False
    desktop = dest_apps / DESKTOP_NAME
    if desktop.exists():
        desktop.unlink()
        removed = True
    icon = dest_icons / ICON_NAME
    if icon.exists():
        icon.unlink()
        removed = True
    return removed
