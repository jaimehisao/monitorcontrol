#!/usr/bin/env bash
# Build RPM and SRPM artifacts from the canonical committed source archive.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
version="$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")"
archive="${1:-dist/monitorcontrol-${version}-source.tar.gz}"
output="${PACKAGE_OUTPUT_DIR:-dist/packages/rpm}"

if [[ $# -eq 0 ]]; then
  ./scripts/build-source-archive.sh dist >/dev/null
fi
if [[ ! -f "$archive" ]]; then
  echo "Canonical source archive not found: $archive" >&2
  exit 1
fi
if [[ "$(basename "$archive")" != "monitorcontrol-${version}-source.tar.gz" ]]; then
  echo "Source archive name does not match version ${version}: $archive" >&2
  exit 1
fi

build_root="$(mktemp -d "${TMPDIR:-/tmp}/monitorcontrol-rpmbuild.XXXXXX")"
trap 'rm -rf "$build_root"' EXIT
mkdir -p "$build_root"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
cp -a "$archive" "$build_root/SOURCES/"
cp -a packaging/rpm/monitorcontrol.spec "$build_root/SPECS/"

rpmbuild -ba \
  --define "_topdir $build_root" \
  "$build_root/SPECS/monitorcontrol.spec"

rm -rf "$output"
mkdir -p "$output/rpm" "$output/srpm"
shopt -s nullglob
rpms=("$build_root"/RPMS/noarch/monitorcontrol-*.noarch.rpm)
srpms=("$build_root"/SRPMS/monitorcontrol-*.src.rpm)
shopt -u nullglob
if [[ ${#rpms[@]} -ne 1 || ${#srpms[@]} -ne 1 ]]; then
  echo "Expected one RPM and one SRPM; found ${#rpms[@]} and ${#srpms[@]}" >&2
  exit 1
fi
cp -a "${rpms[0]}" "$output/rpm/"
cp -a "${srpms[0]}" "$output/srpm/"
printf '%s\n' "$output/rpm/$(basename "${rpms[0]}")"
printf '%s\n' "$output/srpm/$(basename "${srpms[0]}")"
