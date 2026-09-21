#!/usr/bin/env bash
# verify_cuda_release_battery.sh — RUN THIS ON THE RACE VM, under setsid+nohup so it does NOT inherit
# the ssh channel. Launched by scripts/release/verify_cuda_release.sh, which owns the cap and the stop.
#
#   setsid nohup bash ~/cuda_rel_verify/scripts/release/verify_cuda_release_battery.sh \
#     </dev/null >~/cuda_rel_verify_work/battery.out 2>&1 & disown
#
# ── WHAT THIS BATTERY IS ──────────────────────────────────────────────────────────────────────
# The release-verify leg the CUDA lane has never had: the campaign's standing oracle gates, run
# against the binaries that came OUT OF THE WHEEL a user would install, instead of against a race arm
# compiled on the box. Same gates, same evaluator, same clock discipline, same fixtures — different
# artifact under test, and that difference is the entire point (see wheel_gate_cells.py's header for
# why certifying a race arm says nothing about the shipped runtime).
#
# ── PHASES ────────────────────────────────────────────────────────────────────────────────────
#   unpack    unzip the wheel with the STDLIB (no pip, no network: the box has no github egress and
#             pypi egress is unproven), chmod the workers, and census every embedded binary by hash.
#   load      prove the wheel's worker LOADS and answers its ready handshake on this box, and record
#             the dynamic-link facts (`ldd`, whether libcuda resolves) that a GPU-less host would hit.
#   stage     chain7stage.sh, reused verbatim: fixtures regenerated AND PROVEN IDENTICAL to round 6's
#             certified echoes, the checkpoint converted, GPU pinned and VERIFIED at 1410 MHz with
#             zero off-pin tolerance. Nothing may be measured until STAGE_OK.
#   cells     one gate cell at a time under cell_watchdog's cw_cell, so every cell carries its own
#             clocks_before/clocks_after/offpin sample — the per-cell discipline the verdict reports.
#   gate      gate_any.py (reused verbatim) then gate_coverage_gemma3_round19.py (reused verbatim):
#             ALL_PASS at FULL SCOPE and COVERAGE_OK, counted from the cells and not from the request.
#   conform   scripts/algenta_conform.py --backend cuda: the typed support verdict for this checkpoint.
#   verdict   emit cuda-release-verdict.json, or emit NOTHING and fail.
#
# A phase that fails stops the battery. No verdict is written on any failure, any clock/offpin
# deviation, or any wheel-hash mismatch — the controller re-checks all of that before it accepts the
# file, so a half-passed window cannot produce a publishable artifact.
#
# ── THE BUDGET, FROM MEASURED COSTS AND NOT FROM HOPE ─────────────────────────────────────────
# Costs below are the campaign's MEASURED per-cell figures (round 14: 22 pp256/pp1024 cells in ~44
# min, ~120 s each; round 18: a 3-cell pp1024 gate at ~142 s/cell; round 19: an 11-cell full-scope
# gate in ~23.5 min), against the default 60 min cap + 5 min grace less the 180 s stop margin:
#   boot + sshd probe + sync + launch                        ~5 min  ->   5
#   unpack + census + load probe                             ~1 min  ->   6
#   stage: fixtures proven identical + 101 GB convert + pin   ~7 min  ->  13
#   11 gate cells through the SHIPPED path at ~120 s/cell    ~22 min  ->  35
#   gate + coverage evaluation + conformance CLI              ~2 min  ->  37
#   verdict emission + artifact collection                    ~1 min  ->  38
# **~38 min against a ~62 min usable horizon: ~24 min of contingency.** The shipped path has never
# been timed on this box, so treat the per-cell figure as INHERITED, not measured: if a cell turns
# out to cost more, the deadline watchdog kills the phase and the window ends with NO VERDICT rather
# than a partial one. A killed battery is unpublishable; a declined one merely is not.
set -uo pipefail

SRC_TREE=${SRC_TREE:-$HOME/cuda_rel_verify}
WORK=${WORK:-$HOME/cuda_rel_verify_work}
WHEEL_PATH=${WHEEL_PATH:-$HOME/cuda_rel_verify.whl}
EXPECT_WHEEL_SHA=${EXPECT_WHEEL_SHA:-}
EXPECT_WHEEL_BYTES=${EXPECT_WHEEL_BYTES:-}
GPU=${GPU:-1}
CAP_MIN=${CAP_MIN:-60}
GRACE_MIN=${GRACE_MIN:-5}
SAFETY_S=${SAFETY_S:-180}
CKPT=${CKPT:-/mnt/ramblob/g3conv27b}
HF_CKPT=${HF_CKPT:-$HOME/gemma3-27b}
GATE_PROMPTS=${GATE_PROMPTS:-pp256,pp1024,val550,rag4096}
VM_NAME=${VM_NAME:-trtllm-gemma-us-west1-c}
VM_ZONE=${VM_ZONE:-us-west1-c}
VM_PROJECT=${VM_PROJECT:-eplanev2}
VM_LAST_START=${VM_LAST_START:-unknown}
# The four round-6 fixture shapes. Same specs the campaign's own runner defaults to, named here
# rather than inherited so the scope this window certified is in this window's log.
GATE_SPECS=${GATE_SPECS:-"pp256:/tmp/g3pp256/prompt_0000.txt pp1024:/tmp/g3pp1024/prompt_0000.txt val550:/tmp/g3race500/prompt_0000.txt rag4096:/tmp/g3rag/rag4096.txt"}
PY314=${PY314:-}
# ── ENGINE-SHAPED KNOBS, ALL FORWARDED BY THE CONTROLLER ───────────────────────────────────────
# The defaults above are the gemma3-27b campaign's. Every one of these is an ENGINE or SKU fact that
# a different bundled engine changes, and before they were knobs at all the battery could only ever
# certify gemma: the oracle directory and the eos ids were hardcoded inside gate_any.py, the
# certified-shape list inside gate_coverage_gemma3_round19.py, and the clock pin inside
# cell_watchdog.sh. They are read here and passed on explicitly, because an env var that has to cross
# a process boundary must be NAMED at that boundary -- the rule this battery's own launch comment
# records round 18 paying for.
ORACLE_DIR=${ORACLE_DIR:-}
ORACLE_LABEL=${ORACLE_LABEL:-}
EOS_TOKENS=${EOS_TOKENS:-106,1}
GATE_COVERAGE_PROMPTS=${GATE_COVERAGE_PROMPTS:-$GATE_PROMPTS}
GATE_COVERAGE_SINGLE_RUN=${GATE_COVERAGE_SINGLE_RUN:-rag4096}
CW_PIN_MHZ=${CW_PIN_MHZ:-1410}
STAGE_SCRIPT=${STAGE_SCRIPT:-chain7stage.sh}
# A stage that does not emit FIXTURE_IDENTITY_OK must not be demanded of. The gemma stage proves its
# fixtures identical to round 6's certified echoes; another engine's lane has no such banked echoes,
# and grepping for a marker the stage never writes is a guaranteed refusal dressed up as a gate.
STAGE_NEEDS_FIXTURE_IDENTITY=${STAGE_NEEDS_FIXTURE_IDENTITY:-1}
CELL_MIN=${CELL_MIN:-2}
# The serve-entry live launch. This is the evidence that a user can actually START the shipped
# engine, which an oracle gate over `algenta.inference.decode` does not by itself prove: decode()
# drives the worker directly, while `algenta serve` additionally resolves the bundled engine binary,
# runs the startup gate and answers over the CLI. Empty SERVE_MODEL skips the phase and the verdict
# records that it was skipped rather than implying it happened.
SERVE_MODEL=${SERVE_MODEL:-}
SERVE_PROMPT=${SERVE_PROMPT:-}
SERVE_MAX_NEW_TOKENS=${SERVE_MAX_NEW_TOKENS:-16}

