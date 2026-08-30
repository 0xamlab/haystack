---
icon: briefcase
description: Queueing/inventory/LP-scoring formulas, earned-value and PERT project math, real-estate underwriting ratios and mortgage amortization, and telecom link-budget/traffic-engineering formulas -- four independent back-office formula libraries.
---

# Business operations and real-estate kernels

Four small, independent formula libraries that each cover one back-office domain in a screen's
worth of closed-form arithmetic: `operations_research` (queueing theory, inventory-order sizing,
and scorekeeping formulas that share names with, but do not implement, linear-program and
transportation-problem solving), `project_management` (earned-value management, PERT three-point
estimation, and a "critical path" function that is a pass-through, not a scheduling algorithm),
`real_estate` (the cap-rate/GRM/DSCR/LTV ratios and mortgage-payment formula an underwriter runs
by hand), and `telecommunications` (Shannon capacity, Erlang-B blocking probability, and the
SNR/BER/link-margin formulas behind a radio or trunk-line link budget). None of the four imports
from or is imported by any of the others, and none carries a struct or a status-code range —
every function here takes plain `Float64` (or, for period counts, `Int`) arguments and returns a
single `Float64`.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# D=1000 units/yr, ordering cost $50/order, holding cost $2/unit/yr
runtime.execute("operations_research", "eoq_quantity", [1000.0, 50.0, 2.0])["result"]
# 223.60679774997897 -- sqrt(2*D*S/H), the order size that minimizes ordering + holding cost

