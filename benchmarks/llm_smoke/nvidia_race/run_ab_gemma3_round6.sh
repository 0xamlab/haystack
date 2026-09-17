#!/usr/bin/env bash
# run_ab_gemma3_round6.sh — pinned-clocks interleaved A/B for ROUND 6 of the gemma-3-27b-it
# TensorRT-LLM 1.2.1 prefill race (H200). Round 5 (PR #998) flipped all three cells with the
# five-lever stack; this round widens the margins, priority rag4096 (1.0135x is fragile). The
# lever under test is the raw-mma v2 of the fused windowed attention kernel (#994's 7B FA2
# techniques ported); FA2 defaults OFF, so the baseline arm here is #998's ship candidate
# (R5_all2) rebuilt from THIS branch — the bracketing baseline every delta is measured against.
#
#   R6_base       #998's full stack: TC_SHIM + G3_STREAM + G3_GEGLU_U4 + G3_ATTN_FLASH +
#                 G3_PF_TCATTN + FA + F16ATTN + F16NORM + F16MLP + ROPE2 (= R5_all2)
#   R6_fa2        R6_base + ALGENTA_G3_PF_FA2
#                 the window kernel v2: raw mma.sync m16n8k16 with the P tile's A-fragment
#                 packed in registers (sP + one fence per key block deleted), the O epilogue
#                 written straight to global (sO + its 33.8 KB window + its fence deleted),
#                 and cp.async K/V double buffering on the f16 route only (kv32=1 keeps the
#                 synchronous in-register-convert load — cp.async cannot convert).
#   R6_fa2_bn32   R6_fa2 + ALGENTA_G3_PF_BN32    (WANT_BN_ARMS=1) key-block-width sweep —
#   R6_fa2_bn128  R6_fa2 + ALGENTA_G3_PF_BN128   BN was inherited from the 7B WMMA kernel.
#
# PROTOCOL (the owner's, unchanged from round 5):
#   * oracle gate BEFORE any speed claim, on every changed arm: G0 16/16 + G1 64/64 greedy
#     tokens vs the cache-free fp32 transformers oracle, the 64-token run repeated for
#     determinism, val550, and rag4096 with the EOS-stop rule. A failed gate aborts the sweep.
#   * clocks pinned 1410 MHz, read before AND after every cell and re-pinned on drift, with a
#     1 Hz clock/power/util sampler running for the duration of every cell; off-pin cells are
#     reported by name, never dropped — a cell with an off-pin sample is re-taken.
#   * 3 warmup + 7 measured per cell, arms INTERLEAVED run-by-run, and arm A re-run at the END
#     of each prompt group so the group is A..B..A: the bracketing drift is measured, and a
#     lever delta that does not exceed it is reported NOT RESOLVED rather than as a win. The
#     20-run A/B median comes from running the timing stage over three brackets.
#   * every cell runs under ~/lever3/cell_watchdog.sh (600 s stall -> SIGKILL the process
#     group -> continue -> an explicit {"stalled":true} marker), so a wedged driver can never
#     silently burn an hour or be misread as a crashed arm.
#   * TRT-LLM 1.2.1 re-served FRESH in the same session for the final ratios (byte-identical
#     config to the stored H200 column: pytorch backend, FLASHINFER, bf16, tp 1, 1410 MHz,
#     same prompts, same client, same 3 warmup + 7 measured), and the re-serve must reproduce
#     round 5's same-session column (41.520 / 110.782 / 426.766 ms) within 1% or the ratio is
#     labelled CROSS-SESSION.
#   * the flag audit (scripts/audit_tc_flags.sh) runs over the built binaries, so the published
#     cells carry proof of which flags the measured binary actually had.
#
# Usage (on trtllm-gemma-us-west1-c, from the repo root):
#   bash run_ab_gemma3_round6.sh                     # build every arm, gate, sweep, re-serve
#   STAGE=build bash run_ab_gemma3_round6.sh
#   STAGE=gate ARM=R6_fa2 bash run_ab_gemma3_round6.sh
#   STAGE=timing ARM_A=R6_base ARM_B=R6_fa2 bash run_ab_gemma3_round6.sh
#   BUILD_ARMS=0 STAGE=timing bash run_ab_gemma3_round6.sh
set -uo pipefail