NR="$SRC_TREE/benchmarks/llm_smoke/nvidia_race"
L3="$NR/vm_harness/lever3"
SITE="$WORK/site-packages"
RUNS="$WORK/runs"
LOGS="$WORK/logs"
CLK="$WORK/clocks"
LOGFILE=${CW_LOGFILE:-$WORK/battery.log}
HB="$WORK/heartbeat.log"
BATTERY_EXIT="$WORK/BATTERY_EXIT"
PHASE_FILE="$WORK/PHASE"
VERDICT="$WORK/cuda-release-verdict.json"
CENSUS="$WORK/wheel-census.json"

# THE CAP IS VM-ON TIME FROM lastStartTimestamp, WHICH INCLUDES THE BOOT THIS SCRIPT CANNOT OBSERVE —
# so only the caller can compute the deadline. Refusing to run uncapped is chain19.sh's rule, kept.
if [ -z "${CW_DEADLINE_EPOCH:-}" ]; then
  echo "FATAL: CW_DEADLINE_EPOCH is unset. The cap is VM-ON time from lastStartTimestamp, which"
  echo "       includes the boot+ssh this script cannot observe, so only the caller can compute it."
  echo "       Refusing to run an uncapped spot window."
  exit 2
fi

mkdir -p "$RUNS" "$LOGS" "$CLK" "$SITE"
# EXPORTED, not just assigned: the inline `bash -c` and `python3 -c` bodies below read these from the
# environment, and a body that silently sees an empty $SITE unpacks a wheel into the home directory
# and then reports that the worker is missing. Same rule the campaign learned the hard way — an env
# var that has to cross a process boundary must be named at every one (chain19.sh's launch-line
# comment records an `export` of a variable the ssh line never set exporting NOTHING).
export SRC_TREE WORK WHEEL_PATH SITE RUNS LOGS CLK LOGFILE GPU PY314 CKPT HF_CKPT
export GATE_SPECS GATE_PROMPTS CENSUS VERDICT BATTERY_EXIT PHASE_FILE HB NR L3
# Assigned further down, but marked for export here: `export NAME` before an assignment still exports
# the value it later gets, and the gate/conform evaluators below read these out of the environment.
export GATE_JSON CONFORM_JSON
# Same rule for the engine-shaped knobs: gate_any.py reads ORACLE_DIR/EOS_TOKENS,
# gate_coverage_gemma3_round19.py reads GATE_COVERAGE_PROMPTS/GATE_COVERAGE_SINGLE_RUN, and
# cell_watchdog.sh reads CW_PIN_MHZ -- all out of the environment, so an un-exported assignment here
# would silently leave each of them on its gemma default while the log claimed otherwise.
export ORACLE_DIR ORACLE_LABEL EOS_TOKENS GATE_COVERAGE_PROMPTS GATE_COVERAGE_SINGLE_RUN
export CW_PIN_MHZ STAGE_SCRIPT STAGE_NEEDS_FIXTURE_IDENTITY
export SERVE_JSON SERVE_MODEL SERVE_PROMPT SERVE_MAX_NEW_TOKENS

ts() { date -u +%FT%TZ; }
log() { echo "[$(ts)] $*" | tee -a "$LOGFILE"; }
mins_left() {
  left=$(( (CW_DEADLINE_EPOCH - $(date +%s)) / 60 ))
  [ "$left" -lt 0 ] && left=0
  echo "$left"
}
# The honest horizon: the deadline MINUS the stop-issuing margin, because a phase that finishes after
# the stop is issued does not finish.
affordable_min() {
  left=$(( (CW_DEADLINE_EPOCH - SAFETY_S - $(date +%s)) / 60 ))
  [ "$left" -lt 0 ] && left=0
  echo "$left"
}
budget_or_die() { # $1 = minutes the next phase needs ; $2 = phase name
  if [ "$(affordable_min)" -lt "$1" ]; then
    log "BUDGET: $2 needs ~$1 min but only $(affordable_min) min is affordable before the"
    log "        stop margin. DECLINING rather than starting a phase that cannot finish — a"
    log "        killed battery is unpublishable, a declined one merely is not."
    finish 11 "declined_$2"
  fi
}

# ── THE BATTERY'S FATE IS AN ARTIFACT, NOT AN INFERENCE ───────────────────────────────────────
# chain19.sh's lesson, inherited deliberately: a stale heartbeat says "something stopped", never
# "what finished, what failed, and whether any cell ran". So every exit path writes BATTERY_EXIT.
# AND ONE EXIT TRAP ONLY — in bash a later `trap ... EXIT` REPLACES the earlier one rather than
# stacking, which is how round 19's chain left CHAIN_EXIT empty (it exited itself, took the plain
# EXIT path, and `chain_exit` had been displaced by a trap registered after the pids appeared).
PHASE="init"
set_phase() { PHASE="$1"; echo "$1" > "$PHASE_FILE" 2>/dev/null; }
set_phase "init"
: > "$BATTERY_EXIT"

battery_exit() {
  rc=$1
  {
    echo "battery_exit_utc=$(ts)"
    echo "rc=$rc"
    echo "phase=$PHASE"
    echo "gate_verdict=$(cat "$WORK/GATE_VERDICT" 2>/dev/null || echo NOT_RUN)"
    echo "cells_written=$(ls -1 "$RUNS"/gate_*.out 2>/dev/null | wc -l | tr -d ' ')"
    echo "verdict_emitted=$([ -f "$VERDICT" ] && echo yes || echo no)"
    echo "deadline_epoch=$CW_DEADLINE_EPOCH"
    echo "mins_left_at_exit=$(mins_left)"
  } >> "$BATTERY_EXIT"
  log "BATTERY EXIT rc=$rc phase=$PHASE (recorded in $BATTERY_EXIT)"
  if [ "$rc" = "0" ]; then
    log "BATTERY COMPLETE"
  else
    log "BATTERY_FAILED rc=$rc phase=$PHASE"
  fi
}
finish() { battery_exit "$1"; kill "${HB_PID:-}" "${WD_PID:-}" 2>/dev/null; exit "$1"; }
trap 'finish $?' EXIT
trap 'battery_exit 143; kill "${HB_PID:-}" "${WD_PID:-}" 2>/dev/null; exit 143' TERM
trap 'battery_exit 130; kill "${HB_PID:-}" "${WD_PID:-}" 2>/dev/null; exit 130' INT

