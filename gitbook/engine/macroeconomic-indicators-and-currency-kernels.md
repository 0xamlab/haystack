---
icon: sack-dollar
description: Time-value-of-money and loan math, corporate/investment finance ratios, national-economy indicators (GDP, inflation, unemployment), and human population statistics -- four independent formula libraries, not one FX or "currency-conversion" module despite its name.
---

# Macroeconomic indicators and currency kernels

Four modules for the arithmetic of money and population at scales above a single trade or a
single organism: what a loan or a deposit is worth at a different point in time, how a company or
an investment portfolio is doing, how a national economy is doing, and how a human population is
structured and changing. None of these compute foreign-exchange conversion — despite the name,
`currency` is a time-value-of-money and loan library, not an FX module (see below) — and none of
them touch the ecological, non-human sense of "population" documented elsewhere in this corpus.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# A $100,000 loan at 0.5%/month for 360 months (a 30-year fixed mortgage)
runtime.execute("currency", "amortization_payment", [100000.0, 0.005, 360])["result"]
# 599.5505251527569

runtime.execute("finance", "annuity_payment", [100000.0, 0.005, 360])["result"]
# 599.5505251527569 -- byte-identical: the same formula, duplicated across two modules
```

## The modules

| Module | What it does |
| --- | --- |
| `currency` | Time-value-of-money and loan math: currency rounding, compound and continuously-compounded interest, present/future value of a lump sum, present/future value of an annuity, effective annual rate, discount factors, the rule of 72, and a full amortization schedule with the remaining loan balance at any payment. No FX or unit-conversion function of any kind lives here. |
| `demographics` | Human population statistics: crude birth/death rates, natural increase, total fertility rate, infant mortality, a life-expectancy approximation, dependency ratio, sex ratio, population growth rate, doubling time (rule of 70), urbanization rate, and a median-age estimate. Exclusively demographic — no ecological population dynamics. |
| `economic_indicators` | National-economy measurement: GDP growth and per-capita GDP, real GDP from a deflator, inflation from CPI, unemployment rate, the Gini coefficient, Phillips curve, Okun's law, velocity of money, the Fisher equation, trade balance, and purchasing-power-parity exchange rate. |
| `finance` | Corporate and investment finance: NPV, IRR (Newton's method), payback period, ROI, compound interest, present/future value, annuity payment, Sharpe ratio, max drawdown, CAGR, and WACC. |

## `currency` is not an FX module — and it duplicates half of `finance`

The hint that would normally attach to a module named `currency` — parsing ISO codes, converting
between USD and EUR, tracking exchange rates — does not describe anything in
`mojo/engine/currency.mojo`. Its own docstring says so plainly: "Currency Math… compound interest,
continuous compounding, amortization, present/future value, annuities, effective annual rate,
discount factor, and rule of 72." Every one of its twelve functions is time-value-of-money or
loan arithmetic; "currency" here means "the mathematics of money," not "the mathematics of
exchanging one money for another." The one function in this whole family that touches exchange
rates at all is `economic_indicators.purchasing_power_parity` (`price_domestic / price_foreign`),
documented under economic indicators below, not currency.

That scope also means `currency` overlaps almost completely with `finance`. Reading both source
files side by side, `compound_interest(principal, rate, periods)` and
`present_value(future_value, rate, periods)` are defined **identically** in both modules —
same body, same formula, same return type — and `currency.amortization_payment` /
`finance.annuity_payment` compute the same PMT formula (`P·r·(1+r)^n / ((1+r)^n - 1)`) under two
different names, confirmed above to return the same float to the last bit for a real 30-year loan.
The two modules are not interchangeable end to end, though: `currency` is the only one of the two
with an amortization *schedule* and a post-hoc loan-balance lookup (`amortization_schedule`,
`loan_balance_after`), while `finance` is the only one with portfolio and corporate-finance
functions that have no `currency` counterpart at all — `npv`, `irr`, `sharpe_ratio`,
`max_drawdown`, `cagr`, `wacc`, `payback_period`, `roi`. A caller doing loan amortization wants
`currency`; a caller doing investment or corporate analysis wants `finance`; the four functions
that exist in both should agree by construction, since they are the same code.

{% hint style="warning" %}
**`round_currency`'s docstring claims banker's rounding it does not implement.** The docstring
reads "Round to specified decimal places (banker's rounding)," but the body forms
`floor(amount * 10^decimals + 0.5) / 10^decimals` — ordinary round-half-**up**, not
round-half-to-even. `round_currency(2.5, 0)` returns `3.0`; true round-half-to-even returns
`2.0`. This is not a hypothetical reading of the source: [FinQA exact
execution](../benchmarks/finqa-exact-execution.md) and [Program execution
scoring](program-execution-scoring.md) both measure this kernel against a real financial-QA
benchmark and record it producing wrong answers on ties that round-half-to-even would get
right (`INTC/2016/page_33.pdf-3`, `RE/2010/page_42.pdf-4`, `ZBH/2008/page_70.pdf-2`,
`CMCSA/2008/page_59.pdf-4`, `AMT/2012/page_118.pdf-2`), plus a second failure mode from forming
`amount * mult` as a single rounded float before the compare. `currency` is a frozen kernel already
shipping elsewhere in this tree, so this page documents the behavior as it actually is rather than
as its docstring claims — use `progexec.roundexact.round_half_even_scaled` (see the pages above)
where true ties-to-even matters.
{% endhint %}

## `demographics` is human population statistics — a different "population" than `ecology`'s

This corpus has a second module literally named `population`, documented in [Ecology and
organismal biology kernels](ecology-and-organismal-biology-kernels.md), and that page's own intro
already calls out the exact overlap this page would otherwise create: `population` there is "a
discrete-time simulation engine" for species counts — logistic growth, Lotka-Volterra
predator-prey dynamics, two-species competition, and a boolean extinction-risk check — and
explicitly "never touch[es] birth/death-rate tables, life expectancy, or any human-demographic
quantity." `demographics`, documented on this page, is the mirror image: every one of its twelve
functions is a real human-demography formula — crude birth/death rates, total fertility rate,
infant mortality, dependency ratio, sex ratio — and none of them simulate a population trajectory
forward in time the way `population.logistic_growth` or `population.lotka_volterra_step` do.
There is no shared function name and no import between the two modules; `demographics` takes
pre-aggregated counts (births, deaths, population size) and returns a single-period rate or
ratio, while ecological `population` takes a growth rate and a carrying capacity and steps a
simulated count forward. The two names ("population" the module, "population" the parameter)
refer to genuinely different things and should not be conflated.

## Worked examples, verified against the real pinned test suites

`mojo/tests/libs/test_currency.mojo`, `test_demographics.mojo`, `test_economic_indicators.mojo`,
and `test_finance.mojo` are all auto-generated smoke tests — each function is called once with a
literal `0.5`-family argument and the only assertion is that the result is finite, so none of them
pin a real numeric answer. The real pinned suites for this family live in
`tests/mojo/test_wave31.mojo` (currency), `test_wave84.mojo` (demographics),
`test_wave56.mojo` (economic indicators), and `test_wave13.mojo` (finance). Every number below is
copied from one of those four files and independently re-derived from the formula in the
corresponding `.mojo` source, not invented:

**`currency`**

| Call | Result | Formula check |
| --- | --- | --- |
| `compound_interest(1000.0, 0.05, 10)` | `1628.894626777442` | `1000 * 1.05^10` |
| `continuous_compound(1000.0, 0.05, 10.0)` | `1648.7212707001281` | `1000 * e^0.5` |
| `present_value(1000.0, 0.05, 5)` | `783.5261664684588` | `1000 / 1.05^5` |
| `present_value_annuity(100.0, 0.05, 10)` | `772.1734929184818` | `100 * (1 - 1.05^-10) / 0.05` |
| `future_value_annuity(100.0, 0.05, 10)` | `1257.789253554884` | `100 * (1.05^10 - 1) / 0.05` |
| `effective_annual_rate(0.12, 12)` | `0.12682503013196977` | `(1 + 0.12/12)^12 - 1` |
| `discount_factor(0.05, 1)` | `0.9523809523809523` | `1 / 1.05` |
| `rule_of_72(0.06)` | `12.0` | `72 / 6` |
| `amortization_payment(100000.0, 0.005, 360)` | `599.5505251527569` | 30-year mortgage PMT above |
| `round_currency(1.235, 2)` | `1.24` | round-half-up (see warning above) |

For `amortization_schedule(100000.0, 0.005, 360)`, the pinned test checks two structural
properties rather than every row: the first period's interest portion is exactly `500.0`
(`100000 * 0.005`), and the final (360th) row's remaining balance is within `0.01` of `0.0` — the
loan pays itself off exactly on schedule. `loan_balance_after(100000.0, 0.005, 360, 180)` — the
same loan, checked halfway through — returns a balance strictly between `0` and `100000`, i.e.
still amortizing, not yet paid off.

**`demographics`** (all from a hypothetical 5,000,000-person population)

| Call | Result | Formula check |
| --- | --- | --- |
| `crude_birth_rate(50000.0, 5000000.0)` | `10.0` | `50000/5000000 * 1000` |
| `crude_death_rate(40000.0, 5000000.0)` | `8.0` | `40000/5000000 * 1000` |
| `natural_increase_rate(10.0, 8.0)` | `2.0` | `CBR - CDR` |
| `dependency_ratio(1500000.0, 500000.0, 3000000.0)` | `≈66.667` | `(1.5M+0.5M)/3M * 100` |
| `population_growth_rate(50000.0, 40000.0, 5000.0, 5000000.0)` | `0.3` | `(50k-40k+5k)/5M * 100` |
| `doubling_time(2.0)` | `35.0` | rule of 70: `70/2` |
| `median_age_estimate(30.0, 15.0)` | `48.5` | `15 + 50*0.7 - 10*0.15` |

**`economic_indicators`**

| Call | Result | Formula check |
| --- | --- | --- |
| `gdp_growth(110.0, 100.0)` | `0.1` | `(110-100)/100` |
| `inflation_rate(105.0, 100.0)` | `0.05` | `(105-100)/100` |
| `unemployment_rate(5.0, 100.0)` | `0.05` | `5/100` |
| `okuns_law(4.0, 2.0)` | `2.0` | `4/2` (default coefficient is also `2.0`) |
| `fisher_equation(0.05, 0.02)` | `0.03` | `0.05 - 0.02` |
| `trade_balance(100.0, 80.0)` | `20.0` | surplus |
| `purchasing_power_parity(10.0, 5.0)` | `2.0` | `10/5` |
| `gini_coefficient([1.0, 1.0, 1.0, 1.0])` | `0.0` | perfect equality |
| `gini_coefficient([0.0, 0.0, 0.0, 1000.0])` | `0.75` | independently re-derived; more unequal than `[1,2,3,100]`'s `0.7028` |

**`finance`** (a $1,000 investment returning $300/year for 5 years, at a 10% discount rate)

| Call | Result | Formula check |
| --- | --- | --- |
| `npv(0.10, [-1000, 300, 300, 300, 300, 300])` | `≈137.24` | discounted sum of the six cash flows |
| `irr([-1000, 300, 300, 300, 300, 300])` | `≈0.15238` (15.24%) | Newton's method root of the NPV function above; re-checked by confirming `npv(irr_value, cashflows) ≈ 0` |
| `roi(150.0, 100.0)` | `0.5` | `(150-100)/100` |
| `cagr(1000.0, 2000.0, 5.0)` | `≈0.14870` | `(2000/1000)^(1/5) - 1` |
| `wacc(600.0, 400.0, 0.10, 0.05, 0.30)` | `0.074` | `0.6*0.10 + 0.4*0.05*0.7` |
| `max_drawdown([100, 110, 90, 95, 120])` | `≈0.1818` | worst peak-to-trough: `(110-90)/110` |
| `payback_period([-1000, 400, 400, 400])` | `2.5` | breaks even 2.5 periods in, by linear interpolation within period 3 |

## Edge-case behavior worth knowing

* **Every division-by-population-or-zero guard in `demographics` and `economic_indicators`
  returns `0.0`, not `NaN` or an error.** `crude_birth_rate(100.0, 0.0)`,
  `gdp_growth(100.0, 0.0)`, `unemployment_rate(5.0, 0.0)`, and every sibling with a `<= 0.0` (or
  `fabs(x) < 1e-15`) guard on their denominator all return a plain `0.0`. A caller cannot
  distinguish "the rate really is zero" from "the input was degenerate" without checking the
  denominator itself before the call.
* **`rule_of_72` returns `1e30`, not `0.0` or an error, for a non-positive rate** — a large finite
  sentinel meant to read as "effectively never doubles" in a downstream comparison, not `0.0`
  which would misleadingly read as "doubles instantly."
* **`payback_period` returns `-1.0`** when the cash flows never recover the initial investment
  (or the input list is empty) — a negative sentinel a caller must special-case, since a real
  payback period is never negative.
* **`irr` has no convergence guarantee.** It runs Newton's method for up to `max_iter` (default
  `100`) steps and simply returns whatever `r` it last reached if `tol` (default `1e-6`) is never
  satisfied or the derivative underflows below `1e-15` — there is no separate signal distinguishing
  a converged root from a Newton run that stalled or diverged. Always sanity-check by feeding the
  returned rate back into `npv` and confirming it lands near zero, the same check
  `test_wave13.mojo`'s own pinned test performs.
* **`sharpe_ratio` and `max_drawdown` both return exactly `0.0` for degenerate inputs** — fewer
  than two data points, or a zero standard deviation / zero peak — rather than `NaN`, so a `0.0`
  Sharpe ratio from this function can mean either "no measurable risk-adjusted return" or "not
  enough data to compute one."

## Verification notes

The four real pinned suites above were read in full, not sampled: `tests/mojo/test_wave31.mojo`
(currency, alongside convex optimization and survival analysis in the same wave),
`test_wave84.mojo` (demographics, alongside telecommunications and composites),
`test_wave56.mojo` (economic indicators), and `test_wave13.mojo` (finance, alongside numerical
differentiation and a state-machine test). Every formula-check value in the tables above was
independently recomputed from the plain-Python translation of the real Mojo source in
`mojo/engine/currency.mojo`, `demographics.mojo`, `economic_indicators.mojo`, and `finance.mojo`,
and matches both the pinned test tolerance and the source formula — including the two Gini
coefficient values, which are not asserted exactly in `test_wave56.mojo` (it only asserts
`0.0` for equal incomes and an ordering between two unequal cases) and were computed independently
here from the module's own sorted-rank formula, `G = (2·Σ(i·y_i) - (n+1)·Σy_i) / (n·Σy_i)`.

**Next:** see [FinQA exact execution](../benchmarks/finqa-exact-execution.md) and [Program
execution scoring](program-execution-scoring.md) for the full financial-QA benchmark that exposed
`round_currency`'s rounding bug, or [Ecology and organismal biology
kernels](ecology-and-organismal-biology-kernels.md) for the unrelated, purely ecological
`population` module this page's `demographics` module is not to be confused with.
