---
icon: traffic-light
description: Traffic-signal timing and level-of-service formulas, physical oceanography, mine-planning economics with blasting and ventilation arithmetic, and nuclear/reactor decay physics — four independent engineering-formula modules, not one integrated safety suite.
---

# Transportation and hazard-safety kernels

Four modules that share a page more because of where they sit in the engine's kernel tree than because
of what they compute: `traffic_signal` is intersection-timing arithmetic for road engineers, `marine` is
physical oceanography, `mining` is the economics and process arithmetic of running a mine, and `nuclear`
is radioactive-decay and reactor physics. None of the four imports another, and none shares a function
name with any other — the pairing is topical (transportation control, and three domains where getting an
engineering number wrong has real hazard consequences), not architectural. Two of the four turn out to
cover narrower or different ground than their names suggest, which this page verifies against the real
source rather than assumes: `marine` is oceanography, not naval/ship engineering (no hulls, no propulsion,
no structural loads — see below), and `mining` is dominated by extraction economics and comminution, with
only two of its twelve functions touching worker safety or ground stability at all.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Webster's formula: 12s of lost time per cycle, critical lane-group flow ratios summing to 0.85
runtime.execute("traffic_signal", "cycle_length_webster", [12.0, 0.85])["result"]
# 153.33333333333331 -- optimal signal cycle length, in seconds

# Fe-56, the nuclide with the highest binding energy per nucleon of any commonly cited isotope
runtime.execute("nuclear", "binding_energy_per_nucleon", [492.0, 56.0])["result"]
# 8.785714285714286 -- MeV/nucleon
```

## The modules

| Module | What it does |
| --- | --- |
| `traffic_signal` | Signalized-intersection engineering: Webster cycle length, effective green and green ratio, lane capacity, volume-to-capacity, uniform (HCM) delay, pedestrian crossing time, yellow and all-red clearance intervals, level-of-service classification, intersection capacity utilization, and peak-hour factor. |
| `marine` | Physical oceanography: seawater density, deep- and shallow-water wave speed and period, significant wave height, tidal range, mixed-layer depth, Ekman depth, the Coriolis parameter, Brunt-Väisälä buoyancy frequency, salinity from conductivity, and hydrostatic pressure at depth. |
| `mining` | Mine-planning economics and process engineering: ore grade, strip ratio, recovery rate, mill throughput, Bond work-index comminution energy, cut-off grade, dilution, net smelter return, reserve life, blasting powder factor, ventilation quantity, and subsidence factor. |
| `nuclear` | Radioactive decay and reactor physics: exponential decay and its half-life/activity inverses, binding energy per nucleon, mass defect, reaction Q-value, neutron multiplication, inverse-square dose-rate falloff, exponential shielding attenuation, and a proportionality estimate for critical mass. |

## `traffic_signal`: Webster timing and HCM delay

| Function | What it does |
| --- | --- |
| `cycle_length_webster(total_lost_time, critical_vc_ratio)` | Webster's optimal cycle length, `C = (1.5L + 5) / (1 - Y)`. |
| `effective_green(actual_green, start_loss, end_gain)` | `g = G - start_loss + end_gain`. |
| `green_ratio(effective_green_val, cycle_length)` | `g / C`. |
| `capacity_lane(saturation_flow, green_ratio_val)` | `c = s * (g/C)`. |
| `volume_to_capacity(volume, capacity)` | `v / c`. |
| `delay_uniform(cycle, green_ratio_val, vc_ratio)` | HCM/Webster uniform-delay term `d1 = 0.5*C*(1-g/C)^2 / (1 - min(1,X)*(g/C))`. |
| `pedestrian_crossing_time(distance, walk_speed)` | `t = d / v`. |
| `yellow_interval(perception_time, velocity, deceleration, grade)` | ITE yellow-change formula `Y = t + v / (2*(a + 9.81*G))`. |
| `all_red_interval(width, length, velocity)` | `AR = (W + L) / v`. |
| `level_of_service_delay(delay_sec)` | HCM signalized-intersection LOS, `1`(A, ≤10s) through `6`(F, >80s). |
| `intersection_capacity_utilization(sum_critical_vc, total_lost, cycle_length)` | `ICU = Σ(v/s)_crit + L/C`. |
| `peak_hour_factor(peak_volume, peak_15min_volume)` | `PHF = V / (4 * V15)`. |

This module has a real pinned test suite, `tests/mojo/test_wave97.mojo` (the auto-generated
`mojo/tests/libs/test_traffic_signal.mojo` also exists, calling every function once with `0.5` literals
and checking only finiteness). The pinned suite chains through a realistic four-phase intersection: 12
seconds of total lost time against critical flow ratios summing to `0.85` gives
`cycle_length_webster(12.0, 0.85) = 23.0 / 0.15 = 153.333...` seconds; a 30-second displayed green with a
2.5-second start-up loss and a 1.5-second end gain gives `effective_green(30.0, 2.5, 1.5) = 29.0`; and at
that cycle length `green_ratio(29.0, 153.333...) = 0.189`. Feeding a cycle of 90 seconds, a green ratio of
`0.4`, and a v/c ratio of `0.8` into `delay_uniform` gives `0.5*90*0.36/0.68 = 23.82` seconds/vehicle of
uniform delay — comfortably inside HCM's LOS C band (`level_of_service_delay(23.82) == 3`). The suite also
walks every LOS boundary exactly: `level_of_service_delay(10.0) == 1`, `(20.0) == 2`, `(35.0) == 3`,
`(55.0) == 4`, `(80.0) == 5`, and anything above falls to `6` (F) — each cutoff is inclusive of its own
band, tested at the boundary value itself.

{% hint style="warning" %}
**`cycle_length_webster` only guards the exact singularity, not real-world oversaturation.** Its own
comment says `# Y = 1.0 saturates the intersection and zeros the denominator`, and the code returns `0.0`
for that one exact value — but an oversaturated intersection, where the critical flow ratios sum to
*more* than `1.0`, is a completely ordinary real condition (a lane group failing during rush hour, not a
data-entry edge case), and for `Y > 1.0` the `(1 - Y)` denominator goes negative while the numerator stays
positive. `cycle_length_webster(10.0, 1.05)` returns `-400.0` — a negative cycle length in seconds, not an
error, not a clamp, not the `0.0` sentinel the function uses for the one input value it does catch. A
caller that doesn't independently check `critical_vc_ratio < 1.0` before calling this function can get a
silently negative "optimal cycle length" out of a failing intersection.
{% endhint %}

