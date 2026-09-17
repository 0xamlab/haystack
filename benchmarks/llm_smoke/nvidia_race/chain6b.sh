#!/bin/bash
# chain6b.sh — round-6 phase 0: rebuild shim + probe + arms from the synced tree, then the
# BN sweep (probe correctness + timings at BN 64 / 32 / 128) that decides the key-block width
# of the ship arms before any gate or cell is spent.
set -uo pipefail
cd ~/g3r6/benchmarks/llm_smoke/nvidia_race || exit 1
LOG=${LOG:-/home/angel/chain6b.log}
exec > >(tee -a "$LOG") 2>&1
ts() { date -u +%FT%TZ; }
echo "=== [$(ts)] chain6b START (rebuild + BN sweep) ==="
sudo -n nvidia-smi -pm 1 >/dev/null 2>&1; sudo -n nvidia-smi -lgc 1410,1410 >/dev/null 2>&1
nvidia-smi --query-gpu=index,clocks.current.sm --format=csv,noheader | head -2

STAGE=build bash run_ab_gemma3_round6.sh || { echo BUILD_FAIL; exit 1; }

for BN in 64 32 128; do
  echo "--- [$(ts)] probe --bn $BN (correctness + timing, median of 30) ---"
  CUDA_VISIBLE_DEVICES=1 /tmp/fa_g3_probe --iters 30 --bn "$BN" \
    > ~/lever6/logs/fa_g3_probe_bn$BN.log 2>&1
  rc=$?
  echo "probe bn=$BN rc=$rc fails=$(grep -c ' FAIL' ~/lever6/logs/fa_g3_probe_bn$BN.log)"
  sed -n '/\[3\] timing/,$p' ~/lever6/logs/fa_g3_probe_bn$BN.log
done
echo "=== [$(ts)] chain6b DONE ==="
