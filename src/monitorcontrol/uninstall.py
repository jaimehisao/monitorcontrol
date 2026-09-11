"""Remove everything first-run put in the user session.

Does not touch the I2C udev rule or the i2c group — those are system-wide
and still useful for ddcutil and a later reinstall.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from monitorcontrol.autostart import DEFAULT_DIR as AUTOSTART_DIR
from monitorcontrol.autostart import uninstall as uninstall_autostart
from monitorcontrol.config import DEFAULT_PATH as CONFIG_PATH
from monitorcontrol.gnome_extension import DEFAULT_ROOT as EXT_ROOT
from monitorcontrol.gnome_extension import disable as disable_extension
from monitorcontrol.gnome_extension import uninstall as uninstall_extension
from monitorcontrol.i2c_setup import UDEV_RULE_NAME
from monitorcontrol.launcher import uninstall as uninstall_launcher
from monitorcontrol.paths import user_binary
from monitorcontrol.shortcuts import gnome_store, uninstall as uninstall_shortcuts

I2C_RULE = Path("/etc/udev/rules.d") / UDEV_RULE_NAME


@dataclass
class UninstallResult:
    shortcuts: bool = False
    autostart: bool = False
    launcher: bool = False
    extension: bool = False
    binary: bool = False
    config: bool = False
    notes: list[str] = field(default_factory=list)


def run(
    *,
    shortcut_store=None,
    autostart_dir: Path | None = None,
    apps_dir: Path | None = None,
    icons_dir: Path | None = None,
    extension_root: Path | None = None,
    binary_path: Path | None = None,
    config_path: Path | None = None,
    keep_config: bool = False,
    settings=None,
    runner=None,
) -> UninstallResult:
    result = UninstallResult()

    try:
        store = shortcut_store if shortcut_store is not None else gnome_store()
        uninstall_shortcuts(store)
        result.shortcuts = True
    except Exception as exc:
        result.notes.append(f"shortcuts: {exc}")

    result.autostart = uninstall_autostart(autostart_dir or AUTOSTART_DIR)
    result.launcher = uninstall_launcher(apps=apps_dir, icons=icons_dir)
    disable_kw: dict = {}
    if settings is not None:
        disable_kw["settings"] = settings
    if runner is not None:
        disable_kw["runner"] = runner
    disable_extension(**disable_kw)
    result.extension = uninstall_extension(extension_root or EXT_ROOT)

    dest = binary_path if binary_path is not None else user_binary()
    if dest.is_file():
        dest.unlink()
        result.binary = True

    if not keep_config:
        cfg = config_path if config_path is not None else CONFIG_PATH
        if cfg.is_file():
            cfg.unlink()
            result.config = True
        parent = cfg.parent
        if parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()

    if I2C_RULE.exists():
        result.notes.append(
            f"left {I2C_RULE} so I2C still works; delete it with sudo if you want that gone too"
        )
    return result


def report(result: UninstallResult) -> list[str]:
    lines = []
    for label, did in (
        ("keybindings", result.shortcuts),
        ("autostart", result.autostart),
        ("app menu launcher", result.launcher),
        ("GNOME extension", result.extension),
        ("~/.local/bin/monitorcontrol", result.binary),
        ("config", result.config),
    ):
        lines.append(f"{'removed' if did else 'absent':<8} {label}")
    lines.extend(result.notes)
    lines.append("Quit MonitorControl if it is still running.")
    return lines
