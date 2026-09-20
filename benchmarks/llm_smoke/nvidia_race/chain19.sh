#!/usr/bin/env bash
# chain19.sh — ROUND 19 VM WINDOW DRIVER. RUN THIS ON THE VM, under setsid+nohup so it does NOT
# inherit the ssh channel (round 17 lost 2 x 300 s to exactly that).
#
#   setsid nohup bash ~/g3r19/benchmarks/llm_smoke/nvidia_race/chain19.sh \
#     </dev/null >~/lever19/chain19.out 2>&1 & disown
#
# ── WHAT ROUND 19 IS, AND WHY ITS SHAPE DIFFERS FROM ROUND 18'S ───────────────────────────────
# Round 18 implemented the vectorised f16 prefill GeGLU twin (`_pf_geglu_rows_f16_vec_kernel`),
# proved it BIT-IDENTICAL to the scalar twin (8/8 BITIDENT, 0 BITDIFF, PTX arithmetic verbatim at
# 8x), and MEASURED it at **-19.396 ms (-5.030%) on rag4096 at 24.5x its drift armor with complete
# rank separation (U=0, exact p=0.0079)**. It shipped DEFAULT OFF, and its gate ran ALL_PASS at a
# **REDUCED scope — `GATE SCOPE = ['pp1024']`**: pp256 and val550 were not certified either way and
# rag4096 was certified by arm-vs-arm bit-identity rather than by a fresh oracle gate.
#
# Round 19 therefore does two things in a strict order, and the order is the point:
#   (a) re-gate the lever arm at **FULL SCOPE** — the four shapes round 6 certified — because a
#       default is about to be flipped and a flip certified on one of four published shapes is a gap,
#       not a result. **If ANY gate cell fails, this chain STOPS: no timing, no flip, no row moves.**
#   (b) only then, measure the lever arm **as the future shipped default** at pp256 and pp1024, and
#       re-serve TensorRT-LLM 1.2.1 in the SAME SESSION, because a published row may only move on a
#       median basis against a same-session comparator with the drift armor holding.
#
# ── (b) IS A *DEFAULT* BRACKET, NOT AN A/B BRACKET, AND THAT IS A DELIBERATE CHOICE ───────────
# The quantity a published row needs is the shipped configuration's own median, not a delta — round
# 18 already resolved the delta at rag4096 with complete rank separation, and no published row is
# computed from a delta. So this window brackets ONE configuration under two labels, exactly as
# round 14 did for the post-#1042 default: `R19_def` and `R19_defB` are the SAME BINARY, `cp`'d and
# hash-asserted, because `run_gemma3_round6_cells.sh` always runs both ARM_A and ARM_B and would
# COLLIDE on the cell filename (silently discarding half the samples) if given one name twice. Every
# measured cell therefore belongs to the future default, so n per prompt is 2 x MEAS_RUNS, and the
# A-vs-B spread doubles as a run-to-run REPRODUCIBILITY measurement instead of a wasted slot. The
# closing cell is what makes the group A..B..A and the drift armor a MEASUREMENT.
#
# The control arm `R19_ctl` (the opt-out) is still BUILT and still AUDITED, because post-flip an arm
# is defined by what it opts out of and the audit's reading is INVERTED: the kernel-symbol set
# differential ctl -> def must be exactly 1 added / 0 removed, the added symbol must be the vector
# twin `b0496694ffefbc3c`, and the control must carry NO GEGLU_V2 banner literal. That is the proof
# the opt-out really restores the pre-round-19 default rather than being ignored.
#
# ── THE BUDGET, FROM MEASURED COSTS AND NOT FROM HOPE ─────────────────────────────────────────
# Every cell costs ~110-142 s REGARDLESS of prompt, because the dominant term is the driver loading
# the 101 GB checkpoint in a fresh process. Round 14 measured 22 pp256/pp1024 cells in ~44 min
# (~120 s each) and its TRT re-serve in **2 min 45 s** (serve READY after 72 s, three cells in 60 s).
# Round 18 measured a 3-cell pp1024 gate at 7 min 07 s (~142 s/cell) and `chain7stage.sh` at
# 6 min 36 s. Against a 90 min cap + 5 min grace:
#   boot+ssh+sync ~6 | stage ~7 | build+verify ~3 | FULL gate, 11 cells ~26  = ~42 min overhead
#   pp1024 bracket, 1 warm + 4 meas per slot + 1 closing = 11 cells        = ~22 min -> 64
#   pp256  bracket, same shape                                            = ~22 min -> 86
#   same-session TRT re-serve, three cells                                = ~3 min  -> 89
# **Both brackets plus the re-serve fit, with ~3 min of slack against a 92 min usable horizon.**
# That is arithmetic, and it is why the smoke stage is SKIPPED: it costs ~5 min to prove
# `gegluv_armed = true` at runtime, and the gate's own first cell proves it for free — the assertion
# is re-made below against the gate cells rather than dropped, exactly as round 18 did.
#
# Because the slack is thin, the governor still decides from the CLOCK and not from this table: it
# walks the prompts in priority order, prices each candidate bracket shape, and **reserves both the
# TRT re-serve and the next prompt's minimum viable bracket before starting this one** — the
# reservation is what round 18's governor lacked, and without it a window can spend itself on the
# first bracket and leave no same-session comparator, which makes NOTHING publishable. A shape that
# cannot finish is declined in the log, never started and abandoned: a killed bracket is
# unpublishable, a declined one merely is not.
#
# ── PHASES ────────────────────────────────────────────────────────────────────────────────────
#   stage    chain7stage.sh: fixtures regenerated AND PROVEN IDENTICAL to round 6's certified gate
#            echoes, 101 GB checkpoint converted to /mnt/ramblob, GPU1 pinned and VERIFIED at
#            1410 MHz with zero off-pin tolerance. Nothing downstream may run until STAGE_OK.
#   build    the stock shim + R19_ctl + R19_def, then the binary audit (banner literals AND the
#            self-computing kernel-hash differential). No GPU work.
#   twin     cp R19_def -> R19_defB and assert the two hashes are EQUAL. Refuses on mismatch.
#   gate     the FULL-SCOPE fp32-oracle gate on R19_def, BEFORE any timing cell. Any failure stops.
#   armed    assert `gegluv_armed = true` from the gate cells (free) — the lever must have taken
#            effect at RUNTIME, not merely compiled in.
#   timing   the default bracket, reserve-governed: pp1024 first, then pp256.
#   trtllm   the same-session TensorRT-LLM 1.2.1 re-serve + the reproduction check.
#   summary  medians, IQR, closing-cell drift armor, ratios vs the same-session comparator.
#   bitident R19_def vs R19_defB token streams — the twin mechanism's own identity check.
#
# A phase that fails stops the chain. A phase that would overrun the deadline is killed and the log
# says KILLED_BY_OPERATOR, so an abandoned window is self-describing rather than mysterious.
set -uo pipefail

SRC_TREE=${SRC_TREE:-$HOME/g3r19}
L19=${L19:-$HOME/lever19}
L3=${L3:-$HOME/lever3}                     # lv3_trtllm.sh + gate_any.py + cell_watchdog.sh
GPU=${GPU:-1}
CAP_MIN=${CAP_MIN:-90}
GRACE_MIN=${GRACE_MIN:-5}
NR="$SRC_TREE/benchmarks/llm_smoke/nvidia_race"
RUNNER=${RUNNER:-$NR/run_ab_gemma3_round18.sh}   # round 19 re-targets round 18's runner via its knobs
# The shim object dir is tmpfs and is cleared by vm_sync_r19.sh, so it must be THIS round's: the
# shim #includes a GENERATED header, and re-using a previous round's dir would link the arms against
# a header from a tree that is no longer the one being measured.
PTXD=${PTXD:-/tmp/g3r19tc}
export GPU SRC_TREE PTXD L18="$L19"               # the runner reads L18; point it at round 19's dir

# ── ROUND 19'S ARM NAMES ──────────────────────────────────────────────────────────────────────
DEF=${DEF:-R19_def}        # the POST-flip shipped default: R6_STACK with NO opt-out. Gated + timed.
CTL=${CTL:-R19_ctl}        # the PRE-flip shipped default: R6_STACK + -D ALGENTA_G3_PF_NO_GEGLUV2.
TWIN=${TWIN:-R19_defB}     # byte-identical cp of DEF, distinct label so cells cannot collide.
CELLTAG=${CELLTAG:-_r19}   # so this window's cells do not pool with earlier rounds'
# The gate's own verdict file, named here rather than at the point of use because BOTH the
# SKIP_GATE re-verification path and the fresh-gate coverage audit read it, and the former runs
# first. Under `set -u` a variable first assigned below its first use is a hard failure, not a
# silent empty string.
GJ="$L19/oracle_gate_${DEF}.json"
export DEF CTL TWIN CELLTAG

