---
icon: clock-rotate-left
description: Radiometric dating, rock-magnetic paleolatitude, sediment-layer age modeling, and ice-sheet mass balance across four independent Earth-history kernel modules.
---

# Historical geology and paleoclimate kernels

Four small, independent modules for reconstructing what the planet was doing before anyone was
watching: `paleomagnetism` reads a rock's frozen-in magnetic inclination back into a paleolatitude
and tracks how reliably that record survived; `paleontology` turns isotope ratios into ages and
fossil counts into diversity and turnover rates; `stratigraphy` builds an age model down a
sediment column and carries the decompaction and thermal-maturity corrections that model depends
on; `glaciology` is ice-sheet and glacier physics — mass balance, flow, calving, and the
sea-level-equivalent of a given mass of ice. None import Python, none import each other, and each
carries its own copy of the radiometric decay-age formula rather than sharing one.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# The modern accepted 14C decay constant, lambda = ln(2) / 5730 yr =~ 1.21e-4 / yr.
# Half the original activity remaining should recover the half-life itself.
runtime.execute("paleontology", "radiocarbon_age", [0.5, 1.21e-4])["result"]
# 5728.489095536738 -- yr BP, matching ln(2) / 1.21e-4 to the last digit

# A 45 degree magnetic inclination, run through the dipole formula tan(I) = 2 tan(lambda).
runtime.execute("paleomagnetism", "paleolatitude", [45.0])["result"]
# 26.545482811926583 -- degrees; see "A polynomial trig core" below for why this
# isn't exactly atan(0.5) = 26.565...
```

## The modules

| Module | What it does |
| --- | --- |
| `paleomagnetism` | rock-magnetic paleolatitude and paleointensity: virtual geomagnetic pole latitude, relative paleointensity, declination correction, reversal frequency, and Thellier-style paleointensity QC (Koenigsberger ratio, alteration check, ARM efficiency, coercivity spectrum median) |
| `paleontology` | radiometric ages (¹⁴C, K-Ar, U-Pb), fossil-record statistics (Margalef diversity, extinction/origination/turnover rate), mammalian body-mass allometry from femur length, molecular-clock phylogenetic distance, and skeletal completeness |
| `stratigraphy` | building an age-depth model down a rock column: sedimentation rate, age from depth, generic radiometric age, a hardcoded-constant ¹⁴C age, unconformity gaps, decompaction, vitrinite-reflectance thermal maturity, and a benthic-δ¹⁸O sea-level proxy |
| `glaciology` | ice-sheet and glacier physics: mass balance, Glen's-flow-law internal velocity, basal shear stress, positive-degree-day ablation, Nye's-formula thickness-from-slope, snow water equivalent, ELA from accumulation-area ratio, calving flux, sea-level equivalent of an ice mass, and ice-albedo radiative feedback |

{% hint style="info" %}
**The ice-core paleoclimate proxy lives in `stratigraphy`, not `glaciology`.** The one function in
this family that turns an isotopic paleoclimate record into a number — `sea_level_proxy`, which
converts a benthic δ¹⁸O value into a relative sea-level change the same way marine-sediment
stacks (and, by the same logic, ice-core δ¹⁸O records) are read as an ice-volume proxy — is a
`stratigraphy` function. `glaciology` itself is entirely forward ice-sheet *physics*: mass
balance, flow, calving, thickness. It has no function that ingests an isotope ratio, a core depth,
or any other paleoclimate proxy measurement. If you came here expecting an ice-core deconvolution
routine inside `glaciology`, it is `stratigraphy.sea_level_proxy` you want.
{% endhint %}

## A polynomial trig core, accurate near the equator, degrading toward the poles

`paleomagnetism.paleolatitude` and `paleomagnetism.virtual_geomagnetic_pole_lat` both implement
the standard paleomagnetic dipole formula tan(I) = 2·tan(λ) — they are the same computation
(`paleolatitude` adds a `1e-15` guard against a divide-by-zero at I = 90°, `virtual_geomagnetic_pole_lat`
does not, but both round-trip through the same three helpers). What is unusual is *how* the trig
is computed: `sin_approx`, `cos_approx`, and `atan_approx` are hand-written truncated Taylor
series, not calls into `std.math`'s real `sin`/`cos`/`atan` — `paleomagnetism.mojo` imports `cos`
from `std.math` but never calls it; every angle in this module goes through the polynomial
instead.

That approximation is excellent near the equator and gets measurably worse toward the poles,
because a 4-term Taylor series for sine/cosine and a 4-term series for arctangent are both
truncations that only converge quickly for small arguments:

```python
runtime.execute("paleomagnetism", "paleolatitude", [45.0])["result"]
# 26.545482811926583 -- true atan(0.5*tan(45deg)) = 26.56505117707799; error 0.02 deg

