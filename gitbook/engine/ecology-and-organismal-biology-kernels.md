---
icon: bug
description: Population-dynamics and community-diversity formulas for general ecology, plus five taxon-focused libraries -- ecophysiology, entomology, microbiology, mycology, and bryology -- covering organism-environment physiology and growth kinetics in insects, bacteria, fungi, and mosses.
---

# Ecology and organismal biology kernels

Seven modules for biology above the single-cell/single-gene level and below the scale of climate or
geology: how a population of organisms grows, competes, and gets counted (`ecology`, `population`),
how one organism's body responds to its temperature, oxygen, and water environment (`ecophysiology`),
and four taxon-specific libraries for insects, bacteria, fungi, and mosses (`entomology`,
`microbiology`, `mycology`, `bryology`) that each pair a growth-kinetics model with the taxon's own
field-measurement conventions -- degree-days and trap counts for insects, colony-forming units and
D/Z-values for bacteria, spore dispersal and disease-progress curves for fungi, water-holding capacity
and peat accumulation for mosses. `population` is worth calling out by name: despite the word's
overload elsewhere in this corpus (the age-structured, actuarial sense used by demographic and finance
modules), this module's ten functions are exclusively ecological -- logistic and Lotka-Volterra
predator-prey simulation, two-species competition, extinction risk against a threshold -- and never
touch birth/death-rate tables, life expectancy, or any human-demographic quantity.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# ecology.logistic_growth returns an instantaneous RATE: r=0.5, N=50, K=100
runtime.execute("ecology", "logistic_growth", [0.5, 50.0, 100.0])["result"]
# 12.5 -- dN/dt at N=50 halfway to carrying capacity K=100

