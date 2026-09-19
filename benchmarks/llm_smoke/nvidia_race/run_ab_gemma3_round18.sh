#!/usr/bin/env bash
# run_ab_gemma3_round18.sh — RUN THIS ON THE VM. Round 18: the VECTORISED f16 prefill GeGLU twin,
# gated and bracketed. Extends run_ab_gemma3_round17.sh (same stages, same cells runner, same
# armor protocol); it is NOT a rewrite — the protocol lives in run_gemma3_round6_cells.sh and is
# reused unmodified apart from the new GATE_SPECS knob this round needed.
#
# ── WHAT IS BEING MEASURED, AND WHY THIS LEVER ────────────────────────────────────────────────
# Round 15's identity-based census re-ranked the levers by MEASURED pool; round 17 priced the top
# of the new ranking and closed the old one. `_pf_geglu_rows_f16_kernel` — the f16 MLP combine,
# hash 8f4c4e1d2ba54545 — is **45.687 ms over the `--from-first-attn` region at rag4096, 434
# instances, 8.22% of busy**: a LARGER pool than the whole fused-attention bucket (38.114 ms) that
# no round had examined before round 15. Its traffic is 6 bytes per output element (f16 gate +
# f16 up + f16 activation write) with no re-reads, so 365056 rows x 21504 elements is 47.101 GB
# whose roof at the campaign's own 4.8 TB/s constant is **9.813 ms**. It measures **4.656x that
# roof** — 1.031 TB/s, 21.5% of achievable bandwidth. It is not compute: the elementwise math is
# 0.156% of measured and even every one of the 7.850 G `tanh` at the SFU rate is 5.8%.
#
# The cause is visible in the source and was confirmed from PTX on CPU before any VM minute: the
# kernel is one thread per element with **three 2-byte global accesses each**. Round 17's local
# PTX extraction of the shipped arm shows exactly `2 x ld.global.b16 + 1 x st.global.b16`.
# `-D ALGENTA_G3_GEGLU_U4` is already in the shipped flag stack but vectorises the DECODE GEMV
# (`_g3_norm_gemv2_geglu_kernel_f16_u4`); the prefill f16 GeGLU had no vectorised twin at all.
#
# THE LEVER. `_pf_geglu_rows_f16_vec_kernel` (authored in round 18 behind an opt-IN
# `-D ALGENTA_G3_PF_GEGLU_V2`, and **DEFAULT ON since round 19** with the opt-out
# `-D ALGENTA_G3_PF_NO_GEGLUV2`) gives one
# thread EIGHT CONTIGUOUS f16 = 16 bytes per operand, through new `_ld8h`/`_st8h` helpers that
# carry the `alignment=16` annotation `residentk.loadvec` exists to supply. Local PTX of the lever
# arm shows `2 x ld.global.v4.b32 + 1 x st.global.v4.b32` — **3 memory instructions per 8 elements
# instead of 24**. The precedent is in-lane and measured: ROPEVEC made exactly this change to the
# RoPE family and delivered -1.687 ms on rag4096 at 14.5x its drift armor, against a pool 6.8x
# smaller and 4.4x closer to its roof.
#
# ── THE TWO ARMS, AND WHY THEY DIFFER IN EXACTLY ONE RESPECT ──────────────────────────────────
# ROUND 19 UPDATED THIS SECTION, because round 19 flips GEGLU_V2 DEFAULT-ON and an arm is now
# defined by what it OPTS OUT OF. The flag stacks are the `ARM_A_EXTRA` / `ARM_B_EXTRA` knobs below;
# the names round 18 used are kept as the defaults' meaning, not as the defaults' spelling.
#   ARM_A (round 18: R18_ctl)   R6_STACK + `-D ALGENTA_G3_PF_NO_GEGLUV2` = the PRE-round-19 shipped
#              default, i.e. the R9_both configuration default-ON since #1042 with the SCALAR f16
#              GeGLU twin. **This lever needs NO shim change** — it is pure Mojo — so both arms link
#              the SAME stock shim object, which removes round 17's two-shim complexity entirely and
#              makes the arms differ by one comptime boolean and nothing else.
#   ARM_B (round 18: R18_gegluv) R6_STACK with NO opt-out = the POST-round-19 shipped default, which
#              now carries the vector twin by default. Round 18 spelled this `+ -D
#              ALGENTA_G3_PF_GEGLU_V2`; post-flip that opt-in is an exact NO-OP, proven by
#              BYTE-IDENTITY of the compiled object on CPU rather than by inspection (see
#              `flip_validate.sh`'s record in the round-19 ledger: `default == legacy_optin`,
#              981024 bytes, sha256_16 570515ac338b5cdf).
#
# ── BIT-IDENTITY IS THE CLAIM, AND IT IS CHECKED THREE WAYS ──────────────────────────────────
# GeGLU is purely ELEMENTWISE: no reduction, no accumulation, no cross-element movement, so there
# is no association order to change. `_g3_geglu_f16_elem` is the scalar twin's body transposed
# verbatim. Evidence, in increasing order of cost:
#   1. PTX-BODY DIFFERENTIAL (CPU, already done): the lever's per-element instruction sequence is
#      the scalar twin's, 8x, with the same four f32 immediates at 8x the count. The ONE
#      difference is the output narrowing — 8 x `cvt.rn.f16.f32` becomes 4 x `cvt.rn.f16x2.f32`.
#      Same `.rn` (round-to-nearest-even) mode, two independent conversions per instruction.
#   2. LANE ORDER (CPU, already done, and it was worth checking): `cvt.rn.f16x2.f32 d, X, Y` puts
#      **Y in the LOW 16 bits and X in the HIGH**, proved from the authoritative CUDA header
#      `cuda_fp16.hpp:__internal_device_float2_to_half2_rn`, whose SM80+ path emits
#      `cvt.rn.f16x2.f32 %0, %2, %1` with %1=a %2=b and whose pre-SM80 fallback shows a->low,
#      b->high explicitly. LLVM emits `cvt.rn.f16x2.f32 %r105, <elem1>, <elem0>` and stores %r105
#      at the lowest address, so elem0 lands at act16[g8+0]. CORRECT. (A doc summary that claimed
#      a->low was checked and REJECTED against the header — acting on it would have "fixed" a
#      correct kernel into a lane-swapped one.)
#   3. THE GATE + THE BRACKET'S OWN TOKENS (VM, this script): the full fp32-oracle gate on the
#      lever arm, then `STAGE=bitident`, which compares the GENERATED TOKEN STREAMS of the two
#      arms cell-for-cell. Because the bracket's rag4096 cells run --max-new 256, that comparison
#      is 256 tokens x n samples x both arms, for free, from cells the bracket already runs. The
#      expected result is 100% BITIDENT — not merely "both agree with the oracle".
# Contrast ROPEVEC (re-associates the qk_norm reduction) and LTALGO (a tuned algorithm may split K),
# neither of which could claim bit-identity. This lever can, and is held to it.
#
# ── PROTOCOL (the owner's, unchanged) ─────────────────────────────────────────────────────────
# Oracle gate BEFORE any timing cell, on the changed arm: G0 16/16 + G1 64/64 greedy against the
# cache-free fp32 transformers oracle, plus the gate's own `rep2` bit-identical repeat. Then an
# interleaved A..B..A bracket whose drift armor is MEASURED from the closing cells — a delta that
# does not exceed its armor is NOT RESOLVED, not a win. Median basis, 1410 MHz, offpin=0.
#
# ── THE BUDGET, STATED UP FRONT BECAUSE IT DECIDES WHAT THIS ROUND CAN DELIVER ────────────────
# Measured cell costs on this box: ~110-117 s at pp1024, ~134.6 s at rag4096 (dominated by the
# driver loading the 101 GB checkpoint per fresh process). A cap of 90 min VM-on (+5 grace) buys:
#   boot+ssh ~4 | chain7stage ~14 | build+verify ~6 | gate ~10 | = ~34 min of overhead
#   rag4096 bracket, 3 warm + 5 meas + 2 close x 2 arms = 18 cells = ~41 min  -> cumulative ~75
#   pp1024  bracket, same shape                                            = ~35 min  -> ~110
# **Both n=5 brackets do not fit in one window. That is arithmetic, not a preference.** So this
# script brackets rag4096 FIRST — it is the cell whose region the 45.687 ms census was taken over,
# the cell the 12.07 ms bar is defined on, and the cell every published comparator (round 13's
# same-session TRT-LLM 429.400 ms) lives in — and then spends whatever genuinely remains on
# pp1024, deciding from the CLOCK rather than from hope. Set CW_DEADLINE_EPOCH and the governor
# runs; unset and MEAS_RUNS/PROMPTS are used as given.
#
# ── STAGES ────────────────────────────────────────────────────────────────────────────────────
#   STAGE=build     the stock shim + both arms. No GPU work.
#   STAGE=verify    the binary audit, incl. the SELF-COMPUTING kernel-hash differential.
#   STAGE=smoke     one pp1024 cell per arm; proves `gegluv_armed = true` and the control's absence.
#   STAGE=gate      the fp32-oracle gate on R18_gegluv (GATE_SPECS-restricted; see below).
#   STAGE=timing    the interleaved bracket, budget-governed.
#   STAGE=bitident  compare the two arms' generated token streams from cells already on disk.
#   STAGE=all       build -> verify -> smoke -> gate -> timing -> bitident.
#
#   STAGE=build bash run_ab_gemma3_round18.sh
#   STAGE=gate  GATE_SPECS="pp1024:/tmp/g3pp1024/prompt_0000.txt rag4096:/tmp/g3rag/rag4096.txt" \
#               bash run_ab_gemma3_round18.sh
#   STAGE=timing CW_DEADLINE_EPOCH=$(date -d "$DEADLINE" +%s) bash run_ab_gemma3_round18.sh
set -uo pipefail