runtime.execute("paleomagnetism", "paleolatitude", [60.0])["result"]
# 39.74260591227982 -- true value 40.8933946491309; error 1.15 deg

runtime.execute("paleomagnetism", "paleolatitude", [90.0])["result"]
# 87.72323259046082 -- true value 90.0; error 2.28 deg
```

Each of the three errors was checked independently in plain Python against `math.sin`, `math.cos`
and `math.atan`. The dominant term is `atan_approx` itself: its 4-term series is a poor
approximation right at its own domain boundary, `x = 1.0` (where it hands off to the `π/2 -
atan(1/x)` reflection for `x > 1.0` but takes the raw series at exactly `x = 1.0`), and `tan_lambda
== 1.0` happens exactly when the input inclination is `atan(2) ≈ 63.43°` — a genuinely reachable
paleomagnetic inclination, not an edge case a caller can dismiss as unrealistic. For a
mid-latitude sample (inclination well under ~50°) the error stays under a few hundredths of a
degree; for a sample recording a steep, near-polar field the returned paleolatitude should be
treated as approximate to roughly a degree or two, not as many decimal places as the float
suggests.

## Two radiocarbon-age functions with different signatures, and two sedimentation rates with different guards

`paleontology.radiocarbon_age(ratio, lambda_c14)` and `stratigraphy.radiocarbon_age(activity_fraction)`
share a name and compute the same underlying physics — age = -ln(fraction remaining) / decay
constant — but not the same call shape. `paleontology`'s version takes the decay constant as an
explicit argument; `stratigraphy`'s bakes in a fixed constant (`-8267.0 * ln(F14C)`, where 8267 is
the ¹⁴C mean-life `T½ / ln(2)` for the modern accepted 5730-year half-life, not the older
5568-year Libby half-life) and only takes the activity fraction:

```python
runtime.execute("paleontology", "radiocarbon_age", [0.5, 1.21e-4])["result"]
# 5728.489095536738 -- explicit lambda = 1.21e-4/yr (the accepted ln(2)/5730 constant)

runtime.execute("stratigraphy", "radiocarbon_age", [0.5])["result"]
# 5730.247741689068 -- the module's own hardcoded 8267 mean-life constant; the ~1.76
#                       year gap from the call above is pure rounding, not a different
#                       half-life: 1/8267 = 1.20956e-4, which the paleontology docstring
#                       rounds to the "1.21e-4" used as the explicit lambda above
```

`stratigraphy.radiocarbon_age` also refuses `activity_fraction <= 0.0` or `> 1.0` (returning
`0.0`); `paleontology.radiocarbon_age` has no such guard and will hand `-log(ratio)` a negative or
zero argument without complaint, which for `ratio <= 0.0` is a real `NaN`/`inf`, not a caught
error.

The same split shows up in `sedimentation_rate`, defined once in each module: `stratigraphy`'s
guards `duration_my <= 0.0` and returns `0.0`; `paleontology`'s divides `thickness / time` with no
guard at all, so a caller passing `time = 0.0` gets a raw `inf`, not a refusal.

## The parent/daughter age formula appears three times

`paleontology.potassium_argon_age`, `paleontology.uranium_lead_age`, and
`stratigraphy.radiometric_age` are three call sites for the identical isotope-system-independent
formula, t = ln(1 + R) / λ, where R is the daughter/parent ratio and λ the system's decay constant
— only the constant and the argument name change:

```python
# K-Ar: lambda_k = 5.543e-10 / yr (K-40 total decay constant)
runtime.execute("paleontology", "potassium_argon_age", [0.01, 5.543e-10])["result"]
# 17951165.16898447 -- ~17.95 Myr