# population.logistic_growth takes the same three numbers in a different order
# and returns the population AFTER one full step, not a rate
runtime.execute("population", "logistic_growth", [50.0, 0.1, 100.0])["result"]
# 52.5 -- N + r*N*(1 - N/K) = 50 + 0.1*50*0.5 = 52.5, the next generation's count
```

## The modules

| Module | What it does |
| --- | --- |
| `ecology` | Community-ecology math: logistic and exponential population growth rates, a (buggy -- see below) carrying-capacity estimator, the Lotka-Volterra predator and prey rate equations, Margalef/Shannon/Simpson diversity indices, and Jaccard/Sørensen community-similarity coefficients, plus the species-area relationship. |
| `population` | A discrete-time population-dynamics simulation engine: single-step and multi-step logistic growth, single-step and multi-step Lotka-Volterra predator-prey, two-species Lotka-Volterra competition, a heuristic carrying-capacity/growth-rate estimator from raw counts, doubling time, and a boolean extinction-risk check. Purely ecological -- see the callout above. |
| `ecophysiology` | Whole-organism physiology as a function of its environment: Kleiber's-law metabolic scaling, thermal conductance, the Q10 temperature coefficient, evaporative water loss, aerobic scope, hypoxia tolerance (Pcrit), osmoregulation cost, cardiac output from the Fick principle, respirometric oxygen consumption, and field metabolic rate from the doubly-labelled-water method. |
| `entomology` | Insect population and pest-management math: degree-day accumulation for phenology models, exponential population growth, net reproductive rate and generation time, a Simpson diversity variant, trap-catch and infestation indices, biocontrol efficacy, larval mortality, and a mass/temperature insect metabolic-rate model. |
| `microbiology` | Bacterial growth kinetics and thermal-death (food-safety/sterilization) math: exponential growth, doubling time, Monod substrate-limited growth, generation time from two counts, colony-forming-unit back-calculation, a Kirby-Bauer MIC estimate, a biofilm-formation index, first-order thermal inactivation, and the D-value/Z-value pair from canning and sterilization theory. |
| `mycology` | Fungal growth and plant-disease epidemiology: a Gaussian-plume spore-dispersal estimate, mycelial radial growth rate, ergosterol-based biomass, sporulation density, infection efficiency, a thermal latent-period model, Vanderplank's logistic disease-progress rate, a temperature/humidity spore-germination probability, colony diameter, and a Lotka-Volterra competitive-exclusion index. |
| `bryology` | Moss, liverwort, and hornwort science, heavily weighted toward *Sphagnum* and peatland biogeochemistry: water-holding capacity, specific growth rate, peatland carbon accumulation, desiccation-recovery kinetics, a nitrogen-deposition growth response, a light/water-stress photosynthesis model, peat accumulation rate, an acidity estimate, patch-colonisation probability, and a biomass-to-litter turnover ratio. |

## `ecology`: community diversity, similarity, and population rate equations

| Function | What it does |
| --- | --- |
| `logistic_growth(r, n, k)` | The instantaneous logistic rate `dN/dt = r*n*(1 - n/k)`; `0.0` if `\|k\|` is below `1e-30`. |
| `exponential_growth(n0, r, t)` | `n0 * exp(r*t)`. |
| `carrying_capacity_estimate(n_max, r, n0, t)` | Attempts to invert the logistic-growth equation for `K` given an observed maximum, an initial size, a growth rate, and elapsed time. **Its own docstring and its own code disagree -- see below.** |
| `lotka_volterra_prey(r, n, alpha, p)` | `dN/dt = r*n - alpha*n*p`. |
| `lotka_volterra_predator(beta, n, p, delta)` | `dP/dt = beta*n*p - delta*p`. |
| `species_richness_margalef(s, n)` | `(S - 1) / ln(N)`; `0.0` if `ln(N)` is within `1e-30` of zero (i.e. `N = 1`). |
| `shannon_diversity(proportions_sum_plogp)` | Negates a caller-precomputed `Σ(pi * ln(pi))`. |
| `simpson_index(proportions_sum_p2)` | Passes a caller-precomputed `Σ(pi²)` straight through. |
| `simpson_diversity(simpson_d)` | `1 - D`. |
| `jaccard_similarity(shared, total_a, total_b)` | `shared / (A + B - shared)`; `0.0` if the denominator is within `1e-30` of zero. |
| `sorensen_similarity(shared, total_a, total_b)` | `2*shared / (A + B)`; `0.0` if the denominator is within `1e-30` of zero. |
| `species_area_relationship(c, area, z)` | `c * area^z`. |

`mojo/tests/mojo/test_wave70.mojo` (shared with acoustics and textile modules in that wave) pins exact
numeric assertions for all twelve functions. Two worked from that file: `logistic_growth(0.5, 50.0,
100.0) = 12.5` (used in the intro example above), and `lotka_volterra_predator(0.02, 100.0, 10.0, 0.5)
= 0.02*100*10 - 0.5*10 = 20 - 5 = 15.0` -- with zero prey (`lotka_volterra_predator(0.02, 0.0, 10.0,
0.5)`), the predator term vanishes and the population declines at exactly `-delta*p = -5.0`.

### A real bug: `carrying_capacity_estimate` multiplies by an extra factor its own docstring doesn't have

The docstring states the formula as `K = N_max / (1 - (1 - N_max/N0)*exp(-r*t))`. Expanding
`1 - (1 - N_max/N0)` as `(N_max/N0 - 1)` shows this is exactly `N_max / denom`, where `denom = 1 +
(ratio - 1)*exp(-r*t)` and `ratio = N_max/N0`. But the actual code is:

```
var ratio = n_max / n0
var denom = 1.0 + (ratio - 1.0) * exp(-r * t)
return n_max * ratio / denom
```

-- an extra `* ratio` that the docstring's own stated formula does not include. Running the numbers
independently confirms it: for `n_max=500, r=0.3, n0=50, t=10` (`ratio = 10`), the code returns
`3452.84`, while the docstring's own formula evaluates to `345.28` for the same inputs -- exactly
`ratio` apart, every time. Neither number is the textbook answer, either: numerically inverting the
actual continuous-time logistic solution `N(t) = K / (1 + ((K-N0)/N0)*exp(-r*t))` for `K` at these
same inputs (via root-finding, independently, in plain Python) gives `K ≈ 946.18` -- a third value,
different from both. `mojo/tests/mojo/test_wave70.mojo::test_carrying_capacity_estimate` only checks
`v > 0.0` for this exact input and separately checks the `n0 ≈ 0` fallback branch, so none of this is
caught by the existing test suite. A caller relying on this function for an actual carrying-capacity
estimate is getting a number that matches neither its own documented formula nor the logistic equation
it claims to invert. `population.carrying_capacity_estimate` (below) sidesteps the whole derivation
with a much simpler heuristic that has no such discrepancy.

## `population`: a discrete-time simulation engine, not a demographic model

| Function | What it does |
| --- | --- |
| `exponential_growth(N0, r, t)` | `N0 * exp(r*t)` -- identical formula to `ecology.exponential_growth`. |
| `logistic_growth(N, r, K)` | One discrete Euler step, `N' = N + r*N*(1 - N/K)`, `dt = 1` -- **the population after the step, not a rate**, and with no guard at all against `K = 0` (unlike `ecology.logistic_growth`'s `\|k\| < 1e-30` check). |
| `logistic_simulate(N0, r, K, n_steps)` | Runs `logistic_growth` `n_steps` times, returning a list of `n_steps + 1` values (the initial condition plus one per step); any step that goes negative is clamped to `0.0`. |
| `lotka_volterra_step(prey, pred, alpha, beta, delta, gamma, dt)` | One Euler step of both predator-prey equations at once (`dx/dt = alpha*x - beta*x*y`, `dy/dt = delta*x*y - gamma*y`); returns `[prey', pred']`, each clamped at `0.0`. |
| `lotka_volterra_simulate(prey0, pred0, alpha, beta, delta, gamma, dt, n_steps)` | Runs `lotka_volterra_step` `n_steps` times, returning `n_steps + 1` `[prey, pred]` rows. |
| `carrying_capacity_estimate(populations)` | `max(populations) * 1.1` -- a flat 10% headroom heuristic over a list of observed counts, `0.0` on an empty list. |
| `growth_rate_estimate(N_t, N_t1, K)` | Inverts one logistic step for `r`: `(N_t1 - N_t) / (N_t*(1 - N_t/K))`; `0.0` if that denominator is exactly `0.0`. |
| `competition_model(N1, N2, r1, r2, K1, K2, alpha12, alpha21)` | One Euler step of two-species Lotka-Volterra competition (`dN1/dt = r1*N1*(1 - (N1 + alpha12*N2)/K1)`, symmetric for `N2`); returns `[N1', N2']`, each clamped at `0.0`. |
| `population_doubling_time(r)` | `ln(2) / r`; no guard for `r = 0`. |
| `extinction_risk(population, threshold)` | `population < threshold`, a plain `Bool`. |

