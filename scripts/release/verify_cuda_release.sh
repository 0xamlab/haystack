#!/bin/bash
# verify_cuda_release.sh — RUN THIS ON THE LOCAL MAC. The CUDA RELEASE-VERIFY window controller: it
# owns the cap, it owns the stop, and it owns the refusal. It turns a CUDA wheel that CI only
# COMPILED into a wheel that has been RUN-VERIFIED on real hardware, by running the campaign's
# standing gates against the wheel's own binaries and emitting `cuda-release-verdict.json`.
#
# WHY IT IS AN OPERATOR SCRIPT AND NOT A CI JOB. CI has no GPU anywhere, and the wheel it builds is
# launch-unverified by construction (see `.github/workflows/build-runtime.yml`'s build-linux-cuda
# comment). This script is the missing leg: a human or an agent runs it during an authorised VM
# window, and `publish-pypi`'s release-verify gate then decides from the verdict it produced. The
# controller/battery split mirrors the campaign's own (vm_window_r19.sh + chain19.sh): the cap is
# VM-ON time measured from `lastStartTimestamp`, which includes ~4 min of boot+ssh that no in-VM
# script can observe, so the deadline has to be computed HERE and pushed in — and the stop has to be
# issued from here too, because a VM that is busy measuring cannot be relied on to stop itself.
#
# WHAT IT CERTIFIES, AND WHAT IT DOES NOT. A verdict from this script says: THIS wheel's binaries
# launched on ONE H200 box, passed the full-scope oracle gate (G0 16/16 at pp256/pp1024/val550, G1
# 64/64 with 2/2 bit-identical determinism repeats, rag4096 22/22 + an EOS-stop corroborated by the
# reference) at clocks pinned 1410 MHz with offpin=0 on every cell, and answered the conformance CLI
# for the cuda backend. It is NOT a benchmark win, NOT a multi-hardware or multi-driver
# certification, and NOT a claim about any other host.
#
# THE ONE THING IT MEASURES THAT THE RACE NEVER DID: the gates run against the WHEEL, not against a
# race arm. The campaign's cells are driven by `gemma3_batched_cuda` binaries built on the VM; those
# are a different program from the shipped runtime (a single linked driver vs 27 bounded workers
# built from mojo/engine/main.mojo, --mcpu x86-64-v3, stripped, signed). Certifying a race arm says
# nothing about what a user installs — which is exactly the gap between the advertised kernel
# inventory and the shippable surface. So this battery installs the wheel, points
# ALGENTA_NATIVE_WORKER at the binary that came out of it, and drives the SHIPPED path
# (`algenta.inference.decode`) through `scripts/release/wheel_gate_cells.py`.
#
# REFUSALS (rc != 0, and NO verdict is written or copied): any gate cell failing, any clock or offpin
# deviation, any conformance refusal that is not a typed out-of-table refusal, and any wheel-hash
# mismatch — checked TWICE, before the start (local) and after the scp (on the box), because a
# verdict must name the bytes that were actually tested.
#
# PHASES
#   preflight  every LOCAL precondition, while the VM is still TERMINATED and costs nothing: the
#              wheel exists and hashes, the worktree is clean and pushed, gcloud is on PATH. A local
#              refusal must never cost VM-on minutes (round 18 booted the box and then died on an
#              untracked `mojo_env/.pixi` symlink, burning the boot).
#   start      gcloud compute instances start, up to START_TRIES; TWO CONSECUTIVE SPOT STOCKOUTS
#              abort rather than burn retries against a zone with no capacity (the owner's rule).
#   sync       tar+scp the tree subset the battery needs, then the wheel separately, then RE-HASH the
#              wheel on the box and refuse on mismatch.
#   arm        the independent stop backstop, in its own session, BEFORE anything else can fail.
#   launch     the battery under `setsid nohup ... </dev/null & disown`. THE CHANNEL MUST NOT BE
#              INHERITED: round 17 lost 2 x 300 s to ssh calls hanging client-side because a
#              backgrounded remote process held the channel open.
#   watch      poll the heartbeat file, so liveness is observable without holding a channel open.
#   collect    verdict + cells + clocks, BEFORE the stop (/tmp and /mnt/ramblob are tmpfs).
#   stop       retried until the instance reports TERMINATED, then the project-wide RUNNING check.
#              ALWAYS issued: on success, on failure, on timeout, and on Ctrl-C (trap).
#
# Usage:
#   bash scripts/release/verify_cuda_release.sh --wheel /path/to/algenta_runtime_native-*.whl
#   DRY_RUN=1 bash scripts/release/verify_cuda_release.sh --wheel <whl>   # plan + deadline, touch nothing
set -uo pipefail

VM=${VM:-trtllm-gemma-us-west1-c}
ZONE=${ZONE:-us-west1-c}
PROJECT=${PROJECT:-eplanev2}
REPO=${REPO:-thyn-ai/algenta}   # only ever printed, in the "what to do with the verdict" hint
GPU=${GPU:-1}
CAP_MIN=${CAP_MIN:-60}          # the owner's standing hard cap on VM-ON time. The battery budget at
                                # the bottom of verify_cuda_release_battery.sh is priced against this.
GRACE_MIN=${GRACE_MIN:-5}       # ... plus grace, for the stop to land
STOP_MARGIN_S=${STOP_MARGIN_S:-180}   # issue the stop this far BEFORE the deadline
START_TRIES=${START_TRIES:-2}
POLL_S=${POLL_S:-60}
SSH_TRIES=${SSH_TRIES:-10}
SSH_WAIT_S=${SSH_WAIT_S:-30}
WT=${WT:-$(cd "$(dirname "$0")/../.." && pwd)}
REMOTE_DIR=${REMOTE_DIR:-cuda_rel_verify}
WORK=${WORK:-/home/angel/cuda_rel_verify_work}
LOCAL_LOG=${LOCAL_LOG:-/private/tmp/cuda_release_verify/window.log}
WHEEL=""
DRY_RUN=${DRY_RUN:-0}

