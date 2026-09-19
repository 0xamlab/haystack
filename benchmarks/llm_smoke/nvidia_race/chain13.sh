#!/usr/bin/env bash
# chain13.sh — ROUND 13 window: ROPEVEC straight to cells (it is CERTIFIED — R9_both passed the
# full fp32 oracle in round 12 with determinism 2/2 bit-identical at all three prompts, so no
# gate-first), then the same-session TRT re-serve, then BOTH a pooled summary and a
# same-bracket-only comparison.
#
# SCOPE, DECLARED BEFORE THE BOX WAS STARTED. Three prompts x the smallest bracket that still
# produces drift armor is ~70 min against a 1 h cap, so this window runs **rag4096 and pp256 only**
# and defers pp1024. Rationale: rag4096 carries the pre-registered acceptance band
# ([-1.0, -3.5] ms), pp256 is the cheap cell and retiring its CROSS-SESSION gap was explicitly
# wanted, and pp1024 is the one that can be added later WITHOUT redoing anything — cells pool by
# label, so a future window runs CELLTAG=d on pp1024 and the summariser folds it in. Declaring a
# scope change before starting is the discipline round 9's undeclared mid-window reprioritisation
# made mandatory.
#
# BRACKET SHAPE: 1 warmup + 3 measured + 1 closing per arm per prompt = 5 cells/arm, 10 per prompt,
# 20 total, ~1.8 min each => ~36 min. The closing ARM_A cell is what makes the group A..B..A and
# therefore what makes the drift armor a MEASUREMENT; it is not optional and is not the thing to cut
# when the cap bites. n=3 measured per arm is below the protocol's n>=7 and is declared as a
# deviation in the ledger rather than hidden.
#
# WHY A SECOND, SAME-BRACKET-ONLY COMPARISON. R9_both has NO banked cells from any earlier window,
# while R9_gqa2 has r6_ (round 9/10) and r6b_ (round 11) cells. The pooled summary would therefore
# compare R9_both's fresh median against R9_gqa2's median drawn mostly from OTHER SESSIONS on other
# days — asymmetric pooling, and exactly the kind of basis mismatch that makes a ratio
# un-publishable. So this chain also computes the delta over r6c_ cells ONLY, which is the
# like-for-like, same-session, same-bracket comparison the acceptance band should be judged on.
# Both numbers are printed; the same-bracket one governs.
#
# Usage (on the VM):  nohup setsid bash chain13.sh > ~/lever7/chain13.nohup 2>&1 &
set -uo pipefail
L7=${L7:-$HOME/lever7}
GPU=${GPU:-1}
CAP_MIN=${CAP_MIN:-52}
W=$L7/window13.log
NR=$HOME/g3r7/benchmarks/llm_smoke/nvidia_race
mkdir -p "$L7/logs" "$L7/runs" "$L7/clocks"
T0=$(date +%s)
: > "$W"
exec > >(tee -a "$W") 2>&1
ts() { date -u +%FT%TZ; }
elapsed() { echo $(( ($(date +%s) - T0) / 60 )); }
remaining() { echo $(( CAP_MIN - ($(date +%s) - T0) / 60 )); }

PHASE=starting
( while true; do
    echo "$(date -u +%FT%TZ) window13 ALIVE elapsed_min=$(( ($(date +%s) - T0) / 60 )) phase=$PHASE \
clk=$(nvidia-smi --query-gpu=clocks.current.sm --format=csv,noheader,nounits -i 1 2>/dev/null) \
mem=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 1 2>/dev/null)MiB" >> "$W"
    sleep 120
  done ) &
LIVE_PID=$!
trap 'kill $LIVE_PID 2>/dev/null' EXIT
phase() { PHASE="$1"; echo; echo "########## [$(ts)] elapsed=$(elapsed)min remaining=$(remaining)min PHASE -> $1 ##########"; }
opkill() { echo "[KILLED_BY_OPERATOR] [$(ts)] target=$1 reason=$2" | tee -a "$W"; }

export GPU L7 CUDA_VISIBLE_DEVICES=$GPU
export WARM_RUNS=1 MEAS_RUNS=3 CLOSE_RUNS=1
echo "WINDOW13_START $(ts) cap=${CAP_MIN}min gpu=$GPU bracket=${WARM_RUNS}warm+${MEAS_RUNS}meas+${CLOSE_RUNS}close per arm"

