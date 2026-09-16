#!/usr/bin/env bash
# run_ab_7b_front6.sh — pinned-clocks interleaved A/B for FRONT 6 (the third attempt to flip the
# RAG-4096 0.9556x loss vs TensorRT-LLM 1.2.1 without regressing pp256 / pp1024 / decode).
#
# The baseline here is FRONT 5's SHIP ARM `_f1` (ROPEVEC on top of round 4's `_e3`), rebuilt
# fresh from THIS branch — never a remembered number. Every FRONT-6 lever is a build flag that
# defaults OFF, so `_g0` is byte-for-byte round 5's adopted binary.
#
#   _g0  baseline   round 5's ship arm: _e3 + 7B_PF_ROPEVEC
#                   (= round 2 base + F16NORM/F16MLP/CTX8192 + FA/FASTEXP/BIASROPE
#                      + KVTWIN/FA2 + ROPEVEC)
#   _g1  _g0 + ALGENTA_PF_PASS4096    lever: one 4096-row prefill pass instead of four
#                   1024-row passes. gemm_probe --msweep prices the SAME 1905.3 GFLOP of
#                   per-layer projection work at 216.990 ms per RAG-4096 prefill for 4x1024
#                   against 205.148 ms for 1x4096 (-11.8 ms) and 204.374 ms for 2x2048; the
#                   cause is tail-wave quantization (m=1024, N=3584 = 224 tiles of 128x128 =
#                   2.07 waves on 108 SMs). NOT bit-identical -- a different M re-selects the
#                   cuBLAS algorithm and so the reduction order -- so the token gates decide it.
#                   Cannot touch pp256/pp1024: m is min(n_prompt, cap), and both are <= 1024.
#   _g2  _g1 + ALGENTA_7B_PF_LTALGO   lever: dispatch the four projections through cublasLt on
#                   an algorithm chosen by a TIMED SEARCH over the top-16 heuristics at stage
#                   time, instead of cublasGemmEx's CUBLAS_GEMM_DEFAULT (which re-runs its
#                   heuristic on all 448 calls and which tc_shim_init never gave a workspace,
#                   so split-K was out of reach). gemm_probe at m=4096: qkv -15.1%, o_proj
#                   -19.1%, down -13.8%, gate/up -1.2% = -550.9 us per layer = -15.43 ms over
#                   28 layers. Links a SEPARATE shim object built with -D ALGENTA_TC_SHIM_LT
#                   plus -lcublasLt, so `_g0`/`_g1` link a shim whose bytes carry none of it.
#                   The two levers COMPOUND: the wide pass is what exposes the tail-wave
#                   headroom a better algorithm can then take (at m=1024 the same search is
#                   worth only -36.35 us/layer = -4.07 ms).
#
# REFUTED BY MEASUREMENT BEFORE ANY LEVER WAS BUILT (recorded in the ledger, not raced):
# round 5 ranked "HOST/LAUNCH GAP ~6-10 ms at RAG (wall 284.805 vs GPU busy ~276)" as the
# round's best expected-value attack. front6_decomp.py on a fresh _g0 capture puts the STEADY
# STATE full-prefill window at wall 284.097 ms / busy 280.953 ms -- a 3.144 ms (1.11%) gap,
# consistent across all six warm prefills (3.026-3.246 ms). The "~276" was round 4's busy for
# _e3, stale by ROPEVEC's -3.705 ms. 82.6% of the gap is 1515 uniform 1-5 us per-launch gaps
# over 1580 launches; the only structure in it is the three chunk seams (~200 us each, the
# per-chunk token upload + ctx.synchronize()). So there is at most ~3.1 ms to recover, which
# re-confirms round 3's refutation of prefill CUDA graphs -- RE-MEASURED here, not inherited.
# The first cold prefill in the same capture carries a 383.804 ms gap (58% of its 661.117 ms
# wall) from per-shape cuBLAS first-call costs; that is a warmup artifact the 20-run median
# never sees, and it is why the median window is the one reported.
#
# Protocol (rounds 2-5's, unchanged): one process per arm per cell; each cell is the driver's own
# median of --runs 20 with rel-IQR and outlier reporting; arms interleaved with the baseline
# bracketing the sweep as drift armor; clocks read before and after every cell; G0 (16/16 greedy
# tokens vs the fp32 transformers oracle) and G1 (64/64 self-consistency) run inside every bench
# process, so every cell in this sweep is gate-checked by construction.
#
# ROUND TAG (round 5's log-overwrite gotcha, fixed by construction): EXTRA_TAG is `_ra${ROUND}`
# and ROUND defaults to a UTC timestamp, so two stages of the same round can never silently
# overwrite each other's bench logs. Pass ROUND=<n> only when you WANT the collision.
#
# VRAM HYGIENE (owner rule): every arm is its own short-lived process — nothing is left resident
# between stages, and the GPU is drained to 0 MiB before the next arm is launched.
#
# Usage (on algenta-ent-a100, from the repo root):
#   bash run_ab_7b_front6.sh                       # build every arm + the interleaved sweep
#   BUILD_ARMS=0 RUN_SWEEP=0 RUN_RAG=1 RAG_ARMS="_g0 _g1" bash run_ab_7b_front6.sh
#   BUILD_ONLY="_g1" BUILD_ARMS=1 RUN_SWEEP=0 bash run_ab_7b_front6.sh   # compile check only
set -uo pipefail
SRC=benchmarks/llm_smoke/nvidia_race/qwen25_7b_p3_graph_cuda.mojo
SHIM=benchmarks/llm_smoke/nvidia_race/tc_shim.cu
RTK=benchmarks/llm_smoke/nvidia_race/tc_rt_kernels.cu
NV=${NV:-$HOME/front6/bin}
CKPT=${CKPT:-/tmp/w7b/ckpt}
MEAS=${MEAS:-$HOME/trtllm/front6}
RUNS=${RUNS:-20}
SM=${SM:-sm_80}
CUDA_HOME=${CUDA_HOME:-/usr/local/cuda}
ENV_DIR=${ENV_DIR:-$HOME/w7b/mojo_env/.pixi/envs/default}
MOJO=${MOJO:-$ENV_DIR/bin/mojo}
export MODULAR_HOME=${MODULAR_HOME:-$ENV_DIR/share/max}
TC_OBJ=${TC_OBJ:-/tmp/front6_tc_shim_${SM}.o}
TC_OBJ_LT=${TC_OBJ_LT:-/tmp/front6_tc_shim_lt_${SM}.o}
PTXD=${PTXD:-/tmp/front6_ptxd_${SM}}
# round 2's adopted base + round 3's three levers + round 4's two + round 5's one = FRONT 6's `_g0`
BASE="-D ALGENTA_GPU -D ALGENTA_CUDA -D ALGENTA_STAGE_18944 -D ALGENTA_PF_ONEPASS_B1 \
-D ALGENTA_PF_ATTN_FLASH_B1 -D ALGENTA_PF_ATTN_FLASH2_B1 -D ALGENTA_TC_NOSEAM \
-D ALGENTA_7B_PF_TCATTN -D ALGENTA_TC_SHIM -D ALGENTA_7B_PF_SM1P \
-D ALGENTA_7B_PF_F16NORM -D ALGENTA_7B_PF_F16MLP -D ALGENTA_7B_CTX8192 \
-D ALGENTA_7B_PF_FA -D ALGENTA_7B_PF_FASTEXP -D ALGENTA_7B_PF_BIASROPE"
G0="-D ALGENTA_7B_PF_KVTWIN -D ALGENTA_7B_PF_FA2 -D ALGENTA_7B_PF_ROPEVEC"

