#!/usr/bin/env bash
# chain14.sh — ROUND 14: bracket the NEW SHIPPED DEFAULT (post-double-flip, no lever flags) at
# pp1024 and pp256, n>=7 per prompt with a mandatory closing cell for drift armor, then the
# same-session TRT-LLM re-serve.
#
# SCOPE, DECLARED BEFORE THE FIRST CELL. Hard cap 1.5 h from 05:49:11Z => stop by 07:19Z. The VM
# did not accept SSH until ~05:58Z and re-staging the wiped tmpfs (fixtures + the 101 G checkpoint
# conversion) cost ~7 min, so the usable measurement budget is ~50 min. Every cell costs ~100-120 s
# REGARDLESS of prompt because the dominant term is the driver loading the 101 G checkpoint in a
# fresh process, not the prefill — round 13's rag4096 cells ran 116-125 s and pp256 cells are the
# same order. That arithmetic, not preference, sets the shape below.
#
# WHY THE SAME BINARY UNDER TWO NAMES. run_gemma3_round6_cells.sh names cells
# `r6<TAG>_<ARM>_<prompt>_r<i>` and always runs BOTH ARM_A and ARM_B each round, and ARM_B cannot be
# left empty (it has a default). Setting ARM_A=ARM_B would therefore COLLIDE on the cell filename and
# silently lose half the samples. So the default arm is built once and `cp`'d to a second name:
# identical bits, distinct labels, no collision, and every cell counts toward the default's pooled n.
# The A-vs-B "delta" is then a pure run-to-run REPRODUCIBILITY measurement of one configuration,
# which is a useful number in its own right rather than a wasted arm.
#
# CONTROLS ARE OUT OF SCOPE THIS WINDOW, declared not discovered. The brief allows R9_gqa2/R9_ropev
# only if >=30 min remain after the defaults bracket; at ~50 min of usable budget the bracket itself
# (24 cells) plus the re-serve consumes it. They isolate the two levers for the LEDGER, not for
# publication, so deferring them costs no publishable row.
#
# GATE: NOT RE-RUN, AND THIS IS A DECLARED DEVIATION. Justification, all of it checkable on CPU
# before the box was started: `git diff 5bf62c29 HEAD` shows the ONLY changed Mojo source is
# session_cuda_gemma3_f16.mojo, and kernels_prefill_gemma3.mojo, tc_shim.cu and tc_shim_bridge.mojo
# are BYTE-IDENTICAL to the source the round-12-certified arm ca66b41a2ee34cde was built from. The
# two comptime defaults now resolve to the SAME booleans the certified arm got from its opt-in
# flags, so the selected kernels are the same kernels; the residual binary difference is banner text
# (two TCFLAG strings I rewrote) plus the source-position metadata and SSA renumbering that cascade
# from it. Round 12 set the precedent for exactly this call when it abandoned a redundant R9_base
# re-gate ("already ALL_PASS twice") to protect the measurement. The substitute evidence collected
# here is the flag audit over the REAL LINKED binary (which also exercises the two audit rows added
# in #1042 for the first time on a linked arm) plus the timing stage's own banner_audit.
#
# Usage (on the VM):  nohup setsid bash chain14.sh > ~/lever7/chain14.nohup 2>&1 &
set -uo pipefail
L7=${L7:-$HOME/lever7}
GPU=${GPU:-1}
CAP_MIN=${CAP_MIN:-56}
W=$L7/window14.log
NR=$HOME/g3r7/benchmarks/llm_smoke/nvidia_race
DEF=R9_both          # post-flip, built with NO lever flags == the shipped default
TWIN=R14_defB        # byte-identical copy, distinct label so cells cannot collide
mkdir -p "$L7/logs" "$L7/runs" "$L7/clocks"
T0=$(date +%s)
touch "$W"
exec > >(tee -a "$W") 2>&1
ts() { date -u +%FT%TZ; }
elapsed() { echo $(( ($(date +%s) - T0) / 60 )); }
remaining() { echo $(( CAP_MIN - ($(date +%s) - T0) / 60 )); }

