#!/usr/bin/env python3
"""Validate a release tag's shape, signature, target, and main ancestry."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


TAG_RE = re.compile(r"^v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$")


class TagError(RuntimeError):
    pass


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise TagError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def api_json(url: str, token: str) -> dict[str, object]:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise TagError(f"GitHub tag verification request failed: {error}") from error


def validate_local(root: Path, tag: str, main_ref: str = "origin/main") -> str:
    if not TAG_RE.fullmatch(tag):
        raise TagError(f"invalid release tag {tag!r}; expected exact vX.Y.Z")
    object_type = git(root, "cat-file", "-t", tag)
    if object_type != "tag":
        raise TagError(f"{tag} is lightweight; an annotated signed tag is required")
    commit = git(root, "rev-parse", f"{tag}^{{commit}}")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, main_ref],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 1:
        raise TagError(f"{tag} commit {commit} is not an ancestor of {main_ref}")
    if result.returncode:
        raise TagError(result.stderr.strip() or "could not validate main ancestry")
    return commit


def validate_github(repository: str, tag: str, token: str, commit: str) -> None:
    base = f"https://api.github.com/repos/{repository}/git"
    reference = api_json(f"{base}/ref/tags/{quote(tag, safe='')}", token)
    ref_object = reference.get("object")
    if not isinstance(ref_object, dict) or ref_object.get("type") != "tag":
        raise TagError(f"{tag} is lightweight; an annotated signed tag is required")
    tag_object = api_json(f"{base}/tags/{ref_object.get('sha')}", token)
    verification = tag_object.get("verification")
    if not isinstance(verification, dict) or verification.get("verified") is not True:
        reason = (
            verification.get("reason")
            if isinstance(verification, dict)
            else "missing verification"
        )
        raise TagError(f"{tag} does not have a GitHub-verified signature: {reason}")
    target = tag_object.get("object")
    if not isinstance(target, dict) or target.get("type") != "commit":
        raise TagError(f"{tag} does not point directly to a commit")
    if target.get("sha") != commit:
        raise TagError(
            f"GitHub tag target {target.get('sha')} differs from local target {commit}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--main-ref", default="origin/main")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    parser.add_argument(
        "--local-only", action="store_true", help="skip GitHub signature verification"
    )
    args = parser.parse_args(argv)
    try:
        commit = validate_local(args.root, args.tag, args.main_ref)
        if not args.local_only:
            if not args.repository or not args.token:
                raise TagError("--repository and --token are required")
            validate_github(args.repository, args.tag, args.token, commit)
    except TagError as error:
        print(f"tag validation error: {error}", file=sys.stderr)
        return 1
    print(f"Validated signed release tag {args.tag} at {commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
