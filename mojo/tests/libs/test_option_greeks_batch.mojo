"""tests for option_greeks_batch — parity vs scalar option_pricing, parity
identities, degenerate lanes, SIMD/tail boundary, and a throughput print."""
from std.time import perf_counter_ns

from option_greeks_batch import chain_greeks
from option_pricing import (
    black_scholes_call,
    black_scholes_put,
    delta_call,
    gamma,
    vega,
    theta_call,
)
from std.math import abs as fabs, exp


def close(a: Float64, b: Float64, tol: Float64) -> Bool:
    return fabs(a - b) <= tol


def main() raises:
    var passed = 0
    var failed = 0

    # -- parity vs scalar functions on a hostile grid (calls) -----------------
    var spots = List[Float64]()
    var strikes = List[Float64]()
    var times = List[Float64]()
    var rates = List[Float64]()
    var sigmas = List[Float64]()
    var is_calls = List[Float64]()
    var grid_S = List[Float64]()
    grid_S.append(100.0); grid_S.append(736.5); grid_S.append(0.5); grid_S.append(4200.0)
    var grid_K = List[Float64]()
    grid_K.append(100.0); grid_K.append(700.0); grid_K.append(1.0); grid_K.append(4000.0)
    var grid_T = List[Float64]()
    grid_T.append(0.25); grid_T.append(0.0009920634920634921); grid_T.append(2.0)
    var grid_sig = List[Float64]()
    grid_sig.append(0.2); grid_sig.append(0.05); grid_sig.append(1.5)
    for si in range(len(grid_S)):
        for ki in range(len(grid_K)):
            for ti in range(len(grid_T)):
                for vi in range(len(grid_sig)):
                    spots.append(grid_S[si])
                    strikes.append(grid_K[ki])
                    times.append(grid_T[ti])
                    rates.append(0.05)
                    sigmas.append(grid_sig[vi])
                    is_calls.append(1.0)
    var n_calls = len(spots)
    # append the same grid as PUTS
    for j in range(n_calls):
        spots.append(spots[j])
        strikes.append(strikes[j])
        times.append(times[j])
        rates.append(rates[j])
        sigmas.append(sigmas[j])
        is_calls.append(0.0)

    var res = chain_greeks(spots, strikes, times, rates, sigmas, is_calls)

    var ok_price = True
    var ok_delta = True
    var ok_gamma = True
    var ok_vega = True
    var ok_theta = True
    for j in range(n_calls):
        var S = spots[j]
        var K = strikes[j]
        var T = times[j]
        var r = rates[j]
        var sig = sigmas[j]
        if not close(res.price[j], black_scholes_call(S, K, T, r, sig), 1e-9):
            ok_price = False
        if not close(res.delta[j], delta_call(S, K, T, r, sig), 1e-9):
            ok_delta = False
        if not close(res.gamma[j], gamma(S, K, T, r, sig), 1e-9):
            ok_gamma = False
        if not close(res.vega[j], vega(S, K, T, r, sig), 1e-9):
            ok_vega = False
        if not close(res.theta[j], theta_call(S, K, T, r, sig), 1e-9):
            ok_theta = False
    if ok_price and ok_delta and ok_gamma and ok_vega and ok_theta:
        print("  ✅ option_greeks_batch::call parity vs scalar (", n_calls, "cells, 1e-9 )")
        passed += 1
    else:
        print("  ❌ call parity", ok_price, ok_delta, ok_gamma, ok_vega, ok_theta)
        failed += 1

    # -- put price parity vs scalar + delta/theta parity identities ----------
    var ok_put = True
    var ok_pd = True
    var ok_pt = True
    for j in range(n_calls):
        var b = n_calls + j
        var S = spots[j]
        var K = strikes[j]
        var T = times[j]
        var r = rates[j]
        var sig = sigmas[j]
        if not close(res.price[b], black_scholes_put(S, K, T, r, sig), 1e-9):
            ok_put = False
        if not close(res.delta[b], delta_call(S, K, T, r, sig) - 1.0, 1e-9):
            ok_pd = False
        var theta_p = theta_call(S, K, T, r, sig) + r * K * exp(-r * T)
        if not close(res.theta[b], theta_p, 1e-9):
            ok_pt = False
        if not close(res.gamma[b], res.gamma[j], 0.0):
            ok_put = False  # gamma identical for call/put
        if not close(res.vega[b], res.vega[j], 0.0):
            ok_put = False  # vega identical for call/put
    if ok_put and ok_pd and ok_pt:
        print("  ✅ option_greeks_batch::put parity (price vs scalar, delta-1, theta+rKe^-rT, gamma/vega shared)")
        passed += 1
    else:
        print("  ❌ put parity", ok_put, ok_pd, ok_pt)
        failed += 1

    # -- degenerate lanes: T<=0 / sigma<=0 -> discounted intrinsic, zero greeks
    var dS = List[Float64]()
    var dK = List[Float64]()
    var dT = List[Float64]()
    var dR = List[Float64]()
    var dV = List[Float64]()
    var dC = List[Float64]()
    dS.append(110.0); dK.append(100.0); dT.append(0.0); dR.append(0.05); dV.append(0.2); dC.append(1.0)
    dS.append(90.0); dK.append(100.0); dT.append(0.5); dR.append(0.05); dV.append(0.0); dC.append(0.0)
    dS.append(90.0); dK.append(100.0); dT.append(-1.0); dR.append(0.05); dV.append(0.2); dC.append(1.0)
    var dres = chain_greeks(dS, dK, dT, dR, dV, dC)
    var exp_put_intr = 100.0 * exp(-0.05 * 0.5) - 90.0
    if (
        close(dres.price[0], 10.0, 1e-12)
        and close(dres.price[1], exp_put_intr, 1e-12)
        and close(dres.price[2], 0.0, 1e-12)
        and dres.delta[0] == 0.0 and dres.gamma[1] == 0.0 and dres.theta[2] == 0.0
    ):
        print("  ✅ option_greeks_batch::degenerate lanes -> discounted intrinsic, zero greeks")
        passed += 1
    else:
        print("  ❌ degenerate lanes", dres.price[0], dres.price[1], dres.price[2])
        failed += 1

    # -- SIMD/tail boundary: odd n must equal per-element batch of 1 ----------
    var ok_tail = True
    for probe_n in range(1, 12):
        var pS = List[Float64]()
        var pK = List[Float64]()
        var pT = List[Float64]()
        var pR = List[Float64]()
        var pV = List[Float64]()
        var pC = List[Float64]()
        for j in range(probe_n):
            pS.append(100.0 + Float64(j) * 7.3)
            pK.append(95.0 + Float64(j) * 6.1)
            pT.append(0.1 + Float64(j) * 0.07)
            pR.append(0.03)
            pV.append(0.15 + Float64(j) * 0.05)
            pC.append(1.0 if j % 2 == 0 else 0.0)
        var pr = chain_greeks(pS, pK, pT, pR, pV, pC)
        for j in range(probe_n):
            var one_S = List[Float64](); one_S.append(pS[j])
            var one_K = List[Float64](); one_K.append(pK[j])
            var one_T = List[Float64](); one_T.append(pT[j])
            var one_R = List[Float64](); one_R.append(pR[j])
            var one_V = List[Float64](); one_V.append(pV[j])
            var one_C = List[Float64](); one_C.append(pC[j])
            var single = chain_greeks(one_S, one_K, one_T, one_R, one_V, one_C)
            if not close(pr.price[j], single.price[0], 1e-12):
                ok_tail = False
            if not close(pr.theta[j], single.theta[0], 1e-12):
                ok_tail = False
    if ok_tail:
        print("  ✅ option_greeks_batch::SIMD/tail boundary consistent for n=1..11")
        passed += 1
    else:
        print("  ❌ SIMD/tail boundary")
        failed += 1

    # -- length mismatch raises -----------------------------------------------
    var mm = List[Float64]()
    mm.append(1.0)
    var raised = False
    try:
        _ = chain_greeks(mm, spots, times, rates, sigmas, is_calls)
    except:
        raised = True
    if raised:
        print("  ✅ option_greeks_batch::length mismatch raises")
        passed += 1
    else:
        print("  ❌ length mismatch did not raise")
        failed += 1

    # -- throughput print (not an assertion): 1,000-contract chain ------------
    var bS = List[Float64]()
    var bK = List[Float64]()
    var bT = List[Float64]()
    var bR = List[Float64]()
    var bV = List[Float64]()
    var bC = List[Float64]()
    for j in range(1000):
        bS.append(736.0)
        bK.append(600.0 + Float64(j) * 0.25)
        bT.append(0.02 + Float64(j % 5) * 0.01)
        bR.append(0.05)
        bV.append(0.12 + Float64(j % 7) * 0.03)
        bC.append(1.0 if j % 2 == 0 else 0.0)
    var t0 = perf_counter_ns()
    var reps = 200
    var sink_b: Float64 = 0.0
    for _ in range(reps):
        var out = chain_greeks(bS, bK, bT, bR, bV, bC)
        sink_b += out.price[0] + out.theta[999] + out.gamma[500]
    var t1 = perf_counter_ns()
    var batch_ns = Float64(t1 - t0) / Float64(reps)
    t0 = perf_counter_ns()
    var sink_s: Float64 = 0.0
    for _ in range(reps):
        for j in range(1000):
            sink_s += black_scholes_call(bS[j], bK[j], bT[j], bR[j], bV[j])
            sink_s += delta_call(bS[j], bK[j], bT[j], bR[j], bV[j])
            sink_s += gamma(bS[j], bK[j], bT[j], bR[j], bV[j])
            sink_s += vega(bS[j], bK[j], bT[j], bR[j], bV[j])
            sink_s += theta_call(bS[j], bK[j], bT[j], bR[j], bV[j])
    t1 = perf_counter_ns()
    var scalar_ns = Float64(t1 - t0) / Float64(reps)
    print("  [BENCH] checksums (defeat dead-code elimination):", sink_b, sink_s)
    print(
        "  [BENCH] 1,000-contract chain: batch", batch_ns / 1e3, "us | scalar loop",
        scalar_ns / 1e3, "us | speedup", scalar_ns / batch_ns, "x |",
        batch_ns / 1000.0, "ns/contract",
    )

    print("  [option_greeks_batch] Passed:", passed, "Failed:", failed)
    if failed > 0:
        raise Error("option_greeks_batch tests failed")
