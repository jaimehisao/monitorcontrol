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


def _chmod_tree(root: Path) -> None:
    root.chmod(0o755)
    for path in root.rglob("*"):
        if path.is_dir():
            path.chmod(0o755)
        elif path.is_file():
            path.chmod(0o644)


def install(dest_root: Path = DEFAULT_ROOT) -> Path:
    dest = dest_root / UUID
    src = bundled_dir()
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    # Frozen extracts are often mode 600; user extensions are 644/755.
    _chmod_tree(dest)
    return dest


def uninstall(dest_root: Path = DEFAULT_ROOT) -> bool:
    dest = dest_root / UUID
    if not dest.exists():
        return False
    shutil.rmtree(dest)
    return True


def is_installed(dest_root: Path = DEFAULT_ROOT) -> bool:
    return (dest_root / UUID / "metadata.json").is_file()


def add_enabled_uuid(current: list[str], uuid: str = UUID) -> list[str]:
    if uuid in current:
        return list(current)
    return [*current, uuid]


def remove_enabled_uuid(current: list[str], uuid: str = UUID) -> list[str]:
    return [item for item in current if item != uuid]


def enable(*, runner=subprocess.run, settings=None) -> bool:
    """Enable the extension for the next GNOME session.

    `gnome-extensions enable` only works if the running Shell already
    scanned the UUID. Writing `enabled-extensions` is what makes it
    actually load after logout.
    """
    wrote = False
    store = settings
    if store is None:
        try:
            import gi

            gi.require_version("Gio", "2.0")
            from gi.repository import Gio

            store = Gio.Settings.new("org.gnome.shell")
        except Exception:
            store = None
    if store is not None:
        try:
            current = list(store.get_strv("enabled-extensions"))
            store.set_strv("enabled-extensions", add_enabled_uuid(current))
            wrote = True
        except Exception:
            wrote = False
    try:
        proc = runner(
            ["gnome-extensions", "enable", UUID],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        cli_ok = proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        cli_ok = False
    return wrote or cli_ok


def disable(*, runner=subprocess.run, settings=None) -> bool:
    """Drop the UUID from enabled-extensions. Shell may need a logout."""
    wrote = False
    store = settings
    if store is None:
        try:
            import gi

            gi.require_version("Gio", "2.0")
            from gi.repository import Gio

            store = Gio.Settings.new("org.gnome.shell")
        except Exception:
            store = None
    if store is not None:
        try:
            current = list(store.get_strv("enabled-extensions"))
            store.set_strv("enabled-extensions", remove_enabled_uuid(current))
            wrote = True
        except Exception:
            wrote = False
    try:
        proc = runner(
            ["gnome-extensions", "disable", UUID],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        cli_ok = proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        cli_ok = False
    return wrote or cli_ok