`mojo/tests/mojo/test_wave54.mojo` (shared with a logic-circuits suite and a hash-chain suite in that
wave) exercises all ten functions with real assertions, though several are range checks rather than
exact-value pins: `logistic_simulate(10.0, 0.5, 100.0, 50)` is asserted to return `51` entries ending
between `90` and `110` (converging near `K=100`, not pinned to a specific decimal), and
`lotka_volterra_step`/`competition_model` are asserted only to stay positive. Two are exact: `exponential_growth(100.0, 0.1, 10.0) ≈ 271.828` and `population_doubling_time(0.693147) ≈ 1.0`. The
`carrying_capacity_estimate` case is pinned exactly: four observed populations `[10, 50, 90, 80]` give
`max = 90`, and `90 * 1.1 = 99.0`, matching the test.

```python
runtime.execute("population", "carrying_capacity_estimate",
                [[10.0, 50.0, 90.0, 80.0]])["result"]
# 99.0 -- max(populations) * 1.1, a flat heuristic, not a logistic-model inversion

runtime.execute("population", "extinction_risk", [5.0, 10.0])["result"]
# True -- 5.0 < 10.0
```

## `ecophysiology`: how one organism's body meets its environment

| Function | What it does |
| --- | --- |
| `metabolic_rate_kleiber(mass_kg)` | Kleiber's law, `70 * mass^0.75` (kcal/day); `0.0` if `mass_kg <= 0`. |
| `thermal_conductance(heat_loss, t_body, t_ambient)` | `heat_loss / (T_body - T_ambient)`; `0.0` if the temperatures are equal. |
| `q10_temperature_coefficient(rate1, rate2, t1, t2)` | `(rate2/rate1) ^ (10 / (t2 - t1))`; `0.0` if either rate is non-positive or `t1 == t2`. |
| `evaporative_water_loss(surface_area, permeability, vpd)` | `surface_area * permeability * vpd`; `0.0` on any negative input. |
| `aerobic_scope(max_metabolic_rate, resting_metabolic_rate)` | `MMR - RMR`, clamped at `0.0` (never negative). |
| `hypoxia_tolerance(resting_mr, mass_specific_o2)` | `resting_mr / mass_specific_o2`, a critical-oxygen (Pcrit) estimate; `0.0` if the coefficient is non-positive. |
| `osmoregulation_cost(osmotic_gradient, membrane_permeability, body_mass)` | `gradient * permeability * body_mass`; `0.0` if gradient or permeability is negative (`body_mass` itself is unguarded). |
| `heart_rate_fick(vo2, o2_arterial, o2_venous)` | Cardiac output from the Fick principle, `vo2 / ((CaO2 - CvO2) * 10)`; `0.0` if the arteriovenous difference is non-positive. |
| `oxygen_consumption_rate(delta_o2_ppm, flow_rate_l_h, mass_kg)` | `(delta_o2_ppm * 1e-3) * flow_rate_l_h / mass_kg`; `0.0` if `mass_kg <= 0`. |
| `field_metabolic_rate(mass_kg, taxon_a, taxon_b)` | `taxon_a * mass_kg^taxon_b`, a doubly-labelled-water allometric equation; `0.0` if `mass_kg <= 0` or `taxon_a <= 0`. |

