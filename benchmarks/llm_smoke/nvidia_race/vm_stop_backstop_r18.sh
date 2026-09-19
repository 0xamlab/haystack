#!/bin/bash
# vm_stop_backstop_r18.sh — RUN THIS ON THE LOCAL MAC, IN ITS OWN SESSION. The last-resort owner of
# the stop. It does ONE thing: make sure the race VM ends up TERMINATED, and it does that even if
# every other manager is dead.
#
# WHY THIS EXISTS, FROM ROUND 18'S ACTUAL EVENTS. The window controller `vm_window_r18.sh` owns the
# stop and retries it — but it is a single process, and round 18 killed it three times
# (18:38:35Z, 19:20:56Z, ~20:24Z, all `kill -TERM -- -<PGID>` issued by the operating agent to
# recover from harness defects). Two of those kills took the whole process GROUP with them, and on
# the first one the controller's own EXIT trap was mid-`stop_vm` when the follow-up SIGKILL landed,
# so `gcloud compute instances stop` had already returned
#   "ERROR: Instance has in progress persistent disk IO and cannot be suspended/stopped at this time."
# and NOTHING retried it. The box sat RUNNING and unowned until it was stopped by hand at 18:30:45Z.
# That is the owner's hardest mandate — no race VM outlives its task — failing in the one situation
# where it matters most: when the operator is busy fixing something else.
#
# So the stop gets a SECOND owner that shares no process group with anything. Launch it with
# `launch_detached` below (or any equivalent that calls setsid(2)) so `kill -- -PGID` on the
# controller cannot reach it, and so it outlives a terminal hangup.
#
# IT IS DELIBERATELY STUPID. No staging, no gates, no governor, no opinion about what the window
# should be doing. It polls, and it stops the box when either (a) the deadline arrives, or (b) the
# chain has exited WITHOUT completing timing and the box is idle — because a dead chain with a live
# GPU is pure burn. A clever backstop is a backstop that can be argued out of acting.
#
# Usage:
#   bash vm_stop_backstop_r18.sh --deadline <epoch> [--poll 60] [--idle-grace 300] [--max-min 150]
# Launch detached (macOS has no setsid(1), so go through the libc call):
#   python3 -c 'import os,sys; os.setsid(); os.execv("/bin/bash",["bash"]+sys.argv[1:])' \
#     vm_stop_backstop_r18.sh --deadline 1789850458
set -uo pipefail

VM=${VM:-trtllm-gemma-us-west1-c}
ZONE=${ZONE:-us-west1-c}
PROJECT=${PROJECT:-eplanev2}
GPU=${GPU:-1}
DEADLINE=0
POLL_S=60
IDLE_GRACE_S=300      # chain dead + GPU idle for this long => stop early, do not wait for DEADLINE
MAX_MIN=150           # absolute self-limit, so a mis-set deadline cannot run this forever
# LEVER_DIR is the round's artifact dir on the VM's PERSISTENT boot disk, i.e. where CHAIN_EXIT
# lives. It was named L18 historically; the alias keeps every existing caller byte-compatible
# while letting a later round say what it means. Round 19 passes /home/angel/lever19.
LEVER_DIR=${LEVER_DIR:-${L18:-/home/angel/lever18}}
L18="$LEVER_DIR"
# CHAIN_PAT is the "is anything still working?" liveness pattern, and its DEFAULT COVERS EVERY
# ROUND rather than naming one. A backstop whose pattern does not match the chain actually running
# reads a BUSY window as a dead one and stops it early — the exact failure this script exists to
# prevent, arriving from the opposite direction.
#
# EVERY ALTERNATIVE IS BRACKET-MASKED SO THE PATTERN CANNOT MATCH ITSELF, and round 19 measured what
# happens when one is not. `pgrep -f` matches against the whole command line, and the command line
# that CARRIES this pattern is the probe's own `ssh ... --command "... pgrep -c -f '<pattern>' ..."`.
# A literal `driver_ctx8192` in the pattern therefore matches the probe itself, so the count can never
# reach 0. Observed on the box: `chain_procs=1` on every single probe from 22:37:45Z to 23:00:21Z and
# beyond, ~30 minutes after the chain had exited at 22:29:38Z, with the GPU idle at 0% the whole time.
# Both arms of the early-stop test were then permanently disabled at once — `alive == 0` could never
# be true, and `util == 0 && alive == 0` with it — so an idle spot 8xH200 billed to the DEADLINE. The
# chain's existing rounds already bracket-mask their own names (`chain18[.]sh`) for precisely this
# reason, which `run_gemma3_round6_cells.sh`'s `quiesce` documents as "pgrep matching its own caller";
# `driver_ctx8192` was the one alternative nobody masked. So: `driver_ctx819[2]`. The mask costs
# nothing — the ERE still matches the real process — and it makes a zero count reachable again.
CHAIN_PAT=${CHAIN_PAT:-'chain[0-9]*[.]sh|run_ab_gemma3_round[0-9]*[.]sh|driver_ctx819[2]'}
LOG=${LOG:-/private/tmp/gemma_r18/backstop18.log}
GCLOUD=${GCLOUD:-gcloud}     # overridable so the dry-run can substitute a stub

while (( $# > 0 )); do
  case "$1" in
    --deadline) DEADLINE="$2"; shift 2 ;;
    --poll) POLL_S="$2"; shift 2 ;;
    --idle-grace) IDLE_GRACE_S="$2"; shift 2 ;;
    --max-min) MAX_MIN="$2"; shift 2 ;;
    *) echo "unknown arg $1" >&2; exit 2 ;;
  esac
