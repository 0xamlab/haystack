#!/bin/bash
# vm_sync_r17.sh — RUN THIS ON THE LOCAL MAC, not on the VM. Materialises the round-17 worktree at
# ~/g3r17 on trtllm-gemma-us-west1-c. Same shape and same refusals as vm_sync_r7.sh: the box has NO
# github egress (measured round 6 — clone times out on github.com:443), so the tree is tar'd here
# and `gcloud compute scp`'d over, and this script REFUSES to sync a dirty or unpushed tree because
# the measured binaries must be traceable to a commit that exists upstream.
#
# Usage:  bash vm_sync_r17.sh            (from anywhere; WT defaults to the round-17 worktree)
set -euo pipefail
WT=${WT:-/Users/angel/Developer/decision-engine/.qwen/worktrees/gemma-front7}
VM=${VM:-trtllm-gemma-us-west1-c}
ZONE=${ZONE:-us-west1-c}
PROJECT=${PROJECT:-eplanev2}
REMOTE_DIR=${REMOTE_DIR:-g3r17}

cd "$WT"
BRANCH=$(git rev-parse --abbrev-ref HEAD)
HEAD=$(git rev-parse --short HEAD)

if [[ -n "$(git status --porcelain)" ]]; then
  echo "REFUSING: the worktree is dirty. Commit (or stash) first — the measured binaries must"
  echo "be traceable to a commit. Dirty paths:"
  git status --porcelain | head -20
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
echo "syncing $BRANCH @ $HEAD -> $VM:$REMOTE_DIR"

TGZ=/tmp/g3r17.tgz
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
ls ~/$REMOTE_DIR/benchmarks/llm_smoke/nvidia_race/run_ab_gemma3_round17.sh >/dev/null && echo TREE_OK
# the shim #includes a GENERATED header and /tmp is tmpfs (wiped per stop), so clear the build dir
# and let the round-17 build regenerate BOTH shim flavours from this tree's tc_shim.cu.
rm -rf /tmp/g3r17tc && mkdir -p /tmp/g3r17tc
mkdir -p ~/lever17/logs ~/lever17/runs ~/lever17/clocks
echo SYNC_DONE
EOS

# record the exact head the VM tree came from, so the audit and the ledger can cite it
gcloud compute ssh --zone="$ZONE" --project="$PROJECT" "angel@$VM" -- \
  "echo '$BRANCH $HEAD' > ~/$REMOTE_DIR/.synced_head && cat ~/$REMOTE_DIR/.synced_head"
