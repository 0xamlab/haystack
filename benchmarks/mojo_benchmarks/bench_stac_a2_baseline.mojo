"""bench_stac_a2_baseline.mojo — the STAC-A2 BASELINE problem size, unaudited.

NOT A STAC-A2 RESULT. An official STAC-A2 result requires an audit by the STAC Benchmark
Council and we have not had one. The specification, the R reference implementation and the STAC
Test Harness are Council-restricted and we do not have them. This is the workload STAC-A2
describes, reconstructed from publicly posted STAC Reports, measured here UNAUDITED and
INDEPENDENTLY IMPLEMENTED FROM THE PUBLIC SPECIFICATION. Do not quote any figure below under a
STAC-A2 metric name as though it were certified.

WHY THIS FILE IS SEPARATE FROM bench_stac_a2_workload.mojo
-----------------------------------------------------------
Correctness lives there and runs at sizes that fit in K separate processes. This file does ONE
thing: it runs the full Greeks set at the STAC BASELINE problem size — 5 assets, 25,000 paths,
252 timesteps — under the timing protocol the public STAC Reports describe:

    "The test is executed five times: one cold run and four warm runs; WARM is the fastest
     warm time."

One Greeks set at that size is 94 full path simulations of 31.5M asset-steps each, so five of
them is a substantial run and cannot be repeated across K processes in reasonable time. K = 1
here and the output says so. The K-process tier statistics are in the other file at a reduced
path count, clearly labelled as reduced.

WHAT IT PRINTS, AND WHAT IT MUST NOT BE READ AS
------------------------------------------------
It prints COLD, MEAN and WARM in the STAC sense, plus paths/sec and asset-steps/sec, plus a HOT
tier which is the house convention and is NOT a STAC tier.

Published, audited figures exist for this exact problem size and are printed alongside so the
gap is visible rather than implied. They are audited and ours is not, and one of them is from
2013 hardware, and both of those facts belong in the same sentence as the comparison. There is
no Ratio column against the 2020 DGX A100 report because that report publishes RATIOS ONLY and
never an absolute second, so a ratio against it would be a ratio against an unstated machine.

ZERO DISPATCH: not one runtime-dispatch call. See the verification grep in
bench_stac_a2_workload.mojo's docstring — match the token followed by an open paren, or the
grep matches the sentence that claims it.
"""

from std.time import perf_counter_ns
from std.math import sqrt, abs as fabs
from std.sys import info

from quantfin.heston import (
    HestonParams, heston_basket_greeks, heston_basket_price,
    heston_scheme_name, heston_contract_id,
    HESTON_SCHEME_QE, HESTON_OK,
)

comptime N_ASSETS: Int = 5
comptime RATE: Float64 = 0.03
comptime DIVY: Float64 = 0.05
comptime STRIKE: Float64 = 100.0
comptime TENOR: Float64 = 1.0
comptime BASE_STEPS: Int = 252
comptime BASE_PATHS: Int = 25000
comptime CROSS_CORR: Float64 = 0.4
comptime MASTER_SEED: UInt64 = 0x5A2C4A2


fn _assets() -> List[HestonParams]:
    var s0 = [100.0, 95.0, 105.0, 110.0, 90.0]
    var v0 = [0.04, 0.05, 0.03, 0.06, 0.045]
    var kp = [1.5, 2.0, 1.2, 2.5, 1.8]
    var xi = [0.35, 0.45, 0.30, 0.50, 0.40]
    var rh = [-0.7, -0.6, -0.5, -0.75, -0.65]
    var out = List[HestonParams]()
    for a in range(N_ASSETS):
        out.append(HestonParams(s0[a], v0[a], kp[a], v0[a], xi[a], rh[a], DIVY))
    return out^


fn _corr() -> List[List[Float64]]:
    var c = List[List[Float64]]()
    for i in range(N_ASSETS):
        var row = List[Float64]()
        for j in range(N_ASSETS):
            row.append(1.0 if i == j else CROSS_CORR)
        c.append(row^)
    return c^


