#!/usr/bin/env bash
# Build Debian binary and source-package artifacts from the canonical archive.
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
version="$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")"
archive="${1:-dist/monitorcontrol-${version}-source.tar.gz}"
output="${PACKAGE_OUTPUT_DIR:-dist/packages/debian}"

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

work="$(mktemp -d "${TMPDIR:-/tmp}/monitorcontrol-debbuild.XXXXXX")"
trap 'rm -rf "$work"' EXIT
tar -C "$work" -xzf "$archive"
source_root="$work/monitorcontrol-${version}"
if [[ ! -d "$source_root/debian" ]]; then
  echo "Canonical source archive does not contain Debian packaging" >&2
  exit 1
fi
chmod a+rx "$work" "$source_root"

# A 3.0 (quilt) source package keeps packaging in debian.tar and upstream
# files in orig.tar. Derive both from the one canonical committed archive.
orig_staging="$work/orig"
mkdir -p "$orig_staging"
tar -C "$orig_staging" -xzf "$archive"
rm -rf "$orig_staging/monitorcontrol-${version}/debian"
tar -C "$orig_staging" -czf \
  "$work/monitorcontrol_${version}.orig.tar.gz" \
  "monitorcontrol-${version}"

(
  cd "$source_root"
  dpkg-buildpackage --no-sign -S
  dpkg-buildpackage --no-sign -b
)

rm -rf "$output"
mkdir -p "$output/binary" "$output/source"
shopt -s nullglob
debs=("$work"/monitorcontrol_"${version}"-*_all.deb)
dscs=("$work"/monitorcontrol_"${version}"-*.dsc)
debian_tars=("$work"/monitorcontrol_"${version}"-*.debian.tar.*)
source_changes=("$work"/monitorcontrol_"${version}"-*_source.changes)
source_buildinfo=("$work"/monitorcontrol_"${version}"-*_source.buildinfo)
binary_changes=("$work"/monitorcontrol_"${version}"-*_all.changes)
binary_buildinfo=("$work"/monitorcontrol_"${version}"-*_all.buildinfo)
shopt -u nullglob
if [[ ${#debs[@]} -ne 1 || ${#dscs[@]} -ne 1 || ${#debian_tars[@]} -ne 1 ]]; then
  echo "Expected one DEB, DSC, and debian.tar source artifact" >&2
  exit 1
fi

cp -a "${debs[0]}" "${binary_changes[@]}" "${binary_buildinfo[@]}" \
  "$output/binary/"
cp -a "$work/monitorcontrol_${version}.orig.tar.gz" \
  "${dscs[0]}" "${debian_tars[0]}" \
  "${source_changes[@]}" "${source_buildinfo[@]}" \
  "$output/source/"
printf '%s\n' "$output/binary/$(basename "${debs[0]}")"
printf '%s\n' "$output/source/$(basename "${dscs[0]}")"
