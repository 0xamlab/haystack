---
icon: seedling
description: Five flat-scalar modules for crop and plant production math -- field agriculture, agronomic crop/soil science, horticultural plant physiology, hydroponic nutrient/climate control, and greenhouse structural engineering.
---

# Agricultural production kernels

Five modules covering the arithmetic behind growing something on purpose, at four different
scales: `agriculture` is the broadest layer (growing degree days, water need, fertilizer and seed
rates, yield); `agronomy` narrows to field crops and their soil (radiation-use-efficiency yield
potential, reference evapotranspiration, cation exchange capacity); `horticulture` goes to the
individual plant (photosynthesis light-response curves, net assimilation rate, transplant shock,
rooting-hormone dose-response); `hydroponics` covers soil-less nutrient-solution systems (EC/TDS
conversion, pH and reservoir dilution dosing, fertigation ROI); and `greenhouse` is the structure
around all of them (heat loss, ventilation, CO2 enrichment, supplemental lighting). Every function
across all five is a plain `Float64 -> Float64` formula — no structs, no state — matching the
numbers-in, numbers-out convention used across this corpus.

{% hint style="info" %}
**Two functions are byte-for-byte duplicated between `agriculture` and `agronomy`, with one subtle
guard difference.** `growing_degree_days` and `leaf_area_index` exist in both modules with
identical formulas — but `agriculture.leaf_area_index` only special-cases `ground_area == 0.0`,
while `agronomy.leaf_area_index` special-cases `ground_area <= 0.0`. A negative `ground_area`
passed to the `agriculture` version divides normally and returns a negative LAI; the `agronomy`
version catches it and returns `0.0`. See below for the verified numbers.
{% endhint %}

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("agriculture", "growing_degree_days", [30.0, 10.0, 10.0])["result"]
# 10.0 -- a 30C/10C day against a 10C base crop threshold accumulates exactly 10 GDD

runtime.execute("hydroponics", "ec_from_tds", [500.0, 0.5])["result"]
# 0.25 -- 500 ppm TDS at a 0.5 conversion factor is 0.25 mS/cm nutrient-solution EC
```

## The modules

| Module | What it does |
| --- | --- |
| `agriculture` | General field-crop arithmetic: growing degree days, crop water need (ETc = ET0·Kc), irrigation efficiency, fertilizer rate, seed rate, harvest index, yield per hectare, lime requirement, water-use efficiency, PAR, leaf area index, and nitrogen-use efficiency. |
| `agronomy` | Crop and soil science: radiation-use-efficiency yield potential, nitrogen uptake efficiency, first-order soil organic matter decay, a full FAO-56 Penman-Monteith reference evapotranspiration, leaf area index, light-use efficiency, crop water stress index, irrigation requirement, and cation exchange capacity from clay/organic-matter content. |
| `horticulture` | Individual-plant physiology: a rectangular-hyperbola photosynthesis light-response curve, crop growth rate (NAR × LAI), net assimilation rate from sequential harvests, specific leaf area, transplant shock index, fertigation injector dosing, leaf-to-air VPD, chilling-hour accumulation, pruning light-interception gain, and an auxin dose-response rooting index. |
| `hydroponics` | Soil-less nutrient/climate math: EC↔TDS conversion, nutrient concentration and pH-adjustment dosing, daily light integral, air VPD, water consumption, nutrient uptake rate, grow-light efficacy, reservoir dilution, yield per area, and crop-cycle ROI. |
| `greenhouse` | Structure and environment engineering: conductive heat loss, ventilation rate, solar heat gain, net heating requirement, CO2 enrichment rate, supplemental-lighting hours, irrigation volume, growing-area utilization, heating energy cost, yield per square metre, night-temperature setpoint (DIF), and shade factor. |

## Two identical functions, one better guard

`mojo/engine/agriculture.mojo` and `mojo/engine/agronomy.mojo` each independently implement
`growing_degree_days` and `leaf_area_index`. The GDD formulas are identical in every respect
(`max(0, (t_max + t_min)/2 - t_base)`), so calling either module gives the same answer for the
same inputs:

```python
runtime.execute("agriculture", "growing_degree_days", [28.0, 16.0, 10.0])["result"]
# 12.0
runtime.execute("agronomy", "growing_degree_days", [28.0, 16.0, 10.0])["result"]
# 12.0 -- same formula, same answer
```

`leaf_area_index` is the same story with one difference in the zero/negative guard:

```python
# agriculture.leaf_area_index only guards ground_area == 0.0
runtime.execute("agriculture", "leaf_area_index", [10.0, -5.0])["result"]
# -2.0 -- negative ground area divides through and returns a negative "LAI"

