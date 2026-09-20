#!/usr/bin/env python3
"""Prepare and validate MonitorControl release versions."""

from __future__ import annotations

import argparse
import datetime as dt
from email.utils import format_datetime
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import tomllib


VERSION_COMPONENT = r"(?:0|[1-9][0-9]*)"
VERSION_RE = re.compile(
    rf"^{VERSION_COMPONENT}\.{VERSION_COMPONENT}\.{VERSION_COMPONENT}$"
)
DEBIAN_VERSION_RE = re.compile(
    r"\Amonitorcontrol \((?P<version>[0-9]+\.[0-9]+\.[0-9]+)(?:-[^)]+)?\)"
)
MAINTAINER = (
    "MonitorControl contributors <jaimehisao@users.noreply.github.com>"
)
UNRELEASED_PLACEHOLDER = "- Add changes here."
RELEASE_PLACEHOLDER = "- Describe notable changes for this release."
DISTRIBUTION_NAME = "monitorcontrol-linux"


class ReleaseError(ValueError):
    """A release file or argument is invalid."""


def validate_version(version: str) -> str:
    if not VERSION_RE.fullmatch(version):
        raise ReleaseError(
            f"invalid version {version!r}; expected semantic version X.Y.Z"
        )
    return version


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise ReleaseError(f"cannot read {path}: {error}") from error


def read_versions(root: Path) -> dict[str, str]:
    pyproject_path = root / "pyproject.toml"
    try:
        pyproject = tomllib.loads(_read(pyproject_path))
        pyproject_version = pyproject["project"]["version"]
    except (tomllib.TOMLDecodeError, KeyError, TypeError) as error:
        raise ReleaseError(
            f"cannot read project.version from {pyproject_path}: {error}"
        ) from error

    sources = {
        "pyproject.toml": str(pyproject_version),
        "src/monitorcontrol/__init__.py": _match_version(
            root / "src/monitorcontrol/__init__.py",
            r'^__version__\s*=\s*"(?P<version>[^"]+)"',
        ),
        "packaging/rpm/monitorcontrol.spec": _match_version(
            root / "packaging/rpm/monitorcontrol.spec",
            r"^Version:\s*(?P<version>\S+)",
        ),
        "debian/changelog": _match_version(
            root / "debian/changelog", DEBIAN_VERSION_RE.pattern
        ),
    }
    for name, version in sources.items():
        try:
            validate_version(version)
        except ReleaseError as error:
            raise ReleaseError(f"{name}: {error}") from error
    return sources


def check_distribution_name(root: Path) -> None:
    pyproject_path = root / "pyproject.toml"
    try:
        project = tomllib.loads(_read(pyproject_path))["project"]
        name = project["name"]
    except (tomllib.TOMLDecodeError, KeyError, TypeError) as error:
        raise ReleaseError(
            f"cannot read project.name from {pyproject_path}: {error}"
        ) from error
    if name != DISTRIBUTION_NAME:
        raise ReleaseError(
            f"Python distribution must be {DISTRIBUTION_NAME!r}, got {name!r}"
        )


def _match_version(path: Path, pattern: str) -> str:
    match = re.search(pattern, _read(path), re.MULTILINE)
    if not match:
        raise ReleaseError(f"cannot find version in {path}")
    return match.group("version")


def check(root: Path, tag: str | None = None) -> str:
    check_distribution_name(root)
    versions = read_versions(root)
    distinct = set(versions.values())
    if len(distinct) != 1:
        details = ", ".join(f"{name}={value}" for name, value in versions.items())
        raise ReleaseError(f"release versions do not match: {details}")

    version = next(iter(distinct))
    candidate_tag = tag
    if candidate_tag is None:
        environment_tag = os.environ.get("GITHUB_REF_NAME")
        if (
            environment_tag
            and environment_tag.startswith("v")
            and VERSION_RE.fullmatch(environment_tag[1:])
        ):
            candidate_tag = environment_tag
    if candidate_tag is not None:
        expected = f"v{version}"
        if candidate_tag != expected:
            raise ReleaseError(
                f"tag {candidate_tag!r} does not match release version "
                f"{version!r}; expected {expected!r}"
            )
    return version


def _replace_once(text: str, pattern: str, replacement: str, path: Path) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise ReleaseError(f"cannot update version in {path}")
    return updated