# ── THE FULL GATE SCOPE, SPELLED OUT RATHER THAN INHERITED ────────────────────────────────────
# `run_gemma3_round6_cells.sh` defaults GATE_SPECS to exactly these four prompts, but round 18's
# runner narrows that default to the two bracketed shapes — so round 19 names all four explicitly
# here and the runner logs NO "NON-DEFAULT" note, because this IS the default scope. Round 18's
# reduced gate is the gap this closes: pp256 and val550 were "not certified either way" there.
GATE_SPECS=${GATE_SPECS:-"pp256:/tmp/g3pp256/prompt_0000.txt pp1024:/tmp/g3pp1024/prompt_0000.txt val550:/tmp/g3race500/prompt_0000.txt rag4096:/tmp/g3rag/rag4096.txt"}
# ── THE TIMING ORDER, AND WHY pp1024 GOES FIRST ───────────────────────────────────────────────
# Both prompts have ZERO banked cells for this configuration, so neither can be filled in from an
# earlier window. pp1024 goes first because it carries the larger absolute prize (a ~5% saving is
# ~4.7 ms at pp1024 against ~1.5 ms at pp256) and the tighter published row (1.18x vs 1.35x), i.e.
# it is the one that must not be the casualty of a cap bite. Round 14 used the same reasoning.
PROMPT_PP1024="pp1024:/tmp/g3pp1024/prompt_0000.txt:1"
PROMPT_PP256="pp256:/tmp/g3pp256/prompt_0000.txt:1"
PROMPTS_ORDER=${PROMPTS_ORDER:-"$PROMPT_PP1024 $PROMPT_PP256"}
# REQUIRED_PROMPTS is what the flip is licensed on, and it is BOTH, not "as many as fit". The owner's
# rule, made explicit before the box was started: the default-flip PR merges only when pp1024 AND pp256
# cells plus their same-session TRT are in hand alongside the banked full-scope gate and round 18's rag
# bracket. If the governor must drop pp256 for the clock, this chain STOPS and reports rather than
# handing back a half-measured flip -- because the published pp256 row (1.35x) would then describe a
# configuration that is no longer the shipped default, and a stale row on a flipped default is a
# docs-integrity defect, not a rounding nicety. Dropping pp1024 instead is equally fatal.
REQUIRED_PROMPTS=${REQUIRED_PROMPTS:-"pp1024 pp256"}
DONE_PROMPTS=""
# n candidates per SLOT, in preference order. n_reported = 2 x MEAS_RUNS because both slots are the
# same binary. The floor is 3 (n=6) — the mission's n>=5 — and the preference is 4 (n=8), which is
# what round 14 measured the post-#1042 default on.
MEAS_RUNS_CANDIDATES=${MEAS_RUNS_CANDIDATES:-4 3}
WARM_RUNS=${WARM_RUNS:-1}
CLOSE_RUNS=${CLOSE_RUNS:-1}
# Per-cell seconds, for the governor only, from MEASURED costs. Over-estimates are deliberate: a
# governor that under-estimates spends the window, one that over-estimates only declines to.
CELL_S_PP1024=${CELL_S_PP1024:-122}
CELL_S_PP256=${CELL_S_PP256:-118}
CELL_S_RAG=${CELL_S_RAG:-140}
SAFETY_S=${SAFETY_S:-240}                  # stop-issuing margin, on top of the 5-min grace
# THE TRT RESERVE, AND WHY IT IS RESERVED RATHER THAN LEFT OVER. Round 14 measured the re-serve at
# 2 min 45 s; chain14's own guard was 8 min. Without it the re-serve still costs a quiesce, a
# 72 s serve startup and three cells, and a window that spends itself on brackets first ends with no
# same-session comparator — at which point NO row is publishable and the brackets were worth less
# than the 3 minutes they crowded out. 8 min is the round-14 guard, kept.
TRT_RESERVE_MIN=${TRT_RESERVE_MIN:-8}

export MEAS_RUNS_CANDIDATES WARM_RUNS CLOSE_RUNS GATE_SPECS PROMPTS_ORDER
export SKIP_SMOKE CELL_S_RAG CELL_S_PP1024 CELL_S_PP256 SAFETY_S SKIP_STAGE
export ARM_A_EXTRA ARM_B_EXTRA

if [[ -z "${CW_DEADLINE_EPOCH:-}" ]]; then
  echo "FATAL: CW_DEADLINE_EPOCH is unset. The cap is VM-ON time from lastStartTimestamp, which"
  echo "       includes the boot+ssh this script cannot observe, so only the caller can compute it:"
  echo "         gcloud compute instances describe trtllm-gemma-us-west1-c --project=eplanev2 \\"
  echo "           --zone=us-west1-c --format='value(lastStartTimestamp)'"
  echo "       Refusing to run an uncapped spot window."
  exit 2
fi
export CW_DEADLINE_EPOCH

mkdir -p "$L19/logs" "$L19/runs" "$L19/clocks"
# Freshness reference for the TRT JSON copy below: a file older than this chain's own start is a
# previous window's re-serve and must never be passed off as same-session.
CHAIN_START_MARK=$L19/.chain_start
: > "$CHAIN_START_MARK"
CW_LOGFILE=${CW_LOGFILE:-$L19/round19.log}
export CW_LOGFILE
HB=$L19/heartbeat.log

# ── THE HEARTBEAT READS ITS STATE FROM FILES, BECAUSE A SUBSHELL SNAPSHOTS VARIABLES AT FORK ────
# DEFECT, INHERITED FROM chain18.sh AND REPRODUCED IN ROUND 19'S WINDOW. The heartbeat writer is a
# background subshell, and a subshell gets a COPY of the parent's variables at fork time. It therefore
# printed `phase=init` for the entire window -- observed on every heartbeat line from 21:58:48Z to
# 22:28:49Z, straight through the stage, build, twin and FULL-SCOPE gate phases -- because `PHASE`
# was "init" when the subshell forked and no later assignment in the parent was ever visible to it.
# Round 18's heartbeats show the same frozen `phase=init` through its gate and timing phases, so this
# was never a round-19 regression; it is the inherited reason a heartbeat could not answer the one
# question a heartbeat exists to answer -- WHICH PHASE IS RUNNING -- without an ssh round trip. During
# round 19 that cost real diagnosis time: from the Mac the window looked stuck at `init` for 30
# minutes, and telling "wedged" from "busy in the gate" needed a direct read of round19.log.
# The fix is to publish the state through the filesystem, which a subshell re-reads every iteration.
PHASE_FILE=$L19/PHASE
GATE_FILE=$L19/GATE_VERDICT
set_phase() { PHASE="$1"; echo "$1" > "$PHASE_FILE" 2>/dev/null; }
set_gate()  { GATE_VERDICT="$1"; echo "$1" > "$GATE_FILE" 2>/dev/null; }
set_phase "init"
set_gate "NOT_RUN"

# ── THE CHAIN'S FATE IS AN ARTIFACT, NOT AN INFERENCE ─────────────────────────────────────────
# Round 18 exposed the cost of not having this: the chain died twice and from OUTSIDE the box the
# only evidence was a heartbeat that had gone stale. A stale heartbeat says "something stopped",
# never "what finished, what failed, and whether any cell was timed". This trap writes the answer to
# the persistent boot disk on EVERY exit path, including a failure exit and a signal.
CHAIN_EXIT=$L19/CHAIN_EXIT
: > "$CHAIN_EXIT"
TIMING_COMPLETE=no
TRT_DONE=no
# FLIP_LICENSED is the owner's row-integrity rule made mechanical: a flipped default whose pp256 row
# was never re-measured is a STALE PUBLISHED ROW, i.e. a docs-integrity defect, so "one prompt fit and
# the other did not" is NOT a partial success -- it is a refusal to flip. Only yes licenses the merge.
FLIP_LICENSED=no
RAG_TRT_BASIS=unset
set_gate "NOT_RUN"
chain_exit() {
  local rc=$1
  {
    echo "chain19_exit_utc=$(date -u +%FT%TZ)"
    echo "rc=$rc"
    echo "phase=$PHASE"
    echo "gate_verdict=$GATE_VERDICT"
    echo "timing_complete=$TIMING_COMPLETE"
    echo "trt_reserve_done=$TRT_DONE"
    echo "flip_licensed=$FLIP_LICENSED"
    echo "prompts_completed=$DONE_PROMPTS"
    echo "rag_trt_basis=$RAG_TRT_BASIS"
    echo "measured_cells=$(ls -1 "$L19"/runs/r6*_r[0-9].out 2>/dev/null | wc -l | tr -d ' ')"
    echo "gate_cells=$(ls -1 "$L19"/gate_*/gate_*.out 2>/dev/null | wc -l | tr -d ' ')"
    echo "deadline_epoch=${CW_DEADLINE_EPOCH:-unset}"
    echo "mins_left_at_exit=$(mins_left)"
  } >> "$CHAIN_EXIT"
  log "CHAIN19 EXIT rc=$rc phase=$PHASE gate=$GATE_VERDICT timing_complete=$TIMING_COMPLETE" \
      "trt=$TRT_DONE (recorded in $CHAIN_EXIT)"
}
trap 'chain_exit $?' EXIT
trap 'chain_exit 143; kill $HB_PID $WD_PID 2>/dev/null; exit 143' TERM
trap 'chain_exit 130; kill $HB_PID $WD_PID 2>/dev/null; exit 130' INT
# ── AND THEN RE-REGISTER *ONE* EXIT TRAP, BECAUSE `trap ... EXIT` REPLACES RATHER THAN STACKS ───
# THE DEFECT THIS FIXES WAS INHERITED FROM chain18.sh AND ROUND 19 REPRODUCED IT ON THE VM. chain18
# set `trap 'chain_exit $?' EXIT` here and then, further down, set `trap 'kill $HB_PID ...' EXIT`
# again after each background pid appeared. In bash a later EXIT trap OVERWRITES the earlier one —
# it does not chain — so by the time the chain exited normally, `chain_exit` was no longer
# registered and **CHAIN_EXIT was written empty**. Round 18 never noticed because both of its chain
# deaths were operator SIGTERMs, which hit the TERM trap (where `chain_exit` IS still registered)
# and so did write the file. Round 19's chain exited itself with `exit 1`, took the plain EXIT path,
# and left CHAIN_EXIT empty — measured on the box at 22:29:38Z, `cat ~/lever19/CHAIN_EXIT` returning
# nothing while the backstop logged `CHAIN_EXIT=[]` on every probe for the next 20 minutes.
# THE COST IS NOT COSMETIC. CHAIN_EXIT is what lets the backstop distinguish "the chain died and the
# measurement never finished" from "the chain is between phases": its early-stop arm tests
# `fate == *timing_complete=no* && alive == 0`. With the file empty that test can never pass, so the
# early stop never fires and an idle spot H200 keeps billing until the DEADLINE — exactly the burn
# the artifact exists to prevent, arriving on the one path (a chain that exits itself) where it
# matters most. So: the heartbeat/watchdog kills are folded INTO the single EXIT trap below, after
# both pids exist, and `chain_exit` is re-asserted last so it cannot be displaced again.
_final_exit() {
  local rc=$1
  # unset-safe: an exit before the heartbeat/watchdog started must not trip `set -u` inside the trap,
  # which would abort the trap and lose CHAIN_EXIT a second time.
  kill "${HB_PID:-}" "${WD_PID:-}" 2>/dev/null
  chain_exit "$rc"
}
trap '_final_exit $?' EXIT
trap '_final_exit 143; exit 143' TERM
trap '_final_exit 130; exit 130' INT

