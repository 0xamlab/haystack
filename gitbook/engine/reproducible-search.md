---
icon: dna
description: Evolutionary parameter search whose every draw is addressable, so a fitted result replays bit-exactly on any machine and any core count.
---

# Reproducible evolutionary search

`evolutionary_search` is a genetic optimiser whose randomness is **counter-based and keyed**, not
sequential. Every draw is a pure function of `(generation, individual, gene)` and the master seed, so the
whole search replays bit-exactly — on a different machine, at a different core count, in a different
evaluation order.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

lo, hi = [0.0, 0.0], [10.0, 10.0]
pop = runtime.execute("evolutionary_search", "ga_init", [lo, hi, 24, 12345])["result"]

for gen in range(30):
    fitness = [-(pop[i * 2] - 3.0) ** 2 - (pop[i * 2 + 1] - 7.0) ** 2 for i in range(24)]
    pop = runtime.execute(
        "evolutionary_search", "ga_step",
        [pop, fitness, lo, hi, 3, 0.5, 0.3, 0.15, 2, 12345, gen],
    )["result"]

best = runtime.execute("evolutionary_search", "ga_best", [pop, fitness, 2])["result"]
```

## The modules

| Module | What it does |
| --- | --- |
| `evolutionary_search` | counter-based, addressable genetic optimiser — every draw is a pure function of its coordinates, so a run replays bit-exactly on any machine and any core count |
| `genetic` | the process-seeded genetic optimiser for one-off searches — same population/selection/mutation loop, but a run cannot be replayed |

## Functions

| Function | What it does |
|---|---|
| `ga_init(lo, hi, pop_size, seed)` | Uniform initial population inside the bounds. Individual 0 is seeded at the box midpoint so an incumbent-like candidate is always present. |
| `ga_step(pop, fitness, lo, hi, tournament, cx_rate, mut_rate, mut_scale, elite, seed, gen)` | One generation: elitism, tournament selection, uniform crossover, Gaussian mutation. Fitness is **maximised**. |
| `ga_best(pop, fitness, n_dim)` | The fittest individual's genes, with its fitness appended. |
| `ga_diversity(pop, n_dim)` | Per-dimension population standard deviation — the **identifiability** diagnostic. |
| `ga_saturation(pop, lo, hi)` | Fraction of the population pinned within 1% of each bound: negative at `lo`, positive at `hi`. |

## Why reproducibility is the point

The runtime also ships [`genetic`](runtime-library-catalog.md), which is fine for one-off optimisation.
Its mutation draws from a process-seeded generator, so a run cannot be replayed. That is acceptable when
you want *an* answer and unacceptable when the fitted parameters become evidence — a calibration nobody
can reproduce is an assertion, not a result.

Because draws are addressed rather than consumed in sequence, nothing depends on evaluation order. Two
runs on 8 and 64 cores produce identical populations.

## The design is stateless, deliberately

`ga_step` maps one scored generation to the next and holds no problem state. Fitness is computed by the
caller, so the search can drive anything — a simulation, a backtest, a physical experiment — without the
optimiser needing to know what it is optimising.

## Read the diagnostics, not just the best vector

A fitted value means nothing without knowing whether the objective could resolve it:

* **`ga_diversity`** — a dimension whose population spread never collapses is one the objective is
  indifferent to. Reporting a precise value for it overstates the evidence.
* **`ga_saturation`** — a value pinned to a bound is an artifact of the box, not an estimate. It is the
  difference between "the data prefers 0.6" and "0.6 is as far as we let it go".

Both are worth acting on. Widening a saturated bound is the obvious response and not always the right
one: a bound can be doing useful regularisation, and a wider box that scores worse on held-out data is
telling you so.

## Verification

A one-dimensional search for the peak of `−(x−3)²` converges to 3.008 as a zero-argument selftest, so the
same number is reproducible on any machine. The suite asserts that identical seeds give identical
populations and different seeds do not, that genes never leave their bounds under mutation, that elitism
never lets best fitness regress, and that `ga_saturation` reads exactly +1 at the upper bound, −1 at the
lower and 0 in the interior.

**Next:** score what you fit with [forecast scoring](forecast-scoring.md), or see
[model selection](ml-model-selection.md) for held-out splits that keep a search honest.
