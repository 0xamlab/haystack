#!/usr/bin/env bash
# run_stage5_front7.sh — the two checks that validate mechanisms this round documents but does not
# otherwise exercise. Both are cheap; neither is optional, because an untested mechanism in a
# published protocol is how a later round silently measures the wrong thing.
#
#   A. ALGENTA_LT_PICK — the override that lets a RACED arm run a searched algorithm set the token
#      gates cover (the in-situ search itself runs after G0/G1, so its own choice is not
#      gate-covered). This round the in-situ winners EQUALLED the isolated winners in all four
#      shapes, so pinning them must reproduce `_h1` within noise: that is the control. If the pick
#      did not parse, or pinned the wrong shape, the cell would move or the shim would print a
#      WARNING — both are visible here rather than in a published ratio.
#   B. the throttle-reason probe for the uniform +8.5% isolated->in-situ cublas penalty (§4b of the
#      ledger): clocks.sm cannot separate a power-cap stall from a warm-harness artifact, the
#      reason bits can.
set -uo pipefail
cd "$HOME/front7/repo" || exit 1
MEAS=${MEAS:-$HOME/trtllm/front7}

IDS0=$(python3 -c "
import json;p=json.load(open('/home/angel/trtllm/prompts.json'))
print(','.join(str(int(t)) for t in p['rag'][0]['ids']))")
ORACLE=$(python3 -c "
import json;d=json.load(open('/tmp/w7b/gate/ref_tokens_rag.json'))
print(','.join(str(int(t)) for t in d['rag_0']['generated_ids'][:16]))")

wait_free() {
    for _ in $(seq 1 200); do
        [ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)" ] && return 0
        sleep 2
    done
}

echo "############ A. ALGENTA_LT_PICK control (must reproduce _h1 within noise) ############"
# The indices _hd's in-situ table selected, by shape: gate_up (N=37888,K=3584) cand[5],
# qkv (N=4608,K=3584) cand[6], o_proj (N=3584,K=3584) cand[3], down (N=3584,K=18944) cand[2].
#
# THIS RUNS `_hd`, NOT `_h1`, and that is not a convenience: the override is parsed inside
# `#ifdef ALGENTA_TC_SHIM_LTINSITU`, because putting it in the plain LT block would change the
# object `_h0` links and cost this round the byte-identity of its own baseline. So an arm that
# races a SEARCHED algorithm set must link the LTINSITU object — which is exactly what `_hd` is,
# and with no `--lt-insitu` argument the search is never armed (`g_exploring` stays 0) so every
# dispatch runs the pinned algorithm from tune time. Expected result: `_hd` + pick reproduces
# `_h1` within noise, because the in-situ winners equalled the isolated winners in all four
# shapes. A pick that failed to parse, or named a shape with fewer candidates, prints a WARNING
# here rather than silently measuring the timed winner.
export ALGENTA_LT_PICK="37888x3584:5;4608x3584:6;3584x3584:3;3584x18944:2"
echo "  ALGENTA_LT_PICK=$ALGENTA_LT_PICK  (arm _hd: the override lives in the LTINSITU object)"
wait_free
"$HOME/front7/bin/qwen25_7b_p3_graph_cuda_hd" --checkpoint /tmp/w7b/ckpt --arm p3 \
    --prompt-ids "$IDS0" --oracle "$ORACLE" --warmup 1 --runs 7 \
    --out "$MEAS/pick_control.txt" > "$MEAS/stage5_pick.log" 2>&1
echo "  rc=$?"
grep -E "TC LT: ALGENTA_LT_PICK|TC LT: WARNING|TC LT: tuned|G0 RESULT|G1 RESULT|^prefill4096" \
    "$MEAS/stage5_pick.log" | head -14
unset ALGENTA_LT_PICK

echo "############ B. the throttle-reason probe ############"
wait_free
bash benchmarks/llm_smoke/nvidia_race/run_throttle_probe7.sh _h1 2>&1 \
    | tee "$MEAS/stage5_throttle.log" | tail -30

nvidia-smi --query-gpu=clocks.sm,temperature.gpu,memory.used --format=csv,noheader
echo STAGE5_FRONT7_DONE
