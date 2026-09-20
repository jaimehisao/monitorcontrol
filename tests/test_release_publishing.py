"""Focused tests for protected release publishing helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).parents[1]


def load(name: str):
    path = ROOT / "packaging" / "release" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inventory = load("validate_inventory")
ppa = load("prepare_ppa")
tag = load("validate_tag")
verify = load("verify_publications")


class PPAReleaseTest(unittest.TestCase):
    def test_noble_version_and_distribution_are_derived(self) -> None:
        self.assertEqual(ppa.ppa_version("1.2.3"), "1.2.3-1ppa1~noble1")
        changelog = (
            "monitorcontrol (1.2.3-1) UNRELEASED; urgency=medium\n\n"
            "  * Release.\n"
        )
        updated = ppa.noble_changelog(changelog, "1.2.3", timestamp=0)
        self.assertTrue(
            updated.startswith(
                "monitorcontrol (1.2.3-1ppa1~noble1) noble; urgency=medium"
            )
        )
        self.assertIn(changelog, updated)


class InventoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        replacements = {
            "*": "1",
        }
        for pattern in inventory.expected_patterns("1.2.3", "release"):
            name = pattern
            for old, new in replacements.items():
                name = name.replace(old, new)
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

    def test_accepts_exact_release_inventory(self) -> None:
        files = inventory.validate(self.root, "1.2.3", "release")
        self.assertEqual(len(files), len(inventory.expected_patterns("1.2.3", "release")))

    def test_python_distribution_filenames_use_normalized_name(self) -> None:
        patterns = inventory.expected_patterns("1.2.3", "release")
        self.assertIn(
            "monitorcontrol_linux-1.2.3-py3-none-any.whl", patterns
        )
        self.assertIn("monitorcontrol_linux-1.2.3.tar.gz", patterns)
        self.assertNotIn("monitorcontrol-1.2.3-py3-none-any.whl", patterns)

    def test_rejects_unexpected_standalone_artifact(self) -> None:
        (self.root / "monitorcontrol-1.2.3.pyz").touch()
        with self.assertRaisesRegex(inventory.InventoryError, "standalone"):
            inventory.validate(self.root, "1.2.3", "release")

    def test_rejects_missing_and_duplicate_artifacts(self) -> None:
        (self.root / "SHA256SUMS").unlink()
        with self.assertRaisesRegex(inventory.InventoryError, "found 0"):
            inventory.validate(self.root, "1.2.3", "release")


class PublicationVerificationTest(unittest.TestCase):
    def test_parses_launchpad_source_versions(self) -> None:
        sources = (
            "Package: other\nVersion: 9\n\n"
            "Package: monitorcontrol\nVersion: 1.2.3-1ppa1~noble1\n"
        )
        self.assertEqual(
            verify.parse_debian_sources(sources, "monitorcontrol"),
            {"1.2.3-1ppa1~noble1"},
        )

    def test_bounded_retry_stops_after_success(self) -> None:
        results = iter((False, False, True))
        sleeps = []
        verify.verify_with_retries(
            "test", lambda: next(results), 3, 0.25, sleep=sleeps.append
        )
        self.assertEqual(sleeps, [0.25, 0.25])

    def test_bounded_retry_has_rerunnable_failure(self) -> None:
        with self.assertRaisesRegex(verify.VerificationError, "rerun"):
            verify.verify_with_retries("test", lambda: False, 2, 0, sleep=lambda _: None)


class LocalTagValidationTest(unittest.TestCase):
    def test_rejects_lightweight_tag(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / "file").write_text("data", encoding="utf-8")
            subprocess.run(["git", "add", "file"], cwd=root, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.invalid",
                    "commit",
                    "-qm",
                    "test",
                ],
                cwd=root,
                check=True,
            )
            subprocess.run(["git", "tag", "v1.2.3"], cwd=root, check=True)
            with self.assertRaisesRegex(tag.TagError, "lightweight"):
                tag.validate_local(root, "v1.2.3", "HEAD")


if __name__ == "__main__":
    unittest.main()
