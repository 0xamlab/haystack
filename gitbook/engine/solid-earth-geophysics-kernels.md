---
icon: mountain
description: WGS84 geodesy and coordinate conversion, gravity/magnetic/seismic-velocity survey formulas, earthquake magnitude and travel-time relations, and simplified volcanic-eruption dynamics.
---

# Solid-Earth geophysics kernels

Four independent modules for measuring and modeling the solid Earth, none of which import Python
and none of which share a struct or an error-status vocabulary with one another — each is a flat
set of textbook formulas, `Float64` in and `Float64` (or a small `List[Float64]`) out. `geodesy` is
positioning: distance, bearing, and coordinate conversion on the WGS84 reference ellipsoid.
`geophysics` is survey physics: the gravity and magnetic corrections and P/S-wave elastic-modulus
relations used to interpret a gravimeter, magnetometer, or seismic-reflection line. `seismology` is
earthquake-specific: magnitude scales, seismic moment and radiated energy, and the P/S-wave
travel-time arithmetic used to locate an epicenter. `volcanology` is a set of deliberately
simplified eruption-dynamics formulas — lava flow speed, column height, tephra thickness, gas
emission — none of which claim to be a physical simulation.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# New York (40.7128, -74.0060) to London (51.5074, -0.1278), great-circle distance
runtime.execute("geodesy", "haversine_distance", [40.7128, -74.0060, 51.5074, -0.1278])["result"]
# 5570.222179737958 -- km, spherical-Earth approximation

# Radiated seismic energy for a Mw 9.0 earthquake (Gutenberg-Richter energy-magnitude relation)
runtime.execute("seismology", "energy_from_magnitude", [9.0])["result"]
# 1.995262314968883e+18 -- joules; same order of magnitude as the 2011 Tohoku earthquake
```

## The modules

| Module | What it does |
| --- | --- |
| `geodesy` | WGS84 ellipsoidal positioning: haversine and iterative-Vincenty distance, forward bearing, destination point, midpoint, cross-track and along-track distance from a great-circle path, rhumb-line (constant-bearing) distance, and geodetic ↔ ECEF coordinate conversion |
| `geophysics` | Gravity-survey corrections (free-air, Bouguer anomaly, Airy isostasy), latitude/elevation-dependent gravitational acceleration and geocentric Earth radius, magnetic inclination from field components, and P/S-wave seismic velocity and Vp/Vs (Poisson's ratio) from elastic moduli and density |
| `seismology` | Earthquake magnitude scales (Richter local magnitude, moment magnitude), seismic moment and radiated-energy relations, P/S-wave travel time and the ts-tp epicenter-distance method, a simplified peak-ground-acceleration attenuation, MMI intensity from PGA, and Gutenberg-Richter recurrence statistics |
| `volcanology` | Simplified eruption-dynamics formulas: VEI energy estimate, lava-flow velocity (Jeffreys equation), eruption column height, tephra fallout thickness, magma viscosity from SiO₂ content, effusion rate, lahar velocity, volcanic gas emission rate, recurrence interval, a three-indicator alert level, pyroclastic-flow runout, and caldera collapse volume |

## `geodesy`: distance and position on an ellipsoid, not a sphere

Most of the ten functions work on the mean-radius sphere (`EARTH_RADIUS_KM = 6371.0`), but
`vincenty_distance`, `geodetic_to_ecef`, and `ecef_to_geodetic` use the WGS84 ellipsoid
(`WGS84_A = 6378137.0` m semi-major axis, `WGS84_F = 1/298.257223563` flattening) — the same
reference frame GPS reports coordinates in. The gap between the two models is real and measurable
on the same pair of points:

```python
nyc, london = (40.7128, -74.0060), (51.5074, -0.1278)

runtime.execute("geodesy", "haversine_distance", [*nyc, *london])["result"]
# 5570.222179737958 km -- spherical great circle

runtime.execute("geodesy", "vincenty_distance", [*nyc, *london])["result"]
# 5585.233578943... km -- ellipsoidal geodesic, ~15 km longer

