#!/bin/bash
# chain7full.sh — ROUND 7's single VM-on window, end to end and unattended, on
# trtllm-gemma-us-west1-c. Ordered so that if the 3 h VM-on budget truncates it, the truncation
# costs the least-load-bearing phase: the probe verdict and the per-layer proof come before the
# second timing bracket, and every phase logs its own start/end so the cut point is unambiguous.
#
#   phase 1  probe-log retrieval   the RT=2 question the register census left OPEN: it proved v3
#                                  needs 255 registers and spills 424-488 B, but spill SIZE is
#                                  not spill FREQUENCY in the hot loop. These two logs were
#                                  written to the local SSD before the box was stopped, so they
#                                  survive and answer it for free.
#   phase 2  re-stage              a stop wipes the tmpfs fixtures AND the RAM-blob checkpoint;
#                                  chain7stage.sh regenerates both and PROVES the fixtures are
#                                  token-identical to round 6's certified gate echoes before
#                                  anything is measured, then pins and verifies 1410 MHz.
#   phase 3  build + smoke         shim (with the register census) + R7_base + R7_ropev + flag
#                                  audit; smoke proves ROPEVEC actually ARMED at runtime, so a
#                                  declined lever can never masquerade as an armed one.
#   phase 4  oracle gates          BOTH arms, before any speed claim: G0 16/16 + G1 64/64 with
#                                  the 64-token run repeated for determinism + val550 + rag4096
#                                  22/22 with the EOS-stop rule. ROPEVEC is NOT bit-identical
#                                  (contiguous quads re-associate the qk_norm reduction), so it
#                                  is gated against the fp32 oracle, not against R7_base's bits.
#   phase 5  timing bracket 1      pp256 + pp1024 + rag4096, interleaved A..B..A. pp256 is
#                                  included because it has been CROSS-SESSION since round 6 and
#                                  this round's re-serve can finally make it same-session.
#   phase 6  TRT-LLM re-serve      FRESH, same session; must reproduce 40.728 / 110.744 /
#                                  426.339 within 1% or every ratio is labelled CROSS-SESSION.
#   phase 7  nsys decomposition    the per-layer proof, with the FIXED extractor boundary so
#                                  rope / norm-accum / geglu become measured instead of
#                                  geometry-attributed (round 6 integrity note 4).
#   phase 8  timing bracket 2      rag4096 only, CELLTAG=b, so the priority cell gets a second
#                                  independent bracket and pooled n=14 like round 6.
#
# HEARTBEAT: one line to ~/lever7/heartbeat.log every 60 s for the whole window, phase-tagged, so
# the top-level idle audit sees a live front rather than an idle box and does not stop it mid-cell.
#
# Usage (on the VM):  nohup setsid bash chain7full.sh > ~/lever7/chain7full.out 2>&1 &
set -uo pipefail
L7=${L7:-$HOME/lever7}
GPU=${GPU:-1}
LOG=${LOG:-$L7/chain7full.log}
mkdir -p "$L7/logs" "$L7/runs" "$L7/clocks"
exec > >(tee -a "$LOG") 2>&1
ts() { date -u +%FT%TZ; }

HB=$L7/heartbeat.log
PHASE="starting"
( while true; do echo "$(date -u +%FT%TZ) chain7full GPU=$GPU phase=$PHASE" >> "$HB"; sleep 60; done ) &
HB_PID=$!
trap 'kill $HB_PID 2>/dev/null' EXIT
phase() { PHASE="$1"; echo; echo "############ [$(ts)] PHASE 1..8 -> $1 ############"; }
export GPU L7
export CUDA_VISIBLE_DEVICES=$GPU

cd "$HOME/g3r7/benchmarks/llm_smoke/nvidia_race" || { echo NO_TREE; exit 1; }

