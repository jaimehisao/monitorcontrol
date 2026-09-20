#!/usr/bin/env bash
# Build an RPM from the current tree (CI / local Fedora). Does not need git.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
version="$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")"
staging="${TMPDIR:-/tmp}/monitorcontrol-src"
rm -rf "$staging"
mkdir -p "$staging/monitorcontrol-${version}"
tar -C "$root" \
  --exclude='.git' \
  --exclude='build' \
  --exclude='dist' \
  --exclude='.venv' \
  --exclude='src/monitorcontrol.egg-info' \
  --exclude='**/__pycache__' \
  -cf - . | tar -C "$staging/monitorcontrol-${version}" -xf -
tarball="${TMPDIR:-/tmp}/monitorcontrol-${version}.tar.gz"
tar -C "$staging" -czf "$tarball" "monitorcontrol-${version}"
mkdir -p "${HOME}/rpmbuild/SOURCES" "${HOME}/rpmbuild/SPECS"
cp -a "$tarball" "${HOME}/rpmbuild/SOURCES/"
cp -a packaging/rpm/monitorcontrol.spec "${HOME}/rpmbuild/SPECS/"
rpmbuild -ba "${HOME}/rpmbuild/SPECS/monitorcontrol.spec"
find "${HOME}/rpmbuild/RPMS" "${HOME}/rpmbuild/SRPMS" -name '*.rpm' -print