mkdir -p "$NV" "$MEAS" "$PTXD"

# The oracle is regenerated per boot (/tmp is wiped). A missing ref_tokens.json must not turn
# every cell into a silent G0-skip: say so loudly and let G1 (self-consistency) still run.
REF=/tmp/w7b/gate/ref_tokens.json
ORACLE=""
if [ -f "$REF" ]; then
    ORACLE=$(python3 - "$REF" <<'PY'
import json, sys
ref = json.load(open(sys.argv[1]))
print(",".join(str(int(t)) for t in ref["fixture"]["generated_ids"][:16]))
PY
)
else
    echo "WARN: $REF missing -- G0 will NOT run in these cells (G1 still does). Regenerate with ~/a2a/run_oracle.sh"
fi

build_shim() { # out_obj [extra nvcc -D ...]
    # the shim #includes the embedded-PTX header build_tc_drivers.sh's recipe generates
    if [[ ! -f "$PTXD/tc_rt_ptx.h" ]]; then
        "$CUDA_HOME/bin/nvcc" -ptx -arch=compute_80 "$RTK" -o "$PTXD/tc_rt_kernels.ptx" || return 1
        python3 - "$PTXD/tc_rt_kernels.ptx" "$PTXD/tc_rt_ptx.h" <<'PY' || return 1
import sys
src, dst = sys.argv[1], sys.argv[2]
data = open(src, "rb").read()
chunks = []
for i in range(0, len(data), 24):
    chunks.append(",".join(str(b) for b in data[i:i + 24]))
with open(dst, "w") as out:
    out.write("/* generated by run_ab_7b_front6.sh - embedded PTX */\n")
    out.write("static const unsigned char g_tc_rt_ptx[] = {\n")
    out.write(",\n".join(chunks))
    out.write(",0};\n")
PY
    fi
    local out="$1"; shift
    echo "== nvcc tc_shim.cu ${*:-(stock)} -> $out"
    rm -f "$out"
    "$CUDA_HOME/bin/nvcc" -O3 -arch="$SM" -Xcompiler -fPIC -I"$PTXD" -Xptxas -v "$@" \
        -c "$SHIM" -o "$out" 2>&1 \
        | grep -E "error|_fa_causal_kernel|_fa2_causal_kernel|_fa3_causal_kernel|registers|spill" \
        | head -60
    [[ -f "$out" ]] || { echo "SHIM BUILD FAIL $out"; return 1; }
}

