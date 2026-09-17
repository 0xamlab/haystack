#!/usr/bin/env bash
# run_stage34_front7.sh — FRONT 7 stages 3+4: the TensorRT-LLM side, then our kernel-level capture.
#
# Stage 3 is the CRITERION and the comparison, in that order:
#   3a. a FRESH same-session re-serve of TensorRT-LLM 1.2.1 on round 6's byte-identical recipe.
#       The flip criterion is our wall against THIS session's server median, and rounds 4/5/6
#       drifted monotonically (270.276 -> 272.166 -> 273.186 ms RAG-4096), so a remembered number
#       would move the criterion by ~1% — more than half the margin this round is trying to widen.
#       A re-serve more than 1% from round 6's is labelled CROSS-SESSION, not averaged away.
#   3b. THEIR kernel mix at the RAG-4096 shape, measured. Every round since the first has compared
#       our per-layer decomposition against their pp1024 mix scaled by the number of 1024-row
#       chunks; round 6 said so outright ("still inferred by scaling round 2's pp1024 kernel mix").
#       An extrapolation cannot see a shape-or-state effect, which is exactly the class of error
#       this campaign keeps paying for (the +9.8% isolated-vs-in-situ cublas gap, the 3.3x KVTWIN
#       over-forecast, the FA2 staging forecast).
# Stage 4 captures OUR side at the same shape with the SAME analyzer version for both arms, so the
# delta is a measurement rather than a cross-basis subtraction (round 6's rule).
#
# usage: bash run_stage34_front7.sh                 # 3a, 3b, then nsys on _h0 and $SHIP_ARM
#        SKIP_RERACE=1 bash run_stage34_front7.sh   # only the trace + our captures
set -uo pipefail
cd "$HOME/front7/repo" || exit 1
MEAS=${MEAS:-$HOME/trtllm/front7}
SHIP_ARM=${SHIP_ARM:-_h1}
# only the ship arm is captured: the baseline side comes from FRONT 6's stored `_g2` trace,
# re-decomposed with this round's analyzer below.
NSYS_ARMS=${NSYS_ARMS:-${SHIP_ARM}}

wait_gpu_free() {
    for _ in $(seq 1 300); do
        [ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)" ] && return 0
        sleep 2
    done
    echo "WARN: GPU still busy"
}

if [ "${SKIP_RERACE:-0}" != "1" ]; then
    echo "############ 3a. TensorRT-LLM 1.2.1 fresh same-session re-serve ############"
    wait_gpu_free
    bash benchmarks/llm_smoke/nvidia_race/run_rerace_7b_front7.sh --runs 7 --warmup 3 \
        2>&1 | tee "$MEAS/stage3a_rerace.log" | tail -40
fi

echo "############ 3b. THEIR RAG-4096 kernel mix (measured, not extrapolated) ############"
wait_gpu_free
bash benchmarks/llm_smoke/nvidia_race/run_trtllm_rag_trace7.sh "${TRACE_DELAY:-150}" \
    "${TRACE_DUR:-150}" "${TRACE_CELLS:-rag0}" 2>&1 | tee "$MEAS/stage3b_trtllm_trace.log" | tail -50

echo "############ 4. our kernel-level captures at the same shape ############"
IDS0=$(python3 -c "
import json;p=json.load(open('/home/angel/trtllm/prompts.json'))
print(','.join(str(int(t)) for t in p['rag'][0]['ids']))")
for A in $NSYS_ARMS; do
    wait_gpu_free
    echo "== nsys capture $A rag0 =="
    PROMPT_IDS="$IDS0" BIN="$HOME/front7/bin/qwen25_7b_p3_graph_cuda${A}" \
        OUTD="$MEAS/nsys" bash benchmarks/llm_smoke/nvidia_race/run_nsys_7b_front7.sh \
        "$A" rag0 3 2>&1 | tee "$MEAS/stage4_nsys_${A}.log" | tail -45
done

# The baseline side of the decomposition is NOT re-captured: `_h0`'s shim object is section-,
# symbol- and SASS-identical to FRONT 6's and its Mojo lever code is compiled out, so FRONT 6's
# stored `_g2` trace IS this round's baseline trace. What matters is that both sides go through ONE
# analyzer version, so the stored trace is re-decomposed here with this round's front6_decomp.py
# rather than quoted from round 6's output file.
R6GT="$HOME/trtllm/front6/nsys/gputrace__g2_rag0_cuda_gpu_trace.csv"
if [[ -f "$R6GT" ]]; then
    echo "== re-decomposing FRONT 6's stored _g2 trace with THIS round's analyzer =="
    python3 benchmarks/llm_smoke/nvidia_race/front6_decomp.py "$R6GT" \
        "$HOME/trtllm/front6/nsys/apitrace__g2_rag0_cuda_api_trace.csv" \
        2>&1 | tee "$MEAS/nsys/decomp_h0_from_front6_g2.txt" | tail -45
else
    echo "WARN: $R6GT missing -- capture _h0 explicitly before quoting a baseline decomposition"
fi

echo "############ summary with the TRT-LLM basis ############"
python3 benchmarks/llm_smoke/nvidia_race/front7_summarize.py "$MEAS" \
    --trtllm "$MEAS/trtllm_rerace7.json" --clocks-json "$MEAS/clocks_stage2.json" \
    2>&1 | tee "$MEAS/summary7.txt" | tail -80

nvidia-smi --query-gpu=clocks.sm,temperature.gpu,memory.used --format=csv,noheader
echo STAGE34_FRONT7_DONE