ts() { date -u +%FT%TZ; }
log() { echo "[$(ts)] $*" | tee -a "$CW_LOGFILE"; }
mins_left() {
  local left=$(( (CW_DEADLINE_EPOCH - $(date +%s)) / 60 ))
  (( left < 0 )) && left=0
  echo "$left"
}
# The governor plans against the deadline MINUS the stop-issuing safety margin, which is the only
# honest horizon: a bracket that finishes after the stop is issued does not finish.
affordable_min() {
  local left=$(( (CW_DEADLINE_EPOCH - SAFETY_S - $(date +%s)) / 60 ))
  (( left < 0 )) && left=0
  echo "$left"
}

( while true; do
    # re-read the published state every iteration: `$PHASE`/`$GATE_VERDICT` here would be the values
    # this subshell forked with, which is the frozen-`init` defect described above.
    _p=$(cat "$PHASE_FILE" 2>/dev/null); _g=$(cat "$GATE_FILE" 2>/dev/null)
    echo "$(date -u +%FT%TZ) chain19 GPU=$GPU phase=${_p:-?} pid=$$ mins_left=$(mins_left)" \
      "affordable=$(affordable_min) gate=${_g:-?}" >> "$HB"
    sleep 60
  done ) &
HB_PID=$!
# NO `trap ... EXIT` HERE. Registering one would OVERWRITE the single _final_exit trap above and
# silently un-register `chain_exit`, which is the CHAIN_EXIT-was-empty defect this round reproduced.

# THE DEADLINE WATCHDOG. Separate process, so a phase that hangs is still killed: the chain's own
# budget checks only run BETWEEN phases, and a wedged cell would otherwise sit on the GPU until the
# spot instance was reclaimed. It kills the phase's process GROUP (not a name pattern), writes
# KILLED_BY_OPERATOR so the window is self-describing, and exits non-zero.
(
  while true; do
    sleep 30
    if (( $(date +%s) >= CW_DEADLINE_EPOCH )); then
      echo "[$(date -u +%FT%TZ)] KILLED_BY_OPERATOR phase=$PHASE deadline=$CW_DEADLINE_EPOCH reached" \
        | tee -a "$CW_LOGFILE" "$HB"
      kill -TERM -- -$$ 2>/dev/null
      sleep 20
      kill -KILL -- -$$ 2>/dev/null
      exit 1
    fi
  done
) &
WD_PID=$!
# NO `trap ... EXIT` HERE EITHER, for the same reason. Both pids are killed by _final_exit.

run_phase() { # $1 = phase name ; rest = command
  set_phase "$1"; shift
  log "=== PHASE $PHASE  (mins_left=$(mins_left) affordable=$(affordable_min))  cmd: $* ==="
  "$@"
  local rc=$?
  log "=== PHASE $PHASE rc=$rc  (mins_left=$(mins_left) affordable=$(affordable_min)) ==="
  return $rc
}

log "CHAIN19 START deadline=$CW_DEADLINE_EPOCH ($(date -u -d "@$CW_DEADLINE_EPOCH" +%FT%TZ 2>/dev/null || echo '?'))" \
    "cap=${CAP_MIN}m grace=${GRACE_MIN}m mins_left=$(mins_left) tree=$SRC_TREE"
log "synced_head=$(cat "$SRC_TREE/.synced_head" 2>/dev/null || echo '<none>')"
log "ROUND 19 SCOPE: (a) FULL-SCOPE gate on $DEF = [$GATE_SPECS]"
log "                (b) iff ALL_PASS: the $DEF/$TWIN default bracket over [$PROMPTS_ORDER]"
log "                    then the same-session TRT re-serve. Any gate failure => NO timing, NO flip."
log "governor: MEAS_RUNS_CANDIDATES='$MEAS_RUNS_CANDIDATES' warm=$WARM_RUNS close=$CLOSE_RUNS" \
    "trt_reserve=${TRT_RESERVE_MIN}m safety=${SAFETY_S}s" \
    "cell_s pp1024=$CELL_S_PP1024 pp256=$CELL_S_PP256 rag=$CELL_S_RAG"

# ── 1. STAGE ──────────────────────────────────────────────────────────────────────────────────
# Fixtures must be PROVEN identical to round 6's certified echoes before anything is measured; the
# chain aborts if it cannot prove that, because a benchmark on unproven fixtures is not a benchmark.
# SKIP_STAGE=1 RE-USES a stage that already ran IN THIS SAME VM-ON SESSION and RE-VERIFIES rather
# than trusts: /tmp and /mnt/ramblob are tmpfs and die with the instance, so it is only sound while
# the box has stayed up. Round 18 needed it to recover from a harness bug without re-paying 7 min.
if [[ "${SKIP_STAGE:-0}" == "1" ]]; then
  set_phase "stage_reverify"
  log "=== PHASE stage_reverify (SKIP_STAGE=1) — re-proving, not trusting, the prior STAGE_OK ==="
  ok=1
  for f in /tmp/g3pp256/prompt_0000.txt /tmp/g3pp1024/prompt_0000.txt \
           /tmp/g3race500/prompt_0000.txt /tmp/g3rag/rag4096.txt; do
    if [[ -f "$f" ]]; then
      log "  FIXTURE $f ($(tr ',' '\n' < "$f" | grep -c .) ids)"
    else
      log "  FIXTURE MISSING $f"; ok=0
    fi
  done
  if [[ -d /mnt/ramblob/g3conv27b ]]; then
    log "  CHECKPOINT present: $(du -sh /mnt/ramblob/g3conv27b 2>/dev/null | cut -f1)"
  else
    log "  CHECKPOINT MISSING at /mnt/ramblob/g3conv27b"; ok=0
  fi
  prior=$(grep -c "STAGE_OK" "$L19/chain7stage.log" 2>/dev/null || echo 0)
  log "  prior STAGE_OK markers in this session's stage log: $prior"
  (( prior == 0 )) && { log "  no prior STAGE_OK — SKIP_STAGE is not justified"; ok=0; }
  PIN=$(nvidia-smi -i "$GPU" --query-gpu=clocks.current.sm --format=csv,noheader,nounits)
  log "  GPU$GPU clocks.current.sm=$PIN (want 1410 — ZERO off-pin tolerance)"
  [[ "$PIN" != "1410" ]] && { log "  OFF_PIN: $PIN != 1410 — re-pin or do not measure"; ok=0; }
  if (( ok != 1 )); then
    log "STAGE_REVERIFY FAILED — falling back to a full stage rather than measuring on trust"
    STAGE_SRC="$SRC_TREE" L7="$L19" run_phase stage bash "$NR/chain7stage.sh" || exit 1
  else
    log "=== PHASE stage_reverify rc=0 — fixtures, checkpoint and the 1410 MHz pin all re-proven ==="
  fi
