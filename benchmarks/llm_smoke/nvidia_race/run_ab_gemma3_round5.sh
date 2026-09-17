#!/usr/bin/env bash
# run_ab_gemma3_round5.sh — pinned-clocks interleaved A/B for ROUND 5 of the gemma-3-27b-it
# TensorRT-LLM 1.2.1 prefill race (H200, 2026-09-16). Every arm is ONE build-flag set on top
# of PR #993's adopted arm, and all four round-5 levers default OFF, so `_base` here is
# byte-for-byte the #993 binary rebuilt from THIS branch — the bracketing baseline every delta
# is measured against.
#
#   _base  PR #993: TC_SHIM + G3_STREAM + G3_GEGLU_U4 + G3_ATTN_FLASH + G3_PF_TCATTN
#                   (the FIVE-PASS tensor-core attention chain: head-major Q pack, strided-
#                    batched QK^T, masked softmax, strided-batched PV, head-major O unpack,
#                    plus a per-layer f32->f16 K/V staging pass)
#   _fa    _base + ALGENTA_G3_PF_FA
#                   ONE fused windowed WMMA FlashAttention-2 kernel (tc_shim.cu) replacing all
#                   five passes AND the K/V staging: the sliding window becomes a key-block
#                   range, so a local layer never loads the keys it would mask away.
#   _mlp   _base + ALGENTA_G3_PF_F16NORM + ALGENTA_G3_PF_F16MLP
#                   the pre-staged-A f16 chain: both rmsnorms write the f16 A the qkv/gate-up
#                   GEMMs read directly, the gate/up GEMM writes f16 C, and the GeGLU epilogue
#                   writes the f16 A down_proj reads directly — the shim's per-call
#                   f32->f16 A conversion (and the f32 [m,2*d_ff] C round trip) disappear.
#   _all   _base + FA + F16ATTN + F16NORM + F16MLP    the full stack (the ship candidate)
#   _ctl   _fa rebuilt with _G3_PF_FA_KV32=0 — the CONTROL for the native-f32-KV claim: the
#                   same fused kernel reading a staged f16 K/V, i.e. the staging pass left in.
#
# PROTOCOL (the owner's, unchanged from the H200 re-race):
#   * oracle gate BEFORE any speed claim, on every arm: G0 16/16 + G1 64/64 greedy tokens vs
#     the cache-free fp32 transformers oracle, the 64-token run repeated for determinism,
#     val550, and rag4096 with the EOS-stop rule. A failed gate aborts the sweep.
#   * clocks pinned 1410 MHz, read before AND after every cell and re-pinned on drift, with a
#     1 Hz clock/power/util sampler running for the duration of every cell; off-pin cells are
#     reported by name, never dropped.
#   * 3 warmup + 7 measured per cell, arms INTERLEAVED run-by-run, and arm A re-run at the END
#     of each prompt group so the group is A..B..A: the bracketing drift is measured, and a
#     lever delta that does not exceed it is reported NOT RESOLVED rather than as a win.
#   * every cell runs under ~/lever3/cell_watchdog.sh (600 s stall -> SIGKILL the process
#     group -> continue -> an explicit {"stalled":true} marker), so a wedged driver can never
#     silently burn an hour or be misread as a crashed arm.
#   * TRT-LLM 1.2.1 re-served FRESH in the same session for the final ratios (byte-identical
#     config to the stored H200 column: pytorch backend, FLASHINFER, bf16, tp 1, 1410 MHz,
#     same prompts, same client, same 3 warmup + 7 measured), and the re-serve must reproduce
#     the stored column within 1% or the ratio is labelled CROSS-SESSION.
#   * the flag audit (scripts/audit_tc_flags.sh) runs over the built binaries, so the published
#     cells carry proof of which flags the measured binary actually had.
#
# Usage (on trtllm-gemma-us-west1-c, from the repo root):
#   bash run_ab_gemma3_round5.sh                     # build every arm, gate, sweep, re-serve
#   STAGE=build bash run_ab_gemma3_round5.sh
#   STAGE=gate ARM=R5_all bash run_ab_gemma3_round5.sh
#   STAGE=timing ARM_A=R5_base ARM_B=R5_all bash run_ab_gemma3_round5.sh
#   BUILD_ARMS=0 STAGE=timing bash run_ab_gemma3_round5.sh
set -uo pipefail

