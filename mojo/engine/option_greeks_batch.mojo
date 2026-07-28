"""
option_greeks_batch.mojo — SIMD-batched Black-Scholes greeks across an option chain. Zero Python imports.

Replaces per-contract scalar pricing loops (QuantLib-style) with one call
that vectorizes price/delta/gamma/vega/theta across the CONTRACT axis using
hardware SIMD lanes — built for whole-chain scans (hundreds to thousands of
strikes/expiries per snapshot) where per-call overhead and scalar math
dominate.

Semantics match option_pricing.mojo's scalar functions exactly on the valid
domain (T > 0, sigma > 0); degenerate lanes fall back to discounted
intrinsic value with zero greeks (documented, tested). Theta is per YEAR
(same convention as theta_call); put greeks derive from parity
(delta_put = delta_call - 1, theta_put = theta_call + r·K·e^{-rT}).

Public API:
  chain_greeks — batched BS price + greeks for mixed call/put chains
  ChainGreeksResult — parallel Lists: price, delta, gamma, vega, theta
"""
from std.math import exp, log, sqrt, erf
from std.sys import simd_width_of

comptime SQRT2: Float64 = 1.4142135623730951
comptime INV_SQRT_2PI: Float64 = 0.3989422804014327


struct ChainGreeksResult(Movable):
    var price: List[Float64]
    var delta: List[Float64]
    var gamma: List[Float64]
    var vega: List[Float64]
    var theta: List[Float64]

    fn __init__(
        out self,
        var price: List[Float64],
        var delta: List[Float64],
        var gamma: List[Float64],
        var vega: List[Float64],
        var theta: List[Float64],
    ):
        self.price = price^
        self.delta = delta^
        self.gamma = gamma^
        self.vega = vega^
        self.theta = theta^


