#!/usr/bin/env bash
# run_ab_gemma3_round9.sh — pinned-clocks interleaved A/B for ROUND 7 of the gemma-3-27b-it
# TensorRT-LLM 1.2.1 prefill race (H200), branch feat/gemma-margin7 off main @ afc60709 (#1006).
#
# Round 6 shipped rag4096 1.0959x / pp1024 1.1779x / pp256 1.2931x and proved the GEMM bucket is
# AT PARITY AND AT THE ROOF (292.05 vs 296.55 ms, both ~100% of the 1410 MHz-pinned dense f16
# ceiling), so this round attacks only the non-GEMM remainder. Its primary lever — v3's RT=2
# row-tiles sharing one B-fragment stream, the ONLY way to cut the shared-load stream that round
# 6 named as binding — was REFUTED BY THE REGISTER FILE before a single timing was taken: 36 v3
# instantiations peak at 255/255 registers with 24 spilling 424-488 B, against v2's 165-172 and
# zero spill. So the arms here are the compensation levers, and the baseline is round 6's
# published ship candidate rebuilt from this branch — the bracketing arm every delta rides on.
#
#   R9_base    #1006's ship set: TC_SHIM + G3_STREAM + G3_GEGLU_U4 + G3_ATTN_FLASH + G3_PF_TCATTN
#              + FA + F16ATTN + F16NORM + F16MLP + ROPE2 + FA2 + KV16 + BN32  (= R6_kv16_bn32,
#              the binary that produced 389.033 / 94.022 ms)
#   R9_gqa2    R9_base + the GQA-PACKED v3 attention dispatch (rt=2 row-tiles per warp over the two
#              query heads of one kv head, so grid.y halves and each K/V ldmatrix feeds two mma).
#              BIT-IDENTICAL to v2 — 216/216 BITIDENT-v2, 0 BITDIFF, 0 FAIL at BN=32 and BN=64 —
#              and shape-gated to n_keys >= 2048, so pp256/pp1024 keep v2 bit for bit.
#   R9_both    R9_gqa2 + ROPEVEC, the half-warp-per-head RoPE with 16-byte `_ld4`/`_st4` quads
#              replacing ROPE2's four strided scalar accesses per lane per array (~24 memory
#              instructions per head -> ~8), 16 heads per block instead of 8. NOT bit-identical:
#              contiguous quads re-associate the qk_norm sum-of-squares, so this arm rides the
#              fp32-oracle token gates rather than a bit-identity argument.
#
# ⚠️ BOTH LEVERS ARE DEFAULT-ON AS OF ROUND 13, WHICH INVERTS HOW THESE ARMS ARE BUILT. The
#    shipped default is now exactly `R9_both`, the arm round 13 measured (rag4096 385.458 ms,
#    1.1140x same-session). So an arm is defined by what it OPTS OUT OF, not by what it opts into,
#    and passing the old `-D ALGENTA_G3_PF_ROPEVEC` / `-D ALGENTA_G3_PF_GQA2` is a NO-OP that
#    silently does nothing. The four reachable configurations:
#
#      config                       flags to pass                          isolates
#      ---------------------------  -------------------------------------  ----------------------
#      R9_both   GQA2 + ROPEVEC     (none — this is the default)           the shipped default
#      R9_gqa2   GQA2 only          -D ALGENTA_G3_PF_NO_ROPEVEC            ROPEVEC (vs R9_both)
#      R9_ropev  ROPEVEC only       -D ALGENTA_G3_PF_NO_GQA2               GQA2 (vs R9_both)
#      R9_base   neither            both opt-outs                          the pre-round-9 ship
#
#    R9_base/R9_gqa2/R9_both are always built. R9_ropev is built only when BUILD_ROPEV_ARM=1, so
#    the default build stays at three arms and costs no extra VM minutes; set it when a bracket
#    needs to attribute GQA2's delta against a ROPEVEC-only arm rather than against the ship.
#    NOTE for the next window: a post-flip rebuild gives NEW sha256 hashes for every arm, because
#    the comptime defaults changed. chain13.sh's pinned hashes (R9_gqa2 3db7f0dfaf04a7c1, R9_both
#    ca66b41a2ee34cde) describe the ROUND-9 BUILT binaries and remain correct for reproducing
#    round 13 — they must be re-pinned, not inherited, before any fresh build is timed.
#
# PROTOCOL (the owner's, unchanged): oracle gate BEFORE any speed claim on every changed arm
# (G0 16/16 + G1 64/64 greedy vs the cache-free fp32 transformers oracle, the 64-token run
# repeated for determinism, val550, rag4096 with the EOS-stop rule); clocks pinned 1410 MHz read
# before AND after every cell with a 1 Hz sampler for the duration and ZERO off-pin tolerance
# (an off-pin cell is re-taken, and reported by name); 3 warmup + 7 measured, arms interleaved
# run-by-run with ARM_A re-run at the end of each prompt group so the group is A..B..A and the
# bracketing drift is MEASURED (a delta that does not exceed its armor is NOT RESOLVED, not a
# win); every cell under cell_watchdog.sh; TRT-LLM re-served FRESH in the same session and
# reproducing 40.728 / 110.744 / 426.339 within 1% or the ratio is labelled CROSS-SESSION;
# flag audit over the built binaries.
#
# The CELL RUNNER is round 6's run_gemma3_round6_cells.sh, deliberately NOT forked: its own
# header says the protocol lives in exactly one place, and it is generic over ARM_*/BIN_DIR/
# MEAS/CELLTAG/PROMPTS. Round 7 cells therefore carry r6*/r6b* labels inside ~/lever7 — the
# prefix is a label, not a round number, and the summariser is pointed at the round-7 dir.
#
# Usage (on trtllm-gemma-us-west1-c):
#   bash run_ab_gemma3_round9.sh                     # build, gate, sweep, re-serve
#   STAGE=build bash run_ab_gemma3_round9.sh
#   STAGE=gate ARM=R9_gqa2 bash run_ab_gemma3_round9.sh
#   STAGE=timing ARM_A=R9_base ARM_B=R9_gqa2 bash run_ab_gemma3_round9.sh
#   BUILD_ARMS=0 STAGE=timing bash run_ab_gemma3_round9.sh
set -uo pipefail