# $200,000 principal, 0.5%/month, 360 monthly payments (30-year fixed)
runtime.execute("real_estate", "mortgage_payment", [200000.0, 0.005, 360])["result"]
# 1199.1010503055138 -- P*r*(1+r)^n / ((1+r)^n - 1)
```

## The modules

| Module | What it does |
| --- | --- |
| `operations_research` | Linear-program objective scoring (not solving), single-cell and 2x2-tableau transportation-cost sums (not the transportation *problem*), a 3-task assignment-cost sum (not the assignment problem), EOQ order quantity and total cost, the newsvendor critical ratio, Little's Law in both directions, server utilization, and M/M/1 expected queue length and wait time. |
| `project_management` | Earned-value management: EV, SV, CV, SPI, CPI, EAC, ETC, VAC, and TCPI; PERT three-point estimation; task float; and a `critical_path_duration` that is a pre-summed pass-through, not a precedence-graph algorithm. |
| `real_estate` | Investment-property underwriting ratios (cap rate, gross rent multiplier, cash-on-cash return, DSCR, LTV, break-even ratio, price per sqft), NOI, a closed-form fixed-rate mortgage payment, equity build-up from amortization, appreciation, and a simplified single-cashflow IRR approximation. |
| `telecommunications` | Shannon channel capacity, Erlang-B blocking probability, BPSK bit-error rate, spectral efficiency, link margin, thermal noise power, SNR (linear and dB), Nyquist data rate, propagation delay, throughput, and availability percentage. |

## `operations_research`: queueing and inventory formulas, plus LP/transportation *scorekeeping*, not solving

| Function | What it does |
| --- | --- |
| `simplex_objective_value_2(c1, x1, c2, x2)` | `c1*x1 + c2*x2` — evaluates a candidate point, does not search for one. |
| `simplex_objective_value_3(c1, x1, c2, x2, c3, x3)` | `c1*x1 + c2*x2 + c3*x3` — same, three variables. |
| `transportation_cost(cost, allocation)` | `cost * allocation` — one cell of a shipping tableau. |
| `total_transportation_cost_2x2(c1, a1, c2, a2, c3, a3, c4, a4)` | `Σ(c_i * a_i)` over four fixed cells — the caller supplies both the costs and the (already decided) allocations. |
| `assignment_cost_3(c1, c2, c3)` | `c1 + c2 + c3` — the total cost of an assignment that has already been made for 3 tasks. |
| `eoq_quantity(demand, ordering_cost, holding_cost)` | `sqrt(2*D*S/H)` — the classic economic-order-quantity formula. |
| `eoq_total_cost(demand, ordering_cost, holding_cost)` | `sqrt(2*D*S*H)` — total annual ordering + holding cost at the EOQ. |
| `newsvendor_critical_ratio(cu, co)` | `cu / (cu + co)` — the critical fractile for a single-period stocking decision. |
| `little_law_l(lambda_rate, w)` | `L = λ * W` — expected number in a system. |
| `little_law_w(l, lambda_rate)` | `W = L / λ` — expected time in a system. |
| `utilization_factor(arrival_rate, service_rate)` | `ρ = λ / μ`. |
| `mm1_expected_queue_length(rho)` | `Lq = ρ² / (1 - ρ)`; `0.0` if `ρ` is NaN, infinite, negative, or `>= 1` (an unstable queue is reported as empty, not infinite). |
| `mm1_expected_wait_time(rho, mu)` | `Wq = ρ / (μ*(1-ρ))`; same degenerate-input guard, plus `0.0` if `μ <= 0`. |

**None of the four names that sound like OR solvers actually solve anything.** Reading
`operations_research.mojo`'s own docstring and every function body above confirms it: `simplex_objective_value_2`/`_3` only compute `Σ(c_i * x_i)` at a point the caller already picked — there
is no pivoting, no feasibility search, nothing resembling the simplex algorithm despite the name.
`transportation_cost` and `total_transportation_cost_2x2` likewise only sum `cost * allocation`
over cells the caller has already decided how to fill; there is no supply/demand balancing and no
size beyond the hardcoded 2x2 case. `assignment_cost_3` sums three costs the caller has already
matched to three tasks. This is a real, checkable difference from
[Combinatorics, convex optimization, and scipy-compatibility kernels](combinatorics-convex-optimization-and-scipy-compat-kernels.md)'s
`linear_programming` module, which **does** solve: `linear_programming.lp_solve_2var` runs vertex
enumeration to find an optimal `(x, y)`, and `linear_programming.transportation_cost` — same bare
function name as the one in this module, different signature and different job — runs the
Northwest-Corner method over arbitrary-size `supply`, `demand`, and `costs` arrays to produce a
feasible (not optimal) shipping plan. Calling `operations_research.transportation_cost(cost,
allocation)` with a single `(cost, allocation)` pair when what was wanted was
`linear_programming.transportation_cost(supply, demand, costs)`'s multi-cell solver produces a
plausible-looking number for the wrong problem.

A worked queueing chain, using the exact inputs `tests/mojo/test_wave68.mojo`
pins: a single M/M/1 server at `ρ = 0.8` (`λ = 4`, `μ = 5`) has `utilization_factor(4.0, 5.0) =
0.8`, `mm1_expected_queue_length(0.8) = 0.8² / 0.2 = 3.2` customers waiting on average, and
`mm1_expected_wait_time(0.8, 5.0) = 0.8 / (5 * 0.2) = 0.8` time units in queue. Halving the
utilization to `ρ = 0.2` collapses the queue by more than a factor of ten —
`mm1_expected_queue_length(0.2) = 0.04 / 0.8 = 0.05` — the quadratic-over-linear shape of the
M/M/1 formula, not a linear one, is why utilization above roughly 0.8 is where queueing systems
are usually kept from operating.

## `project_management`: EVM, PERT, and a critical path that is a pass-through

| Function | What it does |
| --- | --- |
| `earned_value(bac, pct_complete)` | `EV = BAC * pct_complete / 100`. |
| `schedule_variance(ev, pv)` | `SV = EV - PV`. |
| `cost_variance(ev, ac)` | `CV = EV - AC`. |
| `schedule_performance_index(ev, pv)` | `SPI = EV / PV`; `0.0` if `pv == 0`. |
| `cost_performance_index(ev, ac)` | `CPI = EV / AC`; `0.0` if `ac == 0`. |
| `estimate_at_completion(bac, cpi)` | `EAC = BAC / CPI`; `0.0` if `cpi == 0`. |
| `estimate_to_complete(eac, ac)` | `ETC = EAC - AC`. |
| `variance_at_completion(bac, eac)` | `VAC = BAC - EAC`. |
| `to_complete_performance_index(bac, ev, ac)` | `TCPI = (BAC - EV) / (BAC - AC)`; `0.0` if the denominator is `0`. |
| `critical_path_duration(task_durations_sum)` | Returns its one argument unchanged. |
| `float_time(late_finish, early_finish)` | `Float = LF - EF`. |
| `pert_estimate(optimistic, most_likely, pessimistic)` | `E = (O + 4M + P) / 6`. |

**`critical_path_duration` is a pass-through, not a critical-path algorithm.** Its own docstring
says as much: `"CP = sum (pass pre-computed sum)"`, and the body is a bare `return
task_durations_sum` — the caller is expected to have already walked the task network and summed
the durations along its longest path before this function ever runs. That is a genuinely
different job from
[Routing, scheduling & trade-offs](optimization-heuristics.md#the-critical-path-and-when-it-is-the-wrong-explanation)'s
`optimization.scheduling.rcpsp_bound_flat`, which takes the actual precedence graph (`pred_from`,
`pred_to`) and per-activity resource demands, computes the longest path itself, returns which
operations are on it (`critical_ops`), and additionally accounts for resource contention the
precedence-only path can't see. A caller that wants "what is the project's critical path" needs
`rcpsp_bound_flat`; `critical_path_duration` only echoes back a number someone else already
computed.

**`pert_estimate` computes the deterministic three-point mean, not a PERT distribution sample.**
It is easy to confuse with `distributions.sample_pert` (documented in
[Probability distributions and dependence kernels](probability-distributions-and-dependence-kernels.md)),
which draws a random value from a Beta-PERT distribution fitted to `(min, mode, max, lambda)`.
`pert_estimate(optimistic, most_likely, pessimistic)` returns the same single weighted-average
number every time for the same three inputs — `pert_estimate(2.0, 5.0, 14.0) = (2 + 20 + 14)/6 =
6.0`, always `6.0` — where `sample_pert` returns a different stochastic draw on every call. One is
the textbook point estimate a project plan reports; the other is a Monte Carlo input for
simulating schedule risk.

A full earned-value pass, hand-verified against the formulas above (values chosen independently
of the pinned test cases, so this exercises the chain rather than repeating it): a project with a
`$500,000` budget at completion (`BAC`), `42%` complete (`EV = 500000 * 0.42 = 210,000`), planned
value `PV = 230,000`, and actual cost `AC = 240,000`:

```python
bac, pv, ac = 500000.0, 230000.0, 240000.0
ev = runtime.execute("project_management", "earned_value", [bac, 42.0])["result"]     # 210000.0
sv = runtime.execute("project_management", "schedule_variance", [ev, pv])["result"]   # -20000.0 (behind schedule)
cv = runtime.execute("project_management", "cost_variance", [ev, ac])["result"]       # -30000.0 (over budget)
spi = runtime.execute("project_management", "schedule_performance_index", [ev, pv])["result"]  # 0.9130...
cpi = runtime.execute("project_management", "cost_performance_index", [ev, ac])["result"]      # 0.875
eac = runtime.execute("project_management", "estimate_at_completion", [bac, cpi])["result"]     # 571428.57...
vac = runtime.execute("project_management", "variance_at_completion", [bac, eac])["result"]     # -71428.57...
```

Both variances are negative and `CPI < 1.0`, so the project is simultaneously behind schedule and
over budget; `EAC` (`$571,429`) exceeds the original `$500,000` budget by exactly `-VAC`
(`$71,429`) — the two numbers are definitionally the same gap seen from opposite ends, which is a
useful self-check on any EVM chain built from these functions.

## `real_estate`: underwriting ratios and a closed-form mortgage

| Function | What it does |
| --- | --- |
| `cap_rate(noi, property_value)` | `NOI / Value * 100`; `0.0` if `\|value\|` is near zero. |
| `gross_rent_multiplier(price, annual_rent)` | `Price / Rent`; `0.0` if rent is near zero. |
| `cash_on_cash_return(annual_cashflow, total_invested)` | `CF / Invested * 100`; `0.0` if invested is near zero. |
| `debt_service_coverage(noi, annual_debt_service)` | `NOI / ADS`; `0.0` if ADS is near zero. |
| `loan_to_value(loan_amount, property_value)` | `Loan / Value * 100`; `0.0` if value is near zero. |
| `net_operating_income(gross_income, vacancy_rate, operating_expenses)` | `GI*(1-VR) - OE`. |
| `mortgage_payment(principal, monthly_rate, n_months)` | `P*r*(1+r)^n / ((1+r)^n - 1)`; `principal / n_months` (straight-line) if `rate <= 0` and `n_months > 0`; `0.0` if `n_months <= 0`. |
| `price_per_sqft(price, sqft)` | `Price / SqFt`; `0.0` if sqft is near zero. |
| `break_even_ratio(operating_expenses, debt_service, gross_income)` | `(OE + DS) / GI * 100`; `0.0` if income is near zero. |
| `internal_rate_of_return_approx(initial, cashflow, years)` | `(cashflow/initial)^(1/years) - 1`; `0.0` if `initial` is near zero, `years <= 0`, or the ratio is non-positive. |
| `equity_buildup(original_loan, remaining_loan)` | `Original - Remaining`. |
| `appreciation_value(initial_value, annual_rate, years)` | `PV * (1+r)^years`; returns `initial_value` unchanged if `years <= 0`. |

**`internal_rate_of_return_approx` is a two-point CAGR, not a multi-cashflow IRR solver.** A real
IRR finds the discount rate that zeroes the NPV of a whole series of periodic cashflows; this
function only ever sees a single `initial` outlay and a single terminal `cashflow`, and computes
the compound annual growth rate between the two — correct for "I put in `X`, I got out `Y`,
`n` years later, and nothing happened in between," and not a substitute for a real cashflow-series
IRR when there were interim distributions.

A full underwriting chain on one hypothetical property — purchase price and appraised value
`$950,000`, gross income `$120,000/yr`, `6%` vacancy, `$42,000/yr` operating expenses, `75%` LTV
financed at `6.5%`/30-year fixed — hand-computed and independently verified in Python against the
formulas above (no pinned test covers this exact combination, so treat these as a worked
derivation, not a quoted fixture):

```python
noi = runtime.execute("real_estate", "net_operating_income", [120000.0, 0.06, 42000.0])["result"]
noi   # 70800.0  -- 120000*0.94 - 42000

