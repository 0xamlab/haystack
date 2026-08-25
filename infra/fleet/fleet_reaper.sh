#!/usr/bin/env bash
# fleet_reaper.sh — keep the self-hosted macOS fleet snappy: reap orphaned
# Runner.Worker processes (jobs GitHub considers finished/cancelled but whose
# worker never released the slot — the "busy forever" zombie mode that wedged
# the fleet on 2026-08-24) and restart listeners that hold an assigned job but
# have no live worker.
#
# SAFETY: a worker is only killed when its runner has ZERO in_progress jobs on
# GitHub across every fleet-consuming repo. Any API error => no kills (fail
# closed), logged. Run under the com.thyn.fleet-reaper LaunchAgent (60s) or cron.
set -uo pipefail

ORG="${FLEET_REAPER_ORG:-thyn-ai}"
REPO_CACHE="/tmp/fleet-reaper-repos.txt"
# Ground truth must cover EVERY repo that can schedule onto the fleet, so derive
# the list from the org (cached 10min) instead of a hand-maintained repo list.
if [ ! -f "$REPO_CACHE" ] || [ $(( $(date +%s) - $(stat -f %m "$REPO_CACHE") )) -gt 600 ]; then
  gh api "orgs/$ORG/repos" --paginate --jq '.[].full_name' >"$REPO_CACHE" 2>/dev/null || true
fi
REPOS="${FLEET_REAPER_REPOS:-$(tr '\n' ' ' <"$REPO_CACHE" 2>/dev/null)}"
RUNNER_DIRS="${FLEET_REAPER_DIRS:-/Users/angel/Developer/actions-runner /Users/angel/actions-runner-mac /Users/angel/actions-runner-mac-2 /Users/angel/actions-runner-mac-3 /Users/angel/actions-runner-mac-4}"
LOG="${FLEET_REAPER_LOG:-$HOME/Library/Logs/thyn-fleet-reaper.log}"
STATUS="${FLEET_REAPER_STATUS:-/tmp/fleet-reaper-status.json}"
DRY_RUN="${FLEET_REAPER_DRY_RUN:-0}"
LISTENER_STUCK_SECS="${FLEET_REAPER_LISTENER_STUCK_SECS:-600}"

mkdir -p "$(dirname "$LOG")"
log() { echo "$(date '+%F %T') $*" >>"$LOG"; }

# ── 1. Ground truth: which runner names have a live (in_progress) job right now.
LIVE_FILE=$(mktemp)
API_OK=1
QUEUED_TOTAL=0
for repo in $REPOS; do
  err=$(mktemp)
  runs=$(gh run list --repo "$repo" --status in_progress --limit 25 --json databaseId --jq '.[].databaseId' 2>"$err") || {
    grep -q '404' "$err" || API_OK=0   # missing repo/disabled actions is fine; real API errors are not
    rm -f "$err"; continue; }
  rm -f "$err"
  q=$(gh run list --repo "$repo" --status queued --limit 25 --json databaseId --jq 'length' 2>/dev/null) || q=0
  QUEUED_TOTAL=$(( QUEUED_TOTAL + q ))
  for run_id in $runs; do
    gh api "repos/$repo/actions/runs/$run_id/jobs?per_page=100" \
      --jq '.jobs[] | select(.status=="in_progress") | "\(.runner_name // "none") \(.started_at)"' \
      >>"$LIVE_FILE" 2>/dev/null || API_OK=0
  done
done

if [ "$API_OK" != "1" ]; then
  log "SKIP cycle: GitHub API error — refusing to reap (fail closed)"
  echo "{\"ts\":\"$(date -u +%FT%TZ)\",\"api_ok\":false,\"reaped\":[]}" >"$STATUS"
  rm -f "$LIVE_FILE"; exit 0
fi

REAPED_NAMES=""
RESTARTED=""

