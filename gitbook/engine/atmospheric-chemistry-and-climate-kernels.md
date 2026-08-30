---
icon: smog
description: Gas-phase photochemistry and pollutant-lifetime formulas, plus two independently-implemented single-point weather-index toolkits that compute instantaneous psychrometric conditions rather than long-term climate statistics.
---

# Atmospheric chemistry, climate, and meteorology kernels

Three modules for the atmosphere: one that tracks how a trace gas reacts and disappears
(photolysis, hydroxyl-radical oxidation, radiative forcing, acid deposition), and two that convert
a handful of raw surface observations — temperature, humidity, wind, pressure — into the derived
quantities a forecaster or a building-codes engineer actually uses (dew point, wet-bulb
temperature, heat index, wind chill, pressure altitude). All thirty-one functions across the three
modules take and return plain `Float64` scalars.

{% hint style="warning" %}
**`climate` is not long-term climate modeling.** Despite the name, `climate.mojo`'s own docstring
describes it as a drop-in replacement for `metpy`'s instantaneous-observation functions — heat
index, wind chill, dew point, wet bulb, vapor pressure — and every function in it takes a single
point-in-time reading and returns a single derived value. There is no time series, no trend, no
climatology, and no statistical model anywhere in the module. `meteorology.mojo` covers almost the
same ground (dew point, wet bulb, wind chill, heat index, pressure altitude) with independently
coded, differently-parameterized formulas. The two modules are best read as one overlapping
weather-physics toolkit implemented twice, not as "short-term forecasting" versus "long-term
climate" — see the module-by-module comparison further down this page.
{% endhint %}

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# CO2 at today's ~420 ppm against the 280 ppm pre-industrial reference
runtime.execute("atmospheric_chemistry", "greenhouse_forcing", [420.0, 280.0])["result"]
# 2.1692383283786794 -- IPCC's simplified formula (Myhre et al. 1998), 5.35*ln(C/C0);
# published estimates of CO2's own forcing since pre-industrial are ~2.1-2.2 W/m^2

