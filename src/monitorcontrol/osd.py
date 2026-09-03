"""On-screen HUD for brightness and volume changes.

GNOME on Wayland will not let us pick a pixel position, so this is a small
undecorated window the compositor places. Rapid updates reuse the same
window and reset the hide timer, like the macOS OSD.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import GLib, Gtk  # noqa: E402

from monitorcontrol.controller import Change
from monitorcontrol.vcp import Feature
from monitorcontrol.window import _icon_for

HIDE_MS = 1500


class Osd:
    def __init__(self, application: Gtk.Application) -> None:
        self._hide_id: int | None = None
        self.win = Gtk.Window(
            application=application,
            title="",
            decorated=False,
            resizable=False,
        )
        self.win.add_css_class("osd-window")
        self.win.set_default_size(260, 72)
        self.win.set_hide_on_close(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.icon = Gtk.Image.new_from_icon_name("display-brightness-symbolic")
        self.icon.set_pixel_size(28)
        self.label = Gtk.Label(label="0%")
        self.label.add_css_class("osd-percent")
        self.label.set_xalign(1)
        self.label.set_hexpand(True)
        row.append(self.icon)
        row.append(self.label)
        self.bar = Gtk.LevelBar()
        self.bar.set_min_value(0)
        self.bar.set_max_value(100)
        box.append(row)
        box.append(self.bar)
        self.win.set_child(box)

    def show_changes(self, changes: list[Change]) -> None:
        if not changes:
            return
        change = changes[0]
        self.show(change.feature, change.state.percent)

    def show(self, feature: Feature, percent: int) -> None:
        percent = max(0, min(100, int(percent)))
        self.icon.set_from_icon_name(_icon_for(feature))
        self.label.set_text(f"{percent}%")
        self.bar.set_value(percent)
        self.win.present()
        if self._hide_id is not None:
            GLib.source_remove(self._hide_id)
        self._hide_id = GLib.timeout_add(HIDE_MS, self._hide)

    def _hide(self) -> bool:
        self._hide_id = None
        self.win.set_visible(False)
        return False