# agronomy.leaf_area_index guards ground_area <= 0.0
runtime.execute("agronomy", "leaf_area_index", [10.0, -5.0])["result"]
# 0.0 -- negative ground area is caught and floored to zero
```

A negative ground area is not a physically meaningful input either way, so this is a low-stakes
inconsistency rather than a wrong-answer bug on realistic data — but it means the two modules are
not perfectly interchangeable at the boundary, and a caller that validates inputs against one
module's guard clause cannot assume the other module validates the same way.

## `agronomy`'s reference evapotranspiration is the real FAO-56 equation

`evapotranspiration_penman(rn, temp, wind, vpd)` is not a toy simplification — it is the standard
FAO-56 Penman-Monteith reference-crop evapotranspiration equation, including the slope-of-saturation-
vapor-pressure-curve term (`Δ`) and a psychrometric constant fixed at `γ = 0.0665 kPa/°C`, which is
the textbook value at sea-level atmospheric pressure (~101.3 kPa). For a typical well-watered,
midsummer reference-grass day (15 MJ/m²/day net radiation, 25°C, 2 m/s wind, 1.0 kPa vapor pressure
deficit):

```python
runtime.execute("agronomy", "evapotranspiration_penman", [15.0, 25.0, 2.0, 1.0])["result"]
# 5.181095764245874 -- mm/day; FAO-56 reference ET0 for well-watered grass typically
# falls in the 4-6 mm/day range on a summer day with these conditions
```

A hotter, windier day (18 MJ/m²/day, 30°C, 3 m/s, 2.0 kPa VPD) pushes it to `7.87 mm/day`, still
inside the plausible high-demand range the FAO-56 method is designed to produce. Because `γ` is
hardcoded rather than derived from an elevation/pressure input, the formula is only exact at sea
level — at altitude, the real psychrometric constant is lower, and this function will slightly
overestimate ET0.

## Two VPD formulas answering different physical questions

`hydroponics.vpd(temperature, humidity)` and `horticulture.vpd_plant(leaf_temp, air_temp,
relative_humidity)` share a name fragment and a saturation-vapor-pressure core (the Magnus
equation), but they are not the same quantity:

* `hydroponics.vpd` takes **one** temperature and computes the deficit between the air's actual and
  saturated vapor pressure at that single temperature — the standard air VPD used to size a
  dehumidifier or judge a grow-tent's transpiration potential.
* `horticulture.vpd_plant` takes **two** temperatures — leaf and air — and computes
  `es(leaf_temp) - es(air_temp)·RH/100`, the leaf-to-air VPD used to judge stomatal closure and
  plant-level water stress, which can differ from air VPD whenever the leaf runs warmer or cooler
  than the surrounding air (a common daytime effect under high light).

The two also use slightly different empirical constants in the underlying Magnus formula
(`b = 237.3` in `hydroponics.vpd`, `b = 237.7` in `horticulture.vpd_plant`), so even at the same
single temperature they land close but not identical:

```python
runtime.execute("hydroponics", "vpd", [25.0, 60.0])["result"]
# 1.2671110870027391 -- kPa, air VPD at 25C/60%RH

runtime.execute("horticulture", "vpd_plant", [25.0, 25.0, 60.0])["result"]
# 1.263939296155738 -- kPa, leaf-to-air VPD with leaf temp == air temp;
# close to the air-VPD figure above but not exact, due to b=237.7 vs b=237.3