runtime.execute("geodesy", "rhumb_distance", [*nyc, *london])["result"]
# 5794.120750735244 km -- constant-bearing path, longer still (not the shortest route)
```

All three numbers were independently re-derived in Python from the same formulas as the source
(see [Verification](#verification)) and agree with the Mojo source to floating-point precision.
`vincenty_distance` iterates its own `lam` correction up to 100 times and falls back to
`haversine_distance` if it fails to converge to `1e-12` inside that budget — it never raises or
returns a partial answer.

`cross_track_distance` and `along_track_distance` reproduce the classic navigation-formulary
example: a point at `(53.2611, -0.7972)` measured against a path starting at `(53.3206, -1.7297)`
on bearing 096°. Hand-computed independently in Python from the same haversine/bearing calls the
Mojo source uses:

```python
runtime.execute("geodesy", "cross_track_distance",
                [53.2611, -0.7972, 53.3206, -1.7297, 53.21725, -0.23590])["result"]
# 0.3056648607756511 km off the path -- matching the ~0.31 km (0.166 NM) figure
# the same worked example produces in Ed Williams' Aviation Formulary
```

`geodetic_to_ecef` and `ecef_to_geodetic` are exact inverses of each other to about 9 significant
figures (the latter iterates its own latitude estimate 10 times rather than solving closed-form):

```python
xyz = runtime.execute("geodesy", "geodetic_to_ecef", [45.0, 45.0, 0.0])["result"]
xyz
# [3194419.1450606193, 3194419.145060619, 4487348.4088657275]  -- meters

runtime.execute("geodesy", "ecef_to_geodetic", xyz)["result"]
# [44.99999999999999, 45.0, -9.313225746154785e-10]  -- lat, lon, altitude back to ~1nm
```

## `geophysics`: gravity, magnetism, and seismic velocity for subsurface survey

**P/S-wave velocity and Poisson's ratio.** `seismic_p_wave_velocity` and
`seismic_s_wave_velocity` implement the standard isotropic-elastic relations
`Vp = sqrt((K + 4G/3) / ρ)` and `Vs = sqrt(G / ρ)` (moduli in GPa, density in kg/m³, velocity in
m/s), and `vp_vs_ratio` recovers Poisson's ratio from the two velocities. A textbook crustal rock
(`K = 50 GPa`, `G = 30 GPa`, `ρ = 2700 kg/m³`) lands exactly on the classic "Poisson solid" case:

```python
vp = runtime.execute("geophysics", "seismic_p_wave_velocity", [50.0, 30.0, 2700.0])["result"]
vs = runtime.execute("geophysics", "seismic_s_wave_velocity", [30.0, 2700.0])["result"]
vp, vs
# 5773.502691896258, 3333.3333333333335  -- m/s

