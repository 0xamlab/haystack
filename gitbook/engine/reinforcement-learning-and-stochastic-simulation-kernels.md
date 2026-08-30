---
icon: dice
description: Tabular Q-learning, SARSA and value iteration over an explicit MDP, a linear-Gaussian Kalman filter, reservoir and weighted stream sampling, and constant-memory Count-Min/HyperLogLog sketches.
---

# Reinforcement learning and stochastic simulation kernels

Four modules for making a decision or an estimate when the truth arrives one noisy observation, one
episode, or one streamed item at a time. `reinforcement` learns or evaluates a policy over an explicit
Markov decision process by trial and error; `kalman` tracks a hidden linear state through a sequence of
noisy measurements; `reservoir` draws a statistically valid sample from a population too large, or too
transient, to hold in full; and `sketch` answers a frequency or cardinality question about a stream from
a table far smaller than the stream itself. None of the four imports another, and none of them returns a
status code — like the [mixture-of-experts and routing](mixture-of-experts-and-routing-kernels.md)
family, this is a thematic grouping (sequential decisions and estimates under uncertainty), not a
shared-code one.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# G = 1 + 0.9*1 + 0.9^2*1 = 2.71 -- a 3-step episode discounted at gamma=0.9
runtime.execute("reinforcement", "discounted_return", [[1.0, 1.0, 1.0], 0.9])["result"]
# 2.71

# a 1D Kalman smoother tracking a step change from 0 to 10 across five noisy readings
runtime.execute("kalman", "kalman_smooth_1d",
                [[0.0, 10.0, 10.0, 10.0, 10.0], 1.0, 1.0])["result"]
# [0.0, 6.666666666666666, 8.75, 9.523809523809524, 9.818181818181818]
```

## The modules

| Module | What it does |
| --- | --- |
| `reinforcement` | Tabular reinforcement learning over an explicit state/action MDP: off-policy Q-learning and on-policy SARSA, exact value iteration and policy evaluation by fixed-point iteration, ε-greedy action selection, greedy policy extraction from a Q-table, one-step TD(0) error, and discounted return. |
| `kalman` | A general linear-Gaussian Kalman filter over an arbitrary-dimension state: predict/update steps on an explicit `KalmanState` (mean vector plus covariance matrix), a self-contained 1D smoother for a scalar measurement sequence, and the dense-matrix arithmetic (multiply, transpose, add, subtract, scale, identity, 2x2 inverse, matrix-vector product) the filter is built from. |
| `reservoir` | Seven ways to draw a sample from a fixed or streaming population: Vitter's Algorithm R for uniform reservoir sampling, Efraimidis-Spirakis weighted reservoir sampling, index-only reservoir sampling, bootstrap (n-with-replacement over n items), systematic (every `n/k`-th) sampling, and plain with/without-replacement draws via Fisher-Yates. |
| `sketch` | Two constant-memory approximate structures built from scratch: a Count-Min Sketch (`CountMinSketch`) for approximate item-frequency queries that never under-count, and a HyperLogLog (`HyperLogLog`) for approximate distinct-count cardinality estimation, plus the bit-mixing hash and leading-zero-count primitives both are built from. |

## Reinforcement learning: a 3-state MDP, worked three ways

`mojo/tests/libs/test_reinforcement.mojo` is auto-generated and calls only three of the eight functions
(`epsilon_greedy_action`, `td_error`, `discounted_return`) at the literal input `0.5`, checking finiteness
and nothing else. The real coverage is a hand-written suite in `tests/mojo/test_wave59.mojo`, built
around one fixed 3-state MDP:

```
rewards[0] = [0.0, 1.0]     # s0: a0 -> s1 (reward 0), a1 -> s2 (reward 1)
rewards[1] = [10.0, 0.0]    # s1: a0 -> s2 (reward 10), a1 -> s1 (reward 0)
rewards[2] = [0.0, 0.0]     # s2 is terminal, both actions self-loop

