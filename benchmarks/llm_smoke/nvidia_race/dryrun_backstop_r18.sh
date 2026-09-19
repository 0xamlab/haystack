#!/bin/bash
# dryrun_backstop_r18.sh — LOCAL PROOF, no VM and no gcloud, that vm_stop_backstop_r18.sh survives
# the death of everything that launched it and still issues the stop.
#
# Claim under test: the backstop runs in its OWN SESSION (setsid), so `kill -KILL -- -<PGID>`
# against the window controller's process group cannot reach it, and it then stops the instance on
# its own. Round 18 lost exactly this property — killing the controller's group killed its EXIT trap
# mid-`stop_vm`, and the box stayed RUNNING until stopped by hand.
#
# TWO HARNESS BUGS THIS VERSION FIXES, both of which made the first cut prove nothing:
#   * the controller was started with a plain `&`, which in a non-interactive script does NOT create
#     a new process group, so the group-kill killed the TEST (exit 137). Now started via setsid too,
#     and the test REFUSES to kill anything if the controller's pgid equals its own.
#   * `PATH='<stub>:$PATH'` was single-quoted inside a double-quoted string, so PATH became the stub
#     dir alone and `ps`/`sleep`/`tr`/`cut` all vanished — the backstop then "died" for want of
#     `sleep`, not for want of session isolation. The environment is now exported to python3 and
#     inherited through execv, which needs no quoting at all.
set -uo pipefail
# SB is overridable so a later round can dry-run the SAME backstop against its own worktree without
# writing into round 18's artifact dir. The stub gcloud reads it from the environment rather than
# from a baked-in path, which is what makes the override actually take effect inside the stub.
SB=${SB:-/private/tmp/gemma_r18/sandbox}
export SB
CHAIN_TAG=${CHAIN_TAG:-chain18}
export CHAIN_TAG
rm -rf "$SB"; mkdir -p "$SB/bin"
NR=${NR:-/Users/angel/Developer/decision-engine/.qwen/worktrees/gemma-r18/benchmarks/llm_smoke/nvidia_race}

cat > "$SB/bin/gcloud" <<'STUB'
#!/bin/bash
SB=${SB:-/private/tmp/gemma_r18/sandbox}
CHAIN_TAG=${CHAIN_TAG:-chain18}
LOG=$SB/gcloud_calls.log
STATE=$SB/state
echo "$(date -u +%FT%TZ) gcloud $*" >> "$LOG"
case "$1 $2 $3" in
  "compute instances describe")
    if [[ "$(cat "$STATE" 2>/dev/null)" == "TERMINATED" ]]; then echo TERMINATED; else echo RUNNING; fi ;;
  "compute instances stop")   echo TERMINATED > "$STATE"; echo "Stopping instance(s)... done." ;;
  "compute instances list")
    if [[ "$(cat "$STATE" 2>/dev/null)" == "TERMINATED" ]]; then echo ""; else echo "vm us-west1-c RUNNING"; fi ;;
  "compute instances start")  echo RUNNING > "$STATE" ;;
  "compute ssh "*)
    printf '0\nSEP\n0\nSEP\n%s_exit_utc=2026-09-19T19:36:21Z rc=1 phase=gate timing_complete=no\n' "$CHAIN_TAG" ;;
esac
exit 0
STUB
chmod +x "$SB/bin/gcloud"
echo RUNNING > "$SB/state"

cat > "$SB/controller.sh" <<CTRL
#!/bin/bash
set -uo pipefail
CPG=\$(ps -o pgid= -p \$\$ | tr -d ' ')
echo "CONTROLLER_PID=\$\$" > "$SB/controller.info"
echo "CONTROLLER_PGID=\$CPG" >> "$SB/controller.info"
python3 -c 'import os,sys; os.setsid(); os.execv("/bin/bash",["bash"]+sys.argv[1:])' \\
  "$NR/vm_stop_backstop_r18.sh" --deadline "\$1" --poll 3 --idle-grace 6 --max-min 5 \\
  >>"$SB/backstop_stdout.log" 2>&1 &
echo "BACKSTOP_PID=\$!" >> "$SB/controller.info"
sleep 2
ps -o pid=,pgid=,sid= -p "\$!" 2>/dev/null | awk '{print "BACKSTOP_PGID="\$2" BACKSTOP_SID="\$3}' \\
  >> "$SB/controller.info"
sleep 600
CTRL
chmod +x "$SB/controller.sh"

DEADLINE=$(( $(date +%s) + 120 ))
export PATH="$SB/bin:$PATH" GCLOUD="$SB/bin/gcloud" LOG="$SB/backstop.log"
python3 -c 'import os,sys; os.setsid(); os.execv("/bin/bash",["bash"]+sys.argv[1:])' \
  "$SB/controller.sh" "$DEADLINE" &
CPID=$!
sleep 7
echo "=== controller.info ==="; cat "$SB/controller.info"
get() { sed -n "s/^$1=//p" "$SB/controller.info" | head -1; }
CPGID=$(get CONTROLLER_PGID); BPID=$(get BACKSTOP_PID)
BPGID=$(get BACKSTOP_PGID); BSID=$(get BACKSTOP_SID)
SELF=$(ps -o pgid= -p $$ | tr -d ' ')
echo "=== test pgid=$SELF  controller pgid=$CPGID  backstop pid=$BPID pgid=$BPGID sid=$BSID ==="
if [[ -z "$CPGID" || "$CPGID" == "$SELF" ]]; then
  echo "TEST HARNESS BUG: controller shares the test's pgid — refusing to kill"; exit 2
fi
if [[ "$BPGID" == "$CPGID" ]]; then
  echo "ISOLATION FAILED: the backstop is IN the controller's process group ($BPGID)"; exit 1
fi
echo "ISOLATION OK: backstop pgid=$BPGID sid=$BSID differs from controller pgid=$CPGID"
echo "=== SIGKILL the controller's whole process group (pgid=$CPGID) ==="
kill -KILL -- "-$CPGID" 2>/dev/null
sleep 2
if ps -p "$BPID" >/dev/null 2>&1; then
  echo "SURVIVED: backstop pid=$BPID alive after kill -9 of the controller's group"
else
  echo "FAILED: backstop died with the controller"; exit 1
fi
echo "=== waiting for the backstop to act on the idle + chain-dead probe ==="
for i in $(seq 1 16); do
  sleep 3
  grep -q "BACKSTOP_DONE\|BACKSTOP_FAILED" "$SB/backstop.log" 2>/dev/null && break
done
echo "=== backstop log ==="; tail -12 "$SB/backstop.log" 2>/dev/null
echo "=== stub instance state (want TERMINATED) ==="; cat "$SB/state"
echo "=== stop calls recorded by the stub ==="; grep -c "instances stop" "$SB/gcloud_calls.log"
ok=1
grep -q "BACKSTOP_DONE" "$SB/backstop.log" 2>/dev/null || { echo "NO BACKSTOP_DONE"; ok=0; }
[[ "$(cat "$SB/state")" == "TERMINATED" ]] || { echo "STATE NOT TERMINATED"; ok=0; }
kill -KILL "$BPID" 2>/dev/null
if (( ok == 1 )); then
  echo "DRY_RUN_VERDICT: PASS — the backstop survives the controller's group-kill and stops the box"
else
  echo "DRY_RUN_VERDICT: FAIL"; exit 1
fi
