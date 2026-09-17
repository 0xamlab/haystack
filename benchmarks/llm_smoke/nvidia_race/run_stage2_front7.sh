#!/usr/bin/env bash
# run_stage2_front7.sh — FRONT 7 stage 2: the raced cells, then the audits that make them quotable.
#
#   1. the interleaved pp256 / pp1024 / gen64 / gen256 sweep, baseline FIRST and LAST (drift armor)
#   2. the three token-exact RAG-4096 prompts x every raced arm, each with its own --no-eos-stop
#      oracle, so every cell carries a real G0 (round 6's fix; before that RAG-4096 had only ever
#      been gated on self-consistency, which cannot detect a lever that is deterministically wrong)
#   3. front7_clocks.py over the 200 ms sampler + the CELL_WINDOW lines: per-cell off-pin time,
#      minimum clock, power draw and a power-cap-vs-thermal attribution. FRONT 6 disclosed a
#      zero-drift breach it could only bound with an argument because its sampler ran at 1 Hz.
#   4. scripts/audit_tc_flags.sh: the flag audit, with FRONT 7's runtime-effect fields
#      (o16_twin_armed, o16_declined_at_runtime, o16_verify_pass, lt_insitu_frozen_4). A flag
#      literal can be present while the effect is absent, so the audit records the effect.
#   5. front7_summarize.py: the ratio table, the baseline bracket, and the check that `_h0`
#      reproduces FRONT 6's published cells — because `_h0` IS FRONT 6's ship arm rebuilt and a
#      baseline that does not reproduce makes every ratio in the round meaningless.
#
# usage: bash run_stage2_front7.sh                      # _h0 _h1 _h2, all three RAG prompts
#        ARMS="_h0 _h1 _h0" RAG_ARMS="_h0 _h1" RAG_PROMPTS="0" bash run_stage2_front7.sh
set -uo pipefail
cd "$HOME/front7/repo" || exit 1
MEAS=${MEAS:-$HOME/trtllm/front7}
AB=benchmarks/llm_smoke/nvidia_race/run_ab_7b_front7.sh
export ROUND=${ROUND:-s2}
export ARMS=${ARMS:-_h0 _h1 _h2 _h0}
export RAG_ARMS=${RAG_ARMS:-_h0 _h1 _h2}
export RAG_PROMPTS=${RAG_PROMPTS:-0 1 2}
LOG="$MEAS/stage2.log"

echo "############ stage 2: the raced cells ############" | tee "$LOG"
echo "ARMS=$ARMS RAG_ARMS=$RAG_ARMS RAG_PROMPTS=$RAG_PROMPTS ROUND=$ROUND" | tee -a "$LOG"
nvidia-smi --query-gpu=clocks.sm,power.limit,temperature.gpu,memory.used --format=csv,noheader | tee -a "$LOG"

PROOF=0 BUILD_ARMS=0 RUN_SWEEP=1 RUN_RAG=1 RUN_VERIFY=0 RUN_DIAG=0 STAGE=2 \
    bash "$AB" 2>&1 | tee -a "$LOG" | grep --line-buffered -E "^== |^prefill|^gen |G0 RESULT|G1 RESULT|CELL_WINDOW|DECLINED|WARN|CLOCKS:|AB_FRONT7_DONE"

echo "############ 3. per-cell clock/power attribution (200 ms) ############" | tee -a "$LOG"
python3 benchmarks/llm_smoke/nvidia_race/front7_clocks.py \
    "$MEAS/clocks_stage2_200ms.csv" "$LOG" --pin 1410 --thresh 0.5 \
    --json "$MEAS/clocks_stage2.json" 2>&1 | tee -a "$LOG"

echo "############ 4. flag audit ############" | tee -a "$LOG"
bash scripts/audit_tc_flags.sh --bin-dir "$HOME/front7/bin" --logs "$MEAS" \
    --out "$MEAS/flag_audit.json" 2>&1 | tee -a "$LOG"

echo "############ 5. summary + ratios ############" | tee -a "$LOG"
python3 benchmarks/llm_smoke/nvidia_race/front7_summarize.py "$MEAS" \
    --trtllm "$MEAS/trtllm_rerace7.json" --clocks-json "$MEAS/clocks_stage2.json" 2>&1 | tee -a "$LOG"

nvidia-smi --query-gpu=clocks.sm,temperature.gpu,memory.used --format=csv,noheader | tee -a "$LOG"
echo STAGE2_FRONT7_DONE | tee -a "$LOG"
