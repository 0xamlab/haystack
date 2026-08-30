---
icon: mountain
description: Landform evolution and fluvial morphometrics, soil/rock mechanics for construction, soil formation and classification science, and sediment transport/grain-size statistics, across four independent scalar-formula modules.
---

# Surface processes: landforms, soils, and sediment

Four small, independent modules for the physics and empirical formulas of the Earth's surface:
how a river basin's shape and flow carve and diffuse a landscape (`geomorphology`), how soil and
rock support or fail under a foundation or a slope (`geotechnical`), how a soil profile develops
its horizons and gets classified (`pedology`), and how sediment grains move, settle, and sort
themselves once eroded (`sedimentology`). None of the four share a namespace prefix or import
Python — each is a flat, single-file module of `Float64`-in/`Float64`-out functions with no
structs and no shared state, called directly by its bare module name.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("geotechnical", "bearing_capacity_terzaghi",
                [25.0, 18.0, 1.5, 2.0, 37.2, 22.5, 19.7])["result"]
# 1892.1 — Terzaghi ultimate bearing capacity (kPa) for a 2 m strip footing at 1.5 m depth

runtime.execute("sedimentology", "grain_size_phi", [0.0625])["result"]
# 4.0 — 0.0625 mm is exactly the sand/silt boundary on the Wentworth scale, phi 4
```

## The modules

| Module | What it does |
| --- | --- |
| `geomorphology` | Landform evolution and river-basin morphometrics: stream power, bed shear stress, the Shields parameter and Stokes settling velocity for sediment entrainment, stream-power-law erosion, hillslope diffusion, and basin-shape statistics (drainage density, relief ratio, sinuosity, Hack's law length, ruggedness number, hypsometric integral). |
| `geotechnical` | Soil and rock mechanics for construction: Terzaghi ultimate bearing capacity, effective stress, Rankine active/passive earth-pressure coefficients and Jaky's at-rest coefficient, simplified elastic settlement, slope-stability factor of safety, and the phase relationships (void ratio, porosity, degree of saturation) that connect them. |
| `pedology` | Soil formation and classification science: composite development indices (soil development index, profile development index), clay illuviation, Munsell-colour rubification, organic-horizon depth from a litter/decomposition balance, base saturation, Jenny's (1941) climate-age solum-thickness model, biological weathering, element translocation, and an inverse age-from-pedogenesis estimate. |
| `sedimentology` | Sediment transport, deposition, and grain-size statistics: Stokes settling velocity, the Shields parameter and its critical threshold, Meyer-Peter–Müller bedload transport, the Rouse suspended-sediment concentration profile, phi-scale grain-size conversion, and Folk-and-Ward sorting and skewness. |

All four modules match their name and the working assumption behind this page — there is no
`distillation`-style surprise here: `geomorphology.mojo`, `geotechnical.mojo`, `pedology.mojo`, and
`sedimentology.mojo` each open with a docstring describing exactly the earth-science subject their
name implies, and the function bodies bear that out.

## Everything here is a scalar in, a scalar out

Every function across all four modules takes only `Float64` parameters and returns a single
`Float64` — the contract lists zero structs for any of them. There is no `TxBuffer`-style shared
carrier the way `tensorx` has, and no `KMeansResult`-style struct the way the ML modules return;
a caller building a multi-step calculation (say, computing a Shields parameter and feeding it into
bedload transport) threads every intermediate value through Python itself, one `["result"]` at a
time.

## Two independent Shields parameters, two independent settling velocities

`geomorphology` and `sedimentology` both implement the Shields parameter and the Stokes settling
velocity — the two modules never call into each other, and the two implementations are not
byte-for-byte the same function under two names:

- **Shields parameter.** `geomorphology.shields_parameter(shear_stress, density_s, density_f, g,
  grain_size)` takes gravitational acceleration as an explicit parameter and only guards the exact
  case `denom == 0.0`. `sedimentology.shields_parameter(bed_shear_stress, grain_diameter_m,
  grain_density, fluid_density)` hardcodes `g = 9.81` internally (dropping it as a parameter
  entirely) and guards the broader `denom <= 0.0` — so a caller who accidentally passes
  `fluid_density > grain_density` gets `0.0` from `sedimentology` but a real (negative) number from
  `geomorphology`.
- **Stokes settling velocity.** `geomorphology.settling_velocity_stokes(density_s, density_f, g,
  diameter, viscosity)` takes **dynamic** viscosity μ (Pa·s) directly:
  `ws = (ρs−ρf)·g·d² / (18·μ)`. `sedimentology.settling_velocity_stokes(grain_diameter_m,
  grain_density, fluid_density, kinematic_viscosity)` takes **kinematic** viscosity ν (m²/s) and
  fluid density separately, hardcodes `g = 9.81`, and divides by `18·ν·ρf` — algebraically the same
  formula, since `ν·ρf = μ`, but the parameter list, order, and units are entirely different. The
  two do agree numerically once fed physically equivalent inputs — see the worked examples below.

Neither pairing is a bug; they are separate authors' solutions to the same physics, reachable under
two different module names, and a caller who assumes one signature works for the other will get a
`TypeError`-style argument-count mismatch, not a wrong answer.

## Bearing capacity doesn't compute its own N-factors

`geotechnical.bearing_capacity_terzaghi(c, gamma, d, b, nc, nq, ngamma)` implements only the
combination step of Terzaghi's formula — `q_ult = c·Nc + γ·D·Nq + 0.5·γ·B·Nγ` — and takes the three
bearing-capacity factors `Nc`, `Nq`, `Nγ` as plain `Float64` arguments. It does not look them up
from a friction-angle table and does not know what `φ` the caller had in mind. A caller has to
already have the right factors for their footing type and friction angle (Terzaghi published
separate general-shear and local-shear tables, and later authors such as Meyerhof and Vesic revised
them) — the worked example below uses figures commonly tabulated for `φ ≈ 30°` strip footings under
general shear failure (`Nc ≈ 37.2`, `Nq ≈ 22.5`, `Nγ ≈ 19.7`), but that table lookup happens
entirely outside this kernel.

## A river basin, worked by hand

Every number below was computed independently in Python against the formulas in
`mojo/engine/geomorphology.mojo`, not read from the module's own test file — see
[Verification](#verification). One small basin, consistent SI units throughout:

```python
runtime.execute("geomorphology", "drainage_density", [12000.0, 4_000_000.0])["result"]
# 0.003 — 12 km of channel draining a 4 km² basin (1/m)

