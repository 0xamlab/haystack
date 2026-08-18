"""
Importance Sampling for Rare Tail Events — Phase 3 refactor.
Accepts SimRequest instead of PythonObject cfg.
IS config fields read from req.is_cfg (typed ISCfg struct).
Pre-parsed variable arrays (dt, p0..p3) read from req directly.
Zero PythonObject in simulation hot loop.
"""
from std.random import randn_float64, random_float64
from std.math import sqrt, exp, log

from types     import ExprNode, SimRequest
from expr      import eval_expr, parse_expr
from distributions import sample_one
from stats     import compute_mean, compute_variance, pctile, fast_sort
from output    import build_output


def _weighted_mean(vals: List[Float64], weights: List[Float64], n: Int) -> Float64:
    var tw: Float64 = 0.0; var wm: Float64 = 0.0
    for i in range(n): tw += weights[i]; wm += vals[i] * weights[i]
    return wm / max(tw, 1e-300)

def _weighted_variance(vals: List[Float64], weights: List[Float64], n: Int, wmean: Float64) -> Float64:
    var tw: Float64 = 0.0; var wv: Float64 = 0.0
    for i in range(n): tw += weights[i]; wv += weights[i] * (vals[i] - wmean) * (vals[i] - wmean)
    return wv / max(tw, 1e-300)

def _ess(weights: List[Float64], n: Int) -> Float64:
    var sum_w: Float64 = 0.0; var sum_w2: Float64 = 0.0
    for i in range(n): sum_w += weights[i]; sum_w2 += weights[i] * weights[i]
    if sum_w2 <= 0.0: return 0.0
    return sum_w * sum_w / sum_w2


