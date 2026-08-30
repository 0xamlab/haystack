---
icon: temperature-half
description: Cryogenic and permafrost thermal physics, the four classical thermodynamic relations, battery electrochemistry, and solar/wind/photovoltaic energy-yield engineering across seven independent kernel modules.
---

# Thermal, cryogenic, and energy kernels

Seven small, self-contained modules for the thermal and energy-conversion physics that sit
underneath electrochemical storage and renewable generation: the ideal gas law and the two Carnot
relations that bound every heat engine and every refrigerator, the specialized low-temperature
engineering that keeps a superconductor or a liquefied gas cold, the frozen-ground and sea-ice
science of permafrost (an Earth-science module in an otherwise engineering-flavored family — see
below), the electrochemistry of a battery pack, and the irradiance/wind-resource geometry and
economics behind solar and wind power plants. None import Python, and none share code with each
other — `capacity_factor` alone has three independent implementations in this family, one per
generation technology.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("battery", "state_of_charge", [80.0, 100.0])["result"]
# 80.0 — 80 Ah remaining out of a 100 Ah pack, as a percentage

runtime.execute("cryogenics", "carnot_cop_cooling", [77.0, 300.0])["result"]
# 0.3452914798206278 — the ideal refrigeration COP for lifting heat from
# liquid-nitrogen temperature (77 K) up to room temperature (300 K)
```

## The modules

| Module | What it does |
| --- | --- |
| `battery` | State of charge, depth of discharge, coulombic efficiency, energy/power density, C-rate, discharge time, Peukert capacity, cycle-life degradation, internal resistance from a loaded-voltage reading, and series/parallel pack voltage and capacity. |
| `cryogenics` | Ideal gas density, Joule-Thomson cooling, Carnot cooling COP, simplified Linde-cycle liquefaction yield, cryostat boil-off rate, thermal contraction, conductive heat leak through an insulating wall, superconductor critical-temperature estimation, residual resistivity ratio, cryocooler input power, radiative heat flux between concentric vacuum-insulated surfaces, and the helium lambda point constant. |
| `cryology` | Permafrost thickness from mean annual air temperature, Stefan-equation active-layer depth, volumetric ground ice content, an annual freeze-thaw cycle estimate, Kersten-model frozen-soil thermal conductivity, ice-wedge volume, thermokarst subsidence, permafrost carbon release under a warming scenario, sea-ice extent anomaly, and snow/ice albedo feedback forcing. |
| `photovoltaics` | Cell efficiency, fill factor, power output, temperature-corrected power, annual energy yield from a performance ratio, plane-of-array irradiance from a horizontal measurement, solar LCOE, capacity factor, peak sun hours, and system performance ratio. |
| `solar_energy` | Irradiance on a tilted surface, panel power output, temperature derating, NOCT cell-temperature estimation, solar declination and hour angle, solar altitude (via a hand-rolled `asin`), capacity factor, LCOE, simple payback period, inverter efficiency, and series-string voltage. |
| `thermodynamics` | Ideal gas pressure and volume, Carnot engine efficiency, entropy change, heat capacity, adiabatic process pressure, isothermal work, Stefan-Boltzmann radiated power, Fourier conductive heat flux, Gibbs free energy, and the Clausius-Clapeyron vapor-pressure relation. |
| `wind_energy` | Available wind power, the Betz limit constant, power coefficient, tip-speed ratio, swept area, annual energy production, capacity factor, the wind-shear power law, Weibull mean wind speed (Rayleigh case), kinetic power density, rotor thrust, and Jensen-model wake velocity. |

## Cryology is Earth science, not engineering

Despite sitting next to `cryogenics` in this family, `cryology.mojo`'s own docstring calls it "ice,
permafrost, and frozen ground science" — every one of its ten functions is a climate/geoscience
quantity (permafrost thickness, active-layer depth, sea-ice extent anomaly, snow-ice albedo
feedback, permafrost carbon release under a warming scenario) rather than a cooling-system design
equation. `cryogenics`, by contrast, is genuinely engineering: Joule-Thomson valves, cryocoolers,
vacuum superinsulation, superconductor critical temperature. The two modules share a name root and
a temperature domain but answer different questions — one asks "how cold can we make this system,"
the other asks "how much frozen ground/ice is out there and what happens as it thaws."

## Two views of the same Carnot cycle

`thermodynamics.carnot_efficiency(T_hot, T_cold)` and `cryogenics.carnot_cop_cooling(t_cold,
t_hot)` are the same reversible cycle read in opposite directions — a heat engine's maximum
efficiency versus a refrigerator's maximum coefficient of performance:

```python
runtime.execute("thermodynamics", "carnot_efficiency", [600.0, 300.0])["result"]
# 0.5 — a heat engine between 600 K and 300 K converts at most half its input heat to work

