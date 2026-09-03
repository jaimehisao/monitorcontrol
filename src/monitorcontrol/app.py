"""GTK application: daemon + window + GNOME brightness follow."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from monitorcontrol import APP_ID, APP_NAME
from monitorcontrol.config import Config, load as load_config
from monitorcontrol.controller import Controller
from monitorcontrol.dbus import export_session, own_bus_name
from monitorcontrol.gnome_backlight import NativeBrightnessFollower, apply_native_percent, attach_mutter
from monitorcontrol.osd import Osd
from monitorcontrol.service import MonitorService
from monitorcontrol.settings_actions import SettingsActions
from monitorcontrol.window import ControlWindow


def _load_css() -> None:
    provider = Gtk.CssProvider()
    data = resources.files("monitorcontrol").joinpath("data/style.css").read_bytes()
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

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        _load_css()
        self.hold()
        self.controller = Controller(step=self.config.step, sync=self.config.sync)
        self.controller.refresh()
        self.service = MonitorService(self.controller)
        try:
            export_session(self.service)
            own_bus_name()
        except Exception:
            pass
        follower = NativeBrightnessFollower(
            lambda percent: apply_native_percent(self.controller, percent)
        )
        try:
            attach_mutter(follower)
        except Exception:
            pass

    def do_activate(self) -> None:
        self._ensure_window()
        if self._show_window and self.win is not None:
            self.win.present()
        self._show_window = True

    def _ensure_window(self) -> None:
        if self.win is not None:
            return
        assert self.controller is not None
        self.win = ControlWindow(self, self.controller)
        self.win.on_settings = self._open_settings
        self.osd = Osd(self)
        self.controller.subscribe(self.osd.show_changes)

    def _open_settings(self) -> None:
        from monitorcontrol.autostart import DEFAULT_DIR as AUTOSTART_DIR
        from monitorcontrol.config import DEFAULT_PATH
        from monitorcontrol.gnome_extension import DEFAULT_ROOT as EXT_ROOT
        from monitorcontrol.settings import SettingsDialog
        from monitorcontrol.shortcuts import gnome_store

        if self._settings_dialog is None:
            actions = SettingsActions(
                self.config,
                config_path=DEFAULT_PATH,
                autostart_dir=AUTOSTART_DIR,
                extension_root=EXT_ROOT,
                shortcut_store=gnome_store(),
            )
            self._settings_dialog = SettingsDialog(actions)
        self._settings_dialog.present(self.win)

    def do_shutdown(self) -> None:
        if self.controller is not None:
            self.controller.close()
            self.controller = None
        Adw.Application.do_shutdown(self)


def run_app(*, background: bool = False, config_path: Path | None = None) -> int:
    config = load_config(config_path) if config_path is not None else load_config()
    app = Application(show_window=not background, config=config)
    return app.run(["monitorcontrol"])
