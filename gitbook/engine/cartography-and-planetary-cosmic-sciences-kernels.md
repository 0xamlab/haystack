---
icon: satellite
description: Map-scale and projection arithmetic for cartography, Julian-date and orbital-mechanics formulas for astronomy, Hubble-law cosmology and blackbody radiation laws, and habitability/biosignature scoring for astrobiology.
---

# Cartography and planetary & cosmic sciences kernels

Four independent kernel modules for measuring things at four very different scales. **Cartography**
turns a ground distance into a map coordinate and back — scale factors, UTM zones, the Mercator and
equirectangular projections, great-circle distance. **Astronomy** places an object in time and on the
sky — Julian dates, sidereal time, solar declination and day length, Kepler's equation, apparent
magnitude, ecliptic-to-equatorial conversion. **Cosmology** describes the universe at the largest
scale — Hubble-law kinematics, redshift and the three cosmological distance measures, critical
density, and the two blackbody-radiation laws (Stefan-Boltzmann, Wien) that apply equally to a star,
a planet, or the cosmic microwave background. **Astrobiology** turns those same stellar and planetary
quantities into habitability numbers — the classical habitable-zone limits, planetary equilibrium
temperature, water activity, radiation dose rate, and spore-survival fractions for panspermia.

None of the four modules import each other, import Python, or share a struct. Every function takes
plain `Float64` scalars (`latitude_to_utm_zone` and `day_length`'s `day_of_year` are the only two
`Int` arguments in the family) and returns either a single `Float64`/`Int` or, for
`ecliptic_to_equatorial`, a two-element `List[Float64]`.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Great-circle distance, New York to London, on a spherical Earth (radius 6371 km).
# Latitudes/longitudes are in radians: 40.7128N/-74.0060E and 51.5074N/-0.1278E.
runtime.execute("cartography", "great_circle_distance",
                [0.710572, -1.291648, 0.898974, -0.002231, 6371.0])["result"]
# 5570.22 -- km, matches the commonly cited ~5570 km air distance