SM=${SM:-sm_90}
GPU=${GPU:-1}
SRC_TREE=${SRC_TREE:-$HOME/g3r5}          # the synced worktree the arms are built from
DRIVER=${DRIVER:-$HOME/adj/build/driver_ctx8192.mojo}   # STOCK, unmodified
CKPT=${CKPT:-/mnt/ramblob/g3conv27b}
L5=${L5:-$HOME/lever5}
L3=${L3:-$HOME/lever3}                    # cell_watchdog.sh + gate_any.py live here
CUDA_HOME=${CUDA_HOME:-/usr/local/cuda}
ENV_DIR=${ENV_DIR:-$HOME/algenta/mojo_env/.pixi/envs/default}
MOJO=${MOJO:-$ENV_DIR/bin/mojo}
export MODULAR_HOME=${MODULAR_HOME:-$ENV_DIR/share/max}
export CUDA_VISIBLE_DEVICES=$GPU
TC_OBJ=${TC_OBJ:-/tmp/g3r5tc/tc_shim.o}
STAGE=${STAGE:-all}
ARM=${ARM:-R5_all}
ARM_A=${ARM_A:-R5_base}
ARM_B=${ARM_B:-R5_all}
BUILD_ARMS=${BUILD_ARMS:-1}
PY=/usr/bin/python3

BASE="-D ALGENTA_GPU -D ALGENTA_CUDA -D ALGENTA_STAGE_6144 -D ALGENTA_G3_GEGLU_U4 \
-D ALGENTA_TC_SHIM -D ALGENTA_G3_ATTN_FLASH -D ALGENTA_G3_PF_TCATTN -D ALGENTA_G3_STREAM"

mkdir -p "$L5/runs" "$L5/logs" "$L5/clocks" "$(dirname "$TC_OBJ")"
CW_LOGFILE=$L5/lever5.log
export CW_LOGFILE
# shellcheck disable=SC1091
source "$L3/cell_watchdog.sh"
cw_init "$L5/runs" "$L5/logs" "$L5/clocks" "$GPU"

ts() { date -u +%FT%TZ; }
log() { echo "[$(ts)] $*" | tee -a "$CW_LOGFILE"; }

build_shim() {
  log "=== tc_shim.o from $SRC_TREE (nvcc -arch=$SM) ==="
  # Delegated to build_shim_gemma3_round5.sh, which generates the embedded-PTX header first:
  # tc_shim.cu #includes "tc_rt_ptx.h" (generated from tc_rt_kernels.cu), so a bare nvcc on a
  # fresh box dies with `tc_rt_ptx.h: No such file or directory`. It only ever worked before
  # because an older run had left the header in the -I directory -- which an instance restart
  # wipes, and which is exactly how this round's probe stage and follow-on build both died at
  # the last step of long chains.
  PTXD="$(dirname "$TC_OBJ")" SM="$SM" CUDA_HOME="$CUDA_HOME" \
    NR="$SRC_TREE/benchmarks/llm_smoke/nvidia_race" \
    bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/build_shim_gemma3_round5.sh" \
    > "$L5/logs/nvcc.log" 2>&1
  local rc=$?
  log "nvcc rc=$rc bytes=$(stat -c %s "$TC_OBJ" 2>/dev/null)"
  (( rc != 0 )) && { tail -40 "$L5/logs/nvcc.log" | tee -a "$CW_LOGFILE"; return 1; }
  # the fused kernel's own standalone correctness harness (host double-precision reference,
  # every raced shape, all four kv32/of16 combinations). Runs BEFORE anything is gated or
  # timed: an off-by-one in the window's key-block floor is exactly the defect that can move a
  # few logits and still argmax to the same tokens.
  if [[ -f "$SRC_TREE/benchmarks/llm_smoke/nvidia_race/fa_g3_probe.cu" ]]; then
    log "=== fa_g3_probe: the fused windowed kernel vs a host double-precision reference ==="
    "$CUDA_HOME/bin/nvcc" -O3 -arch="$SM" \
      "$SRC_TREE/benchmarks/llm_smoke/nvidia_race/fa_g3_probe.cu" "$TC_OBJ" \
      -lcublas -lcudart -o /tmp/fa_g3_probe > "$L5/logs/probe_build.log" 2>&1
    if [[ -x /tmp/fa_g3_probe ]]; then
      /tmp/fa_g3_probe --iters 20 2>&1 | tee "$L5/logs/fa_g3_probe.log" | tee -a "$CW_LOGFILE"
      grep -q "=== fa_g3_probe: 0 FAIL" "$L5/logs/fa_g3_probe.log" \
        || { log "FA PROBE FAILED -- no arm may be gated or timed"; return 1; }
    else
      log "fa_g3_probe did not build; see $L5/logs/probe_build.log"; return 1
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
      "$DRIVER" -o "$L5/$name" \
      -Xlinker "$TC_OBJ" -Xlinker -lcublas -Xlinker -lcudart \
      -Xlinker -L"$CUDA_HOME/lib64" ) > "$L5/logs/build_$name.log" 2>&1
  local rc=$?
  log "build $name rc=$rc bytes=$(stat -c %s "$L5/$name" 2>/dev/null)"
  if (( rc != 0 )) || [[ ! -x "$L5/$name" ]]; then
    tail -40 "$L5/logs/build_$name.log" | tee -a "$CW_LOGFILE"; return 1
  fi
  return 0
}

