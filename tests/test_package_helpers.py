"""Focused tests for package artifact selection."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
SELECT = ROOT / "scripts/select-package.sh"


class SelectPackageTest(unittest.TestCase):
    def run_select(self, directory: Path, pattern: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(SELECT), str(directory), pattern],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_prints_the_only_matching_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            package = directory / "monitorcontrol-1.0.0-1.noarch.rpm"
            package.touch()
            result = self.run_select(directory, "monitorcontrol-*.rpm")
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), str(package))

    def test_rejects_no_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = self.run_select(Path(temporary_directory), "*.deb")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("found 0", result.stderr)

    def test_rejects_multiple_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            (directory / "one.deb").touch()
            (directory / "two.deb").touch()
            result = self.run_select(directory, "*.deb")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("found 2", result.stderr)


if __name__ == "__main__":
    unittest.main()
