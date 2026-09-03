from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from monitorcontrol.autostart import desktop_contents, install, is_installed, uninstall
from monitorcontrol.paths import cli_command, package_src_root


class AutostartTests(unittest.TestCase):
    def test_install_and_remove(self) -> None:
        with TemporaryDirectory() as raw:
            directory = Path(raw)
            path = install(directory, program="/usr/bin/monitorcontrol")
            self.assertTrue(is_installed(directory))
            text = path.read_text(encoding="utf-8")
            self.assertIn("Exec=/usr/bin/monitorcontrol --background", text)
            self.assertIn("X-GNOME-Autostart-enabled=true", text)
            self.assertTrue(uninstall(directory))
            self.assertFalse(is_installed(directory))
            self.assertFalse(uninstall(directory))

    def test_default_command_mentions_module_or_binary(self) -> None:
        text = desktop_contents()
        self.assertIn("--background", text)
        cmd = cli_command()
        self.assertTrue("monitorcontrol" in cmd)
        self.assertTrue(package_src_root().joinpath("monitorcontrol").is_dir())

    def test_installed_binary_path(self) -> None:
        from unittest.mock import patch

        with patch("monitorcontrol.paths.shutil.which", return_value="/usr/bin/monitorcontrol"):
            self.assertEqual(cli_command(), "/usr/bin/monitorcontrol")


if __name__ == "__main__":
    unittest.main()
