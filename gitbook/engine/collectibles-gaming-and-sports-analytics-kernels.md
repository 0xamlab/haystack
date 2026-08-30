---
icon: dice
description: Museum conservation and collections-management arithmetic, coin valuation and grading, lottery combinatorics and expected-value math, and sports performance metrics, across four independent scalar-formula modules.
---

# Collectibles, gaming, and sports analytics kernels

Four modules for domains that share nothing structurally except that each reduces a real-world
judgment call to a small formula: how much daylight a fragile object can survive, what a coin is
worth beyond its metal content, whether a lottery ticket is ever a rational bet, and how to compare
a .300 hitter to a 25-point scorer. `museum` and `numismatics` are both valuation-and-care math for
physical collections — one for institutional holdings, one for a single graded coin — while
`lottery` and `sports_analytics` are both probability-and-scoring math for games, one for pure
chance and one for measured skill. None of the four calls into any of the others; they are grouped
here because each is too small to justify its own page, not because a museum curator and a
sportsbook share any code path.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# the number of distinct 6-of-49 combinations -- a standard "6/49" lottery's jackpot
# odds are exactly 1 in this number
runtime.execute("lottery", "combinations", [49, 6])["result"]
# 13983816.0

# a $2 ticket with a $0.50 expected return keeps 75% of every dollar wagered
runtime.execute("lottery", "house_edge", [0.5, 2.0])["result"]
# 75.0
```

## The modules

| Module | What it does |
| --- | --- |
| `museum` | Conservation-science formulas for light exposure, humidity/moisture equilibrium, preservation indices, and climate stability, plus collections-management ratios: storage density, visitor density, growth rate, insurance appreciation, and a weighted conservation-priority score |
| `numismatics` | Coin valuation and grading arithmetic: melt value, premium over melt, Sheldon-scale grading, population-report scarcity, annualized return, auction fees and total acquisition cost, and bullion content in troy ounces |
| `lottery` | Combinatorics (`C(n,k)`, `P(n,k)`), lottery odds, expected value and house edge, probability of at least one win across multiple tickets, annuity-vs-lump-sum present value, and post-tax payout math |
| `sports_analytics` | Baseball rate stats (batting average, OBP, SLG, OPS, ERA, WHIP), a simplified NFL passer rating, Pythagorean win expectation, Elo expected score and rating update, and basketball true-shooting-percentage and PER approximations |

## `lottery`: combinatorics, odds, and whether a ticket is ever +EV

| Function | What it does |
| --- | --- |
| `combinations(n, k)` | `C(n,k) = n! / (k!(n-k)!)`, computed by an iterative running product (never materializes a factorial), which is what keeps `combinations(49, 6)` from overflowing; `0.0` if `k < 0` or `k > n` |
| `permutations(n, k)` | `P(n,k) = n! / (n-k)!`, same iterative shape; `0.0` if `k < 0` or `k > n` |
| `lottery_odds(total_numbers, drawn, bonus)` | `C(total, drawn) * bonus` — the 1-in-X odds of matching every drawn number plus landing the bonus ball; pass `bonus = 1` for a game with no bonus draw |
| `expected_value(prize, probability)` | `prize * probability` |
| `expected_value_net(prizes_ev_sum, ticket_cost)` | `Σ(EV) - ticket_cost`; the caller sums each prize tier's own `expected_value` first and hands in the total |
| `house_edge(expected_return, ticket_cost)` | `(cost - return) / cost * 100`; `0.0` if `ticket_cost` is within `1e-30` of zero |
| `probability_at_least_one_win(p_single, n_tickets)` | `1 - (1-p)^n`, evaluated as `1 - exp(n * log(q))` rather than repeated multiplication, so it stays accurate for the large ticket counts a real EV analysis needs; `0.0` if `n_tickets <= 0` |
| `annuity_vs_lump_sum(annual_payment, years, discount_rate)` | Present value of a fixed-payment annuity, `payment * (1 - (1+r)^-n) / r`; falls back to `payment * years` when `discount_rate` is within `1e-30` of zero, avoiding the `0/0` the closed form would otherwise hit |
| `tax_after_winnings(gross, federal_rate, state_rate)` | `gross * (1 - federal - state)` |
| `odds_to_probability(odds_against)` | `1 / (odds + 1)` — converts "9-to-1 against" style odds into a probability |
| `probability_to_odds(probability)` | `(1 - p) / p`; `0.0` if `probability` is within `1e-30` of zero |
| `jackpot_ev_threshold(jackpot_odds, ticket_cost)` | `odds * cost` — the jackpot must exceed this figure for the jackpot line of the bet, taken alone, to have non-negative expected value |

**Two real lottery formats, worked end to end.** A standard "6/49" game draws 6 numbers from 49 with
no separate bonus pool: `combinations(49, 6) = 13,983,816`, so `lottery_odds(49, 6, 1)` returns the
same number — the real-world 1-in-14-million odds quoted for that format. Powerball draws 5 white
balls from 69 and one red Powerball from a separate pool of 26:
`lottery_odds(69, 5, 26) = combinations(69, 5) * 26 = 11,238,513 * 26 = 292,201,338`, which is
Powerball's actual published jackpot odds, not a rounded stand-in. Feeding that figure into
`jackpot_ev_threshold(292201338.0, 2.0)` returns `584,402,676`: at a $2 ticket price, the jackpot
alone would need to exceed roughly $584.4 million before the jackpot line of the bet is +EV — and
that threshold ignores the smaller prize tiers, tax withholding, and the chance of splitting the
jackpot with another winner, each of which raises the number a bettor should actually compare a
real jackpot to.

**The annuity is worth less than the lump sum's nominal total, on purpose.** A jackpot advertised as
a $1,000,000/year for 20 years annuity is not "worth $20,000,000 today" — discounting matters.
`annuity_vs_lump_sum(50000.0, 20.0, 0.05)` (a $50,000/year, 20-year annuity discounted at 5%)
returns `623,110.52`, well under the `1,000,000` a naive `payment * years` would give; that
undiscounted figure is exactly what the function falls back to when `discount_rate` is passed as
`0.0`, confirmed by `annuity_vs_lump_sum(50000.0, 20.0, 0.0) = 1,000,000.0`.

## `numismatics`: what a coin is worth beyond its metal

| Function | What it does |
| --- | --- |
| `melt_value(metal_weight_oz, metal_price_per_oz)` | `weight * price` — the coin's value if melted down for raw metal, nothing else |
| `premium_over_melt(market_price, melt_val)` | `(market - melt) / melt * 100`; `0.0` if `melt_val` is within `1e-30` of zero |
| `grade_numeric_to_scale(sheldon_grade)` | Identity, clamped to `[0, 70]` — the Sheldon Scale numismatic dealers and grading services (PCGS, NGC) use, where 70 is a theoretically perfect coin |
| `population_scarcity(certified_count, total_mintage)` | `certified / mintage * 100`; `0.0` if `total_mintage` is within `1e-30` of zero |
| `annual_return(purchase_price, current_price, years)` | `((current/purchase)^(1/years) - 1) * 100`; `0.0` if `purchase_price` or `years` is within `1e-30` of zero, or if the price ratio is non-positive |
| `insurance_value(market_price, coverage_factor)` | `price * factor` |
| `mintage_per_capita(mintage, population)` | `mintage / population`; `0.0` if `population` is within `1e-30` of zero |
| `survival_rate_estimate(surviving, original_mintage)` | `surviving / original * 100`; `0.0` if `original_mintage` is within `1e-30` of zero |
| `price_trend(prices_avg_old, prices_avg_new)` | `(new - old) / old * 100`; `0.0` if `prices_avg_old` is within `1e-30` of zero |
| `auction_fee(hammer_price, buyer_premium_pct)` | `hammer * premium / 100` |
| `total_cost_acquisition(hammer, premium, tax_rate)` | `hammer * (1 + premium/100) * (1 + tax_rate/100)` — buyer's premium and sales tax compound on top of each other, not add |
| `bullion_content_troy_oz(weight_grams, purity)` | `weight * purity / 31.1035` — grams of pure metal converted to troy ounces using the real gram-per-troy-ounce constant |

**Grading and scarcity are two independent axes.** `grade_numeric_to_scale` says nothing about how
many other coins share that grade — a coin graded `65` (`grade_numeric_to_scale(65.0) = 65.0`, well
inside the clamp) could still be `population_scarcity(500.0, 1000000.0) = 0.05` percent of its
original mintage, or the majority of survivors at that grade; the module keeps these as two separate
scalars precisely because a high Sheldon grade and true rarity are different, independently-priced
properties of a coin, not two readings of the same underlying quality.

**Total acquisition cost is multiplicative, and that changes the answer.** For a $10,000 hammer
price at a 20% buyer's premium and 8% sales tax, `total_cost_acquisition(10000.0, 20.0, 8.0)` returns
`12,960.0` — i.e. `10000 * 1.20 * 1.08` — not `10000 * (1 + 0.20 + 0.08) = 12,800.0`. The 160-dollar
gap is tax being charged on the premium as well as the hammer price, which is how most auction
houses actually invoice a sale; a caller that additively approximates the two surcharges will
under-quote the true cost on every purchase.

**Bullion content uses the real conversion constant, not a rounded one.** `31.1035` grams per troy
ounce is precise to five significant figures (the commonly rounded `31.1` would misprice a large
holding); `bullion_content_troy_oz(31.1035, 1.0) = 1.0` exactly recovers one troy ounce from one
gram-for-gram-equivalent input, and `bullion_content_troy_oz(8.0, 0.9)` (an 8-gram coin at 90%
purity) returns `0.23151` troy ounces of pure metal.

## `museum`: conservation physics and collections ratios

| Function | What it does |
| --- | --- |
| `lux_hours_annual(lux_level, hours_per_day, days_per_year)` | `lux * hours_per_day * days_per_year` — cumulative annual light dose, the standard unit conservators budget a fragile object's total light exposure in |
| `uv_exposure(uv_mw_per_lumen, lux)` | `uv_ratio * lux`, in mW/m² |
| `relative_humidity_from_temps(dry_bulb, wet_bulb)` | Simplified `RH ≈ 100 - 5*(dry_bulb - wet_bulb)` (%); the docstring is explicit this is a linear approximation, not the psychrometric chart |
| `moisture_content_equilibrium(rh, temperature)` | Simplified `EMC ≈ rh*0.15 + temperature*0.01` (%) |
| `time_weighted_preservation_index(twpi_ref, temp, rh)` | Simplified `TWPI ≈ ref * exp(-0.05*(temp-20) - 0.02*(rh-50))` — decays exponentially away from a 20°C / 50% RH reference point |
| `light_damage_reciprocity(intensity, duration)` | `intensity * duration` — the reciprocity law: a given cumulative dose does the same damage whether delivered as low light for a long time or bright light briefly |
| `climate_stability_score(temp_variation, rh_variation)` | `100 - 2*ΔT - ΔRH` — higher is a more stable environment |
| `storage_density(items, floor_area)` | `items / floor_area`; `0.0` if `floor_area <= 0` |
| `collection_growth_rate(items_added, items_deaccessioned, total)` | `(added - removed) / total * 100` (%); `0.0` if `total <= 0` |
| `insurance_value_appreciation(initial_value, annual_rate, years)` | `initial * (1 + rate)^years`, evaluated as `exp(years * log(1+rate))` |
| `visitor_density(visitors, gallery_area)` | `visitors / gallery_area`; `0.0` if `gallery_area <= 0` |
| `conservation_priority_score(condition, significance, risk)` | `condition*0.4 + significance*0.3 + risk*0.3` — a fixed weighting, condition counted more heavily than either significance or risk |

**Every conservation formula here is a documented simplification, not a metrology-grade
instrument reading.** The module's own docstring flags `relative_humidity_from_temps`,
`moisture_content_equilibrium`, and `time_weighted_preservation_index` as approximations
(`≈`, not `=`); a real psychrometric RH calculation depends on barometric pressure and a lookup
table, and real equilibrium-moisture-content and TWPI models (the Image Permanence Institute's
actual TWPI, for one) are considerably more involved than a single exponential in two variables.
These functions are useful for the ordering and rough sizing of a conservation decision — is this
gallery's climate more stable than that one's, is this display case's light dose over budget — not
for a certificate-grade environmental report.

**A worked light-dose and appreciation example, pinned in the test suite.** A gallery lit at
50 lux for 8 hours a day, 365 days a year: `lux_hours_annual(50.0, 8.0, 365.0) = 146,000` lux-hours,
the annual dose a conservator compares against a material-specific budget (paper and textiles
typically get a far lower annual allowance than oil paintings). Separately, a $1,000,000 collection
appreciating at 5% a year for a decade: `insurance_value_appreciation(1000000.0, 0.05, 10.0)`
returns `1,628,894.63` — the exact compound-growth figure, not a linear 50%-over-ten-years
approximation, which would understate it by over $128,000.

**`storage_density` and `visitor_density` are the same ratio shape over different denominators.**
Both divide a count by an area and both return `0.0` rather than dividing by zero when the area is
non-positive, but they answer different questions: `storage_density` tracks how tightly objects are
packed into storage (a collections-management concern), while `visitor_density` tracks how crowded
a gallery is (a conservation *and* visitor-experience concern, since foot traffic raises humidity
and vibration). Neither function calls the other, and nothing in `museum` computes one from the
other.

## `sports_analytics`: baseball, football, Elo, and basketball, four unrelated scoring systems in one module

| Function | What it does |
| --- | --- |
| `batting_average(hits, at_bats)` | `H / AB`; `0.0` if `at_bats == 0` |
| `on_base_percentage(hits, walks, hbp, at_bats, sf)` | `(H + BB + HBP) / (AB + BB + HBP + SF)`; `0.0` if the denominator is `0` |
| `slugging_percentage(total_bases, at_bats)` | `TB / AB`; `0.0` if `at_bats == 0` |
| `ops(obp, slg)` | `OBP + SLG` — takes the two already-computed rates, does not recompute them |
| `era(earned_runs, innings_pitched)` | `(ER / IP) * 9`; `0.0` if `innings_pitched == 0` |
| `whip(walks, hits, innings_pitched)` | `(BB + H) / IP`; `0.0` if `innings_pitched == 0` |
| `passer_rating_nfl(comp, att, yards, td, interceptions)` | The standard simplified NFL formula: four components (completion rate, yards/attempt, TD rate, interception rate), each clamped to `[0, 2.375]`, averaged and scaled by 100; `0.0` if `att == 0` |
| `pythagorean_wins(runs_scored, runs_allowed, exponent)` | `RS^e / (RS^e + RA^e)` — Bill James's win-expectation formula; `1.0` if `runs_allowed <= 0` (and `runs_scored > 0`), `0.0` if `runs_scored <= 0` |
| `elo_expected_score(rating_a, rating_b)` | `1 / (1 + 10^((Rb - Ra)/400))` |
| `elo_new_rating(old_rating, k, actual_score, expected_score)` | `R + K*(S - E)` |
| `true_shooting_percentage(points, fga, fta)` | `PTS / (2*(FGA + 0.44*FTA))`; `0.0` if the denominator is `0` |
| `player_efficiency_rating_approx(points, rebounds, assists, steals, blocks, turnovers, minutes, pace)` | Simplified PER: `((PTS+REB+AST+STL+BLK-TO) / MIN) * (pace/100)`; `0.0` if `minutes == 0` |

**`passer_rating_nfl` reproduces the real formula's exact perfect-game ceiling.** Feeding it a
maximal line — `passer_rating_nfl(30.0, 30.0, 500.0, 5.0, 0.0)`, 30-for-30 passing (100% completion),
500 yards, 5 touchdowns, 0 interceptions — pushes all four intermediate components (`a`, `b`, `c`,
`d`) past their `2.375` ceiling, where each gets clamped back down to exactly `2.375`. Averaging four
copies of `2.375` and scaling by 100 gives `(2.375*4)/6*100 = 158.333...`, which is the NFL's own
well-known perfect passer rating of 158.3 — this module's "simplified" formula (its own docstring's
word) reproduces the real ceiling exactly, even though a non-maximal game line will diverge from the
NFL's official computation in the low decimals.

**`pythagorean_wins`'s zero-handling is asymmetric on purpose.** A team that has scored but allowed
nothing (`pythagorean_wins(100.0, 0.0, 2.0) = 1.0`) is a perfect team by construction — the formula
never has to compute `0^e` in the denominator, because the function checks `runs_allowed <= 0` before
touching the exponentiation. A team that has allowed runs but scored none returns `0.0` by the same
short-circuit. Only when both are positive does the function fall through to the real
`exp(exponent * log(x))` formulation — for a team that has scored 800 runs and allowed 700 at the
classical exponent of `2.0`, `pythagorean_wins(800.0, 700.0, 2.0) = 640000 / 1130000 = 0.566372`,
meaning that run differential alone predicts roughly a `.566` winning percentage.

**Elo's two functions are a pure function and a state update, and they compose in one call.** Two
equally-rated players show `elo_expected_score(1500.0, 1500.0) = 0.5` — a coin flip, as Elo requires
of an even match. A 200-point favorite's edge is `elo_expected_score(1600.0, 1400.0) = 0.7597` (a
plausible large-but-not-overwhelming favorite). Feeding that expectation into the update function for
a player who won as the expected favorite — `elo_new_rating(1500.0, 32.0, 1.0, 0.5) = 1500 + 32*(1 -
0.5) = 1516.0` — is the exact chain a real rating system runs after every game: expected score first,
then the K-factor-scaled correction against the actual result.

## Verification notes

The four `mojo/tests/libs/test_*.mojo` files behind this page (`test_lottery.mojo`,
`test_museum.mojo`, `test_numismatics.mojo`, `test_sports_analytics.mojo`) are auto-generated
coverage smoke tests: every function is called once with the literal argument `0.5` (or `0.5`
repeated for multi-argument functions, `5`/`1` for the few `Int`-typed lottery parameters), and the
only assertion is that the result is finite — none of them pin a specific expected number. The real
numeric coverage lives in four separate hand-authored files under `tests/mojo/`:
`test_wave90.mojo` (`lottery`, 26 pinned assertions including the real 6/49 and Powerball odds),
`test_wave83.mojo` (`museum`, 24 pinned assertions), `test_wave94.mojo` (`numismatics`, 25 pinned
assertions), and `test_wave77.mojo` (`sports_analytics`, assertions covering every function in the
module). Every worked figure given above traces to one of those four files or was independently
recomputed in plain Python from the formula in the corresponding `mojo/engine/*.mojo` source and
matched to the value the wave test already asserts.

Grepping `gitbook/` for `museum`, `numismatics`, `lottery`, and `sports_analytics` outside this page
turns up nothing but the machine-generated [runtime library catalog](runtime-library-catalog.md) —
no other page documents these four modules, and none of the four imports or is imported by a module
documented elsewhere in this corpus.

**Next:** see [Runtime library catalog](runtime-library-catalog.md) for every module and function,
or [Mixture-of-experts and routing kernels](mixture-of-experts-and-routing-kernels.md) for another
page grouping several small, formula-only modules that don't share code but are too small to stand
alone.
