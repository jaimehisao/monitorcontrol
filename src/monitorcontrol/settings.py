"""Preferences window: autostart, shortcuts, GNOME Quick Settings, step/sync."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from monitorcontrol.settings_actions import SettingsActions


class SettingsDialog(Adw.PreferencesDialog):
    def __init__(self, actions: SettingsActions) -> None:
        super().__init__()
        self.set_title("MonitorControl")
        self.actions = actions
        config = actions.config

        general = Adw.PreferencesPage(title="General", icon_name="preferences-system-symbolic")
        group = Adw.PreferencesGroup(title="Displays")
        self._sync = Adw.SwitchRow(
            title="Sync displays",
            subtitle="Keyboard and the GNOME brightness slider move every monitor that supports brightness",
        )
        self._sync.set_active(config.sync)
        self._sync.connect("notify::active", self._on_sync)
        self._step = Adw.SpinRow.new_with_range(1, 50, 1)
        self._step.set_title("Brightness step")
        self._step.set_subtitle("Percent change per key press")
        self._step.set_value(config.step)
        self._step.connect("notify::value", lambda *_args: self._on_step())
        group.add(self._sync)
        group.add(self._step)
        general.add(group)

        session = Adw.PreferencesGroup(title="Session")
        self._autostart = Adw.SwitchRow(
            title="Launch at login",
            subtitle="Keep the daemon running so keys and Quick Settings have somewhere to talk",
        )
        self._autostart.set_active(config.autostart)
        self._autostart.connect("notify::active", self._on_autostart)
        session.add(self._autostart)
        general.add(session)
        self.add(general)

        keyboard = Adw.PreferencesPage(title="Keyboard", icon_name="input-keyboard-symbolic")
        keys = Adw.PreferencesGroup(
            title="Media keys",
            description="Same idea as MonitorControl on macOS: brightness keys drive the external display. On a laptop GNOME already owns those keys; this is for desktops, and for laptops we also follow the built-in slider.",
        )
        self._shortcuts = Adw.SwitchRow(
            title="Bind brightness keys",
            subtitle="XF86MonBrightnessUp / Down → monitorcontrol brightness",
        )
        self._shortcuts.set_active(config.shortcuts)
        self._shortcuts.connect("notify::active", self._on_shortcuts)
        self._volume = Adw.SwitchRow(
            title="Bind volume keys to the monitor",
            subtitle="Leave off unless the display has speakers you actually use. System volume keeps the keys otherwise.",
        )
        self._volume.set_active(config.volume_keys)
        self._volume.connect("notify::active", self._on_volume)
        keys.add(self._shortcuts)
        keys.add(self._volume)
        keyboard.add(keys)
        self.add(keyboard)

        gnome = Adw.PreferencesPage(title="GNOME", icon_name="video-display-symbolic")
        qs = Adw.PreferencesGroup(
            title="Quick Settings",
            description="Installs a Shell extension that puts a brightness slider in the same Quick Settings menu Fedora already uses. Enable the extension after install (GNOME may ask you to log out).",
        )
        self._extension = Adw.SwitchRow(
            title="Quick Settings brightness slider",
            subtitle="monitorcontrol@monitorcontrol.dev",
        )
        self._extension.set_active(False)
        self._extension.connect("notify::active", self._on_extension)
        qs.add(self._extension)
        gnome.add(qs)
        self.add(gnome)

    def _on_sync(self, row: Adw.SwitchRow, _pspec: object) -> None:
        self.actions.set_sync(bool(row.get_active()))

    def _on_step(self, *_args: object) -> None:
        self.actions.set_step(int(self._step.get_value()))

    def _on_autostart(self, row: Adw.SwitchRow, _pspec: object) -> None:
        self.actions.set_autostart(bool(row.get_active()))

    def _on_shortcuts(self, row: Adw.SwitchRow, _pspec: object) -> None:
        self.actions.set_shortcuts(bool(row.get_active()))

    def _on_volume(self, row: Adw.SwitchRow, _pspec: object) -> None:
        self.actions.set_volume_keys(bool(row.get_active()))

    def _on_extension(self, row: Adw.SwitchRow, _pspec: object) -> None:
        self.actions.set_extension(bool(row.get_active()))