# ── HEARTBEAT + DEADLINE WATCHDOG ─────────────────────────────────────────────────────────────
# The heartbeat reads its state FROM FILES, because a subshell snapshots variables at fork time:
# chain18/19 both printed `phase=init` for an entire window for exactly that reason, which made a
# heartbeat unable to answer the one question it exists to answer (WHICH PHASE IS RUNNING).
( while true; do
    _p=$(cat "$PHASE_FILE" 2>/dev/null)
    echo "$(ts) battery GPU=$GPU phase=${_p:-?} pid=$$ mins_left=$(mins_left)" \
      "affordable=$(affordable_min)" >> "$HB"
    sleep 60
  done ) &
HB_PID=$!
# Separate process, so a phase that HANGS is still killed: the budget checks below only run BETWEEN
# phases, and a wedged cell would otherwise sit on the GPU until the spot instance was reclaimed.
# It kills the process GROUP (not a name pattern) and writes KILLED_BY_OPERATOR.
( while true; do
    sleep 30
    if [ "$(date +%s)" -ge "$CW_DEADLINE_EPOCH" ]; then
      echo "[$(ts)] KILLED_BY_OPERATOR phase=$(cat "$PHASE_FILE" 2>/dev/null) deadline reached" \
        | tee -a "$LOGFILE" "$HB"
      kill -TERM -- -$$ 2>/dev/null
      sleep 20
      kill -KILL -- -$$ 2>/dev/null
      exit 1
    fi
  done ) &
WD_PID=$!
# NO `trap ... EXIT` here or above: registering one would OVERWRITE the single trap and silently
# un-register battery_exit, which is the CHAIN_EXIT-was-empty defect round 19 reproduced.

run_phase() { # $1 = phase name ; rest = command
  set_phase "$1"; shift
  log "=== PHASE $PHASE  (mins_left=$(mins_left) affordable=$(affordable_min))  cmd: $* ==="
  "$@"
  rc=$?
  log "=== PHASE $PHASE rc=$rc  (mins_left=$(mins_left) affordable=$(affordable_min)) ==="
  return $rc
}

log "BATTERY START deadline=$CW_DEADLINE_EPOCH cap=${CAP_MIN}m grace=${GRACE_MIN}m mins_left=$(mins_left)"
# Captured once, at the top, and exported: the verdict reports a started/finished pair, and deriving
# "started" from the deadline later would be an inference dressed up as a measurement.
BATTERY_START=$(ts)
export BATTERY_START
log "synced_head=$(cat "$SRC_TREE/.synced_head" 2>/dev/null || echo '<none>')"
log "vm=$VM_NAME zone=$VM_ZONE project=$VM_PROJECT lastStartTimestamp=$VM_LAST_START gpu=$GPU"
log "wheel=$WHEEL_PATH expect_sha=$EXPECT_WHEEL_SHA expect_bytes=$EXPECT_WHEEL_BYTES"
log "gate scope=[$GATE_PROMPTS] specs=[$GATE_SPECS] ckpt=$CKPT hf=$HF_CKPT"

# A python 3.14 interpreter, because the wheel declares `requires-python >=3.14,<3.15` and the
# shipped path is what must run. The box has one inside the campaign's pixi env; PY314 overrides.
if [ -z "$PY314" ]; then
  for candidate in "$HOME/algenta/mojo_env/.pixi/envs/default/bin/python3.14" \
                   "$HOME/algenta/mojo_env/.pixi/envs/default/bin/python" \
                   "$(command -v python3.14 2>/dev/null || true)"; do
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then PY314="$candidate"; break; fi
  done
fi
[ -n "$PY314" ] || { log "FATAL: no python3.14 interpreter found (set PY314=)"; finish 12; }
log "python: $PY314 ($("$PY314" -V 2>&1))"

# ── 1. UNPACK THE WHEEL WITH THE STDLIB, AND CENSUS EVERY BINARY IN IT ────────────────────────
# `python3 -m zipfile -e` and no pip: the box has no github egress and a venv would need an index. A
# wheel IS a zip, so unpacking it is exactly as faithful as installing it for the purpose here —
# running the worker binary it contains — and it leaves the bytes untouched.
budget_or_die 3 unpack
run_phase unpack bash -c '
  set -uo pipefail
  rm -rf "$SITE" && mkdir -p "$SITE"
  "$PY314" -m zipfile -e "$WHEEL_PATH" "$SITE" || exit 1
  # zipfile does not preserve the executable bit, and a worker that is not +x cannot be launched.
  find "$SITE" -name "algenta-runtime-worker*" -type f -exec chmod 0755 {} +
  WORKER="$SITE/algenta_runtime_native/algenta-runtime-worker"
  [ -f "$WORKER" ] || { echo "NO WORKER IN WHEEL: $WORKER"; exit 1; }
  sha256sum "$WHEEL_PATH" | cut -d" " -f1 > "$WORK/wheel.sha256"
  echo "WHEEL_SHA256=$(cat "$WORK/wheel.sha256")"
  echo "WHEEL_BYTES=$(stat -c %s "$WHEEL_PATH")"
  echo "--- embedded engine binaries ---"
  sha256sum "$SITE"/algenta_runtime_native/algenta-runtime-worker* | tee "$WORK/binaries.sha256"
' || { log "FATAL: the wheel did not unpack to a runnable worker"; finish 13; }

# THE WHEEL HASH IS RE-CHECKED ON THE BOX AGAINST WHAT THE CONTROLLER HASHED LOCALLY. The controller
# already compared the two after the scp; this is the second, independent check at the moment of use,
# because a verdict that names the wrong bytes is worse than no verdict.
GOT_SHA=$(cat "$WORK/wheel.sha256" 2>/dev/null || echo "")
if [ -n "$EXPECT_WHEEL_SHA" ] && [ "$GOT_SHA" != "$EXPECT_WHEEL_SHA" ]; then
  log "*** WHEEL HASH MISMATCH: expected=$EXPECT_WHEEL_SHA got=$GOT_SHA"
  log "    REFUSING: the verdict must name the bytes that were tested."
  finish 9
fi
log "WHEEL_HASH_OK: $GOT_SHA"
if [ -n "$EXPECT_WHEEL_BYTES" ]; then
  GOT_BYTES=$(stat -c %s "$WHEEL_PATH" 2>/dev/null || echo 0)
  [ "$GOT_BYTES" = "$EXPECT_WHEEL_BYTES" ] || {
    log "*** WHEEL BYTE-COUNT MISMATCH: expected=$EXPECT_WHEEL_BYTES got=$GOT_BYTES"; finish 9; }
fi

run_phase census "$PY314" -c '
import hashlib, json, os, glob
site = os.environ["SITE"]
pkg = os.path.join(site, "algenta_runtime_native")
rows = []
for path in sorted(glob.glob(os.path.join(pkg, "algenta-runtime-worker*"))):
    blob = open(path, "rb").read()
    digest = hashlib.sha256(blob).hexdigest()
    rows.append({"name": os.path.basename(path), "bytes": len(blob),
                 "sha256": digest, "sha256_16": digest[:16]})
libs = []
for path in sorted(glob.glob(os.path.join(pkg, "lib*"))):
    blob = open(path, "rb").read()
    digest = hashlib.sha256(blob).hexdigest()
    libs.append({"name": os.path.basename(path), "bytes": len(blob), "sha256_16": digest[:16]})