None of `ecophysiology`'s ten functions has a real pinned test -- `mojo/tests/libs/test_ecophysiology.mojo`
is the auto-generated smoke suite that calls each function once with the literal argument `0.5` and
checks only that the result is finite. Every number below was hand-computed independently from
`mojo/engine/ecophysiology.mojo`'s formulas, in plain Python, and two of them land on textbook
reference values:

```python
runtime.execute("ecophysiology", "q10_temperature_coefficient", [10.0, 20.0, 20.0, 30.0])["result"]
# 2.0 -- metabolic rate doubling over a 10 C rise is Q10's textbook-standard value

runtime.execute("ecophysiology", "heart_rate_fick", [250.0, 20.0, 15.0])["result"]
# 5.0 L/min -- VO2=250 mL/min, a-v O2 difference=5 mL/100mL, a realistic resting cardiac output
```

`heart_rate_fick`'s `* 10.0` divisor is a real unit conversion, not an arbitrary constant: `VO2` is in
mL O2/min and the arteriovenous difference is in mL O2 per **100 mL** blood, so the raw ratio comes out
in units of 100 mL blood/min; multiplying the denominator by `10` converts that to L/min in one step
(`x / 100 * 1000 = x / 10`). Checked independently against the standard clinical Fick-equation form
(`CO [L/min] = VO2 [mL/min] / ((CaO2 - CvO2) * 10)`), the conversion is correct.

## `entomology`: pest phenology and insect population statistics