# ── EVERY KNOB THE BATTERY READS IS DECLARED HERE, ONCE, IN THE CONTROLLER ─────────────────────
# Declaring them at the top rather than inline on the launch line is what makes the launch line
# auditable: this file's own header warns that "an env var that has to survive four process
# boundaries must be named at each one", and the first-run defect this block fixes is exactly that
# warning ignored -- GATE_SPECS was settable locally, was never named on the ssh line, and so the
# battery silently ran the gemma /tmp/g3* fixtures no matter what the operator asked for. A knob
# that cannot cross the boundary is not a knob; it is a hardcoded default with extra steps.
# Defaults are the gemma3-27b campaign's, unchanged, so an invocation with no env is byte-for-byte
# the old behaviour.
GATE_PROMPTS=${GATE_PROMPTS:-pp256,pp1024,val550,rag4096}
GATE_SPECS=${GATE_SPECS:-"pp256:/tmp/g3pp256/prompt_0000.txt pp1024:/tmp/g3pp1024/prompt_0000.txt val550:/tmp/g3race500/prompt_0000.txt rag4096:/tmp/g3rag/rag4096.txt"}
# WHICH oracle directory and WHICH eos ids decide the gate. These travel together because an eos set
# from the wrong tokenizer admits or rejects early stops for the wrong reason. gemma: 106,1.
# Qwen2.5-7B-Instruct: 151645.
ORACLE_DIR=${ORACLE_DIR:-}
ORACLE_LABEL=${ORACLE_LABEL:-}
EOS_TOKENS=${EOS_TOKENS:-106,1}
# The coverage evaluator refuses unless the gate's claimed scope equals this set. It must be the
# same scope as GATE_PROMPTS or the two evaluators disagree about what was requested -- which is
# precisely the condition the coverage evaluator exists to catch, so deriving it from GATE_PROMPTS
# by default is the only safe default.
GATE_COVERAGE_PROMPTS=${GATE_COVERAGE_PROMPTS:-$GATE_PROMPTS}
GATE_COVERAGE_SINGLE_RUN=${GATE_COVERAGE_SINGLE_RUN:-rag4096}
# The clock pin, in MHz. A SKU that clamps `nvidia-smi -lgc` to a different value would otherwise
# have every 1 Hz sample counted off-pin and the window refused for being perfectly pinned.
CW_PIN_MHZ=${CW_PIN_MHZ:-1410}
# WHICH stage script prepares the box, and whether it owes a fixture-identity proof. The gemma
# stage proves fixtures identical to round 6's certified echoes; another engine's lane has no such
# banked echoes, so demanding the marker of a stage that does not emit it is a guaranteed refusal.
STAGE_SCRIPT=${STAGE_SCRIPT:-chain7stage.sh}
STAGE_NEEDS_FIXTURE_IDENTITY=${STAGE_NEEDS_FIXTURE_IDENTITY:-1}
CELL_MIN=${CELL_MIN:-2}
CW_TIMEOUT_S=${CW_TIMEOUT_S:-900}
# The serve-entry live launch: `algenta serve --backend cuda` against the wheel's own engine. Empty
# SERVE_MODEL skips the phase and the verdict records that it was skipped -- a launch-unverified
# wheel must say so rather than imply it was launched.
SERVE_MODEL=${SERVE_MODEL:-}
SERVE_PROMPT=${SERVE_PROMPT:-}
SERVE_MAX_NEW_TOKENS=${SERVE_MAX_NEW_TOKENS:-16}
# IAP TUNNELLING. Some boxes in this project have NO external IP at all (algenta-ent-h100 is
# internal-only at 10.128.0.96) and answer ssh ONLY through `--tunnel-through-iap`. Without the flag
# every probe/ssh/scp here fails as a connection error, the sync phase reads it as SYNC FAILED, and
# the window closes having measured nothing -- but having already paid for the boot. Set SSH_IAP=1.
SSH_IAP=${SSH_IAP:-0}
IAP_FLAG=""
[ "$SSH_IAP" = "1" ] && IAP_FLAG="--tunnel-through-iap"
# Zones worth trying for THIS machine type, in order, for the stockout message above. The default is
# the a3-highgpu-1g set (1x H100 80GB, sm_90 -- the cheapest box that can run the sm_90a engine):
# us-central1-a then us-central1-b, because both offer the machine type AND sit behind this
# project's Cloud NAT. Override it when the machine type changes.
ZONE_CANDIDATES=${ZONE_CANDIDATES:-us-central1-a,us-central1-b}

while [ $# -gt 0 ]; do
  case "$1" in
    --wheel) WHEEL="$2"; shift 2 ;;
    --vm) VM="$2"; shift 2 ;;
    --zone) ZONE="$2"; shift 2 ;;
    --project) PROJECT="$2"; shift 2 ;;
    --gpu) GPU="$2"; shift 2 ;;
    --cap-min) CAP_MIN="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) sed -n '2,60p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 8 ;;
  esac
done

# TRUNCATE, DO NOT APPEND ACROSS RUNS: several gates below are `grep -q <marker> "$LOCAL_LOG"`, and a
# marker left over from an earlier attempt would satisfy them falsely — the same class of defect as a
# guard that passes for the wrong reason. The previous log is preserved alongside, timestamped.
mkdir -p "$(dirname "$LOCAL_LOG")"
if [ -f "$LOCAL_LOG" ]; then
  mv "$LOCAL_LOG" "$(echo "$LOCAL_LOG" | sed 's/\.log$//').$(date -u +%Y%m%dT%H%M%SZ).log"
fi
: > "$LOCAL_LOG"
ts() { date -u +%FT%TZ; }
log() { echo "[$(ts)] $*" | tee -a "$LOCAL_LOG"; }
# IAP_FLAG is deliberately an UNQUOTED single-token string, not an array: this script runs under
# `set -u` and macOS ships bash 3.2, where "${arr[@]}" on an empty array is an unbound-variable
# error. Empty expands to nothing, set expands to exactly one word.
gc() {
  case "$1" in
    ssh|scp) gcloud compute "$@" --project="$PROJECT" --zone="$ZONE" $IAP_FLAG ;;
    *)       gcloud compute "$@" --project="$PROJECT" --zone="$ZONE" ;;
  esac
}

