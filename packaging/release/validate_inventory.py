#!/usr/bin/env python3
"""Validate release artifacts against a complete, duplicate-free inventory."""

from __future__ import annotations

import argparse
from fnmatch import fnmatch
import json
from pathlib import Path
import sys


class InventoryError(RuntimeError):
    pass


def expected_patterns(version: str, stage: str) -> list[str]:
    python = [
        f"python/monitorcontrol_linux-{version}-py3-none-any.whl",
        f"python/monitorcontrol_linux-{version}.tar.gz",
        f"python/monitorcontrol-{version}-source.tar.gz",
    ]
    native = [
        f"fedora-43/rpm/monitorcontrol-{version}-*.fc43.noarch.rpm",
        f"fedora-43/srpm/monitorcontrol-{version}-*.fc43.src.rpm",
        f"fedora-44/rpm/monitorcontrol-{version}-*.fc44.noarch.rpm",
        f"fedora-44/srpm/monitorcontrol-{version}-*.fc44.src.rpm",
        f"debian-13/binary/monitorcontrol_{version}-*_all.deb",
        f"debian-13/binary/monitorcontrol_{version}-*_all.changes",
        f"debian-13/binary/monitorcontrol_{version}-*_all.buildinfo",
        f"debian-13/source/monitorcontrol_{version}.orig.tar.gz",
        f"debian-13/source/monitorcontrol_{version}-*.dsc",
        f"debian-13/source/monitorcontrol_{version}-*.debian.tar.*",
        f"debian-13/source/monitorcontrol_{version}-*_source.changes",
        f"debian-13/source/monitorcontrol_{version}-*_source.buildinfo",
    ]
    noble = [
        f"noble/monitorcontrol_{version}.orig.tar.gz",
        f"noble/monitorcontrol_{version}-1ppa1~noble1.dsc",
        f"noble/monitorcontrol_{version}-1ppa1~noble1.debian.tar.*",
        f"noble/monitorcontrol_{version}-1ppa1~noble1_source.changes",
        f"noble/monitorcontrol_{version}-1ppa1~noble1_source.buildinfo",
    ]
    if stage == "build":
        return python + native + noble
    if stage == "release":
        return [
            *(Path(item).name for item in python),
            f"monitorcontrol-{version}-*.fc43.noarch.rpm",
            f"monitorcontrol-{version}-*.fc43.src.rpm",
            f"monitorcontrol-{version}-*.fc44.noarch.rpm",
            f"monitorcontrol-{version}-*.fc44.src.rpm",
            f"monitorcontrol_{version}-*_all.deb",
            *(Path(item).name for item in noble),
            f"monitorcontrol-{version}.spdx.json",
            "SHA256SUMS",
            "provenance.bundle.json",
            "provenance.json",
        ]
    raise InventoryError(f"unknown inventory stage {stage!r}")


def validate(root: Path, version: str, stage: str) -> list[Path]:
    files = sorted(path for path in root.rglob("*") if path.is_file())
    relative = [path.relative_to(root).as_posix() for path in files]
    forbidden = (".AppImage", ".pex", ".pyz", ".zip")
    standalone = [name for name in relative if name.endswith(forbidden)]
    if standalone:
        raise InventoryError(
            "standalone binary artifacts are forbidden: " + ", ".join(standalone)
        )

    patterns = expected_patterns(version, stage)
    matched: dict[str, str] = {}
    for pattern in patterns:
        candidates = [name for name in relative if fnmatch(name, pattern)]
        if len(candidates) != 1:
            raise InventoryError(
                f"expected exactly one {pattern!r}, found {len(candidates)}"
            )
        matched[pattern] = candidates[0]
    expected = set(matched.values())
    unexpected = sorted(set(relative) - expected)
    if unexpected:
        raise InventoryError("unexpected artifacts: " + ", ".join(unexpected))
    if stage == "release":
        basenames: dict[str, str] = {}
        for name in relative:
            basename = Path(name).name
            if basename in basenames:
                raise InventoryError(
                    f"duplicate artifact basename {basename!r}: "
                    f"{basenames[basename]}, {name}"
                )
            basenames[basename] = name
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("version")
    parser.add_argument("--stage", choices=("build", "release"), default="build")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        files = validate(args.root, args.version, args.stage)
        if args.manifest:
            args.manifest.write_text(
                json.dumps(
                    [path.relative_to(args.root).as_posix() for path in files],
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
    except (OSError, InventoryError) as error:
        print(f"inventory error: {error}", file=sys.stderr)
        return 1
    print(f"Validated {len(files)} {args.stage} artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