runtime.execute("real_estate", "cap_rate", [noi, 950000.0])["result"]           # 7.4526...
runtime.execute("real_estate", "gross_rent_multiplier", [950000.0, 118000.0])["result"]  # 8.0508...
runtime.execute("real_estate", "loan_to_value", [712500.0, 950000.0])["result"]  # 75.0

pmt = runtime.execute("real_estate", "mortgage_payment", [712500.0, 0.065 / 12, 360])["result"]
pmt   # 4503.48...  -- monthly payment on the $712,500 loan
ads = pmt * 12
runtime.execute("real_estate", "debt_service_coverage", [noi, ads])["result"]    # 1.3101... -- NOI covers debt service 1.31x
runtime.execute("real_estate", "break_even_ratio", [42000.0, ads, 120000.0])["result"]  # 80.03...
```

`DSCR = 1.31` clears the `1.20-1.25` floor most commercial lenders require; `break_even_ratio =
80.03%` says gross income could fall by roughly a fifth before operating expenses and debt service
together consume all of it. Five years of `3.5%`/yr appreciation on the same property —
`appreciation_value(950000.0, 0.035, 5)` — compounds to `$1,128,301.99`, and because that is the
only cashflow event in the holding period, feeding the same two numbers into
`internal_rate_of_return_approx(950000.0, 1128301.99, 5)` recovers `3.5%` exactly, which is the
correct self-check for a CAGR formula being fed a pure compounding scenario back at itself.

## `telecommunications`: link budget and traffic-engineering formulas, not topology or HTTP

| Function | What it does |
| --- | --- |
| `shannon_capacity(bandwidth, snr)` | `C = B * log2(1 + SNR)` bits/s; `0.0` if bandwidth `<= 0`. |
| `erlang_b(n, a)` | Erlang-B blocking probability for `n` trunks under offered load `a` Erlangs, via the exact recursive form `1/B(k) = 1 + (k/a)/B(k-1)`. |
| `bit_error_rate_bpsk(snr_linear)` | `BER ≈ 0.5 * exp(-SNR)` (simplified BPSK approximation); `0.5` if SNR is negative. |
| `spectral_efficiency(data_rate, bandwidth)` | `η = R / B` bits/s/Hz; `0.0` if bandwidth `<= 0`. |
| `link_margin(rx_power, rx_sensitivity)` | `Prx - sensitivity`, in dB. |
| `thermal_noise_power(bandwidth, temperature)` | `N = kTB`, `k = 1.38e-23` J/K. |
| `signal_to_noise_ratio(signal_power, noise_power)` | `S / N`; `0.0` if noise `<= 0`. |
| `snr_db(snr_linear)` | `10 * log10(SNR)`; `0.0` if SNR `<= 0`. |
| `data_rate_nyquist(bandwidth, levels)` | `R = 2*B*log2(M)`; `0.0` if bandwidth `<= 0` or levels `<= 1`. |
| `propagation_delay(distance, speed)` | `distance / speed`; `0.0` if speed `<= 0`. |
| `throughput(data_bits, total_time)` | `data_bits / total_time`; `0.0` if time `<= 0`. |
| `availability_percentage(uptime, total_time)` | `uptime / total_time * 100`; `0.0` if time `<= 0`. |

**None of this overlaps with the two other modules named around "network" in this corpus.**
[Networking and social-graph kernels](networking-and-social-graph-kernels.md) documents
`network_protocol` (HTTP status-code text, MIME-type lookup, query-string parsing — no socket, no
packet) and `network_analysis` (undirected-graph metrics: PageRank, centrality, connected
components — no signal, no channel). `telecommunications` is a third, disjoint thing again: every
function above operates on a physical or statistical-traffic quantity — bandwidth in Hz, SNR,
Erlangs of offered load, propagation speed — and none of its twelve functions takes an adjacency
list, a URL, or an HTTP status code as an argument. Grepping `mojo/engine/telecommunications.mojo`
and `network_protocol.mojo`/`network_analysis.mojo` confirms neither imports the other, and no
function name collides across all three modules.

**`erlang_b`'s recursion is the textbook one, verified by hand.** The classic Erlang-B recursive
formula is `B(0) = 1`, `B(k) = a*B(k-1) / (k + a*B(k-1))`; taking the reciprocal gives `1/B(k) = 1
+ (k/a) * (1/B(k-1))`, which is exactly the loop the source runs (`inv_b = 1.0 + inv_b * i / a`,
starting from `inv_b = 1.0`). `tests/mojo/test_wave84.mojo` pins
`erlang_b(0, 5.0) = 1.0` (zero trunks blocks every call) and asserts `erlang_b(10, 5.0)` falls
between `0.0` and `0.05`; re-running the recursion by hand gives `erlang_b(10, 5.0) =
0.018384570336648136` — ten circuits carrying 5 Erlangs of offered traffic block about `1.84%` of
attempts, consistent with published Erlang-B tables for that trunk group.

A link-budget chain, hand-computed and verified independently: a `20 MHz` channel at `290 K`
(room-temperature receiver) has a thermal noise floor of `thermal_noise_power(20e6, 290.0) =
1.38e-23 * 290 * 20e6 = 8.004e-14` W. A received signal of `2e-13` W against that floor gives
`signal_to_noise_ratio(2e-13, 8.004e-14) = 2.4988` (linear), or `snr_db(2.4988) = 3.977` dB, and
`shannon_capacity(20e6, 2.4988) = 20e6 * log2(3.4988) ≈ 36.14 Mbit/s` — the maximum error-free
rate that channel can theoretically carry at that SNR, before any modulation or coding overhead.

## Verification

All four `mojo/tests/libs/test_*.mojo` files for this batch
(`test_operations_research.mojo`, `test_project_management.mojo`, `test_real_estate.mojo`,
`test_telecommunications.mojo`) are auto-generated coverage smoke tests: every function is called
once with the literal argument `0.5` for every `Float64` parameter (`0.5` also stands in for the
one `Int` parameter each of `erlang_b` and `real_estate`'s three `Int`-typed functions —
`mortgage_payment`, `internal_rate_of_return_approx`, `appreciation_value` — actually receive the
literal `5`) and the test only checks the result is finite — none of the four pins a
specific numeric output. The real, hand-derived numeric assertions for this batch live instead in
`tests/mojo/test_wave68.mojo` (`operations_research`, alongside seismology and photonics; 18
`_assert(...)` calls across the 17 OR-specific test functions), `tests/mojo/test_wave76.mojo`
(`real_estate`, alongside metallurgy and game physics; 12 `test_*` functions, one per public
function, most pairing a normal case with a zero-guard check), `tests/mojo/test_wave96.mojo` (`project_management`,
alongside timber and spectroscopy — its own header calls out "70+ assertions" across all three
modules), and `tests/mojo/test_wave84.mojo` (`telecommunications`, alongside composites and
demographics; 25 `assert_true(...)` calls inside `test_telecommunications()`, though the file's own
trailing `print` on that function claims 28 — the discrepancy is in the source's comment, not in
this page's count, which was obtained by grepping the function body directly). Every specific number quoted on
this page traces to one of those four wave files or to an independent Python re-derivation of the
formula from `mojo/engine/{operations_research,project_management,real_estate,telecommunications}.mojo`,
noted inline above wherever it isn't a pinned test value.

**Next:** see the real LP solver and Northwest-Corner transportation heuristic these formulas are
often confused with in
[Combinatorics, convex optimization, and scipy-compatibility kernels](combinatorics-convex-optimization-and-scipy-compat-kernels.md),
the precedence-and-resource critical path in
[Routing, scheduling & trade-offs](optimization-heuristics.md), or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
