#!/usr/bin/env bash
#
# build-package.sh — assemble the Azure Marketplace Managed Application package.
#
# A managed-app offer package is a flat .zip of:
#   * mainTemplate.json       — the ARM template (compiled from ../main.bicep; NOT committed, it's a build artifact)
#   * createUiDefinition.json — the portal deploy form (committed)
#   * viewDefinition.json     — the post-deploy overview (committed)
#
# Output: managed-app/dist/algenta-decision-managed-app.zip — upload as the package in Partner Center.
#
# Prereqs: az CLI (with bicep) + zip. Run from anywhere; paths are resolved relative to this script.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BICEP="$HERE/../main.bicep"
DIST="$HERE/dist"
STAGE="$DIST/stage"

command -v az >/dev/null || { echo "az CLI not found" >&2; exit 127; }
command -v zip >/dev/null || { echo "zip not found" >&2; exit 127; }
[ -f "$BICEP" ] || { echo "missing $BICEP" >&2; exit 66; }
[ -f "$HERE/createUiDefinition.json" ] || { echo "missing createUiDefinition.json" >&2; exit 66; }
[ -f "$HERE/viewDefinition.json" ] || { echo "missing viewDefinition.json" >&2; exit 66; }

rm -rf "$STAGE"; mkdir -p "$STAGE"
echo "compiling mainTemplate.json from main.bicep …"
az bicep build --file "$BICEP" --outfile "$STAGE/mainTemplate.json"
cp "$HERE/createUiDefinition.json" "$STAGE/createUiDefinition.json"
cp "$HERE/viewDefinition.json" "$STAGE/viewDefinition.json"

ZIP="$DIST/algenta-decision-managed-app.zip"
rm -f "$ZIP"
( cd "$STAGE" && zip -q -X "$ZIP" mainTemplate.json createUiDefinition.json viewDefinition.json )
rm -rf "$STAGE"
echo "built: $ZIP"
unzip -l "$ZIP" 2>/dev/null | sed -n '2,6p' || true