SM=${SM:-sm_90}
GPU=${GPU:-1}
SRC_TREE=${SRC_TREE:-$HOME/g3r18}          # the tree vm_sync_r18.sh materialises
CKPT=${CKPT:-/mnt/ramblob/g3conv27b}
L18=${L18:-$HOME/lever18}
L3=${L3:-$HOME/lever3}                     # cell_watchdog.sh + gate_any.py live here
CUDA_HOME=${CUDA_HOME:-/usr/local/cuda}
ENV_DIR=${ENV_DIR:-$HOME/algenta/mojo_env/.pixi/envs/default}
MOJO=${MOJO:-$ENV_DIR/bin/mojo}
export MODULAR_HOME=${MODULAR_HOME:-$ENV_DIR/share/max}
export CUDA_VISIBLE_DEVICES=$GPU

PTXD=${PTXD:-/tmp/g3r18tc}                 # tmpfs: wiped per stop, regenerated by the shim build
TC_STOCK=$PTXD/tc_shim.o

STAGE=${STAGE:-all}
ARM=${ARM:-R18_gegluv}                     # the CHANGED arm, i.e. the one the gate must earn
ARM_A=${ARM_A:-R18_ctl}                    # bracket A = control = the shipped default
ARM_B=${ARM_B:-R18_gegluv}                 # bracket B = the lever
ARM_C=${ARM_C-}
CELLTAG=${CELLTAG:-_r18}                   # so this bracket's cells do not pool with earlier rounds'
BUILD_ARMS=${BUILD_ARMS:-1}
PY=${PY:-/usr/bin/python3}

