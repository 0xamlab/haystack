#!/usr/bin/env bash
# run_nsys_gemma3_round7.sh — per-kernel nsys decomposition of the round-7 arms, so every
# millisecond the A/B claims is attributed to a NAMED kernel rather than inferred, and so the
# bar-fallback deliverable (the per-layer proof of where the remaining rag4096 gap lives) is
# measured rather than modelled.
#
# WHY ROUND 7 NEEDS ITS OWN DECOMPOSITION AND NOT ROUND 6's. Round 6 could only report the
# norm-accum and rope buckets as GEOMETRY-ATTRIBUTED estimates (instance-share 248/310, by launch
# geometry), and had to hedge both with a "~" in its ranked-lever list, because of its own
# integrity note 4: the priming-subtraction's `mojo_per_layer` and `norms` rows came out
# NEGATIVE and were invalid as printed. The cause was the region boundary — both traces were
# bounded by "last cluster after a >3 ms idle gap", and load flows into priming with no such gap,
# so the two traces did not bound the same region and the load term did not cancel. Round 7's
# extractor (mr_extract_gemma3_round7.py --from-first-attn) bounds BOTH traces at the first
# fused-attention launch instead, which model load never issues, so the boundary is identical by
# construction and load cancels exactly. That is what turns rope / norm-accum / geglu from
# attributed into measured — and those are precisely the buckets round 7's compensation levers
# live in, so the round cannot price them without it.
#
# Captures (one prefill each, --max-new 1 so the trace IS the prefill and not the decode):
#   R7_base   rag4096 + pp1024 + priming   the bracketing baseline (= #1006's ship candidate)
#   R7_ropev  rag4096 + pp1024 + priming   the ROPEVEC arm
# The priming fixture is the 32-row prompt: seal() runs the four priming prefills REGARDLESS of
# the prompt, and at m=32 the timed prefill declines both the fused attention (m <
# _G3_PF_FA_MIN_M) and the TC GEMM seam (m < TC_MIN_M), so that capture is load + priming +
# epsilon, and the epsilon is bounded and conservative for the buckets the levers move.
# Clocks are read before AND after every capture; a capture taken off-pin is labelled, not used.
#
# Usage (on trtllm-gemma-us-west1-c):  bash run_nsys_gemma3_round7.sh
set -uo pipefail
GPU=${GPU:-1}
L7=${L7:-$HOME/lever7}
NS=$L7/nsys
CKPT=${CKPT:-/mnt/ramblob/g3conv27b}
PY=/usr/bin/python3
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# round 6's captured TRT-LLM full-lifetime trace, for the flashinfer / rope comparison the
# bar-fallback deliverable needs. Same box, same clocks; whether it is the SAME SESSION as this
# round's re-serve is recorded, not assumed.
TRT_SQLITE=${TRT_SQLITE:-$HOME/trtllm/gemma_rerace/nsys/trtllmfull_rag4096.sqlite}
export CUDA_VISIBLE_DEVICES=$GPU
export MODULAR_HOME=${MODULAR_HOME:-$HOME/algenta/mojo_env/.pixi/envs/default/share/max}
mkdir -p "$NS" "$L7/logs"
CW_LOGFILE=$L7/lever7.log
export CW_LOGFILE
# shellcheck disable=SC1091
source "$HOME/lever3/cell_watchdog.sh"
cw_init "$L7/runs" "$L7/logs" "$L7/clocks" "$GPU"
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$CW_LOGFILE"; }

smi_raw() { nvidia-smi --query-gpu=clocks.current.sm --format=csv,noheader,nounits -i $GPU; }

# the priming-only fixture, rebuilt every run because /tmp is wiped by a stop/start
mkdir -p /tmp/g3short32
$PY -c "print(' '.join(open('/tmp/g3pp256/prompt_0000.txt').read().replace(',', ' ').split()[:32]))" \
  > /tmp/g3short32/prompt_0000.txt
[[ $(wc -w < /tmp/g3short32/prompt_0000.txt) -eq 32 ]] || { echo "SHORT32 FIXTURE BAD"; exit 1; }

CAPTURES=(
  "R7_base:rag4096:/tmp/g3rag/rag4096.txt:1"
  "R7_ropev:rag4096:/tmp/g3rag/rag4096.txt:1"
  "R7_base:pp1024:/tmp/g3pp1024/prompt_0000.txt:1"
  "R7_ropev:pp1024:/tmp/g3pp1024/prompt_0000.txt:1"
  "R7_base:priming:/tmp/g3short32/prompt_0000.txt:1"
  "R7_ropev:priming:/tmp/g3short32/prompt_0000.txt:1"
)