runtime.execute("geomorphology", "relief_ratio", [800.0, 8000.0])["result"]
# 0.1 — 800 m of relief over an 8 km basin length

runtime.execute("geomorphology", "ruggedness_number", [800.0, 0.003])["result"]
# 2.4 — relief (m) times drainage density (1/m), dimensionless

runtime.execute("geomorphology", "hypsometric_integral", [350.0, 100.0, 800.0])["result"]
# 0.35714285714285715 — a basin skewed toward its lower elevations (HI < 0.5)

runtime.execute("geomorphology", "sinuosity", [15000.0, 10000.0])["result"]
# 1.5 — a 15 km channel meandering through a 10 km straight-line valley

runtime.execute("geomorphology", "hack_law_length", [1.4, 4.0, 0.6])["result"]
# 3.2163553939916976 — Hack's law predicted main-stream length for a 4 km² catchment
```

The same basin under a flood discharge of 50 m³/s, a 0.002 channel slope, and 2 m of flow depth:

```python
runtime.execute("geomorphology", "stream_power", [50.0, 0.002, 1000.0, 9.81])["result"]
# 981.0 — stream power in W/m

tau = runtime.execute("geomorphology", "shear_stress_flow", [1000.0, 9.81, 2.0, 0.002])["result"]
# 39.24 — bed shear stress in Pa

runtime.execute("geomorphology", "shields_parameter", [tau, 2650.0, 1000.0, 9.81, 0.01])["result"]
# 0.24242424242424243 — well above the ~0.047 threshold quartz sand starts moving at (see
#                       sedimentology.critical_shear_stress below): 1 cm bed grains are entrained

runtime.execute("geomorphology", "erosion_rate_spl", [1e-5, 4_000_000.0, 0.002, 0.5, 1.0])["result"]
# 4e-05 — stream-power-law incision (m/yr) for this area, slope, and a modest erodibility K

runtime.execute("geomorphology", "hillslope_diffusion", [0.01, 0.05])["result"]
# 0.0005 — sediment flux (m²/yr) off a gently concave hillslope, Kd = 0.01 m²/yr

