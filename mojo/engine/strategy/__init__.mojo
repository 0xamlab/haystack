"""
strategy — evaluate and compare decision strategies on common random numbers. Zero Python.

This file exists because `from strategy.contract import ...` cannot resolve without it: Mojo
reports "unable to locate module 'strategy' / failed to resolve parent package body" and every
sibling module in the package, and every SDK path that reaches one, fails at import. It carries
no code on purpose — a package body that defined anything would be a second place for the
vocabulary in `strategy.contract` to live.

What the tree already had, and what it did not
---------------------------------------------
`decision_analysis.mojo` holds twelve one-shot decision criteria — expected value, expected
utility, minimax regret, Hurwicz, maximin, maximax, Laplace, the value of perfect information —
over a payoff matrix with no time dimension. `game_theory.mojo` holds an EXACT 2x2 mixed Nash by
indifference equations, a minimax value, Shapley values for three players and a Pareto frontier.
`reinforcement.mojo` holds tabular value iteration, policy evaluation and a greedy policy
extractor over a small MDP. `simulation.mojo` holds an event calendar and an M/M/1 estimator.
Every one of them is frozen, and every number this package reports comes from one of them, from
`discrete_event`, from `evaluation`, from `stats`, from `inference` or from `determinism`.

What was missing is the thing that makes a comparison of strategies mean anything:

  * COMMON RANDOM NUMBERS. Comparing two strategies on independently sampled scenarios measures
    the sampling noise as much as it measures the strategies. Nothing in the strategy-adjacent
    part of the tree drew through the keyed, counter-based generator: `engines/monte_carlo.mojo`
    has 61 ad-hoc RNG sites and zero keyed ones, `simulation.mojo` seven and zero,
    `reinforcement.mojo` three and zero. So no strategy evaluation here was reproducible, let
    alone paired. `strategy.crn` addresses every scenario draw by
    `(seed, family, scenario, step, factor, stream)` through the frozen
    `determinism.counter_rng`, with THE STRATEGY INDEX ABSENT FROM EVERY ENVIRONMENT COORDINATE,
    so two strategies at one scenario read bit-identical draws by construction.

  * A STRATEGY THAT IS NOT AN INTEGER TAG. `game_theory.iterated_pd(strategy1: Int,
    strategy2: Int, rounds: Int)` is the tree's only repeated-play comparison and a "strategy"
    there is an integer selecting a hardcoded rule in the Prisoner's Dilemma. It stays reachable
    and unchanged. `strategy` carries a policy as a flat `(kind, params, arity)` triple whose
    arity is COMPUTED from the environment, so a policy the environment cannot evaluate is
    refused rather than scored.

  * A HORIZON. `decision_analysis` is one shot and `reinforcement` learns a policy rather than
    scoring a stated one. Evaluating a given strategy over many steps of many sampled scenarios,
    and reporting the spread over those scenarios, had no home.

Absence, bounds and non-finites
-------------------------------
Every driver returns a status and a `has_*` flag beside each quantity; a quantity that could not
be computed carries `0.0` and `False`, never a raw non-finite, because the dispatch refuses to
serialise one and a single absent payoff would turn the whole response into a typed error. No
caller-supplied count is trusted: reading past a `List` end is an uncatchable process abort that
`try`/`except` cannot contain, so every count is checked against the real length before the
first read. Shapes are checked by DIVISION through the frozen `sparse_numerics.csr.dims_fit`,
because `3 * 6148914691236517206 == 2` in wrapping 64-bit arithmetic and a multiply is not a
bound. And bounding memory is not bounding work: the work here is the four-factor product
`n_strategies * n_replications * horizon * (1 + n_factors)` plus the weighted scenario draws,
and it is charged as a product before anything runs.

Status codes
------------
This package owns 450-489 and uses no other range. `strategy.contract.strat_status_name` is the
ONE vocabulary; no module here carries a second status table.

Modules
-------
  contract    — status codes, verdicts, exactness, ceilings, the work budget, the named streams,
                the CRN coordinate assignment, and the flat Policy/Scenario encodings
  crn         — scenario generation on common random numbers, policy evaluation over a horizon,
                and the measured pairing and independence audits that justify the package
  policy      — a policy as an object rather than an integer tag
  equilibrium — N-player normal-form games, adaptive play, and honest exactness
  tournament  — ranking strategies from a paired comparison, with an honest verdict
"""
