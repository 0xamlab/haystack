"""
sensitivity.mojo — Tornado chart + first-order Sobol indices engine.
Extracted from main.mojo (Phase 7). Accepts SimRequest typed struct.
Emits tornado_data with typed fields per variable.
"""
from std.math import exp, sqrt

from types         import ExprNode, SimRequest
from expr          import eval_expr, parse_expr
from distributions import sample_one
from stats         import compute_mean, compute_variance, pctile, fast_sort
from output        import build_output


def run_sensitivity(req: SimRequest) raises -> String:
    """
    First-order sensitivity analysis: Tornado chart + Sobol indices.
    Each variable is varied independently while others held at baseline.
    """
    var runs   = req.runs
    var n_vars = req.n_vars
    var w_ev   = req.scoring.w_ev
    var w_dr   = req.scoring.w_dr
    var n_sens = min(runs, 2000)

    # Parse objective function
    var obj_fn     = req.obj_fns[0] if req.n_objectives > 0 else String("")
    var expr_nodes = List[ExprNode]()
    var expr_root  = -1
    var use_expr   = False
    if obj_fn.byte_length() > 0 and n_vars > 0:
        expr_root = parse_expr(obj_fn, req.vnames, expr_nodes)
        use_expr  = expr_root >= 0

    # Compute baseline values
    var base = List[Float64](capacity=n_vars)
    for i in range(n_vars):
        var bv: Float64
        if req.dt[i] == 0:    bv = req.p0[i]
        elif req.dt[i] == 1:  bv = (req.p0[i] + req.p1[i]) / 2.0
        elif req.dt[i] == 2:  bv = req.p1[i]
        elif req.dt[i] == 3:  bv = exp(req.p0[i] + req.p1[i] * req.p1[i] / 2.0)
        elif req.dt[i] == 10: bv = (req.p0[i] + req.p3[i] * req.p1[i] + req.p2[i]) / (req.p3[i] + 2.0)
        else: bv = req.p0[i]
        base.append(bv)

    var base_out: Float64
    if use_expr:     base_out = eval_expr(expr_nodes, expr_root, base)
    elif n_vars > 0: base_out = base[0]
    else:            base_out = 0.0

    # Full sample — all variables random
    var all_outs = List[Float64](capacity=n_sens)
    for _ in range(n_sens):
        var samp = List[Float64](capacity=n_vars); var dci = 0
        for i in range(n_vars):
            var dv = List[Float64](); var dp = List[Float64]()
            if req.dt[i] == 13 and dci < len(req.disc_vals):
                dv = req.disc_vals[dci].copy(); dp = req.disc_probs[dci].copy(); dci += 1
            samp.append(sample_one(req.dt[i], req.p0[i], req.p1[i], req.p2[i], req.p3[i], dv, dp))
        var o: Float64 = eval_expr(expr_nodes, expr_root, samp) if use_expr else (samp[0] if n_vars > 0 else 0.0)
        all_outs.append(o)

    var total_var    = compute_variance(all_outs, n_sens, compute_mean(all_outs, n_sens))
    var tornado_json = "["
    var sobol_json   = "{"

    for vi in range(n_vars):
        var var_outs = List[Float64](capacity=n_sens)
        for _ in range(n_sens):
            var samp = List[Float64](capacity=n_vars); var dci = 0
            for i in range(n_vars):
                if i == vi:
                    var dv = List[Float64](); var dp = List[Float64]()
                    if req.dt[i] == 13 and dci < len(req.disc_vals):
                        dv = req.disc_vals[dci].copy(); dp = req.disc_probs[dci].copy(); dci += 1
                    samp.append(sample_one(req.dt[i], req.p0[i], req.p1[i], req.p2[i], req.p3[i], dv, dp))
                else:
                    samp.append(base[i])
            var o: Float64 = eval_expr(expr_nodes, expr_root, samp) if use_expr else (samp[0] if n_vars > 0 else 0.0)
            var_outs.append(o)

        fast_sort(var_outs, n_sens)
        var vp5   = pctile(var_outs, n_sens, 5)
        var vp95  = pctile(var_outs, n_sens, 95)
        var vmean = compute_mean(var_outs, n_sens)
        var vvar  = compute_variance(var_outs, n_sens, vmean)
        var si    = max(0.0, min(1.0, vvar / total_var)) if total_var > 0.0 else 0.0

        if vi > 0: tornado_json += ","; sobol_json += ","
        tornado_json += ('{"variable":"' + req.vnames[vi] + '"'
            + ',"low_swing":'           + String(vp5 - base_out)
            + ',"high_swing":'          + String(vp95 - base_out)
            + ',"range":'               + String(vp95 - vp5)
            + ',"mean_impact":'         + String(vmean - base_out)
            + ',"variance_contribution":' + String(vvar) + '}')
        sobol_json += '"' + req.vnames[vi] + '":' + String(si)

    tornado_json += "]"; sobol_json += "}"
    var sens_json = ('"sensitivity_analysis":{"base_outcome":' + String(base_out)
        + ',"n_samples":' + String(n_sens)
        + ',"tornado_chart":' + tornado_json
        + ',"first_order_sobol":' + sobol_json + '}')
    return build_output(all_outs, n_sens, "0.7.0-mojo-sensitivity", "sensitivity", "sensitivity", w_ev, w_dr, sens_json)