runtime.execute("meteorology", "wind_chill", [-10.0, 20.0])["result"]
# -17.86058434436593 -- matches Environment Canada's published wind-chill chart at
# -10C, 20 km/h to within rounding
```

## The modules

| Module | What it does |
| --- | --- |
| `atmospheric_chemistry` | Ozone columns in Dobson units, photolysis rates, steady-state hydroxyl radical concentration, aerosol optical depth, mixing-ratio-to-concentration conversion, atmospheric residence time, a toy smog index, acid-rain pH, simplified CO2 radiative forcing, and OH-oxidation lifetime. |
| `climate` | A `metpy`-replacement toolkit of instantaneous weather-derived quantities: heat index and wind chill (US NWS formulas, °F), dew point and wet bulb (°C), saturation vapor pressure, relative humidity, Australian BOM apparent temperature, cloud base height, and ICAO pressure altitude. |
| `meteorology` | An independently-coded, metric-first sibling toolkit covering much of the same ground — dew point, wet bulb, relative and absolute humidity, wind chill (Environment Canada formula), heat index, potential temperature, precipitable water, and Beer-Lambert visibility extinction — plus a barometric-formula pressure altitude. |

## `atmospheric_chemistry`: photochemistry and pollutant lifetimes

| Function | What it does |
| --- | --- |
| `ozone_column_dobson(column_density_mol_m2)` | Converts a column density to Dobson units: `mol/m² * 6.022e23 / 2.687e20`. |
| `photolysis_rate(actinic_flux, cross_section, quantum_yield)` | `j = F·σ·Φ`, the photolysis rate coefficient. |
| `hydroxyl_steady_state(oh_production, loss_rate_constant, substrate_conc)` | `[OH]ss = P(OH) / (k·[X])`; `0.0` if the denominator is non-positive. |
| `aerosol_optical_depth(extinction_coefficient, path_length)` | `AOD = β·L`, a plain product. |
| `mixing_ratio_to_conc(mixing_ratio_ppm, temperature_k, pressure_pa)` | Ideal-gas conversion `n = χ·P / (k_B·T)`; `0.0` if `temperature_k <= 0`. |
| `residence_time(column_amount, source_rate)` | `τ = burden / source_rate`; `0.0` if `source_rate <= 0`. |
| `smog_formation_index(nox_ppb, voc_ppb)` | `NOx × VOC` — the source's own docstring calls this "an indicator, not mechanistic." |
| `acid_rain_ph(so2_deposition, nox_deposition)` | `5.6 - log10(1 + (SO2+NOx)/100)`; returns exactly `5.6` (natural, CO2-equilibrated rainwater) if deposition is non-positive. |
| `greenhouse_forcing(co2_ppm, co2_ref_ppm)` | `ΔF = 5.35·ln(C/C0)`, the IPCC/Myhre simplified CO2 forcing formula; `0.0` if either concentration is non-positive. |
| `lifetime_from_oh(rate_constant_oh, oh_concentration)` | `τ = 1/(k_OH·[OH])`; `0.0` if the loss rate is non-positive. |

Every number below was computed independently in Python against the formulas quoted directly from
`mojo/engine/atmospheric_chemistry.mojo`; none are invented.

**Ozone column.** A column density of `0.1 mol/m²` converts to `224.12` Dobson units —
right at the ~220 DU threshold the Antarctic ozone hole is conventionally defined by. A denser
column of `0.134 mol/m²` gives `300.32` DU, close to the historical global-mean total-column ozone
figure of ~300 DU:

```python
runtime.execute("atmospheric_chemistry", "ozone_column_dobson", [0.134])["result"]
# 300.31559359880913
```

**Steady-state OH from a CO sink.** Global-mean OH production of `1e6` molecules/cm³/s, against a
CO loss-rate constant of `2.4e-13` cm³/molecule/s and a CO concentration of `2.5e12` molecules/cm³
(roughly 100 ppb at sea level):

```python
runtime.execute("atmospheric_chemistry", "hydroxyl_steady_state", [1e6, 2.4e-13, 2.5e12])["result"]
# 1666666.6666666667 -- ~1.7e6 molecules/cm^3, the right order of magnitude for
# the accepted global tropospheric mean OH concentration (~1e6 cm^-3)
```

**CO2 as a real-world mixing ratio.** `mixing_ratio_to_conc` is a direct ideal-gas-law application,
independently checked against the Loschmidt-style number density of air: at 420 ppm CO2, 288.15 K
(15 °C), and 101,325 Pa (sea-level pressure), `mixing_ratio_to_conc(420, 288.15, 101325)` returns
`1.0697e22` molecules/m³. Dividing by the mixing ratio (`420e-6`) recovers a total air number
density of `2.546e25` molecules/m³ — matching the ideal-gas density at those conditions
(`P / (k_B·T)`) to full precision, confirming the formula is a straight, correctly-applied
`n = χP/(k_B T)`.

**Methane residence time, two ways.** `residence_time` and `lifetime_from_oh` compute the same
physical quantity — how long a gas survives in the atmosphere — from two different inputs, and
agree to within a plausible range for methane. A burden of 5000 Tg against emissions of 550 Tg/yr
gives:

```python
runtime.execute("atmospheric_chemistry", "residence_time", [5000.0, 550.0])["result"]
# 9.090909090909092 years -- close to the commonly cited ~9-11 year atmospheric
# methane lifetime