# ── SSHD READINESS, AND WHY `status=RUNNING` IS NOT ENOUGH ────────────────────────────────────
# GCE's RUNNING means the hypervisor scheduled the guest, not that the guest's ssh is accepting
# connections; on a spot 8xH200 with a large boot disk that gap is routinely a minute or more, and
# round 18's third boot died on exactly that (`4003 failed to connect to port 22` read as SYNC
# FAILED, tearing down a window 4 min in over a fault a 30 s wait would have cleared). So every
# ssh/scp goes through a CHEAP readiness probe first, because a probe that costs a minute is not a
# probe and blindly retrying the expensive operation is what burns the cap.
ssh_ready() {
  i=1
  while [ "$i" -le "$SSH_TRIES" ]; do
    # Through gc, NOT a bare `gcloud compute ssh`: this was the one call site that bypassed the
    # wrapper, so on an IAP-only box the readiness probe would fail while every other ssh in the
    # script had the tunnel flag -- and the failure would read as "sshd never came up" rather than
    # "this controller cannot route to that box at all".
    if gc ssh "$VM" --command 'echo READY' >/dev/null 2>&1; then
      log "sshd READY on probe $i/$SSH_TRIES"
      return 0
    fi
    log "sshd not ready (probe $i/$SSH_TRIES) — waiting ${SSH_WAIT_S}s before the next"
    sleep "$SSH_WAIT_S"
    i=$((i + 1))
  done
  log "FATAL: sshd never became ready after $SSH_TRIES probes"
  return 1
}

STARTED=0
# THE STOP IS RETRIED UNTIL THE INSTANCE REPORTS TERMINATED, AND THIS IS NOT PEDANTRY. `gcloud
# compute instances stop` can return "Instance has in progress persistent disk IO and cannot be
# suspended/stopped at this time" seconds after a boot; round 18 logged that error, printed "stop:
# returned", and EXITED — leaving a spot H200 RUNNING with nothing owning it. A stop that reports
# failure is a stop that has not happened.
STOP_TRIES=${STOP_TRIES:-8}
STOP_WAIT_S=${STOP_WAIT_S:-20}
stop_vm() {
  st=UNKNOWN
  i=1
  while [ "$i" -le "$STOP_TRIES" ]; do
    st=$(gc instances describe "$VM" --format='value(status)' 2>/dev/null || echo UNKNOWN)
    if [ "$st" = "TERMINATED" ]; then
      log "stop: TERMINATED confirmed on attempt $i"
      break
    fi
    log "stop: attempt $i/$STOP_TRIES (status=$st) --discard-local-ssd=false"
    gc instances stop "$VM" --discard-local-ssd=false >>"$LOCAL_LOG" 2>&1
    log "stop: gcloud returned at $(ts)"
    sleep "$STOP_WAIT_S"
    i=$((i + 1))
  done
  st=$(gc instances describe "$VM" --format='value(status)' 2>/dev/null || echo UNKNOWN)
  if [ "$st" = "TERMINATED" ]; then
    log "VERIFY instance status = TERMINATED  TERMINATED_OK"
  else
    log "VERIFY instance status = $st  *** NOT_TERMINATED — STOP MANUALLY NOW: ***"
    log "  gcloud compute instances stop $VM --project=$PROJECT --zone=$ZONE --discard-local-ssd=false"
  fi
  run=$(gcloud compute instances list --project="$PROJECT" --filter='status=RUNNING' \
        --format='value(name,zone,status)' 2>/dev/null)
  if [ -z "$run" ]; then
    log "VERIFY project-wide status=RUNNING is EMPTY — no VM left running"
  else
    log "VERIFY project-wide status=RUNNING is NOT EMPTY:"
    echo "$run" | while read -r l; do log "    STILL RUNNING: $l"; done
  fi
  [ "$st" = "TERMINATED" ]
}
trap 'log "TRAP: interrupted — stopping the VM before exiting"; if [ "$STARTED" = "1" ]; then stop_vm; fi; exit 130' INT TERM

# ── 0. PRE-FLIGHT, BEFORE THE INSTANCE IS STARTED ─────────────────────────────────────────────
log "pre-flight: local conditions only, the VM is still TERMINATED and costs nothing"
[ -n "$WHEEL" ] || { log "PRE-FLIGHT FAILED: --wheel <path-to-cuda-wheel> is required"; exit 8; }
[ -f "$WHEEL" ] || { log "PRE-FLIGHT FAILED: no wheel at $WHEEL"; exit 8; }
case "$WHEEL" in
  *algenta_runtime_native-*.whl) ;;
  *) log "PRE-FLIGHT FAILED: $WHEEL is not an algenta_runtime_native wheel"; exit 8 ;;