# THE TWO KERNEL HASHES, recovered on CPU with the VM TERMINATED by building the real race driver
# off origin/main with and without `-D ALGENTA_G3_PF_GEGLU_V2` and diffing the 16-hex kernel
# symbols. The differential was EXACTLY +1 symbol and -0, i.e. the flag adds one kernel and removes
# none (the scalar twin stays referenced because the dispatch keeps it as the shape-gate fallback).
# A Mojo kernel's hash is NAME-derived, so this is a prediction the VM build can be checked against
# — and if the VM's toolchain disagrees the verify stage says INCONCLUSIVE rather than pretending.
HASH_SCALAR_F16_GEGLU=${HASH_SCALAR_F16_GEGLU:-8f4c4e1d2ba54545}   # _pf_geglu_rows_f16_kernel
HASH_VEC_GEGLU=${HASH_VEC_GEGLU:-b0496694ffefbc3c}                 # _pf_geglu_rows_f16_vec_kernel

# ── THE ARM FLAG STACKS ARE KNOBS, AND ROUND 19'S FLIP IS WHY ─────────────────────────────────
# Round 18 built ARM_A with NO lever flag (it was the shipped default) and ARM_B with
# `-D ALGENTA_G3_PF_GEGLU_V2`. Round 19 flips that flag DEFAULT-ON with the opt-out
# `-D ALGENTA_G3_PF_NO_GEGLUV2`, so those two build lines would have produced TWO IDENTICAL ARMS:
# ARM_A would silently carry the lever it exists to be the control for, ARM_B's opt-in would be an
# exact no-op, and `verify_arms` would have FATAL'd on a 0-added/0-removed kernel differential —
# after a build, a stage and a clock pin had already been paid for. This is #1042's consequence #1
# arriving for the third time (it fixed the round-9 and round-7 runners the same way), and the fix
# is the same shape: **an arm is now defined by what it OPTS OUT OF, and the absence of the opt-out
# IS the lever.** Both stacks are env-overridable so a later round can re-target this runner
# instead of copying it, with the defaults set to the post-flip mapping that reproduces round 18's
# bracket exactly.
ARM_A_EXTRA=${ARM_A_EXTRA:--D ALGENTA_G3_PF_NO_GEGLUV2}   # control = the PRE-round-19 shipped default
ARM_B_EXTRA=${ARM_B_EXTRA:-}                              # lever   = the POST-round-19 shipped default

