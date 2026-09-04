#!/usr/bin/env bash
# Build wheel, sdist, and a PyInstaller one-file Linux binary into dist/.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

version="$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")"
echo "Building MonitorControl ${version}"

rm -rf dist build
mkdir -p dist

python3 -m pip install --disable-pip-version-check -q build pyinstaller
python3 -m build --outdir dist

python3 -m PyInstaller pack/monitorcontrol.spec \
  --noconfirm \
  --distpath build/pyinstaller \
  --workpath build/pyinstaller-work

cp -a "build/pyinstaller/monitorcontrol" "dist/monitorcontrol-${version}-linux"
chmod +x "dist/monitorcontrol-${version}-linux"
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
