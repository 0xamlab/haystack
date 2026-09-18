#!/usr/bin/env bash
# chain10.sh — ONE combined VM window, run under a hard cap, with the observability discipline that
# round 9's misread made mandatory. Everything this window does appends to ONE log
# (~/lever7/window11.log) no matter how many sub-chains run, a liveness line lands every 120 s, and
# any deliberate mid-cell kill writes KILLED_BY_OPERATOR so a missing END is self-explaining rather
# than indistinguishable from a wedge.
#
# PHASES, in the order the cap should be spent (highest value first, because a truncation must cost
# the least-load-bearing phase):
#   1 re-stage      a stop wipes tmpfs AND the RAM-blob checkpoint, so fixtures and the converted
#                   checkpoint must be regenerated and the fixtures PROVEN token-identical to round
#                   6's certified gate echoes before anything is measured.
#   2 bracket close the rag4096 A/B is re-run with CELLTAG=b, so its cells are labelled r6b_* and
#                   POOL with the r6_* cells already banked (5 and 4 measured per arm) instead of
#                   overwriting them. That takes n to >=7 per arm and, critically, completes the
#                   A..B..A group so the drift armor is finally MEASURED — round 9's delta was
#                   NOT RESOLVED for want of exactly that.
#   3 trt re-serve  same-session comparator. Must reproduce 426.339 within 1% or the ratio is
#                   labelled CROSS-SESSION and is not publishable.
#   4 summarise     the pooled table, drift armor, resolved verdicts, clock audit, gates, flag audit.
#   5 ropevec gate  ONLY if >=30 min of cap remains: ROPEVEC is ungated code sitting in main, and an
#                   ungated arm is a liability. Skipped rather than started late.
#
# wgmma IS DELIBERATELY ABSENT. Round 8 produced the census primitives only; the windowed kernel,
# its on-device layout probe and its host-f64 gate are unwritten, and authoring them blind inside a
# capped window is negative expected value. Declared before the window rather than discovered in it.
#
# Usage (on the VM):  nohup setsid bash chain10.sh > ~/lever7/chain10.nohup 2>&1 &
set -uo pipefail
L7=${L7:-$HOME/lever7}
GPU=${GPU:-1}
CAP_MIN=${CAP_MIN:-58}           # hard cap in minutes from THIS SCRIPT's start. The VM boot and the
                                 # tree sync happen before it, so the owner's window cap is this
                                 # plus ~6 min. Sized for the 1 h scope: re-stage ~10, bracket ~20,
                                 # TRT re-serve ~20, summarise ~2.
# Bracket shape, deliberately SHORT (1 warmup + 2 measured + 2 closing per arm = 5 cells per arm,
# ~20 min for the pair). Cells POOL by label across brackets, so this ADDS to the r6_* cells already
# banked (5 and 4 measured per arm) instead of replacing them, taking pooled n to 7 per arm while
# still closing the A..B..A group that produces the drift armor. The protocol's full 3+7+2 is 24
# cells / ~48 min and cannot fit a 1 h cap alongside the re-stage and the TRT re-serve. The cells
# runner logs a NOTE whenever the shape is non-default, so a pooled n is never reported without it.
export WARM_RUNS=${WARM_RUNS:-1}
export MEAS_RUNS=${MEAS_RUNS:-2}
export CLOSE_RUNS=${CLOSE_RUNS:-2}
# ROPEVEC is OUT OF SCOPE for the 1 h window and rides a future substantive one. Gated by an env var
# rather than deleted, so the phase is still here and still states honestly why it did not run.
ROPEVEC_GATE=${ROPEVEC_GATE:-0}
W=$L7/window11.log
mkdir -p "$L7/logs" "$L7/runs" "$L7/clocks"
T0=$(date +%s)
: > "$W"

# ── single-log discipline: every phase, every sub-chain, one file ──
exec > >(tee -a "$W") 2>&1
ts() { date -u +%FT%TZ; }
elapsed() { echo $(( ($(date +%s) - T0) / 60 )); }
remaining() { echo $(( CAP_MIN - ($(date +%s) - T0) / 60 )); }

PHASE=starting
( while true; do
    echo "$(date -u +%FT%TZ) window11 ALIVE elapsed_min=$(( ($(date +%s) - T0) / 60 )) phase=$PHASE \
clk=$(nvidia-smi --query-gpu=clocks.current.sm --format=csv,noheader,nounits -i 1 2>/dev/null) \
mem=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 1 2>/dev/null)MiB" >> "$W"
    sleep 120
  done ) &
LIVE_PID=$!
# The liveness emitter must die with this script, or it outlives the window and makes a dead chain
# look alive — the exact inverse of the failure round 9 had.
trap 'kill $LIVE_PID 2>/dev/null' EXIT

phase() { PHASE="$1"; echo; echo "########## [$(ts)] elapsed=$(elapsed)min remaining=$(remaining)min PHASE -> $1 ##########"; }
# A deliberate kill must be self-explaining in the single log.
opkill() { # $1 = what, $2 = why
  echo "[KILLED_BY_OPERATOR] [$(ts)] target=$1 reason=$2"
}

echo "WINDOW11_START $(ts) cap=${CAP_MIN}min gpu=$GPU"
cd "$HOME/g3r7/benchmarks/llm_smoke/nvidia_race" || { echo NO_TREE; exit 1; }

# ═══ 1 re-stage ═══
phase "1_restage"
# TR=$HOME because the staging scripts live at $HOME/*.sh, NOT $HOME/trtllm/ — the wrong assumption
# there once made a backup report the two most load-bearing files in the lane as MISSING.
TR="$HOME" FIXREF_RUNS="$HOME/lever6/gate_R6_kv16_bn32" FIXREF_MARKER="$L7/FIXTURES_OK" \
  bash chain7stage.sh || { echo RESTAGE_FAIL; exit 1; }