SM=${SM:-sm_90}
GPU=${GPU:-1}
SRC_TREE=${SRC_TREE:-$HOME/g3r7}          # the synced worktree the arms are built from
DRIVER=${DRIVER:-$HOME/adj/build/driver_ctx8192.mojo}   # STOCK, unmodified
CKPT=${CKPT:-/mnt/ramblob/g3conv27b}
L7=${L7:-$HOME/lever7}
L3=${L3:-$HOME/lever3}                    # cell_watchdog.sh + gate_any.py live here
CUDA_HOME=${CUDA_HOME:-/usr/local/cuda}
ENV_DIR=${ENV_DIR:-$HOME/algenta/mojo_env/.pixi/envs/default}
MOJO=${MOJO:-$ENV_DIR/bin/mojo}
export MODULAR_HOME=${MODULAR_HOME:-$ENV_DIR/share/max}
export CUDA_VISIBLE_DEVICES=$GPU
TC_OBJ=${TC_OBJ:-/tmp/g3r7tc/tc_shim.o}
STAGE=${STAGE:-all}
ARM=${ARM:-R9_gqa2}
ARM_A=${ARM_A:-R9_base}
ARM_B=${ARM_B:-R9_gqa2}
ARM_C=${ARM_C-}                  # third interleaved arm; an explicitly EMPTY env stays empty
                                 # (:- would resurrect a default on the chains' ARM_C=)
BUILD_ARMS=${BUILD_ARMS:-1}
# 1 also builds R9_ropev (ROPEVEC only, GQA2 opted out) — see the header table for when a bracket
# needs it. Default 0 so the ordinary build stays at three arms and costs no extra VM minutes.
BUILD_ROPEV_ARM=${BUILD_ROPEV_ARM:-0}
PY=/usr/bin/python3

BASE="-D ALGENTA_GPU -D ALGENTA_CUDA -D ALGENTA_STAGE_6144 -D ALGENTA_G3_GEGLU_U4 \
-D ALGENTA_TC_SHIM -D ALGENTA_G3_ATTN_FLASH -D ALGENTA_G3_PF_TCATTN -D ALGENTA_G3_STREAM"
# #998's five-lever round-5 stack, which #1006 shipped on top of
R5_STACK="-D ALGENTA_G3_PF_FA -D ALGENTA_G3_PF_F16ATTN -D ALGENTA_G3_PF_F16NORM \
-D ALGENTA_G3_PF_F16MLP -D ALGENTA_G3_PF_ROPE2"
# #1006's three round-6 levers — together with R5_STACK this IS the published ship candidate
R6_STACK="$R5_STACK -D ALGENTA_G3_PF_FA2 -D ALGENTA_G3_PF_KV16 -D ALGENTA_G3_PF_BN32"

mkdir -p "$L7/runs" "$L7/logs" "$L7/clocks" "$(dirname "$TC_OBJ")"
CW_LOGFILE=$L7/lever7.log
export CW_LOGFILE
# shellcheck disable=SC1091
source "$L3/cell_watchdog.sh"
cw_init "$L7/runs" "$L7/logs" "$L7/clocks" "$GPU"