wheel_path = os.environ["WHEEL_PATH"]
wheel_blob_sha = open(os.path.join(os.environ["WORK"], "wheel.sha256")).read().strip()
out = {"wheel": {"filename": os.path.basename(wheel_path), "sha256": wheel_blob_sha,
                 "sha256_16": wheel_blob_sha[:16], "bytes": os.path.getsize(wheel_path)},
       "engine_binary_count": len(rows), "engine_binaries": rows, "shared_libraries": libs}
json.dump(out, open(os.path.join(os.environ["WORK"], "wheel-census.json"), "w"), indent=2, sort_keys=True)
print("census: %d engine binaries, %d shared libraries" % (len(rows), len(libs)))
' || { log "FATAL: the binary census failed"; finish 13; }
log "census written to $CENSUS"

# ── 2. THE LOAD PROBE ────────────────────────────────────────────────────────────────────────
# Does the wheel's worker actually LOAD and stay up on this box? That is the minimum a "run-verified"
# claim rests on, and it is checked before any 20-minute gate rather than after. It also records the
# dynamic-link facts a GPU-less host would meet: the CUDA wheel bundles libMGPRT.so, whose own
# DT_NEEDED does NOT include libcuda.so.1 or libnvidia-ml.so.1 (it dlopens them), so the load-time
# closure is self-contained — measured here rather than assumed.
budget_or_die 2 load
run_phase load bash -c '
  set -uo pipefail
  W="$SITE/algenta_runtime_native/algenta-runtime-worker"
  PKG="$SITE/algenta_runtime_native"
  export LD_LIBRARY_PATH="$PKG:${LD_LIBRARY_PATH:-}"
  OUTTXT="$WORK/gpuless_load.txt"
  { echo "worker=$W"
    echo "--- ldd (unresolved entries are what a GPU-less host would hit) ---"
    ldd "$W" 2>&1
    echo "--- unresolved count ---"
    ldd "$W" 2>&1 | grep -c "not found" || true
    echo "--- nvidia-smi ---"
    nvidia-smi --query-gpu=index,name,driver_version,clocks.current.sm --format=csv,noheader 2>&1
  } > "$OUTTXT" 2>&1
  SOCK=/tmp/crv_probe_$$.sock
  timeout 120 "$W" --server "$SOCK" >/dev/null 2>&1 &
  pid=$!
  sleep 8
  if kill -0 "$pid" 2>/dev/null; then
    echo "WORKER_LAUNCH_OK: the wheel worker stayed up as a server (pid $pid)" | tee -a "$OUTTXT"
    kill "$pid" 2>/dev/null
  else
    echo "WORKER_LAUNCH_FAILED: the wheel worker exited during startup" | tee -a "$OUTTXT"
    exit 1
  fi
  echo "NOTE: this host HAS an NVIDIA driver, so this proves LOAD here, not on a GPU-less host." \
    | tee -a "$OUTTXT"
' || { log "FATAL: the wheel's worker did not load — nothing downstream is meaningful"; finish 14; }

# ── 3. STAGE: fixtures proven identical, checkpoint converted, clocks pinned and VERIFIED ─────
# chain7stage.sh is REUSED VERBATIM, not reimplemented: it is the script that proves fixture identity
# against round 6's certified gate echoes and refuses to proceed off-pin, and a release gate that
# hand-rolled its own staging would be a gate nobody could compare with the campaign's cells.
# WHICH stage script runs is a knob, because "the campaign's cells" are per-engine: chain7stage.sh is
# gemma3-27b end to end (it tokenises with ~/models/gemma-3-27b-it, requires the four /tmp/g3*
# fixtures, proves identity against round 6's GEMMA echoes, and converts gemma at weights_dtype=f32).
# Running it for a Qwen2.5-7B wheel would abort at "FIXTURE MISSING /tmp/g3pp256/prompt_0000.txt"
# having already paid for the boot. Another engine supplies its own stage via STAGE_SCRIPT; the
# contract it must satisfy is the same -- print STAGE_OK, leave the converted checkpoint at $CKPT,
# and leave the GPU pinned -- and STAGE_NEEDS_FIXTURE_IDENTITY says whether it also owes the
# round-6-style identity marker.
STAGE_LOG="$WORK/stage.log"
STAGE_BUDGET_MIN=${STAGE_BUDGET_MIN:-10}
budget_or_die "$STAGE_BUDGET_MIN" stage
log "stage script = $NR/$STAGE_SCRIPT (needs_fixture_identity=$STAGE_NEEDS_FIXTURE_IDENTITY)"
[ -f "$NR/$STAGE_SCRIPT" ] || {
  log "FATAL: no stage script at $NR/$STAGE_SCRIPT — the synced tree does not carry it"; finish 15; }
STAGE_SRC="$SRC_TREE" L7="$WORK" GPU="$GPU" CKPT="$CKPT" HF_CKPT="$HF_CKPT" LOG="$STAGE_LOG" \
  CW_PIN_MHZ="$CW_PIN_MHZ" GATE_SPECS="$GATE_SPECS" ORACLE_DIR="$ORACLE_DIR" \
  EOS_TOKENS="$EOS_TOKENS" PY314="$PY314" \
  run_phase stage bash "$NR/$STAGE_SCRIPT" \
  || { log "STAGE FAILED — nothing may be measured"; finish 15; }
grep -q "STAGE_OK" "$STAGE_LOG" 2>/dev/null || {
  log "FATAL: no STAGE_OK in the stage log ($STAGE_LOG)"; finish 15; }
if [ "$STAGE_NEEDS_FIXTURE_IDENTITY" = "1" ]; then
  grep -q "FIXTURE_IDENTITY_OK=True" "$STAGE_LOG" 2>/dev/null || {
    log "FATAL: fixtures were not proven identical to the certified echoes"; finish 15; }
  log "STAGE_OK + FIXTURE_IDENTITY_OK=True: fixtures, checkpoint and the pin all proven"
else
  # RECORDED, NOT SILENT. Skipping the identity proof weakens the gate in a specific, nameable way:
  # the fixtures are the ones this stage generated, not ones proven byte-identical to a banked
  # certified set. A verdict that did not say so would overstate what was certified.
  log "STAGE_OK. NOTE: this stage owes NO fixture-identity marker (STAGE_NEEDS_FIXTURE_IDENTITY=0),"
  log "      so the fixtures are the ones it generated, NOT proven identical to banked certified"
  log "      echoes. Recorded in the verdict; the oracle gate below still binds every token."
fi
log "clock pin for this window: ${CW_PIN_MHZ} MHz (zero off-pin tolerance)"

# ── 4. THE GATE CELLS, ONE PER PROCESS, EACH WITH ITS OWN CLOCK DISCIPLINE ────────────────────
# cell_watchdog.sh is sourced rather than copied: cw_cell is what samples clocks at 1 Hz around a
# cell and reports `clocks_after`/`offpin`, and the verdict has to carry those per cell. One cw_cell
# per label (rather than one driver process for all of them) is what makes the discipline per-cell,
# and it costs a fresh blob load per cell exactly as the race harness does.
# shellcheck source=/dev/null
. "$L3/cell_watchdog.sh"
CW_LOGFILE="$LOGFILE"
CW_TIMEOUT_S=${CW_TIMEOUT_S:-900}
cw_init "$RUNS" "$LOGS" "$CLK" "$GPU"