for dir in $RUNNER_DIRS; do
  [ -d "$dir" ] || continue
  name=$(python3 -c "import json;print(json.load(open('$dir/.runner'))['agentName'])" 2>/dev/null) || continue
  workers=$(pgrep -f "$dir/bin/Runner.Worker" | tr '\n' ' ')
  n_workers=$(echo "$workers" | wc -w | tr -d ' ')
  live_lines=$(grep "^$name " "$LIVE_FILE" || true)

  if [ "$n_workers" -gt 0 ] && [ -z "$live_lines" ]; then
    # Zombie mode: worker alive, GitHub says this runner has no in_progress job.
    for pid in $workers; do
      log "REAP $name worker pid=$pid (no in_progress job on GitHub) dry_run=$DRY_RUN"
      if [ "$DRY_RUN" = "0" ]; then
        pkill -TERM -P "$pid" 2>/dev/null   # java/node/codeql children first
        kill -TERM "$pid" 2>/dev/null
        ( sleep 20; kill -9 "$pid" 2>/dev/null; pkill -9 -P "$pid" 2>/dev/null ) &
      fi
      REAPED_NAMES="$REAPED_NAMES\"$name:$pid\","
    done
  fi

  if [ "$n_workers" -gt 0 ] && [ -n "$live_lines" ]; then
    # Hung-job mode: GitHub shows an in_progress job older than 45min while EVERY
    # worker on this runner has burned <120s CPU => wedged dispatch (2026-08-24:
    # workers alive 40+min at ~0 CPU while main's queue starved). Reap so the
    # listener frees the slot; GitHub fails/requeues the orphaned job.
    oldest=$(echo "$live_lines" | awk '{print $2}' | sort | head -1)
    age=$(python3 -c "
from datetime import datetime, timezone
t=datetime.strptime('$oldest','%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
print(int((datetime.now(timezone.utc)-t).total_seconds()))" 2>/dev/null || echo 0)
    if [ "$age" -gt 2700 ]; then
      all_idle=1
      for pid in $workers; do
        cpu=$(ps -o time= -p "$pid" 2>/dev/null | python3 -c "
import re,sys
m=re.match(r'(?:(\d+):)?(\d+):(\d+)', sys.stdin.read().strip())
h,mm,ss=m.groups('0') if m else ('0','0','0')
print(int(h)*3600+int(mm)*60+int(ss))" 2>/dev/null || echo 99999)
        [ "$cpu" -ge 120 ] && all_idle=0
      done
      if [ "$all_idle" = "1" ]; then
        for pid in $workers; do
          log "REAP-HUNG $name worker pid=$pid (job age=${age}s, all workers cpu<120s) dry_run=$DRY_RUN"
          if [ "$DRY_RUN" = "0" ]; then
            pkill -TERM -P "$pid" 2>/dev/null
            kill -TERM "$pid" 2>/dev/null
            ( sleep 20; kill -9 "$pid" 2>/dev/null; pkill -9 -P "$pid" 2>/dev/null ) &
          fi
          REAPED_NAMES="$REAPED_NAMES\"$name:$pid(hung)\","
        done
      fi
    fi
  fi

  if [ "$n_workers" -eq 0 ] && [ "$QUEUED_TOTAL" -gt 0 ]; then
    # Idle-listener wedge: org has queued work but this runner spawns no worker
    # (listener stuck, 2026-08-24: 4 of 5 idle while queues drained at 1 worker).
    # Grace 300s so normal between-job gaps never trigger a restart.
    idle_file="/tmp/fleet-reaper-idle-$name"
    if [ -f "$idle_file" ]; then
      since=$(cat "$idle_file" 2>/dev/null || date +%s)
      if [ $(( $(date +%s) - since )) -gt 300 ]; then
        log "RESTART-IDLE $name (org queued=$QUEUED_TOTAL, idle>300s) dry_run=$DRY_RUN"
        if [ "$DRY_RUN" = "0" ]; then
          ( cd "$dir" && ./svc.sh stop >>"$LOG" 2>&1; ./svc.sh start >>"$LOG" 2>&1 )
          RESTARTED="$RESTARTED\"$name(idle)\","
        fi
        rm -f "$idle_file"
      fi
    else
      date +%s > "$idle_file"
    fi
  else
    rm -f "/tmp/fleet-reaper-idle-$name" 2>/dev/null
  fi

  if [ "$n_workers" -eq 0 ] && [ -n "$live_lines" ]; then
    # Listener holds an assigned job but no worker exists: restart after grace.
    oldest=$(echo "$live_lines" | awk '{print $2}' | sort | head -1)
    age=$(python3 -c "
from datetime import datetime, timezone
import sys
t=datetime.strptime('$oldest','%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
print(int((datetime.now(timezone.utc)-t).total_seconds()))" 2>/dev/null || echo 0)
    if [ "$age" -gt "$LISTENER_STUCK_SECS" ]; then
      log "RESTART-LISTENER $name (job age=${age}s, no worker) dry_run=$DRY_RUN"
      if [ "$DRY_RUN" = "0" ]; then
        ( cd "$dir" && ./svc.sh stop >>"$LOG" 2>&1; ./svc.sh start >>"$LOG" 2>&1 )
        RESTARTED="$RESTARTED\"$name\","
      fi
    fi
  fi
done

rm -f "$LIVE_FILE"
echo "{\"ts\":\"$(date -u +%FT%TZ)\",\"api_ok\":true,\"reaped\":[${REAPED_NAMES%,}],\"restarted\":[${RESTARTED%,}]}" >"$STATUS"
log "cycle done reaped=[${REAPED_NAMES%,}] restarted=[${RESTARTED%,}]"