ts() { date -u +%FT%TZ; }
log() { echo "[$(ts)] $*" | tee -a "$CW_LOGFILE"; }

build_shim() {
  log "=== tc_shim.o from $SRC_TREE (nvcc -arch=$SM -Xptxas -v) ==="
  # build_shim_gemma3_round7.sh generates (the shim build is round-agnostic: it only regenerates the embedded-PTX header FIRST (tc_shim.cu #includes
  # tc_rt_ptx.h; a bare nvcc on a fresh box dies on it — the trap that killed chain5c, chain5d
  # and round 6's re-stage) and additionally emits the register/spill census, because round 7's
  # primary lever was refuted by exactly that census.
  PTXD="$(dirname "$TC_OBJ")" SM="$SM" CUDA_HOME="$CUDA_HOME" \
    NR="$SRC_TREE/benchmarks/llm_smoke/nvidia_race" REGLOG="$L7/logs/ptxas_v.log" \
    bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/build_shim_gemma3_round7.sh" \
    > "$L7/logs/nvcc.log" 2>&1
  local rc=$?
  log "nvcc rc=$rc bytes=$(stat -c %s "$TC_OBJ" 2>/dev/null)"
  (( rc != 0 )) && { tail -40 "$L7/logs/nvcc.log" | tee -a "$CW_LOGFILE"; return 1; }
  # the v3 register census is recorded in the ledger either way: it is the evidence that the
  # RT=2 lever is register-refuted, not merely untried.
  grep -E "peak registers|VERDICT|instantiations," "$L7/logs/nvcc.log" | tee -a "$CW_LOGFILE"
  return 0
}

build_arm() { # $1 = name ; rest = extra flags
  local name=$1; shift
  local extra="$*"
  log "=== build $name : extra=[$extra] ==="
  ( cd "$SRC_TREE" && $MOJO build $BASE $extra \
      --target-accelerator "$SM" -I mojo/engine -I attention_forge \
      "$DRIVER" -o "$L7/$name" \
      -Xlinker "$TC_OBJ" -Xlinker -lcublas -Xlinker -lcudart \
      -Xlinker -L"$CUDA_HOME/lib64" ) > "$L7/logs/build_$name.log" 2>&1
  local rc=$?
  log "build $name rc=$rc bytes=$(stat -c %s "$L7/$name" 2>/dev/null)"
  if (( rc != 0 )) || [[ ! -x "$L7/$name" ]]; then
    tail -40 "$L7/logs/build_$name.log" | tee -a "$CW_LOGFILE"; return 1
  fi
  return 0
}

if (( BUILD_ARMS == 1 )) && [[ "$STAGE" == "all" || "$STAGE" == "build" ]]; then
  build_shim || exit 1
  # BOTH LEVERS ARE DEFAULT-ON AS OF ROUND 13, so every arm here is defined by what it OPTS OUT OF
  # and the old opt-IN flags (-D ALGENTA_G3_PF_ROPEVEC / -D ALGENTA_G3_PF_GQA2) are now NO-OPS. See
  # the header table for all four reachable configurations. Without the opt-outs a rebuild would
  # hand every arm both levers: the bracket's A arm would silently carry the levers it exists to
  # isolate, the delta would collapse toward zero, and no arm would reproduce the hashes chain13.sh
  # treats as FATAL to mismatch (R9_gqa2 3db7f0dfaf04a7c1). A null bracket that looks like a real
  # one is the failure mode this prevents.
  # R9_base is #1006's ship candidate rebuilt from THIS branch, so the bracket measures against
  # the exact flag set that produced 389.033 / 94.022 / 32.108 ms rather than against a rebuild
  # of some other configuration.
  build_arm R9_base $R6_STACK -D ALGENTA_G3_PF_NO_ROPEVEC -D ALGENTA_G3_PF_NO_GQA2 || exit 1
  # R9_gqa2 = GQA2 only. GQA2 is default-ON and bit-identical to v2, shape-gated to n_keys >= 2048
  # so pp256/pp1024 keep v2 bit for bit and cannot regress; the vector rope is opted OUT so that
  # R9_gqa2 -> R9_both isolates ROPEVEC's own delta, which is what round 13 measured at -1.687 ms.
  build_arm R9_gqa2 $R6_STACK -D ALGENTA_G3_PF_NO_ROPEVEC || exit 1
  # R9_both = the SHIPPED DEFAULT, so it passes no lever flag at all. The absence of both opt-outs
  # IS the configuration; the runtime TCFLAG banners plus the flag audit are what prove it engaged.
  build_arm R9_both $R6_STACK || exit 1
  # R9_ropev (opt-in via BUILD_ROPEV_ARM=1) = ROPEVEC only, GQA2 opted out. Lets a bracket
  # attribute GQA2's delta against a ROPEVEC-only arm rather than against the pre-round-9 ship.
  if (( BUILD_ROPEV_ARM == 1 )); then
    build_arm R9_ropev $R6_STACK -D ALGENTA_G3_PF_NO_GQA2 || exit 1
  else
    log "BUILD_ROPEV_ARM=0 — skipping R9_ropev (ROPEVEC-only arm); set BUILD_ROPEV_ARM=1 to build it"
  fi
  log "=== flag audit over the built arms (scripts/audit_tc_flags.sh) ==="
  bash "$SRC_TREE/scripts/audit_tc_flags.sh" --bin-dir "$L7" --glob 'R9_*' \
       --logs "$L7/runs" --out "$L7/flag_audit.json" 2>&1 | tee -a "$CW_LOGFILE"