else
STAGE_SRC="$SRC_TREE" L7="$L19" \
  run_phase stage bash "$NR/chain7stage.sh" || { log "STAGE FAILED — nothing may be measured"; exit 1; }
# fold the stage's own load-bearing lines into the SINGLE window log, so the round's evidence does
# not depend on reading two files: fixture identity, the checkpoint, and the verified clock pin.
grep -E "STAGE_OK|FIXTURE_IDENTITY_OK|FIXTURE |CHECKPOINT present|clocks.current.sm=|OFF_PIN" \
  "$L19/chain7stage.log" 2>/dev/null | tail -12 | tee -a "$CW_LOGFILE"
grep -q "STAGE_OK" "$L19/chain7stage.log" 2>/dev/null || {
  log "FATAL: no STAGE_OK in the stage log. Refusing to build or measure."; exit 1; }
# FIXTURE IDENTITY IS A HARD PRECONDITION THIS ROUND, not a nicety. The gate's whole claim is
# "the same fixtures round 6 certified", so an unproven fixture makes every gate number below
# incomparable with the certified echoes — and round 19's deliverable IS that comparability.
grep -q "FIXTURE_IDENTITY_OK=True" "$L19/chain7stage.log" 2>/dev/null || {
  log "FATAL: fixtures were not proven identical to round 6's certified echoes. The gate would"; exit 1; }
log "FIXTURES PROVEN IDENTICAL to round 6's certified echoes — the gate is comparable with them"
fi

# ── 2. BUILD + VERIFY, OR RE-VERIFY THE BANKED ARM ────────────────────────────────────────────
# ARM_A=CTL and ARM_B=DEF so the runner's own verify_arms reads the differential in the direction
# that proves the flip: the CONTROL must carry no GEGLU_V2 banner literal, the DEFAULT must, and the
# kernel-symbol set difference ctl -> def must be exactly 1 added / 0 removed with the added symbol
# being the vector twin. ARM (the arm the gate must earn) is DEF.
#
# SKIP_BUILD=1 RE-USES THE ARM A PREVIOUS VM-ON SESSION BUILT AND THE FULL-SCOPE GATE CERTIFIED, and
# that is a TRACEABILITY REQUIREMENT, NOT MERELY A TIME SAVE. The certification attaches to a BINARY,
# by hash, and to nothing else: rebuilding would silently detach the gate from whatever actually gets
# timed, which is round 14's stated reason for pinning hashes and making a mismatch FATAL rather than
# a warning. The arms live in ~/lever19 on the PERSISTENT boot disk, so they survive the stop that
# wiped /tmp and /mnt/ramblob; the checkpoint and fixtures do not, which is why SKIP_STAGE cannot be
# set alongside it and the stage always re-runs and re-proves fixture identity.
#
# THE PINNED HASHES, from the window that ran the gate (round19.log, 22:06:12Z, synced_head
# feat/gemma3-gegluv2-flip-r19 @ 5f12d6f5):
#   R19_def  e4c6fbe26376f817  6182864 B  GEGLU_V2 banner literal = 1  -> VERIFIED ARMED
#   R19_ctl  c033fd2982dc6435  6167416 B  GEGLU_V2 banner literal = 0  -> VERIFIED CLEAN
#   kernel-symbol set ctl=38 def=39, ADDED b0496694ffefbc3c, REMOVED none
# Those two banner counts are the first time this campaign's inverted audit row has been exercised on
# REAL LINKED arms rather than on `--emit object` artifacts, which discharges the limit #1042 and
# round 18 both recorded.
EXPECT_DEF_SHA=${EXPECT_DEF_SHA:-e4c6fbe26376f817}
EXPECT_CTL_SHA=${EXPECT_CTL_SHA:-c033fd2982dc6435}
EXPECT_VEC_HASH=${EXPECT_VEC_HASH:-b0496694ffefbc3c}
if [[ "${SKIP_BUILD:-0}" == "1" ]]; then
  set_phase "build_reverify"
  log "=== PHASE build_reverify (SKIP_BUILD=1) — re-proving the banked arms by HASH, not rebuilding ==="
  ok=1
  for a in "$DEF" "$CTL"; do
    if [[ -x "$L19/$a" ]]; then
      h=$(sha256sum "$L19/$a" | cut -c1-16)
      log "  $a sha256_16=$h bytes=$(stat -c %s "$L19/$a")"
    else
      log "  ARM MISSING $L19/$a"; ok=0; continue
    fi
    want=$EXPECT_CTL_SHA; [[ "$a" == "$DEF" ]] && want=$EXPECT_DEF_SHA
    if [[ "$h" != "$want" ]]; then
      log "  *** HASH MISMATCH for $a: got $h, the gated arm is $want. FATAL, not a warning —"
      log "      timing a rebuilt binary would detach the full-scope certification from it."
      ok=0
    fi
  done
  if (( ok == 1 )); then
    # re-run the runner's OWN binary audit rather than trusting the banked one: banner literals plus
    # the self-computing kernel-symbol differential, over the linked arms as they exist now.
    run_phase verify env STAGE=verify BUILD_ARMS=0 ARM="$DEF" ARM_A="$CTL" ARM_B="$DEF" \
      bash "$RUNNER" || { log "VERIFY FAILED on the banked arms"; ok=0; }
  fi
  if (( ok != 1 )); then
    log "BUILD_REVERIFY FAILED — falling back to a full build. NOTE: a fresh binary is then NOT the"
    log "  one the banked gate certified, so SKIP_GATE must not be honoured either."
    SKIP_GATE=0
    run_phase build env STAGE=build ARM="$DEF" ARM_A="$CTL" ARM_B="$DEF" bash "$RUNNER" || {
      log "BUILD/VERIFY FAILED — no arm, no window"; exit 1; }
  fi
else
run_phase build env STAGE=build ARM="$DEF" ARM_A="$CTL" ARM_B="$DEF" bash "$RUNNER" || {
  log "BUILD/VERIFY FAILED — no arm, no window"; exit 1; }
fi
[[ -x "$L19/$DEF" ]] || { log "FATAL: $L19/$DEF was not produced"; exit 1; }
log "DEFAULT ARM $DEF sha256_16=$(sha256sum "$L19/$DEF" | cut -c1-16) bytes=$(stat -c %s "$L19/$DEF")"
log "CONTROL ARM $CTL sha256_16=$(sha256sum "$L19/$CTL" | cut -c1-16) bytes=$(stat -c %s "$L19/$CTL")"

# ── 3. TWIN ───────────────────────────────────────────────────────────────────────────────────
# Proven identical BY HASH rather than assumed, before any cell runs: if the twin were not the same
# bits, half the bracket's samples would belong to an unknown configuration and the pooled n would
# be a lie. This is round 14's TWIN_IDENTICAL check, kept verbatim in intent.
set_phase "twin"
cp -f "$L19/$DEF" "$L19/$TWIN"
h1=$(sha256sum "$L19/$DEF" | cut -c1-16); h2=$(sha256sum "$L19/$TWIN" | cut -c1-16)
log "TWIN $TWIN sha256_16=$h2 vs $DEF sha256_16=$h1"
[[ "$h1" == "$h2" ]] || { log "FATAL: TWIN HASH MISMATCH — refusing to bracket"; exit 1; }
log "TWIN_IDENTICAL=True (so every cell from either slot is a sample of ONE configuration, and the"
log "  A-vs-B spread is a run-to-run REPRODUCIBILITY measurement rather than a wasted arm)"

# ── 4. SMOKE — SKIPPED, WITH THE ASSERTION IT EXISTS FOR RE-MADE FOR FREE AFTER THE GATE ──────
# `gegluv_armed = true` proves the lever took effect at RUNTIME rather than merely compiling in
# (LTALGO's `lt_shapes_tuned = 0` hazard). The smoke stage costs ~5 min of a budget whose slack is
# ~3 min to prove something the gate's own first cell prints, so the stage is skipped and the
# assertion is enforced below against the gate cells — which is what round 18 did, and what its
# header says: the control's cleanliness is NOT a runtime fact at all, it is verify_arms' `strings`
# audit, which has already run.
if [[ "${SKIP_SMOKE:-1}" == "1" ]]; then
  log "PHASE smoke SKIPPED (SKIP_SMOKE=${SKIP_SMOKE:-1}) — gegluv_armed is asserted after the gate"
else
  run_phase smoke env STAGE=smoke ARM_A="$CTL" ARM_B="$DEF" bash "$RUNNER" || {
    log "SMOKE FAILED — the lever did not arm at runtime; refusing to gate or time it"; exit 1; }
fi

