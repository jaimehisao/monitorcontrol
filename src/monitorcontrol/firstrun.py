"""First-launch dialog. Logic stays in bootstrap; this is only GTK."""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from monitorcontrol.bootstrap import SetupChoice

BODY = (
    "External displays need one admin approval for DDC/CI. "
    "The options below are optional and only change MonitorControl. "
    "Later leaves your system as it is."
)


def prompt_setup(
    parent: Gtk.Widget | None,
    on_choice: Callable[[SetupChoice], None],
    *,
    on_gnome: bool = True,
    needs_i2c: bool = True,
) -> None:
    dialog = Adw.AlertDialog()
    dialog.set_heading("Set up MonitorControl")
    body = BODY if needs_i2c else (
        "Choose what MonitorControl may set up. Later leaves your system as it is."
    )
    dialog.set_body(body)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    autostart = Gtk.CheckButton(label="Start at login")
    autostart.set_active(True)
    shortcuts = Gtk.CheckButton(label="Brightness keys")
    shortcuts.set_active(True)
    extension = Gtk.CheckButton(label="GNOME Quick Settings slider")
    extension.set_active(on_gnome)
    extension.set_visible(on_gnome)
    box.append(autostart)
    box.append(shortcuts)
    box.append(extension)
    if hasattr(dialog, "set_extra_child"):
        dialog.set_extra_child(box)
    dialog.add_response("later", "Later")
    dialog.add_response("setup", "Continue")
    dialog.set_default_response("setup")
    dialog.set_close_response("later")
    dialog.set_response_appearance("setup", Adw.ResponseAppearance.SUGGESTED)

    def _respond(_dialog: Adw.AlertDialog, response: str) -> None:
        proceed = response == "setup"
        on_choice(
            SetupChoice(
                proceed=proceed,
                autostart=proceed and autostart.get_active(),
                shortcuts=proceed and shortcuts.get_active(),
                extension=proceed and on_gnome and extension.get_active(),
            )
        )

    dialog.connect("response", _respond)
    dialog.present(parent)
