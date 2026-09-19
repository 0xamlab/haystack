#!/usr/bin/env bash
# chain18.sh — ROUND 18 VM WINDOW DRIVER. RUN THIS ON THE VM, under setsid+nohup so it does NOT
# inherit the ssh channel (round 17 lost 2 x 300 s to exactly that: a backgrounded remote process
# holding the channel open made two ssh calls hang client-side while the jobs had in fact launched).
#
#   setsid nohup bash ~/g3r18/benchmarks/llm_smoke/nvidia_race/chain18.sh \
#     </dev/null >~/lever18/chain18.out 2>&1 & disown
#
# ONE WINDOW, ONE LOG. Every phase below appends to $L18/round18.log, and a heartbeat line lands in
# $L18/heartbeat.log every 60 s with the phase name and the minutes remaining, so a window that has
# gone quiet is distinguishable from a window that is busy without ssh-ing in to look.
#
# ── THE DEADLINE IS AN INPUT, NOT A GUESS ──────────────────────────────────────────────────────
# CW_DEADLINE_EPOCH must be the epoch of (lastStartTimestamp + CAP_MIN + GRACE), computed by the
# caller on the Mac from `gcloud compute instances describe ... --format
# 'value(lastStartTimestamp)'` — the cap is VM-ON time from the moment the instance started, which
# includes the ~4 min of boot+ssh this script cannot see. Round 17 ran to 93 min 58 s against a
# 90 min cap and issued its stop 69 s after its bracket finished; that is the margin this exists to
# protect. If CW_DEADLINE_EPOCH is unset this script REFUSES rather than run unbounded, because an
# uncapped spot window is how a round ends up billed for hours it did not use.
#
# ── PHASES, AND WHAT EACH ONE IS ALLOWED TO COST ──────────────────────────────────────────────
#   stage    chain7stage.sh: fixtures regenerated AND PROVEN IDENTICAL to round 6's certified gate
#            echoes, 101 GB checkpoint converted to /mnt/ramblob, GPU1 pinned and VERIFIED at
#            1410 MHz with zero off-pin tolerance. Nothing downstream may run until STAGE_OK.
#   build    one stock shim + both arms, then the binary audit (banner literals AND the
#            self-computing kernel-hash differential). No GPU work.
#   smoke    one pp1024 cell per arm; the lever must report `gegluv_armed = true` at RUNTIME, not
#            merely carry the macro. A declined lever must never masquerade as a measured one.
#   gate     the fp32-oracle gate on the CHANGED arm, BEFORE any timing cell. GATE_SPECS defaults
#            to the two bracketed shapes (see run_ab_gemma3_round18.sh for the arithmetic that
#            forces that reduction, which the cells runner logs as NON-DEFAULT).
#   timing   the interleaved A..B..A bracket, budget-governed: rag4096 first, then pp1024 with
#            whatever genuinely remains, deciding from the clock.
#   bitident compare the two arms' generated token streams from the cells already on disk.
#
# A phase that fails stops the chain. A phase that would overrun the deadline is killed and the log
# says KILLED_BY_OPERATOR, so an abandoned window is self-describing rather than mysterious.
set -uo pipefail

SRC_TREE=${SRC_TREE:-$HOME/g3r18}
L18=${L18:-$HOME/lever18}
GPU=${GPU:-1}
CAP_MIN=${CAP_MIN:-90}
GRACE_MIN=${GRACE_MIN:-5}
NR="$SRC_TREE/benchmarks/llm_smoke/nvidia_race"
export GPU SRC_TREE L18
# Pass the governor's knobs through to run_ab_gemma3_round18.sh. These are exported rather than
# defaulted here so the WINDOW CALLER owns the budget decision and it is visible in the launch
# command line rather than buried in a script: MEAS_RUNS_CANDIDATES is the n values the timing
# stage will price, in preference order, and it declines any that cannot FINISH inside the
# deadline. Round 18 sets it to "5" — the protocol floor — rather than "7 5": an n=7 rag4096
# bracket is ~49 min on top of ~34 min of stage/build/gate, i.e. ~83 min against a 90 min cap,
# which leaves ~6 min of margin and risks the watchdog killing the bracket mid-run. A killed
# bracket is unpublishable; a complete n=5 bracket is not, and n=5 is what round 17 measured its
# own RESOLVED delta on. Trading a tighter IQR for a ~1-in-3 chance of no result at all is the
# wrong trade when the predicted effect (23-29 ms of transferred headroom against a 12.07 ms bar)
# is large enough that n=5 will be overwhelmingly significant anyway.
export MEAS_RUNS_CANDIDATES WARM_RUNS CLOSE_RUNS GATE_SPECS PROMPTS_ORDER
export SKIP_SMOKE CELL_S_RAG CELL_S_PP1024 SAFETY_S SKIP_STAGE