# ── 5. GATE, FULL SCOPE, BEFORE ANY TIMING CELL ───────────────────────────────────────────────
# 11 cells: pp256/pp1024/val550 at maxnew 16 and 64 plus a `rep2` bit-identical determinism repeat
# each, and rag4096 at 64 + rep2 (the runner skips maxnew16 for rag4096, which is how round 6's
# certified 22/22 + EOS-stop shape is produced). A gate cell costs ~110-142 s, so ~26 min. Below 28
# min affordable the gate cannot finish, and a gate that cannot finish means no timing may be taken
# at all — so say so and stop rather than start a gate the watchdog will kill mid-cell.
# SKIP_GATE=1 RE-USES A FULL-SCOPE GATE THAT ALREADY PASSED ON THIS VERY BINARY, and re-proves it
# rather than trusting it. Round 19's first window ran the gate to completion at 22:29:38Z
# (all_pass=True over all four shapes, 11 cells, 0 divergences) and then a coverage-counting defect
# in this chain refused it and exited — so the certification exists and is banked on the boot disk at
# ~/lever19/oracle_gate_R19_def.json, and re-running 11 cells (~26 min) to re-derive a verdict already
# on disk would spend nearly half of a 60-min re-serve window. What is re-proven here, all of it
# cheaply and all of it falsifiable:
#   * the coverage evaluator passes over the BANKED JSON (the same evaluator, so the verdict is the
#     one this chain would have reached had its counter not been broken);
#   * the 11 gate cell files are still on disk under gate_<arm>/, so the JSON is not orphaned;
#   * the gated arm's name is this window's DEF, and DEF's hash is the pinned EXPECT_DEF_SHA, so the
#     certification attaches to the binary about to be timed;
#   * `gegluv_armed = true` still reads out of a banked gate cell, i.e. the lever took effect at
#     RUNTIME on the very cells that certified it.
# Any failure falls through to a real gate. This is SKIP_STAGE's discipline applied to the gate, and
# it is sound for the same reason: the boot disk persists across the stop, the evidence is re-read
# rather than assumed, and the fallback is the expensive correct path.
if [[ "${SKIP_GATE:-0}" == "1" ]]; then
  set_phase "gate_reverify"
  log "=== PHASE gate_reverify (SKIP_GATE=1) — re-proving the BANKED full-scope gate ==="
  gok=1
  if [[ ! -f "$GJ" ]]; then log "  no banked gate JSON at $GJ"; gok=0; fi
  if (( gok == 1 )); then
    ngate=$(ls -1 "$L19/gate_$DEF"/gate_*.out 2>/dev/null | wc -l | tr -d ' ')
    log "  banked gate cells on disk: $ngate (want 11 = pp256/pp1024/val550 x3 + rag4096 x2)"
    (( ngate != 11 )) && { log "  *** gate cell count is not 11 — the JSON may be orphaned"; gok=0; }
  fi
  if (( gok == 1 )); then
    dh=$(sha256sum "$L19/$DEF" 2>/dev/null | cut -c1-16)
    log "  $DEF sha256_16=$dh vs the pinned gated arm $EXPECT_DEF_SHA"
    [[ "$dh" == "$EXPECT_DEF_SHA" ]] || { log "  *** the binary is NOT the gated one"; gok=0; }
  fi
  if (( gok == 1 )); then
# MOJO RENDERS `Bool` CAPITALISED, AND THIS PATTERN NEVER KNEW. The banner is printed by
# `print("... gegluv_armed =", self.d_ff % _G3_GEGLUV_VEC == 0, ...)`, and Mojo renders a Bool as
# `True`/`False`, so the cells contain `gegluv_armed = True`. Every check in this campaign was
# written against a lowercase `gegluv_armed = true` and therefore NEVER MATCHED A REAL BANNER --
# round 19 measured it on the box: 10 occurrences of `gegluv_armed = True` and ZERO of the lowercase
# spelling across the 11 banked gate cells. The consequence is not a missing assertion but a
# PERMANENTLY FALSE one: `audit_tc_flags.sh` reported `gegluv_armed: false` for correctly-armed arms,
# and the runner/chain assertions FATAL on an arm that is in fact live. A safety field that is always
# false is worse than no field, because it cries wolf until a genuinely declined arm is waved through
# as the same known bug. It went unnoticed because round 18's windows died earlier for other reasons
# and its timing was launched by hand after a manual recovery, so the assertion never ran to verdict.
# Both spellings are accepted: `[Tt]rue` matches what Mojo emits today and keeps working if a future
# toolchain lowercases it, and a DECLINED arm still fails both, which is the case that must not slip.
    # Search ONLY the cell .out files and for the ARMED literal directly: `grep -rl` over the whole
    # gate dir also walks clocks/ and logs/, and `head -1` then hands back whichever file the
    # traversal reached first rather than one that can answer the question.
    ga=$(grep -lE "gegluv_armed = [Tt]rue" "$L19/gate_$DEF"/gate_*.out 2>/dev/null | head -1)
    if [[ -n "$ga" ]]; then
      log "  $(grep -ohE "gegluv_armed = [Tt]rue" "$ga" | head -1) re-read from the banked gate cell $ga"
    else
      log "  *** gegluv_armed is not true in the banked gate cells"; gok=0
    fi
  fi
  if (( gok == 1 )); then
    log "  running the coverage evaluator over the BANKED JSON (the verdict this chain should have"
    log "    reached at 22:29:38Z had its scope counter not matched out_of_scope= )"
    BANKED=$(/usr/bin/python3 "$NR/gate_coverage_gemma3_round19.py" "$GJ" 2>&1); brc=$?
    echo "$BANKED" | while IFS= read -r ln; do log "    $ln"; done
    (( brc != 0 )) && { log "  *** the banked gate does NOT prove full scope"; gok=0; }
  fi
  if (( gok == 1 )); then
    set_gate "ALL_PASS_FULL_SCOPE(banked, re-verified)"
    log "=== PHASE gate_reverify rc=0 — the BANKED full-scope certification is re-proven and"
    log "    attached by hash to the binary about to be timed. Timing may proceed. ==="
  else
    log "GATE_REVERIFY FAILED — running the real gate rather than timing on trust"
    SKIP_GATE=0
  fi
fi
if [[ "${SKIP_GATE:-0}" == "1" ]]; then
  log "fresh gate SKIPPED — the banked full-scope certification was re-proven above and is pinned"
  log "  by hash to $DEF, so re-running 11 cells would re-derive a verdict already on disk"
elif (( $(affordable_min) < 28 )); then
  log "KILLED_BY_OPERATOR (pre-gate): only $(affordable_min) min affordable, which cannot fund the"
  log "  FULL-SCOPE gate (11 cells, ~26 min). NO timing was taken and none may be published, and"
  log "  THE FLIP DOES NOT HAPPEN — round 19's (a) is a precondition for (b), not a parallel task."
  set_gate "NOT_FUNDED"
  exit 1
else
  run_phase gate env STAGE=gate ARM="$DEF" bash "$RUNNER" || {
    set_gate "FAILED"
    log "GATE FAILED — NO timing cells may be taken or published for this arm, THE FLIP DOES NOT"
    log "  HAPPEN, and no published row moves. Recording and stopping, per the round-19 order."
    exit 1; }