esac
command -v gcloud >/dev/null 2>&1 || { log "PRE-FLIGHT FAILED: gcloud not on PATH"; exit 8; }
command -v python3 >/dev/null 2>&1 || { log "PRE-FLIGHT FAILED: python3 not on PATH"; exit 8; }
# THE LOCAL WHEEL HASH, COMPUTED BEFORE ANYTHING IS STARTED. This is the value the verdict must
# name, and the value publish-pypi's gate later recomputes from the artifact CI built — so a verdict
# can only ever certify the bytes it was made from. Hashing here (not on the box) also means a
# mismatch caused by the transfer is detectable rather than invisible.
LOCAL_WHEEL_SHA=$(python3 -c 'import hashlib,sys
h = hashlib.sha256()
with open(sys.argv[1], "rb") as fh:
    for chunk in iter(lambda: fh.read(1048576), b""):
        h.update(chunk)
print(h.hexdigest())' "$WHEEL") || { log "PRE-FLIGHT FAILED: could not hash $WHEEL"; exit 8; }
LOCAL_WHEEL_BYTES=$(python3 -c 'import os,sys;print(os.path.getsize(sys.argv[1]))' "$WHEEL")
log "wheel: $(basename "$WHEEL") sha256=$LOCAL_WHEEL_SHA bytes=$LOCAL_WHEEL_BYTES"

# ── RUNPATH PRE-FLIGHT: THE ONE CHECK THAT COSTS NOTHING HERE AND A WHOLE WINDOW ON THE BOX ─────
# The engine is linked with `-Xlinker -rpath -Xlinker $ORIGIN` so it finds the libcudart.so.12 the
# wheel bundles BESIDE it. Nothing in CI verifies that landed: the pipeline has no readelf assertion
# at all, and a silently-dropped rpath produces a wheel that hashes fine, validates fine, and then
# fails to load libcudart on the GPU box -- discovered at the most expensive possible moment. So the
# dynamic section is read HERE, on the operator's machine, from the same bytes about to be shipped.
# Non-fatal when no ELF reader is installed (the battery re-asserts on the box, where readelf always
# exists); FATAL when a reader IS available and $ORIGIN is absent, because that wheel cannot work.
ELF_TOOL=""
for t in llvm-readelf readelf greadelf llvm-objdump objdump gobjdump; do
  command -v "$t" >/dev/null 2>&1 && { ELF_TOOL="$t"; break; }
done
if [ -z "$ELF_TOOL" ]; then
  log "NOTE: no readelf/objdump on this host -- skipping the RUNPATH pre-flight. The battery"
  log "      re-asserts \$ORIGIN on the box, where readelf is always present."
else
  RUNPATH_FOUND=$(WHEEL="$WHEEL" ELF_TOOL="$ELF_TOOL" python3 -c '
import os, subprocess, sys, tempfile, zipfile
wheel, tool = os.environ["WHEEL"], os.environ["ELF_TOOL"]
z = zipfile.ZipFile(wheel)
eng = [n for n in z.namelist()
       if n.startswith("algenta_runtime_native/") and n.endswith("conform_generate_cuda")]
if not eng:
    print("NO_ENGINE_MEMBER"); raise SystemExit(0)
with tempfile.NamedTemporaryFile(delete=False, suffix=".engine") as fh:
    fh.write(z.read(eng[0])); path = fh.name
os.chmod(path, 0o755)
args = [tool, "-d", path] if "readelf" in tool else [tool, "--private-headers", path]
out = subprocess.run(args, capture_output=True, text=True, errors="replace").stdout
dyn = [ln for ln in out.splitlines() if "PATH" in ln.upper() and "ORIGIN" in ln]
print(("RUNPATH_OK " + eng[0] + " :: " + dyn[0].strip()) if dyn else "RUNPATH_MISSING")
' 2>/dev/null || echo "RUNPATH_CHECK_ERROR")
  case "$RUNPATH_FOUND" in
    RUNPATH_OK*) log "$RUNPATH_FOUND (via $ELF_TOOL)" ;;
    NO_ENGINE_MEMBER) log "NOTE: no conform_generate_cuda member in this wheel -- is it the cuda variant?" ;;
    RUNPATH_CHECK_ERROR) log "NOTE: the RUNPATH pre-flight errored; the battery re-asserts on the box" ;;
    *) log "*** RUNPATH PRE-FLIGHT: \$ORIGIN was NOT found in the engine's dynamic section ($ELF_TOOL)."
       log "    This wheel's engine cannot locate the libcudart.so.12 bundled beside it, so it will"
       log "    fail to load on the box. Refusing BEFORE any VM-on minutes are spent."
       exit 8 ;;
  esac
fi

# The tree that gets synced must be clean and PUSHED: the measured binaries have to be traceable to a
# commit that exists upstream. The one path this must not trip on is `mojo_env/.pixi`, a documented
# never-commit local symlink (round 19's first window died on it 5 s after the instance came up).
DIRTY=$(cd "$WT" && git status --porcelain 2>/dev/null | grep -v '^?? mojo_env/\.pixi$' || true)
if [ -n "$DIRTY" ]; then
  log "PRE-FLIGHT FAILED: $WT is dirty — commit or stash first. Dirty paths:"
  echo "$DIRTY" | head -20 | tee -a "$LOCAL_LOG"
  exit 8
fi
BRANCH=$(cd "$WT" && git rev-parse --abbrev-ref HEAD)
HEAD=$(cd "$WT" && git rev-parse --short HEAD)
(cd "$WT" && git fetch --quiet origin "$BRANCH" 2>/dev/null || true)
if ! (cd "$WT" && git rev-parse --quiet --verify "origin/$BRANCH" >/dev/null); then
  log "PRE-FLIGHT FAILED: origin/$BRANCH does not exist — push the branch first"; exit 8
fi
REMOTE_HEAD=$(cd "$WT" && git rev-parse "origin/$BRANCH")
if [ "$(cd "$WT" && git rev-parse HEAD)" != "$REMOTE_HEAD" ]; then
  log "PRE-FLIGHT FAILED: HEAD ($HEAD) != origin/$BRANCH — push first so the synced tree matches"
  log "  a commit that exists upstream (a verdict must be traceable to a commit)."
  exit 8
fi
log "PREFLIGHT OK: $BRANCH @ $HEAD is clean (modulo the never-committed mojo_env/.pixi) and pushed"
grep -q "PREFLIGHT OK" "$LOCAL_LOG" || { log "PRE-FLIGHT FAILED (no marker)"; exit 8; }

if [ "$DRY_RUN" = "1" ]; then
  log "DRY_RUN: would start $VM, sync $BRANCH@$HEAD + the wheel, launch the battery, watch,"
  log "          collect cuda-release-verdict.json, then stop. Touching nothing."
  log "DRY_RUN: cap ${CAP_MIN}m + ${GRACE_MIN}m grace, stop margin ${STOP_MARGIN_S}s."
  exit 0
