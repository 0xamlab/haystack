---
icon: sack-dollar
description: Depreciation, financial ratios, and time-value-of-money accounting; actuarial mortality, life-expectancy, and reserve math; insurance premium ratemaking and loss-ratio formulas; and pension funding, vesting, and Social Security benefit calculations.
---

# Accounting, actuarial, insurance, and pension kernels

Four small libraries of scalar financial-math formulas, one per discipline. `accounting` is
corporate bookkeeping: depreciation schedules, profitability and leverage ratios, break-even
analysis, and single-amount time value of money. `actuarial` is the mortality-and-annuity math
behind life insurance and pension reserving: survival probabilities, curtate life expectancy, net
single premiums, and prospective reserves. `insurance` is property-and-casualty ratemaking: pure
and gross premium, loss/expense/combined ratio, claim frequency and severity, Bühlmann
credibility, and retention. `pension` is retirement-plan math: defined-benefit and
defined-contribution projections, funding ratios, required contribution rates, Social Security
bend points, vesting, and safe withdrawal rates. All four take and return plain `Float64` (or
`Int`) scalars — no structs, no shared status-code vocabulary — so each function is one formula,
checkable against a calculator.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("accounting", "straight_line_depreciation", [10000.0, 2000.0, 5])["result"]
# 1600.0 -- (10000 - 2000) / 5, the same $1,600 depreciation charge every year for 5 years