## `marine`: physical oceanography, not naval or ship engineering

The hint for this page named "marine/naval engineering" as the expected scope; reading
`mojo/engine/marine.mojo`'s own docstring — "Marine Science / Oceanography Library... fundamental
oceanographic equations including wave mechanics, tidal dynamics, Coriolis effects, density estimation,
and pressure calculations" — and every function body confirms the module is physical oceanography, full
stop. There is no hull form, no propulsion, no structural load, no vessel stability anywhere in it; the
"marine" in the name means "of the sea," not "of ships."

| Function | What it does |
| --- | --- |
| `seawater_density(temperature, salinity)` | Simplified linear density approximation, `ρ ≈ 1025 + 0.7(S-35) - 0.15(T-10)` kg/m³. |
| `wave_speed_deep(wavelength, g)` | Deep-water dispersion relation, `c = √(gλ/2π)`. |
| `wave_speed_shallow(depth, g)` | Shallow-water wave speed, `c = √(gd)`. |
| `wave_period(wavelength, speed)` | `T = λ / c`. |
| `significant_wave_height(energy_density)` | `Hs = 4√(m0)` from the spectral zeroth moment. |
| `tidal_range(high_tide, low_tide)` | `high - low`. |
| `mixed_layer_depth_estimate(wind_speed, latitude)` | Simplified estimate, `MLD ≈ 0.5*wind² + 10` metres. |
| `ekman_depth(wind_stress, coriolis, eddy_viscosity)` | `D_E = π√(2*Av / \|f\|)`. |
| `coriolis_parameter(latitude_deg)` | `f = 2Ω sin(φ)`, `Ω = 7.2921e-5` rad/s. |
| `buoyancy_frequency(drho_dz, rho0, g)` | Brunt-Väisälä frequency, `N = √(-g/ρ0 · dρ/dz)`, `0` if the water column is unstable. |
| `salinity_from_conductivity(conductivity, temperature)` | Simplified PSU estimate, `S ≈ 0.5*C*(1 - 0.02(T-25))`. |
| `ocean_pressure_at_depth(depth, density, g)` | Hydrostatic pressure, `P = ρgd`. |

