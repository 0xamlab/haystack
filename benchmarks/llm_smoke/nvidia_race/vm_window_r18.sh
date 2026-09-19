#!/bin/bash
# vm_window_r18.sh — RUN THIS ON THE LOCAL MAC. The round-18 VM window controller: it OWNS the cap
# and it OWNS the stop. Everything else in the round runs inside the window this opens.
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
#   sync     vm_sync_r18.sh — tar+scp the committed tree, refusing a dirty or unpushed one.
#   launch   chain18.sh under `setsid nohup ... </dev/null & disown`. THE CHANNEL MUST NOT BE
#            INHERITED: round 17 lost 2 x 300 s to two ssh calls hanging client-side because a
#            backgrounded remote process held the channel open, while the jobs had in fact launched.
#   watch    poll the heartbeat file every 60 s and echo it locally, so liveness is observable
#            without an extra ssh round trip per check and a wedged phase is visible within a minute.
#   stop     issued at min(deadline, chain-complete) + STOP_MARGIN. ALWAYS issued: on success, on
#            failure, on timeout, and on Ctrl-C (trap). `--discard-local-ssd=false` so ~/lever18,
#            ~/lever3, ~/adj and the certified gate echoes survive for the next round.
#   verify   the instance must report TERMINATED and a project-wide `--filter='status=RUNNING'`
#            must come back EMPTY. Both are printed, because "I stopped it" is a claim and the
#            owner's standing mandate is that no race VM is left running after its task ends.
#
# Usage:
#   bash vm_window_r18.sh                 # full window
#   DRY_RUN=1 bash vm_window_r18.sh       # compute the plan and the deadline, touch nothing
set -uo pipefail

VM=${VM:-trtllm-gemma-us-west1-c}
ZONE=${ZONE:-us-west1-c}
PROJECT=${PROJECT:-eplanev2}
CAP_MIN=${CAP_MIN:-90}          # the owner's hard cap on VM-ON time
GRACE_MIN=${GRACE_MIN:-5}       # ... plus grace, for the stop to land
STOP_MARGIN_S=${STOP_MARGIN_S:-180}   # issue the stop this far BEFORE the deadline
START_TRIES=${START_TRIES:-2}
POLL_S=${POLL_S:-60}
WT=${WT:-/Users/angel/Developer/decision-engine/.qwen/worktrees/gemma-r18}
NR="$WT/benchmarks/llm_smoke/nvidia_race"
LOCAL_LOG=${LOCAL_LOG:-/private/tmp/gemma_r18/window18.log}
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
if ! WT="$WT" PREFLIGHT_ONLY=1 bash "$NR/vm_sync_r18.sh" 2>&1 | tee -a "$LOCAL_LOG"; then
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
  log "DRY_RUN: would start, sync, launch chain18.sh, watch, then stop. Touching nothing."
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
BACKSTOP_LOG=${BACKSTOP_LOG:-/private/tmp/gemma_r18/backstop18.log}
if [[ "${BACKSTOP:-1}" == "1" ]]; then
  LOG="$BACKSTOP_LOG" GCLOUD=gcloud \
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
  if WT="$WT" VM="$VM" ZONE="$ZONE" PROJECT="$PROJECT" bash "$NR/vm_sync_r18.sh" >>"$LOCAL_LOG" 2>&1; then
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
log "launching chain18.sh under setsid+nohup, stdin /dev/null, disowned"
# EVERY GOVERNOR KNOB IS PASSED ON THIS LINE, EXPLICITLY. This is a bug that was caught before it
# cost a bracket rather than after: `chain18.sh` `export`s GATE_SPECS / PROMPTS_ORDER / WARM_RUNS /
# CLOSE_RUNS to the runner, but an `export` of a variable the ssh command line never set exports
# NOTHING, so the runner silently falls back to its own default. The default gate scope is two
# prompts (~10.5 min) where this round's budget needs one (~6 min), and at ~41 min for an n=5
# rag4096 bracket against a ~75 min horizon that 4.5 min is the difference between the governor
# STARTING the bracket and DECLINING it. An env var that has to survive three process boundaries
# (Mac shell -> gcloud ssh -> remote shell -> chain -> runner) must be named at each one.
log "governor: MEAS_RUNS_CANDIDATES='${MEAS_RUNS_CANDIDATES:-5}' GATE_SPECS='${GATE_SPECS:-<runner default>}' stop_margin=${STOP_MARGIN_S}s"
# The first post-sync harness call gets the same readiness probe: this is the ssh that has to
# succeed for the window to exist at all, and a 4003 here would look identical to a launch that
# never happened.
ssh_ready || { log "sshd lost after sync — stopping"; stop_vm; exit 7; }
gcloud compute ssh "$VM" --project="$PROJECT" --zone="$ZONE" --command \
  "CW_DEADLINE_EPOCH=$DEADLINE CAP_MIN=$CAP_MIN GRACE_MIN=$GRACE_MIN SAFETY_S=$STOP_MARGIN_S \
   MEAS_RUNS_CANDIDATES='${MEAS_RUNS_CANDIDATES:-5}' \
   GATE_SPECS='${GATE_SPECS:-}' PROMPTS_ORDER='${PROMPTS_ORDER:-}' \
   WARM_RUNS='${WARM_RUNS:-}' CLOSE_RUNS='${CLOSE_RUNS:-}' \
   SKIP_SMOKE='${SKIP_SMOKE:-}' CELL_S_RAG='${CELL_S_RAG:-}' CELL_S_PP1024='${CELL_S_PP1024:-}' \
   SKIP_STAGE='${SKIP_STAGE:-}' \
   setsid nohup bash ~/g3r18/benchmarks/llm_smoke/nvidia_race/chain18.sh \
   </dev/null >~/lever18/chain18.out 2>&1 & disown; sleep 2; \
   echo LAUNCHED pid=\$(pgrep -f chain18.sh | head -1)" >>"$LOCAL_LOG" 2>&1