runtime.execute("horticulture", "vpd_plant", [22.0, 25.0, 60.0])["result"]
# 0.7420620495612658 -- a 3C-cooler leaf (transpirational cooling) cuts the
# leaf-to-air deficit by nearly half versus the equal-temperature case
```

## A cross-module inverse: supplemental lighting hours and daily light integral

`greenhouse.light_supplementation_hours(target_dli, natural_dli, ppfd)` and
`hydroponics.light_daily_integral(ppfd, hours)` are literal inverses of each other, computed in two
different modules from the same underlying DLI relationship (`DLI = PPFD · hours · 3600 / 1e6`).
Given a 10 mol/m²/day light deficit at 400 µmol/m²/s supplemental PPFD:

```python
hours = runtime.execute("greenhouse", "light_supplementation_hours", [20.0, 10.0, 400.0])["result"]
hours
# 6.944444444444445 -- hours of supplemental lighting needed to close the gap

runtime.execute("hydroponics", "light_daily_integral", [400.0, hours])["result"]
# 10.000000000000002 -- feeding that many hours back into the DLI formula
# recovers the original 10 mol/m^2/day deficit, confirming both formulas
# agree on the same PPFD-to-DLI relationship
```

## `chilling_requirement`'s all-or-nothing day model

`horticulture.chilling_requirement`'s docstring states `CH = hours × days / 24 if daily_mean <
threshold`, but there is no `hours` parameter anywhere in the function signature — its actual
inputs are `daily_temps` (a single mean daily temperature), `threshold_temp`, and `days`. The real
implementation is simpler than the docstring formula suggests: if the mean temperature is below
the chilling threshold, it assumes **all 24 hours** of **every** one of the `days` were below
threshold and returns `days * 24.0` outright; otherwise it returns `0.0`.

```python
runtime.execute("horticulture", "chilling_requirement", [5.0, 7.2, 90.0])["result"]
# 2160.0 -- 90 days x 24 h/day, since 5C is below the 7.2C threshold

runtime.execute("horticulture", "chilling_requirement", [10.0, 7.2, 90.0])["result"]
# 0.0 -- 10C is above threshold, so zero chill hours accumulate for the whole span
```

This is a single-representative-temperature model, not a real hourly or daily-varying
accumulation — a 90-day span with a 5°C mean gets full credit for every hour of every day, and a
90-day span with a 7.3°C mean (barely above threshold) gets none. Treat it as a coarse go/no-go
check rather than a precise chill-hour accumulator for a season with real day-to-day temperature
variation.

## Verification

`agriculture`, `hydroponics`, and `greenhouse` each have real, hand-verified pinned-value test
suites — not just smoke tests:

* `tests/mojo/test_wave71.mojo` exercises all 12 `agriculture` functions with worked expected
  values (e.g. `fertilizer_rate(10.0, 0.5, 2.0, 0.8) == 3.75`) — 25 of that file's 75 total
  assertions belong to `agriculture` (the rest cover `marine` and `brewing`, documented
  elsewhere).
* `tests/mojo/test_wave90.mojo` runs 24 pinned assertions against all 12 `hydroponics` functions
  (e.g. `reservoir_dilution(2.0, 1.0, 100.0) == 100.0`).
* `tests/mojo/test_wave94.mojo` runs 25 pinned assertions against all 12 `greenhouse` functions
  (e.g. `co2_enrichment_rate(1000.0, 400.0, 500.0, 0.5) == 0.8`, confirming the `+ leak_rate` term
  is intentional — a leaking greenhouse needs *more* injected CO2 than the bare concentration gap,
  not less).

`agronomy` and `horticulture` have **no such wave-file suite** — `mojo/tests/libs/test_agronomy.mojo`
and `test_horticulture.mojo` are the auto-generated kind that call every function once with the
fixed fixture `(0.5, 0.5, ...)` and check only that the result is finite (`not isnan(x) and not
isinf(x)`), pinning no actual output value and never exercising a guard clause or an edge case.
Every `agronomy` and `horticulture` number on this page (the Penman-Monteith ET examples, the
rooting-hormone index, the pruning-efficiency figures, the leaf-area-index guard comparison, the
chilling-requirement examples) was computed independently in Python from the formulas quoted
directly out of `mojo/engine/agronomy.mojo` and `mojo/engine/horticulture.mojo`, not copied from
any test file, and is reproducible by re-running the same arithmetic.

**Next:** see [Atmospheric chemistry, climate, and meteorology kernels](atmospheric-chemistry-and-climate-kernels.md)
for the sibling vapor-pressure and psychrometric formulas this family's evapotranspiration and VPD
functions build on, or browse the [Runtime library catalog](runtime-library-catalog.md) for every
module and function.