build_arm() { # suffix extra-flags...   (stock shim object, stock link line)
    local suf="$1"; shift
    # shellcheck disable=SC2086
    "$MOJO" build $BASE "$@" --target-accelerator "$SM" -I mojo/engine -I attention_forge \
        "$SRC" -o "$NV/qwen25_7b_p3_graph_cuda${suf}" \
        -Xlinker "$TC_OBJ" -Xlinker -lcublas -Xlinker -lcudart -Xlinker "-L$CUDA_HOME/lib64" \
        > "$MEAS/build_${suf}.log" 2>&1 \
        && echo "BUILD_OK $suf" || { echo "BUILD_FAIL $suf (tail):"; tail -25 "$MEAS/build_${suf}.log"; return 1; }
}

# The LT twin: a SEPARATE shim object compiled with -D ALGENTA_TC_SHIM_LT and a link line that
# adds -lcublasLt. Two objects rather than one shared object is the point -- the stock object is
# compiled without the macro, so the entire cublasLt block is preprocessed away and `_g0`/`_g1`
# link a shim whose bytes carry no part of the LTALGO lever. An arm that passes the Mojo flag but
# links the stock object fails at link time on an undefined symbol, which is the loud failure we
# want; there is no stub that could let such a cell run and report the shipped path instead.
build_arm_lt() { # suffix extra-flags...
    local suf="$1"; shift
    # shellcheck disable=SC2086
    "$MOJO" build $BASE "$@" --target-accelerator "$SM" -I mojo/engine -I attention_forge \
        "$SRC" -o "$NV/qwen25_7b_p3_graph_cuda${suf}" \
        -Xlinker "$TC_OBJ_LT" -Xlinker -lcublas -Xlinker -lcublasLt -Xlinker -lcudart \
        -Xlinker "-L$CUDA_HOME/lib64" \
        > "$MEAS/build_${suf}.log" 2>&1 \
        && echo "BUILD_OK $suf (lt shim)" \
        || { echo "BUILD_FAIL $suf (tail):"; tail -25 "$MEAS/build_${suf}.log"; return 1; }
}

wait_gpu_idle() {
    for _ in $(seq 1 300); do
        [ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)" ] && return 0
        sleep 2
    done
    return 1
}

run_arm() { # suffix [extra driver args...]
    local suf="$1"; shift
    wait_gpu_idle || echo "WARN: gpu not idle before $suf"
    local c0 c1 t0 t1
    c0=$(nvidia-smi --query-gpu=clocks.sm --format=csv,noheader)
    t0=$(date +%s)
    "$NV/qwen25_7b_p3_graph_cuda${suf}" --checkpoint "$CKPT" --arm p3 "$@" \
        > "$MEAS/bench_${suf}$EXTRA_TAG.log" 2>&1
    local rc=$?
    t1=$(date +%s)
    c1=$(nvidia-smi --query-gpu=clocks.sm --format=csv,noheader)
    local mused
    mused=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader)
    echo "== ${suf}${EXTRA_TAG} rc=$rc wall=$((t1 - t0))s clocks=${c0}->${c1} vram_after=${mused}"
    grep -E "^prefill|^gen |G0 RESULT|G1 RESULT|STAGED|TC FLAGS|TCFLAG|ARMED|DECLINED" \
        "$MEAS/bench_${suf}${EXTRA_TAG}.log" | head -28
}

