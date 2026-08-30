---
icon: droplet
description: Surface hydraulics, groundwater flow, lake physics and chemistry, ocean dynamics, storm-water meteorology and the vegetation-water interface across seven independent kernel modules.
---

# Hydrology & water systems kernels

Water moves through a landscape at several distinct scales, and this family has one module per
scale rather than one unified model: rainfall becomes channel flow and storm runoff (`hydrology`),
some of it infiltrates and moves through soil and aquifers (`hydrogeology`), some collects in lakes
with their own physics and chemistry (`limnology`, `limnochemistry`), the ocean has its own
circulation and stratification (`oceanography`), the atmosphere supplies and removes water at the
land surface (`hydrometeorology`), and vegetation intercepts, transpires and is stressed by all of
it (`ecohydrology`). Every function is pure Mojo taking and returning `Float64` — no shared struct,
no Python, and (with one accidental exception noted below) no state carried between calls.

Three formulas appear twice across this family under different names or different unit
conventions, and one function name — `specific_yield` — appears twice with genuinely different
definitions. None of that is a copy-paste error; it reflects that the same physical quantity gets
computed differently in surface-water practice than in groundwater practice. The first worked
example below is a direct cross-check of one of those pairs:

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("hydrology", "curve_number_runoff", [3.0, 80.0])["result"]
# 1.25 — SCS Curve Number direct runoff for 3 inches of rain onto CN 80,
#        imperial formula: S = 1000/CN - 10 (inches)

runtime.execute("hydrometeorology", "runoff_curve_number", [76.2, 80.0])["result"]
# 31.75 — the same storm (3 in = 76.2 mm exactly) and the same CN, metric formula:
#         S = 25400/CN - 254 (mm)
# 1.25 in * 25.4 = 31.75 mm exactly — two independently-written functions, same
# SCS method, agreeing to the last digit once the units are reconciled.
```

## The modules

| Module | What it does |
| --- | --- |
| `hydrology` | Open-channel hydraulics (Manning's equation, hydraulic radius, Froude and Reynolds numbers, Darcy-Weisbach head loss) and storm design (rational method, Kirpich time of concentration in imperial units, SCS curve-number runoff in inches, Hargreaves evapotranspiration), plus an imperial `specific_yield` and a bare Darcy groundwater-velocity function. |
| `hydrogeology` | Aquifer flow and storage: Darcy flux, transmissivity, storativity, Theis and Dupuit discharge, hydraulic gradient, a porosity-based `specific_yield`, capillary rise height, a leaky-aquifer leakance factor, and a binary end-member tracer-mixing age model. |
| `limnology` | Lake physics: ellipsoidal basin volume, hydraulic retention and flushing time, a temperature-gradient stratification index, Secchi-depth-based trophic state (Carlson 1977), dissolved-oxygen saturation (Benson & Krause 1984), light attenuation from Secchi depth, and a simplified cyanobacterial nitrogen-fixation rate. |
| `limnochemistry` | Freshwater ionic chemistry: carbonate alkalinity, ionic strength, the Davies activity-coefficient equation (plus its `pow_10` helper), a calcite saturation index, river silica export flux, Eh-to-pe conversion, phosphorus and nitrogen fractionation, DOC light attenuation, and a thermocline-depth estimate. |
| `oceanography` | Ocean-scale physics: a linearized seawater equation of state, Brunt-Väisälä buoyancy frequency, differential tidal acceleration, geostrophic velocity, Ekman layer depth, mixed-layer heat flux, salinity from chlorinity, shallow- and deep-water wave celerity, and net surface freshwater flux. |
| `hydrometeorology` | The precipitation side of the water balance: SCS-CN runoff and Kirpich time of concentration in metric units, rational-method peak flow with an explicit unit-conversion constant, Green-Ampt infiltration, a Palmer-Drought-Index water-balance term, Budyko-type actual ET, snow water equivalent, rainfall intensity, an SCS antecedent-moisture-condition classifier, and a Gumbel flood-frequency factor. |
| `ecohydrology` | Vegetation-water coupling: Rutter/Gash canopy interception, Priestley-Taylor transpiration, soil-moisture-limited root water uptake and GPP water-stress, streamflow baseflow index, wetland and riparian-buffer residence time and nitrate removal, floodplain productivity from a flood pulse, groundwater-supported ET below a shallow water table, and the annual catchment runoff ratio. |

## The same physics, computed twice

- **`specific_yield` is two unrelated formulas.** `hydrology.specific_yield(volume_drained,
  total_volume)` is the field/lab definition, `Sy = Vd / Vt` — the fraction of saturated volume a
  sample actually releases under gravity drainage. `hydrogeology.specific_yield(porosity,
  residual_moisture)` is the textbook approximation, `Sy ≈ n - θr`, floored at `0.0`. Both describe
  the same aquifer property; neither function accepts the other's arguments.
- **`rational_method_peak_flow` assumes two different unit systems.** `hydrology`'s version is
  `Q = C·i·A` with no conversion constant — the US-customary convention where `i` is in in/hr, `A`
  is in acres, and the true ~1.008 acre·in/hr → cfs factor is conventionally dropped as
  near-enough-to-1. `hydrometeorology`'s version is `Q = C·i·A / 360`, the metric rational formula
  that turns `i` in mm/h and `A` in hectares into `Q` in m³/s. Feeding hectares and mm/h into
  `hydrology.rational_method_peak_flow` returns a number 360× too large with no error.
- **The Kirpich time-of-concentration coefficient depends on the length unit.** `hydrology.
  time_of_concentration_kirpich` uses `tc = 0.0078 · L^0.77 · S^-0.385` (`L` in feet);
  `hydrometeorology.time_of_concentration` uses `tc = 0.0195 · L^0.77 · S^-0.385` (`L` in meters).
  These are the standard imperial/metric Kirpich coefficient pair, not independent guesses — for
  `L = 1000 ft` (304.8 m) and `S = 0.01`, both return ≈9.4 minutes — but nothing in either
  signature enforces which unit a caller passed.
- **`curve_number_runoff` and `runoff_curve_number` are the same SCS method**, named the other way
  around across the two modules, one keyed to inches and one to millimeters — see the opening
  example above.

## Worked numeric examples

None of the seven test files pin numeric assertions (see [Verification](#verification)), so every
number below was hand-traced from the real formula in `mojo/engine/<module>.mojo` and independently
recomputed in Python before being presented here.

**Surface hydraulics.** Manning's equation for a wide channel, `n = 0.03` (natural earth channel),
hydraulic radius 0.5 m, bed slope 0.001, cross-sectional area 2.0 m²:

```python
runtime.execute("hydrology", "manning_velocity", [0.03, 1.0, 0.0004])["result"]
# 0.6666666666666667 m/s

