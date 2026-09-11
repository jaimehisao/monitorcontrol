from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from monitorcontrol.launcher import DESKTOP_NAME, ICON_NAME, desktop_text, install


class LauncherTests(unittest.TestCase):
    def test_rewrites_exec_to_the_installed_binary(self) -> None:
        text = desktop_text("/home/u/.local/bin/monitorcontrol")
        self.assertIn("Exec=/home/u/.local/bin/monitorcontrol", text)
        self.assertNotIn("Exec=monitorcontrol\n", text + "\n")

    def test_installs_desktop_and_icon(self) -> None:
        with TemporaryDirectory() as raw:
            root = Path(raw)
            apps = root / "applications"
            icons = root / "icons"
            dest = install("/opt/monitorcontrol", apps=apps, icons=icons)
            self.assertEqual(dest, apps / DESKTOP_NAME)
            self.assertIn("Exec=/opt/monitorcontrol", dest.read_text(encoding="utf-8"))
            self.assertTrue((icons / ICON_NAME).is_file())
            from monitorcontrol.launcher import uninstall

            self.assertTrue(uninstall(apps=apps, icons=icons))
            self.assertFalse((apps / DESKTOP_NAME).exists())
            self.assertFalse((icons / ICON_NAME).exists())
            self.assertFalse(uninstall(apps=apps, icons=icons))


if __name__ == "__main__":
    unittest.main()
