#!/usr/bin/env python3
"""Build an unsigned noble source package from the canonical source archive."""

from __future__ import annotations

import argparse
from email.utils import formatdate
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib


class PPAError(RuntimeError):
    pass


def ppa_version(version: str) -> str:
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version):
        raise PPAError(f"invalid upstream version {version!r}")
    return f"{version}-1ppa1~noble1"


def noble_changelog(current: str, version: str, timestamp: int | None = None) -> str:
    if not re.match(r"^monitorcontrol \([^)]+\) \S+; urgency=", current):
        raise PPAError("cannot recognize debian/changelog header")
    entry = (
        f"monitorcontrol ({ppa_version(version)}) noble; urgency=medium\n\n"
        "  * Build immutable noble release from the canonical source archive.\n\n"
        " -- MonitorControl contributors <jaimehisao@users.noreply.github.com>  "
        f"{formatdate(timestamp, localtime=False, usegmt=True)}\n\n"
    )
    return entry + current


def build(archive: Path, output: Path) -> list[Path]:
    archive = archive.resolve()
    output = output.resolve()
    with tempfile.TemporaryDirectory(prefix="monitorcontrol-ppa.") as temporary:
        work = Path(temporary)
        with tarfile.open(archive, "r:gz") as source:
            source.extractall(work, filter="data")
        roots = [path for path in work.iterdir() if path.is_dir()]
        if len(roots) != 1:
            raise PPAError("canonical archive must contain exactly one source root")
        source_root = roots[0]
        pyproject = tomllib.loads((source_root / "pyproject.toml").read_text())
        version = str(pyproject["project"]["version"])
        expected_root = f"monitorcontrol-{version}"
        if source_root.name != expected_root:
            raise PPAError(f"expected archive root {expected_root!r}")

        changelog = source_root / "debian/changelog"
        changelog.write_text(
            noble_changelog(changelog.read_text(encoding="utf-8"), version),
            encoding="utf-8",
        )

        upstream = work / "upstream" / expected_root
        shutil.copytree(source_root, upstream)
        shutil.rmtree(upstream / "debian")
        orig = work / f"monitorcontrol_{version}.orig.tar.gz"
        with tarfile.open(orig, "w:gz") as target:
            target.add(upstream, arcname=expected_root)

        result = subprocess.run(
            ["dpkg-buildpackage", "--no-sign", "-S"],
            cwd=source_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise PPAError(result.stderr.strip() or "dpkg-buildpackage failed")

        package_version = ppa_version(version)
        patterns = (
            f"monitorcontrol_{version}.orig.tar.gz",
            f"monitorcontrol_{package_version}.dsc",
            f"monitorcontrol_{package_version}.debian.tar.*",
            f"monitorcontrol_{package_version}_source.changes",
            f"monitorcontrol_{package_version}_source.buildinfo",
        )
        matches: list[Path] = []
        for pattern in patterns:
            found = list(work.glob(pattern))
            if len(found) != 1:
                raise PPAError(f"expected one {pattern}, found {len(found)}")
            matches.append(found[0])
        output.mkdir(parents=True, exist_ok=True)
        copied = []
        for path in matches:
            destination = output / path.name
            shutil.copy2(path, destination)
            copied.append(destination)
        return copied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    try:
        for artifact in build(args.archive, args.output):
            print(artifact)
    except (OSError, KeyError, tomllib.TOMLDecodeError, PPAError) as error:
        print(f"PPA preparation error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
