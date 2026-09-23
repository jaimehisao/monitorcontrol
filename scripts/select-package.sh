#!/usr/bin/env bash
# Print exactly one matching package path, rejecting missing or ambiguous output.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 DIRECTORY GLOB" >&2
  exit 2
fi

directory="$1"
pattern="$2"
if [[ ! -d "$directory" ]]; then
  echo "Package directory does not exist: $directory" >&2
  exit 1
fi

shopt -s nullglob
matches=("$directory"/$pattern)
shopt -u nullglob

if [[ ${#matches[@]} -ne 1 ]]; then
  echo "Expected exactly one package matching $directory/$pattern; found ${#matches[@]}" >&2
  printf '  %s\n' "${matches[@]}" >&2
  exit 1
fi

printf '%s\n' "${matches[0]}"
