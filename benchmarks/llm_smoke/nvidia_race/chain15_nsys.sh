#!/usr/bin/env bash
# chain15_nsys.sh — price the norm-accum lever with the FIXED --from-first-attn extractor.
#
# WHY THIS HAS NEVER BEEN RUN. Round 6 bounded its captured region by IDLE GAP (>3 ms) and took the
# last such region, which swallowed ~304 ms of weight staging; the priming-trace subtraction then
# made the `norms` and `mojo_per_layer` rows come out NEGATIVE and therefore invalid. That is why
# round 6 could only report norm-accum and rope as GEOMETRY-ATTRIBUTED (~16.2 ms for norms) and why
# its ranked-lever list had to hedge both buckets with a "~". `--from-first-attn` bounds the region
# at the FIRST fused-attention launch instead, so model load and weight staging fall outside it, the
# subtraction stops producing negative rows, and norm-accum becomes EXACTLY measured.
#
# THE QUESTION, pre-registered before the trace was taken so the answer cannot be shopped:
#   measured `norms` bucket vs the 6.83 ms DRAM roof.
#     * near the roof  -> the pass is bandwidth-bound, there is NOTHING TO WIN, close the lever;
#     * near ~16 ms    -> it is instruction/loop bound and vectorising the loops is the fix, price it.
#   The roof is a bandwidth argument: the `y` double-read is real (16n vs 12n bytes/row at n=5376) but
#   the ~22 MB working set fits the H200's 60 MB L2, so pass 2 is likely an L2 hit and the headroom
#   is L2 traffic / instruction count, NOT DRAM. A number near the roof would confirm that reasoning
#   empirically rather than by argument.
#
# Cell: rag4096, because the 6.83 ms roof and round 6's ~16.2 ms are both rag4096-basis. Comparing a
# pp1024 measurement against a rag4096 roof would be a basis mismatch.
#
# Usage (VM): nohup setsid bash chain15_nsys.sh > ~/lever7/chain15.nohup 2>&1 &
set -uo pipefail
L7=${L7:-$HOME/lever7}
GPU=${GPU:-1}
CAP_MIN=${CAP_MIN:-26}
W=$L7/window15.log
NR=$HOME/g3r7/benchmarks/llm_smoke/nvidia_race
CKPT=/mnt/ramblob/g3conv27b
ARM=${ARM:-R9_both}
OUT=$L7/nsys15
mkdir -p "$OUT"
T0=$(date +%s)
touch "$W"
exec > >(tee -a "$W") 2>&1
ts() { date -u +%FT%TZ; }
elapsed() { echo $(( ($(date +%s) - T0) / 60 )); }
remaining() { echo $(( CAP_MIN - ($(date +%s) - T0) / 60 )); }
PHASE=starting
( while true; do
    echo "$(date -u +%FT%TZ) window15 ALIVE elapsed_min=$(( ($(date +%s) - T0) / 60 )) phase=$PHASE \
clk=$(nvidia-smi --query-gpu=clocks.current.sm --format=csv,noheader,nounits -i 1 2>/dev/null) \
mem=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 1 2>/dev/null)MiB" >> "$W"
    sleep 60
  done ) &
LIVE_PID=$!
trap 'kill $LIVE_PID 2>/dev/null' EXIT
phase() { PHASE="$1"; echo; echo "########## [$(ts)] elapsed=$(elapsed)min remaining=$(remaining)min PHASE -> $1 ##########"; }

echo "WINDOW15_START $(ts) cap=${CAP_MIN}min gpu=$GPU arm=$ARM cell=rag4096"

phase "1_wait_stage"
for i in $(seq 1 60); do
  grep -q 'STAGE_OK' "$L7/stage15.log" 2>/dev/null && break
  sleep 10