| Function | What it does |
| --- | --- |
| `degree_days(t_max, t_min, t_base)` | `max(0, (Tmax+Tmin)/2 - Tbase)` -- single-day heat-unit accumulation for phenology models. |
| `accumulated_degree_days(daily_dd, days)` | `daily_dd * days`. |
| `population_growth_intrinsic(n0, r, t)` | `n0 * exp(r*t)` -- the same formula shared by `ecology.exponential_growth`, `population.exponential_growth`, and `microbiology.exponential_growth`, under a fourth name here. |
| `net_reproductive_rate(fecundity, survival)` | `fecundity * survival` (`R0`). |
| `generation_time(r0, r)` | `ln(R0) / r`; no guard against `r = 0` or `R0 <= 0`. |
| `doubling_time_population(r)` | `ln(2) / r`; no guard against `r = 0`. |
| `species_diversity_simpson(p_squared_sum)` | `1 - Σ(pi²)` -- the same one-line formula as `ecology.simpson_diversity`, under a different name, taking the sum directly rather than via a separate index step. |
| `trap_catch_index(n_caught, n_traps, n_days)` | `n_caught / (n_traps * n_days)`; no zero-denominator guard. |
| `infestation_rate(infested_units, total_units)` | `infested / total * 100`; no guard. |
| `biocontrol_efficacy(treated_pop, control_pop)` | `(control - treated) / control * 100`; no guard. |
| `larval_mortality_rate(initial_larvae, surviving_larvae)` | `(initial - surviving) / initial * 100`; no guard. |
| `metabolic_rate_insect(mass_mg, temperature_c)` | `0.01 * mass^0.75 * exp(0.07*T)`, computed via `exp(0.75*ln(mass))`; no guard against `mass_mg <= 0` (would produce a `NaN` from `ln` of a non-positive number). |

`mojo/tests/mojo/test_wave89.mojo` (shared with structural-engineering and perfumery suites in that
wave) pins all twelve functions with 25 total assertions. Worked from that file:
`population_growth_intrinsic(100.0, 0.1, 10.0) ≈ 271.8282` (`100 * e^1`), `generation_time(100.0, 0.1)
≈ 46.0517` (`ln(100)/0.1`), and `biocontrol_efficacy(30.0, 100.0) = 70.0` -- 100 untreated ("control")
insects against 30 surviving treated ones is 70% control efficacy.

```python
runtime.execute("entomology", "degree_days", [30.0, 20.0, 10.0])["result"]
# 15.0 -- (30+20)/2 - 10 = 25 - 10

runtime.execute("entomology", "biocontrol_efficacy", [30.0, 100.0])["result"]
# 70.0 -- (100 - 30) / 100 * 100
```

## `microbiology`: growth kinetics and thermal-death (food-safety) math

| Function | What it does |
| --- | --- |
| `exponential_growth(n0, growth_rate, time)` | `n0 * exp(growth_rate*time)`; returns `n0` unchanged if any argument is negative. |
| `doubling_time(growth_rate)` | `ln(2)/growth_rate`; `0.0` if `growth_rate <= 0`. |
| `monod_growth_rate(mu_max, substrate, ks)` | `mu_max * S / (Ks + S)`; `0.0` if the denominator is non-positive. |
| `bacterial_generation_time(n_initial, n_final, elapsed_h)` | `elapsed_h / log2(n_final/n_initial)`; `0.0` unless `n_initial > 0`, `n_final > n_initial`, `elapsed_h > 0`, and the resulting generation count is positive. |
| `colony_forming_units(colony_count, dilution_factor, volume_ml)` | `colony_count / (dilution_factor * volume_ml)`; `0.0` if either factor is non-positive. |
| `minimum_inhibitory_conc(inhibition_zone_mm, disk_conc_ug)` | Kirby-Bauer estimate: `disk_conc / (zone_mm - 6)` if `zone_mm > 6`, else `disk_conc` unchanged ("no inhibition at disc edge"). |
| `biofilm_formation_index(od_sample, od_control)` | `od_sample / od_control`; `0.0` if the control is non-positive. |
| `inactivation_first_order(n0, inactivation_rate, time)` | `n0 * exp(-inactivation_rate*time)`; returns `n0` unchanged if any argument is negative. |
| `d_value(inactivation_rate)` | `ln(10) / inactivation_rate`, the decimal reduction time; `0.0` if the rate is non-positive. |
| `z_value(d1, d2, t1, t2)` | `(t2-t1) / ln(d1/d2) * ln(10)` -- algebraically equal to the standard `(t2-t1) / log10(d1/d2)`; `0.0` if either D-value is non-positive or they're equal. |

