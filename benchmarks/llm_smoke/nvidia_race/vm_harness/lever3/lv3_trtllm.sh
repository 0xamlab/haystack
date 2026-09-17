#!/bin/bash
# lv3_trtllm.sh -- same-session TRT-LLM re-serve immediately after the lever-3 algenta cells,
# so the pp256 verdict stops resting on a CROSS-SESSION stored number (round 1's re-serve
# drifted +1.312% > 1% and was therefore labelled cross-session).
#
# Config is byte-identical to the stored H200 battery and to the round-1 re-serve: pytorch
# backend, attn_backend FLASHINFER, bf16, enable_block_reuse=false, max_input_len 8192,
# max_seq_len 8192, max_batch_size 64, cuda graphs DEFAULT, tp_size 1, GPU1, 1410 MHz pinned,
# same prompts, same client (tl_prefill_client.py), same 3 warmup + 7 measured.
# Waits for lever 3 to exit with a DEBOUNCED quiescence check (a 1-poll check previously let
# rr_gaps2.sh grab port 8000 during a lull between another leg's cells).
set -uo pipefail
GPU=${GPU:-1}
TR=/home/angel/trtllm
L3=/home/angel/lever3
RUNS=$L3/runs; LOGS=$L3/logs; CLK=$L3/clocks
PY=/usr/bin/python3
PF=$TR/tl_prefill_client.py
MODEL=/home/angel/models/gemma-3-27b-it
SERVE=$TR/venv/bin/trtllm-serve
PORT=${PORT:-8000}
BASE=http://127.0.0.1:$PORT
export CUDA_VISIBLE_DEVICES=$GPU

