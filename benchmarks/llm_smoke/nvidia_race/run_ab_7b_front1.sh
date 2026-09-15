#!/usr/bin/env bash
# run_ab_7b_front1.sh — pinned-clocks interleaved A/B for the 7B pp1024/RAG-4096 lever round
# (2026-09-15, the TensorRT-LLM 1.2.1 gap campaign). Every arm below is ONE build flag set on
# top of the shipped TC arm; all three levers default OFF, so the baseline binary is the
# unmodified `-D ALGENTA_7B_PF_TCATTN` arm. Run on algenta-ent-a100 (A100-SXM4-40GB),
# clocks pinned 1410, GPU idle between cells.
#
#   _f0  baseline   ONEPASS_B1 + FLASH_B1 + FLASH2_B1 + TC_NOSEAM + 7B_PF_TCATTN + TC_SHIM
#   _f1  + ALGENTA_7B_PF_SM1P      single-read shared-cached masked softmax   (MEASURED: refuted)
#   _f2  + ALGENTA_7B_PF_F16NORM   rmsnorm writes the f16 A, no shim convert  (MEASURED: small win)
#   _f3  + ALGENTA_7B_PF_F16MLP    f16 gate/up C + f16 SwiGLU -> f16 down A   (MEASURED: the win)
#   _f5  + F16NORM + F16MLP        the adopted pp256/pp1024 configuration
#   _c9  + F16NORM + F16MLP + ALGENTA_7B_CTX8192   the adopted long-context (RAG-4096) arm
#
# Protocol: one process per arm, each cell the driver's own median of 20 runs with rel-IQR and
# outlier reporting; arms interleaved with the baseline bracketing the sweep as drift armor;
# G0 (16/16 greedy tokens vs the fp32 transformers oracle) and G1 (64/64 self-consistency) run
# inside every bench process, and the full 6-prompt token-identity battery (run_gates_7b.py)
# gates the adopted arm before it ships.
set -uo pipefail
SRC=benchmarks/llm_smoke/nvidia_race/qwen25_7b_p3_graph_cuda.mojo
NV=${NV:-$HOME/fronts/bin}
CKPT=${CKPT:-/tmp/w7b/ckpt}
MEAS=${MEAS:-/tmp/front1}
RUNS=${RUNS:-20}
SM=${SM:-sm_80}
CUDA_HOME=${CUDA_HOME:-/usr/local/cuda}
MOJO=${MOJO:-$HOME/w7b/mojo_env/.pixi/envs/default/bin/mojo}
TC_OBJ=${TC_OBJ:-/tmp/tc_shim_${SM}.o}
BASE="-D ALGENTA_GPU -D ALGENTA_CUDA -D ALGENTA_STAGE_18944 -D ALGENTA_PF_ONEPASS_B1 \
-D ALGENTA_PF_ATTN_FLASH_B1 -D ALGENTA_PF_ATTN_FLASH2_B1 -D ALGENTA_TC_NOSEAM \
-D ALGENTA_7B_PF_TCATTN -D ALGENTA_TC_SHIM"

ORACLE=$(python3 - <<'PY'
import json
ref = json.load(open("/tmp/w7b/gate/ref_tokens.json"))
print(",".join(str(int(t)) for t in ref["fixture"]["generated_ids"][:16]))
PY
)
mkdir -p "$MEAS"

build_arm() { # suffix extra-flags
  local suf="$1"; shift
  # shellcheck disable=SC2086
  "$MOJO" build $BASE "$@" --target-accelerator "$SM" -I mojo/engine -I attention_forge \
    "$SRC" -o "$NV/qwen25_7b_p3_graph_cuda${suf}" \
    -Xlinker "$TC_OBJ" -Xlinker -lcublas -Xlinker -lcudart -Xlinker "-L$CUDA_HOME/lib64" \
    && echo "BUILD_OK $suf" || { echo "BUILD_FAIL $suf"; return 1; }
}
wait_gpu_idle() {
  for _ in $(seq 1 300); do
    [ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)" ] && return 0
    sleep 2
  done
  return 1
}
run_arm() { # suffix
  local suf="$1"
  wait_gpu_idle || echo "WARN: gpu not idle before $suf"
  local c0 c1
  c0=$(nvidia-smi --query-gpu=clocks.sm --format=csv,noheader)
  "$NV/qwen25_7b_p3_graph_cuda${suf}" --checkpoint "$CKPT" --arm p3 --oracle "$ORACLE" \
      --runs "$RUNS" --out "$MEAS/bench_${suf}.txt" > "$MEAS/bench_${suf}.log" 2>&1
  c1=$(nvidia-smi --query-gpu=clocks.sm --format=csv,noheader)
  echo "== ${suf} rc=$? clocks=${c0}->${c1}"
  grep -E "^prefill|^gen |G0 RESULT|G1 RESULT|STAGED" "$MEAS/bench_${suf}.log" | head -8
}

if [ "${BUILD_ARMS:-1}" = "1" ]; then
  build_arm _f0
  build_arm _f1 -D ALGENTA_7B_PF_SM1P
  build_arm _f2 -D ALGENTA_7B_PF_F16NORM
  build_arm _f3 -D ALGENTA_7B_PF_F16MLP
  build_arm _f5 -D ALGENTA_7B_PF_F16NORM -D ALGENTA_7B_PF_F16MLP
  build_arm _c9 -D ALGENTA_7B_PF_F16NORM -D ALGENTA_7B_PF_F16MLP -D ALGENTA_7B_CTX8192
fi

# interleaved sweep, baseline first and last (drift armor)
for suf in ${ARMS:-_f0 _f1 _f2 _f3 _f5 _c9 _f0}; do
  run_arm "$suf"
done

# RAG-4096 (FRONT 2) — the three token-exact 4096-token prompts, long-context arm only
if [ "${RUN_RAG:-1}" = "1" ]; then
  for i in 0 1 2; do
    IDS=$(python3 - "$i" <<'PY'
import json, sys
p = json.load(open("/home/angel/trtllm/prompts.json"))
print(",".join(str(int(t)) for t in p["rag"][int(sys.argv[1])]["ids"]))
PY
)
    wait_gpu_idle || true
    "$NV/qwen25_7b_p3_graph_cuda_c9" --checkpoint "$CKPT" --arm p3 --prompt-ids "$IDS" \
        --runs "$RUNS" --out "$MEAS/rag${i}_c9.txt" > "$MEAS/rag${i}_c9.log" 2>&1
    echo "== rag$i rc=$?"
    grep -E "^prefill|^gen |G1 RESULT|STAGED" "$MEAS/rag${i}_c9.log" | head -6
  done
fi
echo "AB_FRONT1_DONE"
