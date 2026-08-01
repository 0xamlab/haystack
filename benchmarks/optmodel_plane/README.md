# optmodel plane — solver-side ceiling harness

Measures the number the MM-OptBench recon says is publishable on its own terms: given
a benchmark-shaped **ground-truth formulation** (the hidden `instance_data` +
verified-optimum side of each instance), what fraction does the deterministic Algenta
plane — `mojo/engine/optmodel/` over the exact `optimization/` kernels — **solve and
verify**, what fraction does it **refuse with a type**, and how often does it emit a
**plausible wrong number** (target: zero, enforced by the gate).

Everything here is deterministic: no LLM, no network, no randomness without a stated
seed.

## Run

```bash
make bench-optmodel-plane                 # curated seeds: referee + plane + gate
make bench-optmodel-mirror                # full 780-instance benchmark mirror + seeds
python3 benchmarks/optmodel_plane/harness.py --mutate-gt --seeds-only    # gate demo 1
python3 benchmarks/optmodel_plane/harness.py --corrupt-wire --seeds-only # gate demo 2
python3 benchmarks/optmodel_plane/harness.py --fill-gt     # stamp referee optima (seeds)
```

The runner is generated Mojo (`build/optmodel_plane/runner_generated.mojo`) executed
through the real toolchain (`pixi run mojo run`, override the env with
`MOJO_ENV_DIR`). Instances travel over a checksummed token wire
(`build/optmodel_plane/wire_*.txt`) parsed at runtime, in chunks (`--chunk-size`,
`--parallel-chunks`), each chunk streaming to `wire_*.log`. Timing is printed with
the host load average beside it.

## The 780-instance benchmark mirror

MM-OptBench (arXiv:2605.12154) withholds its dataset until acceptance, but publishes
the complete design: 6 families x 26 subcategories x 3 structural difficulty tiers
x 10 = 780 solver-verified instances, the full taxonomy (their Table 3), per-family
construction pipelines (their App. E) with scale anchors, and the scoring rule
(objective matches the verified optimum; default tolerance 1e-6 with a 1e-3 absolute
floor for the continuous-objective location families). `make_mirror_instances.py`
mirrors all 26 subcategories deterministically with the paper's
rejection–regeneration protocol: every candidate is certified optimal by an
independent referee (SciPy/HiGHS) before admission, colouring instances are
regenerated until the verified chromatic number matches the target regime, and the
verified optimum is stamped as ground truth. As an extra prover, every all-binary
instance with <= 16 variables (120 of 780) was cross-checked by exhaustive
enumeration — generator, HiGHS, and brute force agree.

Honest deviations, all forced by the referee or the machine: hard-tier
scheduling/routing scales are trimmed to what HiGHS certifies in seconds (job-shop
hard is 6x4, not the paper's 10x6–8; TSP hard is 9 cities); inventory routing uses
the enumerated-route exact form; there are no visual carriers — this is the
solver-side mirror of the machine-readable half. Node budgets for the plane's exact
branch-and-bound are cell-scaled (~75s of solo search per instance, measured
1.9us/cell-node on big-M scheduling); raising them can only move REFUSED to
VERIFIED, never into WRONG, so the ceiling is a lower bound with respect to budget.

## The gates, in order

1. **Referee.** Every instance is independently re-solved by SciPy/HiGHS
   (`scipy.optimize.milp`). A solvable instance is admitted only if HiGHS proves
   optimality and agrees with the stated truth; `refuse_infeasible_rows` and
   `refuse_unbounded` must be reproduced as infeasible/unbounded. Different solver,
   different algorithm, different author — agreement is evidence, not a mirror.
2. **Expected bucket.** Curated seeds state `expect: verified/refused` and must land
   exactly there. Mirror instances state `expect: measure`: VERIFIED counts toward
   the ceiling, a typed REFUSAL counts against it (recorded, never hidden), WRONG
   always fails the gate. Counts are derived from the instance files, never
   hardcoded.
3. **The WRONG bucket must be empty**, and every VERIFIED objective must ALSO match
   the ground truth under the benchmark's published tolerance rule (1e-6 default,
   1e-3 absolute floor for location). `--mutate-gt` perturbs every stated optimum by
   10% and the run must FAIL with every solved instance landing in WRONG
   (demonstrated 2026-08-01: 16/16 WRONG, exit 1). `--corrupt-wire` flips one wire
   token after checksumming and the run must FAIL with a typed PARSE_FAIL
   (demonstrated 2026-08-01: checksum named the token, exit 1) — a framing slip can
   never become a silently different model.

## Measured ceiling (2026-08-01)

Full run: 800 instances (780 mirror + 20 seeds), every solvable one re-proved by the
HiGHS referee in 6.5s, then solved by the plane in 32 four-way-parallel chunks —
12,878s of aggregate solve time, ~95 min wall including one interrupted-and-resumed
chunk (`--resume`), loadavg 80–230 recorded throughout; per-instance p50 4.4ms,
p90 12.0s, max 732s (a budget-exhausting refusal, not a hang).

```
family                        n  verified  refused  wrong
combinatorial               123       123        0      0
location_cover_assign       153       151        2      0
network                     153       153        0      0
planning                    123       113       10      0
refusals (seed by-design)     4         0        4      0
routing                     122       114        8      0
scheduling                  122        91       31      0
TOTAL                       800       745       55      0
```

**Solver-side ceiling on the 780-instance mirror: 729/780 = 93.5% solved AND
verified** (both at strict 1e-4 relative and at the benchmark's official tolerance
rule), **with a wrong-number count of 0 across all 800** — the differentiating
claim, since the benchmark's own failure analysis shows published systems lose most
points to exactly the plausible-wrong-number bucket this plane refuses to emit. By
difficulty tier: easy 260/260 (100%), medium 256/260 (98.5%), hard 213/260 (81.9%).
The seed ceiling stays 16/16.

Every non-answer is a typed refusal, never a silent failure: 49 node-budget
`refused_search_limit` (the exact branch-and-bound's depth cap — a bigger budget can
only raise the ceiling, never corrupt it) and 2 `refused_uncertified` whose root LP
relaxation failed self-certification (`relaxation_failed`, both hard p-center).
Refusals concentrate exactly where exact search is genuinely deep: hard disjunctive
scheduling (job-shop hard 0/10, hybrid flow shop hard 2/10, RCPSP hard 4/10 and
medium 6/10, parallel machines hard 7/10), hard multi-product lot sizing 0/10, hard
9-city MTZ TSP 2/10, hard p-center 8/10. The deepest instance the plane VERIFIED
took 41,833 nodes. Verified per family (mirror only): network 150/150, combinatorial
120/120, location/cover/assign 148/150, routing 112/120, planning 110/120,
scheduling 89/120.

The measurement's own failure modes were re-demonstrated on the final code the same
day: `--mutate-gt` -> 16/16 WRONG, exit 1; `--corrupt-wire` -> typed PARSE_FAIL
naming the checksum drift, exit 1.

## Honest scope

The visual half of MM-OptBench has no public proxy and is out of scope by
construction: this measurement is the benchmark's own oracle-reading ablation run on
the deterministic plane — the upper bound ANY extraction layer (LLM or otherwise)
composed with this plane can reach on the solver side, and the paper reports that
even with oracle instance data the evaluated MLLMs solve almost nothing downstream
(math-specialized models: 0-1/780). A real pass@1 run additionally needs the
withheld dataset, a frontier MLLM for the text+visual extraction, and owner-gated
spend.