[[ -f "$L7/FIXTURES_OK" ]] || { echo "NO FIXTURES_OK — nothing may be measured"; exit 1; }
[[ -d /mnt/ramblob/g3conv27b ]] || { echo "NO CHECKPOINT"; exit 1; }
echo "RESTAGE_OK elapsed=$(elapsed)min remaining=$(remaining)min"

# The arms are already built and flag-audited from the previous window and live on the persistent
# boot disk, so they are NOT rebuilt — but their hashes are re-verified, because a rebuilt binary
# would silently invalidate the gates already banked against the old hash.
phase "1b_verify_arms"
for a in R9_base R9_gqa2 R9_both; do
  [[ -x "$L7/$a" ]] && echo "ARM $a sha256_16=$(sha256sum "$L7/$a" | cut -c1-16) bytes=$(stat -c %s "$L7/$a")" \
                    || echo "ARM $a MISSING"
done
echo "expected from the banked audit: R9_base cd4047affbb40b76 | R9_gqa2 3db7f0dfaf04a7c1 | R9_both ca66b41a2ee34cde"

# ═══ 2 bracket close ═══
phase "2_bracket_close"
if (( $(remaining) < 25 )); then
  echo "SKIP bracket close: only $(remaining)min of cap remain and the short bracket needs ~20"
else
  # CELLTAG=b -> labels r6b_*, which summarize_gemma3_round6.py POOLS with the r6_* cells already
  # banked. This is round 6's own second-bracket mechanism, and it is what turns n=5/4 into n>=7
  # per arm while completing the A..B..A group that produces the drift armor.
  BUILD_ARMS=0 STAGE=timing ARM_A=R9_base ARM_B=R9_gqa2 ARM_C= CELLTAG=b \
    PROMPTS="rag4096:/tmp/g3rag/rag4096.txt:256" \
    bash run_ab_gemma3_round9.sh || echo BRACKET_INCOMPLETE
fi

# ═══ 3 same-session TRT-LLM re-serve ═══
# PRIORITY NOTE: without this there is no same-session comparator and therefore NO publishable
# ratio, so it is guarded at a lower threshold than the bracket — if the cap forces a choice, the
# bracket can be re-run in a later window and pooled, whereas a cross-session ratio cannot be
# published at all.
phase "3_trtllm_reserve"
if (( $(remaining) < 22 )); then
  echo "SKIP TRT re-serve: only $(remaining)min remain and it needs ~20"
  echo "CONSEQUENCE: no same-session comparator, so NO ratio is publishable this window and the"
  echo "bracket delta stays an ours-vs-ours number only."
else
  bash "$HOME/lever3/lv3_trtllm.sh" || echo RESERVE_WARN
  cp -f "$HOME"/lever3/runs/trtllm_pp256.json "$HOME"/lever3/runs/trtllm_pp1024.json \
        "$HOME"/lever3/runs/trtllm_rag4096.json "$L7/runs/" 2>/dev/null || true
  echo "--- reproduction check vs round 6's same-session 40.728 / 110.744 / 426.339 (+-1%) ---"
  for c in pp256 pp1024 rag4096; do
    [[ -f "$L7/runs/trtllm_$c.json" ]] && echo "$c: $(tail -1 "$L7/runs/trtllm_$c.json")" \
                                       || echo "$c: NO JSON"
  done
fi

# ═══ 4 pooled summary ═══
phase "4_summarise"
MEAS="$L7" /usr/bin/python3 summarize_gemma3_round6.py R9_base R9_gqa2 2>&1 | tail -60

# ═══ 5 ROPEVEC gate ═══
phase "5_ropevec_gate"
if (( ROPEVEC_GATE == 1 )) && (( $(remaining) >= 30 )); then
  echo "remaining=$(remaining)min >= 30, gating R9_both (ROPEVEC is ungated code in main)"
  BUILD_ARMS=0 STAGE=gate ARM=R9_both ARM_A=R9_base \
    bash run_ab_gemma3_round9.sh || echo GATE_BOTH_FAIL
elif (( ROPEVEC_GATE != 1 )); then
  echo "ROPEVEC GATE IS OUT OF SCOPE for this window (ROPEVEC_GATE=$ROPEVEC_GATE) and rides a"
  echo "future substantive one. R9_both therefore REMAINS UNGATED: it must not be timed, quoted,"
  echo "or shipped, and its modelled -2.2..-2.7 ms stays a model, now additionally subject to the"
  echo "~70% probe-to-wall-clock transfer ratio round 9 measured."
else
  echo "SKIP ROPEVEC gate: only $(remaining)min of cap remain and the gate needs ~25-50."
  echo "R9_both REMAINS UNGATED and must not be timed, quoted or shipped."
fi

# ═══ off-pin census ═══
phase "6_offpin_census"
bad=0
for c in "$L7"/clocks/*.csv; do
  [[ -f "$c" ]] || continue
  n=$(awk -F, 'NR>1 && $2+0 != 1410 {k++} END{print k+0}' "$c" 2>/dev/null)
  [[ "$n" != "0" ]] && { echo "OFF_PIN $(basename "$c"): $n samples — RE-TAKE REQUIRED"; bad=1; }
done
(( bad == 0 )) && echo "ALL CELLS ON-PIN at 1410 MHz (zero off-pin samples across every cell)"

phase "done"
echo "CHAIN10_DONE $(ts) elapsed=$(elapsed)min of cap=${CAP_MIN}min"
nvidia-smi --query-gpu=index,clocks.current.sm,memory.used --format=csv,noheader
