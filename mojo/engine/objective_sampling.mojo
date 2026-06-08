"""
objective_sampling.mojo — shared native objective sampling helpers for
compare / decision_tree / importance_sampling.
"""
from types import ExprNode, SimRequest
from expr import eval_expr, parse_expr
from distributions import sample_one


def sample_request_outcomes(
    req: SimRequest,
    runs_override: Int = -1,
) raises -> List[Float64]:
    var runs = runs_override if runs_override > 0 else req.runs
    if runs < 1:
        runs = 1

    var outcomes = List[Float64](capacity=runs)
    var objective = req.obj_fns[0] if req.n_objectives > 0 else req.obj_fn
    var expr_nodes = List[ExprNode]()
    var expr_root = -1
    var use_expr = False
    if len(objective) > 0 and req.n_vars > 0:
        expr_root = parse_expr(objective, req.vnames, expr_nodes)
        use_expr = expr_root >= 0

    for _ in range(runs):
        var sample = List[Float64](capacity=req.n_vars)
        var disc_idx = 0
        for i in range(req.n_vars):
            var disc_values = List[Float64]()
            var disc_probs = List[Float64]()
            if req.dt[i] in (13, 26) and disc_idx < len(req.disc_vals):
                disc_values = req.disc_vals[disc_idx].copy()
                disc_probs = req.disc_probs[disc_idx].copy()
                disc_idx += 1
            sample.append(
                sample_one(
                    req.dt[i],
                    req.p0[i],
                    req.p1[i],
                    req.p2[i],
                    req.p3[i],
                    disc_values,
                    disc_probs,
                )
            )

        var outcome = 0.0
        if use_expr and expr_root >= 0:
            outcome = eval_expr(expr_nodes, expr_root, sample)
        elif req.n_vars > 0:
            outcome = sample[0]
        outcomes.append(outcome)

    return outcomes^
