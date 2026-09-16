#!/usr/bin/env bash
# run_rerace_7b_front6.sh — the FRONT-6 re-race against a FRESHLY RE-SERVED TensorRT-LLM 1.2.1.
#
# BYTE-FOR-BYTE round 4's protocol and rounds 2-3's before it (`run_rerace_7b_front4.sh`), only
# the artifact paths move to ~/trtllm/front6. Keeping the recipe identical is what makes the
# final ratios comparable rather than merely present, and it is what lets the re-serve be
# checked against round 4's RE-SERVED TRT-LLM cells (pp256 34.944 ms, pp1024 71.400 ms,
# RAG-4096 270.276 ms) for the 1% same-session reproduction the owner's protocol demands — a
# re-serve that misses by more than 1% must be labelled CROSS-SESSION, not averaged away. Round
# 4's own note applies unchanged: TRT-LLM's ~30 ms engine-side context-phase floor makes pp256
# unstable between sessions, so pp256 is the cell most likely to carry the CROSS-SESSION label.
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
#     The container is torn down to 0 MiB at the end — nothing is left resident between stages.
#
# ROUND 6 note (2026-09-16). This is round 5's script with ONLY the artifact paths moved
# (~/trtllm/front5 -> ~/trtllm/front6) and the completion marker renamed. The recipe is
# deliberately byte-identical because comparability is the whole point: the re-serve must land
# within 1% of round 5's RE-SERVED TRT-LLM cells (pp256 35.491 ms, pp1024 71.934 ms, RAG-4096
# 272.166 ms) or the cell is labelled CROSS-SESSION rather than averaged away. Round 6's flip
# criterion is our wall against THEIR 272.166 ms RAG-4096 server median, so a re-serve that
# quietly moved would move the criterion with it.
#
# usage: bash run_rerace_7b_front6.sh [--runs 7] [--warmup 3]
set -uo pipefail
MEAS=${MEAS:-$HOME/trtllm/front6}
OUT=${OUT:-$MEAS/trtllm_rerace6.json}
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
echo "RERACE6_DONE rc=$race_rc out=$OUT"
