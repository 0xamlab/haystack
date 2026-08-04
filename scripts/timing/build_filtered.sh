#!/usr/bin/env bash
# Filtered Mojo build for timing-lane iteration, with the dispatch artifact protected.
#
# WHY THIS WRAPPER EXISTS
#
# scripts/build_mojo_binary.sh regenerates mojo/engine/runtime_library_dispatch_generated.mojo in
# place on every run, and when MOJO_RUNTIME_MODULE_FILTER is set it regenerates that file with ONLY
# the filtered modules. The committed artifact -- 101k lines covering all 498 modules -- is therefore
# silently replaced by a handful, which fails
# tests/test_runtime_library_dispatch_generation.py::test_generated_runtime_library_dispatch_is_in_sync
# and would ship a runtime missing almost every kernel.
#
# The build script already refuses to install a filtered BINARY at the canonical path. It has no such
# guard on the dispatch SOURCE. This wrapper adds one: whatever happens, the full dispatch is
# regenerated on exit.
#
# A full unfiltered build is impractical during iteration (16 GB RSS cap, 1800 s timeout), so filtered
# builds are the normal path and this footgun would otherwise be trodden on repeatedly.
#
# Usage:
#   scripts/timing/build_filtered.sh counter_rng,linear_models,calibration
#   scripts/timing/build_filtered.sh                # defaults to the timing kernel set

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"

FILTER="${1:-counter_rng,linear_models,calibration,conformal,model_compare}"
OUT="${BINARY_PATH:-${REPO_ROOT}/mojo_build/simulate_timing}"
# main.mojo `#include`s its sibling dispatch table from ITS OWN directory, not via -I -- so
# MOJO_RUNTIME_MODULE_FILTER alone, with MOJO_SRC left at the tracked mojo/engine/main.mojo, is a
# SILENT NO-OP: main.mojo would still pick up the full, untouched, ~114k-line
# mojo/engine/runtime_library_dispatch_generated.mojo regardless of the filter
# (build_mojo_binary.sh refuses this combination outright now). Stage a copy so the filter
# actually takes effect, the way CI's own build and scripts/build_runtime_shards.py already do.
STAGE_DIR="$(mktemp -d "${REPO_ROOT}/mojo_build/.timing-build-stage.XXXXXX")"

cleanup_and_restore_dispatch() {
    local status=$?
    rm -rf "${STAGE_DIR}"
    echo "→ restoring the full runtime dispatch artifact"
    python3 "${REPO_ROOT}/scripts/generate_runtime_library_dispatch.py" >/dev/null
    local lines
    lines="$(wc -l < "${REPO_ROOT}/mojo/engine/runtime_library_dispatch_generated.mojo" | tr -d ' ')"
    echo "  dispatch restored: ${lines} lines"
    exit "${status}"
}
trap cleanup_and_restore_dispatch EXIT
cp "${REPO_ROOT}/mojo/engine/main.mojo" "${STAGE_DIR}/main.mojo"

echo "→ filtered build"
echo "  modules: ${FILTER}"
echo "  binary : ${OUT}"

# Gate 0 item 7: fallback denial in EVERY env, test and benchmark. These were never actually pinned,
# so every kernel call in this lane could have been silently answered by a Python fallback -- which
# returns plausible numbers and invalidates every speed and determinism claim without erroring.
export RUNTIME_FALLBACK_MODE="deny"
export MOJO_ALLOW_SUBPROCESS_FALLBACK="false"

MOJO_RUNTIME_MODULE_FILTER="${FILTER}" \
MOJO_SRC="${STAGE_DIR}/main.mojo" \
DISPATCH_OUTPUT_PATH="${STAGE_DIR}/runtime_library_dispatch_generated.mojo" \
BINARY_PATH="${OUT}" \
    bash "${REPO_ROOT}/scripts/build_mojo_binary.sh"

echo "→ probing dispatch through the socket transport"
python3 "${REPO_ROOT}/scripts/timing/kernel_probe.py" --binary "${OUT}"
