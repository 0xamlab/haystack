"""
qmc_sobol.mojo — Quasi-Monte Carlo with Sobol low-discrepancy sequences.
Extracted from main.mojo (Phase 7). Accepts SimRequest typed struct.
"""
from std.random import random_float64

from types         import ExprNode, SimRequest
from expr          import eval_expr, parse_expr
from distributions import sample_one
from correlation   import icdf
from sobol         import SobolGen
from output        import build_output


def run_qmc_sobol(req: SimRequest) raises -> String:
    """Quasi-Monte Carlo using Sobol sequences for low-discrepancy sampling."""
    var runs   = req.runs
    var n_vars = req.n_vars
    var w_ev   = req.scoring.w_ev
    var w_dr   = req.scoring.w_dr

    # Parse objective function
    var obj_fn     = req.obj_fns[0] if req.n_objectives > 0 else String("")
    var expr_nodes = List[ExprNode]()
    var expr_root  = -1
    var use_expr   = False
    if len(obj_fn) > 0 and n_vars > 0:
        expr_root = parse_expr(obj_fn, req.vnames, expr_nodes)
        use_expr  = expr_root >= 0

    var sobol    = SobolGen(n_vars)
    var outcomes = List[Float64](capacity=runs)
    for _ in range(runs):
        var pt   = sobol.next_point()
        var samp = List[Float64](capacity=n_vars)
        for i in range(n_vars):
            var u   = pt[i] if i < len(pt) else random_float64()
            var val = icdf(u, req.dt[i], req.p0[i], req.p1[i], req.p2[i])
            if req.dt[i] in (5, 9, 10, 11, 12, 13):
                var dv = List[Float64](); var dp = List[Float64]()
                val = sample_one(req.dt[i], req.p0[i], req.p1[i], req.p2[i], req.p3[i], dv, dp)
            samp.append(val)
        var o: Float64 = eval_expr(expr_nodes, expr_root, samp) if use_expr else (samp[0] if n_vars > 0 else 0.0)
        outcomes.append(o)

    return build_output(outcomes, runs, "0.7.0-mojo-qmc-sobol", "qmc_sobol", "qmc_sobol", w_ev, w_dr, '"simulation_model":"qmc_sobol"')
