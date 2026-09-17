#!/usr/bin/env bash
# chain9.sh — ROUND 9's VM window: gates-first A/B of the GQA-packed attention dispatch (and, as a
# third arm, GQA2 + ROPEVEC together) against round 6's published ship configuration.
#
# WHY THIS ORDER. The protocol is gates before any speed claim, so the expensive part (oracle
# gates) runs before the part that produces numbers, and a failed gate stops everything. Phases are
# marked so that if the 3 h VM-on budget truncates the window, the truncation point is unambiguous
# and the least-load-bearing phase is the one lost:
#
#   1 build    shim (with the -Xptxas -v register census) + three arms + flag audit
#   2 smoke    does GQA2 actually ARM at runtime, and what is the first delta? A declined lever
#              must never masquerade as an armed one, so the banner is checked, not assumed.
#   3 gates    R9_gqa2 then R9_both, full fp32 oracle: G0 16/16 + G1 64/64 with the 64-token run
#              repeated for determinism + val550 + rag4096 22/22 EOS-stop
#   4 cells    pp256 + pp1024 + rag4096, interleaved A..B..C..A, 3 warmup + 7 measured
#   5 trtllm   same-session re-serve; must reproduce 40.728 / 110.744 / 426.339 within 1% or every
#              ratio is labelled CROSS-SESSION. pp256 finally gets a same-session column.
#   6 nsys     the fixed --from-first-attn extractor: exact rope / norm-accum / geglu / attention
#              buckets, which both proves the attention delta landed where the probe said and
#              prices norm-accum properly instead of on round 6's geometry attribution.
#
# THE ARMS. R9_base is #1006's ship flag set rebuilt from THIS branch, so the bracket measures
# against the exact configuration that produced 389.033 / 94.022 / 32.108 ms rather than against a
# rebuild of something else.
#
#   R9_base   TC_SHIM + G3_STREAM + G3_GEGLU_U4 + G3_ATTN_FLASH + G3_PF_TCATTN + FA + F16ATTN
#             + F16NORM + F16MLP + ROPE2 + FA2 + KV16 + BN32        (= round 6's R6_kv16_bn32)
#   R9_gqa2   R9_base + ALGENTA_G3_PF_GQA2 — GQA-packed v3 attention from n_keys >= 2048.
#             BIT-IDENTICAL to v2 (probe: 216/216 BITIDENT-v2, 0 BITDIFF, 0 FAIL at BN=32 and
#             BN=64), and pp256/pp1024 sit below the threshold so they keep v2 bit for bit.
#   R9_both   R9_gqa2 + ALGENTA_G3_PF_ROPEVEC — the two levers together. ROPEVEC is NOT
#             bit-identical (contiguous quads re-associate the qk_norm sum-of-squares), so this
#             arm is the one that genuinely needs the fp32 oracle.
#
# Usage (on the VM):  nohup setsid bash chain9.sh > ~/lever7/chain9.out 2>&1 &
set -uo pipefail
L7=${L7:-$HOME/lever7}
GPU=${GPU:-1}
LOG=${LOG:-$L7/chain9.log}
mkdir -p "$L7/logs" "$L7/runs" "$L7/clocks"
exec > >(tee -a "$LOG") 2>&1
ts() { date -u +%FT%TZ; }

HB=$L7/heartbeat.log
PHASE=starting
( while true; do echo "$(date -u +%FT%TZ) chain9 GPU=$GPU phase=$PHASE" >> "$HB"; sleep 60; done ) &
HB_PID=$!
trap 'kill $HB_PID 2>/dev/null' EXIT
phase() { PHASE="$1"; echo; echo "########## [$(ts)] PHASE -> $1 ##########"; }
export GPU L7 CUDA_VISIBLE_DEVICES=$GPU

cd "$HOME/g3r7/benchmarks/llm_smoke/nvidia_race" || { echo NO_TREE; exit 1; }