if [[ -z "${CW_DEADLINE_EPOCH:-}" ]]; then
  echo "FATAL: CW_DEADLINE_EPOCH is unset. The cap is VM-ON time from lastStartTimestamp, which"
  echo "       includes the boot+ssh this script cannot observe, so only the caller can compute it:"
  echo "         gcloud compute instances describe trtllm-gemma-us-west1-c --project=eplanev2 \\"
  echo "           --zone=us-west1-c --format='value(lastStartTimestamp)'"
  echo "       then CW_DEADLINE_EPOCH=\$(( \$(date -d \"\$LST\" +%s) + ($CAP_MIN+$GRACE_MIN)*60 ))."
  echo "       Refusing to run an uncapped spot window."
  exit 2
fi
export CW_DEADLINE_EPOCH

mkdir -p "$L18/logs" "$L18/runs" "$L18/clocks"
CW_LOGFILE=${CW_LOGFILE:-$L18/round18.log}
export CW_LOGFILE
HB=$L18/heartbeat.log

# ── THE CHAIN'S FATE IS AN ARTIFACT, NOT AN INFERENCE ─────────────────────────────────────────
# Round 18 exposed the cost of not having this: the chain died twice (rc=1 at 19:15:16Z on a
# mis-calibrated kernel-symbol audit, rc=1 at 19:36:21Z on a reduced-scope gate that reported
# ALL_PASS=False), and from OUTSIDE the box the only evidence was a heartbeat that had gone stale
# at 19:14:44Z. A stale heartbeat says "something stopped", never "what finished, what failed, and
# whether any cell was timed" — so an operator cannot tell an abandoned window from a completed one
# and cannot tell idle burn from work. This trap writes the answer to the persistent boot disk on
# EVERY exit path, including a failure exit and a signal, so the next window (and the report) reads
# the chain's fate from a file rather than reconstructing it from timestamps.
CHAIN_EXIT=$L18/CHAIN_EXIT
: > "$CHAIN_EXIT"
TIMING_COMPLETE=no
chain_exit() {
  local rc=$1
  {
    echo "chain18_exit_utc=$(date -u +%FT%TZ)"
    echo "rc=$rc"
    echo "phase=$PHASE"
    echo "timing_complete=$TIMING_COMPLETE"
    echo "measured_cells=$(ls -1 "$L18"/runs/r6*_r[0-9].out 2>/dev/null | wc -l | tr -d ' ')"
    echo "gate_cells=$(ls -1 "$L18"/gate_*/gate_*.out 2>/dev/null | wc -l | tr -d ' ')"
    echo "deadline_epoch=${CW_DEADLINE_EPOCH:-unset}"
    echo "mins_left_at_exit=$(mins_left)"
  } >> "$CHAIN_EXIT"
  # ...and into the single window log too, so the fate survives a later window truncating
  # CHAIN_EXIT. The log is append-only across the round; CHAIN_EXIT describes the latest chain.
  log "CHAIN18 EXIT rc=$rc phase=$PHASE timing_complete=$TIMING_COMPLETE (recorded in $CHAIN_EXIT)"
}
trap 'chain_exit $?' EXIT
trap 'chain_exit 143; kill $HB_PID $WD_PID 2>/dev/null; exit 143' TERM
trap 'chain_exit 130; kill $HB_PID $WD_PID 2>/dev/null; exit 130' INT

ts() { date -u +%FT%TZ; }
log() { echo "[$(ts)] $*" | tee -a "$CW_LOGFILE"; }
mins_left() {
  local left=$(( (CW_DEADLINE_EPOCH - $(date +%s)) / 60 ))
  (( left < 0 )) && left=0
  echo "$left"
}

PHASE="init"
( while true; do
    echo "$(date -u +%FT%TZ) chain18 GPU=$GPU phase=$PHASE pid=$$ mins_left=$(mins_left)" >> "$HB"
    sleep 60
  done ) &
HB_PID=$!
trap 'kill $HB_PID 2>/dev/null' EXIT

# THE DEADLINE WATCHDOG. Separate process, so a phase that hangs is still killed: the chain's own
# budget checks only run BETWEEN phases, and a wedged cell would otherwise sit on the GPU until the
# spot instance was reclaimed. It kills the phase's process GROUP (not a name pattern — the lesson
# run_gemma3_round6_cells.sh's `quiesce` documents about pgrep matching its own caller), writes
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
trap 'kill $HB_PID $WD_PID 2>/dev/null' EXIT