Every number below is lifted from the real pinned suite, `tests/mojo/test_wave71.mojo` (the
auto-generated `mojo/tests/libs/test_marine.mojo` also exists, smoke-testing every function at `0.5`
literals for finiteness only). At the reference point `T=10°C, S=35 PSU`, `seawater_density` returns
exactly `1025.0`; warming to `20°C` at the same salinity gives `1023.5` (warmer water is less dense), and
raising salinity to `40` at `10°C` gives `1028.5` (saltier water is denser) — both terms of the linear
approximation checked independently. `coriolis_parameter(90.0)` (the pole) gives `2Ω = 1.45842e-4`,
`coriolis_parameter(0.0)` (the equator) gives exactly `0`, and `coriolis_parameter(30.0)` gives exactly
`Ω = 7.2921e-5` since `sin(30°) = 0.5`. `buoyancy_frequency(-0.01, 1025.0, 9.81)` — a stable water column,
density falling with height — returns `√(9.81/1025*0.01) ≈ 0.00978` rad/s; flip the sign to `+0.01`
(density *rising* with height, an unstable column) and the function returns `0.0` rather than the complex
number the raw formula would otherwise imply.

{% hint style="warning" %}
**`mixed_layer_depth_estimate` silently ignores the `latitude` argument it accepts.** The function's own
docstring gives its complete formula — `MLD ≈ 0.5 * wind² + 10` — and that formula never mentions
latitude; reading the body confirms it: `return 0.5 * wind_speed * wind_speed + 10.0` never touches the
second parameter at all. Calling `mixed_layer_depth_estimate(12.0, 0.0)` (equator) and
`mixed_layer_depth_estimate(12.0, 89.0)` (near the pole) both return exactly `82.0` — real mixed-layer
depth genuinely depends on latitude through the Coriolis-driven Ekman dynamics this same module implements
one function away (`ekman_depth`, immediately below it in the file), so a caller passing different
latitudes expecting a different answer is passing a parameter that does nothing. This is worth contrasting
with `ekman_depth` two functions later, which accepts a `wind_stress` argument it *also* never uses — but
says so directly in its own docstring ("`wind_stress` is accepted for API consistency but not used in the
simplified Ekman depth formula"). `mixed_layer_depth_estimate` has no equivalent disclosure; the dead
parameter is real but undocumented.
{% endhint %}

## `mining`: extraction economics and comminution, not geology or dedicated safety

The hint for this page asked whether `mining` leans toward geology/extraction or toward safety. Reading
`mojo/engine/mining.mojo` end to end settles it: ten of twelve functions are mine-planning economics
(grade, strip ratio, recovery, cut-off grade, dilution, net smelter return, reserve life) and comminution
process engineering (mill throughput, Bond work-index energy, blasting powder factor). There is no
mineralogy, no stratigraphy, no rock-strength testing anywhere — this is not a geology module. Only two
functions touch anything safety- or stability-adjacent: `ventilation_quantity` (fresh-air supply per
underground worker) and `subsidence_factor` (a ground-movement ratio). "Mining engineering" here means the
economics and metallurgical-process side of running a mine, with a thin, secondary slice of ventilation
and ground-control arithmetic — not a dedicated hazard/safety suite.

| Function | What it does |
| --- | --- |
| `ore_grade(metal_mass, ore_mass)` | `Grade = (metal/ore) * 100`, percent. |
| `strip_ratio(waste_volume, ore_volume)` | `SR = waste / ore`. |
| `recovery_rate(metal_recovered, metal_in_feed)` | `R = (recovered/feed) * 100`, percent. |
| `mill_throughput(feed_rate, hours)` | `T = rate * hours`, tonnes. |
| `bond_work_index_energy(wi, p80, f80)` | Bond's law comminution energy, `E = 10*Wi*(1/√P80 - 1/√F80)` kWh/t. |
| `cut_off_grade(mining_cost, processing_cost, metal_price, recovery)` | `COG = (MC+PC) / (Price * Recovery) * 100`; **`recovery` here is a 0–1 fraction.** |
| `dilution_factor(tonnes_waste_in_ore, tonnes_ore)` | `D = waste / (waste + ore) * 100`, percent. |
| `net_smelter_return(metal_price, grade, recovery, smelting_cost)` | `NSR = Price*(Grade/100)*(Recovery/100) - SC`; **`recovery` here is a 0–100 percent.** |
| `reserve_life(tonnes_reserve, annual_production)` | `Life = reserve / production`, years. |
| `powder_factor(explosive_kg, rock_tonnes)` | `PF = explosive / rock`, kg/t. |
| `ventilation_quantity(workers, airflow_per_worker)` | `Q = n * q`, m³/s. |
| `subsidence_factor(extraction_height, depth)` | `SF = extraction_height / depth`. |

The real pinned suite, `tests/mojo/test_wave78.mojo` (alongside the auto-generated
`mojo/tests/libs/test_mining.mojo`, which only smoke-tests finiteness), works a coherent small-mine
example: `bond_work_index_energy(15.0, 100.0, 10000.0)` — a Bond work index of 15 kWh/t grinding ore from
an 80%-passing feed size of 10,000 μm down to 100 μm product — gives `150*(0.1 - 0.01) = 13.5` kWh/t.
`net_smelter_return(2000.0, 1.5, 92.0, 5.0)` — $2,000/t metal, 1.5% ore grade, 92% recovery, $5/t smelting
cost — gives `2000*0.015*0.92 - 5 = 22.6` $/t of ore. `cut_off_grade(5.0, 10.0, 2000.0, 0.9)` — the same
$2,000/t metal price at 90% recovery, against $5/t mining plus $10/t processing cost — gives
`15/(2000*0.9)*100 ≈ 0.833%`: any block of ore grading below that is worth less to mine than it costs.

{% hint style="warning" %}
**`recovery` means two different things in two functions of the same module.** `cut_off_grade`'s own
docstring specifies `recovery: Recovery (0-1)` and the pinned test calls it with `0.9`; `net_smelter_return`'s
docstring specifies `recovery: Recovery (%)` and divides it by `100` internally, and the pinned test calls
it with `92.0`. Both are individually correct implementations of their respective real formulas, and both
are internally consistent with their own docstrings — but a caller who takes `recovery_rate`'s output
(which itself returns a 0–100 percent, e.g. `90.0`) and feeds it straight into `cut_off_grade` expecting the
same convention `net_smelter_return` uses gets a cut-off grade smaller by two orders of magnitude:
`cut_off_grade(5.0, 10.0, 2000.0, 90.0)` — recovery mistakenly passed as `90` instead of `0.9` — returns
`0.00833%` instead of `0.833%`, with no error, no warning, and no type distinguishing the two conventions.
{% endhint %}

## `nuclear`: reactor and radioactive-decay physics, distinct from `dosimetry`

The hint for this page asked to verify `nuclear` against the already-documented `dosimetry` module (see
[Pharmacology and toxicology kernels](pharmacology-and-toxicology-kernels.md)). Reading both source files
confirms they are genuinely different domains that happen to share vocabulary. `dosimetry` is radiation
*protection* physics for a person standing near a source — Gray, Sievert, ICRP tissue- and
radiation-weighting factors, kerma, buildup factor, tenth-value shielding layers. `nuclear` is *reactor and
nuclear-reaction* physics — atom counts, binding energy, mass defect, Q-values, neutron multiplication, and
criticality — plain unweighted physical quantities with no ICRP factor anywhere in the module. The overlap
is structural, not functional: both modules independently implement an exponential-decay function
(`nuclear.radioactive_decay`, `N(t) = N0·exp(-λt)`, tracking atom count; `dosimetry.activity_decay`,
`A(t) = A0·exp(-λt)`, tracking activity in Bq) and both implement an inverse-something falloff
(`nuclear.dose_rate_inverse_square`, a bare `D_ref·(d_ref/d)²` proportionality; `dosimetry.dose_rate`, the
same inverse-square shape but scaled by a named air-kerma-rate constant Γ). Neither module calls the
other, and no function name is shared between them — a caller doing health-physics dose-rate work wants
`dosimetry`; a caller doing decay-chain, binding-energy, or criticality arithmetic wants `nuclear`.

| Function | What it does |
| --- | --- |
| `radioactive_decay(n0, lambda_val, t)` | `N(t) = N0 · exp(-λt)`. |
| `half_life_from_lambda(lambda_val)` | `t½ = ln(2)/λ`; `0` if `λ ≈ 0`. |
| `lambda_from_half_life(half_life)` | `λ = ln(2)/t½`; `0` if `t½ ≈ 0`. |
| `activity(lambda_val, n)` | `A = λN`, becquerels. |
| `decay_constant_from_activity(activity_val, n)` | `λ = A/N`; `0` if `N ≈ 0`. |
| `binding_energy_per_nucleon(total_be, a)` | `BE/A`, MeV/nucleon; `0` if `A ≈ 0`. |
| `mass_defect(z, n, atomic_mass, mp, mn)` | `Δm = Z·mp + N·mn - M`. |
| `q_value(mass_reactants, mass_products, c2)` | `Q = (m_r - m_p)·c²`, MeV. |
| `neutron_multiplication(k_eff, generation)` | `N = k^generation`. |
| `dose_rate_inverse_square(dose_ref, d_ref, d)` | `D = D_ref·(d_ref/d)²`; `0` if `d ≈ 0`. |
| `shielding_attenuation(intensity0, mu, thickness)` | `I = I0·exp(-μx)`. |
| `critical_mass_estimate(density, sigma_f, nu)` | `ρ·σ_f·ν` — a bare proportionality, explicitly not an actual mass (own docstring: "not actual mass"). |

The real pinned suite, `tests/mojo/test_wave72.mojo` (alongside `mojo/tests/libs/test_nuclear.mojo`'s
finiteness-only smoke test), confirms the decay/half-life pair are exact inverses: `half_life_from_lambda`
and `lambda_from_half_life` chained round-trip a decay constant of `0.1` back to `0.1` to machine precision.
For helium-4, `mass_defect(2.0, 2.0, 4.00260, 1.00728, 1.00866)` — 2 protons and 2 neutrons at their free
masses, against He-4's real measured atomic mass of `4.00260` u — gives `Δm = 0.02928` u, the mass
converted to the alpha particle's binding energy. `neutron_multiplication(1.05, 10.0)` — a reactor running
5% supercritical for 10 generations — gives `1.05^10 ≈ 1.629`, a 63% neutron-population increase, while
`k_eff = 1.0` (exactly critical) holds the population flat at `1.0` regardless of generation count.
`dose_rate_inverse_square(100.0, 2.0, 4.0)` (doubling distance) gives a quarter of the dose, `25.0`; halving
distance instead (`dose_rate_inverse_square(100.0, 2.0, 1.0)`) gives four times the dose, `400.0` — the
same inverse-square law `dosimetry.dose_rate` implements with a physical constant in place of this
function's bare reference-dose ratio.

## Verification

All four modules have real, hand-written pinned test suites layered on top of their auto-generated
per-module smoke tests — this is not a "smoke tests only" family:

| Module | Auto-generated smoke test | Real pinned suite |
| --- | --- | --- |
| `traffic_signal` | `mojo/tests/libs/test_traffic_signal.mojo` | `tests/mojo/test_wave97.mojo` |
| `marine` | `mojo/tests/libs/test_marine.mojo` | `tests/mojo/test_wave71.mojo` |
| `mining` | `mojo/tests/libs/test_mining.mojo` | `tests/mojo/test_wave78.mojo` |
| `nuclear` | `mojo/tests/libs/test_nuclear.mojo` | `tests/mojo/test_wave72.mojo` |

The auto-generated files each call every function once with literal `0.5` arguments (or `0.5`/`0.5`
repeated for multi-argument functions) and check only that the result is finite — they pin no specific
numeric output. Every number worked out above comes from the real pinned suites or was independently
re-derived in plain Python against the formulas in `mojo/engine/traffic_signal.mojo`, `marine.mojo`,
`mining.mojo`, and `nuclear.mojo`, and can be reproduced by re-running the same arithmetic.

**Next:** see [Pharmacology and toxicology kernels](pharmacology-and-toxicology-kernels.md) for
`dosimetry`, the radiation-protection module `nuclear` is distinct from, or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
