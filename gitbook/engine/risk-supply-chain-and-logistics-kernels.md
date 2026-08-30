---
icon: truck
description: Portfolio/returns-series risk metrics (VaR, Sharpe, drawdown) alongside five independent operations-research modules for demand forecasting, EOQ/safety-stock, procurement economics, logistics KPIs, and transportation engineering.
---

# Risk, supply-chain, and logistics kernels

Six modules for the arithmetic behind planning and measuring a physical or financial operation:
how risky a return series has been, how much of something to order and when, how well a
purchasing function is negotiating, how well a fleet and warehouse are running, and how a road or
intersection behaves under load. None of the six import each other, and — with one notable
exception below — none share a function name with another; the pairing is topical (a finance-risk
module next to five operations-research modules that all eventually touch "how much stock to
keep on hand"), not architectural. Every function in all six takes and returns plain `Float64`
scalars or `List[Float64]` — no structs, no status-code vocabulary.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Five returns, risk-free rate 0.0 -- mean 0.04, population std 0.014142135623730951
returns = [0.05, 0.03, 0.04, 0.06, 0.02]
runtime.execute("risk", "sharpe_ratio", [returns, 0.0])["result"]
# 2.8284271247461903 -- (mean - risk_free) / population standard deviation

# Annual demand 1,000 units, $50 to place an order, $2/unit/year to hold one
runtime.execute("inventory", "eoq", [1000.0, 50.0, 2.0])["result"]
# 223.60679774997897 -- sqrt(2 * demand * order_cost / holding_cost)
```

## The modules

| Module | What it does |
| --- | --- |
| `risk` | Portfolio and returns-series risk metrics: historical value-at-risk, conditional VaR (Expected Shortfall), max drawdown and drawdown series, Sharpe/Sortino/Calmar ratios, CAPM beta and Jensen's alpha, information ratio, and downside deviation. |
| `supply_chain` | Demand forecasting and production-lot economics: lead-time demand, the bullwhip ratio, forecast error (MAE/MAPE/bias/tracking signal), economic production quantity, type-1/type-2 service levels, total cost of ownership, and moving-average/exponential-smoothing forecasts. |
| `inventory` | Order-quantity and safety-stock formulas: EOQ, reorder point, safety stock from a z-score, total inventory cost, the newsvendor critical-ratio quantity, a normal-CDF service level, ABC classification, days of supply, inventory turnover, fill rate, and periodic-review order-up-to quantity. |
| `procurement` | Purchasing economics: total cost of ownership, price variance and PPV%, inventory turnover and days inventory outstanding, EOQ, reorder point, safety stock, weighted supplier scoring, savings percentage, maverick-spend ratio, and annualized early-payment discount. |
| `logistics` | Warehouse and fleet KPI ratios: vehicle and warehouse utilization, order fill rate, perfect-order rate, inventory turns, days of supply, cost per unit shipped, on-time delivery rate, dwell time, cross-dock throughput, route efficiency, and carbon per tonne-km. |
| `transportation` | Traffic and vehicle-operations engineering: level-of-service density, highway and intersection capacity, travel time, Webster-style signal delay, car-following headway, braking stopping distance, speed-dependent fuel consumption, passenger-car equivalents, deterministic queue length, vehicle operating cost, and crash rate. |

## `risk` is portfolio risk, not options risk

The hint for this page asked to check `risk` against the already-documented finance-domain
`option_pricing`/`option_greeks_batch` content in
[Batched chain greeks](ml-chain-greeks.md). Reading both source files, they turn out to be
unrelated except by the word "risk" appearing in both domains' vocabulary. `option_pricing.mojo`
implements Black-Scholes pricing, the option greeks (delta/gamma/vega/theta), binomial trees, put-call
parity, and implied volatility — derivatives pricing for a single contract given spot, strike,
rate, time, and volatility. `risk.mojo` implements none of that: every function here takes a
`List[Float64]` of historical returns (or portfolio values) and produces a scalar describing how
that series behaved — value-at-risk, drawdown, a risk-adjusted ratio, or a regression coefficient
against a benchmark. There is no shared function name, no shared parameter shape (`risk` never
takes a strike price or a volatility surface; `option_pricing` never takes a returns series), and
neither module imports the other. A caller pricing an option's Greeks wants
`option_pricing`/`option_greeks_batch`; a caller measuring a portfolio's historical risk wants
`risk`.

| Function | What it does |
| --- | --- |
| `value_at_risk(returns, confidence)` | Historical VaR: linearly-interpolated `(1-confidence)` percentile of the sorted return series, negated so a loss reports positive. |
| `conditional_var(returns, confidence)` | CVaR / Expected Shortfall: mean of the returns at or below the VaR threshold, negated the same way. |
| `max_drawdown(values)` | Largest peak-to-trough fractional decline across a value series. |
| `drawdown_series(values)` | The same fractional decline computed at every point, not just the maximum. |
| `sharpe_ratio(returns, risk_free=0.0)` | `(mean - risk_free) / population_std`; `0.0` if the series has essentially no spread. |
| `sortino_ratio(returns, target=0.0)` | `(mean - target) / downside_deviation`; penalizes only sub-target returns. |
| `beta(asset_returns, market_returns)` | CAPM beta: `cov(asset, market) / var(market)`. |
| `alpha(asset_returns, market_returns, risk_free=0.0)` | Jensen's alpha: `mean(asset) - rf - beta * (mean(market) - rf)`. |
| `information_ratio(returns, benchmark)` | `mean(excess) / std(excess)` where `excess = returns - benchmark`, element-wise. |
| `calmar_ratio(returns, values)` | `(mean(returns) * 252) / max_drawdown(values)` — an annualized-return-over-drawdown ratio. |
| `downside_deviation(returns, target=0.0)` | `sqrt(mean(min(r - target, 0)^2))`, dividing by the full sample size `n`, not just the count of sub-target observations. |

Every number below is drawn from the real pinned suite, `tests/mojo/test_wave24.mojo` (the
auto-generated `mojo/tests/libs/test_risk.mojo` also exists, smoke-testing every function at
literal `0.5` arguments for finiteness only). On the return series `[0.05, 0.03, 0.04, 0.06,
0.02]`, `sharpe_ratio` computes a mean of `0.04` and a **population** standard deviation (divisor
`n`, not `n-1`) of `0.014142135623730951`, giving `2.8284271247461903` — independently reproducible
in plain Python with no library beyond `math.sqrt`. On the ten-point series `[-0.10, -0.05, 0.02,
0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10]`, `value_at_risk(returns, 0.95)` interpolates between the
sorted series' 0th and 1st entries at fractional index `(1-0.95)*(10-1) = 0.45` —
`-(-0.10*0.55 + -0.05*0.45) = 0.0775` — and `conditional_var` at the same confidence averages every
return at or below that `-0.0775` return level, which is always `>=` the plain VaR since it is
averaging in the whole left tail, not just the boundary. On the value path `[100, 90, 95, 80,
100]`, `max_drawdown` reports `0.2` (peak `100`, trough `80`), and `drawdown_series` reports the
same trajectory point-by-point: `[0.0, 0.1, 0.05, 0.2, 0.0]`. `beta(returns, returns)` — an asset
regressed against itself — returns exactly `1.0`, and `alpha(returns, returns, 0.0)` — an asset
that never outperforms its own benchmark — returns exactly `0.0`, both algebraic identities that
would hold for any input series, not just the one in the test.

{% hint style="info" %}
**`downside_deviation`'s denominator is the whole sample, not the shortfall count.** Reading the
body directly — `ss += d*d` only when `d < 0.0`, then `sqrt(ss / Float64(n))` where `n` is
`len(returns)` regardless of how many terms were actually negative — this module's downside
deviation is smaller than a version that divided by the count of sub-target observations alone. A
series with one bad return out of five contributes only that one squared deviation but still
divides by `5`, not `1`; `sortino_ratio`, built on this function, inherits the same convention.
{% endhint %}

## `supply_chain`: forecasting and production-lot economics

| Function | What it does |
| --- | --- |
| `lead_time_demand(demand_rate, lead_time)` | `demand_rate * lead_time`. |
| `bullwhip_effect(demand_variance, order_variance)` | `order_variance / demand_variance`; ratio `> 1` means orders amplify the underlying demand signal. |
| `forecast_error_mae(actual, forecast)` | Mean absolute error between two equal-length series. |
| `forecast_error_mape(actual, forecast)` | Mean absolute percentage error, skipping any actual value of `0`. |
| `forecast_bias(actual, forecast)` | `mean(forecast - actual)`; positive means systematic over-forecasting. |
| `tracking_signal(actual, forecast)` | Cumulative forecast error divided by mean absolute deviation of that error. |
| `economic_production_qty(demand, setup_cost, holding_cost, production_rate)` | EPQ: `sqrt(2*D*S / (H*(1 - D/P)))`; `0.0` if the production rate does not exceed demand. |
| `total_cost_of_ownership(purchase, ordering, holding, shortage)` | Plain sum of the four named cost components. |
| `service_level_type1(stockout_probability)` | `1 - P(stockout)` — a cycle service level. |
| `fill_rate_type2(expected_shortage, demand)` | `1 - E[shortage] / demand` — a Type 2 (unit) fill rate. |
| `moving_average_forecast(data, periods)` | Average of the last `periods` observations, clamped to however much data actually exists. |
| `exponential_smoothing_forecast(data, alpha)` | Single exponential smoothing, seeded with `F(1) = data[0]`. |

The real pinned suite, `tests/mojo/test_wave44.mojo` (alongside the auto-generated
`mojo/tests/libs/test_supply_chain.mojo`, which only checks finiteness at `0.5` literals), works a
full worked chain: `forecast_error_mae([10, 20, 30], [12, 18, 33])` gives `7/3 ≈ 2.333`;
`forecast_bias` on the same shape (`[10,20,30]` vs. `[12,22,32]`, every forecast two units high)
gives exactly `2.0`; and `tracking_signal([100,100,100], [105,110,103])` gives exactly `3.0` — a
cumulative error of `18` over a mean absolute deviation of `6`. `moving_average_forecast([10, 20,
30, 40], 3)` averages the last three points to `30.0`, and the same data with `periods=2` gives
`35.0`. `exponential_smoothing_forecast([10, 20, 30], 0.5)` seeds at `10.0`, updates to `0.5*20 +
0.5*10 = 15.0`, then `0.5*30 + 0.5*15 = 22.5` — matching the pinned `22.5` exactly — and a lower
`alpha=0.1` run stays closer to the early data (`< 22.5`), which is exactly what a slower-adapting
smoothing constant should do.

## `inventory`: EOQ, safety stock, and the newsvendor model

| Function | What it does |
| --- | --- |
| `eoq(demand, order_cost, holding_cost)` | `sqrt(2*D*S/H)`; `0.0` if `holding_cost <= 0`. |
| `reorder_point(demand_rate, lead_time, safety_stock)` | `demand_rate*lead_time + safety_stock`. |
| `safety_stock(z_score, demand_std, lead_time)` | `z * demand_std * sqrt(lead_time)`. |
| `total_inventory_cost(demand, order_qty, order_cost, holding_cost)` | `(D/Q)*S + (Q/2)*H`; `0.0` if `order_qty <= 0`. |
| `newsvendor_qty(mean_demand, std_demand, cost_under, cost_over)` | `mean + z*std`, where `z = Φ⁻¹(cost_under / (cost_under + cost_over))` via a Beasley-Springer-Moro rational approximation. |
| `service_level(z_score)` | Standard normal CDF at `z_score`, via an Abramowitz-and-Stegun polynomial approximation. |
| `abc_classify(values)` | Top-20%-cumulative-value items get class `0` (A), next up to 50% get class `1` (B), the rest get class `2` (C). |
| `days_of_supply(inventory, daily_demand)` | `inventory / daily_demand`; `0.0` if `daily_demand <= 0`. |
| `inventory_turnover(cogs, avg_inventory)` | `cogs / avg_inventory`; `0.0` if `avg_inventory <= 0`. |
| `fill_rate(orders_filled, total_orders)` | `orders_filled / total_orders` (integer inputs); `0.0` if `total_orders <= 0`. |
| `periodic_review_order(target, on_hand, on_order)` | `max(0, target - on_hand - on_order)`. |

The real pinned suite is `tests/mojo/test_wave32.mojo` (the auto-generated
`mojo/tests/libs/test_inventory.mojo` only checks finiteness). `eoq(1000.0, 50.0, 2.0)` gives
`sqrt(50000) ≈ 223.607`, and feeding that same quantity back into `total_inventory_cost(1000.0,
223.607, 50.0, 2.0)` gives `≈ 447.21` — the minimum of the cost curve, confirmed by the test
against two other order quantities (`100` and `500`) that both cost more. `safety_stock(1.96,
10.0, 4.0)` gives `1.96 * 10 * sqrt(4) = 39.2`. `service_level(1.96) ≈ 0.975` and
`service_level(-1.96) ≈ 0.025` — the approximation is accurate to about four decimal places
against the true normal CDF (independently checked: the real error function gives `0.9750021...`
against this module's `0.9750022...`).

`abc_classify`'s thresholds are on **cumulative** value share, not each item's own share of the
total — which produces a result that reads oddly until the rule is stated precisely. Five items
valued `[50, 5, 100, 10, 35]` (total `200`) sort descending as `100, 50, 35, 10, 5`. The `100`-value
item alone is half the portfolio, but it is graded on where its own cumulative slice *ends*
(`100/200 = 0.50`), which lands exactly on the `<= 0.20` → A boundary's neighbor: `0.50` clears the
`0.20` cutoff for A but still qualifies for B (`<= 0.50`), so the single highest-value item — fully
50% of total value — is classified `1` (B), not `0` (A). Every item after it lands past the `0.50`
cutoff and is classified `2` (C), including the second-highest-value item (`50`, class C) which by
itself is a quarter of total value. With only five items and one dominant value, the ABC scheme's
20/30/50 cumulative bands compress almost the entire portfolio into B and C; the classification is
about where an item falls in the sorted cumulative curve, not about its rank or its own percentage
of the total.

## `procurement`: cost variance and supplier scoring

| Function | What it does |
| --- | --- |
| `total_cost_of_ownership(purchase, operating, maintenance, disposal)` | Plain sum of the four named lifecycle-cost components. |
| `price_variance(actual_price, standard_price, quantity)` | `(actual - standard) * quantity`. |
| `purchase_price_variance_pct(actual, standard)` | `(actual - standard) / standard * 100`; `0.0` if `standard == 0`. |
| `inventory_turnover(cogs, avg_inventory)` | `cogs / avg_inventory`; `0.0` if `avg_inventory == 0`. |
| `days_inventory_outstanding(inventory_turnover_val)` | `365 / inventory_turnover`; `0.0` if the input is `0`. |
| `economic_order_quantity(demand, ordering_cost, holding_cost)` | `sqrt(2*D*S/H)`; `0.0` only if `holding_cost == 0` exactly. |
| `reorder_point(daily_demand, lead_time, safety_stock_val)` | `daily_demand*lead_time + safety_stock_val`. |
| `safety_stock(z_score, demand_std, lead_time)` | `z * demand_std * sqrt(lead_time)`. |
| `supplier_score_weighted(scores_sum, weights_sum)` | `scores_sum / weights_sum`; `0.0` if `weights_sum == 0`. |
| `savings_percentage(old_price, new_price)` | `(old - new) / old * 100`; `0.0` if `old_price == 0`. |
| `maverick_spend_ratio(off_contract, total_spend)` | `off_contract / total_spend * 100`; `0.0` if `total_spend == 0`. |
| `payment_discount_annualized(discount_pct, full_days, discount_days)` | `(d/(1-d)) * (365/(full_days-discount_days)) * 100` — the annualized cost of forgoing an early-payment discount. |

The real pinned suite, `tests/mojo/test_wave82.mojo` (alongside the auto-generated
`mojo/tests/libs/test_procurement.mojo`), works a "2/10 net 30" early-payment discount end to
end: `payment_discount_annualized(2.0, 30.0, 10.0)` computes `d = 0.02`, a 20-day gap between the
discount window and full payment terms, and returns `(0.02/0.98) * (365/20) * 100 ≈ 37.245%` — the
implied annualized interest rate of *not* taking a 2% discount for paying 20 days early, high
enough that most treasury policies would take the discount. `economic_order_quantity(10000.0,
50.0, 2.0)` gives `sqrt(500000) ≈ 707.107`, and `safety_stock(1.96, 20.0, 7.0)` gives `1.96 * 20 *
sqrt(7) ≈ 103.72`.

{% hint style="warning" %}
**`economic_order_quantity` and `inventory.eoq` compute the identical formula but guard differently
against a negative holding cost.** `inventory.eoq` refuses any `holding_cost <= 0.0` and returns the
`0.0` sentinel. `procurement.economic_order_quantity` only checks `holding_cost == 0.0` — reading
the guard clause directly confirms a strictly-negative holding cost slips past it into
`sqrt(2*D*S/H)` with a negative argument under the root, which this codebase's `sqrt` (like
IEEE-754 `sqrt` generally) turns into `NaN` rather than `0.0`. A caller who validated only against
`inventory.eoq`'s guard and then swapped in `procurement.economic_order_quantity` expecting the same
sentinel behavior on bad input gets `NaN` back instead.
{% endhint %}

## `logistics`: KPI ratios with no guard clauses at all

| Function | What it does |
| --- | --- |
| `vehicle_utilization(loaded_km, total_km)` | `(loaded/total) * 100`. |
| `order_fill_rate(filled_orders, total_orders)` | `(filled/total) * 100`. |
| `perfect_order_rate(perfect, total)` | `(perfect/total) * 100`. |
| `inventory_turns(cogs, avg_inventory)` | `cogs / avg_inventory`. |
| `days_of_supply(avg_inventory, daily_demand)` | `avg_inventory / daily_demand`. |
| `warehouse_utilization(used_space, total_space)` | `(used/total) * 100`. |
| `cost_per_unit_shipped(total_cost, units_shipped)` | `total_cost / units_shipped`. |
| `on_time_delivery_rate(on_time, total_deliveries)` | `(on_time/total) * 100`. |
| `dwell_time(arrival_time, departure_time)` | `departure - arrival`, hours. |
| `cross_dock_throughput(items_processed, hours)` | `items / hours`. |
| `route_efficiency(actual_distance, optimal_distance)` | `(optimal/actual) * 100`. |
| `carbon_per_tonne_km(total_co2_kg, tonnes, km)` | `co2 / (tonnes * km)`. |

Every number here comes from the real pinned suite, `tests/mojo/test_wave99.mojo` (alongside the
auto-generated `mojo/tests/libs/test_logistics.mojo`): `vehicle_utilization(800.0, 1000.0) = 80.0`,
`inventory_turns(1000000.0, 200000.0) = 5.0`, `dwell_time(8.0, 14.0) = 6.0`,
`cross_dock_throughput(5000.0, 8.0) = 625.0`, and `carbon_per_tonne_km(50.0, 10.0, 100.0) = 0.05`
(50 kg CO2 moving 10 tonnes 100 km), each matching the formula above exactly.

{% hint style="warning" %}
**Reading `mojo/engine/logistics.mojo` end to end, none of its twelve functions contain a single
`if` statement.** Every one of them is a bare division, subtraction, or multiplication — no
zero-denominator guard, unlike its siblings on this page: `inventory.inventory_turnover` and
`procurement.inventory_turnover` both return `0.0` when `avg_inventory <= 0`, but
`logistics.inventory_turns` — the same `cogs / avg_inventory` formula, one module over — has no such
check. `logistics.cost_per_unit_shipped(100.0, 0.0)` returns IEEE-754 `+inf`, not `0.0`, and
`logistics.days_of_supply(avg_inventory=300.0, daily_demand=0.0)` does the same. This is the same
unguarded-division pattern already documented in `urban_planning` (see
[Building and facility systems kernels](building-and-facility-systems-kernels.md)) — a caller
piping a `0` denominator through any `logistics` function gets a silent `inf` back, not an error.
{% endhint %}

## `transportation`: engineering formulas, distinct from two other traffic-flavored functions in this codebase

The hint for this page asked to check `transportation` against the already-documented
`traffic_signal`/`urban_planning` content. Both of those modules do compute traffic-flavored
numbers, but neither one duplicates anything in `transportation`, and all three use the phrase
"level of service" for a genuinely different computation:

* `urban_planning.traffic_level_of_service(volume, capacity)` (documented in
  [Building and facility systems kernels](building-and-facility-systems-kernels.md)) is a bare
  volume-to-capacity ratio — a coarse, single-number congestion check a city planner runs against a
  whole corridor or zoning district.
* `traffic_signal.level_of_service_delay(delay_sec)` (documented in
  [Transportation and hazard-safety kernels](transportation-and-hazard-safety-kernels.md)) classifies
  a signalized intersection's average per-vehicle *delay* into the HCM's lettered A-F bands.
* `transportation.level_of_service_density(flow, speed)`, documented on this page, is neither of
  those: it is `flow / speed`, a vehicle-density number (veh/km/lane) in the Greenshields tradition
  used to characterize a freeway or highway segment, not an intersection or a zoning district, and
  it returns a raw density, not a classification letter.

No function name is shared among the three modules, none imports another, and the formulas compute
three different physical quantities that all happen to be called some flavor of "traffic level of
service" in transportation-engineering literature.

| Function | What it does |
| --- | --- |
| `level_of_service_density(flow, speed)` | `flow / speed`; `0.0` if `speed ≈ 0`. |
| `highway_capacity(lanes, capacity_per_lane)` | `lanes * capacity_per_lane`. |
| `travel_time(distance, speed)` | `distance / speed`; `0.0` if `speed ≈ 0`. |
| `delay_at_signal(cycle_length, green_ratio, arrival_rate, service_rate)` | The same simplified Webster delay formula as `traffic_signal.delay_uniform`, clamping the flow ratio `λ/μ` at `1.0`. |
| `headway(speed, reaction_time, deceleration)` | `reaction_time + speed / (2*deceleration)`; falls back to just `reaction_time` if `deceleration ≈ 0`. |
| `stopping_distance(speed, reaction_time, friction, grade)` | `speed*reaction_time + speed^2 / (2*g*(friction+grade))`, `g = 9.81 m/s²`. |
| `fuel_consumption_rate(base_rate, speed, optimal_speed)` | `base_rate * (1 + 0.01*(speed-optimal_speed)^2)`. |
| `passenger_car_equivalent(trucks_pct, terrain_factor)` | `1 + trucks_pct*(terrain_factor - 1)`. |
| `intersection_capacity(saturation_flow, green_ratio)` | `saturation_flow * green_ratio`. |
| `queue_length_estimate(arrival_rate, service_rate, time_period)` | `max(0, (arrival_rate - service_rate) * time_period)`. |
| `vehicle_operating_cost(fuel_cost, distance, fuel_efficiency)` | `fuel_cost * distance / fuel_efficiency`; `0.0` if `fuel_efficiency ≈ 0`. |
| `crash_rate(crashes, vmt_millions)` | `crashes / vmt_millions`; `0.0` if `vmt_millions ≈ 0`. |

Every number here is drawn from the real pinned suite, `tests/mojo/test_wave72.mojo` (alongside the
auto-generated `mojo/tests/libs/test_transportation.mojo`, finiteness-only): a four-lane highway at
2,000 veh/hr/lane gives `highway_capacity(4.0, 2000.0) = 8000.0`; a 90-second signal cycle with a
0.4 green ratio and a 0.6 volume-to-capacity ratio (`λ=0.3`, `μ=0.5`) gives `delay_at_signal(90.0,
0.4, 0.3, 0.5) = 0.5*90*0.36/0.76 ≈ 21.32` seconds/vehicle; a 20 m/s vehicle with a 2.5-second
reaction time on level, dry-ish pavement (`friction=0.35`) gives `stopping_distance(20.0, 2.5,
0.35, 0.0) = 50 + 400/6.867 ≈ 108.25` m; and 10% trucks on rolling terrain
(`terrain_factor=2.5`) gives `passenger_car_equivalent(0.10, 2.5) = 1.15`.

## Where the six modules literally duplicate each other

Two operations-adjacent formulas appear, verbatim, in more than one module on this page, and one
function *name* is reused for two different real-world quantities:

* **`eoq`/`economic_order_quantity`** — `inventory` and `procurement` implement the identical
  `sqrt(2*demand*order_cost/holding_cost)` formula under two different names, differing only in the
  guard clause noted above.
* **`safety_stock`** and **`reorder_point`** — `inventory` and `procurement` implement these two
  formulas identically, parameter-for-parameter (`safety_stock` even keeps the exact same argument
  names in both modules).
* **`inventory_turnover`/`inventory_turns`** — `inventory`, `procurement`, and `logistics` all
  compute `cogs / avg_inventory`; only the first two guard the zero-denominator case.
* **`days_of_supply`** — `inventory` and `logistics` both compute `inventory / daily_demand`;
  again, only `inventory`'s guards.
* **`total_cost_of_ownership` is the same function name used for two unrelated cost breakdowns.**
  `supply_chain.total_cost_of_ownership(purchase, ordering, holding, shortage)` sums the four
  classic inventory-model cost buckets. `procurement.total_cost_of_ownership(purchase, operating,
  maintenance, disposal)` sums four lifecycle-asset cost buckets instead — the same
  four-argument-sum shape, but none of the last three arguments mean the same thing between the two
  modules. A caller who reads only the function name and return type, without checking which
  module it came from, cannot tell which cost model it computed.
* **Two different "service level" definitions coexist deliberately.**
  `supply_chain.service_level_type1(stockout_probability) = 1 - stockout_probability` is a plain
  complement of an input probability the caller already estimated elsewhere.
  `inventory.service_level(z_score)` runs a full normal-CDF approximation on a z-score. Neither
  calls the other, and neither is "the" service level function — they answer the question from two
  different starting points (a stockout probability you already have, vs. a safety-stock z-score
  you want translated into a probability).

## Verification

All six modules have real, hand-verified pinned test suites layered on top of their
auto-generated per-module smoke tests — this is not a "smoke tests only" family:

| Module | Auto-generated smoke test | Real pinned suite |
| --- | --- | --- |
| `risk` | `mojo/tests/libs/test_risk.mojo` | `tests/mojo/test_wave24.mojo` |
| `supply_chain` | `mojo/tests/libs/test_supply_chain.mojo` | `tests/mojo/test_wave44.mojo` |
| `inventory` | `mojo/tests/libs/test_inventory.mojo` | `tests/mojo/test_wave32.mojo` |
| `procurement` | `mojo/tests/libs/test_procurement.mojo` | `tests/mojo/test_wave82.mojo` |
| `logistics` | `mojo/tests/libs/test_logistics.mojo` | `tests/mojo/test_wave99.mojo` |
| `transportation` | `mojo/tests/libs/test_transportation.mojo` | `tests/mojo/test_wave72.mojo` |

The auto-generated files each call every function once with literal `0.5` arguments (or a small
literal list, for the `List[Float64]` parameters) and check only that the result is finite — they
pin no specific numeric output. Every number given above comes from a real pinned suite or was
independently re-derived in plain Python against the formula in the corresponding
`mojo/engine/*.mojo` file, and can be reproduced by re-running the same arithmetic.

**Next:** see [Batched chain greeks](ml-chain-greeks.md) for the unrelated `option_pricing`/
`option_greeks_batch` finance modules, or [Transportation and hazard-safety kernels](transportation-and-hazard-safety-kernels.md)
for `traffic_signal`'s intersection-timing formulas, or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
