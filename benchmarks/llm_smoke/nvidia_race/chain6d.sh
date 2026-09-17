#!/bin/bash
# chain6d.sh — round-6 phase 2 (budget-trimmed): rag4096 bracket 2 (CELLTAG=b, so the pooled
# median reaches n=14 on the priority cell), TRIMMED nsys (base+ship x rag4096+priming = the
# exact measured-request subtraction set), mr_extract + mr_subtract, final pooled summary.
set -uo pipefail
cd ~/g3r6/benchmarks/llm_smoke/nvidia_race || exit 1
LOG=/home/angel/chain6d.log
exec > >(tee -a "$LOG") 2>&1
ts() { date -u +%FT%TZ; }
SHIP=R6_kv16_bn32
PY=/usr/bin/python3
echo "=== [$(ts)] chain6d START ==="
sudo -n nvidia-smi -pm 1 >/dev/null 2>&1; sudo -n nvidia-smi -lgc 1410,1410 >/dev/null 2>&1

echo "--- [$(ts)] rag4096 bracket 2 (CELLTAG=b) ---"
BUILD_ARMS=0 STAGE=timing CELLTAG=b ARM_A=R6_base ARM_B="$SHIP" ARM_C= \
  PROMPTS="rag4096:/tmp/g3rag/rag4096.txt:256" \
  bash run_ab_gemma3_round6.sh || { echo RAG2_FAIL; exit 1; }

echo "--- [$(ts)] trimmed nsys: base+ship x rag4096+priming ---"
mkdir -p /tmp/g3short32
$PY -c "print(' '.join(open('/tmp/g3pp256/prompt_0000.txt').read().replace(',', ' ').split()[:32]))" \
  > /tmp/g3short32/prompt_0000.txt
[[ $(wc -w < /tmp/g3short32/prompt_0000.txt) -eq 32 ]] || { echo SHORT32_BAD; exit 1; }
# rewrite the capture list for this session: ONLY base+ship x rag4096+priming (4 captures,
# ~15 min) — the exact set the measured-request subtraction needs; pp1024 captures dropped
# for budget (the pp1024 claim rides its timing bracket, and the GEMM-parity extraction uses
# the rag4096 pair).
$PY - <<'PY'
import re
p = 'run_nsys_gemma3_round6.sh'
s = open(p).read()
s2 = re.sub(r'CAPTURES=\(.*?\n\)\n', '''CAPTURES=(
  "R6_base:rag4096:/tmp/g3rag/rag4096.txt:1"
  "R6_kv16_bn32:rag4096:/tmp/g3rag/rag4096.txt:1"
  "R6_base:priming:/tmp/g3short32/prompt_0000.txt:1"
  "R6_kv16_bn32:priming:/tmp/g3short32/prompt_0000.txt:1"
)
''', s, count=1, flags=re.S)
assert s2 != s and 'R6_kv16_bn32:priming' in s2
open(p, 'w').write(s2)
print("CAPTURES trimmed to 4")
PY
GPU=${GPU:-1} bash run_nsys_gemma3_round6.sh || echo NSYS_WARN

echo "--- [$(ts)] measured-request extraction + priming subtraction ---"
for arm in R6_base "$SHIP"; do
  $PY mr_extract_gemma3_round6.py ~/lever6/nsys/${arm}_rag4096.sqlite --cell rag4096 \
      --json ~/lever6/mr_${arm}_rag4096.json || echo "MRX_FAIL $arm rag"
  $PY mr_extract_gemma3_round6.py ~/lever6/nsys/${arm}_priming.sqlite --cell pp256 \
      --json ~/lever6/mr_${arm}_priming.json || echo "MRX_FAIL $arm priming"
  $PY mr_subtract_gemma3_round6.py ~/lever6/mr_${arm}_rag4096.json \
      ~/lever6/mr_${arm}_priming.json rag4096 || echo "MSUB_FAIL $arm"
done

echo "--- [$(ts)] final pooled summary ---"
MEAS=~/lever6 $PY summarize_gemma3_round6.py R6_base "$SHIP" || true
echo "=== [$(ts)] chain6d DONE ==="
nvidia-smi --query-gpu=index,clocks.current.sm,memory.used --format=csv,noheader
