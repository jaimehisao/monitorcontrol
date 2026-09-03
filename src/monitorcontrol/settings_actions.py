"""Settings side effects, kept out of GTK so they can be tested."""

from __future__ import annotations

from pathlib import Path

from monitorcontrol import autostart, gnome_extension, shortcuts
from monitorcontrol.config import Config, save
from monitorcontrol.paths import cli_command
from monitorcontrol.shortcuts import MemoryShortcutStore, ShortcutStore


class SettingsActions:
    def __init__(
        self,
        config: Config,
        *,
        config_path: Path,
        autostart_dir: Path,
        extension_root: Path,
        shortcut_store: ShortcutStore | None = None,
        program: str | None = None,
    ) -> None:
        self.config = config
        self.config_path = config_path
        self.autostart_dir = autostart_dir
        self.extension_root = extension_root
        self.shortcut_store = shortcut_store or MemoryShortcutStore()
        self.program = program or cli_command()

    def persist(self) -> None:
        save(self.config, self.config_path)

    def set_step(self, step: int) -> None:
        self.config.step = step
        self.config = self.config.clamp()
        self.persist()

    def set_sync(self, enabled: bool) -> None:
        self.config.sync = enabled
        self.persist()

    def set_autostart(self, enabled: bool) -> None:
        self.config.autostart = enabled
        if enabled:
            autostart.install(self.autostart_dir, self.program)
        else:
            autostart.uninstall(self.autostart_dir)
        self.persist()

    def set_shortcuts(self, enabled: bool) -> None:
        self.config.shortcuts = enabled
        if enabled:
            shortcuts.install(
                self.shortcut_store,
                include_volume=self.config.volume_keys,
                program=self.program,
            )
        else:
            shortcuts.uninstall(self.shortcut_store)
        self.persist()

    def set_volume_keys(self, enabled: bool) -> None:
        self.config.volume_keys = enabled
        if self.config.shortcuts:
            shortcuts.install(
                self.shortcut_store,
                include_volume=enabled,
                program=self.program,
            )
        self.persist()

    def set_extension(self, enabled: bool) -> Path | None:
        if enabled:
            return gnome_extension.install(self.extension_root)
        gnome_extension.uninstall(self.extension_root)
        return None
