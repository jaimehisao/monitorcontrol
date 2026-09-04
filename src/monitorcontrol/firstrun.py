"""First-launch dialog. Logic stays in bootstrap; this is only GTK."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

BODY = (
    "MonitorControl will ask for admin permission once so it can talk to "
    "your displays over DDC/CI. After that it enables brightness keys, "
    "starts at login, and adds a slider to GNOME Quick Settings."
)


def prompt_setup(parent: Gtk.Widget | None, on_choice: Callable[[bool], None]) -> None:
    dialog = Adw.AlertDialog()
    dialog.set_heading("Set up MonitorControl")
    dialog.set_body(BODY)
    dialog.add_response("later", "Later")
    dialog.add_response("setup", "Continue")
    dialog.set_default_response("setup")
    dialog.set_close_response("later")
    dialog.set_response_appearance("setup", Adw.ResponseAppearance.SUGGESTED)

    def _respond(_dialog: Adw.AlertDialog, response: str) -> None:
        on_choice(response == "setup")

    dialog.connect("response", _respond)
    dialog.present(parent)
