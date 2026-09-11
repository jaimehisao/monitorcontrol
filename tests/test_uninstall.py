from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from monitorcontrol.autostart import DESKTOP_NAME as AUTOSTART_NAME
from monitorcontrol.autostart import install as install_autostart
from monitorcontrol.config import save, Config
from monitorcontrol.gnome_extension import UUID, add_enabled_uuid, install as install_ext
from monitorcontrol.launcher import DESKTOP_NAME, ICON_NAME, install as install_launcher
from monitorcontrol.shortcuts import MemoryShortcutStore, install as install_keys, installed_paths
from monitorcontrol.uninstall import report, run


class FakeSettings:
    def __init__(self, values: list[str]) -> None:
        self.values = list(values)

    def get_strv(self, key: str) -> list[str]:
        return list(self.values)

    def set_strv(self, key: str, values: list[str]) -> None:
        self.values = list(values)


class Proc:
    returncode = 0


class UninstallTests(unittest.TestCase):
    def test_removes_user_session_files(self) -> None:
        with TemporaryDirectory() as raw:
            root = Path(raw)
            store = MemoryShortcutStore()
            install_keys(store, program="mc")
            install_autostart(root / "autostart", program="/opt/mc")
            install_launcher("/opt/mc", apps=root / "apps", icons=root / "icons")
            install_ext(root / "ext")
            binary = root / "bin" / "monitorcontrol"
            binary.parent.mkdir()
            binary.write_text("#!/bin/sh\n", encoding="utf-8")
            config = root / "config" / "config.json"
            save(Config(setup_complete=True), config)
            settings = FakeSettings(add_enabled_uuid([]))

            result = run(
                shortcut_store=store,
                autostart_dir=root / "autostart",
                apps_dir=root / "apps",
                icons_dir=root / "icons",
                extension_root=root / "ext",
                binary_path=binary,
                config_path=config,
                settings=settings,
                runner=lambda *_a, **_k: Proc(),
            )
            self.assertTrue(result.shortcuts)
            self.assertTrue(result.autostart)
            self.assertTrue(result.launcher)
            self.assertTrue(result.extension)
            self.assertTrue(result.binary)
            self.assertTrue(result.config)
            self.assertEqual(installed_paths(store), [])
            self.assertFalse((root / "autostart" / AUTOSTART_NAME).exists())
            self.assertFalse((root / "apps" / DESKTOP_NAME).exists())
            self.assertFalse((root / "icons" / ICON_NAME).exists())
            self.assertFalse((root / "ext" / UUID).exists())
            self.assertFalse(binary.exists())
            self.assertFalse(config.exists())
            self.assertNotIn(UUID, settings.values)
            text = "\n".join(report(result))
            self.assertIn("removed", text)
            self.assertIn("Quit MonitorControl", text)

    def test_keep_config(self) -> None:
        with TemporaryDirectory() as raw:
            root = Path(raw)
            config = root / "config.json"
            save(Config(step=8), config)
            result = run(
                shortcut_store=MemoryShortcutStore(),
                autostart_dir=root / "autostart",
                apps_dir=root / "apps",
                icons_dir=root / "icons",
                extension_root=root / "ext",
                binary_path=root / "no-binary",
                config_path=config,
                keep_config=True,
                settings=FakeSettings([]),
                runner=lambda *_a, **_k: Proc(),
            )
            self.assertFalse(result.config)
            self.assertTrue(config.exists())

    def test_absent_paths_are_ok(self) -> None:
        with TemporaryDirectory() as raw:
            root = Path(raw)
            result = run(
                shortcut_store=MemoryShortcutStore(),
                autostart_dir=root / "autostart",
                apps_dir=root / "apps",
                icons_dir=root / "icons",
                extension_root=root / "ext",
                binary_path=root / "missing",
                config_path=root / "missing.json",
                settings=FakeSettings([]),
                runner=lambda *_a, **_k: Proc(),
            )
            self.assertFalse(result.autostart)
            self.assertFalse(result.launcher)
            self.assertFalse(result.extension)
            self.assertFalse(result.binary)
            self.assertFalse(result.config)


if __name__ == "__main__":
    unittest.main()