if (( BUILD_ARMS == 1 )) && [[ "$STAGE" == "all" || "$STAGE" == "build" ]]; then
  build_shim || exit 1
  build_arm R5_base || exit 1
  build_arm R5_fa     -D ALGENTA_G3_PF_FA || exit 1
  build_arm R5_mlp    -D ALGENTA_G3_PF_F16NORM -D ALGENTA_G3_PF_F16MLP || exit 1
  build_arm R5_all    -D ALGENTA_G3_PF_FA -D ALGENTA_G3_PF_F16ATTN \
                      -D ALGENTA_G3_PF_F16NORM -D ALGENTA_G3_PF_F16MLP || exit 1
  log "=== flag audit over the built arms (scripts/audit_tc_flags.sh) ==="
  bash "$SRC_TREE/scripts/audit_tc_flags.sh" --bin-dir "$L5" --glob 'R5_*' \
       --logs "$L5/runs" --out "$L5/flag_audit.json" 2>&1 | tee -a "$CW_LOGFILE"
fi
[[ "$STAGE" == "build" ]] && { log "STAGE=build complete"; exit 0; }

# everything below needs the GPU. The cells (watchdog, clock pinning, 1 Hz sampler, the
# interleaved bracket) live in run_gemma3_round5_cells.sh next to this script, so the protocol
# has exactly one definition and this file only decides the order of the stages.
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
CELLS_SH=${CELLS_SH:-$HERE/run_gemma3_round5_cells.sh}
SUMMARIZE=${SUMMARIZE:-$HERE/summarize_gemma3_round5.py}
export BIN_DIR="$L5" MEAS="$L5" CW_LOGFILE

if [[ "$STAGE" == "all" || "$STAGE" == "smoke" ]]; then
  log "=== smoke: does the fused kernel ARM, and what is the first delta? ==="
  STAGE=smoke ARM_A="$ARM_A" ARM_B="$ARM_B" bash "$CELLS_SH" || exit 1
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
  STAGE=timing ARM_A="$ARM_A" ARM_B="$ARM_B" bash "$CELLS_SH" || exit 1
fi
[[ "$STAGE" == "timing" ]] && exit 0

if [[ "$STAGE" == "all" ]]; then
  log "=== same-session TRT-LLM 1.2.1 re-serve ==="
  GPU=$GPU bash "$L3/lv3_trtllm.sh" 2>&1 | tee -a "$CW_LOGFILE"
  cp -f "$L3"/runs/trtllm_pp256.json "$L3"/runs/trtllm_pp1024.json \
        "$L3"/runs/trtllm_rag4096.json "$L5/runs/" 2>/dev/null
  log "=== per-kernel nsys decomposition ==="
  GPU=$GPU bash "$HERE/run_nsys_gemma3_round5.sh" 2>&1 | tee -a "$CW_LOGFILE"
  log "=== report ==="
  $PY "$SUMMARIZE" R5_base R5_all 2>&1 | tee -a "$CW_LOGFILE"
fi

log "=== run_ab_gemma3_round5.sh COMPLETE ==="
nvidia-smi --query-gpu=index,clocks.current.sm,memory.used --format=csv,noheader | tee -a "$CW_LOGFILE"
