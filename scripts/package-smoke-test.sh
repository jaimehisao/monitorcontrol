#!/usr/bin/env bash
# Verify package-owned application files after install or uninstall.
set -euo pipefail

if [[ $# -ne 2 || ( "$1" != "installed" && "$1" != "removed" ) ]]; then
  echo "usage: $0 {installed|removed} VERSION" >&2
  exit 2
fi

state="$1"
version="$2"
files=(
  /usr/bin/monitorcontrol
  /usr/share/applications/dev.monitorcontrol.MonitorControl.desktop
  /usr/share/icons/hicolor/scalable/apps/dev.monitorcontrol.MonitorControl.svg
  /usr/lib/udev/rules.d/90-monitorcontrol-i2c.rules
  /usr/lib/modules-load.d/i2c-dev.conf
  /usr/share/gnome-shell/extensions/monitorcontrol@monitorcontrol.dev/metadata.json
  /usr/share/gnome-shell/extensions/monitorcontrol@monitorcontrol.dev/extension.js
)

package_owns_file() {
  local file="$1"
  if command -v rpm >/dev/null; then
    rpm -qf "$file" | grep -q '^monitorcontrol-'
    return
  fi

  local canonical
  canonical="$(readlink -f "$file")"
  while IFS= read -r owned; do
    if [[ -e "$owned" && "$(readlink -f "$owned")" == "$canonical" ]]; then
      return 0
    fi
  done < <(dpkg-query -L monitorcontrol)
  return 1
}

if [[ "$state" == "installed" ]]; then
  [[ "$(monitorcontrol --version)" == "MonitorControl $version" ]]
  python3 -c \
    "import monitorcontrol; assert monitorcontrol.__version__ == '$version'"
  if command -v rpm >/dev/null; then
    [[ "$(rpm -q --qf '%{VERSION}' monitorcontrol)" == "$version" ]]
  else
    [[ "$(dpkg-query -W -f='${Version}' monitorcontrol)" == "$version"-* ]]
  fi
  for file in "${files[@]}"; do
    [[ -f "$file" ]] || {
      echo "Expected installed file is missing: $file" >&2
      exit 1
    }
    package_owns_file "$file" || {
      echo "Installed file is not owned by monitorcontrol: $file" >&2
      exit 1
    }
  done
else
  if command -v monitorcontrol >/dev/null; then
    echo "monitorcontrol command remains after uninstall" >&2
    exit 1
  fi
  if python3 -c "import monitorcontrol" >/dev/null 2>&1; then
    echo "monitorcontrol Python package remains after uninstall" >&2
    exit 1
  fi
  for file in "${files[@]}"; do
    [[ ! -e "$file" ]] || {
      echo "Package-owned file remains after uninstall: $file" >&2
      exit 1
    }
  done
fi
