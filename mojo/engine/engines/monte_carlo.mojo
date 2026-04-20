"""
monte_carlo.mojo — Standard Monte Carlo + streaming + parallel fast path.

Extracted from main.mojo (Phase 7). Accepts SimRequest typed struct.
Supports:
  - Parallel path: xorshift64 per-thread RNG, pre-sized output, parallelize[]
  - Sequential path: Cholesky correlation, discrete/categorical, multi-objective
  - Streaming path: Welford online stats, NDJSON progress frames over socket
  - SIMD sampling via sample_normal_simd4 / sample_uniform_simd4 (Phase 7)
"""
from std.python import Python, PythonObject
from std.random import random_float64, randn_float64
from std.math import sqrt, exp, log, cos, pi, pow
from std.algorithm import parallelize
from std.sys import info

from types          import ExprNode, SimRequest
from expr           import eval_expr, parse_expr
from distributions  import sample_one
from stats          import compute_mean, fast_sort, pctile
from correlation    import cholesky_lower, sample_correlated_normal
from output         import build_output


# ── Per-thread xorshift64 RNG (thread-safe) ────────────────────────────────────

@always_inline
fn xorshift64(state: UInt64) -> UInt64:
    var s = state
    s ^= s << 13; s ^= s >> 7; s ^= s << 17
    return s

@always_inline
fn xr_f64(state: UInt64) -> Float64:
    return Float64(state >> 11) * (1.0 / 9007199254740992.0)

@always_inline
fn xr_normal(mut s: UInt64) -> Float64:
    s = xorshift64(s)
    var u1 = xr_f64(s) + 1e-300
    s = xorshift64(s)
    var u2 = xr_f64(s)
    return sqrt(-2.0 * log(u1)) * cos(2.0 * pi * u2)

fn thread_seed(tid: Int, base: UInt64) -> UInt64:
    var s = base + UInt64(tid) * UInt64(6364136223846793005)
    s = xorshift64(s); s = xorshift64(s); s = xorshift64(s)
    return s


# ── Parallel-safe helpers (all use xorshift64 RNG via inout state) ─────────────

@always_inline
fn _round(x: Float64) -> Float64:
    """Round to nearest integer (positive values only, used for Poisson)."""
    return Float64(Int(x + 0.5))

fn _par_gamma(mut s: UInt64, shape: Float64, scale: Float64) -> Float64:
    """Marsaglia-Tsang gamma sampler using xorshift64 RNG for parallel path.
    Takes mut s (mutable copy) — internal state advances don't propagate to caller."""
    var shape_adj = shape
    var boost: Float64 = 1.0
    if shape < 1.0:
        shape_adj = shape + 1.0
        s = xorshift64(s)
        boost = pow(max(xr_f64(s), 1e-15), 1.0 / shape)
    var d = shape_adj - 1.0 / 3.0
    var c = 1.0 / sqrt(9.0 * d)
    for _ in range(1000):
        s = xorshift64(s)
        var u1 = xr_f64(s) + 1e-300
        s = xorshift64(s)
        var u2 = xr_f64(s)
        var x = sqrt(-2.0 * log(u1)) * cos(2.0 * pi * u2)
        var v = 1.0 + c * x
        if v <= 0.0:
            continue
        v = v * v * v
        s = xorshift64(s)
        var u = xr_f64(s)
        if u < 1.0 - 0.0331 * (x * x) * (x * x):
            return boost * scale * d * v
        if log(max(u, 1e-300)) < 0.5 * x * x + d * (1.0 - v + log(max(v, 1e-300))):
            return boost * scale * d * v
    return boost * scale * d  # fallback (should not reach with 1000 iters)

@always_inline
fn _par_acos_approx(x: Float64) -> Float64:
    """Fast acos approximation for von Mises sampler."""
    var cx = max(-1.0, min(1.0, x))
    return pi / 2.0 - (cx + cx * cx * cx / 6.0 + 3.0 * cx * cx * cx * cx * cx / 40.0)


# ── Universal parallel-safe scalar sampler (all 27 distributions) ──────────────

