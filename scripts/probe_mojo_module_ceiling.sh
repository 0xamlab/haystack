#!/usr/bin/env bash
# Probe modular/modular#2766 against the CURRENTLY PINNED Mojo compiler.
#
# Background: an internal compiler pass recurses once per top-level declaration in a single
# translation unit and stack-overflows somewhere between 500 (compiles) and 600 (crashes) modules.
# This codebase's runtime-library catalog is ~640 modules, so build_mojo_binary.sh REFUSES an
# unfiltered (monolith) build unless MOJO_BUILD_ALLOW_UNSAFE_MONOLITH=1, and production ships
# 24-module shards instead. Whenever the toolchain pin moves (e.g. 1.0.0b2 -> 1.0.0 -> 1.1.0),
# run this probe: if the monolith compiles, the upstream bug is FIXED for this compiler and the
# sharding mechanism + the MOJO_BUILD_MAX_SAFE_MODULES guard can be retired; if it crashes, the
# guard stays and the verdict is recorded.
#
# Usage:
#   scripts/probe_mojo_module_ceiling.sh
#
# The probe builds the FULL unfiltered dispatch into a scratch binary (no repo artifacts touched)
# and reports one of:
#   VERDICT: FIXED        (monolith compiled + linked; #2766 no longer applies to this pin)
#   VERDICT: STILL_BROKEN (crash/refusal; keep sharding, ceiling unchanged)
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROBE_DIR="${PROBE_DIR:-${REPO_ROOT}/mojo_build/probe-module-ceiling}"
mkdir -p "${PROBE_DIR}"

module_count="$(cd "${REPO_ROOT}" && python3 -c \
    "import sys; sys.path.insert(0, '.'); from apps.runtime.mojo_inventory import discover_runtime_library_modules; print(len(discover_runtime_library_modules()))")"
echo "[probe-module-ceiling] runtime-library catalog: ${module_count} modules"
echo "[probe-module-ceiling] guard ceiling: MOJO_BUILD_MAX_SAFE_MODULES=${MOJO_BUILD_MAX_SAFE_MODULES:-550}"

start_ts="$(date +%s)"
MOJO_BUILD_ALLOW_UNSAFE_MONOLITH=1 \
BINARY_PATH="${PROBE_DIR}/monolith" \
OBJECT_PATH="${PROBE_DIR}/monolith.o" \
TEMP_OBJECT_PATH="${PROBE_DIR}/monolith.o.tmp" \
TEMP_BINARY_PATH="${PROBE_DIR}/monolith.tmp" \
    "${REPO_ROOT}/scripts/build_mojo_binary.sh" >"${PROBE_DIR}/build.log" 2>&1
rc=$?
elapsed=$(( $(date +%s) - start_ts ))

echo "[probe-module-ceiling] build rc=${rc} in ${elapsed}s (log: ${PROBE_DIR}/build.log)"
tail -n 5 "${PROBE_DIR}/build.log" >&2 || true

if [[ "${rc}" -eq 0 && -x "${PROBE_DIR}/monolith" ]]; then
    echo "VERDICT: FIXED — the pinned compiler built the ${module_count}-module monolith."
    echo "The MOJO_BUILD_MAX_SAFE_MODULES guard and the sharding rationale are candidates for retirement."
    exit 0
fi
echo "VERDICT: STILL_BROKEN — monolith build failed/crashed on the pinned compiler; keep sharding."
exit 1
