#!/bin/bash
# vm_window_r19.sh — RUN THIS ON THE LOCAL MAC. The round-19 VM window controller: it OWNS the cap
# and it OWNS the stop. Everything else in the round runs inside the window this opens.
#
# DERIVED FROM round 18's `vm_window_r18.sh` BY IDENTIFIER SUBSTITUTION, NOT REWRITTEN — round 18
# paid for this controller's structure in three group-kills and one 4003-on-boot, and every one of
# those lessons is a comment below that still applies verbatim. What round 19 changes is: the
# round's paths (`~/g3r19`, `~/lever19`,
# `/private/tmp/gemma_r19`), the chain it launches (`chain19.sh`), the governor knobs it names on
# the launch line (the FULL four-prompt gate scope, the twin-bracket shape, and a PROTECTED TRT
# re-serve reserve), and the two extra fields the watch surfaces — because round 19's gate verdict
# is the deliverable the flip is conditional on, so ALL_PASS-vs-FAILED must be visible from the Mac
# without spending an ssh round trip to find out.
#
# WHY A CONTROLLER AND NOT A HANDFUL OF gcloud CALLS. The cap is **VM-ON time measured from
# `lastStartTimestamp`**, which includes ~4 min of boot+ssh that no in-VM script can observe. So the
# deadline has to be computed HERE, from the instance's own reported start, and pushed into the VM —
# and the stop has to be issued from here too, because a VM that is busy measuring cannot be relied
# on to stop itself. Round 17 ran to 93 min 58 s against a 90 min cap and issued its stop 69 s after
# its bracket finished. That is the margin this script exists to make structural rather than lucky.
#
# PHASES
#   start    gcloud compute instances start; up to START_TRIES attempts. Two consecutive spot
#            STOCKOUTs abort the round (the owner's rule) rather than burn retries against a zone
#            that has no capacity; the message says so and the VM is left TERMINATED.
#   sync     vm_sync_r19.sh — tar+scp the committed tree, refusing a dirty or unpushed one.
#   launch   chain19.sh under `setsid nohup ... </dev/null & disown`. THE CHANNEL MUST NOT BE
#            INHERITED: round 17 lost 2 x 300 s to two ssh calls hanging client-side because a
#            backgrounded remote process held the channel open, while the jobs had in fact launched.
#   watch    poll the heartbeat file every 60 s and echo it locally, so liveness is observable
#            without an extra ssh round trip per check and a wedged phase is visible within a minute.
#   stop     issued at min(deadline, chain-complete) + STOP_MARGIN. ALWAYS issued: on success, on
#            failure, on timeout, and on Ctrl-C (trap). `--discard-local-ssd=false` so ~/lever19,
#            ~/lever3, ~/adj and the certified gate echoes survive for the next round.
#   verify   the instance must report TERMINATED and a project-wide `--filter='status=RUNNING'`
#            must come back EMPTY. Both are printed, because "I stopped it" is a claim and the
#            owner's standing mandate is that no race VM is left running after its task ends.
#
# Usage:
#   bash vm_window_r19.sh                 # full window
#   DRY_RUN=1 bash vm_window_r19.sh       # compute the plan and the deadline, touch nothing
set -uo pipefail

VM=${VM:-trtllm-gemma-us-west1-c}
ZONE=${ZONE:-us-west1-c}
PROJECT=${PROJECT:-eplanev2}
CAP_MIN=${CAP_MIN:-90}          # the owner's standing hard cap on VM-ON time. The round-19 RE-SERVE
                                # window overrides it to 75 via env (owner-authorised), because it
                                # re-proves a banked gate instead of re-running it; the default stays
                                # 90 so a future full window is not silently under-capped.
GRACE_MIN=${GRACE_MIN:-5}       # ... plus grace, for the stop to land
STOP_MARGIN_S=${STOP_MARGIN_S:-180}   # issue the stop this far BEFORE the deadline
START_TRIES=${START_TRIES:-2}
POLL_S=${POLL_S:-60}
WT=${WT:-/Users/angel/Developer/decision-engine/.qwen/worktrees/gemma-r19}
NR="$WT/benchmarks/llm_smoke/nvidia_race"
LOCAL_LOG=${LOCAL_LOG:-/private/tmp/gemma_r19/window19.log}
DRY_RUN=${DRY_RUN:-0}