# Only the labels gate_any.py will look for, derived from the SAME scope the evaluator is given, so
# the cells and the verdict cannot disagree about what was requested.
LABELS=$("$PY314" -c '
import os, sys
scope = {s.strip() for s in os.environ["GATE_PROMPTS"].replace(":", ",").split(",") if s.strip()}
specs = dict()
for spec in os.environ["GATE_SPECS"].split():
    name, _, path = spec.partition(":")
    specs[name] = path
labels = []
for name in sorted(scope):
    if name not in specs:
        sys.stderr.write("scope names a prompt with no fixture spec: %s\n" % name)
        raise SystemExit(2)
    widths = (64,) if name == "rag4096" else (16, 64)
    for width in widths:
        labels.append("gate_%s_maxnew%d" % (name, width))
        if width == 64:
            labels.append("gate_%s_maxnew64_rep2" % name)
print(" ".join(labels))
') || { log "FATAL: could not derive the cell labels from the gate scope"; finish 16; }
N_LABELS=$(echo "$LABELS" | wc -w | tr -d ' ')
log "cells to run: $N_LABELS -> [$LABELS]"
# ~2 min per cell is the INHERITED race figure with headroom; the shipped path has never been timed
# here, so the budget over-estimates deliberately (a governor that under-estimates spends the window).
CELL_MIN=${CELL_MIN:-2}
budget_or_die $(( N_LABELS * CELL_MIN + 2 )) cells

for label in $LABELS; do
  name=$(echo "$label" | sed -e 's/^gate_//' -e 's/_maxnew.*$//')
  width=$(echo "$label" | sed -e 's/.*_maxnew//' -e 's/_rep2$//')
  fixture=""
  for spec in $GATE_SPECS; do
    [ "${spec%%:*}" = "$name" ] && fixture="${spec##*:}"
  done
  if [ -z "$fixture" ]; then
    log "FATAL: no fixture for prompt '$name' (label $label)"; finish 16
  fi
  log "--- cell $label (prompt=$name max_new=$width fixture=$fixture) ---"
  # cw_cell writes $RUNS/$label.out from the command's stdout, which is exactly the file gate_any.py
  # reads, so the driver's JSON line lands where the evaluator expects it.
  cw_cell "$label" env PYTHONPATH="$SITE:$SRC_TREE/packages/algenta" \
    ALGENTA_NATIVE_WORKER="$SITE/algenta_runtime_native/algenta-runtime-worker" \
    ALGENTA_RUNTIME_WORKER="$SITE/algenta_runtime_native/algenta-runtime-worker" \
    ALGENTA_RUNTIME_FALLBACK_MODE=deny \
    CUDA_VISIBLE_DEVICES="$GPU" \
    "$PY314" "$SRC_TREE/scripts/release/wheel_gate_cells.py" \
      --runs "$WORK/cell_tmp" --ckpt "$CKPT" --hf-checkpoint "$HF_CKPT" \
      --worker "$SITE/algenta_runtime_native/algenta-runtime-worker" --wheel "$WHEEL_PATH" \
      --only "$label" --specs "$name:$fixture"
  rc=$?
  # The driver writes into its own --runs dir; cw_cell captured its stdout to $RUNS/$label.out, which
  # is the file the evaluator reads. Keep the driver's copy too, for the audit trail.
  if [ -f "$WORK/cell_tmp/$label.out" ]; then
    cp "$WORK/cell_tmp/$label.out" "$RUNS/$label.json" 2>/dev/null || true
  fi
  if [ "$rc" != "0" ]; then
    log "CELL $label rc=$rc — a failed cell is a failed gate; stopping rather than continuing"
    log "  (the alternative is a gate with a hole in it, which is the round-18 reduced-scope gap)"
    finish 17
  fi
  grep -q '"generated"' "$RUNS/$label.out" 2>/dev/null || {
    log "CELL $label wrote no JSON token line — treating as a failure"; finish 17; }
  # ZERO OFF-PIN TOLERANCE, PER CELL, CHECKED AS THE WINDOW GOES rather than at the end: a cell that
  # ran off-pin is not comparable with the certified echoes, and discovering that after 11 cells
  # would waste the window instead of one cell. The pin is CW_PIN_MHZ, not a literal 1410: this check
  # and cell_watchdog's own off-pin count must agree on the number, or one of them refuses a window
  # the other called clean.
  offpin=$(awk '{print $2}' "$CLK/clocks_$label.csv" 2>/dev/null | grep -vc "^${CW_PIN_MHZ}\$" || true)
  after=$(nvidia-smi -i "$GPU" --query-gpu=clocks.current.sm --format=csv,noheader,nounits 2>/dev/null)
  log "CELL $label DISCIPLINE clocks_after=${after}MHz offpin=${offpin:-?} want=${CW_PIN_MHZ}MHz"
  if [ "${offpin:-1}" != "0" ] || [ "${after:-0}" != "$CW_PIN_MHZ" ]; then
    log "*** CLOCK DISCIPLINE BROKEN on $label (clocks_after=$after offpin=$offpin want=$CW_PIN_MHZ)."
    log "    REFUSING: a cell taken off the ${CW_PIN_MHZ} MHz pin is not comparable with the"
    log "    certified echoes."
    finish 18
  fi
done
log "ALL $N_LABELS CELLS RAN, each rc=0, each at ${CW_PIN_MHZ} MHz with offpin=0"

# ── 5. THE GATE VERDICT, FROM THE CAMPAIGN'S OWN EVALUATORS ───────────────────────────────────
# gate_any.py compares every emitted token against the cache-free fp32 oracle prefix, requires the
# 64-token repeats to be bit-identical, and admits an early stop only when the oracle holds EOS at the
# same index (that is what makes rag4096's 22/22 corroborated rather than self-consistent). Both
# evaluators are used VERBATIM: a release gate that forked the evaluator would fork the definition of
# "pass", and then the published inventory and the shipped wheel would be certified by different rules.
budget_or_die 2 gate
GATE_JSON="$WORK/gate_cuda_release.json"
run_phase gate "$PY314" "$L3/gate_any.py" "$RUNS" "$GATE_JSON" "cuda release wheel" "$GATE_PROMPTS" \
  || { log "gate_any.py exited non-zero"; finish 19; }
"$PY314" -c '
import json, os, sys
d = json.load(open(os.environ["GATE_JSON"], encoding="utf-8"))
print("GATE ALL_PASS =", d.get("all_pass"), "| scope =", d.get("scope"),
      "| out_of_scope =", d.get("out_of_scope_prompts"))
sys.exit(0 if d.get("all_pass") is True else 1)
' || { log "GATE FAILED — no verdict, no publish"; finish 19; }
echo "ALL_PASS" > "$WORK/GATE_VERDICT"
# The coverage evaluator, reused verbatim: it counts coverage FROM THE CELLS and refuses when the
# request-derived and cell-derived scopes disagree, whichever way that points. Round 19 needed it
# after a greedy `.*scope=` shell re-parse reported "1 of 4" for a gate that had enumerated four.
if [ -f "$NR/gate_coverage_gemma3_round19.py" ]; then
  run_phase coverage "$PY314" "$NR/gate_coverage_gemma3_round19.py" "$GATE_JSON" \
    || { log "COVERAGE REFUSED — the gate did not certify all four shapes"; finish 20; }
else
  log "NOTE: gate_coverage_gemma3_round19.py not in the synced tree; ALL_PASS alone is weaker"
  log "      evidence (it trusts the request-derived scope field). Recorded in the verdict."
fi
log "GATE PASSED at FULL SCOPE, counted from the cells"

# ── 6. THE CONFORMANCE CLI, FOR THE CUDA BACKEND ──────────────────────────────────────────────
# `algenta conform --backend cuda` is the cheapest point of refusal in the product: it judges the
# checkpoint's facts against the capability table before any weights are converted. A typed refusal
# here means the shipped CUDA path does not claim this model, which contradicts the gate that just
# passed — so a refusal (exit 2) stops the battery. Exit 3 (supported pending the tensor probe) is
# admissible and recorded as such, because config-only inputs genuinely owe a probe.
budget_or_die 2 conform
CONFORM_JSON="$WORK/conformance_cuda.json"
run_phase conform "$PY314" "$SRC_TREE/scripts/algenta_conform.py" "$HF_CKPT" \
  --backend cuda --json "$CONFORM_JSON"
conform_rc=$?
log "conform rc=$conform_rc (0=supported 3=supported_pending_probe 2=REFUSED 1=unusable input)"
if [ "$conform_rc" = "2" ] || [ "$conform_rc" = "1" ]; then
  log "*** CONFORMANCE REFUSED THE cuda BACKEND for this checkpoint while the oracle gate passed."
  log "    Those two facts contradict each other; refusing to issue a verdict."
  finish 21
fi

# ── 7. THE SERVE ENTRY, LIVE-LAUNCHED ─────────────────────────────────────────────────────────
# WHY THIS PHASE EXISTS AT ALL. Everything above drives the wheel's worker through
# `algenta.inference.decode` -- a Python call into the shipped path. That proves the wheel's binaries
# COMPUTE. It does not prove a user can START them: `algenta serve --backend cuda` additionally has
# to resolve the bundled engine binary out of the installed package, run the startup gate against
# this host's facts, spawn the engine, and answer over the CLI with tokens. A wheel that passes every
# oracle cell and then cannot be launched by its own advertised entry point is not a shippable wheel,
# and before this phase the battery would have certified exactly that.
# The launch is NOT given --engine-binary: the whole claim under test is that the resolver finds the
# engine that came out of THIS wheel. Overriding it would prove the file runs, not that it is found.
#
# WHAT THIS PHASE DOES *NOT* PROVE, stated so the verdict cannot be over-read. This is a LAUNCH
# proof, not a token-identity gate: it requires rc=0 and a non-zero token count, and it records the
# tokens, but it does not compare them against the oracle. Nor is it redundant with the cells above:
# the cells drive `algenta.inference.decode` through the wheel's generic `algenta-runtime-worker`,
# while this drives the BUNDLED certified engine that `algenta serve --backend cuda` resolves -- two
# different binaries out of the same wheel. Comparing the serve path's tokens to the oracle is the
# obvious next strengthening; it is not done here because the `--json` report's token field is not
# yet pinned by a test, and a gate that guesses its own input schema refuses good windows.
SERVE_JSON="$WORK/serve_launch.json"
SERVE_TXT="$WORK/serve_launch.txt"
# EXPORTED, and this is not optional: the launch below runs in a `bash -c` CHILD, which reads these
# out of the environment. SERVE_JSON was already exported at the top of this file, but SERVE_TXT and
# SERVE_IDS are assigned here -- unexported, the child would `tee` to an empty path and take the
# "neither SERVE_PROMPT nor a readable fixture" branch, failing a launch that was correctly set up.
# This is precisely the defect this battery's own header records round 18 paying for.
export SERVE_TXT SERVE_IDS
budget_or_die 3 serve
if [ -z "$SERVE_MODEL" ]; then
  # SKIPPED IS RECORDED AS SKIPPED. A verdict that simply omitted the serve launch would read as
  # "launched, nothing to report"; an explicit skipped marker with the reason is the only honest form.
  log "SERVE LAUNCH SKIPPED: SERVE_MODEL is empty. The verdict records serve_launch.status=skipped."
  log "  This window therefore did NOT prove the shipped entry point starts. Set SERVE_MODEL to the"
  log "  HF snapshot dir (and optionally SERVE_PROMPT) to make the launch part of the gate."
  "$PY314" -c '
import json, os
json.dump({"status": "skipped", "reason": "SERVE_MODEL empty", "rc": None, "tokens": None},
          open(os.path.join(os.environ["WORK"], "serve_launch.json"), "w"), indent=2)
' || log "WARNING: could not write the serve-skip marker"
else
  # The prompt: SERVE_PROMPT as text if given, else the FIRST gate fixture's token ids, so the serve
  # launch generates from exactly the bytes the oracle gate certified rather than from a prompt this
  # phase invented. --prompt-token-ids also skips the tokenizer, which removes a dependency from the
  # one phase whose job is to prove the engine starts.
  SERVE_IDS=""
  for spec in $GATE_SPECS; do
    f="${spec##*:}"
    if [ -f "$f" ]; then SERVE_IDS=$(head -1 "$f" | tr -d ' \n'); break; fi
  done
  run_phase serve bash -c '
    set -uo pipefail
    export PYTHONPATH="$SITE:$SRC_TREE/packages/algenta"
    export ALGENTA_NATIVE_WORKER="$SITE/algenta_runtime_native/algenta-runtime-worker"
    export ALGENTA_RUNTIME_WORKER="$SITE/algenta_runtime_native/algenta-runtime-worker"
    export ALGENTA_RUNTIME_FALLBACK_MODE=deny
    export CUDA_VISIBLE_DEVICES="$GPU"
    ARGS=(serve --backend cuda --model "$SERVE_MODEL" --converted-dir "$CKPT"
          --max-new-tokens "$SERVE_MAX_NEW_TOKENS" --json)
    if [ -n "${SERVE_PROMPT:-}" ]; then
      ARGS+=(--prompt "$SERVE_PROMPT")
    elif [ -n "${SERVE_IDS:-}" ]; then
      ARGS+=(--prompt-token-ids "$SERVE_IDS")
    else
      echo "SERVE_LAUNCH_FAILED: neither SERVE_PROMPT nor a readable fixture in GATE_SPECS"
      exit 2
    fi
    echo "cmd: python -m algenta.cli ${ARGS[*]}" | tee "$SERVE_TXT"
    # `python -m algenta.cli`, NOT the `algenta` console script: the wheel is unpacked with the
    # stdlib zipfile (no pip, no index on this box), so no console_script was ever installed. The
    # module path is the same entry point pyproject declares (`algenta = "algenta.cli:main"`).
    "$PY314" -m algenta.cli "${ARGS[@]}" >"$SERVE_JSON" 2>>"$SERVE_TXT"
    rc=$?
    echo "serve_rc=$rc" | tee -a "$SERVE_TXT"
    exit $rc
  '
  serve_rc=$?
  log "serve launch rc=$serve_rc (0=launched and generated, 2=TYPED REFUSAL, 1=error)"
  if [ "$serve_rc" != "0" ]; then
    log "*** THE SHIPPED ENTRY POINT DID NOT LAUNCH on a host whose wheel just passed the oracle"
    log "    gate. Those two facts contradict each other; refusing to issue a verdict."
    log "    stderr: $(tail -5 "$SERVE_TXT" 2>/dev/null)"
    finish 23
  fi
  # rc=0 is necessary but NOT sufficient: a launch that produced zero tokens is not a launch. The
  # claim this phase makes is "the entry point served tokens", so the tokens are checked.
  SERVE_TOKENS=$("$PY314" -c '
import json, os, sys
try:
    d = json.load(open(os.path.join(os.environ["WORK"], "serve_launch.json"), encoding="utf-8"))
except Exception as exc:
    print("UNPARSEABLE:%s" % exc); raise SystemExit(0)
toks = d.get("tokens") or (d.get("generation") or {}).get("tokens") or []
ids = d.get("token_ids") or (d.get("generation") or {}).get("token_ids") or []
print(len(toks) or len(ids))
' 2>/dev/null || echo "?")
  log "SERVE_LAUNCH_OK: rc=0, tokens=$SERVE_TOKENS, backend=cuda, engine resolved from the wheel"
  case "$SERVE_TOKENS" in
    ''|0|'?'|UNPARSEABLE*)
      log "*** the serve entry exited 0 but produced no tokens — that is not a launch"; finish 23 ;;
  esac
fi

# ── 8. EMIT THE VERDICT ───────────────────────────────────────────────────────────────────────
budget_or_die 1 verdict
run_phase verdict env WORK="$WORK" VERDICT="$VERDICT" CENSUS="$CENSUS" GATE_JSON="$GATE_JSON" \
  CONFORM_JSON="$CONFORM_JSON" CLK="$CLK" RUNS="$RUNS" GPU="$GPU" WHEEL_PATH="$WHEEL_PATH" \
  VM_NAME="$VM_NAME" VM_ZONE="$VM_ZONE" VM_PROJECT="$VM_PROJECT" VM_LAST_START="$VM_LAST_START" \
  SRC_TREE="$SRC_TREE" GATE_PROMPTS="$GATE_PROMPTS" CW_DEADLINE_EPOCH="$CW_DEADLINE_EPOCH" \
  CW_PIN_MHZ="$CW_PIN_MHZ" SERVE_JSON="$SERVE_JSON" STAGE_SCRIPT="$STAGE_SCRIPT" \
  STAGE_NEEDS_FIXTURE_IDENTITY="$STAGE_NEEDS_FIXTURE_IDENTITY" STAGE_LOG="$STAGE_LOG" \
  GATE_SPECS="$GATE_SPECS" EOS_TOKENS="$EOS_TOKENS" ORACLE_DIR="$ORACLE_DIR" \
  CKPT="$CKPT" HF_CKPT="$HF_CKPT" \
  "$PY314" -c '
import glob, json, os, subprocess
from datetime import datetime, timezone

work = os.environ["WORK"]
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


census = read_json(os.environ["CENSUS"], {}) or {}
gate = read_json(os.environ["GATE_JSON"], {}) or {}
conform = read_json(os.environ["CONFORM_JSON"], {}) or {}
head = ""
try:
    head = open(os.path.join(os.environ["SRC_TREE"], ".synced_head"), encoding="utf-8").read().strip()
except Exception:
    pass

# Per-cell clock discipline, read from the 1 Hz samplers cell_watchdog wrote, so the verdict carries
# the EVIDENCE and not a claim: clocks_before/after, sample count, and off-pin count per cell.
# THE PIN COMES FROM THE ENVIRONMENT, and the samples are compared as INTEGERS. They were compared
# as strings, which is a masked defect: min(["1410","990"]) is "1410" because "1" < "9", so a clock
# that sagged to 990 MHz would have been reported as clock_min_mhz=1410 -- the drift invisible in the
# very field a reader would check it in. `offpin` happened to catch it, but a verdict whose min/max
# fields lie is not a verdict worth re-checking.
PIN_MHZ = str(os.environ.get("CW_PIN_MHZ", "1410"))
cells = []
for path in sorted(glob.glob(os.path.join(os.environ["CLK"], "clocks_gate_*.csv"))):
    label = os.path.basename(path)[len("clocks_"):-len(".csv")]
    samples = [ln.split() for ln in open(path, encoding="utf-8", errors="replace") if ln.strip()]
    raw = [s[1].rstrip(",") for s in samples if len(s) > 1]
    numeric = []
    for value in raw:
        try:
            numeric.append(int(value))
        except ValueError:
            pass
    offpin = sum(1 for c in numeric if str(c) != PIN_MHZ)
    cells.append({
        "label": label,
        "clock_samples": len(raw),
        "clock_samples_numeric": len(numeric),
        "clock_min_mhz": min(numeric) if numeric else None,
        "clock_max_mhz": max(numeric) if numeric else None,
        "clocks_first_mhz": numeric[0] if numeric else None,
        "clocks_last_mhz": numeric[-1] if numeric else None,
        "pinned_mhz": int(PIN_MHZ),
        "offpin": offpin,
        "offpin_zero": offpin == 0 and bool(numeric),
    })

driver = ""
try:
    driver = subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader",
                             "-i", os.environ["GPU"]], capture_output=True, text=True).stdout.strip()
