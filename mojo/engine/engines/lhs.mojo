"""
lhs.mojo — Latin Hypercube Sampling engine.
Extracted from main.mojo (Phase 7). Accepts SimRequest typed struct.
"""
from std.random import random_float64

from types         import ExprNode, SimRequest
from expr          import eval_expr, parse_expr
from distributions import sample_one
from correlation   import icdf
from output        import build_output


def run_lhs(req: SimRequest) raises -> String:
    """Latin Hypercube Sampling — stratified coverage of the probability space."""
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

    # Fisher-Yates shuffle for stratum permutation per variable
    var strata = List[List[Int]]()
    for _ in range(n_vars):
        var perm = List[Int](capacity=runs)
        for i in range(runs): perm.append(i)
        for i in range(runs - 1, 0, -1):
            var j = Int(random_float64() * Float64(i + 1))
            if j > i: j = i
            var tmp = perm[i]; perm[i] = perm[j]; perm[j] = tmp
        strata.append(perm^)

    var outcomes = List[Float64](capacity=runs)
    for ri in range(runs):
        var samp = List[Float64](capacity=n_vars); var dci = 0
        for i in range(n_vars):
            var stratum = strata[i][ri]
            var u   = (Float64(stratum) + random_float64()) / Float64(runs)
            var val = icdf(u, req.dt[i], req.p0[i], req.p1[i], req.p2[i])
            if req.dt[i] in (5, 9, 10, 11, 12, 13):
                var dv = List[Float64](); var dp = List[Float64]()
                if req.dt[i] == 13 and dci < len(req.disc_vals):
                    dv = req.disc_vals[dci].copy(); dp = req.disc_probs[dci].copy(); dci += 1
                val = sample_one(req.dt[i], req.p0[i], req.p1[i], req.p2[i], req.p3[i], dv, dp)
            samp.append(val)
        var o: Float64 = eval_expr(expr_nodes, expr_root, samp) if use_expr else (samp[0] if n_vars > 0 else 0.0)
        outcomes.append(o)

    return build_output(outcomes, runs, "0.7.0-mojo-lhs", "lhs", "lhs", w_ev, w_dr, '"simulation_model":"lhs"')