phase "1_probe_log_retrieval"
for BN in 32 64; do
  f=$L7/logs/fa_g3_probe_bn$BN.log
  if [[ -f "$f" ]]; then
    echo "=== fa_g3_probe --bn $BN (written before the stop; survives on local SSD) ==="
    echo "  FAIL=$(grep -c ' FAIL' "$f") BITIDENT-v2=$(grep -c 'BITIDENT-v2' "$f") \
BITDIFF=$(grep -c 'BITDIFF' "$f") NOv2REF=$(grep -c 'NOv2REF' "$f")"
    echo "  -- correctness rows that are NOT a clean pass/bit-ident --"
    grep -E "BITDIFF|NOv2REF| FAIL|STATUS " "$f" | head -20 || echo "  (none)"
    echo "  -- [1d] rejection battery --"
    grep -E "^\[1d\]" "$f" | head -8
    echo "  -- [4] ROUND-7 DECISION TABLE (RT=2 DESPITE the spill: did it beat v2?) --"
    sed -n '/\[4\] ROUND-7/,/fa_g3_probe:/p' "$f"
  else
    echo "MISSING $f — the probe did not get to bn=$BN before the stop"
  fi
done

phase "2_restage"
bash chain7stage.sh || { echo "RESTAGE_FAIL — nothing may be measured"; exit 1; }
grep -q "STAGE_OK" "$L7/chain7stage.log" || { echo "NO STAGE_OK — abort"; exit 1; }

phase "3_build_smoke"
STAGE=smoke bash run_ab_gemma3_round7.sh || { echo BUILD_OR_SMOKE_FAIL; exit 1; }

phase "4_oracle_gates"
BUILD_ARMS=0 STAGE=gate ARM=R7_ropev bash run_ab_gemma3_round7.sh \
  || { echo GATE_ROPEV_FAIL; exit 1; }
BUILD_ARMS=0 STAGE=gate ARM=R7_base bash run_ab_gemma3_round7.sh \
  || { echo GATE_BASE_FAIL; exit 1; }

P_ALL="pp256:/tmp/g3pp256/prompt_0000.txt:1 pp1024:/tmp/g3pp1024/prompt_0000.txt:1 rag4096:/tmp/g3rag/rag4096.txt:256"
phase "5_timing_bracket1"
BUILD_ARMS=0 STAGE=timing ARM_A=R7_base ARM_B=R7_ropev ARM_C= PROMPTS="$P_ALL" \
  bash run_ab_gemma3_round7.sh || { echo TIMING_B1_FAIL; exit 1; }

phase "6_trtllm_reserve"
bash "$HOME/lever3/lv3_trtllm.sh" || echo RESERVE_WARN
cp -f "$HOME"/lever3/runs/trtllm_pp256.json "$HOME"/lever3/runs/trtllm_pp1024.json \
      "$HOME"/lever3/runs/trtllm_rag4096.json "$L7/runs/" 2>/dev/null || true
echo "--- same-session reproduction check against 40.728 / 110.744 / 426.339 ---"
for c in pp256 pp1024 rag4096; do
  [[ -f "$L7/runs/trtllm_$c.json" ]] && echo "$c: $(tail -1 "$L7/runs/trtllm_$c.json")" \
    || echo "$c: NO JSON"
done

phase "7_nsys_decomposition"
bash run_nsys_gemma3_round7.sh || echo NSYS_WARN

phase "8_timing_bracket2_rag4096"
BUILD_ARMS=0 STAGE=timing ARM_A=R7_base ARM_B=R7_ropev ARM_C= CELLTAG=b \
  PROMPTS="rag4096:/tmp/g3rag/rag4096.txt:256" \
  bash run_ab_gemma3_round7.sh || echo TIMING_B2_WARN

phase "9_offpin_census_and_summary"
echo "=== off-pin census across every measured cell (ZERO tolerance) ==="
if ls "$L7"/clocks/*.csv >/dev/null 2>&1; then
  for c in "$L7"/clocks/*.csv; do
    n=$(awk -F, 'NR>1 && $2+0 != 1410 {k++} END{print k+0}' "$c" 2>/dev/null)
    tot=$(awk 'NR>1' "$c" 2>/dev/null | wc -l)
    [[ "$n" != "0" ]] && echo "OFF_PIN $(basename "$c"): $n of $tot samples"
  done
  echo "(any cell listed above must be RE-TAKEN before its number is quoted)"
else
  echo "no clock CSVs found"
fi
echo "=== pooled results ==="
MEAS="$L7" /usr/bin/python3 summarize_gemma3_round6.py R7_base R7_ropev 2>&1 | tail -40 || true

phase "done"
echo "=== [$(ts)] chain7full DONE ==="
nvidia-smi --query-gpu=index,clocks.current.sm,memory.used --format=csv,noheader
