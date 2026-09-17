#!/bin/bash
# chain7probe.sh — ROUND 7 PHASE 0 (probe-only, the go/no-go gate). Nothing in this script
# touches the production dispatch, builds an arm, runs an oracle gate or times a cell: it exists
# to answer ONE question before any of that budget is spent — does feeding two m16 row-tiles from
# each B-fragment load (v3, RT=2) beat round 6's v2, and if so does GQA-packing or FA_BM=128 win?
#
# ORDER IS DELIBERATE. This campaign's probes have over-forecast 3/3 times, so the cheapest
# refutation runs first:
#   1. clocks pinned 1410 and VERIFIED (zero off-pin tolerance) — a probe taken off-pin is not
#      a probe, and the decision table drives a commit decision.
#   2. build the shim with `-Xptxas -v` and READ THE REGISTER/SPILL CENSUS. v3 at RT=2 needs
#      ~224 registers against a 255 ceiling; if it spills, the lever is dead on arrival and the
#      script stops here without spending a single timing iteration.
#   3. fa_g3_probe correctness: every shape x every (kv32,dbuf,of16) x (RT,GQA) arm against the
#      host double-precision windowed reference, AND v3 held to BIT identity against v2 (v3
#      changes no rounding point, so tolerance would be a weaker claim than the code can make).
#      Plus the [1d] rejection arms: a declined lever must never masquerade as an accepted one.
#   4. fa_g3_probe's [4] decision table at the production mapping, BN 32 and 64.
#
# HEARTBEAT: the top-level idle audit stops any GPU VM with no cell activity, and a probe phase
# produces no cells. So this script appends to ~/lever7/heartbeat.log every 60 s for its whole
# duration; the audit treats heartbeat freshness < 25 min as legitimate activity.
#
# Usage (on trtllm-gemma-us-west1-c):  bash chain7probe.sh
set -uo pipefail
SRC=${SRC:-$HOME/g3r7}
NR=$SRC/benchmarks/llm_smoke/nvidia_race
L7=${L7:-$HOME/lever7}
L3=${L3:-$HOME/lever3}
GPU=${GPU:-1}
SM=${SM:-sm_90}
CUDA_HOME=${CUDA_HOME:-/usr/local/cuda}
TC_OBJ=${TC_OBJ:-/tmp/g3r7tc/tc_shim.o}
ITERS=${ITERS:-30}
LOG=${LOG:-$L7/chain7probe.log}
mkdir -p "$L7/logs" "$L7/runs" "$L7/clocks" "$(dirname "$TC_OBJ")"
exec > >(tee -a "$LOG") 2>&1
ts() { date -u +%FT%TZ; }

# ── heartbeat emitter: one line a minute, phase-tagged, killed when this script exits ──
HB=$L7/heartbeat.log
PHASE="starting"
( while true; do echo "$(date -u +%FT%TZ) chain7probe GPU=$GPU phase=$PHASE pid=$$" >> "$HB";
    sleep 60; done ) &
HB_PID=$!
trap 'kill $HB_PID 2>/dev/null' EXIT
setphase() { PHASE="$1"; echo "=== [$(ts)] PHASE: $1 ==="; }

export CUDA_VISIBLE_DEVICES=$GPU

setphase "clock_pin"
sudo -n nvidia-smi -pm 1 >/dev/null 2>&1
sudo -n nvidia-smi -lgc 1410,1410 >/dev/null 2>&1
nvidia-smi --query-gpu=index,clocks.current.sm,clocks.max.sm --format=csv,noheader
PIN=$(nvidia-smi -i "$GPU" --query-gpu=clocks.current.sm --format=csv,noheader,nounits)
echo "GPU$GPU clocks.current.sm=$PIN (want 1410)"
if [[ "$PIN" != "1410" ]]; then
  echo "OFF_PIN_AT_START: $PIN != 1410 — refusing to probe; re-pin and re-run"
  exit 1
fi

setphase "build_shim_with_regcensus"
PTXD="$(dirname "$TC_OBJ")" SM="$SM" CUDA_HOME="$CUDA_HOME" NR="$NR" REGLOG="$L7/logs/ptxas_v.log" \
  bash "$NR/build_shim_gemma3_round7.sh"
rc=$?
if (( rc != 0 )) || [[ ! -f "$TC_OBJ" ]]; then
  echo "BUILD_FAIL rc=$rc — no probe, no decision"; exit 1
fi
echo "tc_shim.o bytes=$(stat -c %s "$TC_OBJ")"