# U-Pb: lambda_u = 1.55125e-10 / yr (U-238 decay constant)
runtime.execute("paleontology", "uranium_lead_age", [0.15, 1.55125e-10])["result"]
# 900963367.446631 -- ~901.0 Myr

# stratigraphy's generic version, same ratio and constant as the U-Pb call above
runtime.execute("stratigraphy", "radiometric_age", [0.15, 1.55125e-10])["result"]
# 900963367.446631 -- identical result; same formula, different module, different name
```

`stratigraphy.radiometric_age` additionally refuses `decay_constant <= 0.0` or a negative ratio
(returns `0.0`); neither `potassium_argon_age` nor `uranium_lead_age` in `paleontology` carries
that guard.

## A stratigraphic column, decompacted and dated

`stratigraphy`'s functions compose the way an actual stratigraphic column is worked through by
hand — thickness in, age out, correcting for burial along the way:

```python
# 500 m below a surface dated at 2.0 Ma, at a steady 50 m/Myr sedimentation rate
runtime.execute("stratigraphy", "age_from_depth", [500.0, 2.0, 50.0])["result"]
# 12.0 -- Ma

# A 50 m compacted sand that started at 60% porosity and now sits at 20%
runtime.execute("stratigraphy", "compaction_correction", [50.0, 0.6, 0.2])["result"]
# 100.0 -- the original depositional thickness was twice the present compacted one

# delta-13C-style fractionation: sample ratio 1.000 against a standard of 1.002
runtime.execute("stratigraphy", "isotope_fractionation", [1.0, 1.002])["result"]
# -1.9960079840319889 -- per mille, the standard (R_sample/R_standard - 1) x 1000 notation
```

`compaction_correction`'s formula (`T_obs · (1 - φ_current) / (1 - φ_initial)`) is the standard
Athy-style decompaction used to reconstruct a bed's original thickness before burial squeezed the
pore space out of it; it refuses only the degenerate case `initial_porosity >= 1.0` (division by a
non-positive denominator), returning the observed thickness unchanged rather than a division
result.

`thermal_maturity_vitrinite` is the one function in this family whose formula is explicitly
labeled an approximation in its own docstring ("approximate Barker 1988"): `Ro ≈ exp(0.0078·T_max
- 1.2) · (1 + 0.01·ln(duration_my + 1))`, floored at `Ro = 0.2`. At 100°C peak burial temperature
sustained 10 Myr it returns `Ro = 0.6728021...` percent, squarely inside the 0.5–1.3% range
petroleum geologists call the oil window — a sanity check against the literature, not a pinned
test value.

## Ice-sheet physics, chained the way a real ice-flow estimate is chained

`glaciology`'s functions are pure forward mechanics — no fitting, no proxy inversion — and the two
that model ice flow compose directly, driving stress into deformation velocity:

```python
# 300 m of ice on a 0.02 rad (~1.15 deg) surface slope
tau = runtime.execute("glaciology", "basal_shear_stress", [300.0, 0.02])["result"]
tau
# 53971.02176396548 -- Pa (rho_ice=917 kg/m3, g=9.81 m/s2)