mkdir -p "$(dirname "$LOCAL_LOG")"
# TRUNCATE, DO NOT APPEND ACROSS RUNS. Several gates below are `grep -q <marker> "$LOCAL_LOG"`
# (PREFLIGHT OK, SYNC_DONE, LAUNCHED), and a marker left over from an earlier attempt would
# satisfy them falsely — the same class of defect as a guard that passes for the wrong reason.
# Round 18's first window aborted and a re-run would have inherited its log; the previous run is
# preserved alongside, timestamped, rather than overwritten.
if [[ -f "$LOCAL_LOG" ]]; then
  mv "$LOCAL_LOG" "${LOCAL_LOG%.log}.$(date -u +%Y%m%dT%H%M%SZ).log"
fi
: > "$LOCAL_LOG"
ts() { date -u +%FT%TZ; }
log() { echo "[$(ts)] $*" | tee -a "$LOCAL_LOG"; }
gc() { gcloud compute "$@" --project="$PROJECT" --zone="$ZONE"; }

# ── SSHD READINESS, AND WHY `status=RUNNING` IS NOT ENOUGH ────────────────────────────────────
# Round 18's third boot died on a TRANSIENT: `gcloud compute scp` was issued ~60 s after the
# instance reported RUNNING, while sshd was still coming up, and IAP answered
# `ERROR: (gcloud.compute.ssh) ... 4003 failed to connect to port 22`. The controller read that as
# SYNC FAILED and tore the window down — 4 min of VM-on spent on a fault that a 30 s wait would
# have cleared. GCE's RUNNING means the hypervisor scheduled the guest, not that the guest's ssh
# is accepting connections, and on a spot 8xH200 with a large boot disk that gap is routinely a
# minute or more. So every ssh/scp below goes through a readiness probe first, and the probe is
# CHEAP (`echo READY`) rather than a real payload, because a probe that costs a minute is not a
# probe. Retrying the expensive operation blindly is what burns the cap.
SSH_TRIES=${SSH_TRIES:-10}
SSH_WAIT_S=${SSH_WAIT_S:-30}
ssh_ready() { # returns 0 once a trivial remote command succeeds
  local i
  for i in $(seq 1 "$SSH_TRIES"); do
    if gcloud compute ssh "$VM" --project="$PROJECT" --zone="$ZONE" \
         --command 'echo READY' >/dev/null 2>&1; then
      log "sshd READY on probe $i/$SSH_TRIES"
      return 0
    fi
    log "sshd not ready (probe $i/$SSH_TRIES) — waiting ${SSH_WAIT_S}s before the next"
    sleep "$SSH_WAIT_S"
  done
  log "FATAL: sshd never became ready after $SSH_TRIES probes ($(( SSH_TRIES * SSH_WAIT_S ))s)"
  return 1
}
ssh_retry() { # $1 = tries ; rest = a gcloud compute ssh/scp invocation
  local n=$1; shift
  local i
  for i in $(seq 1 "$n"); do
    ssh_ready || return 1
    if "$@" >>"$LOCAL_LOG" 2>&1; then return 0; fi
    log "remote call failed on attempt $i/$n ($*) — re-probing sshd before retrying"
    sleep "$SSH_WAIT_S"
  done
  return 1
}