# ── EARLY EXIT on the register census: RT=2 that spills is dead on arrival ──
setphase "reg_census_verdict"
CEN=$L7/logs/ptxas_v.log
python3 - "$CEN" <<'PY'
import re, sys
txt = open(sys.argv[1], errors="replace").read()
# ptxas -v emits "Compiling entry function '<mangled>' for 'sm_90'" then "Used N registers, ...
# M bytes spill stores". Mangled template args are not parsed positionally (fragile across nvcc
# versions); the census is reported over ALL v3 instantiations and the peak, which is the
# quantity the go/no-go actually rides on.
ents = re.split(r"Compiling entry function ", txt)
rows = []
for e in ents[1:]:
    if "_fa_g3_window3_kernel" not in e:
        continue
    name = e.split("'")[1] if "'" in e else "?"
    r = re.search(r"Used (\d+) registers", e)
    s = re.search(r"(\d+) bytes spill stores", e)
    rows.append((name, int(r.group(1)) if r else -1, int(s.group(1)) if s else 0))
if not rows:
    print("VERDICT: INCONCLUSIVE — no v3 entries in the ptxas log at all, so the build did not "
          "emit them. Treat as NO-GO until explained, NOT as a pass.")
    sys.exit(2)
sp = [x for x in rows if x[2] > 0]
peak = max(x[1] for x in rows)
print(f"v3 instantiations: {len(rows)}; peak registers {peak}/255; with non-zero spill: {len(sp)}")
for n, r, s in sorted(sp, key=lambda x: -x[2])[:12]:
    print(f"  SPILLS {s} B  regs={r}  ...{n[-88:]}")
if sp:
    print("VERDICT: v3 SPILLS to local memory. Per the round-7 plan that is DEAD ON ARRIVAL — "
          "halving the shared-load stream cannot pay for local-memory traffic, and the RT=2 "
          "arms are the ones that cost the registers. No timing is worth taking.")
    sys.exit(3)
print("VERDICT: no spills. PROCEED to correctness + the [4] decision table.")
sys.exit(0)
PY
CEN_RC=$?
if (( CEN_RC == 3 )); then
  echo "STOPPING: the register census refutes RT=2 before any timing was taken."
  echo "Round 7 falls back to the rope + norm-accum compensation levers."
  exit 0
fi
if (( CEN_RC == 2 )); then
  echo "STOPPING: the census is inconclusive (no v3 entries). Investigate before spending GPU time."
  exit 1
fi

setphase "build_probe"
"$CUDA_HOME/bin/nvcc" -O3 -arch="$SM" "$NR/fa_g3_probe.cu" "$TC_OBJ" \
  -lcublas -lcudart -o /tmp/fa_g3_probe > "$L7/logs/probe_build.log" 2>&1
rc=$?
if (( rc != 0 )) || [[ ! -x /tmp/fa_g3_probe ]]; then
  echo "PROBE_BUILD_FAIL rc=$rc"; tail -40 "$L7/logs/probe_build.log"; exit 1
fi
echo "probe built: $(stat -c %s /tmp/fa_g3_probe) bytes"

for BN in 64 32; do
  setphase "probe_bn$BN"
  /tmp/fa_g3_probe --iters "$ITERS" --bn "$BN" > "$L7/logs/fa_g3_probe_bn$BN.log" 2>&1
  rc=$?
  nf=$(grep -c ' FAIL' "$L7/logs/fa_g3_probe_bn$BN.log")
  nb=$(grep -c 'BITIDENT-v2' "$L7/logs/fa_g3_probe_bn$BN.log")
  nd=$(grep -c 'BITDIFF' "$L7/logs/fa_g3_probe_bn$BN.log")
  echo "probe bn=$BN rc=$rc FAIL=$nf BITIDENT_v2=$nb BITDIFF=$nd"
  sed -n '/\[1d\]/,$p' "$L7/logs/fa_g3_probe_bn$BN.log" | grep -v '^pp256\|^pp1024\|^rag\|^odd' | head -20
  echo "--- [4] decision table (bn=$BN run) ---"
  sed -n '/\[4\] ROUND-7/,$p' "$L7/logs/fa_g3_probe_bn$BN.log"
  PIN2=$(nvidia-smi -i "$GPU" --query-gpu=clocks.current.sm --format=csv,noheader,nounits)
  echo "clocks after bn=$BN probe: $PIN2 (want 1410)"
  [[ "$PIN2" != "1410" ]] && echo "OFF_PIN_AFTER_PROBE bn=$BN: $PIN2 — the table above is INVALID"
done

setphase "done"
echo "=== [$(ts)] chain7probe DONE — read the [4] tables above; GQA2/BM128 dev vs v2 is the "
echo "    go/no-go. A win must exceed the RT1 control's own deviation from v2, else it is noise. ==="
