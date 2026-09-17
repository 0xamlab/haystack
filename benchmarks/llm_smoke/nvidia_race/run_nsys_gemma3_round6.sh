#!/usr/bin/env bash
# run_nsys_gemma3_round6.sh — per-kernel nsys decomposition of the round-6 arms, so every
# millisecond the A/B claims is attributed to a named kernel rather than inferred.
#
# WHY: the round-4 accounting charged `_f32_to_f16_kernel` 8.682 ms at pp1024 to "KV-cache
# staging". That kernel is SHARED: it is also the shim's per-call f32->f16 A conversion for all
# four projection GEMMs. At gemma-3-27b's shapes one pp1024 prefill launches it 373 times =
# 4 projection seams x 62 layers (248) + K and V x 62 layers (124) + the lm_head A (1), and by
# BYTES the KV share is 25.2 MB of 248.5 MB per layer = 10.1%, i.e. ~0.88 ms of the 8.682 --
# down_proj's 22.0M-element A alone is 53%. The instance COUNT in these traces settles it
# without any modelling: the fused attention removes only the 124 KV launches, the pre-staged-A
# chain removes the other 248, so
#   R6_base 373  ->  R6_fa 249  ->  R6_all 1
# is the falsifiable prediction, and the traces either show it or the attribution is wrong.
#
# Captures (one prefill each, --max-new 1 so the trace is the prefill and not the decode):
#   R6_base  pp1024 + rag4096     the bracketing baseline
#   R6_all   pp1024 + rag4096     the ship candidate
#   R6_fa    pp1024               the fused attention ALONE
#   R6_mlp   pp1024               the pre-staged-A f16 chain ALONE
# Clocks are read before and after every capture; a capture taken off-pin is labelled, not used.
#
# Usage (on trtllm-gemma-us-west1-c):  bash run_nsys_gemma3_round6.sh
set -uo pipefail
GPU=${GPU:-1}
L6=${L6:-$HOME/lever6}
NS=$L6/nsys
CKPT=${CKPT:-/mnt/ramblob/g3conv27b}
PY=/usr/bin/python3
export CUDA_VISIBLE_DEVICES=$GPU
export MODULAR_HOME=${MODULAR_HOME:-$HOME/algenta/mojo_env/.pixi/envs/default/share/max}
mkdir -p "$NS" "$L6/logs"
CW_LOGFILE=$L6/lever6.log
export CW_LOGFILE
# shellcheck disable=SC1091
source "$HOME/lever3/cell_watchdog.sh"
cw_init "$L6/runs" "$L6/logs" "$L6/clocks" "$GPU"
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$CW_LOGFILE"; }

smi_raw() { nvidia-smi --query-gpu=clocks.current.sm --format=csv,noheader,nounits -i $GPU; }

# arm:prompt:tokens-file:max-new
# the priming-only fixture: seal() runs the four priming prefills REGARDLESS of the prompt, so
# a 32-row prompt (m < TC_MIN_M -> the timed prefill stays on the tiny SIMT path) isolates
# load + priming. measured_request = cluster(full trace) - cluster(priming trace), per bucket,
# same arm, same session, clocks pinned for both -- exact subtraction instead of a 4/5
# layer-tile-share model. Regenerated deterministically from the gated pp256 fixture's first
# 32 ids; the file is written to /tmp (wiped by a stop/start) and rebuilt here every run.
mkdir -p /tmp/g3short32
$PY -c "print(' '.join(open('/tmp/g3pp256/prompt_0000.txt').read().replace(',', ' ').split()[:32]))" \
  > /tmp/g3short32/prompt_0000.txt
[[ $(wc -w < /tmp/g3short32/prompt_0000.txt) -eq 32 ]] || { echo "SHORT32 FIXTURE BAD"; exit 1; }
CAPTURES=(
  "R6_base:pp1024:/tmp/g3pp1024/prompt_0000.txt:1"
  "R6_fa2:pp1024:/tmp/g3pp1024/prompt_0000.txt:1"
  "R6_kv16:pp1024:/tmp/g3pp1024/prompt_0000.txt:1"
  "R6_base:rag4096:/tmp/g3rag/rag4096.txt:1"
  "R6_fa2:rag4096:/tmp/g3rag/rag4096.txt:1"
  "R6_kv16:rag4096:/tmp/g3rag/rag4096.txt:1"
  "R6_base:priming:/tmp/g3short32/prompt_0000.txt:1"
  "R6_fa2:priming:/tmp/g3short32/prompt_0000.txt:1"
  "R6_kv16:priming:/tmp/g3short32/prompt_0000.txt:1"
)
# optional BN-sweep captures when WANT_BN_ARMS=1 built them
if (( ${WANT_BN_ARMS:-0} == 1 )); then
  CAPTURES+=("R6_kv16_bn32:rag4096:/tmp/g3rag/rag4096.txt:1"
             "R6_kv16_bn32:priming:/tmp/g3short32/prompt_0000.txt:1")
fi

log "=== run_nsys_gemma3_round6.sh (${#CAPTURES[@]} captures) ==="
for spec in "${CAPTURES[@]}"; do
  arm=$(echo "$spec" | cut -d: -f1); cell=$(echo "$spec" | cut -d: -f2)
  tf=$(echo "$spec" | cut -d: -f3); mn=$(echo "$spec" | cut -d: -f4)
  tag="${arm}_${cell}"
  before=$(smi_raw)
  if [[ "$before" != "1410" ]]; then
    sudo -n nvidia-smi -pm 1 >/dev/null 2>&1; sudo -n nvidia-smi -lgc 1410 >/dev/null 2>&1
    sleep 2; before=$(smi_raw)
  fi
  log "NSYS $tag START clocks=${before}MHz"
  nsys profile -o "$NS/$tag" --force-overwrite true \
    --trace=cuda --sample=none --cpuctxsw=none --cudabacktrace=none \
    "$L6/$arm" "$CKPT" --tokens-file "$tf" --max-new "$mn" --f16 --prefill \
    > "$NS/nsysrun_$tag.out" 2>&1
  rc=$?
  after=$(smi_raw)
  log "NSYS $tag END rc=$rc clocks_after=${after}MHz rep=$(du -h "$NS/$tag.nsys-rep" 2>/dev/null | cut -f1)"
  if (( rc == 0 )) && [[ -f "$NS/$tag.nsys-rep" ]]; then
    nsys stats --report cuda_gpu_kern_sum --format csv --output "$NS/${tag}_stats" \
      "$NS/$tag.nsys-rep" > "$L6/logs/nsysstats_$tag.log" 2>&1
    nsys export --type sqlite --force-overwrite true -o "$NS/$tag.sqlite" \
      "$NS/$tag.nsys-rep" >> "$L6/logs/nsysstats_$tag.log" 2>&1
    log "  kern_sum -> $NS/${tag}_stats_cuda_gpu_kern_sum.csv  sqlite -> $NS/$tag.sqlite"
  fi
done

log "=== decomposition ==="
$PY "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/decomp_gemma3_round6.py" \
  "$NS" "$L6/decomp_round6.json" 2>&1 | tee -a "$CW_LOGFILE"
log "=== run_nsys_gemma3_round6.sh COMPLETE ==="
nvidia-smi --query-gpu=index,clocks.current.sm,memory.used --format=csv,noheader | tee -a "$CW_LOGFILE"
