#!/usr/bin/env bash
# MAX 26.5 (the `max` conda package that mojo 1.0.0's parallelize/max.gpu moved into) ships its own
# kernel-development packages named linalg, pipeline, quantization and kv_cache as precompiled
# .mojoc files under <env>/lib/mojo/. Those names are ALSO this repo's runtime-library modules —
# the SDK-facing dispatch contract exposes modules called exactly `linalg`, `pipeline`,
# `quantization`, `kv_cache` (mojo/engine/<name>.mojo, and packages/algenta's
# runtime_library_contract.json lists them under those names, derived from the file names by
# apps/runtime/mojo_inventory.py), so renaming them out of the collision is NOT an option without
# breaking the public contract.
#
# Mojo 1.0.0 resolves the precompiled .mojoc packages in the env's lib/mojo directory AHEAD of
# `-I` directories and even ahead of the importing file's own sibling directory (measured: a file
# sitting NEXT TO mojo/engine/linalg.mojo that does `from linalg import Matrix` resolves to the
# MAX package and fails with "package 'linalg' does not contain 'Matrix'"), so with the .mojoc
# files present the engine's modules become unreachable. Move the colliding MAX packages aside
# where the compiler cannot see them.
#
# Idempotent; survives until the next `pixi install` restores them, which is why every build entry
# point re-runs this. Touches nothing the engine needs from MAX: what the engine consumes from the
# `max` package is max.algorithm (parallelize) and max.gpu (DeviceContext/barrier/AddressSpace),
# which live in max.mojoc / algorithm.mojoc and stay in place.
set -euo pipefail

LIB_DIR="${1:?usage: shadow_max_pkg_name_collisions.sh <pixi-env-lib-dir>}"
# The eviction target MUST live OUTSIDE ${LIB_DIR}/mojo: the Mojo compiler scans that whole
# directory recursively for packages — dot-subdirectories included (measured: .mojoc files evicted
# into lib/mojo/.algenta-shadowed STILL resolved and shadowed the engine's modules).
ALGENTA_SHADOWED_PKG_DIR="${LIB_DIR}/.algenta-shadowed-max"
mkdir -p "${ALGENTA_SHADOWED_PKG_DIR}"
# Clean up the earlier, ineffective eviction location if a previous run left it behind.
rm -rf "${LIB_DIR}/mojo/.algenta-shadowed"
for _shadowed_pkg in linalg pipeline quantization kv_cache; do
    if [[ -f "${LIB_DIR}/mojo/${_shadowed_pkg}.mojoc" ]]; then
        # Concurrent builds race on this mv; the loser finds the file already moved, which is the
        # desired end state either way, so swallow that failure instead of aborting the build.
        if mv "${LIB_DIR}/mojo/${_shadowed_pkg}.mojoc" "${ALGENTA_SHADOWED_PKG_DIR}/${_shadowed_pkg}.mojoc" 2>/dev/null; then
            echo "[shadow-max-collisions] shadowed MAX package '${_shadowed_pkg}' — engine module" \
                "mojo/engine/${_shadowed_pkg}.mojo owns that name in the runtime contract" >&2
        fi
    fi
done