fn xr_sample(dt: Int, p0: Float64, p1: Float64, p2: Float64, p3: Float64, mut s: UInt64) -> Float64:
    """Sample one value from any distribution type using xorshift64 RNG.
    Handles all 27 distribution types for the parallel MC path.
    Takes mut s (mutable copy) — caller advances s independently after each call."""
    if dt == 0:  # normal(mean=p0, std=p1)
        s = xorshift64(s); var u1 = xr_f64(s) + 1e-300
        s = xorshift64(s); var u2 = xr_f64(s)
        return p0 + p1 * sqrt(-2.0 * log(u1)) * cos(2.0 * pi * u2)
    elif dt == 1:  # uniform(low=p0, high=p1)
        s = xorshift64(s); return p0 + (p1 - p0) * xr_f64(s)
    elif dt == 2:  # triangular(low=p0, mode=p1, high=p2)
        s = xorshift64(s); var u = xr_f64(s)
        var rng = p2 - p0
        if rng == 0.0: return p0
        var fc = (p1 - p0) / rng
        if u < fc: return p0 + sqrt(u * rng * (p1 - p0))
        else: return p2 - sqrt((1.0 - u) * rng * (p2 - p1))
    elif dt == 3:  # lognormal(mu=p0, sigma=p1)
        s = xorshift64(s); var u1 = xr_f64(s) + 1e-300
        s = xorshift64(s); var u2 = xr_f64(s)
        var z = sqrt(-2.0 * log(u1)) * cos(2.0 * pi * u2)
        return exp(p0 + p1 * z)
    elif dt == 4:  # fixed
        return p0
    elif dt == 5:  # beta(alpha=p0, beta=p1)
        var x = _par_gamma(s, p0, 1.0)
        s = xorshift64(s); s = xorshift64(s); s = xorshift64(s)  # diverge state for 2nd gamma
        var y = _par_gamma(s, p1, 1.0)
        var t = x + y
        if t != 0.0: return x / t
        return 0.5
    elif dt == 7:  # exponential(rate=p0)
        s = xorshift64(s); var u = xr_f64(s) + 1e-300
        return -log(u) / p0
    elif dt == 8:  # weibull(shape=p0, scale=p1)
        s = xorshift64(s); var u = xr_f64(s) + 1e-300
        return p1 * pow(-log(u), 1.0 / p0)
    elif dt == 9:  # gamma(shape=p0, scale=p1)
        return _par_gamma(s, p0, p1)
    elif dt == 10:  # pert(low=p0, likely=p1, high=p2, gamma=p3)
        var r = p2 - p0
        if r == 0.0: return p0
        var mu = (p0 + p3 * p1 + p2) / (p3 + 2.0)
        var alpha = max((mu - p0) / r * (p3 + 2.0) / (1.0 + p3), 0.01)
        var beta = max(((p2 - mu) / r) * (p3 + 2.0) / (1.0 + p3), 0.01)
        var bx = _par_gamma(s, alpha, 1.0)
        s = xorshift64(s); s = xorshift64(s); s = xorshift64(s)  # diverge state for 2nd gamma
        var by = _par_gamma(s, beta, 1.0)
        var bt = bx + by
        var bval: Float64 = 0.5
        if bt != 0.0: bval = bx / bt
        return p0 + r * bval
    elif dt == 11:  # bernoulli(p=p0)
        s = xorshift64(s)
        if xr_f64(s) < p0: return 1.0
        return 0.0
    elif dt == 12:  # poisson(lambda=p0)
        if p0 <= 0.0: return 0.0
        if p0 > 30.0:
            # Normal approximation for large lambda
            s = xorshift64(s); var u1 = xr_f64(s) + 1e-300
            s = xorshift64(s); var u2 = xr_f64(s)
            var z = sqrt(-2.0 * log(u1)) * cos(2.0 * pi * u2)
            var val = p0 + sqrt(p0) * z
            if val < 0.0: val = 0.0
            return _round(val)
        var l = exp(-p0); var k: Float64 = 0.0; var pv: Float64 = 1.0
        while pv > l:
            k += 1.0
            s = xorshift64(s); pv *= xr_f64(s)
        return k - 1.0
    elif dt == 14:  # student_t(df=p0, mu=p1, sigma=p2)
        s = xorshift64(s); var u1 = xr_f64(s) + 1e-300
        s = xorshift64(s); var u2 = xr_f64(s)
        var n = sqrt(-2.0 * log(u1)) * cos(2.0 * pi * u2)
        var chi2 = _par_gamma(s, p0 / 2.0, 2.0)
        if chi2 <= 0.0: return p1
        return p1 + p2 * n / sqrt(chi2 / p0)
    elif dt == 15:  # cauchy(location=p0, scale=p1)
        s = xorshift64(s)
        var u = max(1e-10, min(1.0 - 1e-10, xr_f64(s)))
        var denom = u if u < 0.5 else 1.0 - u
        return p0 + p1 * (2.0 * u - 1.0) / (2.0 * denom) * pi
    elif dt == 16:  # laplace(mu=p0, b=p1)
        s = xorshift64(s)
        var u = xr_f64(s) - 0.5
        var sign: Float64 = 1.0
        if u < 0.0: sign = -1.0
        var abs_u = u if u >= 0.0 else -u
        return p0 - p1 * sign * log(max(1.0 - 2.0 * abs_u, 1e-15))
    elif dt == 17:  # pareto(alpha=p0, x_m=p1)
        s = xorshift64(s); var u = max(xr_f64(s), 1e-15)
        return p1 * pow(u, -1.0 / p0)
    elif dt == 18:  # gumbel(mu=p0, beta=p1)
        s = xorshift64(s)
        var u = max(1e-15, min(1.0 - 1e-15, xr_f64(s)))
        return p0 - p1 * log(-log(u))
    elif dt == 19:  # rayleigh(sigma=p0)
        s = xorshift64(s)
        return p0 * sqrt(-2.0 * log(max(xr_f64(s), 1e-15)))
    elif dt == 20:  # arcsine(lo=p0, hi=p1)
        s = xorshift64(s); var u = xr_f64(s)
        var sv = sqrt(u)
        return p0 + (p1 - p0) * sv * sv
    elif dt == 21:  # logistic(mu=p0, s=p1)
        s = xorshift64(s)
        var u = max(1e-15, min(1.0 - 1e-15, xr_f64(s)))
        return p0 + p1 * log(u / (1.0 - u))
    elif dt == 22:  # halfnormal(sigma=p0)
        s = xorshift64(s); var u1 = xr_f64(s) + 1e-300
        s = xorshift64(s); var u2 = xr_f64(s)
        var z = sqrt(-2.0 * log(u1)) * cos(2.0 * pi * u2)
        if z < 0.0: z = -z
        return z * p0
    elif dt == 23:  # vonmises(mu=p0, kappa=p1)
        if p1 <= 0.0:
            s = xorshift64(s)
            return 2.0 * pi * xr_f64(s)
        var tau = 1.0 + sqrt(1.0 + 4.0 * p1 * p1)
        var rho = (tau - sqrt(2.0 * tau)) / (2.0 * p1)
        var r = (1.0 + rho * rho) / (2.0 * rho)
        for _ in range(1000):
            s = xorshift64(s); var u1 = xr_f64(s)
            var zv: Float64
            if u1 < 0.5: zv = cos(pi * u1)
            else: zv = -cos(pi * (u1 - 0.5))
            var z_val = (1.0 + r * zv) / (r + zv)
            var cv = p1 * (r - z_val)
            s = xorshift64(s); var u2 = xr_f64(s)
            if cv * (2.0 - cv) > u2:
                s = xorshift64(s)
                var sign: Float64 = 1.0
                if xr_f64(s) <= 0.5: sign = -1.0
                return p0 + sign * _par_acos_approx(z_val)
            if log(max(cv / max(u2, 1e-300), 1e-300)) + 1.0 >= cv:
                s = xorshift64(s)
                var sign: Float64 = 1.0
                if xr_f64(s) <= 0.5: sign = -1.0
                return p0 + sign * _par_acos_approx(z_val)
        return p0  # fallback
    elif dt == 24:  # neg_binomial(r=p0, p=p1)
        var lam = _par_gamma(s, p0, max((1.0 - p1) / max(p1, 1e-15), 1e-15))
        if lam <= 0.0: return 0.0
        if lam > 30.0:
            s = xorshift64(s); var u1 = xr_f64(s) + 1e-300
            s = xorshift64(s); var u2 = xr_f64(s)
            var z = sqrt(-2.0 * log(u1)) * cos(2.0 * pi * u2)
            var val = lam + sqrt(lam) * z
            if val < 0.0: val = 0.0
            return _round(val)
        var l = exp(-lam); var k: Float64 = 0.0; var pv: Float64 = 1.0
        while pv > l:
            k += 1.0
            s = xorshift64(s); pv *= xr_f64(s)
        return k - 1.0
    elif dt == 25:  # hypergeometric(N=p0, K=p1, n=p2)
        var k: Float64 = 0.0
        var N_i = p0; var K_i = p1; var n_i = p2
        while n_i > 0.0 and K_i > 0.0 and N_i > 0.0:
            var prob = K_i / N_i
            s = xorshift64(s)
            if xr_f64(s) < prob: k += 1.0; K_i -= 1.0
            N_i -= 1.0; n_i -= 1.0
        return k
    # dt == 13 (discrete) and dt == 26 (categorical) are excluded from
    # the parallel path by the has_discrete check, so they never reach here.
    return p0