runtime.execute("cryogenics", "carnot_cop_cooling", [77.0, 300.0])["result"]
# 0.3452914798206278 — moving heat the other direction, from 77 K up to 300 K,
# costs at least 1/COP = 2.8961 J of work per joule of heat lifted
```

`carnot_efficiency` is `1 - T_cold/T_hot`; `carnot_cop_cooling` is `T_cold/(T_hot - T_cold)`. Both
are exact algebraic rearrangements of the same Carnot cycle, one framed around work extracted from
a hot reservoir, the other around heat pumped out of a cold one.

## The same function name, different physics

`energy_density` exists in both `battery` and `wind_energy`, and it is not the same quantity in
each: `battery.energy_density(energy_wh, mass_kg)` is a gravimetric energy density in Wh/kg (how
much energy a cell packs per unit mass), while `wind_energy.energy_density(density, velocity)` is
`0.5 * ρ * v³`, a kinetic power flux in W/m² — the module's own docstring calls it "wind energy
density" but labels the units W/m², which is a power density, not a true energy density (J/m³).
Calling the wrong one because the name matched would silently swap Wh/kg for W/m² with no type
error to catch it.

`capacity_factor` has three independent implementations across the renewable-generation modules,
all computing the same ratio — actual energy produced over the maximum a plant could have
produced — with different argument names for the installed-capacity term:

- `wind_energy.capacity_factor(actual_energy, rated_power, hours)`
- `photovoltaics.capacity_factor(actual_energy, installed_kw, hours)`
- `solar_energy.capacity_factor_solar(annual_kwh, rated_kw, hours_year)`

All three divide by `rated * hours` and guard the same zero-denominator case; none call the
others.

## Worked examples

Every number below was recomputed independently in plain Python from the formula in the cited
`.mojo` file, not read off a test fixture (the real test files pin no numeric outputs — see
Verification).

**Battery pack, `battery.mojo`.** A 4S3P pack of 3.7 V / 2.5 Ah cells, discharged from 100 Ah to 80
Ah at a rate that would empty a rated-100 Ah/20 h battery in 10 hours instead:

```python
runtime.execute("battery", "battery_pack_voltage", [4.0, 3.7])["result"]   # 14.8  (V)
runtime.execute("battery", "battery_pack_capacity", [3.0, 2.5])["result"]  # 7.5   (Ah)
runtime.execute("battery", "depth_of_discharge", [80.0])["result"]         # 20.0  (%, DOD = 100 - SOC)
runtime.execute("battery", "peukert_capacity", [100.0, 20.0, 10.0, 1.2])["result"]
# 114.86983549970348 — see "Edge cases" below: this simplified formula's exponent is
# inverted relative to the textbook Peukert relation
```

**Cryogenic cooldown, `cryogenics.mojo`.** Lifting heat from liquid-nitrogen temperature (77 K) to
room temperature (300 K) through a 1 m² wall with `k = 0.02 W/(m·K)` and 5 cm of insulation:

```python
runtime.execute("cryogenics", "heat_leak_through_wall", [0.02, 1.0, 300.0, 77.0, 0.05])["result"]
# 89.19999999999999 W of conductive heat leak into the cold side

runtime.execute("cryogenics", "carnot_cop_cooling", [77.0, 300.0])["result"]
# 0.3452914798206278 — so removing that 89.2 W of heat leak ideally costs
# cryocooler_input_power(89.2, 0.3452914798206278) == 258.33 W of compressor input power
```

**Permafrost, `cryology.mojo`.** A site with mean annual air temperature -10°C and a geothermal
gradient of 0.025 °C/m:

```python
runtime.execute("cryology", "permafrost_thickness", [-10.0, 0.025])["result"]
# 400.0 m — H = |MAAT| / gradient