# The STOCK driver, outside the synced tree, exactly as rounds 7/9/17 used it — the driver is the
# harness, not the thing under test, and building from an unmodified driver is what keeps the arms'
# hashes comparable with the certified R9_both family.
DRIVER=${DRIVER:-$HOME/adj/build/driver_ctx8192.mojo}
if [[ ! -f "$DRIVER" ]]; then
  DRIVER=$SRC_TREE/benchmarks/llm_smoke/nvidia_race/vm_harness/adj/build/driver_ctx8192.mojo
  echo "NOTE: ~/adj/build/driver_ctx8192.mojo absent; using the in-tree copy at $DRIVER"
fi

BASE="-D ALGENTA_GPU -D ALGENTA_CUDA -D ALGENTA_STAGE_6144 -D ALGENTA_G3_GEGLU_U4 \
-D ALGENTA_TC_SHIM -D ALGENTA_G3_ATTN_FLASH -D ALGENTA_G3_PF_TCATTN -D ALGENTA_G3_STREAM"
R5_STACK="-D ALGENTA_G3_PF_FA -D ALGENTA_G3_PF_F16ATTN -D ALGENTA_G3_PF_F16NORM \
-D ALGENTA_G3_PF_F16MLP -D ALGENTA_G3_PF_ROPE2"
R6_STACK="$R5_STACK -D ALGENTA_G3_PF_FA2 -D ALGENTA_G3_PF_KV16 -D ALGENTA_G3_PF_BN32"

# Round 18 brackets rag4096 first and pp1024 second, and the budget governor may cut the second.
# pp256 is NOT in the set: at m=256 the prefill runs one short tile, and while the GeGLU twin does
# engage there, the region census that priced this lever was taken at rag4096, so that is where the
# predicted effect size lives. PROMPTS_ORDER is what the governor walks, in priority order.
PROMPT_RAG="rag4096:/tmp/g3rag/rag4096.txt:256"
PROMPT_PP1024="pp1024:/tmp/g3pp1024/prompt_0000.txt:1"
PROMPTS_ORDER=${PROMPTS_ORDER:-"$PROMPT_RAG $PROMPT_PP1024"}
# GATE_SPECS defaults to the TWO BRACKETED SHAPES: G0 16/16 comes from pp1024, G1 64/64 and the
# rep2 bit-identical repeat come from both. A full four-prompt gate is ~38 min and does not fit
# alongside a bracket in a 90-min cap; the reduction is logged by the cells runner as NON-DEFAULT.
GATE_SPECS=${GATE_SPECS:-"pp1024:/tmp/g3pp1024/prompt_0000.txt rag4096:/tmp/g3rag/rag4096.txt"}
export GATE_SPECS

# Per-cell seconds, for the governor only. Round 17 measured 134.6 s at rag4096; round 15's
# ledger records ~110-117 s for the shorter prompts. Over-estimates are deliberate: a governor
# that under-estimates spends the window, one that over-estimates only declines to.
CELL_S_RAG=${CELL_S_RAG:-140}
CELL_S_PP1024=${CELL_S_PP1024:-120}
SAFETY_S=${SAFETY_S:-240}                  # stop-issuing margin, on top of the 5-min grace

mkdir -p "$L18/runs" "$L18/logs" "$L18/clocks" "$PTXD"
CW_LOGFILE=${CW_LOGFILE:-$L18/round18.log}
export CW_LOGFILE

ts() { date -u +%FT%TZ; }
log() { echo "[$(ts)] $*" | tee -a "$CW_LOGFILE"; }

# ── THE BUDGET GOVERNOR ───────────────────────────────────────────────────────────────────────
# Round 17 ran to 93 min 58 s against a 90-min cap and issued its stop 69 s after the bracket
# finished. That worked, but it worked because the bracket happened to end when it did. A window
# that has to CHOOSE between two brackets needs the choice made from the clock, mid-run, not from
# an estimate written before the box was started. CW_DEADLINE_EPOCH is the hard stop-by instant;
# `mins_left` is the only thing any stage below is allowed to plan against.
mins_left() {
  if [[ -z "${CW_DEADLINE_EPOCH:-}" ]]; then echo 999; return; fi
  local now left
  now=$(date +%s)
  left=$(( (CW_DEADLINE_EPOCH - SAFETY_S - now) / 60 ))
  (( left < 0 )) && left=0
  echo "$left"
}
need_mins() { # $1 = minutes ; returns 0 if the window can still afford it
  local have; have=$(mins_left)
  (( have >= $1 ))
}
cells_cost_min() { # $1 = prompt name ; $2 = cell count
  local s=$CELL_S_PP1024
  [[ "$1" == rag4096 ]] && s=$CELL_S_RAG
  echo $(( ($2 * s + 59) / 60 ))
}

