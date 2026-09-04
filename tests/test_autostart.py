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

        missing = Path("/tmp/monitorcontrol-not-installed")
        with patch("monitorcontrol.paths.user_binary", return_value=missing), patch(
            "monitorcontrol.paths.shutil.which", return_value="/usr/bin/monitorcontrol"
        ):
            self.assertEqual(cli_command(), "/usr/bin/monitorcontrol")

    def test_install_user_wrapper(self) -> None:
        from unittest.mock import patch

        from monitorcontrol.paths import install_user_binary

        with TemporaryDirectory() as raw:
            bindir = Path(raw) / "bin"
            with patch("monitorcontrol.paths.user_bin_dir", return_value=bindir):
                dest = install_user_binary()
            self.assertTrue(dest.exists())
            text = dest.read_text(encoding="utf-8")
            self.assertIn("-m monitorcontrol", text)
            self.assertTrue(dest.stat().st_mode & 0o100)

    def test_frozen_binary_copy_and_cli(self) -> None:
        from unittest.mock import patch

        from monitorcontrol.paths import cli_command, install_user_binary

        with TemporaryDirectory() as raw:
            orig = Path(raw) / "orig"
            orig.write_bytes(b"ELF")
            orig.chmod(0o755)
            bindir = Path(raw) / "bin"
            with patch("monitorcontrol.paths.is_frozen", return_value=True), patch(
                "monitorcontrol.paths.sys"
            ) as sysmod, patch("monitorcontrol.paths.user_bin_dir", return_value=bindir):
                sysmod.executable = str(orig)
                dest = install_user_binary()
                self.assertEqual(dest.read_bytes(), b"ELF")
            with patch("monitorcontrol.paths.user_binary", return_value=Path("/no-user-bin")), patch(
                "monitorcontrol.paths.is_frozen", return_value=True
            ), patch("monitorcontrol.paths.sys") as sysmod:
                sysmod.executable = "/opt/monitorcontrol"
                self.assertEqual(cli_command(), "/opt/monitorcontrol")


if __name__ == "__main__":
    unittest.main()