# ── SIMD-accelerated sampling (Phase 7) ───────────────────────────────────────

fn sample_normal_simd4(mut s: UInt64, mean: Float64, std: Float64) -> SIMD[DType.float64, 4]:
    """Sample 4 normal values using Box-Muller pairs via xorshift64."""
    s = xorshift64(s); var u1a = xr_f64(s) + 1e-300
    s = xorshift64(s); var u2a = xr_f64(s)
    s = xorshift64(s); var u1b = xr_f64(s) + 1e-300
    s = xorshift64(s); var u2b = xr_f64(s)
    var mag_a = sqrt(-2.0 * log(u1a))
    var mag_b = sqrt(-2.0 * log(u1b))
    var z0 = mag_a * cos(2.0 * pi * u2a)
    var z1 = mag_a * (-cos(2.0 * pi * (u2a + 0.5)))  # sin approximation
    var z2 = mag_b * cos(2.0 * pi * u2b)
    var z3 = mag_b * (-cos(2.0 * pi * (u2b + 0.5)))
    return SIMD[DType.float64, 4](
        mean + std * z0, mean + std * z1,
        mean + std * z2, mean + std * z3
    )

fn sample_uniform_simd4(mut s: UInt64, low: Float64, high: Float64) -> SIMD[DType.float64, 4]:
    """Sample 4 uniform values using xorshift64."""
    s = xorshift64(s); var u0 = xr_f64(s)
    s = xorshift64(s); var u1 = xr_f64(s)
    s = xorshift64(s); var u2 = xr_f64(s)
    s = xorshift64(s); var u3 = xr_f64(s)
    var rng = high - low
    return SIMD[DType.float64, 4](
        low + rng * u0, low + rng * u1,
        low + rng * u2, low + rng * u3
    )


