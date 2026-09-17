#!/usr/bin/env bash
# vm_backup_harness.sh — pull the gemma-3 race harness's VM-ONLY files off trtllm-gemma-us-west1-c
# and stage them in the repo so they are version-controlled. RUN THIS FROM THE LOCAL MACHINE the
# instant the box is startable again; it is the first task of any resumed window, BEFORE any
# measurement.
#
# WHY THIS EXISTS — THE FINDING THAT MADE IT URGENT. Round 8 audited which files the gemma-3 race
# harness actually depends on and found that SIX of them exist in exactly one place in the world:
# the local SSD of a single spot instance that is currently unstartable due to STOCKOUT.
#
#   trtllm_prep.sh       regenerates the prompt fixtures — WITHOUT IT fixture identity against the
#                        pre-stop gate echoes cannot be established at all, so nothing is measurable
#   trtllm_convert.sh    converts gemma-3-27b to /mnt/ramblob/g3conv27b — WITHOUT IT there is no
#                        checkpoint to load
#   cell_watchdog.sh     the 600 s stall->SIGKILL wrapper EVERY cell runs under (round 6: a gate
#                        cell killed mid-blob-load was once misread as a crashed arm because of a
#                        truncated .out)
#   gate_any.py          the oracle gate runner: G0 16/16, G1 64/64, val550, rag 22/22 EOS-stop
#   lv3_trtllm.sh        the TensorRT-LLM re-serve — WITHOUT IT no ratio is claimable, because the
#                        protocol requires a same-session TRT column
#   driver_ctx8192.mojo  the STOCK driver source every arm is built from
#
# They are referenced 19 times across the repo's race scripts and present in NONE of them. `find`
# over the whole worktree returns nothing for all six.
#
# THE CONSEQUENCE, which is a campaign-level risk and not a round-8 inconvenience: a fallback
# region is NOT a fallback for this lane. A new instance in asia-south1-b or asia-south2-c comes
# with an empty SSD, so it has no staging recipe, no watchdog, no gate runner, no TRT re-serve and
# no driver — and `setup_vm.sh` provisions a Qwen3-0.6B smoke model, not gemma-3-27b. Region
# availability is therefore NOT the binding constraint on resuming this race; THIS BACKUP IS.
# Recovering these six files outranks finding capacity.
#
# ALSO NOTE: copying them to /tmp ON THE SAME BOX is not a backup. /tmp is tmpfs and is wiped by
# every stop/start — that is precisely why the fixtures and the checkpoint have to be regenerated
# each window. Durable means the local machine and git, which is what this script does.
#
# Usage:  bash vm_backup_harness.sh [--dry-run]
set -uo pipefail
VM=${VM:-trtllm-gemma-us-west1-c}
ZONE=${ZONE:-us-west1-c}
PROJECT=${PROJECT:-eplanev2}
DEST=${DEST:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/vm_harness}
DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1

# VM-side paths RELATIVE TO $HOME. cell_watchdog.sh, gate_any.py and lv3_trtllm.sh are read from
# $HOME/lever3 by run_gemma3_round6_cells.sh, and driver_ctx8192.mojo from $HOME/adj/build by
# run_ab_gemma3_round*.sh — both verified present on the box.
#
# THE STAGING SCRIPTS LIVE AT $HOME/*.sh, **NOT** $HOME/trtllm/*.sh. This file originally assumed
# the trtllm/ subdirectory, so the first backup run reported the two most load-bearing files in the
# lane as MISSING and silently skipped them — a backup that quietly omits the thing it exists to
# protect is worse than no backup, because it reads as done. The paths below were confirmed by
# `find $HOME -maxdepth 3 -name 'trtllm*'` on the box, which also turned up convert_27b.sh and
# trtllm_fixcuda.sh as part of the same staging recipe; all four are taken. A missing path is still
# reported loudly rather than skipped silently.
FILES=(
  "trtllm_prep.sh"
  "trtllm_convert.sh"
  "convert_27b.sh"
  "trtllm_fixcuda.sh"
  "trtllm_verify.sh"
  "lever3/cell_watchdog.sh"
  "lever3/gate_any.py"
  "lever3/lv3_trtllm.sh"
  "adj/build/driver_ctx8192.mojo"
)
# Directories worth taking wholesale if present — the artifact trail the ledger cites.
DIRS=(
  "lever6/runs"       # round 6's certified gate echoes: the fixture-identity reference
  "lever7/logs"       # round 7's UNRETRIEVED probe logs (the open RT=2-despite-spill question)
)

SSH() { gcloud compute ssh --zone="$ZONE" --project="$PROJECT" "angel@$VM" --command="$1" 2>&1 \
          | grep -vE "WARNING|NumPy|IAP tunnel|External IP|please see|Pseudo-term|^$"; }

echo "=== what is actually on the box (read-only inventory) ==="
SSH 'for f in '"$(printf '%s ' "${FILES[@]}")"'; do
       p="$HOME/$f"; if [[ -e "$p" ]]; then
         printf "PRESENT %-34s %8s bytes  md5=%s\n" "$f" "$(stat -c %s "$p")" "$(md5sum "$p" | cut -c1-12)"
       else printf "MISSING %-34s\n" "$f"; fi; done
     for d in '"$(printf '%s ' "${DIRS[@]}")"'; do
       [[ -d "$HOME/$d" ]] && printf "DIR     %-34s %s entries\n" "$d" "$(ls -1 "$HOME/$d" | wc -l)" \
                          || printf "DIR     %-34s absent\n" "$d"; done'

if (( DRY == 1 )); then echo; echo "--dry-run: nothing copied"; exit 0; fi

mkdir -p "$DEST"
echo
echo "=== packing on the box ==="
SSH 'cd "$HOME" && tar czf /tmp/harness_backup.tgz '"$(printf '%s ' "${FILES[@]} ${DIRS[@]}")"' 2>/dev/null;
     ls -la /tmp/harness_backup.tgz 2>/dev/null || echo PACK_FAILED'

echo "=== retrieving to $DEST ==="
gcloud compute scp --zone="$ZONE" --project="$PROJECT" \
  "angel@$VM:/tmp/harness_backup.tgz" "$DEST/harness_backup.tgz" 2>&1 \
  | grep -vE "WARNING|NumPy|IAP tunnel|External IP|please see|^$"
[[ -f "$DEST/harness_backup.tgz" ]] || { echo "RETRIEVAL FAILED — nothing was backed up" >&2; exit 1; }

tar xzf "$DEST/harness_backup.tgz" -C "$DEST"
echo "=== extracted ==="
find "$DEST" -type f -not -name '*.tgz' | sed "s|$DEST/||" | sort | head -40
echo
echo "Retrieved into $DEST (git-trackable). NEXT STEPS, in order:"
echo "  1. git add benchmarks/llm_smoke/nvidia_race/vm_harness && commit — durable at last."
echo "  2. Copy lever7/logs/fa_g3_probe_bn*.log out and READ THEM: they answer whether RT=2 beat v2"
echo "     despite spilling, which the register census alone could not (it proved spill SIZE; spill"
echo "     FREQUENCY in the hot loop is what decides it)."
echo "  3. Only then start measuring."
