"""
Mojo-native scenario comparison engine — N scenarios × M runs in one Mojo call.
Phase 3 refactor: accepts SimRequest instead of PythonObject cfg.

All scenarios share the same Mojo process — zero Python overhead between scenarios.
Uses build_output() from output.mojo — no hardcoded output fields.

Input:
  { "engine_type": "compare", "runs": 10000, "scoring": {...},
    "scenarios": [
      {"name": "Optimistic", "variables": [...], "objective_function": "..."},
      {"name": "Base Case",  "variables": [...], "objective_function": "..."}
    ] }

Output:
  { "engine_type": "compare", "compare_results": [{...envelope...}, ...] }
"""
from std.python import Python

from types         import ExprNode, SimRequest
from python_bridge import fast_f64, fast_int, py_str
from expr          import eval_expr, parse_expr
from distributions import sample_one
from output        import build_output


def run_compare(req: SimRequest) raises -> String:
    """
    Compare engine: runs N scenarios, each as independent MC simulation.
    Reads scenarios array from raw JSON via the single Python boundary here.
    """
    var runs = req.runs
    var w_ev = req.scoring.w_ev
    var w_dr = req.scoring.w_dr

    # re-parse the raw request to get the scenarios array
    var json_m       = Python.import_module("json")
    var b            = Python.import_module("builtins")
    var cfg          = json_m.loads(req.obj_fn)  # obj_fn stores raw config for compare
    # Fall back: load from a special field in SimRequest or re-parse entire request
    # Since compare has its own schema, we use a dedicated raw_compare field via obj_fn hack
    # The actual design: compare request JSON passed directly; main.mojo stores raw json in obj_fn
    # For compare engine, main.mojo passes the raw request string and we parse scenarios here.
    # This function receives raw via req.obj_fn (set by main.mojo dispatch for compare).
    var scenarios_py = cfg.get("scenarios", Python.evaluate("[]"))
    var n_scenarios  = fast_int(b.len(scenarios_py))
    if n_scenarios == 0:
        return '{"error":"compare requires at least one scenario"}'

    var results_json = "["

    for si in range(n_scenarios):
        var sc      = scenarios_py[si]
        var sc_name = py_str(sc.get("name", "scenario_" + String(si + 1)))
        var sc_vars = sc.get("variables", Python.evaluate("[]"))
        var sc_obj  = py_str(sc.get("objective_function", ""))
        var n_vars  = fast_int(b.len(sc_vars))

        # Parse variables for this scenario
        var dt    = List[Int](capacity=n_vars)
        var p0    = List[Float64](capacity=n_vars)
        var p1    = List[Float64](capacity=n_vars)
        var p2    = List[Float64](capacity=n_vars)
        var p3    = List[Float64](capacity=n_vars)
        var vnames     = List[String](capacity=n_vars)
        var disc_vals  = List[List[Float64]]()
        var disc_probs = List[List[Float64]]()

        for i in range(n_vars):
            var v  = sc_vars[i]
            var nm = py_str(v["name"])
            var di = py_str(v["distribution"])
            var pr = v["params"]
            vnames.append(nm)

            if di == "normal":
                dt.append(0); p0.append(fast_f64(pr["mean"])); p1.append(fast_f64(pr["std"]))
                p2.append(0.0); p3.append(0.0)
            elif di == "uniform":
                dt.append(1); p0.append(fast_f64(pr["low"])); p1.append(fast_f64(pr["high"]))
                p2.append(0.0); p3.append(0.0)
            elif di == "triangular":
                dt.append(2); p0.append(fast_f64(pr["low"])); p1.append(fast_f64(pr["mode"]))
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
            elif di == "categorical":
                dt.append(26); p0.append(0.0); p1.append(0.0); p2.append(0.0); p3.append(0.0)
                var vp2 = pr.get("probabilities", Python.evaluate("[]"))
                var nv2 = fast_int(b.len(vp2))
                var vl2 = List[Float64](capacity=nv2); var pl2 = List[Float64](capacity=nv2)
                var cum2: Float64 = 0.0
                for j in range(nv2):
                    vl2.append(Float64(j)); cum2 += fast_f64(vp2[j]); pl2.append(cum2)
                disc_vals.append(vl2.copy()); disc_probs.append(pl2.copy())
            else:  # fixed / fallback
                dt.append(4); p0.append(fast_f64(pr.get("value", 0))); p1.append(0.0)
                p2.append(0.0); p3.append(0.0)

        # Parse objective function
        var expr_nodes = List[ExprNode]()
        var expr_root  = -1
        var use_expr   = False
        if sc_obj.byte_length() > 0 and n_vars > 0:
            expr_root = parse_expr(sc_obj, vnames, expr_nodes)
            use_expr  = expr_root >= 0

        # MC hot loop
        var outcomes = List[Float64](capacity=runs)
        for _ in range(runs):
            var samp = List[Float64](capacity=n_vars); var dci = 0
            for i in range(n_vars):
                var dv = List[Float64](); var dp = List[Float64]()
                if dt[i] in (13, 26) and dci < len(disc_vals):
                    dv = disc_vals[dci].copy(); dp = disc_probs[dci].copy(); dci += 1
                samp.append(sample_one(dt[i], p0[i], p1[i], p2[i], p3[i], dv, dp))
            var o: Float64 = 0.0
            if use_expr and expr_root >= 0:
                o = eval_expr(expr_nodes, expr_root, samp)
            elif n_vars > 0: o = samp[0]
            outcomes.append(o)

        var envelope = build_output(
            outcomes, runs,
            "0.7.0-mojo-compare", "compare", "compare",
            w_ev, w_dr,
            '"scenario_name":"' + sc_name + '"'
        )
        if si > 0: results_json += ","
        results_json += ('{"name":"' + sc_name + '","envelope":' + envelope + '}')

    results_json += "]"
    return ('{"_proto":1,"engine_version":"0.7.0-mojo-compare"'
        + ',"engine_type":"compare"'
        + ',"simulation_model":"compare"'
        + ',"scenarios_run":' + String(runs)
        + ',"compare_results":' + results_json + '}')