def chain_greeks(
    spots: List[Float64],
    strikes: List[Float64],
    times: List[Float64],
    rates: List[Float64],
    sigmas: List[Float64],
    is_calls: List[Float64],
) raises -> ChainGreeksResult:
    """Batched Black-Scholes price and greeks for a whole option chain.

    All six inputs are parallel arrays of length n (is_calls: 1.0 call /
    0.0 put). Lanes with T <= 0 or sigma <= 0 return discounted intrinsic
    value with zero greeks. Vectorized over hardware SIMD lanes with a
    scalar tail; results are identical to the scalar option_pricing
    functions on the valid domain (same erf-based normal CDF).
    """
    var n = len(spots)
    if (
        len(strikes) != n or len(times) != n or len(rates) != n
        or len(sigmas) != n or len(is_calls) != n
    ):
        raise Error("chain_greeks inputs must have equal lengths")

    var price = List[Float64](capacity=n)
    var delta = List[Float64](capacity=n)
    var gamma_out = List[Float64](capacity=n)
    var vega_out = List[Float64](capacity=n)
    var theta_out = List[Float64](capacity=n)
    for _ in range(n):
        price.append(0.0)
        delta.append(0.0)
        gamma_out.append(0.0)
        vega_out.append(0.0)
        theta_out.append(0.0)

    comptime W = simd_width_of[Float64]()
    var s_p = spots.unsafe_ptr()
    var k_p = strikes.unsafe_ptr()
    var t_p = times.unsafe_ptr()
    var r_p = rates.unsafe_ptr()
    var v_p = sigmas.unsafe_ptr()
    var c_p = is_calls.unsafe_ptr()
    var out_price = price.unsafe_ptr()
    var out_delta = delta.unsafe_ptr()
    var out_gamma = gamma_out.unsafe_ptr()
    var out_vega = vega_out.unsafe_ptr()
    var out_theta = theta_out.unsafe_ptr()

    var i = 0
    while i + W <= n:
        var S = s_p.load[width=W](i)
        var K = k_p.load[width=W](i)
        var T = t_p.load[width=W](i)
        var r = r_p.load[width=W](i)
        var sig = v_p.load[width=W](i)
        # SIMD carries the transcendentals (log/exp/erf/sqrt dominate the
        # cost); guard values keep degenerate lanes finite through the math
        # and the per-lane merge below overwrites them with intrinsics.
        var T_s = T
        var sig_s = sig
        for j in range(W):
            if not (t_p[i + j] > 0.0 and v_p[i + j] > 0.0):
                T_s[j] = 1.0
                sig_s[j] = 1.0
        var sqrt_T = sqrt(T_s)
        var d1 = (log(S / K) + (r + 0.5 * sig_s * sig_s) * T_s) / (sig_s * sqrt_T)
        var d2 = d1 - sig_s * sqrt_T
        var nd1 = 0.5 * (1.0 + erf(d1 / SQRT2))
        var nd2 = 0.5 * (1.0 + erf(d2 / SQRT2))
        var pdf1 = INV_SQRT_2PI * exp(-0.5 * d1 * d1)
        var disc = exp(-r * T_s)

        var call_price = S * nd1 - K * disc * nd2
        var put_price = K * disc * (1.0 - nd2) - S * (1.0 - nd1)
        var g = pdf1 / (S * sig_s * sqrt_T)
        var v_greek = S * pdf1 * sqrt_T
        var call_theta = -(S * pdf1 * sig_s) / (2.0 * sqrt_T) - r * K * disc * nd2

        # per-lane merge: cheap branches on scalars; transcendentals above
        # were the vectorized 90%
        for j in range(W):
            var idx = i + j
            var is_call = c_p[idx] > 0.5
            if t_p[idx] > 0.0 and v_p[idx] > 0.0:
                if is_call:
                    out_price[idx] = call_price[j]
                    out_delta[idx] = nd1[j]
                    out_theta[idx] = call_theta[j]
                else:
                    out_price[idx] = put_price[j]
                    out_delta[idx] = nd1[j] - 1.0
                    out_theta[idx] = call_theta[j] + r_p[idx] * k_p[idx] * disc[j]
                out_gamma[idx] = g[j]
                out_vega[idx] = v_greek[j]
            else:
                var t_eff = t_p[idx] if t_p[idx] > 0.0 else 0.0
                var disc0 = exp(-r_p[idx] * t_eff)
                var intr: Float64
                if is_call:
                    intr = s_p[idx] - k_p[idx] * disc0
                else:
                    intr = k_p[idx] * disc0 - s_p[idx]
                out_price[idx] = intr if intr > 0.0 else 0.0
                out_delta[idx] = 0.0
                out_gamma[idx] = 0.0
                out_vega[idx] = 0.0
                out_theta[idx] = 0.0
        i += W

    # scalar tail
    while i < n:
        var S = s_p[i]
        var K = k_p[i]
        var T = t_p[i]
        var r = r_p[i]
        var sig = v_p[i]
        var is_call = c_p[i] > 0.5
        if T <= 0.0 or sig <= 0.0:
            var disc0 = exp(-r * (T if T > 0.0 else 0.0))
            var intr: Float64
            if is_call:
                intr = S - K * disc0
            else:
                intr = K * disc0 - S
            out_price[i] = intr if intr > 0.0 else 0.0
            out_delta[i] = 0.0
            out_gamma[i] = 0.0
            out_vega[i] = 0.0
            out_theta[i] = 0.0
            i += 1
            continue
        var sqrt_T = sqrt(T)
        var d1 = (log(S / K) + (r + 0.5 * sig * sig) * T) / (sig * sqrt_T)
        var d2 = d1 - sig * sqrt_T
        var nd1 = 0.5 * (1.0 + erf(d1 / SQRT2))
        var nd2 = 0.5 * (1.0 + erf(d2 / SQRT2))
        var pdf1 = INV_SQRT_2PI * exp(-0.5 * d1 * d1)
        var disc = exp(-r * T)
        if is_call:
            out_price[i] = S * nd1 - K * disc * nd2
            out_delta[i] = nd1
            out_theta[i] = -(S * pdf1 * sig) / (2.0 * sqrt_T) - r * K * disc * nd2
        else:
            out_price[i] = K * disc * (1.0 - nd2) - S * (1.0 - nd1)
            out_delta[i] = nd1 - 1.0
            out_theta[i] = (
                -(S * pdf1 * sig) / (2.0 * sqrt_T) - r * K * disc * nd2 + r * K * disc
            )
        out_gamma[i] = pdf1 / (S * sig * sqrt_T)
        out_vega[i] = S * pdf1 * sqrt_T
        i += 1

    return ChainGreeksResult(
        price=price^, delta=delta^, gamma=gamma_out^, vega=vega_out^, theta=theta_out^
    )