fi
# Read the verdict back from the gate's own JSON rather than from the phase's exit code, so the
# ledger can quote the SCOPE the gate actually covered. Round 18's gap was exactly this field: its
# gate reported ALL_PASS=True at `GATE SCOPE = ['pp1024']`, which reads as a pass unless the scope
# is quoted next to it.
#
# ── THE COVERAGE AUDIT, AND THE DEFECT THAT MADE ROUND 19 REFUSE A GATE THAT HAD PASSED ─────────
# At 22:29:38Z this chain logged, on consecutive lines, a contradiction:
#     GATE VERDICT FROM .../oracle_gate_R19_def.json : ALL_PASS scope=pp1024,pp256,rag4096,val550
#                                                      out_of_scope=none
#     *** THE GATE DID NOT COVER ALL FOUR SHAPES (1 of 4) ... NO timing, NO flip.
# The REFUSAL was correct behaviour and the COUNT was wrong. The counter was
#     sed -n 's/.*scope=\([^ ]*\).*/\1/p'
# and `.*scope=` is GREEDY, so it matched the LAST occurrence of `scope=` in the line — which is
# inside `out_of_scope=none`. It therefore captured `none`, counted one element, and reported
# "1 of 4" for a gate that had just listed four. A substring of a field name collided with the field
# name itself: the same class of defect the audit script's own `NO_GEGLUV2`-not-`NO_GEGLU_V2`
# spelling exists to avoid, arriving in my own harness instead of in the flag table.
#
# THE FIX IS STRUCTURAL, NOT A BETTER REGEX. Two changes, and the first is the important one:
#   1. **The shell no longer re-derives a fact the evaluator already knew.**
#      `gate_coverage_gemma3_round19.py` computes coverage AND decides it, returning an exit code;
#      the shell reads the code and logs the evaluator's own lines verbatim. A greedy pattern cannot corrupt a verdict it is
#      never asked to parse. Re-parsing a formatted string in a second language is how one fact came
#      to have two contradictory values on adjacent log lines.
#   2. **Coverage is counted from the CELLS, not from the `scope` field.** This matters independently
#      of the regex, and the parent's question was exactly right to ask it: `gate_any.py` writes
#      `"scope": sorted(IN_SCOPE)` where `IN_SCOPE` comes from **argv[4], i.e. the REQUEST**. So the
#      scope field alone is a statement of intent, not of evidence, and an audit that trusts it can
#      be satisfied by a gate that ran nothing. What closes the hole in `gate_any.py` is that an
#      in-scope prompt with no cells on disk takes the `NOT-RUN` branch and forces `allpass = False`
#      — so `all_pass=True` already entails the cells existed. This audit now asserts that entailment
#      DIRECTLY, per prompt and per cell, instead of relying on it: it counts prompts that are not
#      out-of-scope AND carry at least one `ran=True` block, counts the blocks that ran and passed,
#      requires every determinism repeat to be bit-identical, and requires rag4096's EOS-stop to be
#      corroborated by the oracle also holding EOS at that index. Request-derived and cell-derived
#      coverage must AGREE at 4; a disagreement is a refusal, whichever way it points.
# The cost of the defect, stated for the ledger: the gate — round 19's primary deliverable — had
# already completed and banked at full scope, and the window then spent its remaining ~57 VM-minutes
# idle, because the chain exited on a false refusal and (via the CHAIN_EXIT trap defect fixed above)
# left the backstop with no fate artifact to act on, so only the deadline could stop the box.
if [[ -f "$GJ" ]]; then
  # The evaluator is its OWN FILE, not an inline heredoc, for two reasons: an inline copy could
  # drift from the one this fix was proved against on CPU, and a file can be regression-tested
  # off-box over a banked JSON at zero VM minutes (see its docstring for what it asserts and why
  # counting cells beats trusting the request-derived `scope` field).
  COV_PY="$NR/gate_coverage_gemma3_round19.py"
  if [[ ! -f "$COV_PY" ]]; then
    set_gate "NO_EVALUATOR"
    log "FATAL: no coverage evaluator at $COV_PY. The gate's coverage is then UNKNOWN, which is"
    log "      not a pass — and guessing it in shell is exactly the defect this replaces."; exit 1
  fi
  COVERAGE=$(/usr/bin/python3 "$COV_PY" "$GJ" 2>&1)
  crc=$?
  GATE_VERDICT=$(echo "$COVERAGE" | head -1)
  log "GATE VERDICT FROM $GJ : $GATE_VERDICT"
  echo "$COVERAGE" | tail -n +2 | while IFS= read -r ln; do log "    $ln"; done
  if (( crc != 0 )); then
    set_gate "COVERAGE_REFUSED"
    log "*** THE COVERAGE AUDIT REFUSED THIS GATE. Round 19's deliverable is a FULL-SCOPE"
    log "    certification over all four round-6 shapes, counted from the CELLS ON DISK and not from"
    log "    the request-derived scope field. NO timing, NO flip, no row moves."
    exit 1
  fi
  set_gate "ALL_PASS_FULL_SCOPE"
  log "FULL-SCOPE GATE ALL_PASS on $DEF over all four round-6 shapes, counted from the cells —"
  log "  timing may proceed"
else
  set_gate "NO_JSON"
  log "FATAL: no gate JSON at $GJ — the gate's verdict is UNKNOWN, which is not a pass."; exit 1
fi

# ── 6. THE LEVER MUST HAVE ARMED AT RUNTIME, asserted BEFORE any timing cell ──────────────────
# `gegluv_armed = false` means the shape gate declined and every cell so far ran the SCALAR twin — a
# null bracket wearing the lever's name. Read from the gate cells the phase above already produced,
# so this costs no VM minute. Post-flip this check matters MORE, not less: the flag is now on by
# default, so a silent decline would ship the scalar twin while the banner claimed the vector one.
ARMED=$(grep -rl "gegluv_armed" "$L19/gate_$DEF" "$L19/runs" 2>/dev/null | head -1)
if [[ -z "$ARMED" ]]; then
  log "FATAL: no cell output carries a gegluv_armed field at all. The banner did not print, so the"
  log "       lever's runtime state is UNKNOWN. Refusing to time an unproven arm."; exit 1
fi
grep -m1 "TCFLAG ALGENTA_G3_PF_GEGLU_V2" "$ARMED" 2>/dev/null | tee -a "$CW_LOGFILE"
grep -m1 "^G3 FLAGS:" "$ARMED" 2>/dev/null | tee -a "$CW_LOGFILE"
# MOJO RENDERS `Bool` CAPITALISED, AND THIS PATTERN NEVER KNEW. The banner is printed by
# `print("... gegluv_armed =", self.d_ff % _G3_GEGLUV_VEC == 0, ...)`, and Mojo renders a Bool as
# `True`/`False`, so the cells contain `gegluv_armed = True`. Every check in this campaign was
# written against a lowercase `gegluv_armed = true` and therefore NEVER MATCHED A REAL BANNER --
# round 19 measured it on the box: 10 occurrences of `gegluv_armed = True` and ZERO of the lowercase
# spelling across the 11 banked gate cells. The consequence is not a missing assertion but a
# PERMANENTLY FALSE one: `audit_tc_flags.sh` reported `gegluv_armed: false` for correctly-armed arms,
# and the runner/chain assertions FATAL on an arm that is in fact live. A safety field that is always
# false is worse than no field, because it cries wolf until a genuinely declined arm is waved through
# as the same known bug. It went unnoticed because round 18's windows died earlier for other reasons
# and its timing was launched by hand after a manual recovery, so the assertion never ran to verdict.
# Both spellings are accepted: `[Tt]rue` matches what Mojo emits today and keeps working if a future
# toolchain lowercases it, and a DECLINED arm still fails both, which is the case that must not slip.
if ! grep -qE "gegluv_armed = [Tt]rue" "$ARMED" 2>/dev/null; then
  log "FATAL: gegluv_armed is NOT true in $ARMED. The shape gate declined; the arm ran the SCALAR"
  log "       twin. No timing may be taken and no delta may be attributed to this lever."; exit 1
fi
log "GEGLUV ARMED AT RUNTIME on the shipped default (asserted from $ARMED) — timing may proceed"

# ── 7. TIMING, reserve-governed ───────────────────────────────────────────────────────────────
cells_cost_min() { # $1 = prompt name ; $2 = cell count
  local s=$CELL_S_PP256
  [[ "$1" == pp1024 ]] && s=$CELL_S_PP1024
  [[ "$1" == rag4096 ]] && s=$CELL_S_RAG
  echo $(( ($2 * s + 59) / 60 ))
}
min_n() { echo "$MEAS_RUNS_CANDIDATES" | tr ' ' '\n' | tail -1; }
bracket_cells() { # $1 = meas runs -> total cells for both slots plus the closing cell
  echo $(( 2 * (WARM_RUNS + $1) + CLOSE_RUNS ))
}
# The reservation the governor must leave behind THIS prompt: the TRT re-serve, plus the minimum
# viable bracket of every prompt still to come. Without the second term a window spends itself on
# the first prompt and "declines" the second having never checked it could afford both.
reserve_after() { # $1 = index of the current prompt in PROMPTS_ORDER (0-based)
  local i=0 r=$TRT_RESERVE_MIN n
  for spec in $PROMPTS_ORDER; do
    n=$(echo "$spec" | cut -d: -f1)
    if (( i > $1 )); then r=$(( r + $(cells_cost_min "$n" "$(bracket_cells "$(min_n)")") )); fi
    i=$((i + 1))
  done
  echo "$r"
}