SM=${SM:-sm_90}
GPU=${GPU:-1}
SRC_TREE=${SRC_TREE:-$HOME/g3r6}          # the synced worktree the arms are built from
DRIVER=${DRIVER:-$HOME/adj/build/driver_ctx8192.mojo}   # STOCK, unmodified
CKPT=${CKPT:-/mnt/ramblob/g3conv27b}
L6=${L6:-$HOME/lever6}
L3=${L3:-$HOME/lever3}                    # cell_watchdog.sh + gate_any.py live here
CUDA_HOME=${CUDA_HOME:-/usr/local/cuda}
ENV_DIR=${ENV_DIR:-$HOME/algenta/mojo_env/.pixi/envs/default}
MOJO=${MOJO:-$ENV_DIR/bin/mojo}
export MODULAR_HOME=${MODULAR_HOME:-$ENV_DIR/share/max}
export CUDA_VISIBLE_DEVICES=$GPU
TC_OBJ=${TC_OBJ:-/tmp/g3r6tc/tc_shim.o}
STAGE=${STAGE:-all}
ARM=${ARM:-R6_fa2}
ARM_A=${ARM_A:-R6_base}
ARM_B=${ARM_B:-R6_fa2}
ARM_C=${ARM_C-R6_kv16}           # third interleaved arm; an explicitly EMPTY env stays empty
                                # (:- would resurrect the default on the chains' ARM_C=)
BUILD_ARMS=${BUILD_ARMS:-1}
PY=/usr/bin/python3

BASE="-D ALGENTA_GPU -D ALGENTA_CUDA -D ALGENTA_STAGE_6144 -D ALGENTA_G3_GEGLU_U4 \
-D ALGENTA_TC_SHIM -D ALGENTA_G3_ATTN_FLASH -D ALGENTA_G3_PF_TCATTN -D ALGENTA_G3_STREAM"

mkdir -p "$L6/runs" "$L6/logs" "$L6/clocks" "$(dirname "$TC_OBJ")"
CW_LOGFILE=$L6/lever6.log
export CW_LOGFILE
# shellcheck disable=SC1091
source "$L3/cell_watchdog.sh"
cw_init "$L6/runs" "$L6/logs" "$L6/clocks" "$GPU"

ts() { date -u +%FT%TZ; }
log() { echo "[$(ts)] $*" | tee -a "$CW_LOGFILE"; }

build_shim() {
  log "=== tc_shim.o from $SRC_TREE (nvcc -arch=$SM) ==="
  # Delegated to build_shim_gemma3_round6.sh, which generates the embedded-PTX header first:
  # tc_shim.cu #includes "tc_rt_ptx.h" (generated from tc_rt_kernels.cu), so a bare nvcc on a
  # fresh box dies with `tc_rt_ptx.h: No such file or directory`. It only ever worked before
  # because an older run had left the header in the -I directory -- which an instance restart
  # wipes, and which is exactly how this round's probe stage and follow-on build both died at
  # the last step of long chains.
  PTXD="$(dirname "$TC_OBJ")" SM="$SM" CUDA_HOME="$CUDA_HOME" \
    NR="$SRC_TREE/benchmarks/llm_smoke/nvidia_race" \
    bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/build_shim_gemma3_round6.sh" \
    > "$L6/logs/nvcc.log" 2>&1
  local rc=$?
  log "nvcc rc=$rc bytes=$(stat -c %s "$TC_OBJ" 2>/dev/null)"
  (( rc != 0 )) && { tail -40 "$L6/logs/nvcc.log" | tee -a "$CW_LOGFILE"; return 1; }
  # the fused kernel's own standalone correctness harness (host double-precision reference,
  # every raced shape, all four kv32/of16 combinations). Runs BEFORE anything is gated or
  # timed: an off-by-one in the window's key-block floor is exactly the defect that can move a
  # few logits and still argmax to the same tokens.
  if [[ -f "$SRC_TREE/benchmarks/llm_smoke/nvidia_race/fa_g3_probe.cu" ]]; then
    log "=== fa_g3_probe: the fused windowed kernel vs a host double-precision reference ==="
    "$CUDA_HOME/bin/nvcc" -O3 -arch="$SM" \
      "$SRC_TREE/benchmarks/llm_smoke/nvidia_race/fa_g3_probe.cu" "$TC_OBJ" \
      -lcublas -lcudart -o /tmp/fa_g3_probe > "$L6/logs/probe_build.log" 2>&1
    if [[ -x /tmp/fa_g3_probe ]]; then
      /tmp/fa_g3_probe --iters 20 2>&1 | tee "$L6/logs/fa_g3_probe.log" | tee -a "$CW_LOGFILE"
      grep -q "=== fa_g3_probe: 0 FAIL" "$L6/logs/fa_g3_probe.log" \
        || { log "FA PROBE FAILED -- no arm may be gated or timed"; return 1; }
    else
      log "fa_g3_probe did not build; see $L6/logs/probe_build.log"; return 1
    fi
  fi
  return 0
}

build_arm() { # $1 = name ; rest = extra flags
  local name=$1; shift
  local extra="$*"
  log "=== build $name : extra=[$extra] ==="
  ( cd "$SRC_TREE" && $MOJO build $BASE $extra \
      --target-accelerator "$SM" -I mojo/engine -I attention_forge \
      "$DRIVER" -o "$L6/$name" \
      -Xlinker "$TC_OBJ" -Xlinker -lcublas -Xlinker -lcudart \
      -Xlinker -L"$CUDA_HOME/lib64" ) > "$L6/logs/build_$name.log" 2>&1
  local rc=$?
  log "build $name rc=$rc bytes=$(stat -c %s "$L6/$name" 2>/dev/null)"
  if (( rc != 0 )) || [[ ! -x "$L6/$name" ]]; then
    tail -40 "$L6/logs/build_$name.log" | tee -a "$CW_LOGFILE"; return 1
  fi
  return 0
}

