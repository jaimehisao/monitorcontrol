"""GTK application: one window, one controller."""

from __future__ import annotations

from importlib import resources

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, Gtk  # noqa: E402

from monitorcontrol import APP_ID, APP_NAME
from monitorcontrol.controller import Controller
from monitorcontrol.osd import Osd
from monitorcontrol.window import ControlWindow


def _load_css() -> None:
    provider = Gtk.CssProvider()
    data = resources.files("monitorcontrol").joinpath("data/style.css").read_bytes()
    provider.load_from_data(data)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


class Application(Adw.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.set_application_name(APP_NAME)
        self.controller: Controller | None = None
        self.win: ControlWindow | None = None
        self.osd: Osd | None = None

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        _load_css()
        self.controller = Controller()
        self.controller.refresh()

    def do_activate(self) -> None:
        if self.win is None:
            assert self.controller is not None
            self.win = ControlWindow(self, self.controller)
            self.osd = Osd(self)
            self.controller.subscribe(self.osd.show_changes)
        self.win.present()

    def do_shutdown(self) -> None:
        if self.controller is not None:
            self.controller.close()
            self.controller = None
        Adw.Application.do_shutdown(self)


def run_app() -> int:
    app = Application()
    return app.run(["monitorcontrol"])
