"""Integration tests for the dependency-free release build wrapper."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).parents[1]


class BuildReleaseTest(unittest.TestCase):
    def test_build_uses_committed_tree_for_canonical_source_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            scripts = repository / "scripts"
            scripts.mkdir()
            shutil.copy2(ROOT / "scripts/build-release.sh", scripts)
            (scripts / "release.py").write_text("# test stub\n", encoding="utf-8")
            (repository / "pyproject.toml").write_text(
                '[project]\nname = "monitorcontrol"\nversion = "1.2.3"\n',
                encoding="utf-8",
            )
            (repository / "tracked.txt").write_text("tracked\n", encoding="utf-8")

            fake_python = repository / "fake-python"
            fake_python.write_text(
                "#!/bin/sh\n"
                "set -eu\n"
                'if [ "$1" = "scripts/release.py" ]; then exit 0; fi\n'
                'if [ "$1" = "-c" ]; then echo 1.2.3; exit 0; fi\n'
                'if [ "$1" = "-m" ] && [ "$2" = "build" ]; then\n'
                "  mkdir -p dist\n"
                "  : > dist/monitorcontrol-1.2.3-py3-none-any.whl\n"
                "  : > dist/monitorcontrol-1.2.3.tar.gz\n"
                "  exit 0\n"
                "fi\n"
                'echo "unexpected fake Python arguments: $*" >&2\n'
                "exit 1\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)

            self._git(repository, "init", "-q")
            self._git(repository, "add", ".")
            self._git(
                repository,
                "-c",
                "user.name=Release Test",
                "-c",
                "user.email=release@example.invalid",
                "commit",
                "-qm",
                "fixture",
            )
            (repository / "untracked.txt").write_text(
                "must not be archived\n", encoding="utf-8"
            )

            environment = os.environ.copy()
            environment["PYTHON"] = str(fake_python)
            subprocess.run(
                ["bash", "scripts/build-release.sh"],
                cwd=repository,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )

            archive = repository / "dist/monitorcontrol-1.2.3-source.tar.gz"
            with tarfile.open(archive, "r:gz") as source:
                names = source.getnames()
            self.assertIn("monitorcontrol-1.2.3/tracked.txt", names)
            self.assertNotIn("monitorcontrol-1.2.3/untracked.txt", names)
            self.assertTrue(
                all(
                    name == "monitorcontrol-1.2.3"
                    or name.startswith("monitorcontrol-1.2.3/")
                    for name in names
                )
            )

            checksums = (repository / "dist/SHA256SUMS").read_text(
                encoding="utf-8"
            )
            self.assertEqual(len(checksums.splitlines()), 3)
            self.assertNotIn("monitorcontrol-1.2.3-linux", checksums)

    @staticmethod
    def _git(repository: Path, *arguments: str) -> None:
        subprocess.run(
            ["git", *arguments],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