runtime.execute("geophysics", "vp_vs_ratio", [vp, vs])["result"]
# 0.24999999999999994 -- Poisson's ratio 0.25, since Vp/Vs = sqrt(3) here
```

`vp_vs_ratio` returns the sentinel `0.5` (the incompressible-fluid limit) rather than dividing by
zero whenever `vs <= 0.0` or the ratio's own denominator (`2*(r*r - 1)`) is non-positive — a caller
never sees a `NaN` or an infinite Poisson's ratio.

**Earth's ellipsoidal shape, from the geophysics side.** `earth_radius_at_latitude` computes the
same geocentric radius `geodesy` implicitly assumes is constant (`EARTH_RADIUS_KM`), but as a real
function of latitude: `6378137.0` m at the equator, `6356752.314` m at the pole, `6367489.54` m at
45°.

**Free-air and Bouguer corrections.** `free_air_correction` is the standard `0.3086` mGal/m
vertical gravity gradient; `gravity_anomaly_bouguer` combines it with a simplified GRS80
theoretical-gravity term and a Bouguer plate correction (`0.04191 * ρ * h`). Its own internal
theoretical-gravity term divides the GRS80 polynomial by `1000`, landing it in the same numeric
range (~978–990) as gravity expressed in **Gal**, not the **mGal** the function's own docstring
names for both `observed_g` and the return value:

{% hint style="warning" %}
**`gravity_anomaly_bouguer`'s internal units don't match its documented ones.** Feeding it a
correctly-scaled real observed gravity reading in mGal (real sea-level gravity at 45°N is about
`980,619.9` mGal) produces `979,639.28` mGal back — nowhere near the ±100 mGal range a real
Bouguer anomaly falls in — because the function's own `g_th` term comes out ~1000x too small to
cancel `observed_g` against. The free-air and Bouguer plate terms *are* correctly scaled in mGal
(`0.3086` mGal/m and `0.04191 * ρ * h` mGal both check out against the standard constants); only
the theoretical-gravity term is off by the stated factor of 1000. Verified by hand: `g_th` at 45°
computes to `980.62` (Gal-scale), not `980,619.9` (mGal-scale).
{% endhint %}

**Magnetic inclination returns a tangent, not an angle.** `magnetic_inclination(bz, bh)` returns
`bz / bh` — the tangent of the dip angle, exactly as its own docstring says ("Tangent of
inclination angle (dimensionless)") — not the angle itself in degrees:

```python
runtime.execute("geophysics", "magnetic_inclination", [40000.0, 20000.0])["result"]
# 2.0 -- tan(I); the angle itself is atan(2.0) = 63.43 degrees, a separate conversion the caller
#        has to do
```

It returns the sentinel `1e9` rather than dividing by zero when `bh == 0.0` (a purely vertical
field, as at a magnetic pole).

## `seismology`: magnitude, moment, energy, and travel time

`moment_magnitude` (`Mw = (2/3)·log10(M0) − 10.7`) and its inverse `seismic_moment`
(`M0 = 10^(1.5·Mw + 16.05)`) are the Hanks & Kanamori (1979) moment-magnitude relation, with `M0`
in **dyne-cm** (the constants `-10.7`/`+16.05` are the classic CGS-unit form of the formula, not
the SI/N·m form, which uses `-6.07`/`+9.1`). The two are exact inverses of each other:

```python
runtime.execute("seismology", "seismic_moment", [9.0])["result"]
# 3.5481338923357605e+29 -- dyne-cm

runtime.execute("seismology", "moment_magnitude", [3.5481338923357605e+29])["result"]
# 9.0 -- round-trips exactly

# The 2011 Tohoku earthquake's published M0, ~3.9e29 dyne-cm, plugged straight in:
runtime.execute("seismology", "moment_magnitude", [3.9e29])["result"]
# 9.027376404684333 -- matches the widely reported Mw 9.0-9.1
```

`energy_from_magnitude` (`E = 10^(1.5·Mw + 4.8)`) is the companion Gutenberg-Richter
energy-magnitude relation, with `E` genuinely in joules this time (the `4.8` constant is exactly
`11.8` in the ergs form of the same relation, minus `7` for the erg→joule unit shift) — see the
worked Mw 9.0 example in the opening code block above.

**The ts-tp method has no guard against a physically backwards input.**
`epicenter_distance_from_ts_tp(delta_t, vp, vs)` divides by `(1/vs - 1/vp)`, which is only
positive when `vp > vs` — true for every real rock, since P-waves always outrun S-waves. The
module's own generated test calls it with `vp=3.5`, `vs=6.0` (S faster than P, backwards), which
independently reproduces as a negative "distance":

```python
runtime.execute("seismology", "epicenter_distance_from_ts_tp", [2.0, 3.5, 6.0])["result"]
# -16.8 -- a negative epicentral distance; vp < vs was passed, which is unphysical
```

With `vp` and `vs` the right way around it behaves as documented and round-trips against
`ts_tp_difference`:

```python
dt = runtime.execute("seismology", "ts_tp_difference", [300.0, 6.5, 3.7])["result"]
dt
# 34.92723492723491 -- seconds, for a 300 km path