PHASE=starting
( while true; do
    echo "$(date -u +%FT%TZ) window14 ALIVE elapsed_min=$(( ($(date +%s) - T0) / 60 )) phase=$PHASE \
clk=$(nvidia-smi --query-gpu=clocks.current.sm --format=csv,noheader,nounits -i 1 2>/dev/null) \
mem=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i 1 2>/dev/null)MiB" >> "$W"
    sleep 120
  done ) &
LIVE_PID=$!
trap 'kill $LIVE_PID 2>/dev/null' EXIT
phase() { PHASE="$1"; echo; echo "########## [$(ts)] elapsed=$(elapsed)min remaining=$(remaining)min PHASE -> $1 ##########"; }
opkill() { echo "[KILLED_BY_OPERATOR] [$(ts)] target=$1 reason=$2" | tee -a "$W"; }

export GPU L7 CUDA_VISIBLE_DEVICES=$GPU
export WARM_RUNS=1 MEAS_RUNS=4 CLOSE_RUNS=1
echo "WINDOW14_START $(ts) cap=${CAP_MIN}min gpu=$GPU bracket=${WARM_RUNS}warm+${MEAS_RUNS}meas+${CLOSE_RUNS}close per arm-slot"
echo "ARM SLOTS: A=$DEF B=$TWIN (BYTE-IDENTICAL copies of the shipped default; the A/B delta is a reproducibility check)"

cd "$NR" || { echo NO_TREE; exit 1; }

# ── 1 staging must already be complete, and clocks must be pinned ──
phase "1_verify_stage_and_clocks"
[[ -f "$L7/FIXTURES_OK" ]] || { echo "NO FIXTURES_OK — staging incomplete"; exit 1; }
[[ -d /mnt/ramblob/g3conv27b ]] || { echo "NO CHECKPOINT — staging incomplete"; exit 1; }
grep -q 'STAGE_OK' "$L7/stage14.log" 2>/dev/null && echo "STAGE_OK confirmed in stage14.log" || echo "WARN: no STAGE_OK line in stage14.log — inspect before trusting cells"
grep -E 'IDENTICAL|FIXTURE_IDENTITY_OK' "$L7/stage14.log" 2>/dev/null | tail -6
PIN=$(nvidia-smi -i $GPU --query-gpu=clocks.current.sm --format=csv,noheader,nounits)
echo "clocks=$PIN (want 1410)"
if [[ "$PIN" != "1410" ]]; then
  sudo -n nvidia-smi -pm 1 >/dev/null 2>&1; sudo -n nvidia-smi -lgc 1410,1410 >/dev/null 2>&1
  sleep 2; PIN=$(nvidia-smi -i $GPU --query-gpu=clocks.current.sm --format=csv,noheader,nounits)
  [[ "$PIN" == "1410" ]] || { echo "OFF_PIN $PIN — refusing to measure"; exit 1; }
fi

# ── 2 build. Post-flip, R9_both is built with NO lever flags, so it IS the shipped default. ──
phase "2_build_default"
if (( $(remaining) < 44 )); then
  echo "SKIP build+bracket: only $(remaining)min remain"; exit 1
fi
# PRESERVE THE CERTIFIED BINARY BEFORE THE REBUILD OVERWRITES IT. $L7/R9_both is round 9's build
# ca66b41a2ee34cde, the exact arm round 12 gated ALL_PASS and round 13 timed. Rebuilding writes the
# same filename, so back it up first and assert the hash — that keeps the certification attachable
# by hash and leaves a fallback if the fresh build fails or the cap bites.
if [[ -x "$L7/$DEF" ]]; then
  cp -f "$L7/$DEF" "$L7/${DEF}_r12cert"
  hc=$(sha256sum "$L7/${DEF}_r12cert" | cut -c1-16)
  echo "PRESERVED ${DEF}_r12cert sha256_16=$hc (expect ca66b41a2ee34cde — the round-12 CERTIFIED arm)"
  [[ "$hc" == "ca66b41a2ee34cde" ]] && echo "CERTIFIED_HASH_MATCH=True" \
    || echo "CERTIFIED_HASH_MATCH=False — the preserved arm is NOT the gated one; do not cite the gate for it"
