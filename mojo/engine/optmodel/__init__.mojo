"""
optmodel — a benchmark-shaped formulation plane over `optimization`'s exact solvers.

`optimization/` already holds the solving half: `lp_solve` with duals, `milp_solve`
with a verified incumbent, `infeasibility_core` that names WHICH rows conflict. What it
does not hold is the shape optimisation benchmarks actually hand over: a formulation —
variables with bounds and kinds, one objective, coefficient rows — plus a ground-truth
optimum to be judged against. This package is that missing layer, additive-only:

  formulation — the flat, typed container: dense rows, senses, rhs, per-variable
      kind/bounds. Validation is refusal-first (every defect is a named status with a
      WHERE index), the lowering compiles declared bounds onto the solvers' own
      `x >= 0` convention (shift by the lower bound, one row per upper bound), and the
      point audit re-checks a candidate point against EVERY original constraint, bound
      and integrality declaration — independently of any solver.
  solve — the bridge. Dispatches all-continuous formulations to `lp_solve` (certified
      by `explain.slackness_check`) and discrete ones to `milp_solve` (certified by
      `proven_optimal`), maps the answer back to the caller's variable space, re-audits
      it there, and converts every non-answer into a TYPED refusal: infeasible carries
      an `infeasibility_core` mapped back to original constraint/bound names, a node
      limit is `search_limit`, a failed self-check is never reported as a number.
  judge — the scoring half: a solved objective against a ground-truth optimum at two
      tolerances (strict 1e-4 relative, and the OptMATH-lineage 5%-of-rounded rule),
      and the end-to-end verdict driver that lands every formulation in exactly one of
      three buckets: VERIFIED, REFUSED, WRONG. WRONG is the bucket this package exists
      to keep empty — a plausible wrong number is the one output worse than no output.

Frozen kernels are called, never reimplemented: `model.sense_violation` is the one
definition of "this row fails", `linear`'s ulp budget constants are imported so a row
this package calls satisfied is a row `linear` calls satisfied, and every solve is
`optimization`'s own. Public functions take and return only flat lists, scalars and
same-file structs, so the package lands in the runtime library contract with no new
message type — the same contract shape as `optimization/` itself.
"""