runtime.execute("hydrology", "manning_discharge", [0.03, 2.0, 0.5, 0.001])["result"]
# 1.3280733965528158 m^3/s
```

**Groundwater.** Capillary rise of water (surface tension 0.0728 N/m at 20 °C, contact angle 0,
density 1000 kg/m³) up a 0.1 mm-radius pore — the classic capillary-tube textbook problem:

```python
runtime.execute("hydrogeology", "capillary_rise_height", [0.0728, 0.0, 1000.0, 1e-4])["result"]
# 0.14841997961264017 m — about 14.8 cm, matching the standard worked example
# for a 0.1 mm tube
```

And Dupuit discharge through an unconfined aquifer, `K = 0.001 m/s`, upstream/downstream heads
10 m and 8 m over a 500 m flow path:

```python
runtime.execute("hydrogeology", "dupuit_discharge", [0.001, 10.0, 8.0, 500.0])["result"]
# 3.6e-05 m^2/s (per unit width)
```

**Lakes.** `trophic_state_index` is Carlson's original 1977 calibration, built so that each
doubling of Secchi depth subtracts exactly 10 index points — the three reference depths reproduce
the textbook TSI values to two decimal places:

```python
for sd in (1.0, 2.0, 4.0, 8.0):
    runtime.execute("limnology", "trophic_state_index", [sd])["result"]
# 60.0, 50.011749128131186, 40.02349825626237, 30.035247384393568
```

**Lake chemistry.** The Davies activity coefficient falls off with both ionic strength and the
square of ion charge — a dilute freshwater ion (`I = 0.001 mol/L`, monovalent) is barely affected,
while a divalent ion at typical river/lake ionic strength (`I = 0.01 mol/L`) is noticeably reduced:

```python
runtime.execute("limnochemistry", "activity_coefficient_davies", [0.001, 1.0])["result"]
# 0.9650843672351632 — Na+ or Cl- at I = 0.001, essentially ideal

runtime.execute("limnochemistry", "activity_coefficient_davies", [0.01, 2.0])["result"]
# 0.6625107187224764 — Ca2+ at I = 0.01, the z^2 term pulls it down much further
```

**Ocean.** `wave_celerity_deep` reduces to the standard `c ≈ 1.56·T` coastal-engineering rule of
thumb (`g/2π = 1.5605`), and `wave_celerity_shallow` is the textbook shallow-water speed:

```python
runtime.execute("oceanography", "wave_celerity_deep", [8.0])["result"]
# 12.490479933851947 m/s — vs. the 1.56*8 = 12.48 rule-of-thumb estimate