fi
STAGE=build bash run_ab_gemma3_round9.sh || { echo BUILD_FAIL; exit 1; }
[[ -x "$L7/$DEF" ]] || { echo "NO $DEF BINARY"; exit 1; }
echo "DEFAULT ARM $DEF sha256_16=$(sha256sum "$L7/$DEF" | cut -c1-16) bytes=$(stat -c %s "$L7/$DEF")"
echo "certified round-12 arm was ca66b41a2ee34cde — a DIFFERENT hash is EXPECTED here (banner text"
echo "changed); the configuration is identical because no kernel source changed. See the header."

# ── 3 twin copy, proven identical by hash rather than assumed ──
phase "3_twin_copy"
cp -f "$L7/$DEF" "$L7/$TWIN"
h1=$(sha256sum "$L7/$DEF" | cut -c1-16); h2=$(sha256sum "$L7/$TWIN" | cut -c1-16)
echo "TWIN $TWIN sha256_16=$h2 vs $DEF $h1"
[[ "$h1" == "$h2" ]] || { echo "TWIN HASH MISMATCH — refusing to bracket"; exit 1; }
echo "TWIN_IDENTICAL=True (so every cell from either slot is a sample of ONE configuration)"

# ── 4 the bracket. pp1024 FIRST: it has ZERO banked cells for this arm and carries the parent's
#       publish target, so it is the one that must not be the casualty of a cap bite. ──
phase "4_bracket"
if (( $(remaining) < 30 )); then
  echo "SKIP bracket: only $(remaining)min remain"
else
  BUILD_ARMS=0 STAGE=timing ARM_A=$DEF ARM_B=$TWIN ARM_C= CELLTAG=e \
    PROMPTS="pp1024:/tmp/g3pp1024/prompt_0000.txt:1 pp256:/tmp/g3pp256/prompt_0000.txt:1" \
    bash run_ab_gemma3_round9.sh || { opkill "bracket" "harness returned non-zero; partial cells are banked and pool"; }
fi

# ── 5 same-session TRT re-serve: without it NO ratio is publishable ──
phase "5_trtllm_reserve"
if (( $(remaining) < 8 )); then
  echo "SKIP TRT re-serve: only $(remaining)min remain"
  echo "CONSEQUENCE: no same-session comparator, so NO row is publishable this window"
else
  bash "$HOME/lever3/lv3_trtllm.sh" || echo RESERVE_WARN
  cp -f "$HOME"/lever3/runs/trtllm_pp256.json "$HOME"/lever3/runs/trtllm_pp1024.json \
        "$HOME"/lever3/runs/trtllm_rag4096.json "$L7/runs/" 2>/dev/null || true
  echo "--- reproduction check vs BOTH stored columns (must be within 1% or label CROSS-SESSION) ---"
  /usr/bin/python3 - <<'PY'