# The Sun's conservative habitable zone, Kasting et al. (1993) scaling.
runtime.execute("astrobiology", "habitable_zone_inner", [1.0])["result"]
# 0.9534625892455924 -- AU
runtime.execute("astrobiology", "habitable_zone_outer", [1.0])["result"]
# 1.6666666666666667 -- AU
```

## The modules

| Module | What it does |
| --- | --- |
| `cartography` | map scale (scale factor, representative fraction, ground/map distance conversion), the Mercator and equirectangular projections, UTM zone lookup, great-circle distance, contour-interval suggestion, and magnetic-declination correction |
| `astronomy` | Julian and modified Julian date, Greenwich sidereal time, solar declination and day length, parallax, Kepler's equation (solved by Newton's method), Kepler's third law, apparent/absolute magnitude conversion, and ecliptic-to-equatorial coordinate transform |
| `cosmology` | Hubble-law velocity/distance, approximate lookback time and comoving distance, luminosity and angular-diameter distance, redshift from wavelength shift, cosmic scale factor, critical density, Schwarzschild radius, and the Stefan-Boltzmann and Wien blackbody laws |
| `astrobiology` | habitable-zone inner/outer edges, stellar luminosity from radius and temperature, planetary equilibrium temperature, water activity, radiation dose rate, Q10 metabolic temperature scaling, piezophile pressure-tolerance depth, UV penetration depth, and panspermia spore-survival fraction |

## Cartography: scale is a ratio, projection is a formula

`cartography`'s scale functions are exact inverses of each other by construction —
`scale_factor(map_distance, ground_distance)` returns `map/ground`, `representative_fraction`
returns the same ratio inverted (`ground/map`, the denominator you'd write after "1:"), and
`ground_distance_from_map`/`map_distance_from_ground` convert a measured distance in either
direction through a `scale_denominator`:

```python
# A 1 cm map distance at 1:24,000 (the standard USGS 7.5-minute quadrangle scale).
runtime.execute("cartography", "representative_fraction", [1.0, 24000.0])["result"]
# 24000.0
runtime.execute("cartography", "ground_distance_from_map", [1.0, 24000.0])["result"]
# 24000.0 -- 1 cm on the map is 24,000 cm (240 m) on the ground
runtime.execute("cartography", "map_area_at_scale", [1e6, 24000.0])["result"]
# 0.0017361111111111111 -- a 1 km2 real area is 0.00174 m2 (17.4 cm2) on the map
```

`latitude_to_utm_zone` implements `floor((longitude + 180) / 6) + 1` and reproduces the real UTM
grid: New York's longitude (-74.0060°) lands in zone 18, London's (-0.1278°) in zone 30, and the
boundary cases are exact — a longitude of exactly `0.0` is zone 31 (the zone starts *at* the
meridian), and `-180.0` is zone 1:

```python
runtime.execute("cartography", "latitude_to_utm_zone", [-74.0060])["result"]  # 18 -- New York
runtime.execute("cartography", "latitude_to_utm_zone", [-0.1278])["result"]   # 30 -- London
runtime.execute("cartography", "latitude_to_utm_zone", [0.0])["result"]       # 31
runtime.execute("cartography", "latitude_to_utm_zone", [-180.0])["result"]    # 1
```

The name `latitude_to_utm_zone` is misleading: the parameter and the arithmetic are both
longitude — UTM zones are 6°-wide longitude bands, and latitude plays no part in which zone a point
falls in (it only affects the north/south hemisphere letter, which this function does not return).

`mercator_y` computes `ln(tan(π/4 + lat/2))`, the standard Mercator y-coordinate, and reproduces
the projection's signature property — vertical distortion that explodes toward the poles:

```python
runtime.execute("cartography", "mercator_y", [0.0])["result"]                    # ~0.0 -- equator
runtime.execute("cartography", "mercator_y", [0.7853981633974483])["result"]     # 0.8814 -- 45N
runtime.execute("cartography", "mercator_y", [1.5690509975429023])["result"]     # 7.044 -- 89.9N
```

At exactly ±90° the function does not refuse or return infinity: `cos(π/4 + lat/2)` at the north
pole is `~6.12e-17`, not exactly zero, so the guard (`fabs(c) < 1e-30`) never fires and the function
returns a large but finite number (`37.33` at exactly 90°) instead of a value flagged as undefined.
At exactly the *south* pole the arithmetic works out differently: `t = sin(0)/cos(0) = 0`, which
trips the separate `t <= 0.0` guard and returns `0.0` — a real ground coordinate, not "no answer."
Callers projecting data anywhere near the poles should clamp latitude well short of ±90° themselves;
the function's own epsilon does not catch the case it looks like it should.

`declination_correction(bearing, declination)` is a single addition (`true = magnetic + declination`)
with no range normalization: `declination_correction(350.0, 20.0)` returns `370.0`, not `10.0`, and
`declination_correction(10.0, -20.0)` returns `-10.0`, not `350.0`. A caller that needs a bearing in
`[0, 360)` has to reduce it themselves (`result % 360.0`, adding `360.0` first if the input can be
negative).

## Astronomy: dates, orbits, and the sky

`julian_date(year, month, day)` implements the standard Meeus algorithm, but its `day` parameter is
an `Int`, not the fractional day Julian dates are usually defined against — so the function always
computes the Julian date at **0h UT**, not the noon convention most tables use:

```python
runtime.execute("astronomy", "julian_date", [2000, 1, 1])["result"]
# 2451544.5 -- half a day before the canonical J2000.0 epoch (JD 2451545.0, at 2000-01-01 12:00 UT)
```

The commonly cited J2000.0 epoch, `JD 2451545.0`, is noon on that date; this function can only
return the midnight value that precedes it, `2451544.5`. Any caller matching this function's output
against a published Julian date needs to add `0.5` (or the fraction of a day since 0h) to align the
conventions.

`sidereal_time(jd, longitude)` computes Greenwich Mean Sidereal Time from the same Meeus polynomial
used in `julian_date`'s era, and at the J2000.0 epoch itself matches the standard published
reference value:

```python
runtime.execute("astronomy", "sidereal_time", [2451545.0, 0.0])["result"]
# 18.697374558 -- hours; published GMST at J2000.0 is 18h 41m 50.54s = 18.6974h
```

`kepler_equation(M, e, tol=1e-10)` solves `M = E - e*sin(E)` for the eccentric anomaly `E` by
Newton's method, starting from `E = M` and iterating up to 100 times. It converges in single-digit
iterations even at high eccentricity:

| `e` | `E` (radians, `M = 1.0`) | Newton iterations to `tol=1e-10` |
| --- | --- | --- |
| 0.0167 (Earth-like) | 1.0141790871647136 | 3 |
| 0.5 | 1.4987011335178484 | 5 |
| 0.9 | 1.8620866868745323 | 6 |
| 0.99 | 1.927635550695835 | 6 |

There is no convergence check on the return value: if 100 iterations pass without `|dE| < tol`, the
function returns whatever `E` the last iteration produced, with no status flag distinguishing a
converged answer from a stalled one. For every eccentricity in the table above (including `0.99`)
that never actually happens — Newton's method on Kepler's equation converges quadratically once it
is close, and it gets close fast — but a caller feeding in a near-parabolic `e` approaching `1.0`
has no signal from the return value alone that convergence held.

`orbital_period(semi_major_au)` is Kepler's third law, `T = a^1.5` years, and reproduces the solar
system's actual periods from actual semi-major axes:

```python
runtime.execute("astronomy", "orbital_period", [1.0])["result"]    # 1.0 -- Earth, by definition
runtime.execute("astronomy", "orbital_period", [5.2])["result"]    # 11.857824421031035 -- Jupiter (actual: 11.86 yr)
runtime.execute("astronomy", "orbital_period", [9.58])["result"]   # 29.651608927678783 -- Saturn (actual: 29.4 yr)
```

`sunrise_hour_angle` handles the two polar cases explicitly rather than letting `acos` fail on an
out-of-domain argument: when `-tan(lat)*tan(dec) > 1.0` (polar night — the sun never rises) it
returns a `0°` hour angle, and when it's `< -1.0` (midnight sun — the sun never sets) it returns
`180°`. `day_length` inherits both sentinels through `2 * hour_angle / 15`:

```python
runtime.execute("astronomy", "day_length", [40.7128, 172])["result"]   # 14.922 -- NYC, ~June solstice
runtime.execute("astronomy", "day_length", [40.7128, 355])["result"]   # 9.078 -- NYC, ~December solstice
runtime.execute("astronomy", "day_length", [80.0, 355])["result"]      # 0.0 -- polar night at 80N in December
```

`parallax_correction(distance_au, radius_earth)` reproduces the textbook solar parallax almost
exactly:

```python
runtime.execute("astronomy", "parallax_correction", [1.0, 6.371e6])["result"]
# 8.784186597593584 -- arcseconds; the published Earth equatorial horizontal parallax at 1 AU is 8.794"
```

`ecliptic_to_equatorial(ecliptic_lon, ecliptic_lat, obliquity)` correctly reproduces the geometric
identity at the solstice point — at ecliptic longitude 90° on the ecliptic plane (`lat = 0`), right
ascension is also 90° and declination equals the obliquity itself:

```python
runtime.execute("astronomy", "ecliptic_to_equatorial", [90.0, 0.0, 23.4393])["result"]
# [90.0, 23.439300000000006] -- RA, Dec in degrees
```

## Cosmology: Hubble's law, distance measures, and two blackbody laws

Every cosmological distance function in this module is a small-`z`, matter-free approximation, not
a full Friedmann-equation integration — `comoving_distance_approx` is literally `c*z/H0`, valid only
where `z` is small enough that the universe's expansion history doesn't matter yet:

```python
c_km_s = 299792.458
runtime.execute("cosmology", "comoving_distance_approx", [0.01, c_km_s, 70.0])["result"]
# 42.827494 -- Mpc, at H0 = 70 km/s/Mpc
runtime.execute("cosmology", "luminosity_distance", [42.827494, 0.01])["result"]
# 43.25576894 -- d_L = d_c * (1+z)
runtime.execute("cosmology", "angular_diameter_distance", [42.827494, 0.01])["result"]
# 42.403459405940595 -- d_A = d_c / (1+z)
```

`cosmic_scale_factor(z) = 1/(1+z)` reproduces the standard cosmological facts: the universe was half
its current size at `z = 1`, and the value at the cosmic microwave background's redshift (`z ≈
1089`) matches the commonly cited "the universe was about 1/1090th its current size" figure:

```python
runtime.execute("cosmology", "cosmic_scale_factor", [1.0])["result"]     # 0.5
runtime.execute("cosmology", "cosmic_scale_factor", [1089.0])["result"]  # 0.0009174311926605505
```

`critical_density(h0)` reproduces the textbook value for `H0 = 70` km/s/Mpc:

```python
runtime.execute("cosmology", "critical_density", [70.0])["result"]
# 9.204153899036247e-27 -- kg/m3; commonly cited value at H0~70 is ~9.2e-27 kg/m3
```

`schwarzschild_radius(mass)` reproduces real, independently-known values for the Sun and Earth to
within the precision of the constants used (`G = 6.674e-11`, `c = 3.0e8` — note `c` is rounded to
one significant figure past `3`, not the exact `2.998e8`, so results carry that rounding):

```python
runtime.execute("cosmology", "schwarzschild_radius", [1.989e30])["result"]
# 2949.9079999999994 -- m; the Sun's actual Schwarzschild radius is ~2953 m
runtime.execute("cosmology", "schwarzschild_radius", [5.972e24])["result"]
# 0.008857139555555556 -- m; Earth's actual Schwarzschild radius is ~8.87mm
```

`stefan_boltzmann_luminosity` and `wien_peak_wavelength` are the two blackbody-radiation laws, and
both reproduce the Sun's real properties from its real radius and temperature:

```python
runtime.execute("cosmology", "stefan_boltzmann_luminosity", [6.957e8, 5778.0])["result"]
# 3.843932540746749e+26 -- W; the Sun's actual luminosity is 3.828e26 W
runtime.execute("cosmology", "wien_peak_wavelength", [5778.0])["result"]
# 5.015181645898235e-07 -- m (501.5 nm), close to the Sun's actual visible-green peak, ~502 nm
```

The same Wien's-law function, given the cosmic microwave background's temperature, reproduces the
CMB's well-known peak wavelength:

```python
runtime.execute("cosmology", "wien_peak_wavelength", [2.725])["result"]
# 0.001063402552293578 -- m (1.063 mm), matching the CMB's commonly cited ~1.06mm peak wavelength
```

## Astrobiology: habitability from stellar and planetary numbers

`habitable_zone_inner`/`habitable_zone_outer` implement the classical, temperature-independent
Kasting et al. (1993) scaling (`r = sqrt(L/1.1)` and `sqrt(L/0.36)` AU) rather than the more recent
Kopparapu et al. stellar-temperature-dependent polynomial fits, and for the Sun reproduce the
commonly cited conservative habitable-zone bounds almost exactly:

```python
runtime.execute("astrobiology", "habitable_zone_inner", [1.0])["result"]  # 0.9534625892455924 -- AU
runtime.execute("astrobiology", "habitable_zone_outer", [1.0])["result"]  # 1.6666666666666667 -- AU
```

(Commonly cited conservative bounds for the Sun are approximately 0.95-1.67 AU — the same scaling
this function implements.) Because the formula doesn't depend on stellar temperature at all, it will
systematically misplace the habitable zone for stars far from the Sun's spectral type — a cooler,
redder star's habitable zone actually sits closer in (proportionally) than a temperature-independent
`sqrt(L)` scaling predicts, which is exactly the correction the newer Kopparapu formulas add.

`stellar_luminosity(radius_rsun, temperature_k)` is Stefan-Boltzmann in solar units
(`(R/Rsun)^2 * (T/Tsun)^4`, `Tsun = 5778 K` fixed in the source) and, given Proxima Centauri's real
radius and temperature, lands close to its real catalogued luminosity:

```python
runtime.execute("astrobiology", "stellar_luminosity", [0.154, 3042.0])["result"]
# 0.0018220828922807474 -- Lsun; Proxima Centauri's catalogued luminosity is ~0.0017 Lsun
```

`planetary_equilibrium_temp(stellar_flux_w_m2, albedo)` reproduces Earth's real no-greenhouse
equilibrium temperature from Earth's real solar constant and Bond albedo:

```python
runtime.execute("astrobiology", "planetary_equilibrium_temp", [1361.0, 0.3])["result"]
# 254.58234278554602 -- K; Earth's commonly cited equilibrium temperature (no greenhouse) is ~255K
```

`water_activity(solute_molality, vant_hoff_factor)` is a van't Hoff approximation
(`aw = 1 - i*m*0.018`), and at seawater's approximate ionic strength lands close to seawater's
real measured water activity:

```python
runtime.execute("astrobiology", "water_activity", [0.6, 1.8])["result"]
# 0.98056 -- seawater's commonly cited water activity is ~0.98
```

`pressure_tolerance_depth(max_pressure_atm)` applies the standard rough diving/oceanographic rule
of thumb (10 m of seawater ≈ 1 additional atmosphere) to a piezophile's pressure tolerance. Applied
to a pressure near what's measured at the Challenger Deep (Mariana Trench, the deepest known point
in the ocean, home to documented piezophilic microbes), it lands close to the trench's real depth:

```python
runtime.execute("astrobiology", "pressure_tolerance_depth", [1086.0])["result"]
# 10850.0 -- m; the Challenger Deep's actual depth is ~10,935m at ~1,086 atm
```

The small gap (10,850m vs. the real ~10,935m) is the linear rule's own known limitation: seawater
is slightly compressible and its density increases with depth, so the true pressure-depth curve is
not perfectly linear at trench depths — the 10 m/atm rule is a standard approximation, not an exact
conversion.

{% hint style="warning" %}
**`radiation_dose_rate` is a coarse proportionality, not a validated dosimetry model.** Its formula
is `flux * energy_MeV * LET * 86400 * 1e-3` — dose rate scales linearly with each input, which is
directionally correct physics, but plugging in literature-typical galactic-cosmic-ray values (flux
around 4 particles/cm2/s, energy around 100 MeV, LET around 0.2 MeV/cm — the exact figure the
source's own docstring suggests) produces a result several orders of magnitude larger than the
~0.67 mGy/day actually measured at the Martian surface by the Curiosity rover's RAD instrument. Use
this function to compare doses *relatively* across different flux/energy/LET inputs, not as a
substitute for a real particle-transport dosimetry calculation.
{% endhint %}

`metabolism_rate_q10` and `panspermia_survival_fraction` are both textbook first-order kinetics —
`rate_ref * Q10^((T-Tref)/10)` and `exp(-k*t)` respectively — and behave exactly as those equations
predict: a Q10 of 2 doubles the rate for every 10-degree increase
(`metabolism_rate_q10(1.0, 30, 20, 2.0) == 2.0`), and a six-month interplanetary transit at an
inactivation rate of 2/year leaves `exp(-2*0.5) ≈ 0.368` of an inoculum still viable.

## Verification

All four test files behind this page (`mojo/tests/libs/test_cartography.mojo`,
`test_astronomy.mojo`, `test_cosmology.mojo`, and `test_astrobiology.mojo`) are auto-generated
coverage smoke tests: each calls every function once on a shared, arbitrary fixture (mostly `0.5`
for `Float64` arguments) and checks only that the result is finite — none of them pin a specific
expected numeric output. Every number presented above as a real-world match (New York-London
distance, UTM zones, J2000.0 sidereal time, planetary orbital periods, the Sun's and Earth's
Schwarzschild radii, the Sun's and CMB's Wien peak wavelengths, the Sun's conservative habitable
zone, Proxima Centauri's luminosity, Earth's equilibrium temperature, seawater's water activity, and
the Challenger Deep's pressure-derived depth) was independently computed from the real formulas in
`mojo/engine/cartography.mojo`, `astronomy.mojo`, `cosmology.mojo`, and `astrobiology.mojo` using a
standalone Python re-implementation, not lifted from either the module's own test file or asserted
without checking — every one is reproducible by re-running the same arithmetic.

**Next:** see [Geospatial indexing & joins](geospatial.md) for coordinate-frame-aware distance,
point-in-polygon, and spatial joins beyond flat scale/projection arithmetic, or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
