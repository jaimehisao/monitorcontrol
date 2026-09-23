"""First-run and quiet repair of MonitorControl-owned setup."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

from monitorcontrol.autostart import DESKTOP_NAME
from monitorcontrol.gnome_extension import is_installed
from monitorcontrol.permissions import i2c_ready as probe_i2c
from monitorcontrol.settings_actions import SettingsActions
from monitorcontrol.shortcuts import installed_paths


def running_on_gnome(environ: dict[str, str] | None = None) -> bool:
    env = environ if environ is not None else os.environ
    desktop = env.get("XDG_CURRENT_DESKTOP", "")
    return "gnome" in desktop.lower()


@dataclass
class SetupChoice:
    """What the user asked for. Declining leaves every flag false."""

    proceed: bool = False
    autostart: bool = False
    shortcuts: bool = False
    extension: bool = False


@dataclass
class BootstrapResult:
    i2c_ready: bool
    i2c_prompted: bool
    i2c_error: str | None
    binary: str
    autostart: bool
    shortcuts: bool
    extension: bool
    extension_enabled: bool
    setup_complete: bool


def bootstrap(
    actions: SettingsActions,
    *,
    grant_i2c: Callable[[], tuple[bool, str | None]] | None,
    install_binary: Callable[[], str] | None,
    on_gnome: bool,
    enable_extension: Callable[[], bool] | None = None,
    i2c_ready: bool | None = None,
    needs_i2c: bool = True,
    choice: SetupChoice | None = None,
) -> BootstrapResult:
    choice = choice or SetupChoice()
    ready = probe_i2c() if i2c_ready is None else i2c_ready
    if not choice.proceed:
        return BootstrapResult(
            i2c_ready=ready,
            i2c_prompted=False,
            i2c_error=None,
            binary=actions.program,
            autostart=actions.config.autostart,
            shortcuts=actions.config.shortcuts,
            extension=actions.config.extension,
            extension_enabled=False,
            setup_complete=actions.config.setup_complete,
        )

    binary = actions.program
    if install_binary is not None and (choice.autostart or choice.shortcuts):
        binary = install_binary()
        actions.program = binary

    prompted = False
    error: str | None = None
    if needs_i2c and not ready and grant_i2c is not None:
        prompted = True
        ok, error = grant_i2c()
        if ok:
            ready = True
            error = None
        elif i2c_ready is None:
            ready = probe_i2c()
    elif not needs_i2c:
        ready = True

    if choice.autostart:
        actions.set_autostart(True)
    if choice.shortcuts:
        actions.set_shortcuts(True)
    extension = False
    extension_enabled = False
    if choice.extension and on_gnome:
        actions.set_extension(True)
        extension = True
        if enable_extension is not None:
            extension_enabled = bool(enable_extension())

    complete = (not needs_i2c or ready) and error is None
    actions.config.setup_complete = complete
    actions.persist()
    return BootstrapResult(
        i2c_ready=ready,
        i2c_prompted=prompted,
        i2c_error=error,
        binary=binary,
        autostart=actions.config.autostart,
        shortcuts=actions.config.shortcuts,
        extension=extension,
        extension_enabled=extension_enabled,
        setup_complete=complete,
    )


def repair(actions: SettingsActions, *, on_gnome: bool) -> None:
    """Restore steps the user already enabled. Never enables a new one."""
    if actions.config.autostart:
        desktop = actions.autostart_dir / DESKTOP_NAME
        if not desktop.is_file():
            actions.set_autostart(True)
    if actions.config.shortcuts and not installed_paths(actions.shortcut_store):
        actions.set_shortcuts(True)
    if actions.config.extension and on_gnome and not is_installed(actions.extension_root):
        actions.set_extension(True)