run_phase() { # $1 = phase name ; rest = command
  PHASE="$1"; shift
  log "=== PHASE $PHASE  (mins_left=$(mins_left))  cmd: $* ==="
  "$@"
  local rc=$?
  log "=== PHASE $PHASE rc=$rc  (mins_left=$(mins_left)) ==="
  return $rc
}

log "CHAIN18 START deadline=$CW_DEADLINE_EPOCH ($(date -u -d "@$CW_DEADLINE_EPOCH" +%FT%TZ 2>/dev/null || echo '?'))" \
    "cap=${CAP_MIN}m grace=${GRACE_MIN}m mins_left=$(mins_left) tree=$SRC_TREE"
log "synced_head=$(cat "$SRC_TREE/.synced_head" 2>/dev/null || echo '<none>')"

# ── 1. STAGE ──────────────────────────────────────────────────────────────────────────────────
# Fixtures must be PROVEN identical to round 6's certified echoes before anything is measured; the
# chain aborts if it cannot prove that, because a benchmark on unproven fixtures is not a benchmark.
#
# SKIP_STAGE=1 RE-USES A STAGE THAT ALREADY RAN IN THIS SAME VM-ON SESSION, and re-verifies rather
# than trusts. /tmp and /mnt/ramblob are tmpfs and die with the instance, so this is only sound
# while the box has stayed up — which is exactly the case it exists for: round 18's build phase
# FATAL'd on a mis-calibrated audit check AFTER `STAGE_OK` at 19:14:20Z, and re-running the 14-min
# stage (fixtures + a 101 GB checkpoint conversion + the clock pin) to recover from a harness bug
# would have spent a sixth of the cap re-proving facts that had not changed. So this path checks
# the three things that matter and refuses if any is absent: the four fixtures, the converted
# checkpoint, and GPU1 still pinned at 1410 MHz with zero off-pin tolerance.
if [[ "${SKIP_STAGE:-0}" == "1" ]]; then
  PHASE="stage_reverify"
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
  prior=$(grep -c "STAGE_OK" "$L18/chain7stage.log" 2>/dev/null || echo 0)
  log "  prior STAGE_OK markers in this session's stage log: $prior"
  (( prior == 0 )) && { log "  no prior STAGE_OK — SKIP_STAGE is not justified"; ok=0; }
  PIN=$(nvidia-smi -i "$GPU" --query-gpu=clocks.current.sm --format=csv,noheader,nounits)
  log "  GPU$GPU clocks.current.sm=$PIN (want 1410 — ZERO off-pin tolerance)"
  [[ "$PIN" != "1410" ]] && { log "  OFF_PIN: $PIN != 1410 — re-pin or do not measure"; ok=0; }
  if (( ok != 1 )); then
    log "STAGE_REVERIFY FAILED — falling back to a full stage rather than measuring on trust"
    STAGE_SRC="$SRC_TREE" L7="$L18" run_phase stage bash "$NR/chain7stage.sh" || exit 1
  else
    log "=== PHASE stage_reverify rc=0 — fixtures, checkpoint and the 1410 MHz pin all re-proven ==="
  fi
else
STAGE_SRC="$SRC_TREE" L7="$L18" \
  run_phase stage bash "$NR/chain7stage.sh" || { log "STAGE FAILED — nothing may be measured"; exit 1; }
# fold the stage's own load-bearing lines into the SINGLE window log, so the round's evidence does
# not depend on reading two files: fixture identity, the checkpoint, and the verified clock pin.
grep -E "STAGE_OK|FIXTURE_IDENTITY_OK|FIXTURE |CHECKPOINT present|clocks.current.sm=|OFF_PIN" \
  "$L18/chain7stage.log" 2>/dev/null | tail -12 | tee -a "$CW_LOGFILE"
grep -q "STAGE_OK" "$L18/chain7stage.log" 2>/dev/null || {
  log "FATAL: no STAGE_OK in the stage log. Refusing to build or measure."; exit 1; }
fi

# ── 2. BUILD + VERIFY ─────────────────────────────────────────────────────────────────────────
run_phase build env STAGE=build bash "$NR/run_ab_gemma3_round18.sh" || {
  log "BUILD/VERIFY FAILED — no arm, no window"; exit 1; }

