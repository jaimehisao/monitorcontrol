"""First-run: binary on PATH, I2C, autostart, keys, GNOME slider."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

from monitorcontrol.permissions import i2c_ready as probe_i2c
from monitorcontrol.settings_actions import SettingsActions


def running_on_gnome(environ: dict[str, str] | None = None) -> bool:
    env = environ if environ is not None else os.environ
    desktop = env.get("XDG_CURRENT_DESKTOP", "")
    return "gnome" in desktop.lower()


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


def bootstrap(
    actions: SettingsActions,
    *,
    grant_i2c: Callable[[], tuple[bool, str | None]] | None,
    install_binary: Callable[[], str],
    on_gnome: bool,
    enable_extension: Callable[[], bool] | None = None,
    i2c_ready: bool | None = None,
) -> BootstrapResult:
    binary = install_binary()
    actions.program = binary
    prompted = False
    error: str | None = None
    ready = probe_i2c() if i2c_ready is None else i2c_ready
    if not ready and grant_i2c is not None:
        prompted = True
        ok, error = grant_i2c()
        ready = bool(ok) or probe_i2c()
        if ok:
            error = None
    actions.set_autostart(True)
    actions.set_shortcuts(True)
    extension = False
    extension_enabled = False
    if on_gnome:
        actions.set_extension(True)
        extension = True
        if enable_extension is not None:
            extension_enabled = bool(enable_extension())
    actions.config.setup_complete = True
    actions.persist()
    return BootstrapResult(
        i2c_ready=ready,
        i2c_prompted=prompted,
        i2c_error=error,
        binary=binary,
        autostart=True,
        shortcuts=True,
        extension=extension,
        extension_enabled=extension_enabled,
    )