build_shim() { # $1 = label ; $2 = object path ; $3 = extra macros (may be empty)
  log "=== shim $1 -> $2  extra=[$3] ==="
  PTXD="$PTXD" SM="$SM" CUDA_HOME="$CUDA_HOME" \
    NR="$SRC_TREE/benchmarks/llm_smoke/nvidia_race" \
    REGLOG="$L18/logs/ptxas_v_$1.log" \
    EXTRA_MACROS="$3" OBJNAME="$(basename "$2")" \
    bash "$SRC_TREE/benchmarks/llm_smoke/nvidia_race/build_shim_gemma3_round7.sh" \
    > "$L18/logs/nvcc_$1.log" 2>&1
  local rc=$?
  log "nvcc $1 rc=$rc bytes=$(stat -c %s "$2" 2>/dev/null)"
  grep -E "SHIM_FLAVOUR|RC_SHIM" "$L18/logs/nvcc_$1.log" | tee -a "$CW_LOGFILE"
  if (( rc != 0 )); then tail -40 "$L18/logs/nvcc_$1.log" | tee -a "$CW_LOGFILE"; return 1; fi
  grep -E "peak registers|instantiations," "$L18/logs/nvcc_$1.log" | tail -3 | tee -a "$CW_LOGFILE"
  return 0
}

build_arm() { # $1 = name ; rest = extra mojo flags
  local name=$1; shift
  local extra="$*"
  log "=== build $name : shim=$(basename "$TC_STOCK") extra=[$extra] ==="
  ( cd "$SRC_TREE" && $MOJO build $BASE $extra \
      --target-accelerator "$SM" -I mojo/engine -I attention_forge \
      "$DRIVER" -o "$L18/$name" \
      -Xlinker "$TC_STOCK" -Xlinker -lcublas -Xlinker -lcudart \
      -Xlinker -L"$CUDA_HOME/lib64" ) > "$L18/logs/build_$name.log" 2>&1
  local rc=$?
  log "build $name rc=$rc bytes=$(stat -c %s "$L18/$name" 2>/dev/null)"
  if (( rc != 0 )) || [[ ! -x "$L18/$name" ]]; then
    tail -40 "$L18/logs/build_$name.log" | tee -a "$CW_LOGFILE"; return 1
  fi
  return 0
}

kernel_hashes() { # $1 = binary ; prints the sorted set of PTX KERNEL-ENTRY hashes, one per line
  # ENTRY-BACKED ONLY, AND THAT IS A FIX PAID FOR IN VM MINUTES. The first cut of this function
  # took every `[A-Za-z_][A-Za-z0-9_]*_[0-9a-f]{16}` token in `strings -a`, which is correct for an
  # `--emit object` build (the CPU differential found exactly 38 vs 39, +1/-0) and WRONG for a
  # LINKED EXECUTABLE: the link pulls in the shim, the runtime and embedded cubin bytes, whose
  # incidental 16-hex-suffixed tokens are not kernels. Round 18 measured this on the box — the arms
  # differed by 12 such tokens, of which ELEVEN occurred exactly once each and appeared in NO
  # `.visible .entry` context, i.e. layout noise that moves whenever the binary's contents move.
  # Counting them made the audit report "12 added kernels" where exactly ONE was added, and the
  # FATAL fired on a correct pair of arms. Anchoring on the PTX's own entry declaration fixes it
  # and works identically for an object and for a linked arm.
  strings -a "$1" \
    | grep -oE '\.visible \.entry [A-Za-z_][A-Za-z0-9_]*_[0-9a-f]{16}\(' \
    | sed -E 's/.*_([0-9a-f]{16})\($/\1/' | sort -u
}
raw_hex_tokens() { # $1 = binary ; every 16-hex-suffixed token, for the noise record only
  strings -a "$1" | grep -oE '[A-Za-z_][A-Za-z0-9_]*_[0-9a-f]{16}' \
    | sed -E 's/.*_([0-9a-f]{16})$/\1/' | sort -u
}

