#!/usr/bin/env bash
# Total line count across every tracked .mojo file in the repo, broken down by
# top-level directory. Run from anywhere inside the algenta checkout (uses
# `git ls-files`, so it only counts what's actually committed -- not build
# output, vendored copies under build/, or scratch files that never got added).
#
# Usage: ./count_mojo_loc.sh [path-to-repo]  (defaults to the current directory)
set -euo pipefail
cd "${1:-.}"

files=$(git ls-files -- '*.mojo')
total_files=$(echo "$files" | grep -c .)
total_lines=$(echo "$files" | xargs wc -l | tail -1 | awk '{print $1}')

echo "By top-level directory:"
echo "$files" | awk -F/ 'NF>1{print $1} NF==1{print "."}' | sort -u | while read -r dir; do
  if [ "$dir" = "." ]; then
    subset=$(echo "$files" | grep -v /)
    label="(repo root)"
  else
    subset=$(echo "$files" | grep "^$dir/")
    label="$dir"
  fi
  n_files=$(echo "$subset" | grep -c .)
  n_lines=$(echo "$subset" | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
  printf "  %-20s %6s files  %9s lines\n" "$label" "$n_files" "${n_lines:-0}"
done

echo
echo "Mojo files: $total_files"
echo "Total lines: $total_lines"
