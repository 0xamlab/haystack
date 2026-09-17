#!/bin/bash
# vm_sync_r6.sh — materialise the round-6 source tree at ~/g3r6 on trtllm-gemma-us-west1-c.
# NOTE (measured 2026-09-16): this box CANNOT reach github.com:443 (connection times out), so
# the clone below only works where egress exists; the round-6 session synced with tar+`gcloud
# compute scp` from the local worktree instead:
#   COPYFILE_DISABLE=1 tar czf /tmp/g3r6.tgz --exclude __pycache__ --exclude .pixi \
#     attention_forge benchmarks mojo mojoproject.toml packages scripts
#   gcloud compute scp ... /tmp/g3r6.tgz angel@trtllm-gemma-us-west1-c:g3r6.tgz
#   ssh: rm -rf ~/g3r6 && mkdir -p ~/g3r6 && tar xzf ~/g3r6.tgz -C ~/g3r6
# Keep the arm binaries traceable to the pushed commit by syncing only from a clean, committed,
# PUSHED worktree state (audit_tc_flags.sh records branch/head from the tree it is run in).
set -euo pipefail
BRANCH=${BRANCH:-feat/gemma-fa2-port}
if [ -d "$HOME/g3r6/.git" ]; then
  cd "$HOME/g3r6"
  git fetch --depth 50 origin "$BRANCH"
  git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH" "origin/$BRANCH"
  git reset --hard "origin/$BRANCH"
else
  rm -rf "$HOME/g3r6"
  git clone --depth 50 --branch "$BRANCH" --single-branch \
    https://github.com/thyn-ai/algenta.git "$HOME/g3r6"
  cd "$HOME/g3r6"
fi
echo "HEAD=$(git rev-parse --short HEAD) branch=$(git rev-parse --abbrev-ref HEAD)"
ls benchmarks/llm_smoke/nvidia_race/run_ab_gemma3_round6.sh >/dev/null
ls "$HOME/adj/build/driver_ctx8192.mojo" >/dev/null && echo DRIVER_OK
echo SYNC_DONE