if (( BUILD_ARMS == 1 )) && [[ "$STAGE" == "all" || "$STAGE" == "build" ]]; then
  build_shim || exit 1
  # R6_base is #998's ship candidate (R5_all2 = the full five-lever round-5 stack) rebuilt from
  # THIS branch: FA2 is flag-off in it, so the dispatch path is round 5's verbatim and the
  # bracket measures the v2 kernel against the exact binary that produced 32.108/100.361/421.085.
  R5_STACK="-D ALGENTA_G3_PF_FA -D ALGENTA_G3_PF_F16ATTN -D ALGENTA_G3_PF_F16NORM \
-D ALGENTA_G3_PF_F16MLP -D ALGENTA_G3_PF_ROPE2"
  build_arm R6_base   $R5_STACK || exit 1
  build_arm R6_fa2    $R5_STACK -D ALGENTA_G3_PF_FA2 || exit 1
  build_arm R6_kv16   $R5_STACK -D ALGENTA_G3_PF_FA2 -D ALGENTA_G3_PF_KV16 || exit 1
  if (( ${WANT_BN_ARMS:-0} == 1 )); then
    build_arm R6_kv16_bn32 $R5_STACK -D ALGENTA_G3_PF_FA2 -D ALGENTA_G3_PF_KV16 \
                                 -D ALGENTA_G3_PF_BN32 || exit 1
  fi
  log "=== flag audit over the built arms (scripts/audit_tc_flags.sh) ==="
  bash "$SRC_TREE/scripts/audit_tc_flags.sh" --bin-dir "$L6" --glob 'R6_*' \
       --logs "$L6/runs" --out "$L6/flag_audit.json" 2>&1 | tee -a "$CW_LOGFILE"
fi
[[ "$STAGE" == "build" ]] && { log "STAGE=build complete"; exit 0; }

# everything below needs the GPU. The cells (watchdog, clock pinning, 1 Hz sampler, the
# interleaved bracket) live in run_gemma3_round6_cells.sh next to this script, so the protocol
# has exactly one definition and this file only decides the order of the stages.
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
CELLS_SH=${CELLS_SH:-$HERE/run_gemma3_round6_cells.sh}
SUMMARIZE=${SUMMARIZE:-$HERE/summarize_gemma3_round6.py}
export BIN_DIR="$L6" MEAS="$L6" CW_LOGFILE

if [[ "$STAGE" == "all" || "$STAGE" == "smoke" ]]; then
  log "=== smoke: does the fused kernel ARM, and what is the first delta? ==="
  STAGE=smoke ARM_A="$ARM_A" ARM_B="$ARM_B" ARM_C="$ARM_C" bash "$CELLS_SH" || exit 1
fi
[[ "$STAGE" == "smoke" ]] && exit 0

if [[ "$STAGE" == "all" || "$STAGE" == "gate" ]]; then
  log "=== oracle gate on $ARM ==="
  STAGE=gate ARM="$ARM" bash "$CELLS_SH" || {
    log "GATE FAILED for $ARM -- no timing cells, no ratios, nothing publishable"; exit 1; }
fi
[[ "$STAGE" == "gate" ]] && exit 0

if [[ "$STAGE" == "all" || "$STAGE" == "timing" ]]; then
  log "=== interleaved bracketed A/B: $ARM_A vs $ARM_B ==="
  STAGE=timing ARM_A="$ARM_A" ARM_B="$ARM_B" ARM_C="$ARM_C" bash "$CELLS_SH" || exit 1
fi
[[ "$STAGE" == "timing" ]] && exit 0

if [[ "$STAGE" == "all" ]]; then
  log "=== same-session TRT-LLM 1.2.1 re-serve ==="
  GPU=$GPU bash "$L3/lv3_trtllm.sh" 2>&1 | tee -a "$CW_LOGFILE"
  cp -f "$L3"/runs/trtllm_pp256.json "$L3"/runs/trtllm_pp1024.json \
        "$L3"/runs/trtllm_rag4096.json "$L6/runs/" 2>/dev/null
  log "=== per-kernel nsys decomposition ==="
  GPU=$GPU bash "$HERE/run_nsys_gemma3_round6.sh" 2>&1 | tee -a "$CW_LOGFILE"
  log "=== report ==="
  $PY "$SUMMARIZE" ${SUMMARIZE_ARMS:-R6_base R6_fa2 R6_kv16} 2>&1 | tee -a "$CW_LOGFILE"
fi

log "=== run_ab_gemma3_round6.sh COMPLETE ==="
nvidia-smi --query-gpu=index,clocks.current.sm,memory.used --format=csv,noheader | tee -a "$CW_LOGFILE"