Like `ecophysiology`, none of these ten has a real pinned test -- `mojo/tests/libs/test_microbiology.mojo`
is the auto-generated finite-check smoke suite. Hand-verified against
`mojo/engine/microbiology.mojo`, with one exact-round-number example chosen specifically to be
independently checkable:

```python
runtime.execute("microbiology", "z_value", [10.0, 1.0, 100.0, 110.0])["result"]
# 10.0 exactly -- a D-value that drops by a factor of 10 over a 10 C rise defines Z=10 C by
# construction; the natural-log formula in the source is verified algebraically equal to the
# textbook log10 form for this and every other input

runtime.execute("microbiology", "monod_growth_rate", [1.0, 5.0, 5.0])["result"]
# 0.5 -- at substrate = Ks, Monod growth is exactly half of mu_max, the textbook property
# that defines what Ks means
```

## `mycology`: fungal growth and plant-disease epidemiology

| Function | What it does |
| --- | --- |
| `spore_dispersal_distance(release_height, wind_speed, settling_velocity)` | `wind_speed * release_height / settling_velocity`, a simplified ballistic (no-turbulence) dispersal model; `0.0` if settling velocity is non-positive. |
| `mycelial_growth_rate(colony_diam_t2, colony_diam_t1, time_days)` | `(D2 - D1) / (2*days)` -- radial extension rate from two diameter measurements; `0.0` if `days <= 0`. |
| `fungal_biomass(ergosterol_ug_g, conversion_factor)` | `ergosterol / conversion_factor`; `0.0` if the factor is non-positive. |
| `sporulation_index(spore_count, colony_area_cm2)` | `spore_count / colony_area_cm2`; `0.0` if the area is non-positive. |
| `infection_efficiency(successful_infections, spores_deposited)` | `successful / deposited`; `0.0` if deposited is non-positive. |
| `latent_period(temperature, t_min, t_opt)` | `1 / ((T-Tmin)*(Topt-T))`, a symmetric-parabola thermal response; returns a sentinel `1e9` ("no growth") outside `(Tmin, 2*Topt - Tmin)`. |
| `epidemic_progress_rate(x1, x2, t1, t2)` | Vanderplank's logistic disease-progress rate, `(ln(x2/(1-x2)) - ln(x1/(1-x1))) / (t2-t1)`; `0.0` if either disease-intensity fraction is outside `(0, 1)` or `t2 <= t1`. |
| `spore_germination_prob(temperature, t_opt, relative_humidity)` | A Gaussian temperature response times a linear humidity requirement; `0.0` below 80% RH, otherwise clamped to `[0, 1]`. |
| `colony_diameter(growth_rate_mm_day, time_days)` | `2 * rate * days` -- diameter from a constant radial rate, growing from a near-zero inoculum; `0.0` on negative input. |
| `competitive_exclusion_index(alpha12, alpha21)` | `alpha12 * alpha21` -- a Lotka-Volterra competitive-exclusion ratio (`< 1` coexistence, `> 1` exclusion). |

`mycology`'s ten functions likewise have only the auto-generated smoke suite
(`mojo/tests/libs/test_mycology.mojo`). Hand-verified worked examples:

```python
runtime.execute("mycology", "mycelial_growth_rate", [40.0, 10.0, 5.0])["result"]
# 3.0 mm/day -- a colony grown from 10mm to 40mm diameter over 5 days

runtime.execute("mycology", "epidemic_progress_rate", [0.1, 0.4, 0.0, 10.0])["result"]
# 0.17917594... per day -- disease intensity rising from 10% to 40% over 10 days
```

`mycelial_growth_rate` and `colony_diameter` are inverses in spirit but not interchangeable in
practice: `mycelial_growth_rate` measures a rate from *two diameters already recorded at different
times*, while `colony_diameter` *predicts* a diameter forward from a constant rate assuming growth
started from a vanishingly small inoculum at `t=0` -- calling `colony_diameter` with a rate measured
between two non-zero diameters silently assumes the colony started at zero, which the two measurements
it was derived from did not.

## `bryology`: moss, liverwort, and peatland biogeochemistry

| Function | What it does |
| --- | --- |
| `sphagnum_water_holding(dry_mass_g, saturated_mass_g)` | `(W_sat - W_dry) / W_dry`; `0.0` if dry mass is non-positive. |
| `moss_growth_rate(initial_mass_g, final_mass_g, days)` | `ln(m_final/m_initial) / days`; `0.0` if any mass or `days` is non-positive. |
| `carbon_accumulation_peatland(npp_g_c_m2_yr, decomposition_g_c_m2_yr)` | `NPP - decomposition`; unguarded, can go negative (net carbon loss). |
| `bryophyte_desiccation_recovery(time_h, k_recovery, max_recovery)` | `max_recovery * (1 - exp(-k_recovery*time_h))`. |
| `nitrogen_deposition_effect(n_deposition_kg_ha_yr, optimal_n_kg_ha_yr)` | `1 - \|N - N_opt\| / N_opt`, clamped at `0.0`; `0.0` if `N_opt <= 0`. |
| `moss_photosynthesis_rate(par_umol_m2_s, pmax, half_sat_par, water_potential_mpa)` | Michaelis-Menten light response times an `exp(ψ/2)` water-stress factor (clamped at `1.0`); `0.0` if the light denominator is non-positive. |
| `peat_accumulation_rate(productivity_mm_yr, humification_factor)` | `productivity * (1 - humification_factor)`. |
| `sphagnum_acidity(cation_exchange_capacity, base_saturation)` | `3.0 + 2.0 * base_saturation / 100` -- **`cation_exchange_capacity` is accepted but never used, see below.** |
| `patch_colonisation_probability(spore_rain, substrate_suitability, moisture_factor)` | Product of the three factors, clamped at `1.0`. |
| `biomass_to_litter_ratio(standing_biomass_g_m2, annual_litter_g_m2_yr)` | `biomass / litter_production`, a mean-residence-time estimate (years); `0.0` if litter production is non-positive. |

Only the auto-generated smoke suite exists here too (`mojo/tests/libs/test_bryology.mojo`). Worked
examples, hand-computed from `mojo/engine/bryology.mojo`:

```python
runtime.execute("bryology", "sphagnum_water_holding", [2.0, 40.0])["result"]
# 19.0 -- (40-2)/2, within the 15-30 range the docstring says is typical for Sphagnum

runtime.execute("bryology", "biomass_to_litter_ratio", [500.0, 50.0])["result"]
# 10.0 years -- 500 g/m2 standing biomass over 50 g/m2/yr litter production
```

### A dead parameter: `sphagnum_acidity` ignores its own cation-exchange-capacity argument

The docstring frames this function as estimating "pH from Sphagnum cation exchange characteristics,"
and the signature takes `cation_exchange_capacity` as its first argument. Reading the body directly:

```
return 3.0 + 2.0 * base_saturation / 100.0
```

`cation_exchange_capacity` never appears in the computation. `sphagnum_acidity(1.5, 25.0)` and
`sphagnum_acidity(2.5, 25.0)` return the identical `3.5` -- only `base_saturation` moves the result, no
matter what CEC value is passed. This is consistent with `moe_routing.expert_choice_gate`'s unused
`token_score` argument documented on the
[mixture-of-experts and routing kernels](mixture-of-experts-and-routing-kernels.md) page: a parameter
that is present in the signature and the docstring's framing, but plays no part in the number the
function actually returns.