runtime.execute("seismology", "epicenter_distance_from_ts_tp", [dt, 6.5, 3.7])["result"]
# 300.0 -- exact round trip
```

The function does guard the genuinely-unrepresentable cases: it returns `0.0` rather than an
`inf`/`nan` when `vs == vp` (zero denominator) or when either input already carries a `NaN`.

## `volcanology`: simplified, and explicit that it is

Every formula in this module is labeled "simplified" in its own docstring, and the numbers bear
that out — some land close to published order-of-magnitude figures, some do not, and the module
makes no claim either way:

- `eruption_column_height` (`H = 0.25 · Q^0.25` km, `Q` in kg/s) uses almost exactly the
  coefficient (`~0.236`) of the commonly cited Morton-plume-based empirical relation in the
  volcanic-plumes literature. At `Q = 1e8` kg/s (roughly Pinatubo 1991's peak mass eruption rate),
  it returns `25.0` km — the right order of magnitude for that eruption's ~35 km observed column.
- `caldera_collapse_volume` (`V = π·(d/2)²·depth`) at `d = 8` km, `depth = 1` km — roughly Crater
  Lake/Mount Mazama's dimensions — returns `50.27` km³, in the same range as published estimates of
  Mazama's collapse volume.
- `vei_energy_estimate` (`E = 10^(VEI + 7)` J) returns `1e12` J for VEI 5 — several orders of
  magnitude below published total-energy estimates for a VEI-5 eruption like the 1980 Mount St.
  Helens event (~`1e18` J), which the docstring's "simplified" label already concedes.

```python
runtime.execute("volcanology", "eruption_column_height", [1.0e8, 9.81])["result"]
# 25.0 -- km

runtime.execute("volcanology", "caldera_collapse_volume", [8.0, 1.0])["result"]
# 50.26548245743669 -- km cubed

runtime.execute("volcanology", "magma_viscosity_estimate", [50.0])["result"]
# 10.0 -- Pa.s, for basaltic (50% SiO2) magma
runtime.execute("volcanology", "magma_viscosity_estimate", [70.0])["result"]
# 1000.0 -- Pa.s, for rhyolitic (70% SiO2) magma -- real rhyolite runs several
# orders of magnitude higher (10^6-10^12 Pa.s); the formula's own docstring calls
# it "highly simplified" for exactly this reason
```

`alert_level(seismicity, deformation, gas_emission)` is just `max()` of its three arguments on a
0-4 scale — there is no weighting or combination logic, so a single indicator spiking to 4 drives
the whole alert level to 4 regardless of the other two.

## Verification

All four `mojo/tests/libs/test_{geodesy,geophysics,seismology,volcanology}.mojo` files are the
same auto-generated coverage-smoke pattern used across this corpus: every function is called once
on a shared, arbitrary `0.5`-valued fixture and the test only checks that a scalar result is
finite (`is_finite`) or a list/struct result is non-empty — none of the four pin a specific
expected number. The one exception is `test_seismology.mojo`'s call to
`epicenter_distance_from_ts_tp(2.0, 3.5, 6.0)`, whose non-`0.5` arguments exist only to dodge the
function's own zero-denominator guard (`vp == vs`), not to pin a real physical scenario — as shown
above, those particular values happen to produce the unphysical `vp < vs` case.

Every worked number in this page — the NYC-London distance trio, the cross-track/along-track
navigation example, the geodetic/ECEF round trip, the Vp/Vs/Poisson's-ratio triple, the Tohoku and
round-trip moment-magnitude checks, the ts-tp round trip, and the eruption/caldera figures — was
independently re-derived from the formulas in `mojo/engine/geodesy.mojo`, `geophysics.mojo`,
`seismology.mojo`, and `volcanology.mojo` using a standalone Python script (plain `math`, no
library implementing any of these formulas), not lifted from a test file or asserted from memory.

**Next:** [Geospatial indexing & joins](geospatial.md) covers a separate, unrelated coordinate-frame
and distance-metric package built for spatial indexing rather than survey physics; see the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
