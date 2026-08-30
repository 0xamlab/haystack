---
icon: gavel
description: Auction revenue and payment rules (Vickrey/English/Dutch/VCG), closed-form behavioral-economics biases, and voting rules computed directly from raw ballots.
---

# Auction and market mechanism kernels

Three modules for the arithmetic of decisions made by more than one self-interested party at once.
`auction` prices a single item among bidders who may or may not reveal their true value; `election`
aggregates many individuals' ranked or approved choices into one collective winner; `behavioral_economics`
supplies the closed-form corrections for where real decision-makers on either side of those mechanisms
deviate from the rational-actor assumptions the auction and voting math is built on. None of the three
call into each other or into any other kernel family — each is a small set of independent, closed-form
formulas over plain `Float64`/`Int` scalars and flat lists, not a simulation or a solver.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Three sealed bids: 10, 20, 15
bids = [10.0, 20.0, 15.0]
runtime.execute("auction", "second_price_sealed", [bids, 3])["result"]
# [1.0, 15.0] -- bidder 1 (the 20 bid) wins, but a Vickrey auction only ever
# charges the winner the second-highest bid: 15, not their own 20

# The same three candidates, now as an election: five voters rank all three,
# and candidate 0 beats each rival head-to-head
ballots = [[0, 1, 2], [0, 2, 1], [0, 1, 2], [1, 2, 0], [2, 1, 0]]
runtime.execute("election", "condorcet_winner", [ballots, 3])["result"]
# 0
```

## The modules

| Module | What it does |
| --- | --- |
| `auction` | Sealed-bid, ascending (English), descending (Dutch), and all-pay auction revenue and payment rules; VCG payments, reserve-price filtering, optimal bid shading under uniform independent private values, and a winner's-curse correction for common-value estimates. |
| `behavioral_economics` | Closed-form versions of named deviations from expected-utility maximization: prospect theory's value and probability-weighting functions, hyperbolic and quasi-hyperbolic time discounting, anchoring, the endowment effect, loss aversion, mental accounting, status-quo bias, sunk-cost ratio, ultimatum-game fairness, and nudge effect size. |
| `election` | Voting rules computed directly from raw ranked or approval ballots: plurality, Borda count, Condorcet winner (and the pairwise matrix it is built from), instant-runoff (ranked-choice) elimination, approval voting, and Copeland scores. |

## `auction`: who wins, and what they pay

| Function | What it does |
| --- | --- |
| `first_price_sealed(bids, n)` | Returns `[winner_idx, price]`; the winner pays their own (highest) bid. `[-1, 0]` if `n <= 0`. |
| `second_price_sealed(bids, n)` | Vickrey auction: same winner as first-price, but the price is the **second**-highest bid. |
| `english_auction_revenue(bids, n)` | Ascending-auction revenue = the second-highest bid (bidding stops the instant the second-highest bidder drops out). |
| `dutch_auction_revenue(bids, n)` | Descending-auction revenue = the highest bid (the first bidder to accept the falling price wins at that price). |
| `all_pay_revenue(bids, n)` | Sum of every bid — every bidder pays regardless of outcome. |
| `revenue_equivalence_check(bids, n)` | `True` if the Dutch (highest-bid) and English (second-highest-bid) revenue on **this same bid vector** are within 20% of their average, or both are within `1e-12` of zero. |
| `vcg_payment(values, n, winner_idx)` | The declared winner's payment = the highest value among every *other* bidder. |
| `reserve_price_filter(bids, n, reserve)` | `[count_above, sum_above]` — bids at or above `reserve`. |
| `bid_shading_optimal(value, n_bidders)` | Optimal first-price bid under uniform IPV: `value * (n-1)/n`; `0` if `n_bidders <= 1`. |
| `expected_revenue_uniform(n_bidders, max_val)` | Expected revenue with `n_bidders` uniform `[0, max_val]` valuations: `(n-1)/(n+1) * max_val`. |
| `winners_curse_adjustment(estimate, n_bidders)` | Shades a common-value estimate down by the same `(n-1)/n` factor as `bid_shading_optimal`; unchanged if `n_bidders <= 1`. |

A single three-bid vector `[10.0, 20.0, 15.0]` (the exact case pinned in
`tests/mojo/test_wave63.mojo`) exercises five of these at once:
`first_price_sealed` returns `[1, 20]` (bidder 1 wins, pays their own 20),
`second_price_sealed` returns `[1, 15]` (same winner, pays the second-highest bid),
`english_auction_revenue` and `dutch_auction_revenue` return `15` and `20` respectively (the same two
numbers, read as "what an ascending vs. descending auction would have raised" rather than "who pays
what"), and `reserve_price_filter(bids, 3, 12.0)` returns `[2, 35]` — two bids (20 and 15) clear a
reserve of 12, summing to 35.

**`revenue_equivalence_check` compares two realized numbers, not two expectations.** The classical
revenue equivalence theorem is a statement about *expected* revenue across the equilibrium bidding
strategy for a whole distribution of independent private values — it says first-price and
second-price auctions raise the same revenue *on average*, not that any single draw of bids will look
alike. Reading the body confirms this function checks something narrower and cheaper: it takes
`dutch_auction_revenue` (the top bid) and `english_auction_revenue` (the second bid) from the **same**
bid vector and asks whether those two numbers are within a fixed 20% band of each other. Close bids —
`[9.0, 10.0, 9.5]` — pass (`True`); far apart bids — `[1.0, 100.0, 2.0]` — fail (`False`), both pinned
in `test_wave63.mojo`. That is a reasonable smoke check for "were the top two bids close together,"
not a proof that the underlying auction satisfies the theorem's assumptions (symmetric bidders,
independent private values, risk neutrality, equilibrium bid shading).

**`vcg_payment` trusts `winner_idx` completely.** The function's own loop is
`for i in range(n): if i != winner_idx and values[i] > max_other: max_other = values[i]` — it never
checks that `values[winner_idx]` is actually the largest value in the list. Call it with the true
winner (`vcg_payment([10, 20, 15], 3, 1)` → `15`, the correct VCG payment, matching `second_price_sealed`'s
price for the same bids) and it reproduces textbook second-price behavior. Call it with the *wrong*
index — `vcg_payment([10, 20, 15], 3, 0)`, naming bidder 0 (value 10) as though they had won — and it
returns `20`: the maximum of the other two bidders, which now *exceeds* the named winner's own value.
A real VCG mechanism never charges the winner more than their own bid; this function has no such
floor because it never re-derives the winner from `values` itself, it only ever excludes whichever
index it is told to exclude.

## `behavioral_economics`: closed-form deviations from rational choice

| Function | What it does |
| --- | --- |
| `prospect_theory_value(x, alpha, lambda_loss)` | `x^alpha` for gains, `-lambda_loss * (-x)^alpha` for losses; `0` within `1e-30` of the origin on either side. |
| `probability_weighting(p, gamma)` | Prelec weighting `p^gamma / (p^gamma + (1-p)^gamma)^(1/gamma)`; clamped to `0`/`1` at `p <= 0`/`p >= 1`; returns `p` unweighted if `gamma <= 0`. |
| `hyperbolic_discount(value, k, delay)` | `value / (1 + k * delay)`. |
| `quasi_hyperbolic_discount(value, beta, delta, period)` | `beta * delta^period * value` for `period > 0`; `value` unchanged at `period == 0`; `0` if `delta <= 0`. |
| `anchoring_adjusted_estimate(anchor, adjustment, adjustment_factor)` | `anchor + adjustment * adjustment_factor`. |
| `endowment_effect_wta_wtp_ratio(wta, wtp)` | `wta / wtp`; `0` if `wtp` is within `1e-30` of zero. |
| `loss_aversion_coefficient(loss_impact, gain_impact)` | `\|loss_impact\| / gain_impact`; `0` if `gain_impact` is within `1e-30` of zero. |
| `mental_accounting_total(gains, losses)` | `gains + losses` — plain arithmetic sum, no segregation logic beyond that the caller already split gains from losses. |
| `status_quo_bias(switching_cost, switching_benefit)` | `switching_cost - switching_benefit`; positive favors staying put. |
| `sunk_cost_ratio(sunk, total_budget)` | `sunk / total_budget`; `0` if `total_budget` is within `1e-30` of zero. |
| `fairness_ultimatum_threshold(offer, total)` | `offer / total * 100`; `0` if `total` is within `1e-30` of zero. |
| `nudge_effectiveness(treated_rate, control_rate)` | `treated_rate - control_rate`; negative means the nudge backfired. |

Every worked value below is pinned in `tests/mojo/test_wave78.mojo`, hand-verified against the formula
in `mojo/engine/behavioral_economics.mojo`.

**Loss aversion is visible inside a single function call, not just in `loss_aversion_coefficient`.**
`prospect_theory_value(100.0, 0.88, 2.25)` (a $100 gain, the diminishing-sensitivity exponent
`alpha = 0.88` and loss-aversion coefficient `lambda_loss = 2.25` from Kahneman and Tversky's 1992
parameterization) returns `100^0.88 ≈ 57.544`. The mirror-image loss, `prospect_theory_value(-100.0, 0.88, 2.25)`,
returns `-2.25 * 100^0.88 ≈ -129.474` — over twice the magnitude of the equivalent gain, and the ratio
of the two magnitudes (`129.474 / 57.544 ≈ 2.25`) is exactly `lambda_loss`, since both branches raise
the same `|x|` to the same `alpha`; only the loss branch scales by `lambda_loss` on top. The function
computes both branches as `exp(alpha * log(|x|))` rather than a direct power, which is why `x` within
`1e-30` of zero on either side short-circuits to `0.0` — `log(0)` is `-inf`, and the guard exists to
keep that out of the `exp` call entirely rather than relying on the arithmetic to cancel it out.

**`probability_weighting`'s `gamma <= 0` branch is not "more curvature," it's "no weighting at all."**
`probability_weighting(0.5, 0.61)` — Prelec's own commonly-cited curvature parameter — returns
`≈0.4206`, pulling a fair coin flip's probability below its true value, the classic
overweight-small/underweight-large-probability signature. But passing a non-positive `gamma` doesn't
extrapolate that curve further; it returns `p` completely unchanged, i.e. a rational, undistorted
probability. A caller sweeping `gamma` down through zero expecting the curve to keep bending will
instead hit a discontinuity where the function snaps back to identity.

**The two discounting functions handle "no delay" differently, not by coincidence.** `hyperbolic_discount`
has no special case for `delay = 0` — the formula `value / (1 + k*0)` already reduces to `value`
without help. `quasi_hyperbolic_discount` cannot rely on that same trick: its formula is
`beta * delta^period * value`, and at `period = 0` that would evaluate to `beta * value`, not `value`
— quasi-hyperbolic discounting's whole premise is a *discontinuous* jump at the present moment (the
`beta` term models "now" being disproportionately preferred over "one period from now"), so the
function has to special-case `period <= 0.0` and return `value` outright rather than let the general
formula run. `quasi_hyperbolic_discount(100.0, 0.7, 0.95, 0.0) = 100.0`, but one period out,
`quasi_hyperbolic_discount(100.0, 0.7, 0.95, 1.0) = 0.7 * 0.95 * 100 = 66.5` — a same-day value is
worth 100, a one-period-away value is discounted by both `beta` and `delta` at once.

## `election`: a winner computed directly from ballots

Ballots are `List[List[Int]]` — each inner list one voter's ranked candidate indices, most preferred
first (or, for `approval_voting`, the set of candidates that voter approves, unordered). Every public
function starts by calling the module's private `_ballots_valid`, which rejects `n_candidates <= 0`
and any ballot entry outside `[0, n_candidates)` — reading its own docstring, the reason is that ballot
entries are used directly as list indices downstream, and an out-of-range one would otherwise be an
uncatchable out-of-bounds abort rather than a normal error. Every function below returns a sentinel
(`-1` for a winner index, an empty list for a score vector or matrix) on invalid input instead.

| Function | What it does |
| --- | --- |
| `plurality(ballots, n_candidates)` | Winner by most first-place votes; ties go to the lowest candidate index. |
| `borda_count(ballots, n_candidates)` | Per-candidate Borda scores: a rank-`r` mention scores `n_candidates - 1 - r` points (first place = `n-1`, last = `0`). |
| `borda_winner(ballots, n_candidates)` | The candidate with the highest `borda_count` score. |
| `condorcet_winner(ballots, n_candidates)` | The candidate who beats every other candidate pairwise; `-1` if no such candidate exists (a cycle). |
| `pairwise_matrix(ballots, n_candidates)` | `matrix[i][j]` = number of ballots ranking `i` above `j`. |
| `instant_runoff(ballots, n_candidates)` | Ranked-choice winner: repeatedly eliminate the candidate(s) with the fewest current first-place votes and redistribute until one candidate holds a strict majority. |
| `approval_voting(approvals, n_candidates)` | Winner by total approvals; ties go to the lowest candidate index. |
| `copeland_scores(ballots, n_candidates)` | Per-candidate score: `+1` per pairwise win, `+0.5` per pairwise tie, `0` per loss. |

The five ballots pinned in `tests/mojo/test_wave37.mojo` — `[0,1,2]`, `[0,2,1]`, `[0,1,2]`, `[1,2,0]`,
`[2,1,0]` — give `borda_count` scores `[6.0, 5.0, 4.0]` (candidate 0: three first-place mentions worth
2 points each plus two last-place mentions worth 0 = 6), `plurality`, `borda_winner`, `condorcet_winner`,
and `instant_runoff` all agree on candidate 0 (who holds 3 of 5 first-place votes, a majority IRV
resolves in round one without any elimination), and `copeland_scores` gives `[2.0, 1.0, 0.0]` — 0 beats
both 1 and 2 pairwise, 1 beats only 2, 2 beats no one. A rock-paper-scissors cycle over the same three
candidates (`[0,1,2]`, `[1,2,0]`, `[2,0,1]`) breaks that unanimity on purpose:
`condorcet_winner` returns `-1` (no one beats both rivals), while `copeland_scores` still returns a
complete answer, `[1.0, 1.0, 1.0]` — every candidate wins exactly one of its two pairwise contests, so
Copeland can rank a cycle where Condorcet must refuse to.

**Elimination in `instant_runoff` is by round, not by candidate.** A round finds the *minimum* current
first-place count among active candidates and eliminates *every* candidate tied at that minimum in the
same pass, rather than the more commonly described "eliminate exactly one, then recount" rule. In
practice this rarely changes who eventually wins — the eliminated candidates' votes still redistribute
to the survivors on the next round either way — but it does mean a three-way tie for last place
finishes the election one round faster than a strict one-at-a-time reading of the algorithm would.

### `election` and `voting`: same rule names, different granularity

[Model ensembling](ml-ensembles.md) documents a module also named for a voting concept — `voting`
(`mojo/engine/voting.mojo`) — and flags it there only as "unrelated to model ensembling despite the
name." It is closely related to `election`, though: both implement plurality, Borda, and Condorcet
math, and neither module imports the other (`mojo/engine/election.mojo` and `mojo/engine/voting.mojo`
each have zero `from`/`import` lines beyond the Mojo standard library). The real difference is what
they take as input. `voting`'s functions work on already-decomposed scalars: `plurality_winner` takes
a flat `List[Int]` of one first-choice vote per voter (not ranked ballots), `borda_score` returns the
Borda score for a **single named candidate** from a flat rank array rather than a full ballot set, and
`condorcet_pairwise` doesn't count anything at all — it takes two vote *counts* the caller has already
tallied and just compares them. `voting` also covers ground `election` never touches: apportionment
math (`quota_droop`, `quota_hare`, `dhondt_divisor`, `sainte_lague_divisor` — seat allocation, not
candidate selection), the Banzhaf power index, and spoiler-effect detection. `election`, by contrast,
takes the raw ballots (`List[List[Int]]`) and does every step of the counting itself — building its own
pairwise matrix, running full IRV elimination rounds, tallying Copeland scores from first principles —
and returns a candidate or a full score vector directly, with no apportionment or power-index math at
all. Neither module is redundant with the other: `voting` is single-value social-choice arithmetic
(plus a distinct family of apportionment/power-index formulas), `election` is the ballot-level
computation of a subset of those same named rules.

## Verification

`mojo/tests/libs/test_auction.mojo` and `mojo/tests/libs/test_behavioral_economics.mojo` are
auto-generated coverage smoke tests — every function is called once with fixed literal arguments and
checked only for a finite result, with no numeric value pinned. The real, hand-computed numeric
coverage for all three modules on this page lives in `tests/mojo/test_wave63.mojo` (auction, alongside
cellular automata and music theory), `tests/mojo/test_wave78.mojo` (behavioral economics, alongside
solar energy and mining), and `tests/mojo/test_wave37.mojo` (election, alongside polynomial operations
and bootstrap statistics — its own docstring calls this wave "Voting Methods," which is the file's
label for what the `election` module implements, not a reference to the separate `voting` module
above). Every worked number on this page is drawn from one of those three files or independently
re-derived from the formula in the corresponding `mojo/engine/*.mojo` source.

**Next:** see the disambiguation with [Model ensembling](ml-ensembles.md)'s `voting` module in detail
above, or browse the [Runtime library catalog](runtime-library-catalog.md) for every module and function.