cd "$NR" || { echo NO_TREE; exit 1; }
[[ -f "$L7/FIXTURES_OK" ]] || { echo "NO FIXTURES_OK — run chain7stage.sh first"; exit 1; }
[[ -d /mnt/ramblob/g3conv27b ]] || { echo "NO CHECKPOINT — run chain7stage.sh first"; exit 1; }
PIN=$(nvidia-smi -i $GPU --query-gpu=clocks.current.sm --format=csv,noheader,nounits)
echo "clocks=$PIN (want 1410)"
if [[ "$PIN" != "1410" ]]; then
  sudo -n nvidia-smi -pm 1 >/dev/null 2>&1; sudo -n nvidia-smi -lgc 1410,1410 >/dev/null 2>&1
  sleep 2; PIN=$(nvidia-smi -i $GPU --query-gpu=clocks.current.sm --format=csv,noheader,nounits)
  [[ "$PIN" == "1410" ]] || { echo "OFF_PIN $PIN — refusing to measure"; exit 1; }
fi

# ── arms are NOT rebuilt: they were built in round 9 and gated in round 12. Their hashes are
#    RE-VERIFIED against the banked audit rather than assumed, because a rebuild would silently
#    detach round 12's ROPEVEC certification from the binary being timed. ──
phase "1_verify_arms"
for a in R9_gqa2 R9_both; do
  [[ -x "$L7/$a" ]] && echo "ARM $a sha256_16=$(sha256sum "$L7/$a" | cut -c1-16) bytes=$(stat -c %s "$L7/$a")" \
                    || { echo "ARM $a MISSING — cannot proceed without rebuilding, which would void the gate"; exit 1; }
done
echo "expected (round 9 build, round 12 gate): R9_gqa2 3db7f0dfaf04a7c1 | R9_both ca66b41a2ee34cde"
for a in R9_gqa2 R9_both; do
  h=$(sha256sum "$L7/$a" | cut -c1-16)
  case "$a" in
    R9_gqa2) [[ "$h" == "3db7f0dfaf04a7c1" ]] || echo "HASH MISMATCH $a: $h -- the round-11 cells and round-12 gate do NOT apply to this binary";;
    R9_both) [[ "$h" == "ca66b41a2ee34cde" ]] || echo "HASH MISMATCH $a: $h -- the round-12 ROPEVEC certification does NOT apply to this binary";;
  esac
done

# ═══ 2 the bracket ═══
phase "2_bracket"
if (( $(remaining) < 40 )); then
  echo "SKIP bracket: only $(remaining)min remain and 20 cells need ~36"
else
  # CELLTAG=c -> labels r6c_*, which pool with r6_ and r6b_ in the summariser. R9_both has no
  # earlier cells, so its pool IS this bracket; R9_gqa2's pool spans three sessions, which is why
  # phase 4 recomputes the delta over r6c_ alone.
  BUILD_ARMS=0 STAGE=timing ARM_A=R9_gqa2 ARM_B=R9_both ARM_C= CELLTAG=c \
    PROMPTS="rag4096:/tmp/g3rag/rag4096.txt:256 pp256:/tmp/g3pp256/prompt_0000.txt:1" \
    bash run_ab_gemma3_round9.sh || echo BRACKET_INCOMPLETE
fi

# ═══ 3 same-session TRT re-serve ═══
phase "3_trtllm_reserve"
if (( $(remaining) < 8 )); then
  echo "SKIP TRT re-serve: only $(remaining)min remain"
  echo "CONSEQUENCE: no same-session comparator, so NO widening is publishable this window"
else
  bash "$HOME/lever3/lv3_trtllm.sh" || echo RESERVE_WARN
  cp -f "$HOME"/lever3/runs/trtllm_pp256.json "$HOME"/lever3/runs/trtllm_pp1024.json \
        "$HOME"/lever3/runs/trtllm_rag4096.json "$L7/runs/" 2>/dev/null || true
  echo "--- reproduction check vs the stored column (must be within 1% or label CROSS-SESSION) ---"
  /usr/bin/python3 - <<'PY'
