from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from monitorcontrol.config import Config, load
from monitorcontrol.settings_actions import SettingsActions
from monitorcontrol.shortcuts import MemoryShortcutStore, installed_paths
from monitorcontrol.gnome_extension import is_installed as ext_installed


class SettingsActionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        root = Path(self.tmp.name)
        self.config_path = root / "config.json"
        self.autostart = root / "autostart"
        self.ext = root / "extensions"
        self.store = MemoryShortcutStore()
        self.actions = SettingsActions(
            Config(),
            config_path=self.config_path,
            autostart_dir=self.autostart,
            extension_root=self.ext,
            shortcut_store=self.store,
            program="monitorcontrol",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_toggles(self) -> None:
        self.actions.set_step(8)
        self.actions.set_sync(True)
        self.actions.set_autostart(True)
        self.actions.set_shortcuts(True)
        self.actions.set_volume_keys(True)
        dest = self.actions.set_extension(True)
        self.assertTrue(dest.is_dir())
        self.assertTrue(ext_installed(self.ext))
        self.assertTrue((self.autostart / "dev.monitorcontrol.MonitorControl.desktop").exists())
        self.assertEqual(len(installed_paths(self.store)), 4)
        saved = load(self.config_path)
        self.assertEqual(saved.step, 8)
        self.assertTrue(saved.sync)
        self.assertTrue(saved.volume_keys)

        self.actions.set_volume_keys(False)
        self.assertEqual(len(installed_paths(self.store)), 2)
        self.actions.set_shortcuts(False)
        self.assertEqual(installed_paths(self.store), [])
        self.actions.set_autostart(False)
        self.assertFalse((self.autostart / "dev.monitorcontrol.MonitorControl.desktop").exists())
        self.actions.set_extension(False)
        self.assertFalse(ext_installed(self.ext))


if __name__ == "__main__":
    unittest.main()
