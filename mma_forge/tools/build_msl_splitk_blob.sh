#!/bin/bash
# build_msl_splitk_blob.sh -- beat-llama.cpp campaign front 2, fourth strike (2026-08-09): the
# split-K GPU-fill kernels for the two narrow-N GEMM roles (o_proj K=2048/N=1024 -> S=8,
# down_proj K=3072/N=1024 -> S=12; standalone bench: 1.30-1.33x over the MSL parity accum kernel,
# predicted -1.97 ms on the 256-token resident prefill). Compiles msl_splitk_accum.metal ONCE PER
# KERNEL via its SK_ONLY gate (batch_shim.m registers only functionNames[0] of each MTLB blob, so
# every production kernel ships as its own metallib -- same convention build_msl_parity_blob.sh
# established), concatenates them, and renders the result as the symbol-free C byte array
# mma_forge/generated/msl_splitk_blob.c through the SAME extract_blob.py mechanism every other
# blob in this repo uses. A binary that never links this blob keeps the parity accum kernels for
# both roles (session discovery fields stay -1; `_apply_m_rows_af_nomirror` degrades gracefully).
#
# Usage (repo root):
#   bash mma_forge/tools/build_msl_splitk_blob.sh
#
# Requires: DEVELOPER_DIR pointing at the pinned Xcode, python3.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$REPO_ROOT/benchmarks/llm_smoke/metal_llama_parity_replica/msl_splitk_accum.metal"
OUT_C="$REPO_ROOT/mma_forge/generated/msl_splitk_blob.c"
WORK="$(mktemp -d /tmp/msl_splitk_blob.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode-26.6.0.app/Contents/Developer}"

# One air + one metallib per kernel, in the FIXED discovery order (splitk8 first = o_proj's,
# splitk12 second = down_proj's) -- order only affects pipeline INDEX reproducibility.
for s in 8 12; do
    xcrun -sdk macosx metal -DSK_ONLY="$s" -c "$SRC" -o "$WORK/msl_splitk${s}.air"
    xcrun -sdk macosx metallib "$WORK/msl_splitk${s}.air" -o "$WORK/msl_splitk${s}.metallib"
done

cat "$WORK/msl_splitk8.metallib" "$WORK/msl_splitk12.metallib" > "$WORK/msl_splitk_all.bin"

python3 "$REPO_ROOT/mma_forge/tools/extract_blob.py" "$WORK/msl_splitk_all.bin" "$OUT_C" \
    --symbol algenta_msl_splitk_blob

echo "build_msl_splitk_blob: wrote $OUT_C"
