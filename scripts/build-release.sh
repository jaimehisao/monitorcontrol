#!/usr/bin/env bash
# Build wheel, sdist, and a single-file zipapp "binary" into dist/.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

version="$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")"
echo "Building MonitorControl ${version}"

rm -rf dist build
mkdir -p dist build/zipapp

python3 -m pip install --disable-pip-version-check -q build
python3 -m build --outdir dist

cp -a src/monitorcontrol build/zipapp/monitorcontrol
find build/zipapp -type d -name '__pycache__' -prune -exec rm -rf {} +
find build/zipapp -name '*.py[co]' -delete
python3 -m zipapp build/zipapp \
  --python "/usr/bin/env python3" \
  --main "monitorcontrol.cli:main" \
  --compress \
  --output "dist/monitorcontrol-${version}-linux"
chmod +x "dist/monitorcontrol-${version}-linux"

# Unversioned name is handy for scripts; release uploads both.
cp -a "dist/monitorcontrol-${version}-linux" dist/monitorcontrol

(
  cd dist
  sha256sum \
    monitorcontrol \
    "monitorcontrol-${version}-linux" \
    "monitorcontrol-${version}-py3-none-any.whl" \
    "monitorcontrol-${version}.tar.gz" \
    > SHA256SUMS
)

echo "Artifacts:"
ls -l dist
cat dist/SHA256SUMS