fn _f(x: Float64, dp: Int) -> String:
    # nan and inf must print as themselves. Without this the Int() below saturates and a
    # broken run reports "922337203685477.5807", which a reader will read as a number.
    if x != x:
        return String("nan")
    if x > 1.0e300:
        return String("+inf")
    if x < -1.0e300:
        return String("-inf")
    var neg = x < 0.0
    var v = -x if neg else x
    var scale: Float64 = 1.0
    for _ in range(dp):
        scale *= 10.0
    var scaled = v * scale + 0.5
    var ip = Int(scaled)
    var whole = ip // Int(scale)
    var frac = ip - whole * Int(scale)
    var fs = String(frac)
    while len(fs) < dp:
        fs = "0" + fs
    var s = String(whole) + "." + fs if dp > 0 else String(whole)
    return ("-" + s) if neg else s


fn _lpad(s: String, n: Int) -> String:
    var out = s
    while len(out) < n:
        out = " " + out
    return out


fn _pad(s: String, n: Int) -> String:
    var out = s
    while len(out) < n:
        out += " "
    return out


def main() raises:
    var workers = info.num_physical_cores()
    print("")
    print("=== bench_stac_a2_baseline: the STAC-A2 BASELINE problem size ===")
    print("")
    print("UNAUDITED. INDEPENDENTLY IMPLEMENTED FROM THE PUBLIC SPECIFICATION. NOT a STAC-A2")
    print("result — an official one requires a STAC Benchmark Council audit and we have not had")
    print("one. STAC metric names below identify which published definition a row was modelled")
    print("on; they do not assert certification.")
    print("")
    print("problem .......... " + String(N_ASSETS) + " assets, " + String(BASE_PATHS)
          + " paths, " + String(BASE_STEPS) + " timesteps (the STAC baseline)")
    print("instrument ....... best-of-" + String(N_ASSETS)
          + " call, strike " + _f(STRIKE, 0) + ", 1y, daily early exercise")
    print("                   r = " + _f(RATE, 3) + ", q = " + _f(DIVY, 3)
          + " (q > r, so early exercise is economically live)")
    print("discretisation ... " + heston_scheme_name(HESTON_SCHEME_QE))
    print("early exercise ... Longstaff-Schwartz LSMC, degree-2 basis")
    print("greeks ........... finite differences on COMMON RANDOM NUMBERS")
    print("contract ......... " + heston_contract_id())
    print("dtype ............ Float64.  device: CPU, Apple M4 Max arm64, " + String(workers)
          + " physical cores.  DISPATCHES: 0")
    print("")

    var ps = _assets()
    var c = _corr()

    # One price first, so the answer is on the page next to the time it took. A timing with no
    # answer beside it is a benchmark of nothing.
    var t0 = perf_counter_ns()
    var one = heston_basket_price(
        ps, c, STRIKE, RATE, TENOR, BASE_PATHS, BASE_STEPS, MASTER_SEED, 21,
        HESTON_SCHEME_QE, True, 2, workers,
    )
    var t1 = perf_counter_ns()
    if one.status != HESTON_OK:
        print("refused, status " + String(one.status))
        raise Error("bench_stac_a2_baseline: path generation refused")
    print("THE ANSWER (one price, so the timings below have something attached to them)")
    print("   best-of-5 Bermudan price ......... " + _f(one.price, 4)
          + "   +/- " + _f(one.std_error, 4) + " (1 s.e., empirical)")
    print("   European value, same paths ....... " + _f(one.european_value, 4))
    print("   early exercise premium ........... " + _f(one.early_exercise_premium, 4)
          + "   on " + String(one.n_exercised) + " exercise decisions")
    print("   QE negative variances ............ " + String(one.n_negative_variance)
          + "   (must be 0)")
    print("   martingale-correction fallbacks .. " + String(one.martingale_fallbacks))
    print("   single-price wall time ........... " + _f(Float64(t1 - t0) / 1.0e6, 1) + " ms")
    print("")

    var fails = 0
    if one.n_negative_variance != 0:
        print("   GATE FAIL: QE produced a negative variance. The scheme cannot; the code did.")
        fails += 1
    if one.early_exercise_premium < 0.0:
        print("   GATE FAIL: negative early-exercise premium. An American option is worth at")
        print("   least its European counterpart, so the LSM regression has collapsed.")
        fails += 1

    # STAC's protocol: five executions, one cold and four warm, WARM = fastest warm.
    print("TIMING — the full Greeks set, STAC's 1-cold-4-warm protocol")
    print("   THETA, RHO, DELTA, GAMMA, CROSS-GAMMA, MODEL VEGA (KAPPA / MV_THETA / KHI / V0)")
    print("   and CORRELATION VEGA, all from CRN-paired finite differences.")
    print("")
    var runs = List[Float64]()
    var n_prices = 0
    var greeks_price = 0.0
    var d0 = 0.0
    var g0 = 0.0
    for i in range(5):
        var a0 = perf_counter_ns()
        var g = heston_basket_greeks(
            ps, c, STRIKE, RATE, TENOR, BASE_PATHS, BASE_STEPS, MASTER_SEED, 21,
            HESTON_SCHEME_QE, True, 2, workers,
        )
        var a1 = perf_counter_ns()
        if g.status != HESTON_OK:
            print("refused, status " + String(g.status))
            raise Error("bench_stac_a2_baseline: greeks refused")
        runs.append(Float64(a1 - a0) / 1.0e6)
        n_prices = g.n_prices
        greeks_price = g.price
        d0 = g.delta[0]
        g0 = g.gamma[0]
        print("   run " + String(i) + ("  (COLD)" if i == 0 else "  (warm)") + " ... "
              + _f(Float64(a1 - a0) / 1.0e6, 1) + " ms")

    var cold = runs[0]
    var warm = 1.0e308
    var wmax = 0.0
    var wsum = 0.0
    for i in range(1, 5):
        if runs[i] < warm:
            warm = runs[i]
        if runs[i] > wmax:
            wmax = runs[i]
        wsum += runs[i]
    var mean = (cold + wsum) / 5.0
    var spread = wmax / warm if warm > 0.0 else 0.0

    var asset_steps = Float64(BASE_PATHS) * Float64(BASE_STEPS) * Float64(N_ASSETS)
    var per_set = asset_steps * Float64(n_prices)

    print("")
    print("   prices per Greeks set ........ " + String(n_prices))
    print("   asset-steps per Greeks set ... " + _f(per_set / 1.0e6, 0) + " M")
    print("   DISPATCHES ................... 0")
    print("")
    print("   tier                    seconds   paths/sec (set)   asset-steps/sec   dtype  threads  device")
    print("   ----------------------  --------  ----------------  ----------------  -----  -------  --------------")
    var nms = ["COLD (1st in process) ", "MEAN (all five)       ", "WARM (fastest warm)   "]
    var vals = [cold, mean, warm]
    for i in range(3):
        var ms = vals[i]
        var pps = Float64(BASE_PATHS) * Float64(n_prices) / (ms / 1000.0)
        var aps = per_set / (ms / 1000.0)
        print(
            "   " + nms[i] + "  " + _lpad(_f(ms / 1000.0, 3), 8) + "  " + _lpad(_f(pps, 0), 16)
            + "  " + _lpad(_f(aps / 1.0e6, 2) + " M", 16)
            + "  fp64   " + _lpad(String(workers), 7) + "  M4 Max arm64"
        )
    print("")
    print("   warm dispersion max/min ... " + _f(spread, 2))
    if spread > 3.0:
        print("   INVALID — the four warm runs disagree by more than 3x, so they are measuring")
        print("   the machine and not the code. No cold/warm ratio is printed. Re-run quiet.")
        fails += 1
    else:
        print("   cold/warm ratio ........... " + _f(cold / warm, 2) + "x")
    print("")
    print("   greeks from the last set:  price " + _f(greeks_price, 4)
          + "   delta_0 " + _f(d0, 5) + "   gamma_0 " + _f(g0, 6))
    print("")
    print("PUBLISHED, AUDITED FIGURES FOR THIS PROBLEM SIZE — read the caveats, they are not")
    print("decoration. Ours is unaudited; theirs is audited. One is 2013 hardware.")
    print("")
    print("   SUT             hardware                              cold s   warm s   source")
    print("   --------------  ------------------------------------  -------  -------  ------------------")
    print("   NVDA131118      IBM iDataPlex dx360 M4, 2x Tesla       1.258    0.648   STAC Report (c)2013")
    print("                   K20Xm. HOST CPU MODEL NOT STATED                        nvidia.com PDF")
    print("                   in the public report.")
    print("   INTC260430      HPE ProLiant XD230, 2x Xeon 6980P      0.033    n/a     STAC, audited")
    print("                   (256 cores), 1.5 TB MRDIMM @8800.                       2026-05-05; warm")
    print("                   Liquid-cooled.                                          NOT public.")
    print("   NVDA200909      NVIDIA DGX A100, 8x A100 SXM 40 GiB    n/a      n/a     RATIOS ONLY on the")
    print("                                                                           public page; no")
    print("                                                                           absolute seconds,")
    print("                                                                           and the machines it")
    print("                                                                           is a ratio AGAINST")
    print("                                                                           are unstated.")
    print("")
    print("   Ratio column, ours vs theirs, computed only where an absolute figure is published:")
    print("")
    print("   comparison                                    ours s   theirs s   Ratio (ours/theirs)")
    print("   --------------------------------------------  -------  ---------  -------------------")
    print("   WARM vs NVDA131118 (2013, 2x K20Xm, audited)  "
          + _lpad(_f(warm / 1000.0, 3), 7) + "  " + _lpad("0.648", 9) + "  "
          + _lpad(_f(warm / 1000.0 / 0.648, 1) + "x slower", 19))
    print("   COLD vs NVDA131118 (2013, 2x K20Xm, audited)  "
          + _lpad(_f(cold / 1000.0, 3), 7) + "  " + _lpad("1.258", 9) + "  "
          + _lpad(_f(cold / 1000.0 / 1.258, 1) + "x slower", 19))
    print("   COLD vs INTC260430 (2026, 2x Xeon 6980P,      "
          + _lpad(_f(cold / 1000.0, 3), 7) + "  " + _lpad("0.033", 9) + "  "
          + _lpad(_f(cold / 1000.0 / 0.033, 1) + "x slower", 19))
    print("        audited)")
    print("")
    print("   WE LOSE, AND BY A LOT. Say it plainly rather than burying it: this implementation")
    print("   is orders of magnitude slower than both audited results, including one taken on")
    print("   2013 GPU hardware. The reasons are structural and are not a mystery:")
    print("     * scalar fp64 throughout — no SIMD across the asset or path axis, and the")
    print("       Box-Muller log/cos pair plus the QE sqrt chain are ~10 transcendentals per")
    print("       asset-step, all scalar;")
    print("     * CPU only, against two GPU submissions and a 256-core dual-socket Xeon;")
    print("     * 94 full path regenerations per Greeks set. Spot bumps are the exception —")
    print("       a spot bump only SHIFTS the log-price by log(1+h) under the same draws, so 30")
    print("       of the 94 could be derived from the base path set rather than re-simulated.")
    print("       That optimisation is NOT taken here, so the figure above is conservative;")
    print("     * the audited submissions run vendor Packs (Intel oneAPI Rev R, CUDA 5.5 with")
    print("       cuRAND/cuBLAS/CUB) tuned against the real spec and harness, which we do not")
    print("       have.")
    print("   Cross-revision warning, which also applies to any trend a reader tries to draw:")
    print("   the 2013 K20Xm report is spec revision b2 and the 2026 Xeon report is Pack Rev R.")
    print("   They are not comparable to each other, let alone jointly to us.")
    print("")
    print("K = 1. This file takes ONE cold reading, in ONE process, because five Greeks sets at")
    print("the baseline size is already a long run. A cold figure needs its K stated and this")
    print("one's K is 1. The K-process tier statistics are in bench_stac_a2_workload.mojo at a")
    print("reduced path count, and that file says so on its own face.")
    print("")
    print("CONTEXT REQUIRED: a Mojo process cannot read the system load average. Capture")
    print("`uptime` immediately before and after and quote it beside every figure above.")
    print("")
    print("-- cold / warm / hot, ms per full Greeks set at the STAC baseline size --")
    print("  A stac-a2 baseline greeks ..... " + _f(cold, 1) + " / " + _f(warm, 1)
          + " / " + _f(warm, 1) + "   cold/hot " + _f(cold / warm, 2))
    print(
        "COLD_WARM_HOT stac_a2_greeks_baseline_25000paths " + _f(cold, 1) + " " + _f(warm, 1)
        + " " + _f(warm, 1) + " ms"
    )
    print("")
    print("REMINDER: every figure above is UNAUDITED and independently implemented from the")
    print("public STAC-A2 specification. It is not a STAC-A2 result.")
    if fails == 0:
        print("BENCH_GATE stac_a2_baseline PASS")
    else:
        print("BENCH_GATE stac_a2_baseline FAIL " + String(fails))
        raise Error("bench_stac_a2_baseline: " + String(fails) + " gate failure(s)")