def _update_changelog(text: str, version: str, today: str) -> str:
    release_heading = f"## [{version}] - {today}"
    if re.search(rf"^## \[{re.escape(version)}\](?:\s|$)", text, re.MULTILINE):
        raise ReleaseError(f"CHANGELOG.md already contains release {version}")

    header = "# Changelog"
    if not text.strip():
        return (
            f"{header}\n\n## Unreleased\n\n{UNRELEASED_PLACEHOLDER}\n\n"
            f"{release_heading}\n\n{RELEASE_PLACEHOLDER}\n"
        )

    lines = text.rstrip().splitlines()
    try:
        unreleased_index = lines.index("## Unreleased")
    except ValueError:
        prefix = text.rstrip()
        return (
            f"{prefix}\n\n## Unreleased\n\n{UNRELEASED_PLACEHOLDER}\n\n"
            f"{release_heading}\n\n{RELEASE_PLACEHOLDER}\n"
        )

    next_release = next(
        (
            index
            for index in range(unreleased_index + 1, len(lines))
            if lines[index].startswith("## ")
        ),
        len(lines),
    )
    unreleased_body = "\n".join(lines[unreleased_index + 1 : next_release]).strip()
    if not unreleased_body or unreleased_body == UNRELEASED_PLACEHOLDER:
        unreleased_body = RELEASE_PLACEHOLDER

    before = "\n".join(lines[: unreleased_index + 1]).rstrip()
    after = "\n".join(lines[next_release:]).strip()
    updated = (
        f"{before}\n\n{UNRELEASED_PLACEHOLDER}\n\n"
        f"{release_heading}\n\n{unreleased_body}\n"
    )
    if after:
        updated += f"\n{after}\n"
    return updated


def prepare(root: Path, version: str, now: dt.datetime | None = None) -> None:
    validate_version(version)
    check(root)

    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    now = now.astimezone(dt.timezone.utc)

    paths = {
        "pyproject": root / "pyproject.toml",
        "init": root / "src/monitorcontrol/__init__.py",
        "spec": root / "packaging/rpm/monitorcontrol.spec",
        "debian": root / "debian/changelog",
        "changelog": root / "CHANGELOG.md",
    }
    existing = {name: _read(path) for name, path in paths.items() if path.exists()}

    updated = {
        paths["pyproject"]: _replace_once(
            existing["pyproject"],
            r'^(version\s*=\s*")[^"]+(")',
            rf"\g<1>{version}\g<2>",
            paths["pyproject"],
        ),
        paths["init"]: _replace_once(
            existing["init"],
            r'^(__version__\s*=\s*")[^"]+(")',
            rf"\g<1>{version}\g<2>",
            paths["init"],
        ),
        paths["spec"]: _replace_once(
            existing["spec"],
            r"^(Version:\s*)\S+",
            rf"\g<1>{version}",
            paths["spec"],
        ),
    }

    debian_entry = (
        f"monitorcontrol ({version}-1) UNRELEASED; urgency=medium\n\n"
        f"  * {RELEASE_PLACEHOLDER.removeprefix('- ')}\n\n"
        f" -- {MAINTAINER}  {format_datetime(now)}\n\n"
    )
    updated[paths["debian"]] = debian_entry + existing["debian"].lstrip()
    updated[paths["changelog"]] = _update_changelog(
        existing.get("changelog", ""), version, now.date().isoformat()
    )

    _write_all(updated)
    check(root)


def _write_all(files: dict[Path, str]) -> None:
    temporary: dict[Path, Path] = {}
    try:
        for path, contents in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                delete=False,
            ) as handle:
                handle.write(contents)
                temporary[path] = Path(handle.name)
            mode = (
                stat.S_IMODE(path.stat().st_mode)
                if path.exists()
                else 0o644
            )
            temporary[path].chmod(mode)
        for path, temporary_path in temporary.items():
            temporary_path.replace(path)
    except OSError as error:
        raise ReleaseError(f"cannot write release files: {error}") from error
    finally:
        for temporary_path in temporary.values():
            temporary_path.unlink(missing_ok=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help=argparse.SUPPRESS,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check", help="check release versions")
    check_parser.add_argument("--tag", help="validate a release tag such as v1.2.3")
    prepare_parser = subparsers.add_parser("prepare", help="prepare a release")
    prepare_parser.add_argument("version")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "check":
            version = check(args.root, args.tag)
            print(f"Release versions are consistent: {version}")
        else:
            prepare(args.root, args.version)
            print(f"Prepared release {args.version}")
    except ReleaseError as error:
        print(f"release error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