fi

# ── 1. START ──────────────────────────────────────────────────────────────────────────────────
st=$(gc instances describe "$VM" --format='value(status)' 2>/dev/null || echo UNKNOWN)
log "instance $VM status=$st zone=$ZONE project=$PROJECT cap=${CAP_MIN}m grace=${GRACE_MIN}m"
if [ "$st" != "RUNNING" ]; then
  tries=0; stockouts=0
  while [ "$tries" -lt "$START_TRIES" ]; do
    tries=$((tries + 1))
    log "start attempt $tries/$START_TRIES"
    out=$(gc instances start "$VM" 2>&1); rc=$?
    if [ "$rc" = "0" ]; then stockouts=0; break; fi
    echo "$out" | tail -6 | tee -a "$LOCAL_LOG"
    if echo "$out" | grep -qiE "ZONE_RESOURCE_POOL_EMPTY|stockout|insufficient|capacity"; then
      stockouts=$((stockouts + 1))
      log "SPOT STOCKOUT ($stockouts consecutive) in $ZONE"
      if [ "$stockouts" -ge 2 ]; then
        log "TWO CONSECUTIVE STOCKOUTS — stopping and waiting, per the owner's rule. No further"
        log "  retries this session. The VM is left TERMINATED."
        # WHICH ZONES ARE EVEN CANDIDATES IS A FACT ABOUT THE MACHINE TYPE AND THE NETWORK, not a
        # free-text suggestion. The list this message used to print was wrong for a3-highgpu-1g in
        # two independent ways, both verified with gcloud rather than assumed:
        #   * us-west1-c does not OFFER a3-highgpu-1g at all (`machine-types describe` -> "was not
        #     found"), so naming it sends the next operator to a zone that cannot create the box;
        #   * asia-south1-b has the machine type but NO Cloud NAT -- this project's only two routers
        #     (gw-router, dev-network-router) are both in us-central1 -- so a box there has no
        #     internet egress and cannot fetch the HF snapshot the 7B stage needs.
        # ZONE_CANDIDATES is overridable because the right list depends on the machine type in use.
        log "  Remaining candidates for this machine type: $ZONE_CANDIDATES"
        log "  (a zone qualifies only if it OFFERS the machine type AND has egress for staging)"
        exit 4
      fi
      sleep 90
    else
      log "start failed for a NON-capacity reason; not retrying blindly"; exit 3
    fi
  done
fi
STARTED=1
lst=""
i=1
while [ "$i" -le 40 ]; do
  lst=$(gc instances describe "$VM" --format='value(lastStartTimestamp)' 2>/dev/null || echo "")
  st=$(gc instances describe "$VM" --format='value(status)' 2>/dev/null || echo UNKNOWN)
  [ "$st" = "RUNNING" ] && [ -n "$lst" ] && break
  sleep 15
  i=$((i + 1))
done
log "lastStartTimestamp = $lst  status=$st"
[ -z "$lst" ] && { log "FATAL: no lastStartTimestamp — cannot compute the cap. Stopping."; stop_vm; exit 5; }
# PARSE THE OFFSET, DO NOT ASSUME IT. gcloud reports `lastStartTimestamp` in the INSTANCE's zone
# (-07:00 for us-west1); `date -j -f` on macOS would interpret it in the HOST's zone and land three
# hours early, putting the hard deadline in the past. Python's fromisoformat handles the offset on
# every host. `python3 -c`, NOT a heredoc inside `$( )` — bash 3.2 on macOS mishandles that
# combination — so the python below contains no single quotes.
LST_EPOCH=$(python3 -c 'import sys
from datetime import datetime
s = sys.argv[1].strip()
if s.endswith("Z"):
    s = s[:-1] + "+00:00"
print(int(datetime.fromisoformat(s).timestamp()))' "$lst" 2>/dev/null)
case "${LST_EPOCH:-}" in
  ''|*[!0-9]*) LST_EPOCH=$(date -j -f "%Y-%m-%dT%H:%M:%S%z" "${lst:0:19}${lst: -6}" +%s 2>/dev/null \
                || date -d "$lst" +%s 2>/dev/null || echo 0) ;;
esac
case "${LST_EPOCH:-}" in ''|*[!0-9]*) LST_EPOCH=0 ;; esac
if [ "$LST_EPOCH" = "0" ]; then
  log "FATAL: could not parse lastStartTimestamp '$lst'. Stopping rather than run uncapped."
  stop_vm; exit 5
fi
now_e=$(date +%s)
if [ "$LST_EPOCH" -gt $((now_e + 60)) ]; then
  log "FATAL: parsed lastStartTimestamp is in the FUTURE — the offset was mis-parsed. Stopping."
  stop_vm; exit 5
fi
if [ $((now_e - LST_EPOCH)) -gt 21600 ]; then
  log "FATAL: parsed lastStartTimestamp is $(( (now_e - LST_EPOCH) / 60 )) min old, which is not"
  log "       this start. Refusing; stopping."; stop_vm; exit 5
fi
DEADLINE=$(( LST_EPOCH + (CAP_MIN + GRACE_MIN) * 60 ))
log "VM-ON cap ${CAP_MIN}m + ${GRACE_MIN}m grace => HARD DEADLINE $(date -u -r "$DEADLINE" +%FT%TZ)"
log "already elapsed since start: $(( ($(date +%s) - LST_EPOCH) / 60 )) min"