runtime.execute("geomorphology", "settling_velocity_stokes", [2650.0, 1000.0, 9.81, 0.0001, 0.001])["result"]
# 0.0089925 — a 100 micron quartz grain's fall velocity through 20°C water (μ = 0.001 Pa·s)
```

That last number reappears, computed a different way, in the sedimentology example below —
`sedimentology.settling_velocity_stokes` at kinematic viscosity `1e-6 m²/s` and the same
1000 kg/m³ water is the identical physical input (`ν·ρf = μ = 0.001`), and it produces the same
`0.0089925 m/s`.

`geomorphology.mojo`'s division-by-zero guards are inconsistent across its own file: only
`shields_parameter` (exact `denom == 0.0`) and `hypsometric_integral` (`max_elev == min_elev`)
return the `0.0` sentinel documented as necessary because "inf/nan cannot cross the result wire."
`drainage_density`, `relief_ratio`, and `sinuosity` have no such guard — a zero `basin_area`,
`basin_length`, or `valley_length` reaches an unguarded division and produces `inf` rather than a
defined value. `hack_law_length` and `erosion_rate_spl` both call `pow` with fractional exponents
(`h ≈ 0.6`, `m`/`n`) against a caller-supplied `area`/`slope` with no non-negativity check; a
negative area or slope — never physically valid, but not rejected — produces `NaN` from `pow`
rather than a caught error.

## A shallow foundation, worked by hand

`mojo/engine/geotechnical.mojo`, traced independently in Python. A strip footing 2 m wide at 1.5 m
depth, cohesion 25 kPa, unit weight 18 kN/m³, and `φ = 30°` bearing-capacity factors:

```python
runtime.execute("geotechnical", "bearing_capacity_terzaghi",
                [25.0, 18.0, 1.5, 2.0, 37.2, 22.5, 19.7])["result"]
# 1892.1 — q_ult (kPa): 930.0 (cohesion term) + 607.5 (surcharge term) + 354.6 (self-weight term)

sv = runtime.execute("geotechnical", "overburden_pressure", [5.0, 18.0])["result"]
# 90.0 — vertical total stress at 5 m depth (kPa)

runtime.execute("geotechnical", "coefficient_of_earth_pressure_at_rest", [0.5235987755982988])["result"]
# 0.5 — Jaky's K0 = 1 - sin(30°); sin(30°) = 0.5 exactly

ka = runtime.execute("geotechnical", "rankine_ka", [0.5235987755982988])["result"]
# 0.3333333333333333 — (1 - sin30)/(1 + sin30) = 0.5/1.5

runtime.execute("geotechnical", "rankine_kp", [0.5235987755982988])["result"]
# 3.0 — (1 + sin30)/(1 - sin30) = 1.5/0.5; Ka * Kp = 1.0 always, by construction

runtime.execute("geotechnical", "active_earth_pressure", [ka, sv, 0.0])["result"]
# 30.0 — cohesionless active pressure: Ka * sigma_v

runtime.execute("geotechnical", "active_earth_pressure", [ka, sv, 10.0])["result"]
# 18.452994616207484 — 10 kPa of cohesion reduces the active pressure via the -2c*sqrt(Ka) term
```

Settlement and slope stability, and the phase relationships that connect void ratio and porosity:

```python
runtime.execute("geotechnical", "settlement_elastic", [150.0, 2.0, 20000.0, 0.3])["result"]
# 0.01365 — 13.65 mm of elastic settlement under 150 kPa on a 2 m footing, E = 20 MPa, nu = 0.3

runtime.execute("geotechnical", "factor_of_safety_slope", [500.0, 350.0])["result"]
# 1.4285714285714286 — FS > 1.0: the slope is stable under these forces

e = runtime.execute("geotechnical", "void_ratio", [0.4])["result"]
# 0.6666666666666667 — 40% porosity as a void ratio

runtime.execute("geotechnical", "porosity_from_void_ratio", [e])["result"]
# 0.4 — round-trips back to the original porosity exactly