set_phase "timing"
log "=== timing: reserve governor (TRT reserve ${TRT_RESERVE_MIN} min is PROTECTED) ==="
idx=0
for spec in $PROMPTS_ORDER; do
  n=$(echo "$spec" | cut -d: -f1)
  have=$(affordable_min)
  res=$(reserve_after "$idx")
  log "--- prompt $n : ${have} min affordable, ${res} min must stay reserved (TRT + later prompts) ---"
  picked=0
  for mr in $MEAS_RUNS_CANDIDATES; do
    nc=$(bracket_cells "$mr")
    cost=$(cells_cost_min "$n" "$nc")
    log "    n=$mr per slot (n_reported=$(( mr * 2 ))) -> $nc cells ~${cost} min"
    if (( have - res >= cost )); then
      log "=== timing bracket A=$DEF B=$TWIN prompt=$n MEAS_RUNS=$mr ($nc cells, n=$(( mr * 2 ))) ==="
      log "    armor protocol: $WARM_RUNS warmup + $mr measured per slot + $CLOSE_RUNS closing (A..B..A)"
      (( mr != 7 )) && log "    NOTE: NON-DEFAULT n -- the pooled n and the drift armor must be reported with it"
      # PROMPTS_ORDER AND MEAS_RUNS_CANDIDATES ARE BOTH PINNED TO THIS ONE PROMPT AND THIS ONE n.
      # DEFECT, MEASURED IN ROUND 19'S RE-SERVE WINDOW: the runner's timing stage iterates its OWN
      # `PROMPTS_ORDER` (which this chain exports as BOTH prompts) and re-prices n from its own
      # `MEAS_RUNS_CANDIDATES`, so passing only `PROMPTS="$spec"` did NOT scope it. The first
      # invocation therefore ran pp1024 AND pp256 back-to-back (11 cells each) at an n IT chose, and
      # this chain's per-prompt loop became a second, redundant governor that then "declined" a prompt
      # the runner had already completed -- which is how `prompts_completed` came to list only pp1024
      # while 11 pp256 cells with a closing cell sat on disk. Worse, had the clock allowed it, the
      # second invocation would have re-run pp1024 and overwritten its cells. Two governors over one
      # budget is not redundancy, it is a disagreement; pinning both knobs makes this chain the only
      # one that decides, and the runner's own governor then has exactly one candidate to approve.
      run_phase "timing_$n" env STAGE=timing BUILD_ARMS=0 ARM_A="$DEF" ARM_B="$TWIN" ARM_C= \
        CELLTAG="$CELLTAG" MEAS_RUNS="$mr" MEAS_RUNS_CANDIDATES="$mr" PROMPTS_ORDER="$spec" \
        WARM_RUNS="$WARM_RUNS" CLOSE_RUNS="$CLOSE_RUNS" \
        PROMPTS="$spec" bash "$RUNNER" || { log "TIMING $n returned non-zero"; }
      picked=1
      # COMPLETION IS READ FROM THE RUNNER'S OWN MARKER AND FROM A CLOSING CELL ON DISK, not from the
      # phase's exit code. A group killed mid-bracket leaves cells and no closing cell, and that state
      # must never be reported as a finished measurement -- the same reason TIMING_COMPLETE keys on
      # `TIMING DONE` rather than on rc. The closing cell is what makes the armor computable, so a
      # bracket without one does not count toward the flip licence either.
      ncell=$(ls -1 "$L19"/runs/r6*"${CELLTAG}"_*_"${n}"_r*.out 2>/dev/null | wc -l | tr -d ' ')
      nclose=$(ls -1 "$L19"/runs/r6*"${CELLTAG}"_*_"${n}"_close*.out 2>/dev/null | wc -l | tr -d ' ')
      if grep -q "CELLGROUP $n complete" "$CW_LOGFILE" 2>/dev/null && (( ncell > 0 && nclose > 0 )); then
        DONE_PROMPTS="$DONE_PROMPTS $n"
        log "PROMPT $n COMPLETE: $ncell measured cells + $nclose closing cell(s), CELLGROUP closed"
      else
        log "*** PROMPT $n INCOMPLETE: $ncell measured cells, $nclose closing cells, CELLGROUP marker"
        log "    $(grep -c "CELLGROUP $n complete" "$CW_LOGFILE" 2>/dev/null). NOT counted toward the"
        log "    flip licence -- an incomplete bracket is unpublishable, not partial progress."
      fi
      break
    fi
    log "    n=$mr DOES NOT FIT (${cost} > $(( have - res )) min free) — trying the next candidate"
  done
  if (( picked == 0 )); then
    log "SKIPPED $n: no bracket shape for it fits the remaining window once the TRT reserve and the"
    log "          later prompts are protected. Recorded as a deliberate, arithmetic-forced"
    log "          omission — NOT as a completed measurement."
  fi
  idx=$((idx + 1))
done
# ── THE FLIP LICENCE, EVALUATED MECHANICALLY RATHER THAN LEFT TO A READER OF THE LOG ────────────
# COMPLETION IS READ FROM EVIDENCE, NOT FROM BOOKKEEPING. The loop above records a prompt only if THIS
# chain invoked the runner for it, which round 19 proved is not the same question: the runner closed
# pp256's CELLGROUP inside the pp1024 invocation, so the ledger of invocations said "pp256 missing"
# while 11 pp256 cells with a closing cell sat on disk. A licence verdict that depends on who called
# whom is a verdict about the harness; the owner's rule is about the DATA. So rescan the window log for
# every CELLGROUP this session closed and union it with the invocation record, requiring a closing cell
# on disk for each -- the same two-part test, applied to the evidence rather than to the call graph.
for rp in $REQUIRED_PROMPTS; do
  case " $DONE_PROMPTS " in *" $rp "*) continue ;; esac
  nc=$(ls -1 "$L19"/runs/r6*"${CELLTAG}"_*_"${rp}"_close*.out 2>/dev/null | wc -l | tr -d ' ')
  nm=$(ls -1 "$L19"/runs/r6*"${CELLTAG}"_*_"${rp}"_r*.out 2>/dev/null | wc -l | tr -d ' ')
  if grep -q "CELLGROUP $rp complete" "$CW_LOGFILE" 2>/dev/null && (( nc > 0 && nm > 0 )); then
    DONE_PROMPTS="$DONE_PROMPTS $rp"
    log "PROMPT $rp COMPLETE BY EVIDENCE: CELLGROUP closed, $nm measured + $nc closing cell(s) on"
    log "  disk, though this chain's own invocation record did not credit it (see the defect note"
    log "  above). Counted, because the licence is about the data."
  fi
done
missing=""
for rp in $REQUIRED_PROMPTS; do
  case " $DONE_PROMPTS " in *" $rp "*) ;; *) missing="$missing $rp" ;; esac
done
if [[ -z "$missing" ]]; then
  log "REQUIRED PROMPTS COMPLETE:${DONE_PROMPTS} -- pending the same-session TRT re-serve below"
else
  log "*** FLIP NOT LICENSED: required prompt(s) NOT completed:${missing} (completed:${DONE_PROMPTS:- none})"
  log "    The owner's rule is that the default-flip PR merges ONLY when pp1024 AND pp256 cells plus"
  log "    their same-session TRT are in hand. A flipped default with an un-re-measured published row is"
  log "    a docs-integrity defect, so this is a REFUSAL and not a partial success. The TRT re-serve"
  log "    still runs if it is affordable, because a same-session comparator banked against the"
  log "    completed prompt is reusable evidence and costs ~3 min; but no row moves and no flip lands."
fi

if grep -q "TIMING DONE" "$CW_LOGFILE" 2>/dev/null; then
  TIMING_COMPLETE=yes
  log "timing_complete=yes — a bracket group closed (TIMING DONE present in the window log)"
else
  log "timing_complete=NO — no TIMING DONE marker; any cells on disk are an INCOMPLETE bracket"
fi

# ── 8. SAME-SESSION TRT-LLM RE-SERVE: WITHOUT IT NO ROW IS PUBLISHABLE ────────────────────────
# `lv3_trtllm.sh` serves all THREE cells (pp256, pp1024, rag4096) from one server startup, so
# rag4096's comparator comes for free once the server is up. That matters because round 18 could not
# re-serve at all and had to reuse round 13's pair for the rag row, making its 1.1653x headline
# CROSS-SESSION; this window can retire that.
set_phase "trtllm"
if (( $(affordable_min) < 4 )); then
  log "SKIP TRT re-serve: only $(affordable_min) min affordable"
  log "CONSEQUENCE: no same-session comparator, so NO published row may move on this window's cells"
else
  run_phase trtllm env GPU="$GPU" bash "$L3/lv3_trtllm.sh" || log "RESERVE_WARN: the re-serve returned non-zero"
  # COPY ONLY JSONs NEWER THAN THIS CHAIN'S OWN START, and say so. `~/lever3/runs/` accumulates every
  # previous window's re-serve -- round 19 found round 14's files there, dated Sep 19 07:02, i.e. 17
  # hours stale -- and an unconditional `cp` followed by `ls trtllm_*.json` would have set TRT_DONE=yes
  # on those and handed the summariser a comparator from another session labelled as this one. The
  # summariser does print the mtime in its comparator label, so the laundering would have been
  # VISIBLE rather than silent; this makes it impossible instead.
  copied=0
  for c in pp256 pp1024 rag4096; do
    src="$L3/runs/trtllm_$c.json"
    [[ -f "$src" ]] || { log "  no trtllm_$c.json from the re-serve"; continue; }
    if [[ "$src" -nt "$CHAIN_START_MARK" ]]; then
      cp -f "$src" "$L19/runs/" && copied=$((copied + 1))
    else
      log "  REFUSING to copy trtllm_$c.json: mtime $(date -u -r "$src" +%FT%TZ 2>/dev/null) is OLDER"
      log "    than this chain's start -- it is a previous window's re-serve, not this session's."
    fi
  done
  log "  copied $copied of 3 fresh same-session TRT JSONs into $L19/runs"
  if (( copied >= 2 )); then
    TRT_DONE=yes
    log "TRT re-serve JSONs copied into $L19/runs — the summariser will read them as SAME-SESSION"
  else
    log "NO TRT JSON in $L19/runs — every ratio this window produces is CROSS-SESSION and unpublishable"
  fi
  # Reproduction check against EVERY stored comparator column, and it dumps the raw JSON on a parse
  # failure rather than reporting "could not parse". chain14's inline version referenced an
  # undefined `txt` and printed `could not parse a median` for all three cells; the numbers were
  # sound and only the redundant parser was broken, but a silent parse failure looks identical to a
  # missing re-serve, so this one fails LOUDLY and keeps the raw bytes in the single log.
  /usr/bin/python3 - "$L19/runs" <<'PY' | tee -a "$CW_LOGFILE"