runtime.execute("cryology", "active_layer_depth", [1000.0, 1.5, 2.5e6])["result"]
# 10.182337649086284 m of seasonal thaw, given 1000 thawing degree-days,
# soil thermal conductivity 1.5 W/(m·K) and volumetric heat capacity 2.5e6 J/(m^3*K)
```

**Ideal gas law at STP, `thermodynamics.mojo`.** 1 mole of gas at 273.15 K in 0.0224 m³ (the
approximate molar volume at standard conditions):

```python
runtime.execute("thermodynamics", "ideal_gas_pressure", [1.0, 273.15, 0.0224])["result"]
# 101382.54910714286 Pa — within 0.06% of 101325 Pa (1 standard atmosphere); the residual
# is the rounding in R=8.314 J/(mol*K) and the 0.0224 m^3 input, not a kernel error
```

**Radiated power, `thermodynamics.mojo`.** A 1 m² blackbody at 300 K:

```python
runtime.execute("thermodynamics", "stefan_boltzmann", [300.0, 1.0])["result"]
# 459.27 W  (emissivity defaults to 1.0 when the 3rd argument is omitted)
```

**Wind turbine, `wind_energy.mojo`.** An 80 m rotor diameter (40 m radius) in 1.225 kg/m³ air at a
10 m/s free-stream wind speed:

```python
runtime.execute("wind_energy", "swept_area", [40.0])["result"]
# 5026.548245743669 m^2  (A = pi * r^2)

runtime.execute("wind_energy", "wind_power_available", [1.225, 5026.548245743669, 10.0])["result"]
# 3078760.8005179977 W — the kinetic power in the wind crossing that swept area;
# the Betz limit (betz_limit() == 0.5925925925925926, exactly 16/27) caps how much
# of this a real rotor can ever extract

runtime.execute("wind_energy", "capacity_factor", [2000000.0, 1000.0, 8760.0])["result"]
# 0.228310502283105 — 2 GWh from a 1 MW-rated turbine over a year, a realistic ~23%
# onshore capacity factor
```

**Solar PV string, `photovoltaics.mojo`.** A 300 W module at STC with `Voc = 40 V`, `Isc = 9.5 A`:

```python
runtime.execute("photovoltaics", "cell_efficiency", [300.0, 1000.0, 1.6])["result"]
# 0.1875 — 18.75% panel efficiency for a 1.6 m^2 module at 1000 W/m^2

runtime.execute("photovoltaics", "fill_factor", [300.0, 40.0, 9.5])["result"]
# 0.7894736842105263 — a realistic ~79% fill factor for crystalline silicon