# Glen's flow law, n=3, with a rate factor A=1e-25 Pa^-3 s^-1
runtime.execute("glaciology", "ice_velocity_internal", [1e-25, tau, 3.0, 300.0])["result"]
# 2.358159516066276e-09 -- m/s, ~0.074 m/yr of internal deformational flow
```

`sea_level_equivalent` converts an ice mass directly into meters of sea-level rise, which is
straightforward enough to check against a real published number — the Greenland ice sheet's total
mass is commonly cited near 2.9 × 10¹⁸ kg with a sea-level-rise potential near 7.4 m:

```python
runtime.execute("glaciology", "sea_level_equivalent", [2.9e18, 3.61e14])["result"]
# 7.814436767733382 -- meters, using the real global ocean area (~3.61e14 m^2) and
#                       rho_ocean=1028 kg/m3; in the right ballpark of the cited 7.4 m
#                       (the published figure nets out land-elevation and gravitational
#                       effects this simple mass/(area*density) formula doesn't model)
```

## Refusal behavior

The four modules do not share a refusal convention — each function guards (or doesn't) on its own
terms:

- **`paleomagnetism`** returns `0.0` from every ratio-type function whenever its denominator input
  is non-positive: `geomagnetic_intensity` (susceptibility ≤ 0), `magnetic_reversal_rate` (timespan
  ≤ 0), `koenigsberger_ratio` (induced magnetization ≤ 0), `stability_index` (NRM before ≤ 0),
  `rock_magnetic_susceptibility` (mass ≤ 0), and `anhysteretic_remanence` (bias field ≤ 0).
- **`paleontology`** is the least guarded of the four: `sedimentation_rate`, `extinction_rate`,
  `origination_rate`, and `turnover_rate` all divide with no zero-check. `fossil_diversity_index`
  is the exception — it refuses `n_specimens <= 0.0` or `== 1.0` and also checks its own result for
  NaN (`d - d != 0.0`) before returning it, rather than trusting the guard above to have caught
  every degenerate case.
- **`stratigraphy`** guards the most consistently: `sedimentation_rate`, `radiometric_age`,
  `radiocarbon_age`, `compaction_correction`, and `isotope_fractionation` all return a defined
  fallback (`0.0`, or the input unchanged) rather than propagating an `inf`/`NaN` or dividing by a
  non-positive quantity. `unconformity_gap` clamps a negative gap (strata "younger below older") to
  `0.0` instead of returning a nonsensical negative hiatus.
- **`glaciology`** guards every function that would otherwise take a negative physical quantity
  (thickness, velocity, width, degree-days) and return it unchanged: `ablation_degree_day`,
  `calving_flux`, and `snow_water_equivalent` all return `0.0` given a negative input rather than
  propagating a negative melt or flux. `ice_velocity_internal` and `ice_thickness_from_surface`
  return `0.0` given a non-positive rate factor, stress, thickness, or slope-derived denominator.

## Verification

All four `mojo/tests/libs/test_paleomagnetism.mojo`, `test_paleontology.mojo`,
`test_stratigraphy.mojo`, and `test_glaciology.mojo` files are auto-generated coverage smoke
tests: every function is called once with a shared, arbitrary fixture (`0.5`, `0.6`, `0.7`, ...)
and the suite checks only that the result is finite — none of the four pins a specific numeric
output. Every worked number in this page was instead computed independently in plain Python
against the real formulas in `mojo/engine/paleomagnetism.mojo`, `paleontology.mojo`,
`stratigraphy.mojo`, and `glaciology.mojo` (including re-deriving `sin_approx`/`cos_approx`/
`atan_approx`'s Taylor series by hand to measure their error against `math.sin`/`cos`/`atan`), then
checked for internal consistency — e.g. `radiocarbon_age(0.5, 1.21e-4)` should equal `ln(2) /
1.21e-4` exactly, and it does to the last digit.

**Next:** see [Geospatial indexing & joins](geospatial.md) for the other Earth-science kernel
family in this runtime, or browse the [Runtime library catalog](runtime-library-catalog.md) for
every module and function.
