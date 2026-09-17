#!/usr/bin/env bash
# run_nsys_7b_front7.sh <suffix> [prompt-key] [runs] — kernel-level capture + decomposition of
# ONE arm at ONE prompt shape, for FRONT 7.
#
# Round 6's recipe (front4's capture script + front6_decomp.py as the single analyzer version for
# both arms), with three things carried forward as fixes rather than rediscovered:
#   * `--runs 3`, NOT `--runs 1`. Round 6's trap: in a --runs 1 capture the FIRST prefill carries
#     a 383.804 ms host gap (58% of its 661.117 ms wall) from per-shape cuBLAS first-call cost,
#     and an aggregate reading of that capture mistakes a warmup artifact for the steady state.
#     front6_decomp.py prints EVERY window; the reported one is the median warm window.
#   * windows are cut on evidence, and the chunk count comes from the TRACE, never from an
#     assumed pass cap: round 6's first windower clustered on 2 ms idle gaps and produced an
#     8663 ms window spanning the decode tail, which would have "confirmed" a 6-10 ms host gap
#     that does not exist and sent the next round after CUDA graphs.
#   * ANALYZE_ONLY=1 re-runs the analyzer over an existing capture, because re-profiling to
#     re-test a CSV parser is a fresh measurement nobody asked for.
#
# usage:
#   bash run_nsys_7b_front7.sh _h0 rag0 3
#   bash run_nsys_7b_front7.sh _h1 fixture 3
#   ANALYZE_ONLY=1 bash run_nsys_7b_front7.sh _h0 rag0
set -uo pipefail
SUF="${1:?usage: run_nsys_7b_front7.sh <suffix> [prompt-key] [runs]}"
PKEY="${2:-rag0}"
RUNS="${3:-3}"
BIN=${BIN:-$HOME/front7/bin/qwen25_7b_p3_graph_cuda${SUF}}
CKPT=${CKPT:-/tmp/w7b/ckpt}
OUTD=${OUTD:-$HOME/trtllm/front7/nsys}
REPO=${REPO:-$HOME/front7/repo}
DECOMP=${DECOMP:-$REPO/benchmarks/llm_smoke/nvidia_race/front6_decomp.py}
mkdir -p "$OUTD"

# the prompt and its matching oracle: the fixture (256) or one of the three token-exact RAG-4096
# prompts. The oracle must match the prompt — round 6's second oracle defect was feeding a RAG
# decode the fixture oracle, which fails 16/16 by construction and, worse, exits the driver
# before the timing cell runs.
if [[ "$PKEY" == "fixture" ]]; then
    IDS=""
    REF=/tmp/w7b/gate/ref_tokens.json
    CASE=fixture
else
    N=${PKEY#rag}
    IDS=$(python3 - "$N" <<'PY'
import json, sys
p = json.load(open("/home/angel/trtllm/prompts.json"))
print(",".join(str(int(t)) for t in p["rag"][int(sys.argv[1])]["ids"]))
PY
    )
    REF=/tmp/w7b/gate/ref_tokens_rag.json
    CASE="rag_${N}"
fi
ORACLE=$(python3 - "$REF" "$CASE" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
c = d[sys.argv[2]] if sys.argv[2] in d else d.get("fixture", {})
ids = c.get("generated_ids", [])
print(",".join(str(int(t)) for t in ids[:16]))
PY
)
echo "capture: arm=$SUF prompt=$PKEY runs=$RUNS oracle_len=$(awk -F, '{print NF}' <<< "$ORACLE")"

for _ in $(seq 1 300); do
    [ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)" ] && break
    sleep 2
done
echo "clocks_before=$(nvidia-smi --query-gpu=clocks.sm,power.draw --format=csv,noheader) $(date -u +%T)"

TAG="${SUF}_${PKEY}"
GT="$OUTD/gputrace_${TAG}"
if [[ "${ANALYZE_ONLY:-0}" == "1" && -f "${GT}_cuda_gpu_trace.csv" ]]; then
    echo "ANALYZE_ONLY: reusing ${GT}_cuda_gpu_trace.csv (no new capture)"
else
    EXTRA=()
    [[ -n "$IDS" ]] && EXTRA=(--prompt-ids "$IDS")
    nsys profile --trace=cuda --cuda-graph-trace=node --sample=none --cpuctxsw=none \
        -o "$OUTD/rep_${TAG}" -f true "$BIN" --checkpoint "$CKPT" --arm p3 \
        --oracle "$ORACLE" "${EXTRA[@]+"${EXTRA[@]}"}" \
        --runs "$RUNS" --warmup 2 --out "$OUTD/out_${TAG}.txt" \
        > "$OUTD/nsys_${TAG}.log" 2>&1
    echo "nsys rc=$?"
    echo "clocks_after=$(nvidia-smi --query-gpu=clocks.sm,power.draw --format=csv,noheader)"
    grep -E "^prefill|^gen |G0 RESULT|G1 RESULT|O16 VERIFY|TC FLAGS|TCFLAG|ARMED|DECLINED|TC LT" \
        "$OUTD/nsys_${TAG}.log" | head -30
    nsys stats --report cuda_gpu_trace --format csv --output "$GT" \
        "$OUTD/rep_${TAG}.nsys-rep" > "$OUTD/stats_${TAG}.log" 2>&1
    echo "gpu_trace stats rc=$?"
    nsys stats --report cuda_api_trace --format csv --output "$OUTD/apitrace_${TAG}" \
        "$OUTD/rep_${TAG}.nsys-rep" >> "$OUTD/stats_${TAG}.log" 2>&1
    echo "api_trace stats rc=$?"
    nsys stats --report cuda_gpu_kern_sum --format csv --output "$OUTD/kernsum_${TAG}" \
        "$OUTD/rep_${TAG}.nsys-rep" >> "$OUTD/stats_${TAG}.log" 2>&1
    echo "kern_sum stats rc=$?"
fi

echo "== decomposition ($DECOMP, ONE analyzer version for every arm this round) =="
python3 "$DECOMP" "${GT}_cuda_gpu_trace.csv" \
    "$(ls -1 "${OUTD}"/apitrace_${TAG}_cuda_api_trace.csv 2>/dev/null | head -1)" \
    2>&1 | tee "$OUTD/decomp_${TAG}.txt" | tail -60
echo "== per-kernel family totals (kern_sum) =="
[[ -f "${OUTD}/kernsum_${TAG}_cuda_gpu_kern_sum.csv" ]] && \
    head -22 "${OUTD}/kernsum_${TAG}_cuda_gpu_kern_sum.csv"
echo "NSYS7_DONE_${TAG}"