# ── 1b. ARM THE INDEPENDENT STOP BACKSTOP, BEFORE ANYTHING ELSE CAN FAIL ──────────────────────
# A SECOND owner of the stop, in its own session, sharing no process group with this controller: the
# controller's own trap and retry loop are necessary but NOT sufficient, because they die with the
# controller (round 18 was group-killed three times, and on the first of those the EXIT trap was
# mid-`stop_vm` when the follow-up SIGKILL landed, after GCE had already refused the stop).
# REUSED, NOT REWRITTEN: `vm_stop_backstop_r18.sh` keeps its round-18 name because it is the same
# script round 18 paid for in three group-kills, and its liveness pattern is round-agnostic. What
# this window supplies is LEVER_DIR (so it reads CHAIN_EXIT from the right place) and LOG.
BACKSTOP_LOG=${BACKSTOP_LOG:-/private/tmp/cuda_release_verify/backstop.log}
if [ "${BACKSTOP:-1}" = "1" ]; then
  NRDIR="$WT/benchmarks/llm_smoke/nvidia_race"
  LOG="$BACKSTOP_LOG" GCLOUD=gcloud VM="$VM" ZONE="$ZONE" PROJECT="$PROJECT" GPU="$GPU" \
    LEVER_DIR="$WORK" \
    python3 -c 'import os,sys; os.setsid(); os.execv("/bin/bash",["bash"]+sys.argv[1:])' \
    "$NRDIR/vm_stop_backstop_r18.sh" --deadline "$DEADLINE" --poll "${BACKSTOP_POLL:-60}" \
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

# ── 2. SYNC: the tree subset the battery needs, then the wheel, then RE-HASH the wheel ─────────
# The box has NO github egress (measured round 6 — a clone times out on github.com:443), so the tree
# is tar'd here and scp'd over. COPYFILE_DISABLE stops macOS writing ._ AppleDouble sidecars into the
# tar, which otherwise land in the VM tree as junk.
TGZ=/tmp/cuda_release_verify_tree.tgz
rm -f "$TGZ"
log "sync: taring $BRANCH@$HEAD"
( cd "$WT" && COPYFILE_DISABLE=1 tar czf "$TGZ" \
    --exclude __pycache__ --exclude .pixi --exclude .git \
    benchmarks/llm_smoke/nvidia_race packages/algenta scripts mojo_env/pixi.toml ) || {
  log "SYNC FAILED: could not tar the tree"; stop_vm; exit 6; }
log "sync: tree tarball $(python3 -c 'import os,sys;print(os.path.getsize(sys.argv[1]))' "$TGZ") bytes"
SYNC_TRIES=${SYNC_TRIES:-3}
synced=0
i=1
while [ "$i" -le "$SYNC_TRIES" ]; do
  log "sync attempt $i/$SYNC_TRIES (sshd probe first)"
  if ssh_ready; then
    if gc scp "$TGZ" "angel@$VM:$REMOTE_DIR.tgz" >>"$LOCAL_LOG" 2>&1 && \
       gc scp "$WHEEL" "angel@$VM:$REMOTE_DIR.whl" >>"$LOCAL_LOG" 2>&1; then
      synced=1; break
    fi
  fi
  log "sync attempt $i FAILED — re-probing before the next"
  sleep "$SSH_WAIT_S"
  i=$((i + 1))
done
if [ "$synced" != "1" ]; then
  log "SYNC FAILED after $SYNC_TRIES attempts — stopping; nothing was measured"; stop_vm; exit 6
fi
log "SYNC_DONE: tree + wheel transferred"

# THE WHEEL HASH IS RE-CHECKED ON THE BOX, AND A MISMATCH IS FATAL RATHER THAN A WARNING. The verdict
# names the bytes that were tested; if the transfer corrupted or truncated the wheel, everything
# downstream would certify a file that is not the file CI built and not the file anyone publishes.
ssh_ready || { log "sshd lost after sync — stopping"; stop_vm; exit 7; }
# `sha256sum`, not a python one-liner over ssh: the campaign already hashes arms this way
# (chain19.sh's build_reverify), it is one process on the box, and it has no quoting surface to get
# wrong across four process boundaries.
REMOTE_WHEEL_SHA=$(gc ssh "$VM" --command \
  "sha256sum \$HOME/$REMOTE_DIR.whl 2>/dev/null | cut -d' ' -f1" 2>>"$LOCAL_LOG" | tail -1)
log "remote wheel sha256=$REMOTE_WHEEL_SHA"
if [ "$REMOTE_WHEEL_SHA" != "$LOCAL_WHEEL_SHA" ]; then
  log "*** WHEEL HASH MISMATCH after transfer: local=$LOCAL_WHEEL_SHA remote=$REMOTE_WHEEL_SHA"
  log "    REFUSING to run a battery whose verdict could not name the bytes it tested. Stopping."
  stop_vm; exit 9
fi
log "WHEEL_HASH_OK: the box holds the exact bytes this window will certify"
gc ssh "$VM" --command "rm -rf ~/$REMOTE_DIR && mkdir -p ~/$REMOTE_DIR $WORK/runs $WORK/logs \
  $WORK/clocks $WORK/site-packages && tar xzf ~/$REMOTE_DIR.tgz -C ~/$REMOTE_DIR && \
  ls ~/$REMOTE_DIR/scripts/release/verify_cuda_release_battery.sh >/dev/null && echo TREE_OK && \
  ls ~/$REMOTE_DIR/benchmarks/llm_smoke/nvidia_race/vm_harness/lever3/gate_any.py >/dev/null && \
  echo GATE_ANY_OK && echo '$BRANCH $HEAD' > ~/$REMOTE_DIR/.synced_head" >>"$LOCAL_LOG" 2>&1
grep -q "GATE_ANY_OK" "$LOCAL_LOG" || { log "SYNC FAILED: the gate harness did not land"; stop_vm; exit 6; }
log "TREE_OK + GATE_ANY_OK confirmed; synced_head=$BRANCH@$HEAD"