import json, glob, os
STORED = {"pp256": 41.520, "pp1024": 110.782, "rag4096": 426.766}
R6 = {"pp256": 40.728, "pp1024": 110.744, "rag4096": 426.339}
for c in ("pp256", "pp1024", "rag4096"):
    p = os.path.expanduser(f"~/lever7/runs/trtllm_{c}.json")
    if not os.path.exists(p):
        print(f"  {c:<8} NO JSON"); continue
    txt = open(p, errors="replace").read().strip().splitlines()
    val = None
    for ln in reversed(txt):
        ln = ln.strip()
        if ln.startswith("{"):
            try:
                d = json.loads(ln)
            except Exception:
                continue
            for k in ("ttft_ms", "median_ms", "ttft_median_ms", "median"):
                if isinstance(d.get(k), (int, float)):
                    val = float(d[k]); break
            if val: break
    if val is None:
        print(f"  {c:<8} could not parse a median from {p}"); continue
    ds = 100.0 * (val - STORED[c]) / STORED[c]
    d6 = 100.0 * (val - R6[c]) / R6[c]
    ok = abs(ds) <= 1.0
    print(f"  {c:<8} re-served {val:8.3f} ms | vs stored {STORED[c]:8.3f} = {ds:+.3f}% "
          f"{'REPRODUCES' if ok else 'CROSS-SESSION'} | vs round6 {R6[c]:8.3f} = {d6:+.3f}%")
PY
fi

# ═══ 4 summaries: pooled AND same-bracket-only ═══
phase "4_summarise"
echo "--- (a) POOLED summary (r6_ + r6b_ + r6c_; note R9_both has only r6c_ so its pool is this bracket) ---"
MEAS="$L7" /usr/bin/python3 summarize_gemma3_round6.py R9_gqa2 R9_both 2>&1 | tail -45

echo "--- (b) SAME-BRACKET-ONLY comparison (r6c_ cells only) — THIS ONE GOVERNS ---"
/usr/bin/python3 - <<'PY'
import json, glob, os, statistics
runs = os.path.expanduser("~/lever7/runs")
def med(arm, prompt):
    vals = []
    for f in sorted(glob.glob(f"{runs}/r6c_{arm}_{prompt}_r*.json")) + \
             sorted(glob.glob(f"{runs}/r6c_{arm}_{prompt}_r*.out")):
        try:
            txt = open(f, errors="replace").read().strip().splitlines()
        except Exception:
            continue
        for ln in reversed(txt):
            ln = ln.strip()
            if not ln.startswith("{"): continue
            try: d = json.loads(ln)
            except Exception: continue
            for k in ("ttft_ms", "prefill_ms", "median_ms", "ttft_median_ms"):
                if isinstance(d.get(k), (int, float)):
                    vals.append(float(d[k])); break
            break
    return vals
for prompt in ("rag4096", "pp256"):
    a = med("R9_gqa2", prompt); b = med("R9_both", prompt)
    if not a or not b:
        print(f"  {prompt:<9} insufficient r6c_ cells (R9_gqa2 n={len(a)}, R9_both n={len(b)})"); continue
    ma, mb = statistics.median(a), statistics.median(b)
    def iqr(v):
        s = sorted(v); n = len(s)
        return (s[(3*n)//4] - s[n//4]) if n >= 4 else 0.0
    delta = mb - ma
    print(f"  {prompt:<9} R9_gqa2 n={len(a)} median={ma:.3f} ms (IQR {iqr(a):.3f}) | "
          f"R9_both n={len(b)} median={mb:.3f} ms (IQR {iqr(b):.3f}) | delta={delta:+.3f} ms "
          f"({100.0*delta/ma:+.3f}%)")
    if prompt == "rag4096":
        band = (-3.5, -1.0)
        inside = band[0] <= delta <= band[1]
        print(f"            acceptance band [{band[0]}, {band[1]}] ms -> "
              f"{'INSIDE (flip candidate)' if inside else 'OUTSIDE (flag stays default-OFF)'}")
PY

# ═══ 5 off-pin census ═══
phase "5_offpin_census"
bad=0
for c in "$L7"/clocks/*.csv; do
  [[ -f "$c" ]] || continue
  n=$(awk -F, 'NR>1 && $2+0 != 1410 {k++} END{print k+0}' "$c" 2>/dev/null)
  [[ "$n" != "0" ]] && { echo "OFF_PIN $(basename "$c"): $n samples — RE-TAKE REQUIRED"; bad=1; }
done
(( bad == 0 )) && echo "no off-pin samples in any cell of this window"

phase "done"
echo "CHAIN13_DONE $(ts) elapsed=$(elapsed)min of cap=${CAP_MIN}min"
nvidia-smi --query-gpu=index,clocks.current.sm,memory.used --format=csv,noheader
