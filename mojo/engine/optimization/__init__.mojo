"""
optimization — a general objective that can actually reach a solver. Zero Python.

What the tree has today, and why it is not enough
-------------------------------------------------
An objective crosses into the frozen optimizers by exactly three mechanisms, and none
of them interoperates with the others:

1. An integer `func_id` selecting one hardcoded function. There are FOUR mutually
   incompatible id tables — `optimization_constrained.eval_objective_c` (0 = Σx², 1 =
   -(x0*x1), 2 = Σx), `optimization_meta.eval_objective` (0 = sphere, 1 = Rastrigin,
   2 = Ackley), `convex.eval_function` (0 = quadratic, 1 = Rosenbrock) and
   `root_finding.eval_func` (0 = x²-2, 1 = x³-x-2, 2 = cos x - x, 3 = eˣ-3x). The same
   integer means a different function in each, and every one of them returns `0.0` for
   an id it does not recognise. The consequence is silent and total:
   `convex.gradient_descent` with an unknown id sees an all-zero gradient and returns
   `x0` on iteration 0 (`if gnorm < tol: break`), `root_finding.newton_raphson` returns
   `x0` immediately, and `optimization_meta.run_ga` degenerates into a random walk.
   Nothing anywhere reports that the objective was never evaluated.
2. A polynomial coefficient list (`optimize.mojo`), ascending powers, ONE variable.
3. An objective as a STRING parsed to an AST (`expr.parse_expr` / `expr.eval_expr`).
   This is the only general mechanism in the tree and no optimizer uses it.

So a general objective — several variables, arbitrary arithmetic, its own constraints —
cannot reach any optimizer at all. This package is the missing plumbing, and `model.mojo`
is its keystone: everything else in the package takes an `OptModel` and returns a status
alongside its numbers.

Modules:
  model — the model container over the frozen `types.ExprNode` IR: variables with
        bounds, kinds and warm starts; an objective arena plus a direction; constraints
        as (arena, sense, rhs); a solver policy; a validator that rejects a malformed
        model whole; a non-recursive scalar evaluator that reports a domain failure as a
        status instead of masking it to a plausible number; and the flat `ModelFlat`
        wire form with its pack/unpack pair.
  assignment — the optimal assignment (Hungarian / Jonker-Volgenant shortest augmenting
        paths) over a rectangular cost matrix, with both dual potential vectors as the
        complementary-slackness certificate, an explicit `perfect` flag, and forbidden
        pairings as a `Bool` mask rather than a big-M cost. The frozen
        `combinatorial.assignment_greedy` — the tree's only assignment kernel, and greedy
        without saying so at the call site — is reused as the warm start, the upper bound
        and an independent oracle, and `greedy_assignment_flat` reports its cost, its
        unplaced agents and its uncovered tasks.
  linear — an exact linearity extractor over an expression arena (a product of two
        variables, a variable divisor or a transcendental over a variable is a status
        naming the node, the opcode and the variable, never a linearised approximation)
        and a two-phase tableau simplex on general `n`: infeasible and unbounded are
        distinct statuses that carry NO objective, duals and reduced costs come back in
        the caller's sense with a right-hand-side range each, and cycling is handled by
        switching to Bland's rule on a detected stall. The frozen `lp_solve_2var` stays
        reachable as the two-variable fast path and is the suite's differential oracle.
  integer — branch and bound over `linear`, with an optimality gap that tells the truth.
        Every node's bound is one `lp_solve` call, branch bounds are rows TIGHTENED down
        the tree rather than stacked (so the per-node LP never grows with depth), the search
        is an explicit stack, and `feasible` / `proven_optimal` / `search_complete` are
        three separate booleans because a node limit that stops the search does not prove
        optimality. A truncated run reports its incumbent with the real remaining `gap`
        against a `best_bound` taken from the nodes it never opened, and an unbounded
        relaxation is its own status because it proves neither that the integer program is
        unbounded nor that it is infeasible. The frozen `combinatorial.knapsack_01_value`
        stays the exact DP for its one problem shape and is the suite's differential oracle.
  explain — the answer to the question a status code raises: which rows are tight at the
        optimum and what each is worth (with complementary slackness and strong duality
        checked, and a tight row priced at zero reported as degeneracy rather than as a
        contradiction); an IIS-style infeasibility core by deletion filtering, whose
        minimality is MEASURED with one re-solve per member instead of inferred from the
        filter's monotonicity; and a per-variable objective decomposition carrying the
        residual that proves the parts sum to the whole. Every feasibility question is an
        `lp_solve` status, because the frozen `linear_programming.is_feasible` reads every
        `>=` and `==` row as `<=`, indexes `b[i]` unguarded, and — taking a point — could
        only ever refute infeasibility, never establish it.

Design rules the package keeps
------------------------------
*An answer that does not exist is absent, not zero.* `linalg.mat_solve` returns an
all-zeros vector for a singular matrix, `linear_programming.lp_solve_2var` returns an
empty list for an infeasible program (and only ever handles two variables, and only
maximises), `linear_programming.dual_value` computes no dual at all — it calls
`lp_solve_2var` and hands back the PRIMAL optimum, with its arguments in a different
order — and `eigen_full.eigh_symmetric` returns empty for `n > 200`. Every driver here
carries a status code with one value per outcome, and "the value is 0.0" is never the
same return as "there is no value".

Public functions take and return only `List`/`Int`/`Float64`/`Bool`/`String` or a
struct declared in the same file, so the package lands in the runtime library contract
without a new message type. It is therefore *not* in `_SKIP_RUNTIME_DIRS`. The
struct-taking entry points that mention `ExprNode` (`OptModel`, `OptConstraint`,
`List[ExprNode]`) are deliberately Mojo-level only: `ExprNode` lives in `types.mojo`, so
a signature naming it cannot be marshalled, and the flat `ModelFlat` form is what
crosses the wire.
"""