# ── 3. LAUNCH (channel must NOT be inherited) ─────────────────────────────────────────────────
# EVERY GOVERNOR KNOB IS PASSED ON THIS LINE, EXPLICITLY. An env var that has to survive four process
# boundaries (Mac shell -> gcloud ssh -> remote shell -> battery -> cell driver) must be named at each
# one: round 18 caught a bug where an `export` of a variable the ssh line never set exported NOTHING
# and the runner silently fell back to its own default.
log "launching verify_cuda_release_battery.sh under setsid+nohup, stdin /dev/null, disowned"
# WHAT IS BEING FORWARDED IS LOGGED BEFORE IT IS FORWARDED. A window whose log does not name the
# gate scope, the fixture specs, the oracle and the pin cannot be audited afterwards: the whole
# point of a release verdict is that a reader can tell what was certified, and "whatever the
# defaults were" is not an answer.
log "forwarding: GATE_PROMPTS=[$GATE_PROMPTS] coverage=[$GATE_COVERAGE_PROMPTS]"
log "forwarding: GATE_SPECS=[$GATE_SPECS]"
log "forwarding: ORACLE_DIR=[$ORACLE_DIR] EOS_TOKENS=[$EOS_TOKENS] CW_PIN_MHZ=$CW_PIN_MHZ"
log "forwarding: STAGE_SCRIPT=$STAGE_SCRIPT needs_fixture_identity=$STAGE_NEEDS_FIXTURE_IDENTITY"
log "forwarding: CELL_MIN=$CELL_MIN CW_TIMEOUT_S=$CW_TIMEOUT_S SERVE_MODEL=[$SERVE_MODEL]"
gc ssh "$VM" --command \
  "CW_DEADLINE_EPOCH=$DEADLINE CAP_MIN=$CAP_MIN GRACE_MIN=$GRACE_MIN SAFETY_S=$STOP_MARGIN_S \
   GPU=$GPU WORK=$WORK SRC_TREE=\$HOME/$REMOTE_DIR WHEEL_PATH=\$HOME/$REMOTE_DIR.whl \
   EXPECT_WHEEL_SHA=$LOCAL_WHEEL_SHA EXPECT_WHEEL_BYTES=$LOCAL_WHEEL_BYTES \
   VM_NAME=$VM VM_ZONE=$ZONE VM_PROJECT=$PROJECT VM_LAST_START='$lst' \
   GATE_PROMPTS='$GATE_PROMPTS' GATE_SPECS='$GATE_SPECS' \
   ORACLE_DIR='$ORACLE_DIR' ORACLE_LABEL='$ORACLE_LABEL' EOS_TOKENS='$EOS_TOKENS' \
   GATE_COVERAGE_PROMPTS='$GATE_COVERAGE_PROMPTS' \
   GATE_COVERAGE_SINGLE_RUN='$GATE_COVERAGE_SINGLE_RUN' CW_PIN_MHZ='$CW_PIN_MHZ' \
   STAGE_SCRIPT='$STAGE_SCRIPT' STAGE_NEEDS_FIXTURE_IDENTITY='$STAGE_NEEDS_FIXTURE_IDENTITY' \
   CELL_MIN='$CELL_MIN' CW_TIMEOUT_S='$CW_TIMEOUT_S' \
   SERVE_MODEL='$SERVE_MODEL' SERVE_PROMPT='$SERVE_PROMPT' \
   SERVE_MAX_NEW_TOKENS='$SERVE_MAX_NEW_TOKENS' \
   CKPT='${CKPT:-/mnt/ramblob/g3conv27b}' HF_CKPT='${HF_CKPT:-\$HOME/gemma3-27b}' \
   PY314='${PY314:-}' \
   setsid nohup bash \$HOME/$REMOTE_DIR/scripts/release/verify_cuda_release_battery.sh \
   </dev/null >$WORK/battery.out 2>&1 & disown; sleep 2; \
   echo LAUNCHED pid=\$(pgrep -f verify_cuda_release_batter[y] | head -1)" >>"$LOCAL_LOG" 2>&1
grep -q "LAUNCHED" "$LOCAL_LOG" || { log "no LAUNCHED marker — stopping"; stop_vm; exit 7; }
log "$(grep -m1 LAUNCHED "$LOCAL_LOG")"

# ── 4. WATCH ──────────────────────────────────────────────────────────────────────────────────
# Liveness comes from the heartbeat file the battery writes, not from holding an ssh session open: a
# watch that depends on the channel is the failure mode that cost round 17 five minutes twice.
last_hb=""
while true; do
  now=$(date +%s)
  hb=$(gc ssh "$VM" --command "tail -2 $WORK/heartbeat.log 2>/dev/null; echo ---; \
       cat $WORK/PHASE 2>/dev/null; echo ---; cat $WORK/BATTERY_EXIT 2>/dev/null; echo ---; \
       grep -m1 'GATE ALL_PASS' $WORK/battery.log 2>/dev/null; echo ---; \
       grep -m1 'BATTERY COMPLETE' $WORK/battery.log 2>/dev/null" 2>/dev/null | tr '\n' '|')
  [ "$hb" != "$last_hb" ] && log "hb: $hb"
  last_hb="$hb"
  case "$hb" in *"BATTERY COMPLETE"*) log "battery reports COMPLETE"; break ;; esac
  case "$hb" in *"BATTERY_FAILED"*) log "battery reports FAILED — collecting the evidence, then stopping"; break ;; esac
  if [ $((now + STOP_MARGIN_S)) -ge "$DEADLINE" ]; then
    log "DEADLINE APPROACHING (stop margin ${STOP_MARGIN_S}s) — stopping the window now"; break
  fi
  sleep "$POLL_S"
done

# ── 5. COLLECT, THEN STOP ─────────────────────────────────────────────────────────────────────
# Pull the artifacts BEFORE the stop: /tmp and /mnt/ramblob are tmpfs and die with it, and having the
# window's evidence locally means it can be audited without another billable start.
ART=${ART:-/private/tmp/cuda_release_verify/artifacts}
mkdir -p "$ART"
log "collecting artifacts -> $ART"
# serve_launch.json IS A DELIVERABLE, so it is collected: the serve phase proves the shipped entry
# point starts, and a verdict claiming serve_launch=launched whose evidence stayed on a stopped VM is
# a claim without its proof. stage.log and the oracle dir are collected for the same reason -- they
# are what makes the fixture/oracle provenance auditable after the box is gone. `2>/dev/null` on the
# tar keeps a missing optional member from failing the whole collection.
gc ssh "$VM" --command "cd $WORK && tar czf /tmp/crv_art.tgz battery.log heartbeat.log BATTERY_EXIT \
   PHASE clocks runs cuda-release-verdict.json gate_cuda_release.json conformance_cuda.json \
   wheel-census.json gpuless_load.txt CHAIN_EXIT \
   serve_launch.json serve_launch.txt stage.log battery.out wheel.sha256 binaries.sha256 \
   oracle7b 2>/dev/null; ls -l /tmp/crv_art.tgz" \
   >>"$LOCAL_LOG" 2>&1