## Repeated formulas across module boundaries

Several formulas in this family appear more than once, under different module names, sometimes with
different parameter orders and always worth checking before assuming a name means the same thing
everywhere:

* **Exponential growth** (`N0 * exp(r*t)`) appears under that exact formula in `ecology`, `population`,
  and `microbiology`, and under the name `population_growth_intrinsic` in `entomology` -- four modules,
  one formula.
* **`logistic_growth`** is the same name in `ecology` and `population` for two different things: an
  instantaneous ODE rate in `ecology` (arguments `r, n, k`) versus the population *after* one discrete
  Euler step in `population` (arguments `N, r, K`) -- see the intro example at the top of this page.
* **`carrying_capacity_estimate`** is likewise the same name in both modules, for two very different
  approaches: `ecology`'s attempt at an analytic logistic-model inversion (which has the bug described
  above) versus `population`'s much simpler `max(observed) * 1.1` heuristic over a list of samples.
* **Simpson diversity** (`1 - Σpi²`) appears as `ecology.simpson_diversity` (taking a precomputed `D`)
  and as `entomology.species_diversity_simpson` (taking `Σpi²` directly, skipping the intermediate `D`
  step) -- the same one-line formula, two names, one fewer argument-passing step in the entomology
  version.
* **Lotka-Volterra competition coefficients** (`alpha12`/`alpha21`) show up at two different
  granularities: `mycology.competitive_exclusion_index` reduces them to a single ratio
  (`alpha12 * alpha21`), while `population.competition_model` uses the same two coefficients inside a
  full two-species discrete simulation step.

## Verification

Three of these seven modules have real, hand-pinned numeric test suites, not just coverage smoke
tests: `ecology` (`mojo/tests/mojo/test_wave70.mojo`, shared with `acoustics` and `textile`),
`entomology` (`mojo/tests/mojo/test_wave89.mojo`, shared with structural engineering and perfumery),
and `population` (`mojo/tests/mojo/test_wave54.mojo`, shared with logic circuits and hash chains) --
together covering all 32 functions across those three modules with real expected values, though
`population`'s simulation-returning functions (`logistic_simulate`, `lotka_volterra_step`,
`lotka_volterra_simulate`, `competition_model`) are asserted on bounds and shape (positivity, list
length, convergence range) rather than pinned to an exact decimal in every case. The other four
modules -- `ecophysiology`, `microbiology`, `mycology`, `bryology` -- have only the auto-generated
`mojo/tests/libs/test_*.mojo` smoke suites: each calls every function once with the literal argument
`0.5` and checks only that the result is finite, with no numeric value pinned anywhere. Every worked
example on this page for those four modules was hand-computed independently from the real formulas in
`mojo/engine/{ecophysiology,microbiology,mycology,bryology}.mojo`, and where a textbook reference value
exists (Q10 = 2.0 for a rate-doubling response, Monod growth at exactly half of `mu_max` when
`substrate = Ks`, a Z-value of exactly `10.0` for a D-value that drops tenfold over a 10°C rise), the
computed number was checked against it. The `ecology.carrying_capacity_estimate` bug and the
`bryology.sphagnum_acidity` dead parameter were each confirmed independently -- by direct algebraic
expansion and, for the carrying-capacity case, by numerically solving the actual logistic equation for
`K` with `scipy.optimize.brentq` -- rather than asserted from a single read of the source.

**Next:** see [Epidemiology and disease dynamics kernels](epidemiology-and-disease-dynamics-kernels.md)
for the same compartmental/rate-equation style of modeling applied to disease spread instead of species
populations, or browse the [Runtime library catalog](runtime-library-catalog.md) for every module and
function.
