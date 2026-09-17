#!/bin/bash
# chain6c.sh — round-6 phase 2 (after the interim table): second brackets for the 20-run-median
# protocol on the priority cells, nsys captures + exact measured-request decomposition
# (priming-trace subtraction), final summary. Optional attribution/extra arms via env.
set -uo pipefail
cd ~/g3r6/benchmarks/llm_smoke/nvidia_race || exit 1
LOG=${LOG:-/home/angel/chain6c.log}
exec > >(tee -a "$LOG") 2>&1
ts() { date -u +%FT%TZ; }
SHIP=${SHIP:-R6_kv16_bn32}
echo "=== [$(ts)] chain6c START (ship=$SHIP) ==="
sudo -n nvidia-smi -pm 1 >/dev/null 2>&1; sudo -n nvidia-smi -lgc 1410,1410 >/dev/null 2>&1

echo "--- [$(ts)] timing bracket 2: rag4096 ---"
BUILD_ARMS=0 STAGE=timing CELLTAG=b ARM_A=R6_base ARM_B="$SHIP" ARM_C= \
  PROMPTS="rag4096:/tmp/g3rag/rag4096.txt:256" \
  bash run_ab_gemma3_round6.sh || { echo TIMING_RAG2_FAIL; exit 1; }

echo "--- [$(ts)] timing bracket 2: pp1024 ---"
BUILD_ARMS=0 STAGE=timing CELLTAG=b ARM_A=R6_base ARM_B="$SHIP" ARM_C= \
  PROMPTS="pp1024:/tmp/g3pp1024/prompt_0000.txt:1" \
  bash run_ab_gemma3_round6.sh || { echo TIMING_PP1024_2_FAIL; exit 1; }

if [[ ${WANT_BRACKET3:-0} == 1 ]]; then
  echo "--- [$(ts)] timing bracket 3: rag4096 + pp1024 ---"
  BUILD_ARMS=0 STAGE=timing CELLTAG=c ARM_A=R6_base ARM_B="$SHIP" ARM_C= \
    PROMPTS="rag4096:/tmp/g3rag/rag4096.txt:256 pp1024:/tmp/g3pp1024/prompt_0000.txt:1" \
    bash run_ab_gemma3_round6.sh || echo TIMING3_WARN
fi

if [[ ${WANT_PP256:-0} == 1 ]]; then
  echo "--- [$(ts)] pp256 bracket (regression guard) ---"
  BUILD_ARMS=0 STAGE=timing CELLTAG=b ARM_A=R6_base ARM_B="$SHIP" ARM_C= \
    PROMPTS="pp256:/tmp/g3pp256/prompt_0000.txt:1" \
    bash run_ab_gemma3_round6.sh || echo TIMING_PP256_WARN
fi

echo "--- [$(ts)] nsys captures + decomposition ---"
GPU=${GPU:-1} bash run_nsys_gemma3_round6.sh || echo NSYS_WARN

echo "--- [$(ts)] final summary ---"
MEAS=~/lever6 /usr/bin/python3 summarize_gemma3_round6.py R6_base "$SHIP" || true
echo "=== [$(ts)] chain6c DONE ==="