runtime.execute("atmospheric_chemistry", "lifetime_from_oh", [6.3e-15, 1e6])["result"]
# 158730158.73015872 seconds = 5.03 years, using the 298 K rate constant for
# CH4 + OH (6.3e-15 cm^3/molecule/s) and the same 1e6 cm^-3 global-mean [OH];
# the real global-mean lifetime is longer because most of the troposphere is
# colder than 298 K, which lowers the effective rate constant
```

The two independent formulas land within the same order of magnitude for the same real gas —
a reasonable internal-consistency check, not an exact match, since `lifetime_from_oh` only accounts
for OH oxidation while the real atmospheric methane budget also includes minor soil and
stratospheric sinks.

**Acid rain pH has a defined clean-rain floor.** With zero SO2/NOx deposition, `acid_rain_ph`
returns exactly `5.6` — the textbook pH of rainwater in equilibrium with atmospheric CO2 alone, with
no pollutant contribution. Realistic deposition (`so2=300`, `nox=100` mg/L-equivalents) pushes it
down to a plausible acid-rain value:

```python
runtime.execute("atmospheric_chemistry", "acid_rain_ph", [0.0, 0.0])["result"]
# 5.6 -- exact floor, hit whenever total deposition is non-positive
runtime.execute("atmospheric_chemistry", "acid_rain_ph", [300.0, 100.0])["result"]
# 4.901029995663981
```

**No guard against negative or zero inputs on the plain-product functions.** `ozone_column_dobson`,
`photolysis_rate`, `aerosol_optical_depth`, and `smog_formation_index` are direct multiplications
with no range check anywhere in the source — a negative `path_length` or `cross_section` produces a
negative "optical depth" or "photolysis rate" silently rather than refusing. The functions that
divide (`hydroxyl_steady_state`, `mixing_ratio_to_conc`, `residence_time`, `lifetime_from_oh`) all
guard their denominator against `<= 0.0` and return `0.0` instead of dividing.

## `climate` and `meteorology`: two implementations of the same handful of formulas

Both modules solve the same small set of problems — dew point from temperature and humidity,
wet-bulb temperature, wind chill, heat index, humidity conversions, pressure altitude — with
separately written formulas, different unit conventions (`climate` works in °F for heat index and
wind chill; `meteorology` works in °C throughout), and, in one case below, a different empirical
constant for the same named formula. Grepping the rest of `gitbook/` for `climate` or `meteorology`
by name turns up nothing but the auto-generated
[Runtime library catalog](runtime-library-catalog.md), so this is the first hand-written page for
either.

| `climate` function | `meteorology` function | Formula match? |
| --- | --- | --- |
| `dew_point(temp_c, humidity)` — Magnus, `b=237.3` | `dew_point(temperature, relative_humidity)` — Magnus, `b=237.7` | Same equation family, slightly different empirical constant |
| `wind_chill(temp_f, wind_mph)` — NWS formula, °F/mph | `wind_chill(temperature, wind_speed_kmh)` — Environment Canada formula, °C/km-h | Different national formulas, same physical quantity |
| `heat_index(temp_f, humidity)` — Rothfusz, °F | `heat_index(temperature, relative_humidity)` — Rothfusz, °C | Same regression re-expressed in different units (verified below) |
| `wet_bulb_approx(temp_c, humidity)` | `wet_bulb_temperature(temperature, relative_humidity)` | Both cite Stull (2011); **neither matches it** (see the hint below) |
| `pressure_altitude(station_pressure_hpa)` — ICAO formula | `pressure_altitude(pressure_pa)` — barometric formula | Same standard aviation relationship, slightly different rounding of the physical constants (verified below) |
| — | `absolute_humidity`, `potential_temperature`, `precipitable_water`, `visibility_extinction` | No `climate` equivalent |
| `saturation_vapor_pressure`, `relative_humidity`, `apparent_temperature`, `cloud_base_height`, `celsius_to_fahrenheit`, `fahrenheit_to_celsius` | — | No `meteorology` equivalent |

**The two heat-index variants agree exactly once unit-converted.** `climate.heat_index` runs the
Rothfusz regression in Fahrenheit; `meteorology.heat_index` runs an independently-coded set of
coefficients in Celsius. At the same physical condition (35 °C = 95 °F, 60% RH), they produce the
same answer to five decimal places:

```python
runtime.execute("climate", "heat_index", [95.0, 60.0])["result"]
# 113.09030830000012 F
runtime.execute("meteorology", "heat_index", [35.0, 60.0])["result"]
# 45.05017127776002 C

# (113.09030830000012 - 32) * 5/9 = 45.05017127777783 -- matches to 1e-8
```

**The two pressure-altitude formulas independently agree to under a meter.** `climate` implements
the ICAO pressure-altitude formula; `meteorology` implements the barometric-height formula. At
850 hPa / 85,000 Pa:

```python
runtime.execute("climate", "pressure_altitude", [850.0])["result"]
# 1456.6982111506986
runtime.execute("meteorology", "pressure_altitude", [85000.0])["result"]
# 1457.5140912855181
```

Both implement the same standard aviation pressure-altitude relationship
(`h = 44330 * (1 - (P/1013.25)^(1/5.255))`, published in some references with the equivalent
feet-based constant `145366.45 ft = 44307.694 m` that `climate` uses instead) — landing within a
meter of each other here is exactly what two independently-typed copies of the same formula, with
a hair of rounding difference in the published constants, should produce.

{% hint style="danger" %}
**Both "Stull (2011)" wet-bulb functions produce a physically impossible result, and one of them
can return `NaN` from a term that is nominally multiplied by zero.**

`climate.wet_bulb_approx`'s source has two trailing terms —
`+ t * (0.151977 - 1.0 + 1.0) - t * 0.151977` — that cancel to exactly zero by algebra
(`t*0.151977 - t*0.151977 = 0`), leaving a truncated formula that is not the arctangent-based
equation Stull (2011) actually published. The real Stull formula, computed independently for the
same inputs, stays below the dry-bulb temperature as physics requires; this module's version does
not:

```python
runtime.execute("climate", "wet_bulb_approx", [25.0, 60.0])["result"]
# 28.145131116395778 -- HIGHER than the 25 C dry-bulb input