runtime.execute("geotechnical", "degree_of_saturation", [0.15, e, 2.65])["result"]
# 0.5962499999999998 — ~59.6% saturated at 15% gravimetric water content, Gs = 2.65
```

`void_ratio` is the only function in this module with an explicit guard: `porosity >= 1.0` (which
would divide by zero) or a self-comparison failure (`porosity != porosity`, i.e. NaN) both return
`0.0`. `porosity_from_void_ratio`, `degree_of_saturation`, `effective_stress`,
`overburden_pressure`, `factor_of_safety_slope`, `settlement_elastic`, `rankine_ka`, and
`rankine_kp` have no equivalent checks — a void ratio of `-1`, a saturation calculation with `e =
0`, a zero `driving_force`, a zero `modulus`, or a `phi` of exactly ±90° (which zeroes `rankine_kp`'s
or `rankine_ka`'s denominator) all reach an unguarded division and produce `inf`.

## A soil profile, worked by hand

`mojo/engine/pedology.mojo`, traced independently in Python. A single developing profile, so the
numbers below chain together rather than standing alone:

```python
bs = runtime.execute("pedology", "base_saturation_percent", [18.0, 30.0])["result"]
# 60.0 — 18 cmol+/kg of exchangeable bases over a 30 cmol+/kg CEC; >50% clears the docstring's
#        Mollisol-type criterion

runtime.execute("pedology", "clay_illuviation_ratio", [32.0, 18.0])["result"]
# 1.7777777777777777 — Bt-horizon clay (32%) over E-horizon clay (18%); >1.2 signals real
#                       clay accumulation per the docstring

runtime.execute("pedology", "rubification_index", [5.0, 6.0, 4.0])["result"]
# 7.5 — a 5R hue, chroma 6, value 4 (a fairly red, well-oxidised subsoil colour)

runtime.execute("pedology", "organic_horizon_depth", [300.0, 0.3])["result"]
# 10.0 cm — steady-state O-horizon depth: 300 g/m²/yr litter, k = 0.3/yr, 100 g/m² per cm

runtime.execute("pedology", "solum_thickness_estimate", [1000.0, 15.0, 100.0])["result"]
# 246.13976089820056 cm — Jenny (1941) climate-age model: 1000 mm/yr precipitation,
#                          15 deg C, 100 ky of soil age

pdi = runtime.execute("pedology", "profile_development_index", [15.0, 3.0, 40.0])["result"]
# 1800.0 — 15% clay increase, structure grade 3, a 40 cm horizon

runtime.execute("pedology", "biological_weathering_index", [0.5, 40.0])["result"]
# 0.2 — 0.5 km/m³ fine-root density and 40% lichen cover

runtime.execute("pedology", "translocation_coefficient", [250.0, 100.0])["result"]
# 2.5 — 250 mg/kg subsoil vs. 100 mg/kg topsoil: accumulated in the subsoil (Tc > 1, e.g. Fe
#       in a spodosol per the docstring)

runtime.execute("pedology", "soil_age_from_pedogenesis", [pdi, 18.0])["result"]
# 100.0 — the same PDI of 1800, at an accumulation rate of 18 PDI-units/ky, implies exactly
#         the 100 ky age used as an input above

runtime.execute("pedology", "soil_development_index", [30.0, bs, 4.0])["result"]
# 19.309787692112593 — cube root of (30% clay x 60% base saturation x 4% organic matter)
```

`soil_age_from_pedogenesis` and `profile_development_index` are algebraic inverses of each other
given a fixed rate (`age = PDI / rate`, `PDI = clay_increase * structure_grade * thickness`), which
is why feeding one module's output into the other above returns exactly the age (100 ky) the profile
example started from — not a coincidence, a property of the two formulas.

Eight of this module's ten functions guard their division or their `pow`-with-non-positive-base
case explicitly, returning `0.0`: `soil_development_index` (product `<= 0.0`),
`clay_illuviation_ratio` (`eluvial_clay_pct <= 0.0`), `rubification_index` (`value <= 0.0`),
`organic_horizon_depth` (`decomposition_rate <= 0.0`), `base_saturation_percent` (`cec_cmol_kg <=
0.0`), `solum_thickness_estimate` (`temperature_c <= 0.0`), `translocation_coefficient`
(`element_topsoil <= 0.0`), and `soil_age_from_pedogenesis` (`pdi_rate <= 0.0`). The remaining two,
`profile_development_index` and `biological_weathering_index`, are pure multiplication with no
division to guard.

## A sand bed under flow, worked by hand

`mojo/engine/sedimentology.mojo`, traced independently in Python. Grain-size conversion first:

```python
runtime.execute("sedimentology", "grain_size_phi", [1.0])["result"]
# 0.0 — 1 mm is exactly phi 0, the reference point of the scale