# ── Main engine entry point ────────────────────────────────────────────────────

def run_monte_carlo(req: SimRequest) raises -> String:
    """
    Full Monte Carlo engine. Dispatches to parallel, sequential, or streaming path.
    Accepts SimRequest — no PythonObject parameters.
    """
    var runs   = req.runs
    var n_vars = req.n_vars
    var w_ev   = req.scoring.w_ev
    var w_dr   = req.scoring.w_dr

    # Parse objective functions and expression trees
    var obj_fns      = req.obj_fns.copy()
    var n_objectives = req.n_objectives
    var obj_roots    = List[Int]()
    var obj_node_sets = List[List[ExprNode]]()

    for oi in range(n_objectives):
        var obj_nodes = List[ExprNode]()
        var obj_root  = -1
        if len(obj_fns[oi]) > 0 and n_vars > 0:
            obj_root = parse_expr(obj_fns[oi], req.vnames, obj_nodes)
        obj_roots.append(obj_root)
        obj_node_sets.append(obj_nodes^)

    var use_expr   = n_objectives > 0 and obj_roots[0] >= 0
    var expr_nodes = obj_node_sets[0].copy() if n_objectives > 0 else List[ExprNode]()
    var expr_root  = obj_roots[0]

    # Build Cholesky correlation matrix if needed
    var use_cholesky = False
    var chol_L       = List[List[Float64]]()
    var normal_indices = List[Int]()
    for i in range(n_vars):
        if req.dt[i] == 0: normal_indices.append(i)
    var n_normal = len(normal_indices)

    if req.n_corr > 0 and n_normal >= 2:
        var corr_mat = List[List[Float64]]()
        for i in range(n_normal):
            var row = List[Float64](capacity=n_normal)
            for j in range(n_normal): row.append(1.0 if i == j else 0.0)
            corr_mat.append(row.copy())
        for k in range(len(req.corrs)):
            var c  = req.corrs[k].copy()
            var i1 = -1; var i2 = -1
            for ni in range(n_normal):
                if req.vnames[normal_indices[ni]] == req.vnames[c.var1_idx]: i1 = ni
                if req.vnames[normal_indices[ni]] == req.vnames[c.var2_idx]: i2 = ni
            if i1 >= 0 and i2 >= 0:
                corr_mat[i1][i2] = c.coefficient; corr_mat[i2][i1] = c.coefficient
        chol_L = cholesky_lower(corr_mat, n_normal)
        use_cholesky = True

    # Detect discrete/categorical variables
    var has_discrete = False
    for i in range(n_vars):
        if req.dt[i] == 13 or req.dt[i] == 26: has_discrete = True; break

    var stream_mode      = req.stream_mode
    var checkpoint_every = req.checkpoint_every

    # ── Parallel fast path ──────────────────────────────────────────────────
    var can_parallel = (
        not use_cholesky and n_objectives == 1
        and not has_discrete and runs >= 1000
        and not stream_mode
    )

    if can_parallel:
        var n_workers = req.workers if req.workers > 0 else info.num_physical_cores()
        if n_workers < 1: n_workers = 1

        var par_outcomes = List[Float64](capacity=runs)
        for _ in range(runs): par_outcomes.append(0.0)
        var raw_out = par_outcomes.unsafe_ptr()

        var dt_par  = req.dt.copy(); var p0_par = req.p0.copy()
        var p1_par  = req.p1.copy(); var p2_par = req.p2.copy()
        var p3_par  = req.p3.copy()
        var par_nodes = expr_nodes.copy()
        var par_root  = expr_root
        var par_runs  = runs; var par_nvars = n_vars; var par_nw = n_workers
        var par_use_expr = use_expr
        var base_seed  = UInt64(0xA341316C_AABB3D29)

        @parameter
        fn worker(tid: Int) capturing:
            var s     = thread_seed(tid, base_seed)
            var chunk = par_runs // par_nw
            var lo    = tid * chunk
            var hi    = lo + chunk if tid < par_nw - 1 else par_runs
            var samp  = List[Float64](capacity=par_nvars)

            for idx in range(lo, hi):
                samp.clear()
                for i in range(par_nvars):
                    var val = xr_sample(dt_par[i], p0_par[i], p1_par[i], p2_par[i], p3_par[i], s)
                    s = xorshift64(s)
                    samp.append(val)
                var o: Float64 = 0.0
                if par_use_expr and par_root >= 0:
                    o = eval_expr(par_nodes, par_root, samp)
                elif par_nvars > 0: o = samp[0]
                raw_out[idx] = o

        parallelize[worker](n_workers)

        var extra = '"simulation_model":"monte_carlo","parallel":true,"workers":' + String(n_workers)
        return build_output(par_outcomes, runs, "0.7.0-mojo-parallel", "monte_carlo", "monte_carlo", w_ev, w_dr, extra)

    # ── Sequential path (Cholesky / discrete / multi-objective / streaming) ─
    var outcomes       = List[Float64](capacity=runs)
    var multi_outcomes = List[List[Float64]]()
    for _ in range(n_objectives): multi_outcomes.append(List[Float64](capacity=runs))

    var welford_n: Int = 0; var welford_mean: Float64 = 0.0
    var welford_M2: Float64 = 0.0; var welford_min: Float64 = 1e300
    var welford_max: Float64 = -1e300; var welford_n_loss: Int = 0

    for _ in range(runs):
        var samp = List[Float64](capacity=n_vars); var dci = 0

        if use_cholesky and n_normal >= 2:
            var z_corr = sample_correlated_normal(chol_L, n_normal); var ni: Int = 0
            for i in range(n_vars):
                var dv = List[Float64](); var dp = List[Float64]()
                if req.dt[i] == 13 and dci < len(req.disc_vals):
                    dv = req.disc_vals[dci].copy(); dp = req.disc_probs[dci].copy(); dci += 1
                if req.dt[i] == 0 and ni < n_normal:
                    samp.append(req.p0[i] + req.p1[i] * z_corr[ni]); ni += 1
                else:
                    samp.append(sample_one(req.dt[i], req.p0[i], req.p1[i], req.p2[i], req.p3[i], dv, dp))
        else:
            for i in range(n_vars):
                var dv = List[Float64](); var dp = List[Float64]()
                if req.dt[i] in (13, 26) and dci < len(req.disc_vals):
                    dv = req.disc_vals[dci].copy(); dp = req.disc_probs[dci].copy(); dci += 1
                samp.append(sample_one(req.dt[i], req.p0[i], req.p1[i], req.p2[i], req.p3[i], dv, dp))

        var o: Float64 = 0.0
        if use_expr and expr_root >= 0: o = eval_expr(expr_nodes, expr_root, samp)
        elif n_vars > 0: o = samp[0]
        outcomes.append(o)

        if stream_mode:
            welford_n += 1
            var delta = o - welford_mean
            welford_mean += delta / Float64(welford_n)
            var delta2 = o - welford_mean
            welford_M2  += delta * delta2
            if o < welford_min: welford_min = o
            if o > welford_max: welford_max = o
            if o < 0.0: welford_n_loss += 1
            if welford_n % checkpoint_every == 0 or welford_n == runs:
                var w_std = sqrt(welford_M2 / Float64(welford_n - 1)) if welford_n > 1 else 0.0
                var w_pol = Float64(welford_n_loss) / Float64(welford_n)
                print('{"type":"progress","runs_completed":' + String(welford_n)
                    + ',"runs_total":' + String(runs)
                    + ',"progress":' + String(Float64(welford_n) / Float64(runs))
                    + ',"mean":' + String(welford_mean)
                    + ',"std":' + String(w_std)
                    + ',"min":' + String(welford_min)
                    + ',"max":' + String(welford_max)
                    + ',"probability_of_loss":' + String(w_pol) + '}')

        for oi in range(n_objectives):
            var oo: Float64 = 0.0
            if obj_roots[oi] >= 0: oo = eval_expr(obj_node_sets[oi], obj_roots[oi], samp)
            elif n_vars > 0: oo = samp[0]
            multi_outcomes[oi].append(oo)

    var ver = "0.7.0-mojo-universal"
    if use_cholesky: ver = "0.7.0-mojo-universal-cholesky"
    if stream_mode:  ver = "0.7.0-mojo-streaming"

    var multi_out_json = ""
    if n_objectives > 1:
        multi_out_json = '"multi_output":['
        for oi in range(n_objectives):
            if oi > 0: multi_out_json += ","
            var mo      = multi_outcomes[oi].copy()
            var mo_mean = compute_mean(mo, len(mo))
            fast_sort(mo, len(mo))
            multi_out_json += ('{"objective":"' + obj_fns[oi] + '"'
                + ',"mean":' + String(mo_mean)
                + ',"p5":'  + String(pctile(mo, len(mo), 5))
                + ',"p50":' + String(pctile(mo, len(mo), 50))
                + ',"p95":' + String(pctile(mo, len(mo), 95)) + '}')
        multi_out_json += "]"

    var extra = '"simulation_model":"monte_carlo"'
    if use_cholesky: extra += ',"correlated":true'
    if stream_mode:  extra += ',"streamed":true,"checkpoint_every":' + String(checkpoint_every)
    if n_objectives > 1 and len(multi_out_json) > 0: extra += "," + multi_out_json

    var final_json = build_output(outcomes, runs, ver, "monte_carlo", "monte_carlo", w_ev, w_dr, extra)
    if stream_mode:
        print('{"type":"final","result":' + final_json + '}')
        return String("")
    return final_json