verify_arms() {
  # The binary-level audit. FOUR claims, all checked from the linked executables rather than from
  # the flags we intended to pass, because this campaign was burned once by a rebuild that had
  # silently dropped `-D ALGENTA_G3_STREAM` and produced a gemma-3-27b column wrong at oracle index
  # 0 on 5/6 prompts with nothing recording it.
  #   1. the control carries NO GEGLU_V2 banner literal (a build cannot print a line it lacks)
  #   2. the lever DOES carry it
  #   3. the kernel-symbol SET DIFFERENCE between the arms is exactly the vector twin — computed
  #      here, not assumed, so the audit survives a toolchain whose hashes differ from the CPU run
  #   4. that difference equals the hash the CPU differential PREDICTED (b0496694ffefbc3c), and the
  #      scalar twin's own hash (8f4c4e1d2ba54545) is still present in BOTH arms
  log "=== VERIFY: what the two linked binaries actually carry ==="
  local a b lit ha hb added removed
  for a in "$ARM_A" "$ARM_B"; do
    b="$L18/$a"
    [[ -x "$b" ]] || { log "FATAL: $b missing — run STAGE=build"; return 1; }
    log "  $a sha256_16=$(sha256sum "$b" | cut -c1-16) bytes=$(stat -c %s "$b")"
    lit=$(strings -a "$b" | grep -c "TCFLAG ALGENTA_G3_PF_GEGLU_V2=1" || true)
    log "  $a GEGLU_V2 banner literal = $lit"
    log "  $a scalar f16 GeGLU hash $HASH_SCALAR_F16_GEGLU present = $(kernel_hashes "$b" | grep -c "^$HASH_SCALAR_F16_GEGLU$" || true)"
    if [[ "$a" == "$ARM_A" ]]; then
      if (( lit != 0 )); then
        log "FATAL: the CONTROL arm $a carries the lever's banner literal. The bracket would not"
        log "       bound the lever. Refusing to continue."
        return 1
      fi
      log "  $a VERIFIED CLEAN: no GEGLU_V2 banner literal"
    else
      if (( lit == 0 )); then
        log "FATAL: the LEVER arm $a carries no GEGLU_V2 banner literal. The macro did not reach"
        log "       the compiler; a declined lever must never masquerade as a measured one."
        return 1
      fi
      log "  $a VERIFIED ARMED: banner literal present"
    fi
  done
  kernel_hashes "$L18/$ARM_A" > "$L18/logs/hashes_$ARM_A.txt"
  kernel_hashes "$L18/$ARM_B" > "$L18/logs/hashes_$ARM_B.txt"
  # the noise record, kept so the entry-backed filter's effect is auditable rather than asserted
  raw_hex_tokens "$L18/$ARM_A" > "$L18/logs/rawtokens_$ARM_A.txt"
  raw_hex_tokens "$L18/$ARM_B" > "$L18/logs/rawtokens_$ARM_B.txt"
  log "  non-kernel 16-hex tokens (layout noise, recorded not counted):" \
      "$ARM_A=$(wc -l < "$L18/logs/rawtokens_$ARM_A.txt" | tr -d ' ')" \
      "$ARM_B=$(wc -l < "$L18/logs/rawtokens_$ARM_B.txt" | tr -d ' ')" \
      "differing=$(comm -3 "$L18/logs/rawtokens_$ARM_A.txt" "$L18/logs/rawtokens_$ARM_B.txt" | wc -l | tr -d ' ')"
  added=$(comm -13 "$L18/logs/hashes_$ARM_A.txt" "$L18/logs/hashes_$ARM_B.txt")
  removed=$(comm -23 "$L18/logs/hashes_$ARM_A.txt" "$L18/logs/hashes_$ARM_B.txt")
  log "  kernel-symbol set: $ARM_A=$(wc -l < "$L18/logs/hashes_$ARM_A.txt" | tr -d ' ')" \
      "$ARM_B=$(wc -l < "$L18/logs/hashes_$ARM_B.txt" | tr -d ' ')"
  log "  ADDED by the lever   : ${added:-<none>}"
  log "  REMOVED by the lever : ${removed:-<none>}"
  local n_add n_rem
  n_add=$(echo -n "$added" | grep -c . || true)
  n_rem=$(echo -n "$removed" | grep -c . || true)
  if (( n_add != 1 || n_rem != 0 )); then
    log "FATAL: the arms differ by $n_add added / $n_rem removed kernel symbols, not the 1/0 the"
    log "       CPU differential predicted. The two arms are NOT one macro apart; any bracket"
    log "       would measure an unknown difference. Refusing to continue."
    return 1
  fi
  if [[ "$added" == "$HASH_VEC_GEGLU" ]]; then
    log "  VERIFIED: the single added kernel IS the CPU-predicted vector twin $HASH_VEC_GEGLU"
    log "            (_pf_geglu_rows_f16_vec_kernel). Hashes are path- and host-independent here,"
    log "            reproducing round 15's finding on the round-18 lever."
  else
    # NOT FATAL, and the reason matters: the hash is a NAME-derived content hash and the CPU
    # prediction came from a different host's toolchain. The set differential above is the binding
    # evidence (exactly one kernel added, none removed, and the only source difference between the
    # arms is one `-D` that adds one kernel); the hash match is a cross-check. A mismatch is
    # recorded loudly and the runtime `gegluv_armed` field plus the nsys instance counts settle it.
    log "  WARNING: the added kernel's hash is $added, NOT the CPU-predicted $HASH_VEC_GEGLU."
    log "           Recorded as INCONCLUSIVE-on-hash, not as a failure: the 1/0 set differential"
    log "           still proves the arms differ by exactly one kernel, and the only source"
    log "           difference between them is the macro that adds the vector twin. The runtime"
    log "           gegluv_armed field and the trace's per-hash instance counts are the tiebreakers."
  fi
  return 0
}