runtime.execute("sedimentology", "grain_size_phi", [0.0625])["result"]
# 4.0 — 0.0625 mm is the sand/silt boundary, phi 4

runtime.execute("sedimentology", "phi_to_mm", [4.0])["result"]
# 0.0625 — round-trips back exactly
```

1 mm quartz sand (density 2650 kg/m³) in water (1000 kg/m³):

```python
tau_c = runtime.execute("sedimentology", "critical_shear_stress", [0.001, 2650.0, 1000.0])["result"]
# 0.7607655 Pa — threshold shear stress for incipient motion, theta_c = 0.047 built into the formula

theta = runtime.execute("sedimentology", "shields_parameter", [1.5, 0.001, 2650.0, 1000.0])["result"]
# 0.09266981744045964 — actual bed shear stress of 1.5 Pa is well above tau_c, so theta > 0.047

runtime.execute("sedimentology", "bedload_transport", [theta, 0.047, 0.001, 1000.0, 2650.0])["result"]
# 0.07807893849585193 — dimensionless Meyer-Peter-Muller bedload rate, 8*(theta - theta_c)^1.5

runtime.execute("sedimentology", "settling_velocity_stokes", [0.0001, 2650.0, 1000.0, 1e-6])["result"]
# 0.0089925 m/s — a 100 micron grain's fall velocity; identical to the geomorphology worked
#                 example above once viscosity is expressed consistently (nu * rho_f = mu)

runtime.execute("sedimentology", "suspended_load_rouse", [0.5, 0.05, 1.0, 1.0, 5.0])["result"]
# 0.020202020202020204 kg/m³ — concentration at 1 m above the bed, given 0.5 kg/m³ at a 5 cm
#                               reference height, Rouse number 1.0, 5 m total flow depth
```

Grain-size distribution statistics (phi values `84th=1.5, 16th=0.2, 50th=0.8, 95th=2.0, 5th=-0.3`):

```python
runtime.execute("sedimentology", "sorting_coefficient", [1.5, 0.2, 2.0, -0.3])["result"]
# 0.6734848484848485 phi — moderately sorted on the Folk and Ward scale (0.5-1.0)

runtime.execute("sedimentology", "skewness_folk_ward", [1.5, 0.2, 0.8, 2.0, -0.3])["result"]
# 0.06020066889632099 — close to symmetrical, very slightly fine-skewed

runtime.execute("sedimentology", "sediment_budget", [1000.0, 600.0, 200.0])["result"]
# 600.0 — supply 1000, minus deposition 600, plus erosion (remobilised material) 200: net accumulating
```

Six of this module's ten functions guard against a non-positive denominator or base and return
`0.0`: `settling_velocity_stokes` and `shields_parameter` (`denom <= 0.0`, the broader guard
described above), `bedload_transport` (`excess <= 0.0`), `suspended_load_rouse` (`height` outside
`(0, depth)` or a non-positive ratio), `grain_size_phi` (`diameter_mm <= 0.0`), and
`skewness_folk_ward` (either phi-range denominator equal to `0.0`). `critical_shear_stress`,
`phi_to_mm`, `sorting_coefficient`, and `sediment_budget` have no division by a variable quantity
(`sorting_coefficient` only ever divides by the fixed constants `4.0` and `6.6`), so there is
nothing to guard.

## Verification

`mojo/tests/libs/test_geomorphology.mojo`, `test_geotechnical.mojo`, `test_pedology.mojo`, and
`test_sedimentology.mojo` are auto-generated coverage smoke tests, the same pattern documented on
[Classical ML algorithms](ml-classical-algorithms.md) and
[Mixture-of-experts and routing kernels](mixture-of-experts-and-routing-kernels.md): every function
is called once against a shared, arbitrary `0.5`-valued fixture (or, for `bearing_capacity_terzaghi`,
seven copies of `0.5`), and the only assertion is that the result is finite
(`not isnan(x) and not isinf(x)`) — none of the four files pins a specific numeric output. Every
number in the worked examples above was instead computed independently, by re-implementing each
function's formula in plain Python from the real source in `mojo/engine/geomorphology.mojo`,
`geotechnical.mojo`, `pedology.mojo`, and `sedimentology.mojo`, and can be reproduced by re-running
the same arithmetic.

**Next:** see [Geospatial indexing & joins](geospatial.md) for the other Earth-science kernel
family in this runtime, or [Runtime library catalog](runtime-library-catalog.md) for every module
and function.
