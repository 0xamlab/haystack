#!/usr/bin/env bash
# run_rerace_7b_front3.sh — the FRONT-3 re-race against a FRESHLY RE-SERVED TensorRT-LLM 1.2.1.
#
# Same protocol as round 2's re-race (~/trtllm/front1/rerace.json), which is what makes the
# ratios comparable rather than merely present:
#   * TRT-LLM: nvcr.io/nvidia/tensorrt-llm/release:1.2.1, pytorch backend, attn_backend
#     TRTLLM (FLASHINFER is not needed at 7B), bf16, HF checkpoint direct, chunked_prefill
#     off, block/partial reuse AND copy_on_partial_reuse explicitly OFF (1.2.1 defaults block
#     reuse ON, which would race a cache algenta does not have), max_batch 64, max_input_len
#     4352 (1.2.1 defaults 1024 with NO CLI flag — it silently rejects RAG-4096), max_seq_len
#     8192, CudaGraph defaults. Config file: ~/trtllm/serve_config.yaml.
#   * basis: TRT-LLM's executor iter-log device step time (print_iter_log=true), median of
#     --runs measured with --warmup excluded, cells interleaved round-robin. algenta's side is
#     its driver's own median of 20 device-side runs from the A/B sweep.
#   * clocks read before and after; the GPU is drained of algenta processes before the
#     container starts and the container is removed after, so neither side shares the device.
#
# usage: bash run_rerace_7b_front3.sh [--runs 7] [--warmup 3]
set -uo pipefail
MEAS=${MEAS:-$HOME/trtllm/front3}
OUT=${OUT:-$MEAS/trtllm_rerace3.json}
mkdir -p "$MEAS"
D="sudo -n docker"
$D ps >/dev/null 2>&1 || D="docker"

echo "clocks_before=$(nvidia-smi --query-gpu=clocks.sm --format=csv,noheader) $(date -u +%T)"
# the GPU is solo: nothing of ours may be resident while TRT-LLM is timed
for _ in $(seq 1 300); do
    [ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)" ] && break
    sleep 2
done
nvidia-smi --query-compute-apps=pid --format=csv,noheader | head -3

echo "== re-serving TensorRT-LLM 1.2.1 =="
bash "$HOME/trtllm_serve_up.sh" 2>&1 | tail -6
serve_rc=$?
if ! curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health | grep -q 200; then
    echo "SERVE FAILED — not racing against a stale or half-up server"
    $D logs --tail 30 trtllm7b 2>&1 | tail -30
    exit 3
fi
echo "clocks_at_serve=$(nvidia-smi --query-gpu=clocks.sm --format=csv,noheader)"

echo "== racing =="
python3 "$HOME/trtllm_race.py" --out "$OUT" "$@" 2>&1 | tail -30
race_rc=$?

echo "clocks_after_race=$(nvidia-smi --query-gpu=clocks.sm --format=csv,noheader)"
$D rm -f trtllm7b >/dev/null 2>&1 || true
echo "container removed; clocks_now=$(nvidia-smi --query-gpu=clocks.sm --format=csv,noheader)"
echo "RERACE3_DONE rc=$race_rc out=$OUT"