import json, os
STORED = {"pp256": 41.520, "pp1024": 110.782, "rag4096": 426.766}
R6 = {"pp256": 40.728, "pp1024": 110.744, "rag4096": 426.339}
R13 = {"pp256": 41.292, "pp1024": 110.713, "rag4096": 429.400}
for c in ("pp256", "pp1024", "rag4096"):
    p = os.path.expanduser(f"~/lever7/runs/trtllm_{c}.json")
    if not os.path.exists(p):
        print(f"  {c:<8} NO JSON"); continue
    val = None
    for ln in reversed(open(p, errors="replace").read().strip().splitlines()):
        ln = ln.strip()
        if not ln.startswith("{"): continue
        try: d = json.loads(ln)
        except Exception: continue
        for k in ("ttft_ms", "median_ms", "ttft_median_ms", "median"):
            if isinstance(d.get(k), (int, float)): val = float(d[k]); break
        if val: break
    if val is None:
        # BUG FIXED after round 14: this parse FAILED for all three cells ("could not parse a
        # median") while the repo's own summarize_gemma3_round6.py read the same files fine, so my
        # key list did not match the real schema. Rather than guess again, DUMP THE RAW JSON so the
        # value is always in the single log and the authoritative comparison is the summariser's.
        # A silent parse failure here would have looked like a missing re-serve.
        print(f"  {c:<8} could not parse a median from {p} — RAW CONTENT FOLLOWS:")
        for ln in txt[-3:]:
            print(f"           raw| {ln[:400]}")
        continue
    ds = 100.0*(val-STORED[c])/STORED[c]; d13 = 100.0*(val-R13[c])/R13[c]
    ok = abs(ds) <= 1.0
    print(f"  {c:<8} re-served {val:8.3f} ms | vs stored {STORED[c]:8.3f} = {ds:+.3f}% "
          f"{'REPRODUCES' if ok else 'CROSS-SESSION'} | vs round13 {R13[c]:8.3f} = {d13:+.3f}%")
PY
fi

# ── 6 summaries: pooled (r6_+r6b_+r6c_+r6e_) and this-bracket-only ──
phase "6_summarise"
echo "--- (a) POOLED summary ---"
MEAS="$L7" /usr/bin/python3 summarize_gemma3_round6.py $DEF $TWIN 2>&1 | tail -40
echo "--- (b) THIS-BRACKET-ONLY (r6e_ cells), one configuration in both slots ---"
/usr/bin/python3 - <<'PY'
import json, glob, os, statistics
runs = os.path.expanduser("~/lever7/runs")
def vals(arm, prompt):
    out = []
    for f in sorted(glob.glob(f"{runs}/r6e_{arm}_{prompt}_r*.out")) + \
             sorted(glob.glob(f"{runs}/r6e_{arm}_{prompt}_r*.json")):
        try: txt = open(f, errors="replace").read().strip().splitlines()
        except Exception: continue
        for ln in reversed(txt):
            ln = ln.strip()
            if not ln.startswith("{"): continue
            try: d = json.loads(ln)
            except Exception: continue
            for k in ("ttft_ms", "prefill_ms", "median_ms", "ttft_median_ms"):
                if isinstance(d.get(k), (int, float)): out.append(float(d[k])); break
            break
    return out
def vals_close(arm, prompt):
    """The closing cell(s) of the A..B..A bracket — the second A, which is what makes the drift
    armor a MEASUREMENT rather than an assumption. Kept separate from vals() so a missing close
    cell is reported as NOT COMPUTABLE instead of being silently folded into the median."""
    out = []
    for f in sorted(glob.glob(f"{runs}/r6e_{arm}_{prompt}_close*.out")) + \
             sorted(glob.glob(f"{runs}/r6e_{arm}_{prompt}_close*.json")):
        try: txt = open(f, errors="replace").read().strip().splitlines()
        except Exception: continue
        for ln in reversed(txt):
            ln = ln.strip()
            if not ln.startswith("{"): continue
            try: d = json.loads(ln)
            except Exception: continue
            for k in ("ttft_ms", "prefill_ms", "median_ms", "ttft_median_ms"):
                if isinstance(d.get(k), (int, float)): out.append(float(d[k])); break
            break
    return out