STARTED=0
# THE STOP IS RETRIED UNTIL THE INSTANCE REPORTS TERMINATED, AND THIS IS NOT PEDANTRY. Round 18's
# first window hit the exact failure this loop exists for: `gcloud compute instances stop` returned
#   "ERROR: Instance has in progress persistent disk IO and cannot be suspended/stopped at this
#    time."
# because the instance had come up only seconds earlier, and the previous version logged the error,
# printed "stop: returned", and EXITED — leaving a spot H200 VM RUNNING with nothing owning it.
# The owner's standing mandate is that no race VM is left running after its task ends, so a stop
# that reports failure is a stop that has not happened: retry, and if it still will not terminate,
# say so in the loudest terms available rather than exiting 0.
STOP_TRIES=${STOP_TRIES:-8}
STOP_WAIT_S=${STOP_WAIT_S:-20}
stop_vm() { # idempotent, retried, and always verifies
  local st i
  for i in $(seq 1 "$STOP_TRIES"); do
    st=$(gcloud compute instances describe "$VM" --project="$PROJECT" --zone="$ZONE" \
          --format='value(status)' 2>/dev/null || echo UNKNOWN)
    if [[ "$st" == "TERMINATED" ]]; then
      log "stop: TERMINATED confirmed on attempt $i"
      break
    fi
    log "stop: attempt $i/$STOP_TRIES (status=$st) --discard-local-ssd=false"
    gcloud compute instances stop "$VM" --project="$PROJECT" --zone="$ZONE" \
      --discard-local-ssd=false >>"$LOCAL_LOG" 2>&1
    log "stop: gcloud returned at $(ts)"
    sleep "$STOP_WAIT_S"
  done
  st=$(gcloud compute instances describe "$VM" --project="$PROJECT" --zone="$ZONE" \
        --format='value(status)' 2>/dev/null || echo UNKNOWN)
  if [[ "$st" == "TERMINATED" ]]; then
    log "VERIFY instance status = TERMINATED  TERMINATED_OK"
  else
    log "VERIFY instance status = $st  *** NOT_TERMINATED — STOP MANUALLY NOW: ***"
    log "  gcloud compute instances stop $VM --project=$PROJECT --zone=$ZONE --discard-local-ssd=false"
  fi
  local run
  run=$(gcloud compute instances list --project="$PROJECT" --filter='status=RUNNING' \
        --format='value(name,zone,status)' 2>/dev/null)
  if [[ -z "$run" ]]; then
    log "VERIFY project-wide status=RUNNING is EMPTY — no VM left running"
  else
    log "VERIFY project-wide status=RUNNING is NOT EMPTY:"
    echo "$run" | while read -r l; do log "    STILL RUNNING: $l"; done
  fi
  [[ "$st" == "TERMINATED" ]]
}
trap 'log "TRAP: interrupted — stopping the VM before exiting"; [[ $STARTED == 1 ]] && stop_vm; exit 130' INT TERM

# ── 0. PRE-FLIGHT, BEFORE THE INSTANCE IS STARTED ─────────────────────────────────────────────
# Every local precondition is checked here, while the VM is still TERMINATED and costs nothing.
# The cap is measured from `lastStartTimestamp`, so a start followed by an immediate local refusal
# is pure VM-on burn — which is precisely what round 18's first window did: it booted the box, then
# the sync stage refused on an untracked `mojo_env/.pixi` symlink and the whole window was over in
# 10 seconds having measured nothing.
log "pre-flight: checking the worktree is clean and pushed BEFORE starting anything"
if ! WT="$WT" PREFLIGHT_ONLY=1 bash "$NR/vm_sync_r19.sh" 2>&1 | tee -a "$LOCAL_LOG"; then
  log "PRE-FLIGHT FAILED — the VM was NOT started, so no VM-on time was spent. Fix and re-run."
  exit 8
fi
grep -q "PREFLIGHT OK" "$LOCAL_LOG" || { log "PRE-FLIGHT FAILED (no PREFLIGHT OK) — not starting"; exit 8; }
command -v gcloud >/dev/null || { log "FATAL: gcloud not on PATH"; exit 8; }

# ── 1. START ──────────────────────────────────────────────────────────────────────────────────
st=$(gcloud compute instances describe "$VM" --project="$PROJECT" --zone="$ZONE" \
      --format='value(status)' 2>/dev/null || echo UNKNOWN)
log "instance $VM status=$st zone=$ZONE project=$PROJECT cap=${CAP_MIN}m grace=${GRACE_MIN}m"
if (( DRY_RUN == 1 )); then
  log "DRY_RUN: would start, sync, launch chain19.sh, watch, then stop. Touching nothing."
  exit 0
fi
if [[ "$st" != "RUNNING" ]]; then
  tries=0; stockouts=0
  while (( tries < START_TRIES )); do
    tries=$((tries + 1))
    log "start attempt $tries/$START_TRIES"
    out=$(gcloud compute instances start "$VM" --project="$PROJECT" --zone="$ZONE" 2>&1)
    rc=$?
    if (( rc == 0 )); then stockouts=0; break; fi
    echo "$out" | tail -6 | tee -a "$LOCAL_LOG"
    if echo "$out" | grep -qiE "ZONE_RESOURCE_POOL_EMPTY|stockout|insufficient|capacity"; then
      stockouts=$((stockouts + 1))
      log "SPOT STOCKOUT ($stockouts consecutive) in $ZONE"
      if (( stockouts >= 2 )); then
        log "TWO CONSECUTIVE STOCKOUTS — stopping and waiting, per the owner's rule. No further"
        log "  retries this session. Candidate zones if the instance must be recreated:"
        log "  us-west1-c (current), asia-south1-b, asia-south2-c."
        exit 4
      fi
      sleep 90
    else
      log "start failed for a NON-capacity reason; not retrying blindly"
      exit 3
    fi
  done
