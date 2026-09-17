#!/bin/bash
# vm_sync_r7.sh — RUN THIS ON THE LOCAL MAC, not on the VM. Materialises the round-7 worktree at
# ~/g3r7 on trtllm-gemma-us-west1-c.
#
# WHY NOT git clone: the box has NO github egress (measured round 6 — clone times out on
# github.com:443), so the tree is tar'd here and `gcloud compute scp`'d over. The arm binaries
# still have to be traceable to a pushed commit, so this script REFUSES to sync a dirty or
# unpushed tree: sync only from a clean, committed, PUSHED state, and audit_tc_flags.sh then
# records a head that actually exists upstream. (On the VM tree the audit's branch/head fields
# read "unknown" by construction — that is expected and was stated in round 6's integrity notes.)
#
# Usage:  bash vm_sync_r7.sh            (from anywhere; WT defaults to the round-7 worktree)
set -euo pipefail
WT=${WT:-/Users/angel/Developer/decision-engine/.qwen/worktrees/gemma-front7}
VM=${VM:-trtllm-gemma-us-west1-c}
ZONE=${ZONE:-us-west1-c}
PROJECT=${PROJECT:-eplanev2}
REMOTE_DIR=${REMOTE_DIR:-g3r7}

cd "$WT"
BRANCH=$(git rev-parse --abbrev-ref HEAD)
HEAD=$(git rev-parse --short HEAD)

# ── refuse to sync a state that cannot be traced back to upstream ──
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

TGZ=/tmp/g3r7.tgz
rm -f "$TGZ"
# COPYFILE_DISABLE stops macOS from writing ._ AppleDouble sidecars into the tar, which otherwise
# land in the VM tree as junk files nvcc and the audit both trip over.
COPYFILE_DISABLE=1 tar czf "$TGZ" \
  --exclude __pycache__ --exclude .pixi --exclude .git \
  attention_forge benchmarks mojo mojoproject.toml packages scripts
echo "tar: $(stat -f %z "$TGZ") bytes"

gcloud compute scp --zone="$ZONE" --project="$PROJECT" "$TGZ" "angel@$VM:g3r7.tgz"
gcloud compute ssh --zone="$ZONE" --project="$PROJECT" "angel@$VM" -- bash -s <<'EOS'
set -uo pipefail
rm -rf ~/g3r7 && mkdir -p ~/g3r7
tar xzf ~/g3r7.tgz -C ~/g3r7
echo "REMOTE_HEAD_MARKER=$(cat ~/g3r7/.synced_head 2>/dev/null || echo none)"
ls ~/g3r7/benchmarks/llm_smoke/nvidia_race/chain7probe.sh >/dev/null && echo TREE_OK
# the shim #includes a GENERATED header; an instance restart wipes /tmp, so make sure the
# round-7 build regenerates it rather than reusing a stale one from a previous round.
rm -rf /tmp/g3r7tc && mkdir -p /tmp/g3r7tc
mkdir -p ~/lever7/logs ~/lever7/runs ~/lever7/clocks
echo SYNC_DONE
EOS

# record the exact head the VM tree came from, so the audit and the ledger can cite it
gcloud compute ssh --zone="$ZONE" --project="$PROJECT" "angel@$VM" -- \
  "echo '$BRANCH $HEAD' > ~/g3r7/.synced_head && cat ~/g3r7/.synced_head"
