#!/bin/bash
# build_msl_parity_blob.sh -- Phase 3 (hybrid per-role Metal GEMM backend): compiles the three
# msl_parity_*.metal PRODUCTION-WIRING replicas of llama.cpp's kernel_mul_mm_f16_f32 into ONE
# metallib PER KERNEL (batch_shim.m's algenta_open_session registers ONLY functionNames[0] of each
# MTLB blob it scans out of __TEXT,__const, so all three kernels must ship as three separate
# metallibs), concatenates them, and renders the result as the symbol-free C byte array
# mma_forge/generated/msl_parity_blob.c through the EXISTING blob mechanism this repo already uses
# for every mma_forge/attention_forge blob (mma_forge/tools/extract_blob.py -- the same script that
# rendered mm8_blob.c / mm8_vecload4_blob.c / etc.). No new linking mechanism: the generated .c is
# clang -c'd and -Xlinker'd into the production binary exactly like its siblings.
#
# Usage (repo root):
#   bash mma_forge/tools/build_msl_parity_blob.sh
#
# Requires: DEVELOPER_DIR pointing at the pinned Xcode (this repo's standard
# /Applications/Xcode-26.6.0.app/Contents/Developer), python3.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC_DIR="$REPO_ROOT/benchmarks/llm_smoke/metal_llama_parity_replica"
OUT_C="$REPO_ROOT/mma_forge/generated/msl_parity_blob.c"
WORK="$(mktemp -d /tmp/msl_parity_blob.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT

export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode-26.6.0.app/Contents/Developer}"

# One air + one metallib per kernel, in the FIXED discovery order the session's substring discovery
# relies on (qkv_proj, gemm_accum, swiglu) -- order inside the concatenated byte array only affects
# which pipeline INDEX each kernel gets, never correctness, but a stable order keeps the indices
# reproducible build-to-build.
for role in qkv_proj:qkv gemm_accum:accum swiglu:swiglu; do
    kernel="${role%%:*}"
    short="${role##*:}"
    xcrun -sdk macosx metal -c "$SRC_DIR/msl_parity_${kernel}_mul_mm.metal" -o "$WORK/msl_parity_${short}.air"
    xcrun -sdk macosx metallib "$WORK/msl_parity_${short}.air" -o "$WORK/msl_parity_${short}.metallib"
done

cat "$WORK/msl_parity_qkv.metallib" "$WORK/msl_parity_accum.metallib" "$WORK/msl_parity_swiglu.metallib" \
    > "$WORK/msl_parity_all.bin"

python3 "$REPO_ROOT/mma_forge/tools/extract_blob.py" "$WORK/msl_parity_all.bin" "$OUT_C" \
    --symbol algenta_msl_parity_blob

echo "build_msl_parity_blob: wrote $OUT_C"