if [[ "$STAGE" == "all" || "$STAGE" == "build" ]]; then
  build_shim stock "$TC_STOCK" "" || exit 1
  if (( BUILD_ARMS == 1 )); then
    # POST-FLIP (round 19), and the reasoning inverted with it. R6_STACK with NO opt-outs is now the
    # LEVER arm, because ROPEVEC and GQA2 have been default-ON since #1042 and GEGLU_V2 since round
    # 19 — so for all three, the ABSENCE of a flag IS the configuration. The control is the arm that
    # names what it gives up: `$ARM_A_EXTRA` defaults to `-D ALGENTA_G3_PF_NO_GEGLUV2`, which
    # restores the pre-round-19 shipped default byte-for-byte. Same shim object, same libraries, so
    # the two arms differ by exactly one comptime boolean and nothing else.
    build_arm "$ARM_A" $R6_STACK $ARM_A_EXTRA || exit 1
    build_arm "$ARM_B" $R6_STACK $ARM_B_EXTRA || exit 1
  fi
  verify_arms || exit 1
  log "STAGE=build complete"
  [[ "$STAGE" == "build" ]] && exit 0
fi

if [[ "$STAGE" == "verify" ]]; then
  verify_arms; exit $?
fi

# Everything below needs the GPU. The cells (watchdog, clock pinning, 1 Hz sampler, the interleaved
# bracket, the oracle gate) live in round 6's runner, reused UNMODIFIED.
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
CELLS_SH=${CELLS_SH:-$HERE/run_gemma3_round6_cells.sh}
export BIN_DIR="$L18" MEAS="$L18" CW_LOGFILE

if [[ "$STAGE" == "all" || "$STAGE" == "smoke" ]]; then
  log "=== smoke: does the lever ARM at runtime, and is the control clean? ==="
  STAGE=smoke ARM_A="$ARM_A" ARM_B="$ARM_B" ARM_C="$ARM_C" CELLTAG="$CELLTAG" \
    PROMPTS="$PROMPT_PP1024" bash "$CELLS_SH" || exit 1
  # THE BANNER IS THE PROOF THE LEVER IS LIVE, and it has two parts. The literal proves the macro
  # reached the compiler; `gegluv_armed` proves the DISPATCH engaged. The dispatch declines to the
  # scalar twin when `d_ff % 8 != 0`, so a binary can carry the flag and still run the control
  # kernel — LTALGO's `lt_shapes_tuned = 0` hazard, same shape, checked the same way.
  for a in "$ARM_B" "$ARM_A"; do
    log "--- $a smoke banner ---"
    grep -m1 "TCFLAG ALGENTA_G3_PF_GEGLU_V2" "$L18"/runs/smoke_*"${a}"_pp1024.out 2>/dev/null \
      || echo "NOTE: no GEGLU_V2 banner for $a (EXPECTED for $ARM_A, FATAL for $ARM_B)"
    grep -m1 "^G3 FLAGS:" "$L18"/runs/smoke_*"${a}"_pp1024.out 2>/dev/null | tee -a "$CW_LOGFILE"
  done
  if ! grep -q "gegluv_armed = true" "$L18"/runs/smoke_*"${ARM_B}"_pp1024.out 2>/dev/null; then
    log "FATAL: $ARM_B did not report gegluv_armed = true. The shape gate declined and the arm"
    log "       would run the SCALAR twin — any bracket would be a null wearing the lever's name."
    log "       Refusing to spend gate or timing minutes on it."
    exit 1
  fi
  if grep -q "gegluv_armed = false" "$L18"/runs/smoke_*"${ARM_B}"_pp1024.out 2>/dev/null; then
    log "FATAL: gegluv_armed = false — d_ff is not a multiple of 8 on this model. ABORT."; exit 1
  fi
  log "smoke: $ARM_B armed at runtime — the lever is LIVE"
fi

