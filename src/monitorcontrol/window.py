"""Compact Adwaita window with a slider per feature per display."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from monitorcontrol.controller import Controller
from monitorcontrol.display import Display
from monitorcontrol.permissions import SETUP_COMMANDS, permission_message
from monitorcontrol.vcp import FEATURE_LABELS, Feature

FEATURE_ICONS = {
    Feature.BRIGHTNESS: "display-brightness-symbolic",
    Feature.CONTRAST: "preferences-color-symbolic",
    Feature.AUDIO_SPEAKER_VOLUME: "audio-volume-high-symbolic",
}


def _icon_for(feature: Feature) -> str:
    return FEATURE_ICONS.get(feature, "video-display-symbolic")


class ControlWindow(Adw.ApplicationWindow):
    def __init__(self, application: Adw.Application, controller: Controller) -> None:
        super().__init__(application=application, title="MonitorControl")
        self.set_default_size(400, 280)
        self.controller = controller
        self.on_settings = None
        self.on_setup = None
        self._scales: dict[tuple[str, Feature], Gtk.Scale] = {}
        self._percent_labels: dict[tuple[str, Feature], Gtk.Label] = {}
        self._updating = False

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        refresh = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh.set_tooltip_text("Rescan displays")
        refresh.connect("clicked", self._on_refresh)
        header.pack_start(refresh)
        settings_btn = Gtk.Button.new_from_icon_name("emblem-system-symbolic")
        settings_btn.set_tooltip_text("Settings")
        settings_btn.connect("clicked", self._on_settings)
        header.pack_end(settings_btn)
        toolbar.add_top_bar(header)
        self.set_hide_on_close(True)

        self._banner = Adw.Banner()
        self._banner.set_button_label("Set up now")
        self._banner.connect("button-clicked", self._on_banner)

        self._list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self._list.set_margin_top(12)
        self._list.set_margin_bottom(18)
        self._list.set_margin_start(18)
        self._list.set_margin_end(18)

        self._status = Adw.StatusPage(
            icon_name="video-display-symbolic",
            title="No displays detected",
            description="Connect a monitor and press refresh.",
        )

        self._stack = Gtk.Stack()
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(self._list)
        self._stack.add_named(scrolled, "list")
        self._stack.add_named(self._status, "empty")

        self._sync = Adw.SwitchRow(
            title="Sync displays",
            subtitle="One slider sets every monitor that has that control",
        )
        self._sync.set_active(controller.sync)
        self._sync.connect("notify::active", self._on_sync)
        sync_group = Adw.PreferencesGroup()
        sync_group.add(self._sync)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(self._banner)
        content.append(self._stack)
        content.append(sync_group)
        toolbar.set_content(content)
        self.set_content(toolbar)
        self.rebuild()

    def rebuild(self) -> None:
        self._scales.clear()
        self._percent_labels.clear()
        while child := self._list.get_first_child():
            self._list.remove(child)

        message = permission_message()
        if message:
            self._banner.set_title(message)
            self._banner.set_revealed(True)
        else:
            self._banner.set_revealed(False)

        if not self.controller.displays:
            self._stack.set_visible_child_name("empty")
            return

        self._stack.set_visible_child_name("list")
        for display in self.controller.displays:
            self._list.append(self._display_card(display))

    def _display_card(self, display: Display) -> Gtk.Widget:
        group = Adw.PreferencesGroup()
        subtitle = display.connector_type
        if display.kind.value != "none":
            subtitle = f"{subtitle} · {display.kind.value}"
        group.set_title(display.name)
        group.set_description(subtitle)

        if display.warning and not display.features:
            label = Gtk.Label(label=display.warning, wrap=True, xalign=0)
            label.add_css_class("warning-label")
            group.add(label)
            return group

        for feature, state in display.features.items():
            group.add(self._feature_row(display, feature, state.percent))
        if display.warning:
            label = Gtk.Label(label=display.warning, wrap=True, xalign=0)
            label.add_css_class("warning-label")
            group.add(label)
        return group

    def _feature_row(self, display: Display, feature: Feature, percent: int) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.add_css_class("feature-row")
        icon = Gtk.Image.new_from_icon_name(_icon_for(feature))
        icon.set_tooltip_text(FEATURE_LABELS.get(feature, feature.name))
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        scale.set_draw_value(False)
        scale.set_hexpand(True)
        scale.set_value(percent)
        scale.connect(
            "value-changed",
            lambda widget, disp=display, feat=feature: self._on_scale(widget, disp, feat),
        )
        percent_label = Gtk.Label(label=f"{percent}%")
        percent_label.add_css_class("percent-label")
        percent_label.set_xalign(1)
        row.append(icon)
        row.append(scale)
        row.append(percent_label)
        key = (display.identity, feature)
        self._scales[key] = scale
        self._percent_labels[key] = percent_label
        return row

    def _on_scale(self, scale: Gtk.Scale, display: Display, feature: Feature) -> None:
        if self._updating:
            return
        percent = int(round(scale.get_value()))
        changes = self.controller.set_percent(
            display.identity, feature, percent, notify=False
        )
        self._updating = True
        try:
            for change in changes:
                key = (change.display.identity, change.feature)
                label = self._percent_labels.get(key)
                other = self._scales.get(key)
                if label is not None:
                    label.set_text(f"{change.state.percent}%")
                if other is not None and other is not scale:
                    other.set_value(change.state.percent)
            key = (display.identity, feature)
            if key in self._percent_labels:
                self._percent_labels[key].set_text(f"{percent}%")
        finally:
            self._updating = False

    def _on_sync(self, row: Adw.SwitchRow, _pspec: object) -> None:
        self.controller.sync = bool(row.get_active())

    def _on_settings(self, _button: Gtk.Button) -> None:
        if self.on_settings is not None:
            self.on_settings()

    def _on_refresh(self, _button: Gtk.Button) -> None:
        self.controller.refresh()
        self.rebuild()

    def _on_banner(self, _banner: Adw.Banner) -> None:
        if self.on_setup is not None:
            self.on_setup()
            return
        display = self.get_display()
        if display is None:
            return
        clipboard = display.get_clipboard()
        clipboard.set(SETUP_COMMANDS.strip() + "\n")
        self._banner.set_title("Setup commands copied — run them in a terminal, then log out.")