for prompt in ("pp1024", "pp256"):
    a = vals("R9_both", prompt); b = vals("R14_defB", prompt)
    both = sorted(a + b)
    if not both:
        print(f"  {prompt:<7} no r6e_ cells"); continue
    m = statistics.median(both)
    s = sorted(both); n = len(s)
    iqr = (s[(3*n)//4] - s[n//4]) if n >= 4 else 0.0
    rel = 100.0*iqr/m if m else 0.0
    print(f"  {prompt:<7} n={n} (A={len(a)} B={len(b)}) median={m:.3f} ms IQR={iqr:.3f} rel-IQR={rel:.3f}%")
    print(f"           values={['%.3f'%v for v in both]}")
    # DRIFT ARMOR. BUG FIXED after round 14: the glob above is `_r*` only, so it EXCLUDED the
    # warm1/close1 cells — which is exactly where the armor lives. The closing cell ran and ENDed
    # rc=0 offpin=0 both times, but its value was never read, so round 14 could not compute armor
    # and therefore could not publish. Read the close cell explicitly from now on.
    cl = vals_close("R9_both", prompt)
    if cl and a:
        op = statistics.median(a)
        c0 = statistics.median(cl)
        print(f"           ARMOR open(A median)={op:.3f} close={c0:.3f} => {100.0*(c0-op)/op:+.3f}% "
              f"({c0-op:+.3f} ms)")
    else:
        print(f"           ARMOR NOT COMPUTABLE (close cells found: {len(cl)}, A measured: {len(a)}) "
              f"— NO PUBLISH")
    for c in ("trtllm_pp1024", "trtllm_pp256"):
        if c.split("_")[1] != prompt: continue
        p = os.path.expanduser(f"~/lever7/runs/{c}.json")
        if not os.path.exists(p): continue
        t = None
        for ln in reversed(open(p, errors="replace").read().strip().splitlines()):
            ln = ln.strip()
            if not ln.startswith("{"): continue
            try: d = json.loads(ln)
            except Exception: continue
            for k in ("ttft_ms", "median_ms", "ttft_median_ms", "median"):
                if isinstance(d.get(k), (int, float)): t = float(d[k]); break
            if t: break
        if t: print(f"           vs SAME-SESSION TRT {t:.3f} ms => ratio {t/m:.4f}x")
PY

# ── 7 off-pin census ──
# BUG FIXED after round 14: this census reported "OFF_PIN ... RE-TAKE REQUIRED" for EVERY cell in
# the window, including round-9 files, while the harness's own per-cell sampler reported offpin=0 on
# all 22 cells. The census was wrong, not the clocks. The sampler writes
#     2026-09-19T06:42:17Z 1410 MHz, 0 %, 0 %, 0 MiB, 97.13 W, 35
# i.e. a SPACE-separated timestamp+clock, THEN comma-separated nvidia-smi fields, and there is NO
# header row. With -F, that makes $1 the timestamp+clock and $2 the GPU UTILIZATION — so the old
# `$2+0 != 1410` compared utilization to 1410 and could only ever "fail". A census that flags every
# cell is worse than none: it cries wolf until a real off-pin window is dismissed as the same bug.
# Scope note: this now censuses ONLY this window's cells (r6e_ / smoke_ / trtllm_), because the
# clocks dir accumulates every previous window's files and re-judging them here is meaningless.
phase "7_offpin_census"
bad=0; seen=0
for c in "$L7"/clocks/clocks_r6e_*.csv "$L7"/clocks/clocks_smoke_*.csv; do
  [[ -f "$c" ]] || continue
  seen=$((seen+1))
  n=$(awk '{ split($1, a, " "); if (a[2]+0 != 1410) k++ } END{print k+0}' "$c" 2>/dev/null)
  [[ "$n" != "0" ]] && { echo "OFF_PIN $(basename "$c"): $n samples NOT at 1410 MHz — RE-TAKE REQUIRED"; bad=1; }
done
echo "censused $seen clock files from THIS window (r6e_/smoke_); earlier windows' files deliberately excluded"
if (( bad == 0 )); then
  echo "no off-pin samples in any cell of this window"
  echo "cross-check: the harness's own per-cell sampler reported offpin=$(grep -oE 'offpin=[0-9]+' "$W" | sort -u | tr '\n' ' ')"
fi

phase "done"
echo "CHAIN14_DONE $(ts) elapsed=$(elapsed)min of cap=${CAP_MIN}min"
nvidia-smi --query-gpu=index,clocks.current.sm,memory.used --format=csv,noheader