if [[ "$STAGE" == "all" || "$STAGE" == "gate" ]]; then
  log "=== oracle gate on $ARM (the CHANGED arm) — must pass before any speed claim ==="
  log "    GATE_SPECS=[$GATE_SPECS]"
  STAGE=gate ARM="$ARM" bash "$CELLS_SH" || {
    log "GATE FAILED on $ARM: no timing cells may be taken or published for this arm"; exit 1; }
  log "GATE PASSED on $ARM — timing may proceed"
  [[ "$STAGE" == "gate" ]] && exit 0
fi

if [[ "$STAGE" == "all" || "$STAGE" == "timing" ]]; then
  # ── THE GOVERNOR DECIDES, FROM THE CLOCK ────────────────────────────────────────────────────
  # Walk PROMPTS_ORDER in priority order. For each prompt, price a bracket at the protocol's n=7,
  # then n=5, then decline. Nothing is started that cannot FINISH inside the deadline minus the
  # stop-issuing safety margin, so the window never has to abandon a half-run bracket — the one
  # outcome that would make the round unpublishable.
  log "=== timing: budget governor ==="
  log "    deadline_epoch=${CW_DEADLINE_EPOCH:-<unset, governor disabled>} safety=${SAFETY_S}s" \
      "cell_s rag=$CELL_S_RAG pp1024=$CELL_S_PP1024"
  for spec in $PROMPTS_ORDER; do
    n=$(echo "$spec" | cut -d: -f1)
    have=$(mins_left)
    log "--- prompt $n : ${have} min affordable ---"
    picked=0
    for mr in ${MEAS_RUNS_CANDIDATES:-7 5}; do
      # 2 arms x (WARM_RUNS + mr) + CLOSE_RUNS closing cells on arm A
      nc=$(( 2 * (${WARM_RUNS:-3} + mr) + ${CLOSE_RUNS:-2} ))
      cost=$(cells_cost_min "$n" "$nc")
      log "    n=$mr -> $nc cells ~${cost} min"
      if need_mins "$cost"; then
        log "=== timing bracket A=$ARM_A B=$ARM_B prompt=$n MEAS_RUNS=$mr ($nc cells) ==="
        log "    armor protocol: ${WARM_RUNS:-3} warmup + $mr measured + ${CLOSE_RUNS:-2} closing (A..B..A)"
        (( mr != 7 )) && log "    NOTE: NON-DEFAULT n -- the pooled n and the drift armor must be reported with it"
        STAGE=timing ARM_A="$ARM_A" ARM_B="$ARM_B" ARM_C="$ARM_C" CELLTAG="$CELLTAG" \
          MEAS_RUNS="$mr" PROMPTS="$spec" bash "$CELLS_SH" || exit 1
        picked=1
        break
      fi
      log "    n=$mr DOES NOT FIT (${cost} > ${have} min affordable) — trying the next candidate"
    done
    if (( picked == 0 )); then
      log "SKIPPED $n: no bracket shape for it fits the remaining window. Recorded as a"
      log "          deliberate, arithmetic-forced omission — NOT as a completed measurement."
    fi
  done
  log "=== TIMING DONE ==="
  [[ "$STAGE" == "timing" ]] && exit 0
fi

if [[ "$STAGE" == "all" || "$STAGE" == "bitident" ]]; then
  # ── THE CLAIM THIS LEVER MAKES THAT ROPEVEC AND LTALGO COULD NOT ─────────────────────────────
  # Bit-identical to the control, element for element. Checked here against the arms' OWN generated
  # token streams, from cells already on disk (the gate's, and the bracket's --max-new 256 rag4096
  # cells, which is 256 tokens per sample per arm for free). Expected: 100% BITIDENT, 0 BITDIFF.
  # A single BITDIFF falsifies the construction argument and demotes this lever to ROPEVEC's class
  # (oracle-certified, not exact) — which is why the count is printed rather than assumed.
  log "=== bitident: $ARM_A vs $ARM_B generated token streams ==="
  $PY "$HERE/check_bitident_gemma3_round18.py" "$L18" "$ARM_A" "$ARM_B" \
    2>&1 | tee -a "$CW_LOGFILE"
  rc=${PIPESTATUS[0]}
  if (( rc != 0 )); then
    log "BITIDENT rc=$rc — NOT 100% bit-identical. The construction argument is FALSIFIED or the"
    log "          arms are not one macro apart. No 'bit-identical' claim may be published."
  else
    log "BITIDENT rc=0 — the two arms produced identical token streams on every comparable cell"
  fi
  [[ "$STAGE" == "bitident" ]] && exit $rc
fi

log "STAGE=$STAGE complete"