want_arm() { case " ${BUILD_ONLY:-_g0 _g1 _g2} " in *" $1 "*) return 0;; esac; return 1; }

if [ "${BUILD_ARMS:-1}" = "1" ]; then
    # the stock object first and unconditionally: _g0 and _g1 link it, and it must be compiled
    # WITHOUT -D ALGENTA_TC_SHIM_LT so the cublasLt block is preprocessed away entirely.
    build_shim "$TC_OBJ" || exit 1
    # shellcheck disable=SC2086
    want_arm _g2 && { build_shim "$TC_OBJ_LT" -D ALGENTA_TC_SHIM_LT || exit 1; }
    # shellcheck disable=SC2086
    want_arm _g0 && build_arm _g0 $G0
    # shellcheck disable=SC2086
    want_arm _g1 && build_arm _g1 $G0 -D ALGENTA_PF_PASS4096
    # shellcheck disable=SC2086
    want_arm _g2 && build_arm_lt _g2 $G0 -D ALGENTA_PF_PASS4096 -D ALGENTA_7B_PF_LTALGO
fi

# ── the interleaved pp256/pp1024/decode sweep, baseline first and last (drift armor) ──
if [ "${RUN_SWEEP:-1}" = "1" ]; then
  for suf in ${ARMS:-_g0 _g1 _g2 _g0}; do
    EXTRA_TAG="_ra${ROUND:-$(date -u +%H%M%S)}"
    ORACLE_ARG=()
    [ -n "$ORACLE" ] && ORACLE_ARG=(--oracle "$ORACLE")
    run_arm "$suf" "${ORACLE_ARG[@]}" --runs "$RUNS" \
        --out "$MEAS/bench_${suf}${EXTRA_TAG}.txt"
  done
fi

# ── RAG-4096: the flip criterion. The three token-exact 4096-token prompts, long-context arms ──
# FRONT 6 change vs rounds 2-5: these cells now carry a REAL G0. Every previous round raced
# RAG-4096 with G1 (64/64 self-consistency) only, because the oracle covered the 256-token
# fixture and the five chat prompts and no long prompt -- and self-consistency cannot detect a
# lever that is deterministically WRONG. That gap is load-bearing this round: ALGENTA_PF_PASS4096
# only activates above 1024 prompt rows, so the fixture oracle says nothing about it. The driver's
# G0 IS valid under --prompt-ids (it sets n_prompt = len(race_ids), so the decode positions belong
# to the RAG prompt); it was only ever fed the wrong oracle. When ref_tokens_rag.json is absent
# the cell falls back to round 5's behaviour (G1 only) and says so, rather than silently
# comparing a RAG decode against the fixture oracle -- which FAILS 16/16 by construction and,
# worse, makes the driver exit before the timing cell runs.
if [ "${RUN_RAG:-0}" = "1" ]; then
  RAGREF=${RAGREF:-/tmp/w7b/gate/ref_tokens_rag.json}
  for suf in ${RAG_ARMS:-_g0 _g1 _g2}; do
    for i in ${RAG_PROMPTS:-0 1 2}; do
      IDS=$(python3 - "$i" <<'PY'
import json, sys
p = json.load(open("/home/angel/trtllm/prompts.json"))
print(",".join(str(int(t)) for t in p["rag"][int(sys.argv[1])]["ids"]))
PY
      )
      RORACLE=""
      if [ -f "$RAGREF" ]; then
        RORACLE=$(python3 - "$RAGREF" "$i" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
c = d.get(f"rag_{sys.argv[2]}")
print(",".join(str(int(t)) for t in c["generated_ids"][:16]) if c else "")
PY
        )
      fi
      EXTRA_TAG="_rag${i}_${ROUND:-$(date -u +%H%M%S)}"
      if [ -n "$RORACLE" ]; then
        run_arm "$suf" --prompt-ids "$IDS" --oracle "$RORACLE" --runs "$RUNS" \
            --out "$MEAS/rag${i}_${suf}.txt"
      else
        echo "WARN: $RAGREF has no rag_${i} case -- this cell carries G1 ONLY (no oracle gate)"
        run_arm "$suf" --prompt-ids "$IDS" --runs "$RUNS" \
            --out "$MEAS/rag${i}_${suf}.txt"
      fi
    done
  done
fi
echo "AB_FRONT6_DONE"
