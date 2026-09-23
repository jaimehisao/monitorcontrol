#!/usr/bin/env bash
# Build the canonical full-repository source archive from committed HEAD.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

PYTHON="${PYTHON:-python3}"
output_directory="${1:-dist}"
"$PYTHON" scripts/release.py check
version="$("$PYTHON" -c \
  "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")"
archive="monitorcontrol-${version}-source.tar.gz"

mkdir -p "$output_directory"
rm -f "$output_directory/$archive"
git archive \
  --format=tar.gz \
  --prefix="monitorcontrol-${version}/" \
  --output="$output_directory/$archive" \
  HEAD

test -s "$output_directory/$archive"
printf '%s\n' "$output_directory/$archive"
