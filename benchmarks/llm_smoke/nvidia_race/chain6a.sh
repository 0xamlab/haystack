#!/bin/bash
# chain6a.sh — round-6 phase 1 (interim-table path) on trtllm-gemma-us-west1-c.
# Budget order: smoke -> oracle gates (ship candidate + baseline; the checkpoint is a fresh
# conversion, so a gate is re-earned, not inherited) -> rag4096 bracket -> pp1024 bracket ->
# same-session TRT-LLM re-serve -> interim summary. 2 arms interleaved (A..B..A drift armor).
# Ship candidate = R6_kv16_bn32 (FA2 + f16 K/V twin + BN32 + dbuf-at-32); baseline R6_base is
# #998's R5_all2 flag set rebuilt from this branch. Aborts on first failure: a failed gate
# means no timing cells, no ratios, nothing.
set -uo pipefail
cd ~/g3r6/benchmarks/llm_smoke/nvidia_race || exit 1
LOG=${LOG:-/home/angel/chain6a.log}
exec > >(tee -a "$LOG") 2>&1
ts() { date -u +%FT%TZ; }
SHIP=${SHIP:-R6_kv16_bn32}
echo "=== [$(ts)] chain6a START (ship=$SHIP) ==="

echo "--- [$(ts)] clock check ---"
nvidia-smi --query-gpu=index,clocks.current.sm --format=csv,noheader | head -3
sudo -n nvidia-smi -pm 1 >/dev/null 2>&1; sudo -n nvidia-smi -lgc 1410,1410 >/dev/null 2>&1

echo "--- [$(ts)] smoke ($SHIP, R6_base) ---"
BUILD_ARMS=0 STAGE=smoke ARM_A=R6_base ARM_B="$SHIP" ARM_C= \
  bash run_ab_gemma3_round6.sh || { echo SMOKE_FAIL; exit 1; }
echo "smoke verdicts:"
for a in "$SHIP" R6_base; do
  grep -E "flash attention( v2)? (ARMED|DECLINED)" ~/lever6/runs/smoke_${a}_pp1024.out || true
  grep -m1 "^G3 FLAGS:" ~/lever6/runs/smoke_${a}_pp1024.out || true
done
if grep -q "v2 DECLINED" ~/lever6/runs/smoke_${SHIP}_pp1024.out; then
  echo "FA2 DECLINED AT RUNTIME in the ship arm -- cells would measure the round-5 kernel; ABORT"
  exit 1
fi

echo "--- [$(ts)] gate $SHIP ---"
BUILD_ARMS=0 STAGE=gate ARM="$SHIP" bash run_ab_gemma3_round6.sh \
  || { echo GATE_SHIP_FAIL; exit 1; }
echo "--- [$(ts)] gate R6_base ---"
BUILD_ARMS=0 STAGE=gate ARM=R6_base bash run_ab_gemma3_round6.sh \
  || { echo GATE_BASE_FAIL; exit 1; }

echo "--- [$(ts)] timing bracket 1: rag4096 (priority) ---"
BUILD_ARMS=0 STAGE=timing ARM_A=R6_base ARM_B="$SHIP" ARM_C= \
  PROMPTS="rag4096:/tmp/g3rag/rag4096.txt:256" \
  bash run_ab_gemma3_round6.sh || { echo TIMING_RAG1_FAIL; exit 1; }

echo "--- [$(ts)] timing bracket 1: pp1024 ---"
BUILD_ARMS=0 STAGE=timing ARM_A=R6_base ARM_B="$SHIP" ARM_C= \
  PROMPTS="pp1024:/tmp/g3pp1024/prompt_0000.txt:1" \
  bash run_ab_gemma3_round6.sh || { echo TIMING_PP1024_1_FAIL; exit 1; }

echo "--- [$(ts)] same-session TRT-LLM re-serve ---"
GPU=${GPU:-1} bash ~/lever3/lv3_trtllm.sh || echo RESERVE_WARN
cp -f ~/lever3/runs/trtllm_pp256.json ~/lever3/runs/trtllm_pp1024.json \
      ~/lever3/runs/trtllm_rag4096.json ~/lever6/runs/ 2>/dev/null || true

echo "--- [$(ts)] interim summary ---"
MEAS=~/lever6 /usr/bin/python3 summarize_gemma3_round6.py R6_base "$SHIP" || true
echo "=== [$(ts)] chain6a DONE ==="