transitions[0] = [1, 2]
transitions[1] = [2, 1]
transitions[2] = [2, 2]
```

`value_iteration(3, 2, rewards, transitions, gamma=0.9, tol=1e-8)` converges to `V = [9.0, 10.0, 0.0]`:
the terminal state `V[2]` is `0` by construction, `V[1] = max(10 + 0.9*0, 0 + 0.9*10) = 10` (take the
direct reward to the terminal state rather than loop), and `V[0] = max(0 + 0.9*10, 1 + 0.9*0) = max(9, 1) = 9`
(the low-reward-now, high-reward-later path through `s1` beats the immediate `+1` to the
terminal state). `policy_evaluation` run against the greedy policy `[0, 0, 0]` (always take action `a0`)
recovers the identical `V[0] = 9`, `V[1] = 10` by the same fixed-point iteration — the two functions
share no code, but they agree because the greedy policy `value_iteration` would extract from this `V`
is exactly the policy `policy_evaluation` was handed.

`q_learning` and `sarsa` reach the same table by trial and error instead of the closed-form recursion:
starting every episode from `s0`, running with `alpha=0.1`, `gamma=0.9`, `epsilon=0.1` for 500 episodes
drives `Q[1][0]` — the value of taking the direct-to-terminal action from `s1` — above `5.0` (the real
test's own threshold; the exact value depends on the ε-greedy exploration path taken, see below) on its
way toward the fixed point of `10.0`. `policy_from_q` then reads a policy straight off any Q-table by
per-row `argmax` — given `Q = [[1.0, 5.0], [10.0, 3.0], [0.0, 0.0]]`, it returns `[1, 0, 0]`: action `1`
in state `0` (`5.0 > 1.0`), action `0` in state `1` (`10.0 > 3.0`), and action `0` in state `2` — a tie,
broken by taking the first index, which is why a genuinely indifferent state cannot be told apart from
one where every other action was simply never explored.

`epsilon_greedy_action` is the shared mechanism: at `epsilon=0.0` it is pure `argmax` and nothing
else — ten calls against the same `Q_state` all return the same action, deterministically, because the
random draw that would trigger exploration is gated behind `r < epsilon` and `epsilon=0.0` can never
satisfy `r < 0.0` for any `r` returned by `random_float64()` (which is confined to `[0.0, 1.0)`).

### `td_error` and `discounted_return` are the two that need no table at all

`td_error(reward, gamma, v_next, v_current)` is the one-line formula `reward + gamma*v_next - v_current`;
`td_error(5.0, 0.9, 10.0, 8.0) = 5.0 + 9.0 - 8.0 = 6.0`, and the zero case
`td_error(0.0, 0.9, 0.0, 0.0) = 0.0`. `discounted_return(rewards, gamma)` sums `rewards[t] * gamma^t`;
for a 3-step episode of unit rewards at `gamma=0.9`, `1.0 + 0.9 + 0.81 = 2.71` (the code example above),
and a single-reward episode returns that reward unchanged regardless of `gamma`.

### Shape safety: three untrusted counts, one clamp

`q_learning`, `sarsa`, `value_iteration`, and `policy_evaluation` all take `n_states` (and the first two
also `n_actions`) as a caller-supplied `Int` that indexes directly into `rewards` and `transitions`.
Reading the source, all four clamp the working state count down to the *shorter* of `n_states` and
`len(rewards)`/`len(transitions)` before doing anything else — and `value_iteration` and `q_learning`/
`sarsa` additionally clamp the action count to the shortest row across both tables — rather than trust
the caller's count and read past the end of a too-short payload, which in this codebase is an
uncatchable abort rather than a raised exception. A transition target outside the clamped state range
is refused outright, returning an empty table instead of indexing a state that does not exist. This is
the same defensive posture documented for `mixture_of_experts` and its siblings, applied here to a
different family.

## Kalman filtering: predict, update, and where it stops matching `degradation_state`

`kalman_predict` and `kalman_update` are the two textbook steps, and `tests/mojo/test_wave21.mojo` pins
concrete matrix arithmetic (identity, multiply, transpose, 2x2 inverse verified by `M * M⁻¹ ≈ I`) before
exercising the filter itself. Starting from `state0 = KalmanState(x=[0.0, 1.0], P=I(2))` — position 0,
velocity 1 — with a constant-velocity model `F = [[1, 1], [0, 1]]` and process noise `Q = 0.1*I(2)`:

```python
state = runtime.execute("kalman", "kalman_predict", [
    {"x": [0.0, 1.0], "P": [[1.0, 0.0], [0.0, 1.0]]},
    [[1.0, 1.0], [0.0, 1.0]],
    [[0.1, 0.0], [0.0, 0.1]],
])["result"]
state["x"]   # [1.0, 1.0]        -- x' = F*x
state["P"]   # [[2.1, 1.0], [1.0, 1.1]]   -- P' = F*P*F^T + Q, grown from I(2)
```

Independently re-deriving that same arithmetic in plain Python (`F*P*Fᵀ + Q`, no library) reproduces
`[[2.1, 1.0], [1.0, 1.1]]` exactly. Feeding a position measurement of `2.0` (`H = [[1, 0]]`,
`R = [[0.5]]`) through `kalman_update` moves the state toward, but not onto, the measurement — the
predicted position was `1.0`, and the updated position comes out at `1.8076923076923077`: closer to the
measurement than to the prediction, because the measurement noise (`0.5`) is smaller than the predicted
position variance (`2.1`), so the Kalman gain weights the new observation more heavily. The updated
covariance shrinks from `2.1` to `0.40384615384615385` at that same cell — an update always reduces
uncertainty in the observed direction, never grows it, for a linear-Gaussian model with a well-posed
gain.

`kalman_smooth_1d` is a separate, self-contained 1D special case — it does not call `kalman_predict` or
`kalman_update` internally, it re-derives the scalar filter directly (`k = p_pred / (p_pred + measurement_var)`,
one gain per step). Two zero variances is the one input it refuses outright,
returning the raw measurements unchanged rather than dividing by a zero gain denominator; any other
non-negative pair of variances runs the recursion.

### Real matrix inversion is 1x1 or 2x2 only

`mat_inv_2x2` is exactly what its name says — reading the source, `kalman_update`'s internal `_mat_inv`
dispatches to a 1x1 scalar inverse or `mat_inv_2x2`, and nothing else; there is no general `n x n`
inverse anywhere in this module. `kalman_update` reads `m = len(z)` (the measurement dimension) and
refuses to run at all when `m > 2`, so the innovation covariance `S` it needs to invert is guaranteed
to fit one of the two cases it can actually solve. A caller with a 3-dimensional measurement gets the
state and covariance back unchanged, not a wrong answer from an inverse the code cannot compute.

### This is not `degradation_state`

[Asset degradation state](degradation-state.md)'s `pace_kalman_update`/`pace_kalman_run` are also
described as a Kalman filter, and its own "Next" line points toward "richer state" filtering — this page
is that pointer's destination, and it is worth being precise about the relationship because the two do
not share a line of code. Reading `mojo/engine/degradation_state.mojo`, it imports nothing from
`kalman.mojo`; it is a hand-rolled scalar filter hardcoded to a specific 2-state model
(`[pace offset, degradation slope]` observed through `H = [1, age]`), with domain-specific machinery
this module has no equivalent of — wear-slope clamping, load correction for a depleting resource, irregular-arrival
handling, and a fitted non-linear end-of-life cliff. `kalman` is the reverse trade: it supports an
arbitrary-dimension `KalmanState` and caller-supplied `F`/`H`/`Q`/`R` matrices for any linear-Gaussian
model, but has none of `degradation_state`'s domain modelling — no clamping, no cliff, no notion of
"usage age" at all. Building `degradation_state`'s model on top of this module's general `kalman_predict`
/`kalman_update` would work for the 2x2 case (both dimensions clear the `m <= 2` ceiling above), but that
is not what the codebase actually does.

## Reservoir and streaming sampling

All seven functions return values drawn from the input, never synthesized — `reservoir_sample`,
`bootstrap_sample`, `systematic_sample`, `sample_with_replacement`, and `sample_without_replacement` all
return entries copied verbatim out of `data`/`stream`, and `reservoir_sample_indices` returns positions
rather than values so the caller can look up whatever else lives at that index.
`tests/mojo/test_wave27.mojo` pins the structural guarantees directly: sample length always equals the requested
`k` (or the full population when `k >= n`), every returned value traces back to the input, and the
"without replacement" variants (`reservoir_sample_indices`, `sample_without_replacement`) never repeat
an index or a value.

```python
data = [float(i) for i in range(1, 21)]   # 1.0 .. 20.0