def run_importance_sampling(req: SimRequest) raises -> String:
    """
    Importance sampling engine: exponential tilting of normal distributions.
    Reads all config from req.is_cfg + req.dt/p0..p3 — no PythonObject.
    """
    var runs   = req.runs
    var n_vars = req.n_vars
    var w_ev   = req.scoring.w_ev
    var w_dr   = req.scoring.w_dr

    # Parse objective function
    var obj_fn     = req.obj_fns[0] if req.n_objectives > 0 else String("")
    var expr_nodes = List[ExprNode]()
    var expr_root  = -1
    var use_expr   = False
    if obj_fn.byte_length() > 0 and n_vars > 0:
        expr_root = parse_expr(obj_fn, req.vnames, expr_nodes)
        use_expr  = expr_root >= 0

    # IS config
    var threshold     = req.is_cfg.target_threshold if req.has_is_cfg else Float64(-1e30)
    var tail_dir      = req.is_cfg.tail_direction   if req.has_is_cfg else String("lower")
    var tilt_var_name = req.is_cfg.tilt_var_name    if req.has_is_cfg else String("")
    var tilt_override = req.is_cfg.tilt_override     if req.has_is_cfg else Float64(0.0)

    # Find normal variables (only normals can be tilted)
    var normal_idxs = List[Int]()
    var normal_mus  = List[Float64]()
    var normal_sigs = List[Float64]()
    for i in range(n_vars):
        if req.dt[i] == 0:
            normal_idxs.append(i)
            normal_mus.append(req.p0[i])
            normal_sigs.append(req.p1[i])

    # Determine tilt variable
    var tilt_idx: Int = -1
    var tilt_var_global: Int = -1
    if len(normal_idxs) > 0:
        if tilt_var_name.byte_length() > 0:
            for ni in range(len(normal_idxs)):
                if req.vnames[normal_idxs[ni]] == tilt_var_name:
                    tilt_idx = ni; tilt_var_global = normal_idxs[ni]; break
        if tilt_idx < 0:
            var best_sig: Float64 = -1.0
            for ni in range(len(normal_idxs)):
                if normal_sigs[ni] > best_sig:
                    best_sig = normal_sigs[ni]; tilt_idx = ni
            if tilt_idx >= 0: tilt_var_global = normal_idxs[tilt_idx]

    # Compute optimal tilt θ
    var theta: Float64 = 0.0
    if tilt_override != 0.0:
        theta = tilt_override
    elif tilt_idx >= 0 and threshold > -1e29:
        var mu_t  = normal_mus[tilt_idx]
        var sig_t = normal_sigs[tilt_idx]
        if sig_t > 0.0:
            theta = (threshold - mu_t) / (sig_t * sig_t)
            if tail_dir == "lower":
                if theta > 0.0: theta = 0.0
                if theta < -5.0 / sig_t: theta = -5.0 / sig_t
            else:
                if theta < 0.0: theta = 0.0
                if theta > 5.0 / sig_t: theta = 5.0 / sig_t

    var mu_tilt: Float64  = normal_mus[tilt_idx]  if tilt_idx >= 0 else 0.0
    var sig_tilt: Float64 = normal_sigs[tilt_idx] if tilt_idx >= 0 else 1.0
    if tilt_idx >= 0:
        mu_tilt = normal_mus[tilt_idx] + theta * sig_tilt * sig_tilt

    # Simulation hot loop — zero PythonObject
    var outcomes = List[Float64](capacity=runs)
    var iweights = List[Float64](capacity=runs)
    var n_tail: Int = 0

    for _ in range(runs):
        var samp   = List[Float64](capacity=n_vars)
        var log_w: Float64 = 0.0
        for i in range(n_vars):
            var val: Float64
            var dv = List[Float64](); var dp = List[Float64]()
            if i == tilt_var_global and tilt_idx >= 0:
                var z   = randn_float64()
                val     = mu_tilt + sig_tilt * z
                var x_minus_mu = val - normal_mus[tilt_idx]
                log_w  += -theta * x_minus_mu + 0.5 * theta * theta * sig_tilt * sig_tilt
            else:
                val = sample_one(req.dt[i], req.p0[i], req.p1[i], req.p2[i], req.p3[i], dv, dp)
            samp.append(val)

        var o: Float64 = 0.0
        if use_expr and expr_root >= 0: o = eval_expr(expr_nodes, expr_root, samp)
        elif n_vars > 0: o = samp[0]

        var w = exp(min(log_w, 50.0))
        outcomes.append(o); iweights.append(w)
        if tail_dir == "lower" and o < threshold: n_tail += 1
        elif tail_dir == "upper" and o > threshold: n_tail += 1

    var wmean  = _weighted_mean(outcomes, iweights, runs)
    var wvar   = _weighted_variance(outcomes, iweights, runs, wmean)
    var wstd   = sqrt(max(wvar, 0.0))
    var ess    = _ess(iweights, runs)
    var vr_factor = Float64(runs) / max(ess, 1.0)

    var w_total: Float64 = 0.0; var w_tail: Float64 = 0.0
    for i in range(runs):
        w_total += iweights[i]
        if (tail_dir == "lower" and outcomes[i] < threshold) or (tail_dir == "upper" and outcomes[i] > threshold):
            w_tail += iweights[i]
    var tail_prob = w_tail / max(w_total, 1e-300)

    var tail_vals = List[Float64](); var tail_ws = List[Float64]()
    for i in range(runs):
        if (tail_dir == "lower" and outcomes[i] < threshold) or (tail_dir == "upper" and outcomes[i] > threshold):
            tail_vals.append(outcomes[i]); tail_ws.append(iweights[i])
    var cvar_tail: Float64 = 0.0
    if len(tail_vals) > 0:
        cvar_tail = _weighted_mean(tail_vals, tail_ws, len(tail_vals))

    var se_tail: Float64 = 0.0
    if tail_prob > 0.0 and ess > 1.0:
        se_tail = sqrt(tail_prob * (1.0 - tail_prob) / ess)

    var raw_outcomes = outcomes.copy()
    fast_sort(raw_outcomes, runs)

    var tilt_vname = req.vnames[tilt_var_global] if tilt_var_global >= 0 else String("none")
    var is_json = (
        '"importance_sampling_result":{'
        + '"tail_direction":"' + tail_dir + '"'
        + ',"target_threshold":' + String(threshold)
        + ',"tail_probability":' + String(tail_prob)
        + ',"tail_probability_se":' + String(se_tail)
        + ',"cvar_tail":' + String(cvar_tail)
        + ',"weighted_mean":' + String(wmean)
        + ',"weighted_std":' + String(wstd)
        + ',"theta":' + String(theta)
        + ',"tilt_variable":"' + tilt_vname + '"'
        + ',"effective_sample_size":' + String(ess)
        + ',"nominal_sample_size":' + String(runs)
        + ',"variance_reduction_factor":' + String(vr_factor)
        + ',"naive_tail_count":' + String(n_tail) + '}'
    )
    return build_output(raw_outcomes, runs, "0.7.0-mojo-is", "importance_sampling",
                        "importance_sampling", w_ev, w_dr, is_json)
