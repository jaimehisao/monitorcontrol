#!/usr/bin/env bash
# Build an RPM from the current git tree (CI / local Fedora).
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
version="$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")"
tarball="${TMPDIR:-/tmp}/monitorcontrol-${version}.tar.gz"
git archive --prefix="monitorcontrol-${version}/" -o "$tarball" HEAD
mkdir -p "${HOME}/rpmbuild/SOURCES" "${HOME}/rpmbuild/SPECS"
cp -a "$tarball" "${HOME}/rpmbuild/SOURCES/"
cp -a packaging/rpm/monitorcontrol.spec "${HOME}/rpmbuild/SPECS/"
rpmbuild -ba "${HOME}/rpmbuild/SPECS/monitorcontrol.spec"
find "${HOME}/rpmbuild/RPMS" "${HOME}/rpmbuild/SRPMS" -name '*.rpm' -print
