"""Install GNOME custom keybindings for brightness (and optional volume).

GNOME Shell 49+ binds XF86MonBrightness* itself and no-ops on a desktop
with no kernel backlight. Custom media-key commands never fire unless
those shell bindings are cleared. Volume keys stay with PipeWire unless
the user opts in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from monitorcontrol.paths import cli_command

BRIGHTNESS_UP = "monitorcontrol-brightness-up"
BRIGHTNESS_DOWN = "monitorcontrol-brightness-down"
VOLUME_UP = "monitorcontrol-volume-up"
VOLUME_DOWN = "monitorcontrol-volume-down"
VOLUME_MUTE = "monitorcontrol-volume-mute"

PATH_PREFIX = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"
SHELL_SCHEMA = "org.gnome.shell.keybindings"
SHELL_BRIGHTNESS_KEYS = (
    "screen-brightness-up",
    "screen-brightness-down",
    "screen-brightness-up-monitor",
    "screen-brightness-down-monitor",
    "screen-brightness-cycle",
    "screen-brightness-cycle-monitor",
)


@dataclass(frozen=True)
class Binding:
    key: str
    name: str
    accel: str
    args: tuple[str, ...]
    volume: bool = False

    @property
    def path(self) -> str:
        return f"{PATH_PREFIX}{self.key}/"


BINDINGS: tuple[Binding, ...] = (
    Binding(BRIGHTNESS_UP, "MonitorControl brightness up", "XF86MonBrightnessUp", ("brightness", "up")),
    Binding(
        BRIGHTNESS_DOWN,
        "MonitorControl brightness down",
        "XF86MonBrightnessDown",
        ("brightness", "down"),
    ),
    Binding(
        VOLUME_UP,
        "MonitorControl volume up",
        "XF86AudioRaiseVolume",
        ("volume", "up"),
        volume=True,
    ),
    Binding(
        VOLUME_DOWN,
        "MonitorControl volume down",
        "XF86AudioLowerVolume",
        ("volume", "down"),
        volume=True,
    ),
)


class ShortcutStore(Protocol):
    def get_paths(self) -> list[str]: ...
    def set_paths(self, paths: list[str]) -> None: ...
    def write(self, path: str, name: str, command: str, accel: str) -> None: ...
    def drop(self, path: str) -> None: ...
    def inhibit_shell_brightness(self) -> None: ...
    def restore_shell_brightness(self) -> None: ...


class MemoryShortcutStore:
    """In-memory stand-in for GNOME's custom-keybinding schemas."""

    def __init__(self, paths: list[str] | None = None) -> None:
        self.paths = list(paths or [])
        self.entries: dict[str, dict[str, str]] = {}
        self.shell_brightness_inhibited = False

    def get_paths(self) -> list[str]:
        return list(self.paths)

    def set_paths(self, paths: list[str]) -> None:
        self.paths = list(paths)

    def write(self, path: str, name: str, command: str, accel: str) -> None:
        self.entries[path] = {"name": name, "command": command, "binding": accel}

    def drop(self, path: str) -> None:
        self.entries.pop(path, None)

    def inhibit_shell_brightness(self) -> None:
        self.shell_brightness_inhibited = True

    def restore_shell_brightness(self) -> None:
        self.shell_brightness_inhibited = False


def _wanted(include_volume: bool) -> tuple[Binding, ...]:
    if include_volume:
        return BINDINGS
    return tuple(b for b in BINDINGS if not b.volume)


def command_for(binding: Binding, program: str | None = None) -> str:
    base = program or cli_command()
    return " ".join([base, *binding.args])


def install(
    store: ShortcutStore,
    *,
    include_volume: bool = False,
    program: str | None = None,
) -> list[str]:
    # Shell must release XF86MonBrightness* before gsd-media-keys can
    # GrabAccelerator. Writing custom keys first (first-run used to)
    # fails the grab, and gsd never retries.
    store.inhibit_shell_brightness()
    paths = store.get_paths()
    ours = {binding.path for binding in BINDINGS}
    kept = [path for path in paths if path not in ours]
    added: list[str] = []
    wanted = _wanted(include_volume)
    for binding in wanted:
        command = command_for(binding, program)
        # Empty then set so gsd-media-keys re-grabs when this is a reinstall.
        store.write(binding.path, binding.name, command, "")
        store.write(binding.path, binding.name, command, binding.accel)
        kept.append(binding.path)
        added.append(binding.path)
    # Drop volume bindings if the user turned that off.
    for binding in BINDINGS:
        if binding.volume and not include_volume:
            store.drop(binding.path)
    store.set_paths(kept)
    return added


def uninstall(store: ShortcutStore) -> list[str]:
    ours = {binding.path for binding in BINDINGS}
    removed = [path for path in store.get_paths() if path in ours]
    store.set_paths([path for path in store.get_paths() if path not in ours])
    for path in removed:
        store.drop(path)
    store.restore_shell_brightness()
    return removed


def gnome_store() -> ShortcutStore:
    """Live GNOME custom-keybinding store. Imported lazily so tests stay fake."""
    import gi

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio

    class GSettingsShortcutStore:
        schema = "org.gnome.settings-daemon.plugins.media-keys"
        child = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"

        def get_paths(self) -> list[str]:
            return list(Gio.Settings.new(self.schema).get_strv("custom-keybindings"))

        def set_paths(self, paths: list[str]) -> None:
            Gio.Settings.new(self.schema).set_strv("custom-keybindings", paths)

        def write(self, path: str, name: str, command: str, accel: str) -> None:
            settings = Gio.Settings.new_with_path(self.child, path)
            settings.set_string("name", name)
            settings.set_string("command", command)
            settings.set_string("binding", accel)

        def drop(self, path: str) -> None:
            settings = Gio.Settings.new_with_path(self.child, path)
            settings.reset("name")
            settings.reset("command")
            settings.reset("binding")

        def _shell_settings(self):
            try:
                return Gio.Settings.new(SHELL_SCHEMA)
            except Exception:
                return None

        def inhibit_shell_brightness(self) -> None:
            settings = self._shell_settings()
            if settings is None:
                return
            known = set(settings.list_keys())
            for key in SHELL_BRIGHTNESS_KEYS:
                if key in known:
                    settings.set_strv(key, [])

        def restore_shell_brightness(self) -> None:
            settings = self._shell_settings()
            if settings is None:
                return
            known = set(settings.list_keys())
            for key in SHELL_BRIGHTNESS_KEYS:
                if key in known:
                    settings.reset(key)

    return GSettingsShortcutStore()


def installed_paths(store: ShortcutStore) -> list[str]:
    ours = {binding.path for binding in BINDINGS}
    return [path for path in store.get_paths() if path in ours]
