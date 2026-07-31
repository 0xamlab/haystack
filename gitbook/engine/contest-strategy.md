---
icon: chess-clock
description: Simulate N competitors over discrete rounds and compare service-timing options under common random numbers, with simultaneous intervals and an explicit abstain.
---

# Contest simulation & service-timing decisions

`contest_strategy` answers one shaped question: **when should this agent stop for service?** It
simulates the whole field of competitors forward over the remaining rounds, evaluates several timing
options against the same simulated futures, and returns the contrast between them with honest intervals.

The shape recurs wherever agents compete over discrete rounds while a resource decays and a service
interruption resets it — delivery fleets deciding when to recharge, harvesters when to unload, crews when
to rotate, any process where stopping costs time now and buys performance later.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

params = runtime.execute("contest_strategy", "default_contest_params")["result"]
n = 12
board = runtime.execute(
    "contest_strategy", "option_board",
    [[90.0 + 0.12 * i for i in range(n)],   # per-agent rate
     [0.010] * n,                           # per-agent decay slope
     [2.5 * i for i in range(n)],           # elapsed so far
     [8.0] * n,                             # resource age
     [1.0] * n,                             # active
     3, 2, 30,                              # focal agent, target rival, rounds remaining
     params, 20000, 400, 42, 11],
)["result"]

board["v"][7]   # recommended option
board["v"][8]   # verdict: 0 STAY, 1 RECOMMENDED, 2 INCONCLUSIVE
```

## Functions

| Function | What it does |
|---|---|
| `option_board(...)` | Four service-timing options evaluated against shared futures. Returns per-option success probability, paired deltas, simultaneous intervals, a recommendation and a verdict. |
| `outcome_distribution(...)` | Full-field finishing-position distribution per agent — win, top-three and points-equivalent probabilities, plus expected position. |
| `default_contest_params()` | The parameter vector, with documented defaults. |
| `wear_penalty(decay, age, cliff_age, cliff_slope)` | Resource penalty: linear decay plus the cliff past a threshold. One definition, shared by both simulators. |
| `option_service_round(option)` | Maps an option index to the round it services on. |
| `contest_worker_count()` / `contest_strategy_version()` | Parallel width and the contract identifier. |

## Common random numbers, and why they are not optional

Comparing options by running each against its own random futures buries the contrast in sampling noise.
Every option here is evaluated against the **same** simulated world: the same incidents, the same
service-time draws, the same per-agent form. Only the decision differs.

The gain is measurable rather than assumed — the board reports its achieved variance ratio, typically
around **0.37**, which is a 2.7× effective replication gain over independent sampling.

Randomness is counter-based, so a draw is addressed by `(replication, round, agent, process)` rather than
consumed in sequence. That matters after options diverge: once one branch services and another does not,
sequential streams hand them different numbers and the pairing silently disappears. Exogenous draws stay
paired; endogenous events still differ, because the state differs.

## The intervals are simultaneous, and the board can decline

The board *selects* the best of several options, so marginal intervals overstate confidence. It resamples
whole replication rows jointly and uses a max-statistic, giving family-wise coverage.

It then applies an explicit abstention rule: recommend a service option only when its lower simultaneous
bound clears the practical threshold ε. Otherwise the verdict is **INCONCLUSIVE** — a statistically real
0.05-point edge does not justify an operational action, and a board that always answers is not applying
the rule.

## How many replications you need

More is not automatically better, and the useful number is empirical. Across 45 real decision states:

| replications | interval width | matches the N=50,000 answer |
|---|---|---|
| 1,000 | 4.37 pp | 87% |
| 10,000 | 1.36 pp | 93% |
| **20,000** | **0.97 pp** | **96%** |
| 50,000 | 0.61 pp | 100% |

Interval width tracks `1/√N` to within 1–2% at every level, which is the check that these are genuinely
sampling intervals. Below about 20,000 the recommendation itself starts moving with N — at that point the
board is partly reporting its random seed rather than its state.

## Verification

Directional sanity is asserted rather than assumed: with too few rounds remaining to repay the service
cost, servicing must never be recommended. Success probabilities are checked to sum to exactly 1.0, which
is what catches a lost update in the parallel reduction. Degenerate inputs — zero or negative
replications — return INCONCLUSIVE rather than NaN or a crash.

**Next:** model the decaying resource with [asset degradation state](degradation-state.md), or score the
resulting probabilities with [forecast scoring](forecast-scoring.md).
