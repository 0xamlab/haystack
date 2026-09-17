#!/usr/bin/env bash
# run_throttle_probe7.sh — is the uniform +8.5% isolated->in-situ cublas penalty the 400 W cap?
#
# WHAT IT SETTLES. FRONT 7's in-situ algorithm search measured the same four projection shapes two
# ways with the SAME cudaEvent mechanism: once in the stage-time isolated loop FRONT 6 shipped, and
# once in their real slot in the layer chain. Every one of the 29 (shape, candidate) pairs came out
# in situ = isolated x 1.085 +- 0.02, the winner was identical for all four shapes, and the ordering
# of the whole candidate list was preserved. A near-constant MULTIPLICATIVE factor across shapes
# spanning 425 us to 7073 us is not an algorithm property and not a memory-state property of one
# role; it is something every GEMM pays. Two candidates were left:
#   (a) the power cap acting through stall insertion rather than a clock-domain change. FRONT 6 saw
#       draws to 532.9 W against a 400.00 W limit and off-pin samples to 1230 MHz, and this round's
#       200 ms sampler saw a 476.0 W draw with 2.51% of samples off-pin -- but 97.5% AT the pin, so
#       the clock DOMAIN accounts for ~0.25% and cannot be the whole 8.5%;
#   (b) the isolated loop's own state: it re-runs one shape back-to-back on the same buffers, so its
#       weights, its A operand and (for the beta=1 roles) its C operand are all warm from the
#       previous identical iteration, and its operands are whatever the stage-time buffers held
#       rather than live activations.
# `clocks.sm` cannot separate those, because a power-cap stall does not move the reported clock
# domain. The throttle-REASON bits can, so this samples them at 100 ms across two loads:
#   phase A  a sustained RAG-4096 prefill loop  (in situ: the engine's real chain)
#   phase B  gemm_probe's isolated GEMM loop    (the stage-time harness's own pattern)
# and reports, per phase, the fraction of busy samples with SW Power Cap asserted, plus the clock
# and power distributions. If A asserts the cap and B does not, (a) is the mechanism and the
# conclusion is that the remaining GEMM headroom is POWER-limited, so no algorithm search can
# reach it and only an energy reduction can. If neither asserts it, (a) is refuted and (b) stands
# as the explanation, with the +8.5% bounded as a property of the isolated harness rather than of
# the engine.
#
# usage: bash run_throttle_probe7.sh [arm-suffix]
set -uo pipefail
ARM=${1:-_h1}
MEAS=${MEAS:-$HOME/trtllm/front7}
BIN=${BIN:-$HOME/front7/bin/qwen25_7b_p3_graph_cuda${ARM}}
PROBE=${PROBE:-$HOME/front6/bin/gemm_probe}
OUTD="$MEAS/throttle"; mkdir -p "$OUTD"

# the reason-bit field names moved between driver branches; probe for the ones this driver has
REASONS=""
for f in clocks_event_reasons.active clocks_event_reasons.sw_power_cap \
         clocks_event_reasons.hw_slowdown clocks_event_reasons.hw_thermal_slowdown; do
    if nvidia-smi --query-gpu="$f" --format=csv,noheader >/dev/null 2>&1; then
        REASONS="${REASONS:+$REASONS,}$f"
    fi
done
if [[ -z "$REASONS" ]]; then
    for f in clocks_throttle_reasons.active clocks_throttle_reasons.sw_power_cap \
             clocks_throttle_reasons.hw_slowdown clocks_throttle_reasons.hw_thermal_slowdown; do
        if nvidia-smi --query-gpu="$f" --format=csv,noheader >/dev/null 2>&1; then
            REASONS="${REASONS:+$REASONS,}$f"
        fi
    done
fi
echo "throttle-reason fields this driver exposes: ${REASONS:-NONE (falling back to clocks+power)}"
BASE="timestamp,clocks.sm,power.draw,temperature.gpu,utilization.gpu"
FIELDS="${REASONS:+$BASE,$REASONS}"
FIELDS=${FIELDS:-$BASE}

