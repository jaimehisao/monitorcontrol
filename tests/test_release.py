"""Tests for the release preparation and validation tool."""

from __future__ import annotations

import datetime as dt
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "release.py"
SPEC = importlib.util.spec_from_file_location("release_tool", SCRIPT)
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ReleaseToolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self._write_release_tree("1.0.0")

    def _write(self, relative_path: str, contents: str) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")

    def _write_release_tree(self, version: str) -> None:
        self._write(
            "pyproject.toml",
            f'[project]\nname = "monitorcontrol"\nversion = "{version}"\n',
        )
        self._write(
            "src/monitorcontrol/__init__.py", f'__version__ = "{version}"\n'
        )
        self._write(
            "packaging/rpm/monitorcontrol.spec",
            f"Name: monitorcontrol\nVersion:        {version}\n",
        )
        self._write(
            "debian/changelog",
            f"monitorcontrol ({version}-1) UNRELEASED; urgency=medium\n\n"
            "  * Previous release.\n\n"
            " -- MonitorControl contributors "
            "<jaimehisao@users.noreply.github.com>  "
            "Thu, 11 Sep 2026 00:00:00 +0000\n",
        )
        self._write(
            "CHANGELOG.md",
            "# Changelog\n\n## Unreleased\n\n- A user-visible change.\n\n"
            f"## [{version}] - 2026-09-11\n\n- Previous release.\n",
        )

    def test_check_accepts_matching_versions_and_tag(self) -> None:
        self.assertEqual(release.check(self.root, "v1.0.0"), "1.0.0")

    def test_check_uses_release_tag_from_environment(self) -> None:
        with mock.patch.dict("os.environ", {"GITHUB_REF_NAME": "v2.0.0"}):
            with self.assertRaisesRegex(release.ReleaseError, "does not match"):
                release.check(self.root)

    def test_check_reports_every_mismatched_surface(self) -> None:
        self._write(
            "packaging/rpm/monitorcontrol.spec",
            "Name: monitorcontrol\nVersion:        1.0.1\n",
        )
        with self.assertRaisesRegex(
            release.ReleaseError,
            r"packaging/rpm/monitorcontrol\.spec=1\.0\.1",
        ):
            release.check(self.root)

    def test_validate_version_rejects_non_semantic_version(self) -> None:
        for invalid in ("v1.2.3", "1.2", "1.2.3rc1", "01.2.3"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(release.ReleaseError):
                    release.validate_version(invalid)

    def test_prepare_updates_all_versions_and_changelogs(self) -> None:
        now = dt.datetime(2026, 9, 20, 7, 30, tzinfo=dt.timezone.utc)
        release.prepare(self.root, "1.1.0", now=now)

        self.assertEqual(release.check(self.root), "1.1.0")
        debian = (self.root / "debian/changelog").read_text(encoding="utf-8")
        self.assertTrue(
            debian.startswith(
                "monitorcontrol (1.1.0-1) UNRELEASED; urgency=medium"
            )
        )
        self.assertIn("Sun, 20 Sep 2026 07:30:00 +0000", debian)
        self.assertIn("monitorcontrol (1.0.0-1)", debian)

        changelog = (self.root / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(
            "## Unreleased\n\n- Add changes here.\n\n"
            "## [1.1.0] - 2026-09-20\n\n- A user-visible change.",
            changelog,
        )

    def test_prepare_failure_does_not_modify_files(self) -> None:
        pyproject = self.root / "pyproject.toml"
        before = pyproject.read_text(encoding="utf-8")
        self._write(
            "packaging/rpm/monitorcontrol.spec",
            "Name: monitorcontrol\nVersion:        invalid\n",
        )

        with self.assertRaises(release.ReleaseError):
            release.prepare(self.root, "1.1.0")

        self.assertEqual(pyproject.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