import json, os, statistics, sys
from datetime import datetime, timezone
RUNS = sys.argv[1]
# every comparator column this campaign has banked, so a drift is visible against all of them
COLS = {
    "stored (round 5 same-session)": {"pp256": 41.520, "pp1024": 110.782, "rag4096": 426.766},
    "round 6 same-session":          {"pp256": 40.728, "pp1024": 110.744, "rag4096": 426.339},
    "round 13 same-session":         {"pp256": 41.292, "pp1024": 110.713, "rag4096": 429.400},
    "round 14 same-session":         {"pp256": 41.329, "pp1024": 110.968, "rag4096": 428.212},
}
print("--- TRT-LLM 1.2.1 SAME-SESSION re-serve, reproduction check vs every stored column ---")
for cell in ("pp256", "pp1024", "rag4096"):
    p = os.path.join(RUNS, "trtllm_%s.json" % cell)
    if not os.path.exists(p):
        print("  %-8s NO JSON at %s" % (cell, p)); continue
    val, raw = None, ""
    try:
        raw = open(p, errors="replace").read()
        d = json.loads(raw)
        blk = d.get("ttft_ms") or {}
        val = blk.get("median")
        if val is None and isinstance(blk.get("runs"), list) and blk["runs"]:
            val = statistics.median([float(x) for x in blk["runs"]])
    except Exception as e:
        print("  %-8s PARSE FAILED (%s) — RAW CONTENT FOLLOWS so the value is never lost:" % (cell, e))
        for ln in raw.strip().splitlines()[-3:]:
            print("           raw| %s" % ln[:400])
        continue
    if val is None:
        print("  %-8s no ttft_ms median — RAW CONTENT FOLLOWS:" % cell)
        for ln in raw.strip().splitlines()[-3:]:
            print("           raw| %s" % ln[:400])
        continue
    val = float(val)
    mt = datetime.fromtimestamp(os.path.getmtime(p), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = "  %-8s re-served %9.3f ms (json mtime %s)" % (cell, val, mt)
    worst = 0.0
    for name, col in COLS.items():
        ref = col.get(cell)
        if not ref:
            continue
        dp = 100.0 * (val - ref) / ref
        worst = max(worst, abs(dp))
        line += "\n             vs %-28s %9.3f = %+7.3f%% %s" % (
            name, ref, dp, "REPRODUCES" if abs(dp) <= 1.0 else "CROSS-SESSION")
    print(line)
    print("             worst |delta| vs any stored column = %.3f%% => %s"
          % (worst, "within 1%, same-session comparator is sound"
             if worst <= 1.0 else "EXCEEDS 1% — label the ratio CROSS-SESSION and say why"))
PY
fi

# ── 8b. THE rag4096 COMPARATOR BASIS, DECIDED AND RECORDED RATHER THAN ASSUMED ─────────────────
# `lv3_trtllm.sh` serves all three cells from ONE startup, so a fresh rag4096 comparator costs nothing
# extra once the server is up. Round 18 could not re-serve at all and had to reuse round 13's
# same-session pair (429.400 ms) for its rag row, which made its 1.1653x headline CROSS-SESSION. The
# owner's rule for this window: prefer the fresh same-session number UNLESS a single confirmation serve
# drifts >1% from the basis round 18 used, in which case reuse round 18's pair and SAY SO. Either way
# the choice is written down, because a ratio whose comparator basis is unstated is not auditable.
if [[ "$TRT_DONE" == "yes" && -f "$L19/runs/trtllm_rag4096.json" ]]; then
  # Its own file, NOT an inline heredoc: a heredoc inside `$( )` is unsafe on macOS bash 3.2 (the
  # owner's standing rule for this campaign), and an inline copy cannot be regression-tested off-box.
  RAG_TRT_BASIS=$(/usr/bin/python3 "$NR/rag_trt_basis_r19.py" "$L19/runs/trtllm_rag4096.json" 2>&1)
  log "rag4096 TRT COMPARATOR BASIS: $RAG_TRT_BASIS"
elif [[ "$TRT_DONE" == "yes" ]]; then
  RAG_TRT_BASIS="NO rag4096 JSON despite a completed re-serve -> reuse round-18 pair (round 13 same-session 429.400 ms)"
  log "rag4096 TRT COMPARATOR BASIS: $RAG_TRT_BASIS"
else
  RAG_TRT_BASIS="re-serve did not run -> reuse round-18 pair (round 13 same-session 429.400 ms); NO pp256/pp1024 row may move"
  log "rag4096 TRT COMPARATOR BASIS: $RAG_TRT_BASIS"
fi
# The licence also requires the comparator, so fold that in here rather than in two places.
if [[ -z "$missing" && "$TRT_DONE" != "yes" ]]; then
  log "*** FLIP NOT LICENSED: both required prompts completed but there is NO same-session comparator,"
  log "    so no ratio is publishable and no row may move."
fi
if [[ -z "$missing" && "$TRT_DONE" == "yes" ]]; then
  FLIP_LICENSED=yes
  log "FLIP_LICENSED=yes -- pp1024 AND pp256 cells with closing armor, a same-session TRT comparator,"
  log "  and the banked full-scope gate are all in hand. The owner's merge precondition is met."
else
  log "FLIP_LICENSED=no -- see the refusal(s) above. PR #1072 must stay unmerged."
fi

# ── 9. SUMMARIES: medians, IQR, the closing-cell drift armor, and the ratios ──────────────────
# The repo's OWN summariser, not a fresh parser: round 14 lost its publishable rows to a summariser
# glob that excluded `close1`, and the fix landed there (`closing_bracket_median` +
# `bracket_drift_pct`, with "ARMOR NOT COMPUTABLE — NO PUBLISH" when a closing cell is missing).
# Re-using it is what makes that fix apply to this window instead of being re-earned.
set_phase "summary"
SUM=$NR/summarize_gemma3_round6.py
if [[ -f "$SUM" ]]; then
  run_phase summary env MEAS="$L19" /usr/bin/python3 "$SUM" "$DEF" "$TWIN" || log "SUMMARY_WARN"
else
  log "no summariser at $SUM — cells are banked in $L19/runs and can be summarised off-box"
fi
# The armor verdict, stated separately and loudly, because it is the gate on publication and it is
# exactly the number round 14 failed to extract. Opening median vs closing cell, per prompt.
/usr/bin/python3 - "$L19/runs" "$DEF" "$TWIN" <<'PY' | tee -a "$CW_LOGFILE"
import os, re, statistics, sys
RUNS, DEF, TWIN = sys.argv[1], sys.argv[2], sys.argv[3]
def ttft(path):
    try:
        for ln in open(path, errors="replace"):
            m = re.search(r"(?:ttft|TTFT)[^\d]*([0-9]+\.?[0-9]*)", ln)
            if m:
                return float(m.group(1))
    except Exception:
        pass
    return None
print("--- DRIFT ARMOR from the closing cells (open median -> close), per prompt ---")
for prompt in ("pp1024", "pp256", "rag4096"):
    meas, close = [], []
    files = sorted(os.listdir(RUNS)) if os.path.isdir(RUNS) else []
    for f in files:
        if not f.endswith(".out"):
            continue
        m = re.match(r"r6.*_(%s|%s)_%s_(warm\d+|r\d+|close\d+)\.out" % (DEF, TWIN, prompt), f)
        if not m:
            continue
        v = ttft(os.path.join(RUNS, f))
        if v is None:
            continue
        kind = m.group(3)
        if kind.startswith("r"):
            meas.append(v)          # a measured sample of the ONE configuration both slots share
        elif kind.startswith("close"):
            close.append(v)         # the closing cell: what makes the group A..B..A
        # warmup cells are deliberately dropped from both: they are not samples
    if not meas:
        continue
    med = statistics.median(meas)
    if not close:
        print("  %-8s n=%d median %.3f ms -- ARMOR NOT COMPUTABLE, NO PUBLISH (no closing cell)"
              % (prompt, len(meas), med))
        continue
    cmed = statistics.median(close)
    d = cmed - med
    print("  %-8s n=%d median %.3f ms | closing n=%d median %.3f ms | armor %+.3f ms (%+.3f%%)"
          % (prompt, len(meas), med, len(close), cmed, d, 100.0 * d / med if med else 0.0))
PY

# ── 10. BITIDENT (free: it reads cells the phases above already produced) ─────────────────────
# DEF vs TWIN. This is NOT the lever's bit-identity claim — round 18 proved that (8/8 BITIDENT,
# 0 BITDIFF) and the full-scope oracle gate above re-proves the default against the fp32 oracle at
# all four shapes. What this checks is the TWIN MECHANISM: that labelling one binary twice really
# did produce one configuration's samples, which is what makes pooling the two slots' cells sound.
run_phase bitident env STAGE=bitident BUILD_ARMS=0 ARM_A="$DEF" ARM_B="$TWIN" bash "$RUNNER" || {
  log "BITIDENT: not 100% bit-identical between $DEF and $TWIN — the twin mechanism is suspect and";
  log "          pooling the two slots' cells is NOT licensed. Report n per slot separately."; }

log "CHAIN19 COMPLETE mins_left=$(mins_left)"
log "The caller issues the stop; this chain does not, because the cap is measured from"
log "lastStartTimestamp which only the caller has."
set_phase "done"
exit 0