runtime.execute("photovoltaics", "temperature_coefficient", [300.0, -0.004, 45.0])["result"]
# 276.0 W — 8% power loss at 45 degC cell temperature with gamma = -0.004/degC
```

## A hand-rolled `asin`, checked against the real one

`solar_energy.solar_altitude` needs an arcsine and the module has no library one, so it computes
one with a Taylor/reflection polynomial (`asin(x) approx x*(1 + x^2*(1/6 + x^2*(3/40 + ...)))`,
switching to the complementary-angle identity above `|x| > 0.7` for accuracy near the poles).
Checked against Python's `math.asin` at latitude 40 degrees, the solstice declination
`solar_declination(172) = 23.449782846813658` degrees, and solar noon (`hour_angle = 0`):

```python
runtime.execute("solar_energy", "solar_altitude", [40.0, 23.449782846813658, 0.0])["result"]
# 73.44978421771798 (kernel polynomial)
# vs. 73.44978284681363 from math.asin on the identical sin(altitude) — agrees to 1.4e-6 degrees
# and both match the classic solar-noon identity altitude = 90 - lat + declination = 73.449782846813658
```

## Edge cases and refusal behavior

- **`peukert_capacity`'s exponent runs backwards from the textbook relation.** The classical
  Peukert law gives usable amp-hours at an actual discharge rate as `C_rated * (I_actual /
  I_rated)^(1-k)`, which *decreases* as the discharge current rises (a battery yields fewer usable
  Ah the harder it is pushed). This kernel computes `C_rated * ratio^(k-1)` — the exponent's sign
  is flipped — so it does the opposite: `peukert_capacity(100.0, 20.0, 10.0, 1.2)` (discharging at
  twice the rated 5 A rate) returns `114.87`, *more* than the 100 Ah rating, while
  `peukert_capacity(100.0, 20.0, 2.5, 1.2)` (half the rated rate) returns `87.06`, *less*. The
  correct-formula value at 2x the rated rate (`87.06`) is exactly this kernel's value at half the
  rated rate, and vice versa — confirmed by evaluating both formulas side by side. Values from this
  function should not be used for real battery sizing without correcting the exponent's sign.
- **An infinite COP is refused, not returned.** `cryogenics.carnot_cop_cooling` explicitly checks
  `|t_hot - t_cold| < 1e-15` and returns `0.0` instead of dividing by (near-)zero — the source
  comment explains why: "a zero temperature lift has no finite COP; the division yields `inf`,
  which cannot cross the JSON result wire (the worker aborts serializing it), so answer with the
  sentinel." `0.0` here means "no information," not "zero COP."
- **A capacity floor, not a negative one.** `battery.cycle_life_degradation` clamps its
  `1 - degradation_per_cycle * cycles` factor to `0.0` before multiplying, so a battery cycled far
  past its rated life reports zero remaining capacity rather than a physically meaningless negative
  one.
- **No permafrost above freezing.** `cryology.permafrost_thickness` returns `0.0` whenever
  `mean_annual_temp_c >= 0.0` or the geothermal gradient is non-positive — a warm site has no
  permafrost thickness to compute, and the function says so rather than returning a division
  artifact.
- **Two different near-zero thresholds, not one.** `battery`'s and `cryogenics`' guards use
  `1e-15`; `thermodynamics` and `solar_energy` guard division at `1e-30` instead — both are
  legitimate "don't divide by zero" epsilons, but they are not the same constant reused across the
  family, so a value that is "small" by one module's threshold is not necessarily small by
  another's.
- **A sign the docstring doesn't promise.** `thermodynamics.thermal_conductivity_flux` implements
  Fourier's law literally as `-k*A*dT/dx`, but its own `Returns:` docstring says the result is
  "in W (magnitude, positive)." Calling it with `dT = T_hot - T_cold > 0` (the natural way to read
  the argument name) returns a **negative** number — `thermal_conductivity_flux(0.6, 1.0, 10.0,
  0.1) == -60.0` — because the minus sign in the formula is not undone anywhere before return. Take
  the absolute value if the docstring's "positive magnitude" claim is what you actually need.
- **A "%/day" label with no day in the arithmetic.** `cryogenics.boiloff_rate` computes
  `heat_leak / (latent_heat * mass) * 100.0` and its docstring calls the result "%/day," but nothing
  in the formula converts a power (W = J/s) into energy-per-day. Passing `heat_leak` as watts
  produces a %/second figure two orders of magnitude below "%/day" (`boiloff_rate(10.0, 199000.0,
  50.0) == 0.0001005...`, not a day-scaled percentage) — convert `heat_leak` to J/day
  (multiply watts by 86400) before calling if the docstring's unit label is what you want back.

## Verification

All seven `mojo/tests/libs/test_*.mojo` files behind this family (`test_battery.mojo`,
`test_cryogenics.mojo`, `test_cryology.mojo`, `test_photovoltaics.mojo`, `test_solar_energy.mojo`,
`test_thermodynamics.mojo`, `test_wind_energy.mojo`) are auto-generated coverage smoke tests: every
function is called once with a shared, arbitrary `0.5`-valued fixture and the test only checks that
the result is finite — none pin a specific numeric output. (One function is a partial exception:
the generator calls `cryogenics.carnot_cop_cooling` with `(200.0, 300.0)` instead of the shared
`(0.5, 0.5)` fixture, but it still only checks finiteness, not a pinned value.) The worked examples
above were computed independently in Python from the real formulas in `mojo/engine/battery.mojo`,
`cryogenics.mojo`, `cryology.mojo`, `photovoltaics.mojo`, `solar_energy.mojo`,
`thermodynamics.mojo`, and `wind_energy.mojo`, and every number given can be reproduced by
re-running the same arithmetic.

**Next:** see the full function list in the [runtime library catalog](runtime-library-catalog.md),
or the [engine catalog](catalog.md) for how these modules are exposed at the API level.
