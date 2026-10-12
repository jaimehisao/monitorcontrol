"""GTK application: daemon + window + GNOME brightness follow."""

from __future__ import annotations

import logging
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from monitorcontrol import APP_ID, APP_NAME
from monitorcontrol.assetlib import package_data
from monitorcontrol.backlight import is_internal_connector
from monitorcontrol.bootstrap import SetupChoice, bootstrap, repair, running_on_gnome
from monitorcontrol.config import Config, load as load_config
from monitorcontrol.controller import Controller
from monitorcontrol.dbus import export_session
from monitorcontrol.gnome_backlight import NativeBrightnessFollower, apply_native_percent, attach_mutter
from monitorcontrol.gnome_extension import enable as enable_extension
from monitorcontrol.i2c_setup import pkexec_grant
from monitorcontrol.osd import Osd
from monitorcontrol.paths import current_username, install_user_binary
from monitorcontrol.service import MonitorService
from monitorcontrol.settings_actions import SettingsActions
from monitorcontrol.window import ControlWindow

log = logging.getLogger(__name__)


def _load_css() -> None:
    provider = Gtk.CssProvider()
    data = package_data("data", "style.css").read_bytes()
    provider.load_from_data(data)
    display = Gdk.Display.get_default()
    if display is None:
        return
    Gtk.StyleContext.add_provider_for_display(
        display,
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


class Application(Adw.Application):
    def __init__(self, *, show_window: bool = True, config: Config | None = None) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        GLib.set_application_name(APP_NAME)
        self._show_window = show_window
        self.config = config or Config()
        self.controller: Controller | None = None
        self.service: MonitorService | None = None
        self.win: ControlWindow | None = None
        self.osd: Osd | None = None
        self._settings_dialog = None
        self._bootstrapping = False
        self._session = None
        self._follower = None
        self._mutter = None
        self.integration_errors: list[str] = []
        self._export_failed = False

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        _load_css()
        self.hold()
        self.controller = Controller(step=self.config.step, sync=self.config.sync)
        self.controller.refresh()
        self.service = MonitorService(self.controller)

        try:
            self._session = export_session(self.service)
        except Exception as exc:
            log.exception("session API was not exported")
            self.integration_errors.append(f"Session API unavailable: {exc}")
            if not self._show_window:
                self._export_failed = True
                GLib.idle_add(self.quit)
        self._follower = NativeBrightnessFollower(
            lambda percent: apply_native_percent(self.controller, percent)
        )
        try:
            self._mutter = attach_mutter(self._follower)
        except Exception as exc:
            log.exception("GNOME brightness follow failed")
            self.integration_errors.append(f"GNOME brightness follow unavailable: {exc}")

    def do_activate(self) -> None:
        self._ensure_window()
        if self.win is not None and self.integration_errors:
            self.win.set_notice(" ".join(self.integration_errors))
        if self._show_window and self.win is not None:
            self.win.present()
            if self.config.setup_complete and not self._bootstrapping:
                repair(self._settings_actions(), on_gnome=running_on_gnome())
            elif not self.config.setup_complete and not self._bootstrapping:
                self._prompt_first_run()
        self._show_window = True

    def _ensure_window(self) -> None:
        if self.win is not None:
            return
        assert self.controller is not None
        self.win = ControlWindow(self, self.controller)
        self.win.on_settings = self._open_settings
        self.win.on_setup = lambda: self._run_bootstrap(
            SetupChoice(proceed=True, autostart=False, shortcuts=False, extension=False)
        )
        self.win.on_sync_changed = self._persist_sync
        self.osd = Osd(self)
        self.controller.subscribe(self.osd.show_changes)

    def _settings_actions(self) -> SettingsActions:
        from monitorcontrol.autostart import DEFAULT_DIR as AUTOSTART_DIR
        from monitorcontrol.config import DEFAULT_PATH
        from monitorcontrol.gnome_extension import DEFAULT_ROOT as EXT_ROOT
        from monitorcontrol.shortcuts import gnome_store

        return SettingsActions(
            self.config,
            config_path=DEFAULT_PATH,
            autostart_dir=AUTOSTART_DIR,
            extension_root=EXT_ROOT,
            shortcut_store=gnome_store(),
            on_applied=self._apply_config,
        )

    def _prompt_first_run(self) -> None:
        from monitorcontrol.firstrun import prompt_setup

        self._bootstrapping = True

        def chosen(choice: SetupChoice) -> None:
            self._run_bootstrap(choice)
            self._bootstrapping = False

        prompt_setup(
            self.win,
            chosen,
            on_gnome=running_on_gnome(),
            needs_i2c=self._needs_i2c(),
        )

    def _needs_i2c(self) -> bool:
        if self.controller is None:
            return False
        return any(
            not is_internal_connector(display.connector_type)
            for display in self.controller.displays
        )

    def _apply_config(self, config: Config) -> None:
        self.config = config
        if self.controller is not None:
            self.controller.step = config.step
            self.controller.sync = config.sync

    def _persist_sync(self, enabled: bool) -> None:
        if self.config.sync == enabled:
            return
        self._settings_actions().set_sync(enabled)

    def _run_bootstrap(self, choice: SetupChoice) -> None:
        actions = self._settings_actions()
        user = current_username()

        def grant() -> tuple[bool, str | None]:
            from monitorcontrol.paths import user_binary

            installed = user_binary()
            exe = str(installed) if installed.exists() else None
            return pkexec_grant(user, executable=exe)

        packaged = Path("/usr/bin/monitorcontrol")
        result = bootstrap(
            actions,
            grant_i2c=grant if choice.proceed else None,
            install_binary=None if packaged.is_file() else (lambda: str(install_user_binary())),
            on_gnome=running_on_gnome(),
            enable_extension=enable_extension,
            needs_i2c=self._needs_i2c(),
            choice=choice,
        )
        self.config = actions.config
        if self.controller is not None:
            self.controller.sync = self.config.sync
            self.controller.refresh()
        if self.win is not None:
            self.win.rebuild()
            if result.i2c_error and self.win._banner:
                self.win._banner.set_title(result.i2c_error)

    def _open_settings(self) -> None:
        from monitorcontrol.settings import SettingsDialog

        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(self._settings_actions())
        self._settings_dialog.present(self.win)

    def do_shutdown(self) -> None:
        if self._mutter is not None and self._follower is not None:
            handler = getattr(self._follower, "handler_id", None)
            if handler is not None:
                self._mutter.disconnect(handler)
            self._mutter = None
        if self._session is not None:
            self._session.close()
            self._session = None
        if self.controller is not None:
            self.controller.close()
            self.controller = None
        Adw.Application.do_shutdown(self)


def run_app(*, background: bool = False, config_path: Path | None = None) -> int:
    config = load_config(config_path) if config_path is not None else load_config()
    app = Application(show_window=not background, config=config)
    status = app.run(["monitorcontrol"])
    if app._export_failed:
        return 1
    return status
