#!/usr/bin/env bash
# run_ab_7b_tc_attn.sh — pinned-clocks interleaved A/B on the 7B fixture cells:
# the autopsy ship arm (tc_b1_ns) vs the tensor-core prefill-attention port
# (tc_b1_ns_ta, -D ALGENTA_7B_PF_TCATTN). Interleaved A B A B as regime-drift
# armor (the autopsy round's protocol). Run on algenta-ent-a100.
set -uo pipefail
NV=$HOME/algenta_nv
CKPT=/tmp/w7b/ckpt
MEAS=/tmp/w7b/race/results_ta
ORACLE=$(python3 - <<'PY'
import json
ref = json.load(open("/tmp/w7b/gate/ref_tokens.json"))
print(",".join(str(int(t)) for t in ref["fixture"]["generated_ids"][:16]))
PY
)
wait_gpu_idle() {
  for i in $(seq 1 180); do
    t=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)
    [ -z "$t" ] && return 0
    sleep 2
  done
  return 1
}
run_cell() { # binary tag runs
  local bin="$1" tag="$2" runs="$3"
  wait_gpu_idle || return 1
  $bin --checkpoint $CKPT --arm p3 --oracle "$ORACLE" --runs $runs \
      --out $MEAS/${tag}.txt > $MEAS/${tag}.log 2>&1
  grep -E "prefill|gen " $MEAS/${tag}.log | head -4
}
mkdir -p $MEAS
echo "CLOCKS: $(nvidia-smi --query-gpu=clocks.sm --format=csv,noheader)"
run_cell $NV/qwen25_7b_p3_graph_cuda_tc_b1_ns    ab_base_a 20
run_cell $NV/qwen25_7b_p3_graph_cuda_tc_b1_ns_ta ab_ta_a   20
run_cell $NV/qwen25_7b_p3_graph_cuda_tc_b1_ns    ab_base_b 20
run_cell $NV/qwen25_7b_p3_graph_cuda_tc_b1_ns_ta ab_ta_b   20
echo AB_DONE