except Exception:
    pass
gpu_name = ""
try:
    gpu_name = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader",
                               "-i", os.environ["GPU"]], capture_output=True, text=True).stdout.strip()
except Exception:
    pass

# The toolchain pin, READ from the synced mojo_env/pixi.toml rather than transcribed: a verdict that
# claimed a pin it never opened would be exactly the kind of unevidenced field the rest of this file
# exists to avoid. Absent file => empty dict, and the verdict says the pin came from the commit.
pins = {}
try:
    import tomllib
    with open(os.path.join(os.environ["SRC_TREE"], "mojo_env", "pixi.toml"), "rb") as fh:
        pixi = tomllib.load(fh)
    deps = dict(((pixi.get("workspace") or {}).get("dependencies")) or pixi.get("dependencies") or {})
    pins = {k: v for k, v in deps.items()
            if isinstance(v, str) and any(t in k.lower() for t in ("mojo", "max", "python"))}
except Exception:
    pins = {}

# THE SCOPE STATEMENT NAMES THE GPU THAT WAS ACTUALLY USED. It used to assert "ONE H200 box at
# 1410 MHz" as a literal, which is a false claim on any other SKU -- and the purpose of a given
# window may well be to certify a wheel on a cheaper, different GPU. A scope statement is the part of
# a verdict a reader trusts most, so it is composed from the measured gpu_name and the pin ordered.
# (No apostrophes anywhere inside this embedded python body: it is delimited by single quotes, so one
# would close the shell string early and turn the rest of the python into shell syntax errors.)
serve_report = read_json(os.environ.get("SERVE_JSON", ""), {}) or {}
serve_status = serve_report.get("status")
if serve_status is None:
    serve_status = "launched" if serve_report else "not_run"