grep -q "LAUNCHED" "$LOCAL_LOG" || { log "no LAUNCHED marker — stopping"; stop_vm; exit 7; }
log "$(grep -m1 LAUNCHED "$LOCAL_LOG")"

# ── 4. WATCH ──────────────────────────────────────────────────────────────────────────────────
# Liveness comes from the heartbeat file the chain writes, not from holding an ssh session open: a
# watch that depends on the channel is the failure mode that cost round 17 five minutes twice.
last_hb=""
while true; do
  now=$(date +%s)
  hb=$(gcloud compute ssh "$VM" --project="$PROJECT" --zone="$ZONE" --command \
        "tail -2 ~/lever18/heartbeat.log 2>/dev/null; echo ---; \
         grep -cE 'PHASE .* rc=0' ~/lever18/round18.log 2>/dev/null; echo ---; \
         grep -m1 'CHAIN18 COMPLETE' ~/lever18/round18.log 2>/dev/null" 2>/dev/null | tr '\n' '|')
  [[ "$hb" != "$last_hb" ]] && log "hb: $hb"
  last_hb="$hb"
  if [[ "$hb" == *"CHAIN18 COMPLETE"* ]]; then log "chain reports COMPLETE"; break; fi
  if (( now + STOP_MARGIN_S >= DEADLINE )); then
    log "DEADLINE APPROACHING (stop margin ${STOP_MARGIN_S}s) — stopping the window now"
    break
  fi
  sleep "$POLL_S"
done

# ── 5. COLLECT, THEN STOP ─────────────────────────────────────────────────────────────────────
# Pull the artifacts BEFORE the stop: /tmp and /mnt/ramblob are tmpfs and die with it, and while
# ~/lever18 is on the persistent boot disk, having the window's evidence locally means the ledger
# can be written and audited without another billable start.
ART=/private/tmp/gemma_r18/artifacts
mkdir -p "$ART"
log "collecting artifacts -> $ART"
gcloud compute ssh "$VM" --project="$PROJECT" --zone="$ZONE" --command \
  "cd ~/lever18 && tar czf /tmp/r18art.tgz round18.log heartbeat.log chain18.log \
     chain7stage.log logs runs clocks *.json 2>/dev/null; ls -l /tmp/r18art.tgz" >>"$LOCAL_LOG" 2>&1
gcloud compute scp "$VM:/tmp/r18art.tgz" "$ART/r18art.tgz" --project="$PROJECT" --zone="$ZONE" \
  >>"$LOCAL_LOG" 2>&1 && (cd "$ART" && tar xzf r18art.tgz 2>/dev/null && log "artifacts extracted") \
  || log "WARNING: artifact collection incomplete — ~/lever18 still holds them on the boot disk"

stop_vm
log "WINDOW CLOSED. Local log: $LOCAL_LOG  Artifacts: $ART"