gc scp "$VM:/tmp/crv_art.tgz" "$ART/crv_art.tgz" --project="$PROJECT" --zone="$ZONE" \
  >>"$LOCAL_LOG" 2>&1 && (cd "$ART" && tar xzf crv_art.tgz 2>/dev/null && log "artifacts extracted") \
  || log "WARNING: artifact collection incomplete — $WORK still holds them on the boot disk"

# ── 6. THE REFUSAL GATE: NO VERDICT UNLESS EVERYTHING THE VERDICT CLAIMS ACTUALLY HAPPENED ─────
# Checked HERE rather than trusted from the battery's own exit code, because the controller is the
# party that hands a verdict to a publish pipeline and "the remote script said it was fine" is not
# evidence. Four independent conditions, any of which withholds the verdict:
#   (a) a verdict file came home at all;
#   (b) it says pass with rc=0;
#   (c) its wheel_sha256 equals the hash computed LOCALLY before the start — the mismatch case the
#       whole design exists to catch, re-checked at the end rather than only at the transfer;
#   (d) the battery's own artifact says the clock discipline held (every cell 1410 MHz, offpin=0).
VERDICT_OK=0
if [ -f "$ART/cuda-release-verdict.json" ]; then
  # PIN_MHZ IS THIS CONTROLLER'S OWN EXPECTATION, not the verdict's self-report. Checking a verdict
  # against a number the verdict itself supplied would pass for any pin at all, including a pin the
  # operator never asked for -- the "guard that passes for the wrong reason" this file's header warns
  # about. The battery reports its pin; the controller decides whether that pin was the one ordered.
  VERDICT_OK=$(ART="$ART" LOCAL_WHEEL_SHA="$LOCAL_WHEEL_SHA" PIN_MHZ="$CW_PIN_MHZ" python3 -c '
import json, os
d = json.load(open(os.path.join(os.environ["ART"], "cuda-release-verdict.json"), encoding="utf-8"))
want = os.environ["LOCAL_WHEEL_SHA"]
got = (d.get("wheel") or {}).get("sha256") or d.get("wheel_sha256")
pin = str(os.environ["PIN_MHZ"])
clocks = d.get("clocks") or {}
cells = clocks.get("cells") or []
# THE FIELDS THAT ACTUALLY EXIST. This check used to read `clocks_after` per cell -- a key the
# battery never writes (it writes clock_samples/clock_min_mhz/clock_max_mhz/offpin/offpin_zero) --
# so `str(None) != "1410"` held for EVERY cell, bad_clock was never empty, and VERDICT_OK was 0 no
# matter what the window achieved. A perfect battery would still have closed with rc=10 and
# "WINDOW CLOSED WITH NO VERDICT", i.e. the leg could never publish anything. Checking min AND max
# against the pin is both correct and strictly stronger: it says the GPU held the pin for the whole
# cell, not merely that it read the pin once at the end.
bad_clock = [c for c in cells
             if str(c.get("clock_min_mhz")) != pin or str(c.get("clock_max_mhz")) != pin]
bad_offpin = [c for c in cells
              if int(c.get("offpin", 1) or 0) != 0 or c.get("offpin_zero") is not True]
ok = (d.get("verdict") == "pass" and d.get("rc") == 0 and got == want
      and bool(cells) and not bad_clock and not bad_offpin
      and str(clocks.get("pinned_mhz")) == pin
      and (d.get("gates") or {}).get("all_pass") is True)
print("1" if ok else "0")
if not ok:
    print("  verdict=%r rc=%r gates.all_pass=%r" % (d.get("verdict"), d.get("rc"),
          (d.get("gates") or {}).get("all_pass")))
    print("  wheel_sha256 verdict=%s local=%s match=%s" % (got, want, got == want))
    print("  pin requested=%s reported=%s cells=%d off-clock=%d off-pin=%d"
          % (pin, clocks.get("pinned_mhz"), len(cells), len(bad_clock), len(bad_offpin)))
    for c in bad_clock[:4]:
        print("    off-clock cell %r min=%r max=%r" % (c.get("label"),
              c.get("clock_min_mhz"), c.get("clock_max_mhz")))
')
  log "verdict re-check: VERDICT_OK=$VERDICT_OK"
else
  log "NO VERDICT FILE came home — the battery refused or was killed mid-window"
fi

stop_vm

if [ "$VERDICT_OK" != "1" ]; then
  log "WINDOW CLOSED WITH NO VERDICT. Nothing may be published from this window."
  log "  evidence: $ART   log: $LOCAL_LOG"
  log "  rc=10 (gate failure, clock/offpin deviation, wheel-hash mismatch, or an unfinished battery)"
  exit 10
fi
log "WINDOW CLOSED. cuda-release-verdict.json -> $ART/cuda-release-verdict.json"
log "  wheel sha256 = $LOCAL_WHEEL_SHA ($LOCAL_WHEEL_BYTES bytes)"
log "  Local log: $LOCAL_LOG   Artifacts: $ART"
log "NEXT: attach the verdict to the release publish-pypi reads (tag runtime-v<version>):"
log "  gh release upload runtime-v<version> --repo $REPO $ART/cuda-release-verdict.json"
log "then publish (the gate re-hashes the wheel and compares it to this verdict):"
log "  gh workflow run build-runtime.yml --repo $REPO -f publish=true -f verdict_tag=runtime-v<version>"
exit 0