s = runtime.execute("reservoir", "reservoir_sample", [data, 5])["result"]
len(s)   # 5 -- always, drawn uniformly from the 20 values by Vitter's Algorithm R

full = runtime.execute("reservoir", "reservoir_sample", [data, 100])["result"]
len(full)   # 20 -- k >= n returns the whole population, not an error
```

`weighted_reservoir_sample` implements Efraimidis-Spirakis: each item's key is `log(u) / weight` for a
fresh uniform draw `u`, and the `k` items with the largest keys survive — a heavier weight makes a small
`u` (which produces a very negative key) less damaging, so heavier items are kept preferentially without
ever needing to sort the whole stream. Reading the guard clause directly: `k <= 0` or a `weights` list
whose length does not match `stream` returns an empty list rather than indexing a key array that was
never populated — an uncatchable abort in this codebase, avoided the same way `reinforcement`'s shape
clamps avoid one.

### No seed, anywhere in this module — a real, load-bearing gap

Every one of these seven functions draws from `std.random.random_float64()`, Mojo's process-global RNG,
and none of the seven accepts a seed parameter. That is a genuine difference from most of the rest of
this corpus: [Streaming sketches](streaming-sketches.md) derives every hash and every compaction coin
from an explicit, caller-supplied seed specifically so two runs reproduce bit-for-bit;
[Bit-level and hashing kernels](bit-level-and-hashing-kernels.md)'s `counter_rng` is built entirely
around the idea that a draw is a pure function of its coordinates; and `inference.resample`/
`evaluation.resample` (see below) exist *because* an earlier, unseeded bootstrap implementation could
not be reproduced. `reservoir.mojo` has none of that: two calls to `reservoir_sample(data, 5)` on
identical input will, in general, return different subsets, and there is no argument to pass to make
them agree. A caller that needs a reproducible sample from this codebase should reach for the seeded
tools instead, not for this module.

### This is not the corpus's other "bootstrap"

`reservoir.bootstrap_sample` — draw `n` items with replacement from `n` items, nothing more — shares a
name with, but is not called by, the statistical bootstrap machinery documented elsewhere:
`inference.resample`'s `bootstrap_mean_ci`/`bootstrap_median_ci`/`bootstrap_test`,
`evaluation.resample`'s `bootstrap_metric_ci_flat`, and `causal_inference.estimators`'s bootstrap
interval. Grepping those modules' source for `reservoir` turns up nothing; `inference.resample`'s own
docstring is explicit that it exists because a separate, frozen module (`stats_bootstrap`, not this one)
draws from the same unseeded `random_float64()` this page's `reservoir` module uses, and that a
confidence interval that changes between runs cannot be used in a decision that has to be explained. So
there are, in effect, two unrelated notions of "bootstrap" in this codebase: this module's, a plain
resampling primitive with no seed and no statistic attached, and the inference/evaluation family's, a
seeded, reproducible confidence-interval procedure built for exactly the case this one is unsuited to.

## Probabilistic sketches: two structures, and a real bug in one of them

`CountMinSketch` and `HyperLogLog` answer different questions — "how many times has this exact item
been seen" versus "how many distinct items have been seen" — and neither is a Bloom filter:
[Bit-level and hashing kernels](bit-level-and-hashing-kernels.md)'s `bloom_counting` answers a third
question, "have I seen this item at all" (with a bounded false-positive rate and the ability to
un-remember an item), and shares no code with either structure here.

```python
sketch_state = runtime.execute("sketch", "create_cms", [100, 5])["result"]
sketch_state = runtime.execute("sketch", "cms_add", [sketch_state, 42, 3])["result"]["mutated_args"]["sketch"]
sketch_state = runtime.execute("sketch", "cms_add", [sketch_state, 7, 1])["result"]["mutated_args"]["sketch"]