ts() { date -u +%FT%TZ; }
log() { echo "[$(ts)] $*" | tee -a "$L3/trtllm_same_session.log"; }
ck() { nvidia-smi --query-gpu=clocks.current.sm,temperature.gpu,power.draw,memory.used,utilization.gpu --format=csv,noheader -i $GPU; }
smi_raw() { nvidia-smi --query-gpu=clocks.current.sm --format=csv,noheader,nounits -i $GPU; }
ensure_clocks() {
  local c; c=$(smi_raw)
  if [[ "$c" != "1410" ]]; then
    log "CLOCK_DRIFT ($c MHz) -> re-pinning"
    sudo -n nvidia-smi -pm 1 >/dev/null 2>&1; sudo -n nvidia-smi -lgc 1410 >/dev/null 2>&1
    sleep 2; c=$(smi_raw)
  fi
  echo "$c"
}
sample_start() {
  ( while true; do
      printf '%s %s\n' "$(date -u +%FT%TZ)" \
        "$(nvidia-smi --query-gpu=clocks.current.sm,utilization.gpu,utilization.memory,memory.used,power.draw,temperature.gpu --format=csv,noheader -i $GPU)"
      sleep 1
    done > "$1" 2>/dev/null ) &
  SAMPLER_PID=$!
}
cell() {
  local label=$1; shift
  local before after rc nonpin
  before=$(ensure_clocks)
  log "CELL $label START clocks_before=${before}MHz smi=[$(ck)]"
  sample_start "$CLK/clocks_${label}.csv"
  "$@" > "$RUNS/$label.out" 2> "$LOGS/$label.err"; rc=$?
  kill "$SAMPLER_PID" 2>/dev/null; wait "$SAMPLER_PID" 2>/dev/null
  after=$(ensure_clocks)
  nonpin=$(awk '{print $2}' "$CLK/clocks_${label}.csv" 2>/dev/null | grep -vc '^1410$' || true)
  log "CELL $label END rc=$rc clocks_after=${after}MHz offpin=$nonpin smi=[$(ck)]"
}
quiesce() {
  log "=== waiting for lever 3 to exit (debounced, port $PORT must be free) ==="
  local pat="lv3[.]sh|lv2[.]sh|rr_[c]hain.sh|rr_[t]rtllm.sh|rr_[g]aps|rr_[n]sys_trtllm_fix|trtllm[-]serve|L3_[w]arminit|L2_[p]f_flash|v1_[c]tx8192_stream|nsys [p]rofile"
  local clean=0 i mem busy
  for i in $(seq 1 240); do
    if pgrep -f "$pat" >/dev/null 2>&1; then clean=0; else
      mem=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $GPU)
      busy=$( (ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null) | grep -c ":$PORT " || true)
      if [[ "${mem:-9999}" -lt 500 && "${busy:-1}" == "0" ]]; then
        clean=$((clean+1)); (( clean >= 3 )) && { log "QUIESCENT mem=${mem}MiB port free clocks=$(smi_raw)MHz"; return 0; }
      else clean=0; fi
    fi
    sleep 15
  done
  log "quiescence not reached"; return 1
}
model_id() { curl -s -m 10 $BASE/v1/models | $PY -c "import json,sys;print(json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null; }

log "=== lv3_trtllm.sh launched (pid $$) ==="
quiesce || exit 1
before=$(ensure_clocks)
log "launching trtllm-serve (pre-launch clocks=${before}MHz smi=[$(ck)])"
# shellcheck disable=SC1091
. $TR/venv/bin/activate
LD=$(find $TR/venv/lib/python3.10/site-packages/nvidia -maxdepth 3 -type d -name lib 2>/dev/null | tr '\n' ':')
export LD_LIBRARY_PATH="$LD${LD_LIBRARY_PATH:-}"
python -c "import tensorrt_llm,torch,tensorrt;print('versions',tensorrt_llm.__version__,torch.__version__,tensorrt.__version__)" 2>&1 | tee -a "$L3/trtllm_same_session.log"
setsid "$SERVE" serve "$MODEL" --backend pytorch --host 127.0.0.1 --port $PORT \
  --max_batch_size 64 --max_seq_len 8192 --tp_size 1 \
  --extra_llm_api_options $TR/serve_config.yaml > "$LOGS/serve_lv3.log" 2>&1 &
SERVE_PID=$!; echo "$SERVE_PID" > "$L3/serve_lv3.pid"
log "serve pid=$SERVE_PID"
t0=$SECONDS; MID=""
while (( SECONDS - t0 < 900 )); do
  if [[ "$(curl -s -o /dev/null -w '%{http_code}' -m 5 $BASE/health || true)" == "200" ]]; then
    MID=$(model_id); [[ -n "$MID" ]] && break
  fi
  sleep 8
done
if [[ -z "$MID" ]]; then
  log "server not ready in $(( SECONDS - t0 ))s - aborting"; pkill -f "trtllm[-]serve" 2>/dev/null; exit 1
fi
log "READY after $(( SECONDS - t0 ))s model_id=$MID"

cell trtllm_pp256 $PY "$PF" --base-url $BASE --model "$MID" --label trtllm_pp256 \
  --prompt-text /tmp/g3pp256/prompt_0000.text --prompt-ids /tmp/g3pp256/prompt_0000.txt \
  --warmup 3 --measured 7 --max-tokens 1 --ignore-eos --out "$RUNS/trtllm_pp256.json"
cell trtllm_pp1024 $PY "$PF" --base-url $BASE --model "$MID" --label trtllm_pp1024 \
  --prompt-text /tmp/g3pp1024/prompt_0000.text --prompt-ids /tmp/g3pp1024/prompt_0000.txt \
  --warmup 3 --measured 7 --max-tokens 1 --ignore-eos --out "$RUNS/trtllm_pp1024.json"
cell trtllm_rag4096 $PY "$PF" --base-url $BASE --model "$MID" --label trtllm_rag4096 \
  --prompt-text /tmp/g3rag/rag4096.text --prompt-ids /tmp/g3rag/rag4096.txt \
  --warmup 3 --measured 7 --max-tokens 256 --ignore-eos --out "$RUNS/trtllm_rag4096.json"

pid=$(cat "$L3/serve_lv3.pid" 2>/dev/null || true)
if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
  kill "$pid" 2>/dev/null
  for i in $(seq 1 40); do kill -0 "$pid" 2>/dev/null || break; sleep 2; done
  kill -0 "$pid" 2>/dev/null && { kill -9 "$pid"; sleep 5; }
fi
pkill -f "trtllm[-]serve" 2>/dev/null; sleep 6
log "server stopped; post-stop GPU: $(ck)"
log "=== lv3_trtllm.sh COMPLETE ==="
