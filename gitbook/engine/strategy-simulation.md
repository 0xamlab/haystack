---
icon: chess-knight
description: Compare strategies on common random numbers, rank them with the multiplicity corrected, and get "no significant difference" as an answer instead of a coin flip.
---

# Strategy comparison & simulation

Five kernel modules that answer one question honestly: **of these strategies, which is better, and
is the difference real?** All run as compiled kernels inside the runtime that ships with the SDK —
there is nothing to start and nothing to install separately.

Two things make a strategy comparison worth acting on, and neither is the arithmetic. The first is
that every strategy faced the **same** sampled futures, so the difference you measure is the
strategies and not the sampling. The second is that the ranking is allowed to say **the strategies
are indistinguishable** — because a ranking that always names a winner is a random number generator
with extra steps.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Three strategies, five shared scenarios each, strategy-major.
outcomes = [
    10.0, 11.0, 12.0, 13.0, 14.0,   # strategy 0
     9.0, 10.0, 11.0, 12.0, 13.0,   # strategy 1
     9.0,  9.0,  9.0,  9.0,  9.0,   # strategy 2
]

result = runtime.execute(
    "strategy.tournament", "tourney_rank_flat",
    [outcomes, 3, 5, 0.95, 0.05, 0, True, 1e-12],   # 95% intervals, alpha 0.05, Bonferroni
)["result"]

result["verdict"]                     # 2  — a_better: one strategy beats every other
result["winner"]                      # 0
result["rank"]                        # [1, 2, 2]   <- a tie expressed AS a tie
result["mean"]                        # [12.0, 11.0, 9.0]
result["ci_lower"][0]                 # 10.036756838270254
result["ci_upper"][0]                 # 13.963243161729746
result["n_comparisons"]               # 3
result["method_name"]                 # "bonferroni"
result["n_significant"]               # 2
result["n_significant_uncorrected"]   # 3   <- the correction changed a verdict
result["pair_p"][2]                   # 0.04742065566669712
result["pair_adjusted"][2]            # 0.14226196700009136
```

Read the last four lines together. Three strategies is three comparisons, and one of those
comparisons had a p-value of 0.047 — "significant" at 0.05 if you look at it alone. Adjusted for the
fact that you looked three times, it is 0.142, and the pair is reported as **no significant
difference**. Both numbers are in the result, so you can see the multiplicity was handled instead of
taking it on trust.

## The modules

| Module | What it does |
| --- | --- |
| `strategy.crn` | scenario generation on common random numbers, policy replay over a horizon, and the audits that measure the pairing rather than claim it |
| `strategy.tournament` | the paired comparison, the per-strategy interval, the family-wise correction, and the ranking with ties as ties |
| `strategy.policy` | the flat policy encoding — constant, threshold, tabular and mixed — with the arity computed from the environment so a policy the environment cannot evaluate is refused, not scored |
| `strategy.equilibrium` | pure and mixed equilibria, exploitability, adaptive play, and dominated actions, each carrying whether it is exact or approximate |
| `strategy.contract` | the status vocabulary, the ceilings, the work budget, the named random-number streams and the coordinate assignment — the shared refusals, callable on their own so you can validate a request before sending it |
| `game_theory` | the closed-form 2x2 equilibrium and dominated-strategy solver that `strategy.equilibrium` calls directly whenever an exact answer exists, so nothing iterates where it doesn't have to |

## Common random numbers, and why the variance drops

Comparing two strategies on independently sampled scenarios measures the sampling noise as much as
it measures the strategies. Comparing them on the **same** scenarios measures only the strategies.

That is not a stylistic preference, it is a measurement. Two threshold policies over a 64-step
discounted horizon and 200 scenarios:

| | variance of the difference | 95% interval half-width |
| --- | --- | --- |
| paired — both policies on the same scenario | 0.048869 | 0.030825 |
| unpaired — the second policy on its own scenarios | 0.311092 | 0.077773 |

Same problem, same number of scenarios, same work. The unpaired comparison carries **6.4x the
variance** and an interval **2.5x wider**. Everything you would spend on more scenarios to close
that gap, pairing gives you for free.

Pairing is only possible because the generator is **addressed** rather than sequential: a draw is a
pure function of its coordinates — which scenario, which time step, which exogenous factor — so two
strategies that make different numbers of decisions still agree on the value at a given coordinate.
A stateful generator cannot do this. The moment one strategy consumes one extra draw, every
subsequent number diverges and the comparison silently becomes unpaired while still looking paired.

The strategy index appears in **no** environment coordinate. That single omission is the whole
mechanism, and it is enforced by the shape of the call: there is no argument by which a scenario
draw could depend on which strategy is being evaluated.

### The pairing is a number in the result, not a promise

Every comparison reports two variances:

```python
pair = runtime.execute(
    "strategy.tournament", "tourney_paired_diff_flat",
    [outcomes, 3, 5, 0, 2, 0.95, 0.05, True, 1e-12],
)["result"]