done
if (( DEADLINE <= 0 )); then
  echo "FATAL: --deadline <epoch> is required; refusing to run a backstop with no deadline" >&2
  exit 2
fi
mkdir -p "$(dirname "$LOG")"
ts() { date -u +%FT%TZ; }
# pgid, NOT sid: macOS `ps` has no `sid`/`sess` keyword, and asking for one makes it print its
# entire keyword table instead of failing quietly — which the dry-run duly captured into every log
# line. The property that actually matters here is the process GROUP (that is what
# `kill -- -PGID` reaches), and pgid is supported on both macOS and the Linux VM.
log() { echo "[$(ts)] backstop(pid=$$,pgid=$(ps -o pgid= -p $$ 2>/dev/null | tr -d ' ')) $*" | tee -a "$LOG"; }

status() { $GCLOUD compute instances describe "$VM" --project="$PROJECT" --zone="$ZONE" \
             --format='value(status)' 2>/dev/null || echo UNKNOWN; }

# THE STOP, RETRIED UNTIL VERIFIED. Round 18 proved a single attempt is not enough: GCE refuses to
# stop an instance with persistent-disk IO in flight, which is exactly the state a freshly booted or
# just-checkpointed box is in. A refused stop is not a stop.
do_stop() { # $1 = reason
  local i st
  log "STOP REQUESTED ($1)"
  for i in 1 2 3 4 5 6 7 8; do
    st=$(status)
    if [[ "$st" == "TERMINATED" ]]; then
      log "TERMINATED confirmed on attempt $i"
      break
    fi
    log "  attempt $i/8 status=$st"
    $GCLOUD compute instances stop "$VM" --project="$PROJECT" --zone="$ZONE" \
      --discard-local-ssd=false >>"$LOG" 2>&1
    sleep 20
  done
  st=$(status)
  local run
  run=$($GCLOUD compute instances list --project="$PROJECT" --filter='status=RUNNING' \
        --format='value(name,zone,status)' 2>/dev/null)
  if [[ "$st" == "TERMINATED" && -z "$run" ]]; then
    log "BACKSTOP_DONE: instance TERMINATED and project-wide status=RUNNING is EMPTY"
    return 0
  fi
  log "BACKSTOP_FAILED: status=$st running=[$run] — STOP IT BY HAND:"
  log "  gcloud compute instances stop $VM --project=$PROJECT --zone=$ZONE --discard-local-ssd=false"
  return 1
}

# Is the box doing real work? GPU utilisation plus a live chain/driver process, read over one cheap
# ssh. Any error is treated as "unknown", and unknown never triggers the EARLY stop — only the
# deadline does. A backstop that acts on a failed probe would stop a healthy window.
idle_and_chain_dead() {
  local out util alive
  out=$($GCLOUD compute ssh "$VM" --project="$PROJECT" --zone="$ZONE" --command \
    "nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits -i $GPU 2>/dev/null | head -1; \
     echo SEP; pgrep -c -f '$CHAIN_PAT' 2>/dev/null || echo 0; \
     echo SEP; cat $L18/CHAIN_EXIT 2>/dev/null | tr '\n' ' '" 2>/dev/null) || return 1
  [[ -z "$out" ]] && return 1
  util=$(echo "$out" | sed -n '1p' | tr -dc '0-9')
  alive=$(echo "$out" | sed -n '3p' | tr -dc '0-9')
  local fate; fate=$(echo "$out" | sed -n '5p')
  [[ -z "$util" || -z "$alive" ]] && return 1
  log "  probe: gpu_util=${util}% chain_procs=$alive CHAIN_EXIT=[${fate}]"
  # a recorded chain exit with timing_complete=no is the unambiguous case: the chain is gone and the
  # measurement never finished, so every further second is burn.
  if [[ "$fate" == *"timing_complete=no"* && "$alive" == "0" ]]; then
    log "  chain exited WITHOUT completing timing and nothing is running"
    return 0
  fi
  (( util == 0 && alive == 0 )) && return 0
  return 1
}

log "ARMED vm=$VM zone=$ZONE project=$PROJECT deadline=$DEADLINE ($(date -u -r "$DEADLINE" +%FT%TZ 2>/dev/null || echo '?'))" \
    "poll=${POLL_S}s idle_grace=${IDLE_GRACE_S}s max_min=$MAX_MIN"
# Both of these are recorded because both silently decide whether the backstop acts: a wrong
# LEVER_DIR means CHAIN_EXIT is never read (only the deadline can then stop the box), and a wrong
# CHAIN_PAT means a busy window can look idle. Neither is inferable from the log after the fact.
log "      lever_dir=$L18 chain_pat=[$CHAIN_PAT]"
START=$(date +%s)
idle_since=0
while true; do
  now=$(date +%s)
  st=$(status)
  if [[ "$st" == "TERMINATED" ]]; then
    log "instance already TERMINATED — nothing for the backstop to do; exiting"
    exit 0
  fi
  if (( now >= DEADLINE )); then
    do_stop "DEADLINE reached (epoch $DEADLINE)"; exit $?
  fi
  if (( (now - START) / 60 >= MAX_MIN )); then
    do_stop "backstop self-limit ${MAX_MIN}min reached — the deadline was probably mis-set"; exit $?
  fi
  if idle_and_chain_dead; then
    (( idle_since == 0 )) && idle_since=$now
    log "  idle for $(( now - idle_since ))s of ${IDLE_GRACE_S}s grace"
    if (( now - idle_since >= IDLE_GRACE_S )); then
      do_stop "chain dead and GPU idle for ${IDLE_GRACE_S}s — tail is pure burn"; exit $?
    fi
  else
    idle_since=0
  fi
  sleep "$POLL_S"
done
