#!/usr/bin/env python3
"""Poll public PyPI, COPR, and Launchpad metadata for a released version."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import gzip
import json
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class VerificationError(RuntimeError):
    pass


def fetch(url: str) -> bytes:
    try:
        with urlopen(Request(url, headers={"User-Agent": "monitorcontrol-release"}), timeout=30) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError) as error:
        raise VerificationError(f"{url}: {error}") from error


def pypi_visible(version: str) -> bool:
    data = json.loads(fetch(f"https://pypi.org/pypi/monitorcontrol-linux/{version}/json"))
    return data.get("info", {}).get("version") == version


def collect_versions(value: object) -> set[str]:
    versions: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "version" and isinstance(child, str):
                versions.add(child)
            else:
                versions.update(collect_versions(child))
    elif isinstance(value, list):
        for child in value:
            versions.update(collect_versions(child))
    return versions


def copr_visible(version: str, owner: str, project: str) -> bool:
    query = urlencode(
        {
            "ownername": owner,
            "projectname": project,
            "packagename": "monitorcontrol",
            "with_latest_build": "true",
        }
    )
    data = json.loads(fetch(f"https://copr.fedorainfracloud.org/api_3/package?{query}"))
    return any(
        candidate == version or candidate.startswith(f"{version}-")
        for candidate in collect_versions(data)
    )


def parse_debian_sources(contents: str, package: str) -> set[str]:
    versions: set[str] = set()
    for paragraph in re.split(r"\n\s*\n", contents):
        fields = {}
        for line in paragraph.splitlines():
            if ": " in line:
                key, value = line.split(": ", 1)
                fields[key] = value
        if fields.get("Package") == package and "Version" in fields:
            versions.add(fields["Version"])
    return versions


def launchpad_visible(version: str, owner: str, archive: str) -> bool:
    url = (
        f"https://ppa.launchpadcontent.net/{owner}/{archive}/ubuntu/"
        "dists/noble/main/source/Sources.gz"
    )
    versions = parse_debian_sources(gzip.decompress(fetch(url)).decode("utf-8"))
    return f"{version}-1ppa1~noble1" in versions


def verify_with_retries(
    name: str,
    check: Callable[[], bool],
    attempts: int,
    delay: float,
    sleep: Callable[[float], object] = time.sleep,
) -> None:
    errors = []
    for attempt in range(1, attempts + 1):
        try:
            if check():
                print(f"Verified {name} publication")
                return
            errors.append("version not visible")
        except (VerificationError, json.JSONDecodeError, gzip.BadGzipFile, UnicodeError) as error:
            errors.append(str(error))
        if attempt != attempts:
            sleep(delay)
    raise VerificationError(
        f"{name} not verifiable after {attempts} attempts; rerun the failed "
        f"workflow after repository metadata updates (last error: {errors[-1]})"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("--copr-owner", required=True)
    parser.add_argument("--copr-project", required=True)
    parser.add_argument("--ppa-owner", required=True)
    parser.add_argument("--ppa-archive", required=True)
    parser.add_argument("--attempts", type=int, default=20)
    parser.add_argument("--delay", type=float, default=30)
    args = parser.parse_args(argv)
    if args.attempts < 1 or args.delay < 0:
        parser.error("attempts must be positive and delay must be non-negative")
    try:
        verify_with_retries(
            "PyPI", lambda: pypi_visible(args.version), args.attempts, args.delay
        )
        verify_with_retries(
            "COPR",
            lambda: copr_visible(args.version, args.copr_owner, args.copr_project),
            args.attempts,
            args.delay,
        )
        verify_with_retries(
            "Launchpad",
            lambda: launchpad_visible(args.version, args.ppa_owner, args.ppa_archive),
            args.attempts,
            args.delay,
        )
    except VerificationError as error:
        print(f"publication verification error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