log "=== run_nsys_gemma3_round7.sh (${#CAPTURES[@]} captures) ==="
for spec in "${CAPTURES[@]}"; do
  arm=$(echo "$spec" | cut -d: -f1); cell=$(echo "$spec" | cut -d: -f2)
  tf=$(echo "$spec" | cut -d: -f3); mn=$(echo "$spec" | cut -d: -f4)
  tag="${arm}_${cell}"
  before=$(smi_raw)
  if [[ "$before" != "1410" ]]; then
    sudo -n nvidia-smi -pm 1 >/dev/null 2>&1; sudo -n nvidia-smi -lgc 1410,1410 >/dev/null 2>&1
    sleep 2; before=$(smi_raw)
  fi
  log "NSYS $tag START clocks=${before}MHz"
  nsys profile -o "$NS/$tag" --force-overwrite true \
    --trace=cuda --sample=none --cpuctxsw=none --cudabacktrace=none \
    "$L7/$arm" "$CKPT" --tokens-file "$tf" --max-new "$mn" --f16 --prefill \
    > "$NS/nsysrun_$tag.out" 2>&1
  rc=$?
  after=$(smi_raw)
  # ZERO off-pin tolerance applies to decompositions too: an off-pin capture misattributes every
  # bucket, so it is labelled here and excluded from the JSON rather than silently pooled.
  pinok="ON_PIN"
  [[ "$before" != "1410" || "$after" != "1410" ]] && pinok="OFF_PIN_${before}_${after}"
  log "NSYS $tag END rc=$rc clocks=${before}->${after}MHz $pinok rep=$(du -h "$NS/$tag.nsys-rep" 2>/dev/null | cut -f1)"
  if (( rc == 0 )) && [[ -f "$NS/$tag.nsys-rep" ]]; then
    nsys export --type sqlite --force-overwrite true -o "$NS/$tag.sqlite" \
      "$NS/$tag.nsys-rep" >> "$L7/logs/nsysstats_$tag.log" 2>&1
    # --from-first-attn on BOTH the full and the priming trace: identical boundary by
    # construction, which is what makes the load term cancel exactly.
    $PY "$HERE/mr_extract_gemma3_round7.py" "$NS/$tag.sqlite" --cell "$cell" \
        --from-first-attn --json "$NS/mr_$tag.json" \
        > "$L7/logs/mrextract_$tag.log" 2>&1
    log "  mr_extract rc=$? -> $NS/mr_$tag.json ($pinok)"
    grep -E "EXCLUDED|boundary kernel|region =" "$L7/logs/mrextract_$tag.log" | head -3 | tee -a "$CW_LOGFILE"
  fi
done

log "=== exact measured-request buckets by priming subtraction (fixed boundary) ==="
for cell in rag4096 pp1024; do
  for arm in R7_base R7_ropev; do
    f="$NS/mr_${arm}_${cell}.json"; p="$NS/mr_${arm}_priming.json"
    if [[ -f "$f" && -f "$p" ]]; then
      echo "--- $arm $cell ---" | tee -a "$CW_LOGFILE"
      $PY "$HERE/mr_subtract_gemma3_round7.py" "$f" "$p" "$cell" 2>&1 \
        | tee "$L7/logs/mrsub_${arm}_${cell}.log" | tee -a "$CW_LOGFILE"
      # The negative-row check round 6 could not pass: if any bucket is still negative the
      # boundary is still wrong and the rows must not be quoted.
      if grep -q -- "-[0-9][0-9]*\.[0-9]" "$L7/logs/mrsub_${arm}_${cell}.log"; then
        log "  NEGATIVE_ROW_WARN $arm $cell -- boundary still mismatched; do NOT quote these rows"
      else
        log "  no negative buckets: $arm $cell subtraction is VALID"
      fi
    else
      log "  MISSING json for $arm $cell (full=$([[ -f $f ]] && echo y || echo n) prim=$([[ -f $p ]] && echo y || echo n))"
    fi
  done
done

log "=== TRT-LLM 1.2.1 side: flashinfer attention + rope kernel census ==="
if [[ -f "$TRT_SQLITE" ]]; then
  log "reading $TRT_SQLITE (mtime $(stat -c %y "$TRT_SQLITE" 2>/dev/null | cut -d. -f1))"
  $PY - "$TRT_SQLITE" <<'PY' 2>&1 | tee -a "$CW_LOGFILE"
import sqlite3, sys
con = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
rows = con.execute("""
    SELECT s.value, COUNT(*), SUM(k.end-k.start)/1e6
    FROM CUPTI_ACTIVITY_KIND_KERNEL k JOIN StringIds s ON k.demangledName = s.id
    GROUP BY s.value ORDER BY 3 DESC LIMIT 18
""").fetchall()
con.close()
print(f"{'TRT-LLM kernel (whole trace)':<74}{'n':>7}{'ms':>10}")
for name, n, ms in rows:
    print(f"{name[:74]:<74}{n:>7}{ms:>10.3f}")
PY
else
  log "TRT_SQLITE not found at $TRT_SQLITE -- the flashinfer/rope comparison will cite round 6's"
  log "  captured numbers (flashinfer 21.01 ms, rope+appendKV 3.47 ms) and say they are round 6's"
fi

log "=== run_nsys_gemma3_round7.sh COMPLETE ==="
nvidia-smi --query-gpu=index,clocks.current.sm,memory.used --format=csv,noheader | tee -a "$CW_LOGFILE"