runtime.execute("sketch", "cms_query", [sketch_state, 42])["result"]   # 3
runtime.execute("sketch", "cms_query", [sketch_state, 7])["result"]    # 1
runtime.execute("sketch", "cms_query", [sketch_state, 99])["result"]   # 0 -- never added
```

`hll_count` estimates cardinality from the harmonic mean of per-register leading-zero-run maxima, with
a small-range correction below `2.5 * m` registers. Adding the 5 distinct integers `1..5` to a
16-register sketch (`create_hll(4)`) and calling `hll_count` gives `5.995095191062571` against a true
count of `5`; a fresh 16-register sketch fed 1,000 distinct integers instead reports `911.7...` (accuracy degrades as the
stream outgrows 16 registers — the real test suite uses `create_hll(10)`, 1,024 registers, for its
1,000-item case and gets `1004.4`, within the 30% tolerance it asserts). Adding the same item 1,000
times to a fresh sketch reports an estimate near `1.0` — duplicates barely move the count at all,
which is the entire point of a distinct-count estimator.

### `cms_hash`'s frozen row seeds collapse `depth` to `1`, and it is measured, not alleged

This is documented directly in `mojo/engine/streaming/frequency.mojo`'s own docstring, and reproducing
its arithmetic confirms every number in it. `create_cms(width, depth)` seeds row `d` as
`d * 1000003 + 7` — every seed is congruent to `7` modulo `1000003`. `cms_hash(item, seed, width)`
reduces `(item * seed + 17) mod 1000003` before taking it `mod width`, and because every row's seed is
congruent mod `1000003`, every row computes the *same* column for the same item:
`cms_hash(5, 7, 100) == cms_hash(5, 1000010, 100) == cms_hash(5, 2000013, 100) == 52`, verified by
direct computation. A depth-`d` Count-Min sketch is supposed to take the minimum over `d` independent
hash rows so its over-estimate bound holds with probability `1 - e^-d`; with every row identical, the
minimum is taken over one number repeated `d` times, and that guarantee is unearned. The practical
consequence: `create_cms(4096, 4)`, 1,000 additions of item `0`, then `cms_query(2000006)` — an item
never added — returns `1000`, not `0`, because `0` and `2000006` collide in *every* row at once
(`cms_hash` maps both to column `17` in a 4,096-wide table, in all four rows). `sketch.mojo` is part of
this codebase's frozen kernel baseline, so this defect is not fixed here; `streaming.frequency`
(documented on [Streaming sketches](streaming-sketches.md)) works around it by keying each row's input
independently through a seeded generator before handing it to the frozen `cms_hash` for the final column
reduction, rather than trusting `create_cms`'s row seeds. A caller reaching `sketch.create_cms`/
`cms_add`/`cms_query` directly inherits the defect above it: `depth` still costs the same memory and
time, but does not currently buy the independent-row confidence bound the algorithm assumes.

`HyperLogLog` has no equivalent defect. `streaming.distinct`'s own docstring confirms it calls
`sketch.create_hll`, `sketch.hll_add`, `sketch.hll_count`, and `sketch.leading_zeros` directly and
reimplements none of that arithmetic — it adds a keyed hash (`sketch.hll_hash` takes no seed at all, so
two independent HLL deployments in this raw module are never distinguishable by seed), a register-wise
merge, and a flat snapshot format on top, none of which changes what `hll_add`/`hll_count` compute. So a
caller of this module's raw `hll_add`/`hll_count` gets the same cardinality-estimation arithmetic
`streaming.distinct` uses under the hood — just without a seed, without merge, and without a snapshot
format to survive a restart.

## Verification

`kalman` has a real, hand-written pinned suite in `tests/mojo/test_wave21.mojo`: matrix identity,
multiply, transpose and inverse are checked against concrete numbers, and `kalman_predict`/
`kalman_update`/`kalman_smooth_1d` are exercised on the constant-velocity example above.
`reservoir` and `sketch` share a real, hand-written suite in `tests/mojo/test_wave27.mojo`, which checks
structural invariants (length, "values come from the input", "no repeats") for every reservoir function
and functional invariants (`cms_query >= true count`, `hll_count` within a stated tolerance, exact
`leading_zeros` values) for both sketch structures. `reinforcement` has a real, hand-written suite in
`tests/mojo/test_wave59.mojo`, built around the fixed 3-state MDP reproduced above, with `value_iteration`
and `policy_evaluation` pinned to concrete `V` values and `q_learning`/`sarsa` checked for improvement
past a stated threshold (not a pinned value, since both are stochastic — see above). The auto-generated
smoke tests in `mojo/tests/libs/test_kalman.mojo`, `test_reservoir.mojo`, `test_sketch.mojo`, and
`test_reinforcement.mojo` exist alongside these and check only a handful of functions each for
finiteness or non-crashing; the wave suites are the real coverage, and every worked number on this page
was either lifted from one of them directly or independently recomputed from the formulas in
`mojo/engine/kalman.mojo`, `reinforcement.mojo`, `reservoir.mojo`, and `sketch.mojo`.

**Next:** see the domain-specific two-state filter this page's `kalman` is not, on
[Asset degradation state](degradation-state.md), or the seeded, mergeable, snapshot-capable production
versions of this page's sketches on [Streaming sketches](streaming-sketches.md).