# Refuse to run against unproven fixtures: the re-stage must have certified them against round 6's
# gate echoes first, or the cells measure a different prompt set from the one the oracle certified.
[[ -f "$L7/FIXTURES_OK" ]] || { echo "NO FIXTURES_OK MARKER — run chain7stage.sh first"; exit 1; }
[[ -d /mnt/ramblob/g3conv27b ]] || { echo "NO CHECKPOINT — run chain7stage.sh first"; exit 1; }
PIN=$(nvidia-smi -i $GPU --query-gpu=clocks.current.sm --format=csv,noheader,nounits)
echo "[$(ts)] clocks before anything: GPU$GPU=$PIN (want 1410)"
[[ "$PIN" == "1410" ]] || { sudo -n nvidia-smi -pm 1 >/dev/null 2>&1
  sudo -n nvidia-smi -lgc 1410,1410 >/dev/null 2>&1; sleep 2
  PIN=$(nvidia-smi -i $GPU --query-gpu=clocks.current.sm --format=csv,noheader,nounits)
  [[ "$PIN" == "1410" ]] || { echo "OFF_PIN $PIN — refusing to measure"; exit 1; }; }

phase "1_build"
STAGE=build bash run_ab_gemma3_round9.sh || { echo BUILD_FAIL; exit 1; }

phase "2_smoke"
BUILD_ARMS=0 STAGE=smoke ARM_A=R9_base ARM_B=R9_gqa2 ARM_C=R9_both \
  bash run_ab_gemma3_round9.sh || { echo SMOKE_FAIL; exit 1; }
echo "--- did GQA2 actually ARM? (a declined lever must never masquerade) ---"
for a in R9_gqa2 R9_both R9_base; do
  echo "[$a]"; grep -m1 "TCFLAG ALGENTA_G3_PF_GQA2" "$L7/runs/smoke_${a}_pp1024.out" \
    || echo "  no GQA2 banner (expected for R9_base)"
  grep -m1 "TCFLAG ALGENTA_G3_PF_ROPEVEC" "$L7/runs/smoke_${a}_pp1024.out" \
    || echo "  no ROPEVEC banner (expected unless the arm sets it)"
  grep -m1 "^G3 FLAGS:" "$L7/runs/smoke_${a}_pp1024.out" || true
done

phase "3_gates"
BUILD_ARMS=0 STAGE=gate ARM=R9_gqa2 bash run_ab_gemma3_round9.sh \
  || { echo GATE_GQA2_FAIL; exit 1; }
BUILD_ARMS=0 STAGE=gate ARM=R9_both bash run_ab_gemma3_round9.sh \
  || { echo GATE_BOTH_FAIL; exit 1; }

phase "4_cells"
P_ALL="pp256:/tmp/g3pp256/prompt_0000.txt:1 pp1024:/tmp/g3pp1024/prompt_0000.txt:1 rag4096:/tmp/g3rag/rag4096.txt:256"
BUILD_ARMS=0 STAGE=timing ARM_A=R9_base ARM_B=R9_gqa2 ARM_C=R9_both PROMPTS="$P_ALL" \
  bash run_ab_gemma3_round9.sh || { echo TIMING_FAIL; exit 1; }

phase "5_trtllm_reserve"
bash "$HOME/lever3/lv3_trtllm.sh" || echo RESERVE_WARN
cp -f "$HOME"/lever3/runs/trtllm_pp256.json "$HOME"/lever3/runs/trtllm_pp1024.json \
      "$HOME"/lever3/runs/trtllm_rag4096.json "$L7/runs/" 2>/dev/null || true
echo "--- same-session reproduction vs 40.728 / 110.744 / 426.339 (within 1% or CROSS-SESSION) ---"
for c in pp256 pp1024 rag4096; do
  [[ -f "$L7/runs/trtllm_$c.json" ]] && echo "$c: $(tail -1 "$L7/runs/trtllm_$c.json")" \
    || echo "$c: NO JSON"
done

phase "6_nsys"
bash run_nsys_gemma3_round9.sh || echo NSYS_WARN

phase "7_offpin_census"
echo "=== off-pin census across every measured cell (ZERO tolerance) ==="
bad=0
for c in "$L7"/clocks/*.csv; do
  [[ -f "$c" ]] || continue
  n=$(awk -F, 'NR>1 && $2+0 != 1410 {k++} END{print k+0}' "$c" 2>/dev/null)
  tot=$(awk 'NR>1' "$c" 2>/dev/null | wc -l)
  if [[ "$n" != "0" ]]; then echo "OFF_PIN $(basename "$c"): $n of $tot samples — RE-TAKE REQUIRED"; bad=1; fi
done
(( bad == 0 )) && echo "ALL CELLS ON-PIN at 1410 MHz (0 off-pin samples)"

phase "done"
echo "=== [$(ts)] chain9 DONE ==="
nvidia-smi --query-gpu=index,clocks.current.sm,memory.used --format=csv,noheader
