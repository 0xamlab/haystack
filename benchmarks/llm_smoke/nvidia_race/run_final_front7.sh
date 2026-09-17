#!/usr/bin/env bash
# run_final_front7.sh — FRONT 7's measured sequence on the FINAL binaries, in the order the
# owner's protocol requires: bit-identity proof, then the diagnostic, then the raced cells, then
# the audits that make them quotable.
#
# Nothing here is a new lever; it is the sequence, with the two properties that make the numbers
# quotable built into the order rather than left to be remembered:
#   * the proof runs BEFORE any speed claim, on the same binaries that are raced;
#   * the raced cells are interleaved with the baseline bracketing them (drift armor), and every
#     cell is gate-checked inside its own process by construction.
set -uo pipefail
cd "$HOME/front7/repo" || exit 1
MEAS=${MEAS:-$HOME/trtllm/front7}
AB=benchmarks/llm_smoke/nvidia_race/run_ab_7b_front7.sh
export ROUND=${ROUND:-fin}

wait_free() {   # nothing of ours may be on the GPU or mid-build when a stage starts
    for _ in $(seq 1 360); do
        [[ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)" ]] \
            && ! pgrep -x mojo >/dev/null 2>&1 && ! pgrep -x nvcc >/dev/null 2>&1 && return 0
        sleep 5
    done
    echo "WARN: still busy after 30 min; proceeding anyway"
}

echo "############ A. the binaries this round races ############"
ls -la --time-style=+%FT%T "$HOME/front7/bin/" | tail -8
md5sum "$HOME/front7/bin/"qwen25_7b_p3_graph_cuda_h* 2>/dev/null
wait_free

echo "############ B. bit-identity proof on the FINAL binaries (_hv) ############"
PROOF=0 BUILD_ARMS=0 RUN_SWEEP=0 RUN_RAG=0 RUN_DIAG=0 RUN_VERIFY=1 STAGE=11 \
    bash "$AB" > "$MEAS/final_verify.log" 2>&1
echo "  rc=$?"
grep -E "TC O16 VERIFY|O16 VERIFY RESULT|G0 RESULT|G1 RESULT|^prefill|DECLINED" \
    "$MEAS/final_verify.log" | sort | uniq -c | sort -rn | head -12

echo "############ C. the in-situ cublasLt table (_hd, diagnostic) ############"
PROOF=0 BUILD_ARMS=0 RUN_SWEEP=0 RUN_RAG=0 RUN_VERIFY=0 RUN_DIAG=1 DIAG_PROMPT=0 \
    LT_SAMPLES=${LT_SAMPLES:-10} DIAG_RUNS=${DIAG_RUNS:-5} STAGE=12 \
    bash "$AB" > "$MEAS/final_diag.log" 2>&1
echo "  rc=$?"
cp "$MEAS/bench_hd_diag_rag0_${ROUND}.log" "$MEAS/insitu_table_final.log" 2>/dev/null || true
grep -E "TC LT INSITU: shape|TC LT: tuned|LT INSITU: FROZEN|G0 RESULT|^prefill4096" \
    "$MEAS/final_diag.log" | head -14

echo "############ D. the raced cells ############"
ARMS="${ARMS:-_h0 _h1 _h2 _h0}" RAG_ARMS="${RAG_ARMS:-_h0 _h1 _h2}" \
    RAG_PROMPTS="${RAG_PROMPTS:-0 1 2}" STAGE=2 \
    PROOF=0 BUILD_ARMS=0 RUN_SWEEP=1 RUN_RAG=1 RUN_VERIFY=0 RUN_DIAG=0 \
    bash "$AB" > "$MEAS/stage2.log" 2>&1
echo "  rc=$?"
grep -E "^== _h|^prefill|^gen |G0 RESULT|G1 RESULT|DECLINED" "$MEAS/stage2.log" | head -60

echo "############ E. per-cell clock/power attribution (200 ms) ############"
python3 benchmarks/llm_smoke/nvidia_race/front7_clocks.py \
    "$MEAS/clocks_stage2_200ms.csv" "$MEAS/stage2.log" --pin 1410 --thresh 0.5 \
    --json "$MEAS/clocks_stage2.json" 2>&1 | tee "$MEAS/clocks_stage2.txt" | tail -30

echo "############ F. flag audit ############"
bash scripts/audit_tc_flags.sh --bin-dir "$HOME/front7/bin" --logs "$MEAS" \
    --out "$MEAS/flag_audit.json" 2>&1 | tail -30

echo "############ G. summary + ratios ############"
python3 benchmarks/llm_smoke/nvidia_race/front7_summarize.py "$MEAS" \
    --clocks-json "$MEAS/clocks_stage2.json" 2>&1 | tee "$MEAS/summary7.txt" | tail -70

nvidia-smi --query-gpu=clocks.sm,temperature.gpu,memory.used --format=csv,noheader
echo FINAL_FRONT7_DONE