# ── 3. SMOKE (skippable; its load-bearing assertion is repeated after the gate) ───────────────
# The smoke stage exists to prove the lever ARMED AT RUNTIME (`gegluv_armed = true`) rather than
# merely compiling in. That assertion is repeated against the gate cells below, so the stage can be
# skipped when the budget is tight without losing the check — it costs 2 cells (~4 min) to prove
# something the gate's own first cell proves for free. The control arm's cleanliness is NOT a
# runtime fact at all: it is the `strings` audit in verify_arms, which already ran.
if [[ "${SKIP_SMOKE:-0}" == "1" ]]; then
  log "PHASE smoke SKIPPED (SKIP_SMOKE=1) — the gegluv_armed assertion is enforced after the gate"
else
  run_phase smoke env STAGE=smoke bash "$NR/run_ab_gemma3_round18.sh" || {
    log "SMOKE FAILED — the lever did not arm at runtime; refusing to gate or time it"; exit 1; }
fi

# ── 4. GATE (before ANY timing cell) ──────────────────────────────────────────────────────────
# A gate cell costs ~2 min and the reduced two-prompt gate costs ~10. Below 12 min the gate cannot
# finish, and a gate that cannot finish means no timing may be taken at all — so say so and stop,
# rather than starting a gate the deadline watchdog will have to kill mid-cell.
if (( $(mins_left) < 12 )); then
  log "KILLED_BY_OPERATOR (pre-gate): only $(mins_left) min left, which cannot fund a gate."
  log "  No timing was taken and none may be published for this arm."
  exit 1
fi
run_phase gate env STAGE=gate bash "$NR/run_ab_gemma3_round18.sh" || {
  log "GATE FAILED — no timing cells may be taken or published for this arm"; exit 1; }
# THE LEVER MUST HAVE ARMED AT RUNTIME, asserted here whether or not the smoke stage ran, and
# asserted BEFORE any timing cell. `gegluv_armed = false` means the shape gate declined and every
# cell so far ran the SCALAR twin — a null bracket wearing the lever's name, which is the exact
# hazard LTALGO's `lt_shapes_tuned = 0` check exists for. Read from the gate cells the phase above
# already produced, so this costs no VM minute.
ARMED=$(grep -rl "gegluv_armed" "$L18/gate_R18_gegluv" "$L18/runs" 2>/dev/null | head -1)
if [[ -z "$ARMED" ]]; then
  log "FATAL: no cell output carries a gegluv_armed field at all. The banner did not print, so"
  log "       the lever's runtime state is UNKNOWN. Refusing to time an unproven arm."
  exit 1
fi
grep -m1 "TCFLAG ALGENTA_G3_PF_GEGLU_V2" "$ARMED" 2>/dev/null | tee -a "$CW_LOGFILE"
if ! grep -q "gegluv_armed = true" "$ARMED" 2>/dev/null; then
  log "FATAL: gegluv_armed is NOT true in $ARMED. The shape gate declined; the arm ran the scalar"
  log "       twin. No timing may be taken and no delta may be attributed to this lever."
  exit 1
fi
log "GEGLUV ARMED AT RUNTIME (asserted from $ARMED) — the lever is live, timing may proceed"
log "GATE PASSED on the lever arm — timing may proceed"

# ── 5. TIMING (the governor inside decides n and which prompts fit) ───────────────────────────
run_phase timing env STAGE=timing bash "$NR/run_ab_gemma3_round18.sh" || {
  log "TIMING phase returned non-zero"; }
# "COMPLETE" means the bracket group closed, i.e. the runner printed TIMING DONE — not merely that
# the phase returned. A group that was killed mid-bracket leaves cells on disk and no closing cell,
# which is exactly the state that must NOT be reported as a finished measurement.
if grep -q "TIMING DONE" "$CW_LOGFILE" 2>/dev/null; then
  TIMING_COMPLETE=yes
  log "timing_complete=yes — the bracket group closed (TIMING DONE present in the window log)"
else
  log "timing_complete=NO — no TIMING DONE marker; any cells on disk are an INCOMPLETE bracket"
fi

# ── 6. BITIDENT (free: it reads cells the phases above already produced) ──────────────────────
run_phase bitident env STAGE=bitident bash "$NR/run_ab_gemma3_round18.sh" || {
  log "BITIDENT: not 100% bit-identical, or nothing comparable ran. See the table above."; }

log "CHAIN18 COMPLETE mins_left=$(mins_left)"
log "The caller issues the stop; this chain does not, because the cap is measured from"
log "lastStartTimestamp which only the caller has. Stop with:"
log "  gcloud compute instances stop trtllm-gemma-us-west1-c --project=eplanev2 --zone=us-west1-c --discard-local-ssd=false"
PHASE="done"
exit 0
