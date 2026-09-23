from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from monitorcontrol.bootstrap import SetupChoice, bootstrap, repair, running_on_gnome
from monitorcontrol.config import Config, load
from monitorcontrol.settings_actions import SettingsActions
from monitorcontrol.shortcuts import MemoryShortcutStore, installed_paths


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        root = Path(self.tmp.name)
        self.actions = SettingsActions(
            Config(),
            config_path=root / "config.json",
            autostart_dir=root / "autostart",
            extension_root=root / "extensions",
            shortcut_store=MemoryShortcutStore(),
            program="old",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_gnome_first_run_grants_and_enables(self) -> None:
        result = bootstrap(
            self.actions,
            grant_i2c=lambda: (True, None),
            install_binary=lambda: "/home/u/.local/bin/monitorcontrol",
            on_gnome=True,
            enable_extension=lambda: True,
            i2c_ready=False,
            choice=SetupChoice(proceed=True, autostart=True, shortcuts=True, extension=True),
        )
        self.assertTrue(result.i2c_ready)
        self.assertTrue(result.i2c_prompted)
        self.assertIsNone(result.i2c_error)
        self.assertTrue(result.autostart)
        self.assertTrue(result.shortcuts)
        self.assertTrue(result.extension)
        self.assertTrue(result.extension_enabled)
        self.assertEqual(result.binary, "/home/u/.local/bin/monitorcontrol")
        saved = load(self.actions.config_path)
        self.assertTrue(saved.setup_complete)
        self.assertTrue(saved.autostart)
        self.assertTrue(saved.shortcuts)
        self.assertGreaterEqual(len(installed_paths(self.actions.shortcut_store)), 2)

    def test_later_changes_nothing(self) -> None:
        result = bootstrap(
            self.actions,
            grant_i2c=lambda: (_ for _ in ()).throw(AssertionError("grant")),
            install_binary=lambda: (_ for _ in ()).throw(AssertionError("install")),
            on_gnome=True,
            i2c_ready=False,
            choice=SetupChoice(proceed=False),
        )
        self.assertFalse(result.i2c_prompted)
        self.assertFalse(result.autostart)
        self.assertFalse(result.setup_complete)
        self.assertFalse(self.actions.config_path.exists())

    def test_failed_i2c_is_not_marked_complete(self) -> None:
        result = bootstrap(
            self.actions,
            grant_i2c=lambda: (False, "dismissed"),
            install_binary=lambda: "/bin/monitorcontrol",
            on_gnome=False,
            i2c_ready=False,
            choice=SetupChoice(proceed=True, autostart=True, shortcuts=False, extension=False),
        )
        self.assertFalse(result.i2c_ready)
        self.assertEqual(result.i2c_error, "dismissed")
        self.assertFalse(result.setup_complete)
        self.assertFalse(load(self.actions.config_path).setup_complete)
        self.assertTrue(load(self.actions.config_path).autostart)

    def test_repair_restores_only_enabled_steps(self) -> None:
        self.actions.set_autostart(True)
        desktop = self.actions.autostart_dir / "dev.monitorcontrol.MonitorControl.desktop"
        desktop.unlink()
        repair(self.actions, on_gnome=False)
        self.assertTrue(desktop.is_file())
        self.assertFalse(self.actions.config.shortcuts)

    def test_detect_gnome(self) -> None:
        self.assertTrue(running_on_gnome({"XDG_CURRENT_DESKTOP": "GNOME"}))
        self.assertTrue(running_on_gnome({"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}))
        self.assertFalse(running_on_gnome({"XDG_CURRENT_DESKTOP": "KDE"}))
        self.assertFalse(running_on_gnome({}))


if __name__ == "__main__":
    unittest.main()