fi
[[ "$STAGE" == "build" ]] && { log "STAGE=build complete"; exit 0; }

# everything below needs the GPU. The cells (watchdog, clock pinning, 1 Hz sampler, the
# interleaved bracket) live in round 6's runner, reused unmodified — see the header for why.
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
CELLS_SH=${CELLS_SH:-$HERE/run_gemma3_round6_cells.sh}
export BIN_DIR="$L7" MEAS="$L7" CW_LOGFILE

if [[ "$STAGE" == "all" || "$STAGE" == "smoke" ]]; then
  log "=== smoke: does ROPEVEC ARM, and what is the first delta? ==="
  STAGE=smoke ARM_A="$ARM_A" ARM_B="$ARM_B" ARM_C="$ARM_C" bash "$CELLS_SH" || exit 1
  # The banner is the proof the lever is live: ROPEVEC prints its own TCFLAG line, and a
  # runtime decline would leave the ROPE2 kernel in place while the binary still carries the
  # flag — a declined lever must never masquerade as an armed one.
  for a in "$ARM_B" "$ARM_A"; do
    grep -m1 "TCFLAG ALGENTA_G3_PF_ROPEVEC" "$L7/runs/smoke_${a}_pp1024.out" \
      || echo "NOTE: no ROPEVEC banner in smoke_${a} (expected for R9_base)"
  done
fi
[[ "$STAGE" == "smoke" ]] && exit 0

if [[ "$STAGE" == "all" || "$STAGE" == "gate" ]]; then
  log "=== oracle gate on $ARM (the changed arm) ==="
  STAGE=gate ARM="$ARM" bash "$CELLS_SH" || {
    log "GATE FAILED for $ARM -- no timing cells, no ratios, nothing publishable"; exit 1; }
  log "=== oracle gate on $ARM_A (the baseline, re-earned on this checkpoint) ==="
  STAGE=gate ARM="$ARM_A" bash "$CELLS_SH" || {
    log "GATE FAILED for $ARM_A"; exit 1; }
fi
[[ "$STAGE" == "gate" ]] && exit 0

if [[ "$STAGE" == "all" || "$STAGE" == "timing" ]]; then
  log "=== interleaved bracketed A/B: $ARM_A vs $ARM_B ==="
  STAGE=timing ARM_A="$ARM_A" ARM_B="$ARM_B" ARM_C="$ARM_C" bash "$CELLS_SH" || exit 1
fi
[[ "$STAGE" == "timing" ]] && exit 0

if [[ "$STAGE" == "all" ]]; then
  log "=== same-session TRT-LLM 1.2.1 re-serve (must reproduce 40.728/110.744/426.339 +-1%) ==="
  GPU=$GPU bash "$L3/lv3_trtllm.sh" 2>&1 | tee -a "$CW_LOGFILE"
  cp -f "$L3"/runs/trtllm_pp256.json "$L3"/runs/trtllm_pp1024.json \
        "$L3"/runs/trtllm_rag4096.json "$L7/runs/" 2>/dev/null
  log "=== per-kernel nsys decomposition with the FIXED extractor ==="
  GPU=$GPU bash "$HERE/run_nsys_gemma3_round9.sh" 2>&1 | tee -a "$CW_LOGFILE" \
    || log "NSYS_WARN: decomposition incomplete; the ledger must say so rather than reuse " \
           "round 6's geometry-attributed rows"
fi

log "=== run_ab_gemma3_round9.sh COMPLETE ==="
nvidia-smi --query-gpu=index,clocks.current.sm,memory.used --format=csv,noheader | tee -a "$CW_LOGFILE"