scope_bits = [
    "Certifies that THIS wheel launched and passed the oracle gate on ONE %s box"
    % (gpu_name or "GPU"),
    "at %s MHz with offpin=0 on every cell" % PIN_MHZ,
    "gate scope [%s] against the oracle at %s"
    % (os.environ.get("GATE_PROMPTS", "?"), os.environ.get("ORACLE_DIR") or "<evaluator default>"),
    "serve entry live-launch: %s" % serve_status,
]
SCOPE_STATEMENT = (
    ", ".join(scope_bits)
    + ", and answered the conformance table for the cuda backend. It is not a benchmark win, not a "
      "multi-hardware or multi-driver certification, and not a claim about any other host."
)

# Read defensively: the stage log is written by a different script and may be absent if the stage died
# before creating it, and a verdict emitter that raises turns a completed battery into no verdict.
fixture_identity_proven = False
try:
    with open(os.environ.get("STAGE_LOG", ""), encoding="utf-8", errors="replace") as fh:
        fixture_identity_proven = "FIXTURE_IDENTITY_OK=True" in fh.read()
except Exception:
    fixture_identity_proven = False

verdict = {
    "schema_version": 1,
    "verdict": "pass",
    "rc": 0,
    "issued_utc": now,
    "issuer": "scripts/release/verify_cuda_release.sh + verify_cuda_release_battery.sh",
    "scope_statement": SCOPE_STATEMENT,
    "timestamps": {
        "started_utc": os.environ.get("BATTERY_START"),
        "finished_utc": now,
        "deadline_epoch": int(os.environ["CW_DEADLINE_EPOCH"]),
    },
    "wheel": {
        "filename": os.path.basename(os.environ["WHEEL_PATH"]),
        "sha256": (census.get("wheel") or {}).get("sha256"),
        "sha256_16": ((census.get("wheel") or {}).get("sha256") or "")[:16] or None,
        "bytes": (census.get("wheel") or {}).get("bytes"),
        "artifact_name": "algenta-runtime-native-linux-x86_64-cuda",
    },
    "wheel_sha256": (census.get("wheel") or {}).get("sha256"),
    "binaries": {
        "engine_binary_count": census.get("engine_binary_count"),
        "engine_binaries": census.get("engine_binaries") or [],
        "shared_libraries": census.get("shared_libraries") or [],
    },
    "toolchain": {
        "synced_head": head,
        "pin_source": "mojo_env/pixi.toml at the synced commit",
        "pins": pins,
        "cuda_target": "sm_90 (MOJO_BUILD_CUDA_TARGET default in scripts/build_mojo_binary.sh)",
        "driver_version": driver,
    },
    "vm": {
        "name": os.environ["VM_NAME"],
        "zone": os.environ["VM_ZONE"],
        "project": os.environ["VM_PROJECT"],
        "gpu_index": int(os.environ["GPU"]),
        "gpu_name": gpu_name,
        "last_start_timestamp": os.environ["VM_LAST_START"],
    },
    "clocks": {
        "pinned_mhz": int(PIN_MHZ),
        "offpin_total": sum(c["offpin"] for c in cells),
        "cells": cells,
        "clocks_source": "remeasured_per_cell_by_cell_watchdog",
    },
    # THE SERVE ENTRY, AS ITS OWN TOP-LEVEL CLAIM. Kept out of `gates` on purpose: an oracle gate over
    # decode() and a live launch of `algenta serve` are different claims about different code paths,
    # and folding one into the other would let a skipped launch hide inside a passed gate.
    "serve_launch": {
        "status": serve_status,
        "reason": serve_report.get("reason"),
        "requested_backend": "cuda",
        "max_new_tokens": os.environ.get("SERVE_MAX_NEW_TOKENS"),
        "model": serve_report.get("model") or os.environ.get("SERVE_MODEL") or None,
        "engine_resolved_from_wheel": serve_status == "launched",
        "report": serve_report,
    },
    "stage": {
        "script": os.environ.get("STAGE_SCRIPT"),
        "needs_fixture_identity": os.environ.get("STAGE_NEEDS_FIXTURE_IDENTITY") == "1",
        "fixture_identity_proven": fixture_identity_proven,
        "gate_specs": os.environ.get("GATE_SPECS"),
        "converted_checkpoint": os.environ.get("CKPT"),
        "hf_checkpoint": os.environ.get("HF_CKPT"),
        "eos_tokens": os.environ.get("EOS_TOKENS"),
        "oracle_dir": os.environ.get("ORACLE_DIR") or None,
    },
    "gates": {
        # "full scope" is a claim about the EVALUATOR scope list, not a property of every gate. It is
        # derived from the coverage evaluator prompt set, so a reduced-scope window cannot describe
        # itself as full-scope by inheriting a string literal.
        "kind": "fresh_oracle_gate_on_the_wheel[scope=%s]"
                % os.environ.get("GATE_COVERAGE_PROMPTS", os.environ.get("GATE_PROMPTS", "?")),
        "all_pass": gate.get("all_pass"),
        "scope": gate.get("scope"),
        "out_of_scope_prompts": gate.get("out_of_scope_prompts"),
        "requested_scope": sorted(
            s.strip() for s in os.environ["GATE_PROMPTS"].replace(":", ",").split(",") if s.strip()
        ),
        "oracle": gate.get("oracle"),
        "gate_json": gate,
        "cell_files": sorted(
            os.path.basename(p) for p in glob.glob(os.path.join(os.environ["RUNS"], "gate_*.out"))
        ),
    },
    "conformance": {
        "backend": "cuda",
        "status": conform.get("status"),
        "refusals": conform.get("refusals") or [],
        "pending_probe": conform.get("pending_probe") or [],
        "cli": "scripts/algenta_conform.py --backend cuda",
    },
    "evidence": {
        "kind": "fresh_battery",
        "fresh_battery": True,
        "gpuless_load": open(os.path.join(work, "gpuless_load.txt"), encoding="utf-8",
                             errors="replace").read()[-4000:],
        "battery_exit": open(os.path.join(work, "BATTERY_EXIT"), encoding="utf-8",
                             errors="replace").read(),
    },
}
json.dump(verdict, open(os.environ["VERDICT"], "w", encoding="utf-8"), indent=2, sort_keys=True)
print("WROTE", os.environ["VERDICT"])
print("wheel_sha256 =", verdict["wheel_sha256"])
print("cells =", len(cells), "offpin_total =", verdict["clocks"]["offpin_total"])
print("gates.all_pass =", verdict["gates"]["all_pass"], "conformance =", verdict["conformance"]["status"])
' || { log "FATAL: verdict emission failed"; finish 22; }

[ -f "$VERDICT" ] || { log "FATAL: no verdict file at $VERDICT"; finish 22; }
log "VERDICT EMITTED: $VERDICT"
log "  the controller now re-checks it (pass, rc=0, wheel sha == the locally hashed wheel, every"
log "  cell at 1410 MHz with offpin=0) BEFORE it accepts it. A verdict is a claim; the check is proof."
finish 0
