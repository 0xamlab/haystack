#!/usr/bin/env bash
# run_cells.sh — official max-benchmark sonnet cells.
#
# Cell shape (Modular official config, gemma-3-27b-sonnet-decode-heavy-prefix200.yaml,
# adapted to our models): dataset sonnet, num-prompts 500, sonnet-input-len 550,
# output-lengths 256, sonnet-prefix-len 200, endpoint /v1/chat/completions.
# Variant "sat" = --request-rate inf (saturated), variant "rate" = finite Poisson rate.
#
# Usage: run_cells.sh <cell-name> <port> <backend> <model-id> <variant> <rate> <n-runs>
#   e.g. run_cells.sh max_06b 8081 modular <max-model-id> sat inf 20
#
# Protocol note: --no-warmup-to-steady-state is passed because the default steady-state
# warmup (8x oversample at concurrency 128, aborted in flight) produces cancelled-request
# error chunks that count as failed benchmark requests against llama-server/algenta.
set -uo pipefail
CELL=$1; PORT=$2; BACKEND=$3; MODEL_ID=$4; VARIANT=$5; RATE=$6; NRUNS=$7
E=~/algenta/mojo_env/.pixi/envs/default/bin
OUT=~/maxbench/results/${CELL}_${VARIANT}
mkdir -p "$OUT"

RATE_ARGS=()
if [[ "$VARIANT" == "rate" ]]; then RATE_ARGS=(--request-rate "$RATE"); fi

for i in $(seq 1 "$NRUNS"); do
  F="$OUT/run_$(printf '%02d' "$i").json"
  if [[ -f "$F" ]]; then echo "[cell $CELL/$VARIANT] run $i exists, skip"; continue; fi
  echo "[cell $CELL/$VARIANT] run $i/$NRUNS start $(date -u +%H:%M:%S)"
  "$E/max" benchmark \
    --model "$MODEL_ID" \
    --tokenizer ~/qwen3-0.6b-base \
    --backend "$BACKEND" \
    --endpoint /v1/chat/completions \
    --dataset-name sonnet \
    --num-prompts 500 \
    --sonnet-input-len 550 \
    --output-lengths 256 \
    --sonnet-prefix-len 200 \
    --no-warmup-to-steady-state \
    --host 127.0.0.1 --port "$PORT" \
    "${RATE_ARGS[@]}" \
    --result-filename "$F" \
    > "$OUT/run_$(printf '%02d' "$i").log" 2>&1
  RC=$?
  echo "[cell $CELL/$VARIANT] run $i rc=$RC end $(date -u +%H:%M:%S)"
done
echo "[cell $CELL/$VARIANT] DONE"