runtime.execute("oceanography", "wave_celerity_shallow", [2.0])["result"]
# 4.4294469180700204 m/s
```

`tidal_force`, given the Moon's real mass and mean Earth-Moon distance, reproduces the standard
geophysics-textbook figure for lunar tidal acceleration at Earth's surface:

```python
runtime.execute("oceanography", "tidal_force", [7.342e22, 3.844e8, 6.371e6])["result"]
# 1.0992286678329842e-06 m/s^2 — the commonly cited ~1.1 x 10^-6 m/s^2 value
```

{% hint style="warning" %}
**`seawater_density`'s salinity term is scaled two orders of magnitude too small.** At `T = 10 °C,
S = 35 PSU` — ordinary open-ocean surface water — the function returns **999.5997 kg/m³**, barely
above pure water at 0 °C, where real seawater at those conditions is close to 1027 kg/m³. The
source is `1000.0 - 0.0682*T + 0.00817*T*T*0.01 + 0.7814*S*0.01`: the linear temperature term is
unscaled, but both the quadratic temperature term *and* the salinity term carry an extra `*0.01`.
Removing just that factor from the salinity term alone gives `999.5997 - 0.35 + 27.349 = 1026.68
kg/m³` — within a fraction of a percent of the real value — which is strong evidence the `*0.01` on
the salinity term is a scaling slip rather than an intentional simplification. Anything downstream
that consumes this function's output as a real density (`buoyancy_frequency`,
`mixed_layer_heat_flux`) inherits the same near-total insensitivity to salinity.
{% endhint %}

{% hint style="warning" %}
**`buoyancy_frequency`'s `rho_upper`/`rho_lower` naming doesn't match its own "positive = stable"
docstring.** Feed it an ordinary, physically stable water column — lighter water on top
(`rho_upper = 1024`), denser water below (`rho_lower = 1026`), over a 10 m layer — and it returns
`0.0`, not a stability estimate:

```python
runtime.execute("oceanography", "buoyancy_frequency", [1024.0, 1026.0, 10.0])["result"]
# 0.0 — the physically stable arrangement (light over dense)

runtime.execute("oceanography", "buoyancy_frequency", [1026.0, 1024.0, 10.0])["result"]
# 0.04372963185020411 — only the physically UNSTABLE arrangement (dense over light)
# returns a nonzero value
```

`N² = -g/ρ_upper · (ρ_lower - ρ_upper)/thickness` is negative — and so clipped to `0.0` by the
`n2 <= 0.0` guard — exactly when `rho_lower > rho_upper`, i.e. exactly the ordinary case a caller
would expect to name "upper" and "lower" that way. A caller who passes surface and bottom density
in the order their names suggest gets silent `0.0` for every stable water column and a nonzero
result only for an inverted one.
{% endhint %}

**Storm meteorology.** The Gumbel (EV-I) flood-frequency factor for a 100-year event reproduces the
value commonly tabulated in flood-frequency handbooks:

```python
runtime.execute("hydrometeorology", "flood_frequency_factor", [100.0])["result"]
# 3.1368025160051296 — the standard K_100 ≈ 3.14 Gumbel frequency factor
```

{% hint style="warning" %}
**`redox_pe_eh` is missing its own stated `2.303` divisor.** The function's inline comment reads
`factor = 11604.5 / T_K  # F / (R × 2.303)`, but `11604.5` is `F/R` (the Faraday constant divided
by the gas constant, ≈11604.9 K/V) with no division by `ln(10) = 2.303` anywhere in the
expression. The standard aqueous-geochemistry conversion is `pe = Eh(V) / 0.05916` at 25 °C — so
`Eh = 59.16 mV` should return exactly `pe = 1.0`:

```python
runtime.execute("limnochemistry", "redox_pe_eh", [59.16, 25.0])["result"]
# 2.3026068086533624 — not 1.0
```

The output is `ln(10) ≈ 2.303` times larger than the textbook value at every temperature, a
consequence of the missing divisor rather than a different sign or unit convention — the ratio
between the code's factor and the theoretically correct one is `2.3029` at 25 °C, matching `2.303`
to four figures.
{% endhint %}

**Ecohydrology.** `root_water_uptake` and `ecohydrological_stress` share the same linear
soil-moisture-stress fraction — `root_water_uptake` just scales it by a potential-uptake rate:

```python
runtime.execute("ecohydrology", "ecohydrological_stress", [0.25, 0.35, 0.15])["result"]
# 0.5000000000000001 — (0.25 - 0.15) / (0.35 - 0.15)

runtime.execute("ecohydrology", "root_water_uptake", [0.25, 0.35, 0.15, 5.0])["result"]
# 2.5000000000000004 mm/day — the same 0.5 fraction times a 5.0 mm/day potential uptake
```

`riparian_buffer_efficiency`'s first-order removal model is exponential in residence time, so
substrate matters far more than buffer width — a 30 m buffer over fast-draining soil barely
touches nitrate, while a wider buffer over slow, fine-grained soil removes most of it:

```python
runtime.execute("ecohydrology", "riparian_buffer_efficiency", [30.0, 0.02, 5.0])["result"]
# 0.011928287138069482 — 30 m buffer, K_sat = 5 m/day: HRT is only 0.12 days, ~1.2% removed

runtime.execute("ecohydrology", "riparian_buffer_efficiency", [50.0, 0.05, 0.1])["result"]
# 0.9179150013761012 — 50 m buffer, K_sat = 0.1 m/day: HRT is 25 days, ~92% removed
```

## Refusal and edge-case behavior

No function in this family raises or aborts on the inputs below — each returns a defined sentinel
instead of dividing by zero, taking `log(0)`, or propagating a `nan`:

- **Zero-denominator guards return `0.0`, not `inf`/`nan`.** `hydraulic_retention_time`,
  `lake_flushing_rate`, `wetland_retention_time`, `streamflow_baseflow_index`, `hydraulic_gradient`,
  `dupuit_discharge`, `leakance_factor`, and `time_of_concentration` (hydrometeorology) all check
  their denominator against `<= 0.0` before dividing.
- **Fractions that represent a physical proportion are clamped to `[0, 1]`**, not left to overshoot:
  `groundwater_age_mixing` (young-water fraction), `root_water_uptake` and
  `ecohydrological_stress` (soil-moisture stress fraction), and `riparian_buffer_efficiency`
  (removal efficiency) all clamp explicitly rather than returning a value outside the physically
  meaningful range.
- **A non-physical input gets a labeled sentinel rather than a computed-but-meaningless number.**
  `secchi_depth_estimate` returns a fixed oligotrophic default of `10.0 m` for `chlorophyll_a <=
  0.0`; `trophic_state_index` returns `100.0` (hyper-eutrophic) for `secchi_depth_m <= 0.0`;
  `saturation_index_calcite` returns `-1.0` (undersaturated) if calcium or alkalinity is
  non-positive, since `log()` of a non-positive concentration is undefined.
- **`theis_drawdown` and `dupuit_discharge` return `0.0` for a non-positive transmissivity or flow
  length** rather than dividing by it — physically, zero transmissivity means no flow reaches the
  observation point anyway.
- **`runoff_curve_number` refuses an out-of-range curve number** (`cn <= 0.0` or `cn > 100.0`)
  with `0.0` rather than computing a negative or infinite `S`; `hydrology.curve_number_runoff` has
  no equivalent upper-bound check on `cn`, so a caller-supplied `cn > 100` there produces a negative
  `S` and a nonsensical (but finite) runoff depth instead of a refusal.

## Verification

All seven `mojo/tests/libs/test_{hydrology,hydrogeology,limnology,limnochemistry,oceanography,
hydrometeorology,ecohydrology}.mojo` files are auto-generated coverage smoke tests: each calls every
function once on a shared, arbitrary `0.5`-style fixture and checks only that the result is finite
— none pin a specific numeric output. Every number in this page was instead hand-traced against the
real formula in the corresponding `mojo/engine/*.mojo` source file and independently recomputed in
plain Python (no library calls) before being presented, including the three discrepancies flagged
above, each of which was confirmed by evaluating the actual source expression against a known
reference value (a 0.1 mm capillary tube, Carlson's original TSI calibration points, the `c ≈
1.56T` deep-water wave rule, real lunar tidal acceleration, a tabulated Gumbel K₁₀₀, and the
`pe = Eh/0.05916 V` reference point at 25 °C) rather than against the module's own test fixture.

**Next:** see [Geospatial indexing & joins](geospatial.md) for the spatial-indexing and
coordinate-frame machinery this family's per-catchment and per-basin quantities would sit on top
of, or browse the [Runtime library catalog](runtime-library-catalog.md) for every module and
function.
