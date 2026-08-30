---
icon: seedling
description: Per-hive, per-tank, per-stock, per-hectare, and per-trap arithmetic for six specialty production sciences -- beekeeping, aquatic farming, wild-fisheries stock assessment, wine-grape growing and cellar chemistry, forest stand management, and integrated pest management.
---

# Specialty agriculture and aquaculture kernels

Six modules for production sciences that sit outside row-crop agriculture, each with its own
literature and its own unit conventions: managing a honeybee colony (`apiculture`), raising fish or
shrimp in a controlled tank (`aquaculture`), managing a wild fish stock nobody controls the inputs
to (`fisheries`), growing wine grapes and then turning them into wine (`viticulture`), managing a
forest stand over decades (`silviculture`), and deciding when a pest population justifies the cost
of controlling it (`pest_control`). None of the six import each other, and none share a status-code
range -- every function takes and returns plain `Float64` scalars, the same flat-arithmetic
convention used throughout this corpus. What ties them together is the shape of the problem: a
population or stock changes over time under growth, mortality, and harvest, and the arithmetic here
is the per-unit accounting that turns raw counts and measurements into rates, densities, and
economic thresholds.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# 200 kg of honey off 10 hives
runtime.execute("apiculture", "honey_yield_per_hive", [200.0, 10.0])["result"]
# 20.0 kg/hive

