#!/usr/bin/env bash
# Build the canonical source and Python distribution artifacts into dist/.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

PYTHON="${PYTHON:-python3}"
"$PYTHON" scripts/release.py check
version="$("$PYTHON" -c \
  "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")"

echo "Building MonitorControl ${version}"
rm -rf dist build
mkdir -p dist

"$PYTHON" -m build --outdir dist

source_archive="monitorcontrol-${version}-source.tar.gz"
PYTHON="$PYTHON" ./scripts/build-source-archive.sh dist

artifacts=(
  "monitorcontrol_linux-${version}-py3-none-any.whl"
  "monitorcontrol_linux-${version}.tar.gz"
  "$source_archive"
)
for artifact in "${artifacts[@]}"; do
  if [[ ! -f "dist/${artifact}" ]]; then
    echo "Expected artifact was not built: dist/${artifact}" >&2
    exit 1
  fi
done

(
  cd dist
  sha256sum "${artifacts[@]}" > SHA256SUMS
)

echo "Artifacts:"
ls -l dist
cat dist/SHA256SUMS