pair["paired_variance"]          # Var(a - b) over the shared scenarios
pair["unpaired_variance"]        # Var(a) + Var(b) — the same difference on independent draws
pair["variance_ratio"]           # unpaired / paired, ABSENT when the paired variance is zero
pair["paired_variance_lower"]    # did pairing actually buy anything here
```

`Var(a - b) = Var(a) + Var(b) - 2 Cov(a, b)`, so the first is below the second exactly when the
shared scenarios induced positive covariance — which is the entire reason to pair. If you hand in an
outcome matrix whose columns are **not** the same scenario, the ratio comes back at about 1.0 and
tells you so.

It is reported and not enforced, deliberately. A constant strategy has zero variance, so
`Var(a - b) = Var(b) = Var(a) + Var(b)` exactly: the ratio is 1.0 under *perfect* pairing. A ranking
that refused to run unless every pair showed a strict reduction would refuse a correct tournament
that happens to contain a strategy that always does the same thing.

## "No significant difference" is an answer

There are four verdicts, and all four are reachable:

| Verdict | Meaning |
| --- | --- |
| `undecided` (0) | the comparison could not be **made** |
| `no_significant_difference` (1) | the comparison was made and the two are indistinguishable at this alpha, after correction |
| `a_better` (2) | the corrected p-value rejects, and the first strategy is ahead |
| `b_better` (3) | the corrected p-value rejects, and the second is |

"We could not tell" and "they are the same" are different findings and never collapse into each
other. A tournament reports `decided` alongside its verdict for exactly that reason.

At tournament level:

* **every** comparison non-significant gives `no_significant_difference`, no winner, and every
  strategy at rank 1;
* exactly one strategy significantly ahead of **all** the others gives `a_better` and names the
  `winner`;
* significant pairs that do not produce a single strategy ahead of everyone give `undecided` — a
  partial order genuinely does not have a winner, and resolving it in favour of whoever happens to
  sit at rank 1 would report a preference that was never measured.

Two strategies that are truly interchangeable come back as a tie with the noise still in it. Two
copies of the same strategy come back as a tie exactly: every difference is 0.0, so the test
statistic is `0/0`, and the answer is a p-value of 1.0 with the statistic reported **absent** rather
than a fabricated large number or an unserialisable one.

## Ranks, and ties as ties

`rank[s]` is one plus the number of strategies that are significantly better than `s` after
correction. Two strategies nobody beats therefore share rank 1 — a tie is one number appearing
twice, not an arbitrary order between them. `n_at_rank_1`, `n_distinct_ranks` and
`n_undecided_pairs` sit beside the ranks, because a ranking built from the decided relation should
say how much of that relation is unknown.

## Refusal, not partial credit

If any strategy's interval cannot be formed, or any pair's p-value cannot be computed, the **whole**
tournament is refused. A ranking over the strategies that happened to succeed names the winner of a
competition the others were removed from, and a correction applied to a shrunken family divides by
the wrong number of comparisons as well.

Every refusal is typed and none of them can be mistaken for a result — the per-strategy lists come
back **empty** rather than zero-filled, because an empty list is the absence of a measurement and a
zero-filled one is a measurement:

| Situation | Status |
| --- | --- |
| fewer than two replications — a mean exists, an interval does not | `too_few_replications_for_an_interval` |
| fewer than two strategies — nothing to rank | `too_few_strategies_to_compare` |
| a non-finite outcome anywhere in the block | `non_finite_input` |
| the block is not the shape you declared | `flat_block_is_not_that_shape` |
| a strategy index the payload does not contain | `count_exceeds_list_length` |
| comparing a strategy with itself | `no_spread_to_test` |
| a confidence level or alpha outside `(0, 1)` | `confidence_level_out_of_range` |
| a correction method outside the vocabulary | `unknown_multiplicity_method` |
| a request that fits in memory but not in the time budget | `work_budget_exceeded` |

That last one is the one worth knowing about. A thousand strategies at two replications is a
two-thousand-cell block — trivially small — and it is refused, because ranking it means a thousand
Student-t quantile inversions and half a million paired tests. The cost of a comparison is not the
size of its input, and a request that is accepted and then runs for a wall-clock minute is
indistinguishable, from where you are sitting, from one that never comes back. You can ask what a
shape would cost before you send it:

```python
charge = runtime.execute(
    "strategy.tournament", "tourney_work_charge", [1024, 2],
)["result"]     # -1: no such number — this shape is over the budget
```

## Two routes to the same interval

The paired comparison reports a Student-t interval on the mean difference, which assumes the
differences are roughly normal. A percentile bootstrap makes no such assumption and is available on
the same data, seeded so the interval reproduces bit-for-bit:

```python
boot = runtime.execute(
    "strategy.tournament", "tourney_paired_bootstrap_flat",
    [outcomes, 3, 5, 0, 2, 0.05, 400, 11],   # alpha, 400 resamples, seed 11
)["result"]

