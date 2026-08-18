"""
Decision Tree hot-loop engine — pure Mojo, zero Python in the sampling loop.
Phase 3 refactor: accepts SimRequest. Decision tree config stored as raw JSON
in req.decision_tree_cfg.raw_config, re-parsed here (single Python boundary).
"""
from std.python import Python

from types         import ExprNode, SimRequest
from python_bridge import fast_f64, fast_int, py_str
from expr          import eval_expr, parse_expr
from distributions import sample_one
from stats         import compute_mean
from output        import build_output


def run_decision_tree(req: SimRequest) raises -> String:
    """
    Decision tree MC: allocates runs proportional to path probability.
    Re-parses decision_tree_config from raw JSON here (single Python call).
    """
    var runs = req.runs
    var w_ev = req.scoring.w_ev
    var w_dr = req.scoring.w_dr

    if not req.has_decision_tree_cfg:
        return '{"error":"decision_tree_config required for decision_tree engine"}'

    var json_m   = Python.import_module("json")
    var b        = Python.import_module("builtins")
    var dt_cfg   = json_m.loads(req.decision_tree_cfg.raw_config)
    var paths_py = dt_cfg.get("paths", Python.evaluate("[]"))
    var n_paths  = fast_int(b.len(paths_py))
    if n_paths == 0:
        return '{"error":"decision_tree_config.paths is required"}'

    var all_outcomes = List[Float64](capacity=runs)
    var path_labels  = List[String]()
    var path_probs   = List[Float64]()
    var path_means   = List[Float64]()
    var path_runs_v  = List[Int]()

    var total_prob: Float64 = 0.0
    for pi in range(n_paths):
        total_prob += fast_f64(paths_py[pi].get("probability", 1.0 / Float64(n_paths)))
    if total_prob <= 0.0: total_prob = 1.0

    for pi in range(n_paths):
        var path      = paths_py[pi]
        var label     = py_str(path.get("label", "path_" + String(pi)))
        var raw_prob  = fast_f64(path.get("probability", 1.0 / Float64(n_paths)))
        var path_prob = raw_prob / total_prob
        var runs_here = max(1, Int(path_prob * Float64(runs) + 0.5))

        var path_vars = path.get("variables", Python.evaluate("[]"))
        var n_vars    = fast_int(b.len(path_vars))
        var dt    = List[Int](capacity=n_vars); var p0 = List[Float64](capacity=n_vars)
        var p1    = List[Float64](capacity=n_vars); var p2 = List[Float64](capacity=n_vars)
        var p3    = List[Float64](capacity=n_vars)
        var vnames = List[String](capacity=n_vars)
        var disc_vals  = List[List[Float64]]()
        var disc_probs = List[List[Float64]]()

        for i in range(n_vars):
            var v  = path_vars[i]; var nm = py_str(v["name"])
            var di = py_str(v["distribution"]); var pr = v["params"]
            vnames.append(nm)
            if di == "normal":
                dt.append(0); p0.append(fast_f64(pr["mean"])); p1.append(fast_f64(pr["std"]))
                p2.append(0.0); p3.append(0.0)
            elif di == "uniform":
                dt.append(1); p0.append(fast_f64(pr["low"]));  p1.append(fast_f64(pr["high"]))
                p2.append(0.0); p3.append(0.0)
            elif di == "triangular":
                dt.append(2); p0.append(fast_f64(pr["low"]));  p1.append(fast_f64(pr["mode"]))
                p2.append(fast_f64(pr["high"])); p3.append(0.0)
            elif di == "lognormal":
                dt.append(3); p0.append(fast_f64(pr["mean"])); p1.append(fast_f64(pr["std"]))
                p2.append(0.0); p3.append(0.0)
            elif di == "beta":
                dt.append(5); p0.append(fast_f64(pr.get("alpha", 2.0))); p1.append(fast_f64(pr.get("beta", 2.0)))
                p2.append(0.0); p3.append(0.0)
            elif di == "exponential":
                dt.append(7); p0.append(fast_f64(pr.get("rate", 1.0))); p1.append(0.0)
                p2.append(0.0); p3.append(0.0)
            elif di == "weibull":
                dt.append(8); p0.append(fast_f64(pr.get("shape", 1.0))); p1.append(fast_f64(pr.get("scale", 1.0)))
                p2.append(0.0); p3.append(0.0)
            elif di == "gamma":
                dt.append(9); p0.append(fast_f64(pr.get("shape", 1.0))); p1.append(fast_f64(pr.get("scale", 1.0)))
                p2.append(0.0); p3.append(0.0)
            elif di == "pert":
                dt.append(10); p0.append(fast_f64(pr.get("low", 0.0)));   p1.append(fast_f64(pr.get("likely", 0.5)))
                p2.append(fast_f64(pr.get("high", 1.0))); p3.append(fast_f64(pr.get("gamma", 4.0)))
            elif di == "bernoulli":
                dt.append(11); p0.append(fast_f64(pr.get("p", 0.5))); p1.append(0.0)
                p2.append(0.0); p3.append(0.0)
            elif di == "poisson":
                dt.append(12); p0.append(fast_f64(pr.get("lambda", 1.0))); p1.append(0.0)
                p2.append(0.0); p3.append(0.0)
            elif di == "discrete":
                dt.append(13); p0.append(0.0); p1.append(0.0); p2.append(0.0); p3.append(0.0)
                var vp = pr.get("values", Python.evaluate("[]"))
                var pp = pr.get("probabilities", Python.evaluate("[]"))
                var nv = fast_int(b.len(vp))
                var vl = List[Float64](capacity=nv); var pl = List[Float64](capacity=nv)
                var cum: Float64 = 0.0
                for j in range(nv):
                    vl.append(fast_f64(vp[j])); cum += fast_f64(pp[j]); pl.append(cum)
                disc_vals.append(vl.copy()); disc_probs.append(pl.copy())
            elif di == "student_t":
                dt.append(14); p0.append(fast_f64(pr.get("df", 5.0)))
                p1.append(fast_f64(pr.get("loc", 0.0))); p2.append(fast_f64(pr.get("scale", 1.0))); p3.append(0.0)
            elif di == "categorical":
                dt.append(26); p0.append(0.0); p1.append(0.0); p2.append(0.0); p3.append(0.0)
                var vp2 = pr.get("probabilities", Python.evaluate("[]"))
                var nv2 = fast_int(b.len(vp2))
                var vl2 = List[Float64](capacity=nv2); var pl2 = List[Float64](capacity=nv2)
                var cum2: Float64 = 0.0
                for j in range(nv2):
                    vl2.append(Float64(j)); cum2 += fast_f64(vp2[j]); pl2.append(cum2)
                disc_vals.append(vl2.copy()); disc_probs.append(pl2.copy())
            else:
                dt.append(4); p0.append(fast_f64(pr.get("value", 0))); p1.append(0.0)
                p2.append(0.0); p3.append(0.0)

        var path_obj_fn = py_str(path.get("objective_function", ""))
        var expr_nodes  = List[ExprNode]()
        var expr_root   = -1
        var use_expr    = False
        if path_obj_fn.byte_length() > 0 and n_vars > 0:
            expr_root = parse_expr(path_obj_fn, vnames, expr_nodes)
            use_expr  = expr_root >= 0

        var path_outcomes = List[Float64](capacity=runs_here)
        for _ in range(runs_here):
            var samp = List[Float64](capacity=n_vars); var dci = 0
            for i in range(n_vars):
                var dv = List[Float64](); var dp = List[Float64]()
                if dt[i] in (13, 26) and dci < len(disc_vals):
                    dv = disc_vals[dci].copy(); dp = disc_probs[dci].copy(); dci += 1
                samp.append(sample_one(dt[i], p0[i], p1[i], p2[i], p3[i], dv, dp))
            var o: Float64 = 0.0
            if use_expr and expr_root >= 0: o = eval_expr(expr_nodes, expr_root, samp)
            elif n_vars > 0: o = samp[0]
            path_outcomes.append(o); all_outcomes.append(o)

        var path_mean = compute_mean(path_outcomes, runs_here)
        path_labels.append(label); path_probs.append(path_prob)
        path_means.append(path_mean); path_runs_v.append(runs_here)

    var n_total = len(all_outcomes)
    if n_total == 0: return '{"error":"no outcomes generated"}'

    var ev_weighted: Float64 = 0.0
    for pi in range(n_paths): ev_weighted += path_means[pi] * path_probs[pi]

    var paths_json = '"paths":['
    for pi in range(n_paths):
        if pi > 0: paths_json += ","
        paths_json += ('{"path":"' + path_labels[pi] + '"'
            + ',"probability":' + String(path_probs[pi])
            + ',"runs":' + String(path_runs_v[pi])
            + ',"mean_outcome":' + String(path_means[pi])
            + ',"expected_contribution":' + String(path_means[pi] * path_probs[pi]) + '}')
    paths_json += "]"

    var extra_json = ('"simulation_model":"decision_tree"'
        + ',"decision_tree_result":{"n_paths":' + String(n_paths)
        + ',"expected_value":' + String(ev_weighted)
        + ',' + paths_json + '}')
    return build_output(all_outcomes, n_total, "0.7.0-mojo-decision-tree",
                        "decision_tree", "decision_tree", w_ev, w_dr, extra_json)