# Schaefer surplus production: r=0.5, biomass=5000, carrying capacity K=10000
runtime.execute("fisheries", "schaefer_surplus_production", [0.5, 5000.0, 10000.0])["result"]
# 1250.0 -- the stock is at half its carrying capacity, where logistic growth peaks
```

## The modules

| Module | What it does |
| --- | --- |
| `apiculture` | Beekeeping and colony management: honey yield per hive, colony population estimate, varroa mite infestation rate, sugar-syrup feeding ratio, foraging range area, nectar-to-honey concentration, brood viability, winter feed requirement, queen laying rate, pollination value to a crop, hive density per hectare, and overwintering survival. |
| `aquaculture` | Controlled fish/shrimp farming: stocking density, feed conversion ratio, specific growth rate, dissolved-oxygen consumption and carrying capacity, water exchange rate, ammonia production, projected harvest weight, survival rate, production per cycle, biofilter capacity, and cost per kilogram produced. |
| `fisheries` | Wild-stock assessment: catch per unit effort, maximum sustainable yield and biomass at MSY (Schaefer model), the surplus-production curve itself, fishing/natural/total mortality and exploitation rate, annual survival from mortality, von Bertalanffy growth, Fulton's condition factor, gonadosomatic index, and Beverton-Holt stock-recruitment. |
| `viticulture` | Wine-grape growing *and* cellar chemistry: Brix-to-potential-alcohol, chaptalization sugar addition, total acidity, pH buffer capacity, growing-degree-days and the Winkler index, yield per hectare, vine density, the Ravaz pruning-weight index, must volume from crushed grapes, molecular SO2 from free SO2 and pH, and fermentation progress. |
| `silviculture` | Forest stand management and timber mensuration: basal area (tree and stand level), site index, Scribner log-rule volume, standing timber yield per hectare, two competing stand-density indices (Curtis RDI and Reineke SDI), mean and current annual increment, and the thinning ratio for a residual-density target. |
| `pest_control` | Integrated pest management economics: economic threshold and economic injury level, pest density from a sample, trap catch rate, spray coverage, dilution rate, residual effectiveness decay, insecticide resistance ratio, biocontrol agent release rate, fumigation CT product, bait station density, and population reduction percentage. |

## `apiculture`: colony inputs and outputs, worked

| Function | What it does |
| --- | --- |
| `honey_yield_per_hive(total_honey_kg, n_hives)` | `total_honey_kg / n_hives`. |
| `colony_strength_estimate(frames_of_bees, bees_per_frame)` | `frames * bees_per_frame` -- a population estimate from a frame count. |
| `varroa_infestation_rate(mites_counted, bees_sampled)` | `mites / bees * 100`, a percentage. |
| `sugar_syrup_ratio(sugar_kg, water_kg)` | `sugar / (sugar + water)`, a fraction 0-1. |
| `foraging_range_area(radius_km)` | `pi * r^2` -- the area a colony forages within a given flight radius. |
| `nectar_to_honey_ratio(nectar_kg)` | `nectar / 4.0` -- the typical 4:1 evaporation ratio from raw nectar to cured honey. |
| `brood_viability(hatched_cells, total_cells)` | `hatched / total * 100`. |
| `winter_feed_requirement(colony_weight_kg, months, consumption_per_month)` | `months * consumption - (colony_weight - 15.0)`. |
| `queen_laying_rate(eggs_per_day)` | Identity -- returns the input unchanged (up to ~2000 eggs/day is the docstring's stated realistic ceiling, not an enforced bound). |
| `pollination_value(crop_yield_increase_pct, crop_value)` | `crop_value * increase_pct / 100` -- the dollar value a colony's pollination adds to a crop. |
| `hive_density_per_hectare(n_hives, area_ha)` | `n_hives / area_ha`. |
| `overwintering_survival_rate(survived, total)` | `survived / total * 100`. |

`winter_feed_requirement`'s subtraction is the whole model: a colony heavier than the 15 kg baseline
already has honey stores that offset part of what it needs fed, and a colony lighter than baseline
needs *more* than the raw `months * consumption` figure. Hand-verified in
`tests/mojo/test_wave93.mojo` (19 assertions): a colony at
25 kg needing 5 months at 3 kg/month consumption gets `5*3 - (25-15) = 15 - 10 = 5` kg of
supplemental feed, and the same test confirms `foraging_range_area(3.0)` is `pi * 9 = 28.274333882`
km^2 and `varroa_infestation_rate(15.0, 300.0) = 5.0` percent -- a count above the commonly cited
1-3% pre-treatment action threshold in real beekeeping practice, though the function itself has no
opinion on thresholds, it only computes the rate.

## `aquaculture`: a stocking-to-harvest chain

| Function | What it does |
| --- | --- |
| `stocking_density(biomass_kg, volume_m3)` | `biomass / volume` (kg/m^3). |
| `feed_conversion_ratio(feed_kg, weight_gain_kg)` | `feed / weight_gain` -- lower is more efficient. |
| `specific_growth_rate(w_final, w_initial, days)` | `(ln(Wf) - ln(Wi)) / days * 100` (%/day). |
| `dissolved_oxygen_consumption(biomass_kg, rate_per_kg)` | `biomass * rate` (mg O2/hr). |
| `water_exchange_rate(flow_rate, tank_volume)` | `flow / volume * 100` (%/hr). |
| `ammonia_production(feed_rate, protein_pct)` | `feed * protein/100 * 0.03` -- an estimate, not a stoichiometric derivation. |
| `carrying_capacity(do_available, do_per_kg)` | `do_available / do_per_kg` -- the maximum biomass the available oxygen supply can support. |
| `harvest_weight(initial_weight, sgr, days)` | `initial_weight * exp(sgr * days / 100)` -- the exponential-growth counterpart to `specific_growth_rate`. |
| `survival_rate(final_count, initial_count)` | `final / initial * 100`. |
| `production_per_cycle(harvest_weight_avg, count, survival)` | `harvest_weight_avg * count * survival / 100` (kg). |
| `biofilter_capacity(surface_area, nitrification_rate)` | `surface_area * nitrification_rate` (g TAN/day). |
| `cost_per_kg_produced(total_cost, production_kg)` | `total_cost / production_kg`. |

`specific_growth_rate` and `harvest_weight` are exact inverses of each other by construction: growth
over 30 days from 10 g to 50 g gives `sgr = (ln(50) - ln(10)) / 30 * 100 = 5.364793...` %/day
(hand-checked in `tests/mojo/test_wave97.mojo`), and feeding that same full-precision `sgr` back into
`harvest_weight(10.0, sgr, 30.0)` reproduces `50.0` to floating-point precision -- the two functions
round-trip because `harvest_weight` is just
`specific_growth_rate`'s formula solved for `w_final`. The same test file chains a realistic cycle:
`dissolved_oxygen_consumption(200.0, 300.0) = 60000` mg/hr feeds directly into
`carrying_capacity(60000.0, 300.0) = 200` kg -- the biomass level at which that oxygen supply is
exactly saturated.

## `fisheries`: the Schaefer surplus-production model, end to end

| Function | What it does |
| --- | --- |
| `catch_per_unit_effort(total_catch, total_effort)` | `C / E`; `0.0` if `total_effort <= 0`. |
| `maximum_sustainable_yield(r, k)` | `r * K / 4` -- the Schaefer-model peak of the logistic yield curve. |
| `biomass_at_msy(k)` | `K / 2` -- the stock level at which that peak occurs. |
| `schaefer_surplus_production(r, biomass, k)` | `r * B * (1 - B/K)`; `0.0` if `k <= 0`. |
| `fishing_mortality(catch, biomass)` | `C / B`; `0.0` if `biomass <= 0`. |
| `total_mortality(fishing_mort, natural_mort)` | `F + M`. |
| `exploitation_rate(fishing_mort, total_mort)` | `F / Z`; `0.0` if `total_mort <= 0`. |
| `survival_rate(total_mort)` | `exp(-Z)` -- annual survival from total instantaneous mortality. |
| `von_bertalanffy_length(l_inf, k, t, t0)` | `Linf * (1 - exp(-k*(t - t0)))`. |
| `condition_factor(weight_g, length_cm)` | Fulton's `K = 100 * W / L^3`; `0.0` if `length_cm <= 0`. |
| `gonadosomatic_index(gonad_weight, body_weight)` | `gonad_weight / body_weight * 100`; `0.0` if `body_weight <= 0`. |
| `stock_recruitment_bevholt(alpha, beta, spawners)` | Beverton-Holt: `alpha * S / (beta + S)`; `0.0` if `\|beta + S\| < 1e-15`. |

`tests/mojo/test_wave83.mojo` hand-verifies the whole model as one chain (24
assertions): at `r=0.5, K=10000`, `maximum_sustainable_yield` is `1250` and `biomass_at_msy` is
`5000` -- and plugging that same biomass back into `schaefer_surplus_production(0.5, 5000.0,
10000.0)` reproduces `1250.0` exactly, confirming MSY really is the surplus-production curve's peak
value at its own peak biomass, not just a separately-defined constant. Mortality decomposes the same
way: `total_mortality(0.2, 0.3) = 0.5`, `exploitation_rate(0.2, 0.5) = 0.4` (40% of total mortality is
fishing, not natural causes), and `survival_rate(0.5) = exp(-0.5) = 0.6065`.

{% hint style="warning" %}
**`fisheries.survival_rate` and `aquaculture.survival_rate` share a name and nothing else.**
`fisheries.survival_rate(total_mort)` takes one argument -- an instantaneous mortality rate -- and
returns `exp(-Z)`, the fraction of a wild population surviving one year of combined fishing and
natural mortality. `aquaculture.survival_rate(final_count, initial_count)` takes two arguments and
returns a simple `final / initial * 100` batch-survival percentage for a stocked tank or pond. The
two modules never import each other and the contract lists them as entirely separate entries, but a
caller who has memorized one signature and reaches for `survival_rate` in the other module's context
will get an argument-count error at best, or -- if they happen to pass a mortality rate where a count
was expected -- a silently wrong percentage.
{% endhint %}

## `viticulture`: the module covers the vineyard *and* the cellar

The docstring calls this "Viticulture (Grape Growing & Wine)," and the function list backs that up
literally: `growing_degree_days_wine`, `winkler_index_daily`, `vine_density`, and `yield_tonnes_per_hectare`
are field/vineyard measurements, but `brix_to_potential_alcohol`, `chaptalization_sugar`,
`sulfite_molecular_so2`, and `fermentation_progress` are winemaking-cellar chemistry that happens
after the grapes are already picked and crushed. A page titled just "viticulture" (the growing of
grapes) would undersell half of what this module actually computes -- it is viticulture and
enology bundled into one file.

| Function | What it does |
| --- | --- |
| `brix_to_potential_alcohol(brix)` | `brix * 0.55` -- a common rule-of-thumb ABV estimate from must sugar content. |
| `chaptalization_sugar(target_brix, current_brix, volume_l)` | `(target - current) * volume * 1.7` -- grams of sugar needed to raise must to a target Brix. |
| `total_acidity_as_tartaric(ta_g_per_l)` | Identity -- returns the input unchanged; the function exists to name the unit convention (tartaric-acid equivalent), not to convert one. |
| `ph_buffer_capacity(ta, ph)` | `ta * 0.3 / (ph - 2.5)` -- simplified buffering estimate. |
| `growing_degree_days_wine(t_max, t_min, t_base)` | `max(0, (Tmax + Tmin)/2 - Tbase)`. |
| `winkler_index_daily(gdd)` | Identity -- returns the daily GDD contribution unchanged; the caller sums it April-October to get the seasonal Winkler index. |
| `yield_tonnes_per_hectare(kg_total, area_ha)` | `kg_total / (1000 * area_ha)`. |
| `vine_density(vines_per_row, rows, area_ha)` | `vines_per_row * rows / area_ha`. |
| `pruning_weight_ratio(crop_weight, pruning_weight)` | The Ravaz index: `crop_weight / pruning_weight`. |
| `must_volume_from_grapes(grape_kg, extraction_rate)` | `grape_kg * extraction_rate` (typical rate 0.7-0.8). |
| `sulfite_molecular_so2(free_so2, ph)` | `free_so2 / (1 + 10^(pH - 1.81))`. |
| `fermentation_progress(initial_brix, current_brix)` | `(initial - current) / initial * 100`. |

`tests/mojo/test_wave95.mojo` hand-verifies both halves. Field side: `brix_to_potential_alcohol(24.0)
= 13.2` %ABV, and `growing_degree_days_wine(8.0, 4.0, 10.0) = 0.0` -- a day whose average temperature
sits below the 10C base contributes nothing, the `max(0, ...)` guard rather than a negative GDD.
Cellar side: `sulfite_molecular_so2(30.0, 1.81) = 15.0` -- at exactly pH 1.81 the `10^(pH-1.81)` term
is `10^0 = 1`, so the formula halves the free SO2 exactly, and the same test confirms
`fermentation_progress(24.0, 0.0) = 100.0` (fully fermented, all sugar consumed) against
`fermentation_progress(24.0, 24.0) = 0.0` (fermentation hasn't started).

## `silviculture`: forest mensuration and stocking control, not just tending prescriptions

The module's own docstring frames it as "Forest management and timber production calculations,"
which is broader than the narrow textbook definition of silviculture (the practice of establishing,
tending, and harvesting a stand). What's actually here is mostly forest *mensuration* and
growth-and-yield accounting -- basal area, log-volume scaling, stand density indices -- that feeds
the silvicultural decisions (like `thinning_ratio`) rather than being those decisions itself.

| Function | What it does |
| --- | --- |
| `basal_area(dbh_cm)` | `pi * (DBH/2)^2` -- per-tree basal area in **cm^2**, not m^2; `0.0` if `dbh_cm <= 0`. |
| `stand_basal_area(mean_dbh_cm, stems_per_ha)` | `pi * (DBH/200)^2 * stems_per_ha` -- stand-level basal area in **m^2/ha** (the `/200` both converts cm to m and halves for radius). |
| `site_index(height_m, age_years, base_age)` | `height * (base_age / age)^0.5` -- a simplified power-law site index. |
| `volume_scribner(small_end_diameter_in, log_length_ft)` | `(0.79*D^2 - 2*D - 4) * L / 16` -- the Scribner Decimal C log rule approximation, in board feet. |
| `timber_yield_per_ha(stems_per_ha, mean_vol_m3_per_tree)` | `stems * mean_vol` (m^3/ha). |
| `relative_density_index(stems_per_ha, mean_dbh_cm)` | Curtis-style RDI: `N / (25.4/DBH)^1.6`, algebraically `N * (DBH/25.4)^1.6`. |
| `reineke_sdi(stems_per_ha, mean_dbh_cm)` | Reineke SDI: `N * (25.4/DBH)^1.605`. |
| `mean_annual_increment(total_volume_m3, age_years)` | `total_volume / age`; `0.0` if `age_years <= 0`. |
| `current_annual_increment(vol_now, vol_past, years)` | `(vol_now - vol_past) / years`; `0.0` if `years <= 0`. |
| `thinning_ratio(initial_stems, target_stems)` | `(initial - target) / initial`, floored at `0.0` if the target is above the initial density. |

`basal_area` returns **cm^2** per tree while `stand_basal_area` returns **m^2/ha** -- both correct
per their own docstrings, but a caller multiplying `basal_area`'s tree-level output by a stem count
to approximate stand basal area would be off by a factor of 10,000 (cm^2 to m^2) unless they convert
first. Worked examples, hand-computed against `mojo/engine/silviculture.mojo` and independently
checked in Python (no hand-verified wave test exists for this module -- see Verification below):
`basal_area(30.0)` is `706.858` cm^2 per tree; `stand_basal_area(30.0, 400.0)` is `28.274` m^2/ha, a
realistic figure for a moderately stocked stand; `volume_scribner(16.0, 16.0)` (a 16-inch, 16-foot
log) is `166.24` board feet; and `thinning_ratio(1200.0, 700.0)` is `0.41667` -- 41.7% of stems must
be removed to bring 1,200 stems/ha down to a 700 stems/ha target.

{% hint style="danger" %}
**`reineke_sdi` inverts the ratio its own docstring names, and fails the invariance property SDI
exists to have.** Reineke's Stand Density Index is defined so that it stays *constant* along a
stand's self-thinning trajectory -- as trees grow and self-thin, `N` falls and mean DBH rises
together such that `N * DBH^1.605` is conserved, and SDI is that conserved quantity rescaled to a
25.4 cm reference diameter: `SDI = N * (DBH / 25.4)^1.605`. `reineke_sdi`'s code computes
`stems_per_ha * pow(25.4 / mean_dbh_cm, 1.605)` -- the reciprocal ratio inside the same exponent.
Verified independently in Python: take a stand at `N=1000/ha, DBH=15cm` and its self-thinned
descendant at `DBH=30cm` (which the self-thinning relation puts at `N=328.7/ha`). The textbook
formula gives `429.4` for both points, exactly as designed. The as-coded formula gives `2328.8` for
the first point and `251.7` for the second -- nearly a 10x spread between two states of the *same*
stand that should report an identical density index. The sibling function `relative_density_index`
in the same file gets the direction right: it *divides* by `(25.4/DBH)^1.6`, which is algebraically
`N * (DBH/25.4)^1.6`, the correct-direction scaling -- so this isn't a case of the whole module using
one convention, `reineke_sdi` specifically has the exponent's base inverted relative to both the
literature and its own sibling function.
{% endhint %}

## `pest_control`: the economics of when to spray

| Function | What it does |
| --- | --- |
| `economic_threshold(control_cost, crop_value, damage_per_pest)` | `cost / (value * damage_per_pest)` -- the pest density that justifies control. |
| `economic_injury_level(et, gain_threshold)` | `et * gain_threshold`. |
| `pest_density(count, sample_area)` | `count / area`. |
| `trap_catch_rate(caught, traps, days)` | `caught / (traps * days)`. |
| `spray_coverage(volume_applied, area)` | `volume / area` (L/ha). |
| `dilution_rate(concentrate_ml, water_ml)` | `concentrate / (concentrate + water)`. |
| `residual_effectiveness(initial_kill_pct, half_life_days, days_elapsed)` | `initial * exp(-0.693 * days / half_life)` -- `0.693 ~ ln(2)`, an exponential decay to the stated half-life. |
| `resistance_ratio(ld50_resistant, ld50_susceptible)` | `LD50_R / LD50_S`; `>1` indicates resistance. |
| `biocontrol_release_rate(target_density, predator_prey_ratio, area)` | `target_density * area / predator_prey_ratio`. |
| `fumigation_ct(concentration, time_hours)` | `C * T` (g·h/m^3), the fumigation exposure-dose product. |
| `bait_station_density(stations, area_m2)` | `stations / area_m2 * 10000` -- per-hectare density from an area given in m^2. |
| `population_reduction(before, after)` | `(before - after) / before * 100`. |

`tests/mojo/test_wave98.mojo` hand-verifies the whole chain (its assertions run alongside
`geomorphology` and `watchmaking` in the same wave file). `economic_threshold(50.0, 5000.0, 0.01) =
1.0`: at $50 control cost, $5,000 crop value per unit area, and 1% damage per pest, the breakeven
pest density is exactly 1 per unit area. `residual_effectiveness` is verified at three points on its
decay curve: `days_elapsed=0` returns the initial kill percentage unchanged (`residual_effectiveness(90.0,
10.0, 0.0) = 90.0`), and one full half-life halves it almost exactly
(`residual_effectiveness(100.0, 10.0, 10.0) = 100 * exp(-0.693) = 50.0074`, not the exact `50.000` a
true half-life implies) -- `0.693` is a three-decimal approximation of `ln(2) = 0.693147...`, so the
"half-life" is off by about 0.015%, a small, deliberate rounding built into the constant rather than
a bug, since the test file itself (`test_wave98.mojo`) asserts against `100.0 * exp(-0.693)`, the
same approximate constant, not against a recomputed `ln(2)`).
`population_reduction(200.0, 0.0) = 100.0` confirms complete elimination reads as a clean 100%, not
a divide-by-zero on the "after" side (there is no guard needed since `after` never appears in the
denominator).

## Verification

Five of the six modules have real, hand-verified numeric test suites living in `tests/mojo/`
alongside their auto-generated smoke tests: `apiculture` in `test_wave93.mojo` (19 assertions,
shared with `welding` and `color_science`), `aquaculture` in `test_wave97.mojo` (shared with
`adhesives` and `traffic_signal`), `fisheries` in `test_wave83.mojo` (24 assertions, shared with
`museum_science`), `viticulture` in `test_wave95.mojo` (shared with `semiconductors` and
`hydraulics`), and `pest_control` in `test_wave98.mojo` (shared with `geomorphology` and
`watchmaking`) -- each asserts specific literal expected values with a relative-tolerance helper,
not just a finite-value check. `silviculture` has no such wave test anywhere in the corpus (a
targeted grep across every `.mojo` file under this worktree turns up only its own
`mojo/tests/libs/test_silviculture.mojo`, which -- like all six of these modules' `test_libs`
files -- is the auto-generated smoke suite that calls every function once with literal `0.5`
arguments and checks only that the result is finite). The `silviculture` worked examples and the
`reineke_sdi` finding above were hand-computed from the real formulas in
`mojo/engine/silviculture.mojo` and independently checked with standalone Python arithmetic rather
than against any pinned test in this codebase.

**Next:** see [Hydrology & water systems kernels](hydrology-and-water-systems-kernels.md) for the
water-quality and flow arithmetic `aquaculture`'s tank calculations sit beside, or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
