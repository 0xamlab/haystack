#!/bin/bash
# vm_sync_r18.sh — RUN THIS ON THE LOCAL MAC, not on the VM. Materialises the round-18 worktree at
# ~/g3r18 on trtllm-gemma-us-west1-c. Same shape and same refusals as vm_sync_r17.sh: the box has
# NO github egress (measured round 6 — clone times out on github.com:443), so the tree is tar'd
# here and `gcloud compute scp`'d over, and this script REFUSES to sync a dirty or unpushed tree
# because the measured binaries must be traceable to a commit that exists upstream.
#
# Usage:  bash vm_sync_r18.sh            (from anywhere; WT defaults to the round-18 worktree)
set -euo pipefail
WT=${WT:-/Users/angel/Developer/decision-engine/.qwen/worktrees/gemma-r18}
VM=${VM:-trtllm-gemma-us-west1-c}
ZONE=${ZONE:-us-west1-c}
PROJECT=${PROJECT:-eplanev2}
REMOTE_DIR=${REMOTE_DIR:-g3r18}

cd "$WT"
BRANCH=$(git rev-parse --abbrev-ref HEAD)
HEAD=$(git rev-parse --short HEAD)

# THE DIRTY CHECK, AND THE ONE PATH IT MUST NOT TRIP ON. The rule is right and stays: the measured
# binaries must be traceable to a commit that exists upstream. But `git status --porcelain` also
# lists UNTRACKED files, and `mojo_env/.pixi` is a documented never-commit local artifact — the
# pixi environment this worktree shares with another one. `mojo_env/.gitignore` carries `.pixi/*`
# + `!.pixi/config.toml`, which ignores the CONTENTS of a real `.pixi` directory but not a
# *symlink* named `.pixi`, so every worktree that links its env shows this one path as `??`.
# This is not theoretical: it aborted round 18's first window 5 s after the instance came up,
# burning the boot and ~4.4 min of VM-on for a precondition that could have been checked before
# the start. So: ignore that exact path, and nothing else — any tracked modification, any staged
# change, or any other untracked file still refuses.
DIRTY=$(git status --porcelain | grep -v '^?? mojo_env/\.pixi$' || true)
if [[ -n "$DIRTY" ]]; then
  echo "REFUSING: the worktree is dirty. Commit (or stash) first — the measured binaries must"
  echo "be traceable to a commit. Dirty paths:"
  echo "$DIRTY" | head -20
  exit 1
fi
git fetch --quiet origin "$BRANCH" 2>/dev/null || true
if ! git rev-parse --quiet --verify "origin/$BRANCH" >/dev/null; then
  echo "REFUSING: origin/$BRANCH does not exist. Push the branch first:"
  echo "  git push -u origin $BRANCH"
  exit 1
fi
if [[ "$(git rev-parse HEAD)" != "$(git rev-parse "origin/$BRANCH")" ]]; then
  echo "REFUSING: HEAD ($HEAD) != origin/$BRANCH ($(git rev-parse --short "origin/$BRANCH"))."
  echo "Push first so the synced tree matches a commit that exists upstream."
  exit 1
fi
echo "PREFLIGHT OK: $BRANCH @ $HEAD is clean (modulo the never-committed mojo_env/.pixi) and pushed"
# PREFLIGHT_ONLY lets the window controller run every refusal above BEFORE it starts the instance.
# A local precondition must never cost VM-on minutes: the cap is measured from lastStartTimestamp,
# so a start followed by an immediate refusal is pure burn.
if [[ "${PREFLIGHT_ONLY:-0}" == "1" ]]; then
  exit 0
fi
echo "syncing $BRANCH @ $HEAD -> $VM:$REMOTE_DIR"

TGZ=/tmp/g3r18.tgz
rm -f "$TGZ"
# COPYFILE_DISABLE stops macOS writing ._ AppleDouble sidecars into the tar, which otherwise land
# in the VM tree as junk nvcc and the flag audit both trip over.
COPYFILE_DISABLE=1 tar czf "$TGZ" \
  --exclude __pycache__ --exclude .pixi --exclude .git \
  attention_forge benchmarks mojo mojoproject.toml packages scripts
echo "tar: $(stat -f %z "$TGZ") bytes"

gcloud compute scp --zone="$ZONE" --project="$PROJECT" "$TGZ" "angel@$VM:$REMOTE_DIR.tgz"
gcloud compute ssh --zone="$ZONE" --project="$PROJECT" "angel@$VM" -- bash -s <<EOS
set -uo pipefail
rm -rf ~/$REMOTE_DIR && mkdir -p ~/$REMOTE_DIR
tar xzf ~/$REMOTE_DIR.tgz -C ~/$REMOTE_DIR
ls ~/$REMOTE_DIR/benchmarks/llm_smoke/nvidia_race/run_ab_gemma3_round18.sh >/dev/null && echo TREE_OK
ls ~/$REMOTE_DIR/benchmarks/llm_smoke/nvidia_race/chain18.sh >/dev/null && echo CHAIN18_OK
ls ~/$REMOTE_DIR/benchmarks/llm_smoke/nvidia_race/check_bitident_gemma3_round18.py >/dev/null && echo BITIDENT_OK
# the shim #includes a GENERATED header and /tmp is tmpfs (wiped per stop), so clear the build dir
# and let the round-18 build regenerate the stock shim from this tree's tc_shim.cu.
rm -rf /tmp/g3r18tc && mkdir -p /tmp/g3r18tc
mkdir -p ~/lever18/logs ~/lever18/runs ~/lever18/clocks
echo SYNC_DONE
EOS

# record the exact head the VM tree came from, so the audit and the ledger can cite it
gcloud compute ssh --zone="$ZONE" --project="$PROJECT" "angel@$VM" -- \
  "echo '$BRANCH $HEAD' > ~/$REMOTE_DIR/.synced_head && cat ~/$REMOTE_DIR/.synced_head"