IDS0=$(python3 -c "
import json;p=json.load(open('/home/angel/trtllm/prompts.json'))
print(','.join(str(int(t)) for t in p['rag'][0]['ids']))")
ORACLE=$(python3 -c "
import json;d=json.load(open('/tmp/w7b/gate/ref_tokens_rag.json'))
print(','.join(str(int(t)) for t in d['rag_0']['generated_ids'][:16]))")

sample() { # label
    nvidia-smi --query-gpu="$FIELDS" --format=csv -lms 100 > "$OUTD/$1.csv" 2>&1 &
    SP=$!
    echo "  sampling $1 at 100 ms (pid $SP)"
}

wait_free() {
    for _ in $(seq 1 200); do
        [ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)" ] && return 0
        sleep 2
    done
}

echo "############ phase A — IN SITU: a sustained RAG-4096 prefill loop ($ARM) ############"
wait_free
nvidia-smi --query-gpu=clocks.sm,power.draw,power.limit,temperature.gpu --format=csv,noheader
sample A_insitu
"$BIN" --checkpoint /tmp/w7b/ckpt --arm p3 --prompt-ids "$IDS0" --oracle "$ORACLE" \
    --warmup 1 --runs 20 --out "$OUTD/A_insitu.txt" > "$OUTD/A_insitu.log" 2>&1
echo "  rc=$? ; cell line:"; grep -E "^prefill4096" "$OUTD/A_insitu.log" | head -2
kill $SP 2>/dev/null; wait $SP 2>/dev/null
sleep 20      # let the GPU return to idle so phase B starts from the same thermal state

echo "############ phase B — ISOLATED: gemm_probe's back-to-back GEMM loop ############"
if [[ -x "$PROBE" ]]; then
    wait_free
    nvidia-smi --query-gpu=clocks.sm,power.draw,temperature.gpu --format=csv,noheader
    sample B_isolated
    # Five passes, not one: a single gemm_probe run is ~7 s, which at 100 ms sampling leaves
    # single-digit working samples -- the defect that made the first run's phase B
    # inconclusive rather than informative.
    for pass_i in 1 2 3 4 5; do
        "$PROBE" --iters 20 --warmup 5 >> "$OUTD/B_isolated.log" 2>&1
    done
    echo "  rc=$? (5 passes)"
    kill $SP 2>/dev/null; wait $SP 2>/dev/null
else
    echo "  SKIP: $PROBE not found (FRONT 6's probe binary); phase A only"
    kill $SP 2>/dev/null; wait $SP 2>/dev/null
fi

python3 - "$OUTD" <<'PYEOF'
import csv, glob, os, statistics, sys
outd = sys.argv[1]
MIN_SAMPLES = 30      # below this a percentage is noise; say so instead of printing one
print("\n%-12s %5s %5s %22s %12s %8s %7s %6s"
      % ("phase", "rows", "work", "clock min/med/max", "W med/max", "offpin%", "swCap%", "C max"))
verdicts = {}
for path in sorted(glob.glob(os.path.join(outd, "?_*.csv"))):
    base = os.path.basename(path)[:-4]
    rows = list(csv.DictReader(open(path)))
    if not rows:
        print("%-12s NO ROWS" % base)
        continue
    keys = list(rows[0].keys())

    # substring match, NOT endswith: this driver answers a --query-gpu=clocks.sm request with a
    # column headed "clocks.current.sm [MHz]". The first version of this analyzer matched on the
    # REQUESTED name, found nothing, and printed nan under every column while still printing a
    # confident-looking table and a confident-looking conclusion.
    def find(*subs):
        for sub in subs:
            for k in keys:
                if sub in k.lower():
                    return k
        return None

    kclk = find("clocks.current.sm", "clocks.sm")
    kpwr, kut, ktmp = find("power.draw"), find("utilization.gpu"), find("temperature.gpu")
    kcap, khw, kth = find("sw_power_cap"), find("hw_slowdown"), find("hw_thermal")

    def txt(r, k):
        return (r.get(k) or "").strip() if k else ""

    def num(r, k):
        try:
            return float(txt(r, k).split()[0].replace(",", ""))
        except (ValueError, IndexError):
            return float("nan")

    # "working" = GEMM-scale work, discriminated by POWER DRAW as well as utilization: utilization
    # is the share of the sample period with ANY kernel resident, so it reads 100% for a
    # memory-bound gap as readily as for a tensor-core GEMM, and filtering on it alone left the
    # first run's phase B with 8 qualifying samples out of 71 -- too few to percentage.
    work = [r for r in rows if num(r, kpwr) >= 150.0 and num(r, kut) >= 50.0]
    if len(work) < MIN_SAMPLES:
        print("%-12s %5d %5d  INSUFFICIENT SAMPLES (< %d working) -- no percentage reported for "
              "this phase, because a share computed from %d samples is not a measurement"
              % (base, len(rows), len(work), MIN_SAMPLES, len(work)))
        verdicts[base] = None
        continue
    n = len(work)
    cl = sorted(num(r, kclk) for r in work)
    pw = sorted(num(r, kpwr) for r in work)
    offp = sum(1 for c in cl if c < 1409.5)
    cap = sum(1 for r in work if txt(r, kcap).lower() == "active")
    hw = sum(1 for r in work if txt(r, khw).lower() == "active")
    th = sum(1 for r in work if txt(r, kth).lower() == "active")
    verdicts[base] = (100.0 * cap / n, 100.0 * offp / n, statistics.median(cl))
    extra = ("  hw_slowdown=%d hw_thermal=%d" % (hw, th)) if (hw or th) else ""
    print("%-12s %5d %5d %7.0f/%6.0f/%-7.0f %6.1f/%-6.1f %8.2f %7.2f %6.0f%s"
          % (base, len(rows), n, cl[0], statistics.median(cl), cl[-1],
             statistics.median(pw), pw[-1], 100.0 * offp / n, 100.0 * cap / n,
             max(num(r, ktmp) for r in work), extra))

a, b = verdicts.get("A_insitu"), verdicts.get("B_isolated")
print()
if a and b:
    print("reading: SW-power-cap assertion %.2f%% IN SITU vs %.2f%% ISOLATED; off-pin %.2f%% vs "
          "%.2f%%; median clock %.0f vs %.0f MHz." % (a[0], b[0], a[1], b[1], a[2], b[2]))
    if a[0] > b[0] + 10.0:
        print("=> the cap asserts materially MORE in situ: the uniform +8.5% is consistent with "
              "power-cap stall insertion, so the remaining GEMM headroom is POWER-limited and no "
              "algorithm search reaches it -- only an energy reduction does.")
    elif abs(a[0] - b[0]) <= 10.0:
        print("=> the cap asserts at a SIMILAR rate in both phases, so it does not differentiate "
              "them and is not the +8.5%. What remains is the isolated harness's own warm state: "
              "one shape re-run back-to-back on the same buffers, so its weights, its A operand "
              "and (for beta=1) its C operand are warm from the previous identical iteration, and "
              "its operands are stale stage-time contents rather than live activations.")
    else:
        print("=> the cap asserts MORE in the isolated phase; the +8.5% is not a power effect.")
else:
    print("reading: INCONCLUSIVE -- at least one phase did not reach %d working samples. Lengthen "
          "that phase before attributing the +8.5%% to anything: an inconclusive probe is reported "
          "as inconclusive, not read as evidence for either mechanism." % MIN_SAMPLES)
PYEOF
nvidia-smi --query-gpu=clocks.sm,temperature.gpu,memory.used --format=csv,noheader
echo THROTTLE_PROBE7_DONE
