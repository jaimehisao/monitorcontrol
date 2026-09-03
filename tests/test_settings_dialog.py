from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

HAS_DISPLAY = bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))


@unittest.skipUnless(HAS_DISPLAY, "no graphical session")
class SettingsDialogTests(unittest.TestCase):
    def test_builds(self) -> None:
        from gi.repository import Adw

        from monitorcontrol.config import Config
        from monitorcontrol.settings import SettingsDialog
        from monitorcontrol.settings_actions import SettingsActions
        from monitorcontrol.shortcuts import MemoryShortcutStore

        Adw.init()
        with TemporaryDirectory() as raw:
            root = Path(raw)
            actions = SettingsActions(
                Config(),
                config_path=root / "c.json",
                autostart_dir=root / "a",
                extension_root=root / "e",
                shortcut_store=MemoryShortcutStore(),
                program="mc",
            )
            dialog = SettingsDialog(actions)
            self.assertEqual(dialog.get_title(), "MonitorControl")
            dialog._sync.set_active(True)
            dialog._on_step()
            dialog._autostart.set_active(True)
            dialog._shortcuts.set_active(True)
            dialog._volume.set_active(True)
            dialog._extension.set_active(True)
            dialog._extension.set_active(False)


if __name__ == "__main__":
    unittest.main()