fi
STARTED=1
# wait for ssh, and get the AUTHORITATIVE start time the cap is measured from
lst=""
for i in $(seq 1 40); do
  lst=$(gcloud compute instances describe "$VM" --project="$PROJECT" --zone="$ZONE" \
        --format='value(lastStartTimestamp)' 2>/dev/null || echo "")
  st=$(gcloud compute instances describe "$VM" --project="$PROJECT" --zone="$ZONE" \
        --format='value(status)' 2>/dev/null || echo UNKNOWN)
  [[ "$st" == "RUNNING" && -n "$lst" ]] && break
  sleep 15
done
log "lastStartTimestamp = $lst  status=$st"
[[ -z "$lst" ]] && { log "FATAL: no lastStartTimestamp — cannot compute the cap. Stopping."; stop_vm; exit 5; }
# PARSE THE OFFSET, DO NOT ASSUME IT. `date -j -f "%Y-%m-%dT%H:%M:%S"` on macOS interprets the
# naive string in the HOST's zone, and gcloud reports `lastStartTimestamp` in the instance's zone
# (-07:00 for us-west1). On a host that is not in that zone the epoch comes out wrong by the
# difference — measured on this Mac, which is EDT (-0400): parsing 2026-09-19T08:26:50.016-07:00
# naively yields 12:26:50Z instead of 15:26:50Z, **three hours early**, which would have put the
# hard deadline in the past and made this controller stop the VM before anything ran. Python's
# fromisoformat handles the offset (and a Z suffix) correctly on every host, so it is the parser
# and `date` is only the fallback. `python3 -c`, NOT a heredoc inside `$( )`: bash 3.2 on macOS
# mishandles that combination, which is the same trap the owner's rules already flag for
# `gh pr create`. The python below therefore contains no single quotes.
LST_EPOCH=$(python3 -c 'import sys
from datetime import datetime
s = sys.argv[1].strip()
if s.endswith("Z"):
    s = s[:-1] + "+00:00"
print(int(datetime.fromisoformat(s).timestamp()))' "$lst" 2>/dev/null)
if ! [[ "${LST_EPOCH:-}" =~ ^[0-9]+$ ]] || (( LST_EPOCH == 0 )); then
  LST_EPOCH=$(date -j -f "%Y-%m-%dT%H:%M:%S%z" "${lst:0:19}${lst: -6}" +%s 2>/dev/null \
              || date -d "$lst" +%s 2>/dev/null || echo 0)
fi
if ! [[ "${LST_EPOCH:-}" =~ ^[0-9]+$ ]] || (( LST_EPOCH == 0 )); then
  log "FATAL: could not parse lastStartTimestamp '$lst'. Stopping rather than run uncapped."
  stop_vm; exit 5
fi
# Sanity: the parsed start must be in the PAST and recent. A future or wildly old epoch means the
# parse is wrong, and a wrong epoch is worse than no epoch because the window looks capped.
now_e=$(date +%s)
if (( LST_EPOCH > now_e + 60 )); then
  log "FATAL: parsed lastStartTimestamp is in the FUTURE (start=$LST_EPOCH now=$now_e) — the"
  log "       offset was mis-parsed. Refusing to compute a deadline from it. Stopping."
  stop_vm; exit 5
fi
if (( now_e - LST_EPOCH > 6 * 3600 )); then
  log "FATAL: parsed lastStartTimestamp is $(( (now_e - LST_EPOCH) / 60 )) min old, which is not"
  log "       this start. Refusing; stopping."; stop_vm; exit 5
fi
DEADLINE=$(( LST_EPOCH + (CAP_MIN + GRACE_MIN) * 60 ))
log "VM-ON cap ${CAP_MIN}m + ${GRACE_MIN}m grace => HARD DEADLINE $(date -u -r $DEADLINE +%FT%TZ) (epoch $DEADLINE)"
log "already elapsed since start: $(( ($(date +%s) - LST_EPOCH) / 60 )) min"

# ── 1b. ARM THE INDEPENDENT STOP BACKSTOP, BEFORE ANYTHING ELSE CAN FAIL ──────────────────────
# A SECOND owner of the stop, in its own session, sharing no process group with this controller.
# Round 18 needed it three times over: this controller was group-killed at 18:38:35Z, 19:20:56Z and
# ~20:24Z while the operator recovered from harness defects, and on the first of those the
# controller's EXIT trap was mid-`stop_vm` when the follow-up SIGKILL landed, after GCE had already
# refused the stop with "Instance has in progress persistent disk IO". Nothing retried it and the box
# sat RUNNING and unowned until it was stopped by hand. The controller's own trap and retry loop are
# necessary but they are NOT sufficient, because they die with the controller.
# macOS has no setsid(1), so the new session comes from os.setsid(2) via python + os.execv.
BACKSTOP_LOG=${BACKSTOP_LOG:-/private/tmp/gemma_r19/backstop19.log}
if [[ "${BACKSTOP:-1}" == "1" ]]; then
  # REUSED, NOT REWRITTEN: `vm_stop_backstop_r18.sh` keeps its round-18 name because it is the same
  # script round 18 paid for in three group-kills, and renaming it would break the dry-run that
  # proves it. What round 19 supplies is the two knobs that decide whether it acts on the right
  # window: LEVER_DIR, so it reads CHAIN_EXIT from ~/lever19 rather than ~/lever18 (a wrong dir
  # means the early-stop-on-dead-chain path never fires and only the deadline can stop the box), and
  # LOG. Its liveness pattern is round-agnostic by default (`chain[0-9]*[.]sh|...|driver_ctx8192`).
  LOG="$BACKSTOP_LOG" GCLOUD=gcloud LEVER_DIR="${LEVER_DIR:-/home/angel/lever19}" \
    python3 -c 'import os,sys; os.setsid(); os.execv("/bin/bash",["bash"]+sys.argv[1:])' \
    "$NR/vm_stop_backstop_r18.sh" --deadline "$DEADLINE" --poll "${BACKSTOP_POLL:-60}" \
      --idle-grace "${BACKSTOP_IDLE_GRACE:-300}" --max-min "$(( CAP_MIN + GRACE_MIN + 30 ))" \
    >>"$LOCAL_LOG" 2>&1 &
  BACKSTOP_PID=$!
  sleep 3
  if ps -p "$BACKSTOP_PID" >/dev/null 2>&1; then
    log "backstop ARMED pid=$BACKSTOP_PID pgid=$(ps -o pgid= -p "$BACKSTOP_PID" | tr -d ' ')" \
        "log=$BACKSTOP_LOG (own session: a group-kill of THIS controller cannot reach it)"
  else
    log "WARNING: the backstop did not stay up. This controller is then the ONLY owner of the stop."
  fi
fi

# ── 2. SYNC ───────────────────────────────────────────────────────────────────────────────────
# Probes sshd first and RETRIES the whole sync, because the scp inside it is exactly the call that
# died on boot 3 while sshd was still coming up. A transient must cost 30 s, not the window.
SYNC_TRIES=${SYNC_TRIES:-3}
synced=0
for i in $(seq 1 "$SYNC_TRIES"); do
  log "sync attempt $i/$SYNC_TRIES (sshd probe first)"
  if ! ssh_ready; then log "sshd not ready before sync attempt $i"; continue; fi
  if WT="$WT" VM="$VM" ZONE="$ZONE" PROJECT="$PROJECT" bash "$NR/vm_sync_r19.sh" >>"$LOCAL_LOG" 2>&1; then
    synced=1; break
  fi
  log "sync attempt $i FAILED (rc=$?) — see $LOCAL_LOG; re-probing before the next"
  sleep "$SSH_WAIT_S"
done
if (( synced != 1 )) || ! grep -q "SYNC_DONE" "$LOCAL_LOG"; then
  log "SYNC FAILED after $SYNC_TRIES attempts — stopping; nothing was measured"
  stop_vm; exit 6
fi
log "SYNC_DONE confirmed on attempt $i"

# ── 3. LAUNCH (channel must NOT be inherited) ─────────────────────────────────────────────────
log "launching chain19.sh under setsid+nohup, stdin /dev/null, disowned"
# EVERY GOVERNOR KNOB IS PASSED ON THIS LINE, EXPLICITLY. This is a bug round 18 caught before it
# cost a bracket rather than after: `chain19.sh` `export`s GATE_SPECS / PROMPTS_ORDER / WARM_RUNS /
# CLOSE_RUNS to the runner, but an `export` of a variable the ssh command line never set exports
# NOTHING, so the runner silently falls back to its own default. An env var that has to survive four
# process boundaries (Mac shell -> gcloud ssh -> remote shell -> chain -> runner) must be named at
# each one. Round 19 names the FULL four-prompt gate scope here rather than relying on chain19's
# default, so the scope this window certified is in the window log and not only in a script.
#
# ── ROUND 19'S BUDGET, DECLARED BEFORE THE BOX IS STARTED (the round-9 lesson) ─────────────────
# Cap 90 min VM-on + 5 min grace, measured from `lastStartTimestamp`, less a 180 s stop margin.
# Costs are MEASURED, not estimated: round 18 put `chain7stage.sh` at 6 min 36 s and a 3-cell pp1024
# gate at 7 min 07 s (~142 s/cell); round 14 put pp256/pp1024 cells at ~110-117 s and its TRT
# re-serve at 2 min 45 s (serve READY after 72 s, three cells in 60 s).
#   boot + sshd probe + sync + launch                        ~6 min  ->   6
#   stage: fixtures proven identical + 101 GB convert + pin   ~7 min  ->  13
#   build (stock shim + R19_ctl + R19_def) + verify + twin    ~3 min  ->  16
#   smoke: SKIPPED (its `gegluv_armed` assertion is re-made    0 min  ->  16
#          for free against the gate's own first cell)
#   FULL-SCOPE gate, 11 cells over four shapes               ~26 min  ->  42
#   pp1024 bracket, 1 warm + 4 meas per slot + 1 close = 11  ~22 min  ->  64
#   pp256  bracket, same shape                               ~22 min  ->  86
#   same-session TRT-LLM re-serve, three cells                ~3 min  ->  89
# **Both brackets and the re-serve fit inside a 92 min usable horizon, with ~3 min of slack.**
#
# ── THE RE-SERVE WINDOW (CAP_MIN=75), WHICH IS WHAT ROUND 19 ACTUALLY RAN SECOND ───────────────
# Round 19's first window completed the FULL-SCOPE gate -- 11 cells, all four shapes, all_pass=True,
# 0 divergences, banked at ~/lever19/oracle_gate_R19_def.json with the arms at
# R19_def e4c6fbe26376f817 / R19_ctl c033fd2982dc6435 -- and then a greedy `.*scope=` in this chain's
# coverage counter matched `out_of_scope=none`, counted "1 of 4", and refused a gate that had passed.
# Re-running those 11 cells (~26 min) to re-derive a verdict already on disk would spend a third of a
# 75-min window, so the re-serve runs SKIP_GATE=1 + SKIP_BUILD=1, which RE-PROVE rather than trust:
# the coverage evaluator over the banked JSON, the 11 cells still on disk, R19_def's hash == the pinned
# gated hash (so the certification provably attaches to the binary being timed -- a rebuild would
# silently detach it, which is round 14's reason a mismatch is FATAL and not a warning), and
# `gegluv_armed = true` re-read from a banked gate cell. `mojo/` and `scripts/` are byte-identical
# between the gated commit 5f12d6f5 and the current head, so the pinned binary is exactly what this
# tree compiles and traceability is intact without a rebuild.
#   boot + sshd probe + sync + launch                        ~4 min  ->   4
#   stage: re-runs and RE-PROVES fixture identity against     ~7 min  ->  11
#          round 6's certified echoes (/tmp + /mnt/ramblob are tmpfs and died with the stop, so
#          SKIP_STAGE is NOT honoured on a fresh boot)
#   SKIP_BUILD re-verify (hashes + the runner's binary audit) ~1 min  ->  12
#   SKIP_GATE  re-verify (evaluator + cells + armed)         ~0 min  ->  12
#   pp1024 bracket, 1 warm + 4 meas per slot + 1 close = 11  ~22 min  ->  34
#   pp256  bracket, same shape                               ~22 min  ->  56
#   same-session TRT-LLM re-serve, three cells                ~3 min  ->  59
# **~59 min against a 77 min usable horizon (75 + 5 grace, less the 180 s stop margin): ~18 min of
# contingency**, which is the margin the first window's ~3 min did not have.
#
# THE FLIP LICENCE IS BOTH PROMPTS OR NOTHING, and the chain now enforces it mechanically rather than
# leaving it to a reader: REQUIRED_PROMPTS="pp1024 pp256", a prompt counts only if the runner logged
# `CELLGROUP <n> complete` AND a closing cell exists on disk (an incomplete bracket is unpublishable,
# not partial progress), and `FLIP_LICENSED` is written into CHAIN_EXIT. If the governor must drop
# pp256 for the clock, the answer is a REFUSAL -- because the published pp256 row (1.35x) would then
# describe a configuration that is no longer the shipped default, and a stale row on a flipped default
# is a docs-integrity defect, not a rounding nicety. The governor still declines rather than starts a
# bracket it cannot finish, and the TRT reserve stays protected.
# slack is thin, so the governor still decides from the clock: it walks pp1024 then pp256, prices
# n=4 per slot (n_reported=8) then n=3 (n_reported=6, the mission's floor), and **reserves both the
# 8 min TRT re-serve and the next prompt's minimum viable bracket before starting this one** — the
# reservation round 18's governor lacked. A shape that cannot FINISH is declined in the log, never
# started and abandoned, because a killed bracket is unpublishable while a declined one merely is not.
GATE_SPECS_FULL="pp256:/tmp/g3pp256/prompt_0000.txt pp1024:/tmp/g3pp1024/prompt_0000.txt val550:/tmp/g3race500/prompt_0000.txt rag4096:/tmp/g3rag/rag4096.txt"
log "governor: GATE_SPECS='${GATE_SPECS:-$GATE_SPECS_FULL}' (FULL SCOPE, four shapes)"
log "governor: MEAS_RUNS_CANDIDATES='${MEAS_RUNS_CANDIDATES:-4 3}' per slot (n_reported = 2x that)" \
    "TRT_RESERVE_MIN='${TRT_RESERVE_MIN:-8}' stop_margin=${STOP_MARGIN_S}s"
# The first post-sync harness call gets the same readiness probe: this is the ssh that has to
# succeed for the window to exist at all, and a 4003 here would look identical to a launch that
# never happened.
ssh_ready || { log "sshd lost after sync — stopping"; stop_vm; exit 7; }
gcloud compute ssh "$VM" --project="$PROJECT" --zone="$ZONE" --command \
  "CW_DEADLINE_EPOCH=$DEADLINE CAP_MIN=$CAP_MIN GRACE_MIN=$GRACE_MIN SAFETY_S=$STOP_MARGIN_S \
   DEF='${DEF:-R19_def}' CTL='${CTL:-R19_ctl}' TWIN='${TWIN:-R19_defB}' CELLTAG='${CELLTAG:-_r19}' \
   MEAS_RUNS_CANDIDATES='${MEAS_RUNS_CANDIDATES:-4 3}' TRT_RESERVE_MIN='${TRT_RESERVE_MIN:-8}' \
   GATE_SPECS='${GATE_SPECS:-$GATE_SPECS_FULL}' PROMPTS_ORDER='${PROMPTS_ORDER:-}' \
   WARM_RUNS='${WARM_RUNS:-1}' CLOSE_RUNS='${CLOSE_RUNS:-1}' \
   SKIP_SMOKE='${SKIP_SMOKE:-1}' CELL_S_RAG='${CELL_S_RAG:-140}' \
   CELL_S_PP1024='${CELL_S_PP1024:-122}' CELL_S_PP256='${CELL_S_PP256:-118}' \
   SKIP_STAGE='${SKIP_STAGE:-}' \
   SKIP_GATE='${SKIP_GATE:-}' SKIP_BUILD='${SKIP_BUILD:-}' \
   EXPECT_DEF_SHA='${EXPECT_DEF_SHA:-}' EXPECT_CTL_SHA='${EXPECT_CTL_SHA:-}' \
   REQUIRED_PROMPTS='${REQUIRED_PROMPTS:-}' \
   setsid nohup bash ~/g3r19/benchmarks/llm_smoke/nvidia_race/chain19.sh \
   </dev/null >~/lever19/chain19.out 2>&1 & disown; sleep 2; \
   echo LAUNCHED pid=\$(pgrep -f chain19.sh | head -1)" >>"$LOCAL_LOG" 2>&1
grep -q "LAUNCHED" "$LOCAL_LOG" || { log "no LAUNCHED marker — stopping"; stop_vm; exit 7; }
log "$(grep -m1 LAUNCHED "$LOCAL_LOG")"

# ── 4. WATCH ──────────────────────────────────────────────────────────────────────────────────
# Liveness comes from the heartbeat file the chain writes, not from holding an ssh session open: a
# watch that depends on the channel is the failure mode that cost round 17 five minutes twice.
last_hb=""
while true; do
  now=$(date +%s)
  hb=$(gcloud compute ssh "$VM" --project="$PROJECT" --zone="$ZONE" --command \
        "tail -2 ~/lever19/heartbeat.log 2>/dev/null; echo ---; \
         grep -cE 'PHASE .* rc=0' ~/lever19/round19.log 2>/dev/null; echo ---; \
         grep -m1 'GATE VERDICT FROM' ~/lever19/round19.log 2>/dev/null; echo ---; \
         grep -m1 'TRT re-serve JSONs copied' ~/lever19/round19.log 2>/dev/null; echo ---; \
         grep -m1 'CHAIN19 COMPLETE' ~/lever19/round19.log 2>/dev/null" 2>/dev/null | tr '\n' '|')
  [[ "$hb" != "$last_hb" ]] && log "hb: $hb"
  last_hb="$hb"
  if [[ "$hb" == *"CHAIN19 COMPLETE"* ]]; then log "chain reports COMPLETE"; break; fi
  if (( now + STOP_MARGIN_S >= DEADLINE )); then
    log "DEADLINE APPROACHING (stop margin ${STOP_MARGIN_S}s) — stopping the window now"
    break
  fi
  sleep "$POLL_S"
done

# ── 5. COLLECT, THEN STOP ─────────────────────────────────────────────────────────────────────
# Pull the artifacts BEFORE the stop: /tmp and /mnt/ramblob are tmpfs and die with it, and while
# ~/lever19 is on the persistent boot disk, having the window's evidence locally means the ledger
# can be written and audited without another billable start.
ART=/private/tmp/gemma_r19/artifacts
mkdir -p "$ART"
log "collecting artifacts -> $ART"
gcloud compute ssh "$VM" --project="$PROJECT" --zone="$ZONE" --command \
  "cd ~/lever19 && tar czf /tmp/r19art.tgz round19.log heartbeat.log chain19.out CHAIN_EXIT \
     chain7stage.log FIXTURES_OK gate_R19_def logs runs clocks *.json 2>/dev/null; \
     ls -l /tmp/r19art.tgz" >>"$LOCAL_LOG" 2>&1
# THREE ADDITIONS TO ROUND 18'S TAR LIST, each of which is evidence the report has to quote:
#   CHAIN_EXIT     the chain's fate as an artifact (rc, phase, gate_verdict, timing_complete,
#                  trt_reserve_done, cell counts). Round 18 added it and then did not collect it.
#   chain19.out    the nohup stdout, which is where a phase that died before its first log line
#                  leaves anything at all. Round 18's list named `chain18.log`, a file its own launch
#                  line never created — the redirect target is `.out` — so that slot collected nothing.
#   gate_R19_def   the FULL-SCOPE gate's own cells. `run_gemma3_round6_cells.sh` writes STAGE=gate
#                  output to `$MEAS/gate_<arm>/` precisely so gating a second arm cannot overwrite the
#                  first, which also means it is NOT under `runs/` and round 18's tar missed it. This
#                  round's primary deliverable is the gate, so its cells come home.
gcloud compute scp "$VM:/tmp/r19art.tgz" "$ART/r19art.tgz" --project="$PROJECT" --zone="$ZONE" \
  >>"$LOCAL_LOG" 2>&1 && (cd "$ART" && tar xzf r19art.tgz 2>/dev/null && log "artifacts extracted") \
  || log "WARNING: artifact collection incomplete — ~/lever19 still holds them on the boot disk"

stop_vm
log "WINDOW CLOSED. Local log: $LOCAL_LOG  Artifacts: $ART"
