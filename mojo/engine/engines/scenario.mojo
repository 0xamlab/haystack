"""
scenario.mojo — Discrete weighted scenario analysis engine.
Extracted from main.mojo (Phase 7). Accepts SimRequest typed struct.
"""
from std.python import Python
from std.random import random_float64

from types         import ExprNode, SimRequest
from expr          import eval_expr, parse_expr
from output        import build_output
from python_bridge import fast_f64, fast_int, py_str


def run_scenario(req: SimRequest) raises -> String:
    """
    Scenario analysis: discrete weighted outcomes with optional MC sampling.
    Reads scenario_cfg.raw_config (JSON string) for per-scenario variable overrides.
    No PythonObject parameters — raw_config is re-parsed here (single boundary).
    """
    var runs   = req.runs
    var w_ev   = req.scoring.w_ev
    var w_dr   = req.scoring.w_dr
    var n_vars = req.n_vars

    if not req.has_scenario_cfg:
        return '{"error":"scenario_config required for scenario engine"}'

    var json_m = Python.import_module("json")
    var b      = Python.import_module("builtins")
    var sc_cfg = json_m.loads(req.scenario_cfg.raw_config)
    var sc_py  = sc_cfg.get("scenarios", Python.evaluate("[]"))
    var n_sc   = fast_int(b.len(sc_py))
    if n_sc == 0:
        return '{"error":"scenario_config.scenarios required"}'

    # Rebuild objective function expression from req
    var obj_fn     = req.obj_fns[0] if req.n_objectives > 0 else String("")
    var expr_nodes = List[ExprNode]()
    var expr_root  = -1
    var use_expr   = False
    if obj_fn.byte_length() > 0 and n_vars > 0:
        expr_root = parse_expr(obj_fn, req.vnames, expr_nodes)
        use_expr  = expr_root >= 0

    var sc_names    = List[String](capacity=n_sc)
    var sc_probs    = List[Float64](capacity=n_sc)
    var sc_outcomes = List[Float64](capacity=n_sc)
    var ev: Float64 = 0.0

    for s in range(n_sc):
        var sc      = sc_py[s]
        var sc_name = py_str(sc.get("name", "S" + String(s + 1)))
        var sc_prob = fast_f64(sc.get("probability", 1.0 / Float64(n_sc)))
        var sc_vars = sc.get("variables", Python.evaluate("{}"))
        var sc_fn   = py_str(sc.get("objective_function", obj_fn))
        var samp    = List[Float64](capacity=n_vars)
        for i in range(n_vars):
            samp.append(fast_f64(sc_vars.get(req.vnames[i], req.p0[i])))

        var outcome: Float64
        if sc_fn.byte_length() > 0 and sc_fn != obj_fn:
            var sc_nodes = List[ExprNode]()
            var sc_root  = parse_expr(sc_fn, req.vnames, sc_nodes)
            outcome = eval_expr(sc_nodes, sc_root, samp)
        elif use_expr: outcome = eval_expr(expr_nodes, expr_root, samp)
        elif n_vars > 0: outcome = samp[0]
        else: outcome = 0.0

        sc_names.append(sc_name); sc_probs.append(sc_prob); sc_outcomes.append(outcome)
        ev += sc_prob * outcome

    var outcomes = List[Float64](capacity=runs)
    for ri in range(runs):
        var u = random_float64(); var cum: Float64 = 0.0
        for s in range(n_sc):
            cum += sc_probs[s]
            if u <= cum: outcomes.append(sc_outcomes[s]); break
        if len(outcomes) < ri + 1:
            outcomes.append(sc_outcomes[n_sc - 1])

    var sc_json = '"scenario_analysis":{"expected_value":' + String(ev) + ',"scenarios":['
    for s in range(n_sc):
        if s > 0: sc_json += ","
        sc_json += ('{"name":"' + sc_names[s] + '","probability":' + String(sc_probs[s])
            + ',"outcome":' + String(sc_outcomes[s])
            + ',"contribution":' + String(sc_probs[s] * sc_outcomes[s]) + '}')
    sc_json += "]}"
    return build_output(outcomes, runs, "0.7.0-mojo-scenario", "scenario", "scenario", w_ev, w_dr, sc_json)