boot["lo"], boot["hi"]       # the interval
boot["excludes_zero"]        # the verdict-shaped reading of it
boot["rng_version"]          # the generator that produced it, for the record
```

The resample draws a **scenario index** and takes both strategies' outcomes at that index, so the
pairing survives the resample. Resampling the two strategies independently would destroy the
covariance the shared scenarios created — which is the thing being measured.

When the two intervals disagree, that disagreement is the finding.

## Equilibria, and whether they are exact

`strategy.equilibrium` solves games with any number of players between two and eight and any number
of actions up to 1024. A game is one flat payoff tensor, player-major: player `i`'s payoff for joint
profile `g` sits at `payoffs[i * profiles + g]`, and a profile is the action tuple read as a
mixed-radix number with player 0 most significant. So the Prisoner's Dilemma — action 0 cooperate,
action 1 defect — is eight numbers, the row player's four followed by the column player's four.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

prisoners_dilemma = [3.0, 0.0, 5.0, 1.0,      # player 0: CC, CD, DC, DD
                     3.0, 5.0, 0.0, 1.0]      # player 1: CC, CD, DC, DD

report = runtime.execute(
    "strategy.equilibrium", "eq_pure_nash_flat",
    [prisoners_dilemma, 2, 2, 0.0],
)["result"]

report["n_equilibria"]   # 1
report["first_profile"]  # 3   <- (defect, defect)
report["residual"]       # 0.0
report["exactness"]      # 1   closed_form: the enumeration was exhaustive
```

The enumeration checks every profile against every player's alternatives, which is why **"this game
has no pure equilibrium" is an answer** and not a solver giving up:

```python
matching_pennies = [ 1.0, -1.0, -1.0,  1.0,
                    -1.0,  1.0,  1.0, -1.0]

report = runtime.execute(
    "strategy.equilibrium", "eq_pure_nash_flat",
    [matching_pennies, 2, 2, 0.0],
)["result"]

report["n_equilibria"]  # 0
report["has_first"]     # False
report["residual"]      # 2.0   <- and here is how close the closest profile gets
```

`residual` is the smallest amount, over all profiles, that any single player can still gain by
walking away. At 2.0 it is telling you the losing player at every profile moves from -1 to +1, so
this game needs mixing. A report that could only say "found one" or "found nothing" would have
thrown that number away.

### Every equilibrium carries how strong the claim is

`exactness` is a statement about the answer you are holding, not about the algorithm's reputation:

| `exactness` | Meaning |
| --- | --- |
| `closed_form` (1) | a closed form or an exhaustive search produced it **and** its measured exploitability is inside your tolerance — an equilibrium, verified |
| `approximate_with_residual` (2) | it is an eps-equilibrium and `residual` is eps |
| `unknown` (0) | the exploitability could not be computed, so no claim is made and `has_residual` is `False` |

The residual is the exploitability of the profile returned: the largest amount any one player gains
by deviating. It comes from a function you can call yourself on the strategy you were handed, so the
claim is checkable rather than asserted:

```python
half = [0.5, 0.5, 0.5, 0.5]        # both players flip a fair coin

audit = runtime.execute(
    "strategy.equilibrium", "eq_exploitability_flat",
    [matching_pennies, 2, 2, half, 0.0],
)["result"]

audit["residual"]        # 0.0
audit["is_equilibrium"]  # True
audit["value"]           # 0.0    the value of matching pennies
audit["gains"]           # [0.0, 0.0]
```