done
grep -q 'STAGE_OK' "$L7/stage15.log" 2>/dev/null || { echo "NO STAGE_OK after 10min — aborting"; exit 1; }
echo "STAGE_OK confirmed; fixtures:"; grep -E 'IDENTICAL|FIXTURE_IDENTITY_OK=' "$L7/stage15.log" | tail -5
[[ -d "$CKPT" ]] || { echo "NO CHECKPOINT at $CKPT"; exit 1; }
[[ -x "$L7/$ARM" ]] || { echo "NO ARM BINARY $L7/$ARM"; exit 1; }
echo "ARM $ARM sha256_16=$(sha256sum "$L7/$ARM" | cut -c1-16) bytes=$(stat -c %s "$L7/$ARM")"

phase "2_clock_pin"
PIN=$(nvidia-smi -i $GPU --query-gpu=clocks.current.sm --format=csv,noheader,nounits)
if [[ "$PIN" != "1410" ]]; then
  sudo -n nvidia-smi -pm 1 >/dev/null 2>&1; sudo -n nvidia-smi -lgc 1410,1410 >/dev/null 2>&1
  sleep 3; PIN=$(nvidia-smi -i $GPU --query-gpu=clocks.current.sm --format=csv,noheader,nounits)
fi
echo "clocks=$PIN (want 1410)"
[[ "$PIN" == "1410" ]] || { echo "OFF_PIN $PIN — refusing to profile"; exit 1; }

# ── 3 the profiled run. Same invocation the timing cells use, so the trace describes the shipped
#       path. --trace=cuda only (no osrt, no sampling) to keep the trace and its export small; the
#       extractor only needs the kernel launch timeline.
phase "3_nsys_profile"
if (( $(remaining) < 16 )); then echo "SKIP profile: only $(remaining)min remain"; exit 1; fi
cd "$NR" || { echo NO_TREE; exit 1; }
( CUDA_VISIBLE_DEVICES=$GPU nsys profile --trace=cuda --sample=none \
    --cuda-memory-usage=false -o "$OUT/g3rag" --force-overwrite=true \
    "$L7/$ARM" "$CKPT" --tokens-file /tmp/g3rag/rag4096.txt --max-new 1 --f16 --prefill \
    > "$OUT/driver_under_nsys.log" 2>&1 )
echo "nsys_profile rc=$?"
echo "--- driver tail (proves the run completed rather than dying under the profiler) ---"
tail -6 "$OUT/driver_under_nsys.log"
ls -la "$OUT"/g3rag.nsys-rep 2>/dev/null || { echo "NO TRACE FILE — cannot continue"; exit 1; }

phase "4_export_sqlite"
if (( $(remaining) < 10 )); then echo "SKIP export: only $(remaining)min remain"; exit 1; fi
nsys export --type sqlite -o "$OUT/g3rag.sqlite" "$OUT/g3rag.nsys-rep" 2>&1 | tail -3
echo "export rc=$? size=$(stat -c %s "$OUT/g3rag.sqlite" 2>/dev/null)"
[[ -s "$OUT/g3rag.sqlite" ]] || { echo "EMPTY SQLITE — cannot extract"; exit 1; }

phase "5_extract"
# BOTH region definitions, so the difference the fix makes is visible rather than asserted: the
# round-6 idle-gap basis (which produced negative rows) and the fixed first-attn basis.
echo "=== (a) FIXED: --from-first-attn (the basis this window exists to obtain) ==="
/usr/bin/python3 mr_extract_gemma3_round7.py "$OUT/g3rag.sqlite" --cell rag4096 \
    --from-first-attn --json "$OUT/extract_fromattn.json" 2>&1 | tail -45
echo "=== (b) CONTROL: round 6's idle-gap basis, to show what the fix changed ==="
/usr/bin/python3 mr_extract_gemma3_round7.py "$OUT/g3rag.sqlite" --cell rag4096 \
    --json "$OUT/extract_idlegap.json" 2>&1 | tail -30

phase "done"
echo "CHAIN15_DONE $(ts) elapsed=$(elapsed)min of cap=${CAP_MIN}min"
echo "extracts: $OUT/extract_fromattn.json  $OUT/extract_idlegap.json"
nvidia-smi --query-gpu=index,clocks.current.sm,memory.used --format=csv,noheader