# the real Stull (2011) equation for the same T=25 C, RH=60%:
# T*atan(0.151977*sqrt(RH+8.313659)) + atan(T+RH) - atan(RH-1.676331)
#   + 0.00391838*RH^1.5*atan(0.023101*RH) - 4.686035
# = 19.502679418339486 -- correctly below the dry-bulb temperature, and close
#   to published psychrometric-chart values for 25 C / 60% RH (~19.5-19.7 C)
```

Wet-bulb temperature can never exceed dry-bulb temperature (evaporative cooling only removes heat),
so `28.15 °C` for a `25 °C` reading is not a rounding error — it is the wrong formula.
`meteorology.wet_bulb_temperature` diverges even further (`34.54 °C` for the same inputs) and
additionally carries a term the source comments as `# placeholder simplification`:
`(temperature + rh) ** 0.5 * 0.0`. That term is intended as a no-op, but a fractional power of a
negative base is `NaN` under IEEE-754 (`pow`'s standard convention, confirmed here against the
platform math library), and `NaN * 0.0` is `NaN`, not `0.0` — so whenever `temperature +
relative_humidity < 0.0` (any cold, dry condition, e.g. `-20 °C` at `10%` RH), the "placeholder"
poisons the entire result:

```python
runtime.execute("meteorology", "wet_bulb_temperature", [-20.0, 10.0])["result"]
# NaN
```

Neither module's auto-generated smoke test catches this — both call sites use the fixed fixture
`(0.5, 0.5)`, where `temperature + relative_humidity = 1.0`, safely positive. If wet-bulb
temperature is load-bearing for a downstream calculation, treat both functions' output as
unverified and prefer computing the real Stull (2011) formula directly.
{% endhint %}

**`meteorology.dew_point` guards a zero-humidity input that `climate.dew_point` does not.**
`meteorology.dew_point(temperature, relative_humidity)` explicitly returns `temperature - 50.0` if
`relative_humidity <= 0.0`. `climate.dew_point` has no equivalent guard: `humidity = 0` sends
`log(humidity / 100.0)` to `log(0)`, and the resulting `-inf` propagates through
`b * gamma / (a - gamma)` as an indeterminate `-inf / inf`, returning `NaN`:

```python
runtime.execute("climate", "dew_point", [25.0, 0.0])["result"]
# NaN -- no guard against humidity <= 0
runtime.execute("meteorology", "dew_point", [25.0, 0.0])["result"]
# -25.0 -- guarded sentinel (temperature - 50.0)
```

**`climate.wind_chill` and `climate.heat_index` both refuse to extrapolate outside the range their
regression was fit on**, unlike the wet-bulb and dew-point functions above. `wind_chill` returns the
raw temperature unchanged whenever `temp_f > 50.0` or `wind_mph < 3.0` — the NWS formula's own
validity bounds — rather than running the polynomial outside the conditions it was fit under, and
`heat_index` falls back to a simpler linear estimate whenever the full Rothfusz regression would
produce a value under 80 °F, the threshold the regression itself assumes.

## Verification

`mojo/tests/libs/test_atmospheric_chemistry.mojo`, `test_climate.mojo`, and `test_meteorology.mojo`
are auto-generated coverage smoke tests: each calls every function once with the literal
argument(s) `0.5` and checks only that the result is finite (`not isnan(x) and not isinf(x)`) — none
pin a specific numeric output, and none exercise a value large enough or small enough to trip any of
the guard clauses or edge cases documented above. Every worked example on this page was computed
independently in Python from the formulas quoted directly out of `mojo/engine/atmospheric_chemistry.mojo`,
`climate.mojo`, and `meteorology.mojo`, cross-checked against published reference values (IPCC CO2
forcing, NWS/Environment Canada wind-chill charts, standard-atmosphere pressure-altitude tables, and
the real Stull 2011 wet-bulb equation) where a public reference exists, and is reproducible by
re-running the same arithmetic.

**Next:** see [Geospatial indexing & joins](geospatial.md) for the coordinate-frame and distance
primitives this family's column and path-length quantities would combine with, or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