runtime.execute("insurance", "combined_ratio", [0.70, 0.25])["result"]
# 0.95 -- 70% loss ratio + 25% expense ratio; under 1.0 means this book is underwriting profitably
```

## The modules

| Module | What it does |
| --- | --- |
| `accounting` | Depreciation (straight-line, declining-balance, sum-of-years-digits), single-amount time value of money, profitability/liquidity/leverage ratios, break-even analysis, and compound annual growth rate |
| `actuarial` | Time value of money and annuities over continuous (fractional) periods, mortality and survival rates, curtate life expectancy, net single premiums, life-insurance loss/combined ratio, and prospective policy reserves |
| `insurance` | Property-and-casualty ratemaking: pure/gross premium, loss/expense/combined ratio, expected claim frequency and severity, burning cost, Bühlmann credibility, risk loading, aggregate-deductible savings, and policy retention rate |
| `pension` | Defined-benefit and defined-contribution plan projections, annuity factors, funding ratios, required contribution rates, inflation-adjusted and replacement-ratio benefits, Social Security bend-point PIA, vesting schedules, and portfolio withdrawal rates |

## Two functions named `future_value`, computing the same thing two different ways

`accounting` and `actuarial` each define a `future_value` function, and it is worth being precise
about how they differ rather than assuming they're interchangeable. `accounting.future_value(pv,
rate, periods: Int)` computes `pv * (1 + rate) ** periods` using `std.math.pow`, so `periods` is
always a whole number of fiscal years. `actuarial.future_value(present_value_val, rate, periods:
Float64)` computes the same power through its own `_power` helper — `exp(periods * log(base))` —
specifically so `periods` can be fractional, because actuarial calculations routinely need a
non-integer time horizon (a policy in force for 2.5 years, a life expectancy computed in fractional
years). At an integer period count the two are numerically identical to far better than the
corpus's usual `1e-9` cross-check tolerance: `accounting.future_value(1000.0, 0.05, 10)` and
`actuarial.future_value(1000.0, 0.05, 10.0)` both return `1628.894626777442` (`1628.8946267774422`
in full double precision), differing by about `2.3e-13` — the last couple of printed digits — from
the two implementations' different rounding paths through `pow` versus `exp`/`log`. The mirror-image pair, `accounting.present_value_single` and
`actuarial.present_value`, are related the same way (Int periods vs. Float64 periods, `pow` vs.
`exp`/`log`) and agree just as tightly — `present_value_single(1628.89, 0.05, 10)` and
`present_value(1628.89, 0.05, 10.0)` both land at `1000.0` to within the tolerance the wave tests
use (`0.1`).

## `loss_ratio` and `combined_ratio` are duplicated across `actuarial` and `insurance` — and mean different books of business

Both modules define a `loss_ratio` (claims or incurred losses divided by premiums) and a
`combined_ratio` (loss ratio plus expense ratio) with the identical arithmetic, just different
parameter names: `actuarial.loss_ratio(claims, premiums)` vs. `insurance.loss_ratio(incurred_losses,
earned_premiums)`; `actuarial.combined_ratio(loss_ratio_val, expense_ratio)` vs.
`insurance.combined_ratio(loss_r, expense_r)`. This is not an accident the docstrings hide —
`insurance.mojo`'s own module docstring describes itself as "actuarial and insurance pricing
formulas," acknowledging the overlap directly. The real difference is what surrounds each copy.
`actuarial`'s pair sits next to `net_single_premium` and `reserve_prospective` — the life-insurance
reserving chain, where a loss ratio is one more input alongside mortality and discounting. `insurance`'s
pair sits next to a full property-and-casualty ratemaking chain that `actuarial` does not have at
all: `pure_premium`, `gross_premium`, `expense_ratio`, `expected_claim_frequency`,
`expected_claim_severity`, `burning_cost`, `credibility_buhlmann`, `risk_load`,
`aggregate_deductible_savings`, and `retention_rate`. A caller pricing a life block reaches for
`actuarial`; a caller pricing a P&C book reaches for `insurance`, because only `insurance` builds
the premium up from `pure_premium` in the first place. Grepping the rest of `gitbook/` for
`accounting`, `actuarial`, `insurance`, and `pension` as module names turns up no other page
documenting any of the four — the only other mentions are the machine-generated function-count
rows in [Runtime library catalog](runtime-library-catalog.md), a passing reference to this same
`actuarial`-vs-ecological-`population` naming overlap in
[Ecology and organismal biology kernels](ecology-and-organismal-biology-kernels.md) (that page's
`population` module is Lotka-Volterra predator-prey dynamics, not demography — it never touches
these four modules), and a footnote in
[Building and facility systems kernels](building-and-facility-systems-kernels.md) noting that
`pension`'s pinned tests happen to ship in the same wave file as an unrelated `plumbing` module.

## Worked numbers, verified against the real pinned test suites

Unlike many of the engine's 12-function libraries, all four of these ship **both** the
auto-generated `mojo/tests/libs/test_*.mojo` smoke tests (one call per function with literal
`0.5` arguments, checking only that the result is finite) **and** hand-verified pinned numeric
suites in `tests/mojo/test_wave*.mojo`: `test_wave52.mojo` covers all 12 `accounting` functions,
`test_wave67.mojo` covers all 12 `actuarial` functions, `test_wave80.mojo` covers all 12
`insurance` functions, and `test_wave85.mojo` covers all 12 `pension` functions — every function
in this page's scope has a real, non-trivial assertion behind it. A sample, independently
recomputed here against `mojo/engine/*.mojo`'s formulas to confirm the pinned values are right,
not just self-consistent:

* `accounting.sum_of_years_digits(10000.0, 2000.0, 5, 1) == 2666.6666666666665` — year 1 of a
  5-year SYD schedule: `(10000-2000) * 5/15`.
* `accounting.compound_annual_growth(100.0, 200.0, 5) ≈ 0.148698` — a value that doubles in 5 years
  grew at `2^(1/5) - 1 = 14.87%` a year.
* `actuarial.life_expectancy_curtate(0.01, 60, 100) ≈ 32.77` — a 60-year-old with a flat 1% annual
  mortality rate summed to a maximum age of 100 (`Σ_{k=1}^{40} 0.99^k`), not the naive `40` years
  a 0% mortality assumption would give.
* `actuarial.force_of_mortality(0.02) ≈ 0.020203` — `-ln(0.98)`, slightly above the `0.02` raw
  mortality rate it's derived from, because force of mortality is the instantaneous hazard rate,
  not the rate itself.
* `insurance.aggregate_deductible_savings(500.0, 0.05, 800.0) == 25.0` and
  `aggregate_deductible_savings(1000.0, 0.05, 800.0) == 40.0` — the function caps the deductible at
  the average claim size (`min(deductible, avg_claim)`) before multiplying by claim frequency, so
  raising a deductible past the average claim size stops buying any more savings.
* `pension.social_security_bend_points(3000.0, 1024.0, 6172.0) == 1553.92` —
  `0.9 * 1024 + 0.32 * (3000 - 1024)`; AIME here never reaches the second bend point, so the 15%
  top bracket contributes nothing.
* `pension.defined_contribution_value(5000.0, 0.07, 30) ≈ 472303.93` — 30 years of $5,000
  contributions at a 7% return, verified against `5000 * (1.07^30 - 1) / 0.07` directly in Python,
  not just against the wave test's `470000`–`475000` range check.

## Guard-clause conventions differ sharply from module to module

The four modules were not written to one shared defensiveness standard, and the difference is
visible in the source, not just inferred:

* **`pension` guards nearly every division**, and its guard is a *tolerance* check —
  `fabs(denominator) < 1e-30` — not exact equality, so a denominator of `1e-40` is caught by the
  same branch as an exact `0.0`. `replacement_ratio`, `defined_contribution_value`,
  `annuity_factor`, `funding_ratio`, `contribution_rate_required`, `inflation_adjusted_pension`,
  `years_to_full_vesting`, and `withdrawal_rate` all return a defined sentinel (`0.0`, `100.0`, or
  a linear fallback) rather than dividing through.
* **`accounting` guards most of its ratios, but with exact `== 0.0` equality**, and its two
  time-value-of-money functions (`future_value`, `present_value_single`) have no guard at all.
  `present_value_single(fv, -1.0, periods)` divides by `pow(0.0, periods)`, which is `0.0` for any
  `periods > 0`, so a `-100%` rate produces `inf`, not a sentinel.
* **`actuarial` guards almost nothing.** `mortality_rate`, `loss_ratio`, and `reserve_prospective`
  are bare divisions/subtractions; `exposed = 0.0` in `mortality_rate` produces `inf` or `NaN`
  straight through. The one guard it does have, `force_of_mortality`'s `qx >= 1.0 → 0.0`, is a
  degenerate sentinel rather than a mathematically meaningful answer — the true force of mortality
  as `qx → 1` is unbounded, not zero — chosen so the value stays finite enough to cross the
  runtime's return channel.
* **`insurance` guards nothing.** Every function is a bare formula, including
  `gross_premium(pure_premium_val, expense_ratio, profit_margin)`'s `pure_premium_val / (1 -
  expense_ratio - profit_margin)` denominator: if the expense ratio and profit margin sum to or
  past `1.0`, the denominator goes to zero or negative, and `gross_premium(500.0, 0.5, 0.6)`
  returns `-5000.0` — a negative premium — rather than signaling that the loaded rate is
  infeasible. A caller wiring real underwriting inputs into this function needs to validate
  `expense_ratio + profit_margin < 1.0` itself; the kernel will not.

**Next:** see [Runtime library catalog](runtime-library-catalog.md) for every module and function
in the engine, or [Batched chain greeks](ml-chain-greeks.md) for the other corner of financial math
this engine implements — option pricing and Greeks — a separate discipline from the book-value,
mortality, and ratemaking arithmetic on this page that shares no functions with it.
