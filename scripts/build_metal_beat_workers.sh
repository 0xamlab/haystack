#!/usr/bin/env bash
# build_metal_beat_workers.sh -- campaign-local worker builder for feat/metal-beat.
#
# Compiles the attention/GEMM blobs (mma_forge/generated/*.c + attention_forge/generated/*.c,
# EXCLUDING the i8kv pair: kv_i8_quant_blob.c + native_kv_decode_attn_splitk_i8kv_blob.c make
# sampled logits nondeterministic -- the production recipe excludes them), then builds TWO GPU
# workers via scripts/build_mojo_binary.sh:
#   1. Qwen3 tier   (default 3072 staging)  -> mojo_build/gpu-worker/algenta-gpu-worker-mb-qwen3
#   2. TinyLlama tier (ALGENTA_STAGE_6144)  -> mojo_build/gpu-worker/algenta-gpu-worker-mb-llama
#
# Usage: bash scripts/build_metal_beat_workers.sh [qwen3|llama|all]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode-26.6.0.app/Contents/Developer}"

BLOB_OBJ_DIR="${ROOT}/mojo_build/blobs"
mkdir -p "${BLOB_OBJ_DIR}"

CLANG="$(xcrun --find clang)"
SDKROOT_PATH="$(xcrun --show-sdk-path)"

EXCLUDE_BLOBS=(kv_i8_quant_blob.c native_kv_decode_attn_splitk_i8kv_blob.c)

compile_blob() {
    local src="$1"
    local base
    base="$(basename "${src}" .c)"
    for ex in "${EXCLUDE_BLOBS[@]}"; do
        if [[ "$(basename "${src}")" == "${ex}" ]]; then
            return 0
        fi
    done
    local obj="${BLOB_OBJ_DIR}/${base}.o"
    if [[ ! -f "${obj}" || "${src}" -nt "${obj}" ]]; then
        echo "[blobs] compiling ${base}"
        "${CLANG}" -c -O2 -isysroot "${SDKROOT_PATH}" "${src}" -o "${obj}"
    fi
}

for src in "${ROOT}"/mma_forge/generated/*.c "${ROOT}"/attention_forge/generated/*.c; do
    compile_blob "${src}"
done

BLOB_OBJECTS="$(find "${BLOB_OBJ_DIR}" -name '*_blob.o' | sort | paste -sd, -)"
echo "[blobs] linking $(echo "${BLOB_OBJECTS}" | tr ',' '\n' | wc -l | tr -d ' ') blob objects"

FILTER="metaldispatch.qwen3_prefill_decode,metaldispatch.qwen3_decode,metaldispatch.contract,metaldispatch.session_prefill_policy"
STAGE_DIR="${ROOT}/mojo_build/.stage"
mkdir -p "${STAGE_DIR}"
cp "${ROOT}/mojo/engine/main.mojo" "${STAGE_DIR}/main.mojo"

build_worker() {
    local name="$1"
    shift
    echo "[build] ${name} $*"
    env MOJO_BUILD_METAL_GPU=1 \
    MOJO_RUNTIME_MODULE_FILTER="${FILTER}" \
    MOJO_SRC="${STAGE_DIR}/main.mojo" \
    DISPATCH_OUTPUT_PATH="${STAGE_DIR}/runtime_library_dispatch_generated.mojo" \
    MOJO_BUILD_EXTRA_OBJECTS="${BLOB_OBJECTS}" \
    BINARY_PATH="${ROOT}/mojo_build/gpu-worker/algenta-gpu-worker-${name}" \
    "$@" \
    bash "${ROOT}/scripts/build_mojo_binary.sh"
}

TARGET="${1:-all}"
case "${TARGET}" in
    qwen3) build_worker mb-qwen3 ;;
    llama) build_worker mb-llama MOJO_BUILD_EXTRA_DEFINES=ALGENTA_STAGE_6144 ;;
    all)
        build_worker mb-qwen3
        build_worker mb-llama MOJO_BUILD_EXTRA_DEFINES=ALGENTA_STAGE_6144
        ;;
    *) echo "unknown target: ${TARGET}" >&2; exit 2 ;;
esac
echo "[build] done"
