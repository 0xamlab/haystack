#!/bin/bash
# chain7stage.sh — ROUND 7 RE-STAGE on trtllm-gemma-us-west1-c, run FIRST in every VM-on window.
#
# The box was STOPPED between rounds. Its local SSD persists (so ~/trtllm, ~/lever3 and
# ~/lever6/runs — round 6's certified gate echoes — are all still there) but /tmp AND the tmpfs
# RAM blob do NOT, which means both the prompt fixtures (/tmp/g3pp256, /tmp/g3pp1024,
# /tmp/g3race500, /tmp/g3rag) and the converted checkpoint (/mnt/ramblob/g3conv27b) are gone and
# must be regenerated before anything is measured.
#
# "Regenerated from the same recipe" is a CLAIM, not evidence, so this chain proves identity the
# way round 6 did: every driver run echoes the exact prompt id list it ingested into its JSON, so
# round 6's gate cells carry the ORIGINAL ids, and comparing the regenerated fixtures against
# those echoes is a direct token-for-token check with no re-derivation. FIXREF_RUNS points the
# checker at ~/lever6/runs — the NEWEST echoes the oracle certified, on this same checkpoint.
#
# Nothing downstream may run until this prints STAGE_OK.
#
# Usage (on the VM):  bash chain7stage.sh
set -uo pipefail
L7=${L7:-$HOME/lever7}
GPU=${GPU:-1}
TR=${TR:-$HOME/trtllm}
CKPT=${CKPT:-/mnt/ramblob/g3conv27b}
LOG=${LOG:-$L7/chain7stage.log}
mkdir -p "$L7/logs" "$L7/runs" "$L7/clocks"
exec > >(tee -a "$LOG") 2>&1
ts() { date -u +%FT%TZ; }

HB=$L7/heartbeat.log
PHASE="stage"
( while true; do echo "$(date -u +%FT%TZ) chain7stage GPU=$GPU phase=$PHASE pid=$$" >> "$HB";
    sleep 60; done ) &
HB_PID=$!
trap 'kill $HB_PID 2>/dev/null' EXIT
setphase() { PHASE="$1"; echo "=== [$(ts)] PHASE: $1 ==="; }

setphase "inventory"
echo "--- what survived the stop (local SSD) ---"
for d in "$TR" "$HOME/lever3" "$HOME/lever6/runs" "$HOME/adj/build"; do
  if [[ -d "$d" ]]; then echo "PRESENT  $d ($(ls -1 "$d" 2>/dev/null | wc -l) entries)";
  else echo "MISSING  $d"; fi
done
echo "--- what the stop wiped (tmpfs) ---"
for d in /tmp/g3pp256 /tmp/g3pp1024 /tmp/g3race500 /tmp/g3rag "$CKPT"; do
  [[ -e "$d" ]] && echo "PRESENT  $d" || echo "WIPED    $d (expected — must be regenerated)"
done
echo "--- staging scripts available ---"
ls -1 "$TR"/*.sh 2>/dev/null || { echo "NO ~/trtllm/*.sh FOUND — cannot re-stage; ABORT"; exit 1; }
echo "--- gpu state before staging (want 0 MiB on every GPU, no leftover watchers) ---"
nvidia-smi --query-gpu=index,memory.used,clocks.current.sm --format=csv,noheader
pgrep -af "driver_ctx8192|trtllm|nsys" | head -10 || echo "no stale benchmark processes"

setphase "prep_fixtures"
if [[ -x "$TR/trtllm_prep.sh" || -f "$TR/trtllm_prep.sh" ]]; then
  bash "$TR/trtllm_prep.sh" 2>&1 | tail -25 || { echo PREP_FAIL; exit 1; }
else
  echo "NO trtllm_prep.sh — ABORT (do not hand-roll fixtures: identity must be provable)"
  exit 1
fi
for f in /tmp/g3pp256/prompt_0000.txt /tmp/g3pp1024/prompt_0000.txt \
         /tmp/g3race500/prompt_0000.txt /tmp/g3rag/rag4096.txt; do
  if [[ -f "$f" ]]; then
    echo "FIXTURE  $f  ($(wc -w < "$f") ids)"
  else
    echo "FIXTURE MISSING $f — ABORT"; exit 1
  fi
done

setphase "fixture_identity"
# Round 6's gate cells are the reference. If lever6 is absent the checker says so and fails rather
# than silently passing — measuring against a prompt set the oracle never certified is a different
# experiment from the one it certified.
FIXREF_RUNS="$HOME/lever6/runs" FIXREF_MARKER="$L7/FIXTURES_OK" \
  /usr/bin/python3 "$HOME/g3r7/benchmarks/llm_smoke/nvidia_race/check_fixtures_gemma3_round5.py"
rc=$?
if (( rc != 0 )) || [[ ! -f "$L7/FIXTURES_OK" ]]; then
  echo "FIXTURE_IDENTITY_FAIL — ABORT. Nothing may be measured against unproven fixtures."
  exit 1
fi
echo "FIXTURE_IDENTITY_OK=True (verified against round 6's certified gate echoes)"

setphase "convert_checkpoint"
if [[ -f "$TR/trtllm_convert.sh" ]]; then
  bash "$TR/trtllm_convert.sh" 2>&1 | tail -30 || { echo CONVERT_FAIL; exit 1; }
else
  echo "NO trtllm_convert.sh — ABORT"; exit 1
fi
[[ -d "$CKPT" ]] || { echo "CHECKPOINT MISSING at $CKPT after convert — ABORT"; exit 1; }
echo "CHECKPOINT present: $(du -sh "$CKPT" 2>/dev/null | cut -f1) at $CKPT"

setphase "clock_pin"
sudo -n nvidia-smi -pm 1 >/dev/null 2>&1
sudo -n nvidia-smi -lgc 1410,1410 >/dev/null 2>&1
nvidia-smi --query-gpu=index,clocks.current.sm,clocks.max.sm,persistence_mode --format=csv,noheader
PIN=$(nvidia-smi -i "$GPU" --query-gpu=clocks.current.sm --format=csv,noheader,nounits)
echo "GPU$GPU clocks.current.sm=$PIN (want 1410 — ZERO off-pin tolerance)"
if [[ "$PIN" != "1410" ]]; then
  echo "OFF_PIN: $PIN != 1410. Re-pin and re-run; do not measure."
  exit 1
fi

setphase "done"
echo "=== [$(ts)] STAGE_OK — fixtures proven identical to round 6's certified echoes, checkpoint"
echo "    converted, GPU$GPU pinned and verified at 1410 MHz. chain7probe.sh may now run. ==="