### Where an exact answer exists, nothing iterates

A two-by-two game goes to the exact closed form in `game_theory` — solving it by iteration would
return an approximation to an answer the engine already has exactly. Above that shape the solver is
regret matching, and it says so:

```python
solved = runtime.execute(
    "strategy.equilibrium", "eq_solve_flat",
    [matching_pennies, 2, 2, 500, 0.0, False],
)["result"]

solved["method"]      # 1   the closed form ran, not 500 iterations
solved["iterations"]  # 1
solved["strategy"]    # [0.5, 0.5, 0.5, 0.5]
solved["residual"]    # 0.0
```

If you need an exact equilibrium and the shape has no closed form, say so and get a refusal instead
of an approximation you would have to inspect to discover was one — that is the last argument of
`eq_solve_flat`, and above 2x2 it returns `an_exact_answer_was_required_and_only_an_approximate_one_exists`.

Regret matching and fictitious play are both available directly, both report the exploitability of
the average they converged to, and both are `approximate_with_residual` even when the residual comes
out at zero. On matching pennies regret matching reaches 0.5/0.5 with residual 0.0 in 200
iterations; fictitious play on the same game is still at 0.005 after twenty thousand. The residual is
what tells you that, and it is the reason a converged flag on its own is not enough.

There is no randomness anywhere in these solvers. Ties between equally-good actions go to the lowest
action index, a rule the engine will name for you (`eq_tiebreak_rule`) so a stored result can record
what produced it.

### Dominated actions, and sequential best response

```python
dominance = runtime.execute(
    "strategy.equilibrium", "eq_dominated_actions_flat",
    [prisoners_dilemma, 2, 2, 0],
)["result"]

dominance["dominated"]    # [True, False]   cooperate is strictly dominated
dominance["n_dominated"]  # 1
```

Two-player games are decided by the strictly-dominated check in `game_theory`, including for the
column player — the matrix that player sees is built and handed to the same kernel. Three players and
up use a tensor scan, and `method` in the result says which one ran.

Best-response dynamics is there for the question "does myopic play settle here". On the Prisoner's
Dilemma it reaches (defect, defect) in two rounds. On matching pennies it cycles forever, and the
result is a refusal — `iteration_limit_reached_without_convergence` — that still reports the profile
it stopped on and that profile's 2.0 residual. Returning the last profile of a cycle as an
equilibrium would be a wrong answer with nothing downstream able to catch it.

### Refusals, and asking what a game costs first

| Situation | Status |
| --- | --- |
| fewer than two players — that is maximisation, not a game | `player_count_out_of_range` |
| one action per player — every deviation gain is trivially zero and the report would look strong | `degenerate_no_variation_to_compare` |
| more than eight players, or more than 1024 actions | `player_count_out_of_range` / `action_index_out_of_range` |
| the tensor is not `n_players * n_actions ** n_players` long | `flat_block_is_not_that_shape` |
| a tuple shorter than the player count | `count_exceeds_list_length` |
| an action index outside `[0, n_actions)` | `action_index_out_of_range` |
| a mixed strategy row that is not a distribution | `probabilities_are_not_a_distribution` |
| a non-finite payoff | `non_finite_input` |
| a game that fits in memory but not in the time budget | `work_budget_exceeded` |

The player count is an **exponent**, so the cost of a game is nothing like the size of its
description. Eight players with six actions each is 1.6 million profiles and 13 million payoffs —
past the cell ceiling — and even inside that ceiling the scan or the iteration count can be past the
time budget. Both charges are callable, so you can size a request before you send one:

```python
runtime.execute("strategy.equilibrium", "eq_profile_count", [8, 5])["result"]      # 390625
runtime.execute("strategy.equilibrium", "eq_payoff_cells", [8, 6])["result"]       # -1, too large
runtime.execute("strategy.equilibrium", "eq_enumeration_charge", [2, 406])["result"]  # 536706016
runtime.execute("strategy.equilibrium", "eq_enumeration_charge", [2, 407])["result"]  # -1
```

406 actions at two players is the largest enumeration that fits the budget, and it runs in about a
sixth of a second. 407 is refused. Every request the budget accepts is one the engine finishes.

## See also

* [Discrete Event Simulation](discrete-event-simulation.md) — the event calendar these comparisons run on
* [Evaluation Calibration](evaluation-calibration.md) — scoring the outcomes a strategy produces
* [Runtime Library Catalog](runtime-library-catalog.md) — every module and function
