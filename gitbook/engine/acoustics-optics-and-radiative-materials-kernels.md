---
icon: prism
description: Five independent physics-formula modules for sound and light — decibel levels and room acoustics, medical/industrial ultrasound imaging physics, blackbody and photon radiometry, fiber/optical photonics, and geometric-optics lens and reflection formulas.
---

# Acoustics, optics, and radiative materials kernels

Five small, stateless modules for the closed-form physics equations behind sound and light
measurement: decibel arithmetic and room acoustics (`acoustics`), medical and industrial
ultrasound imaging physics (`ultrasonics`), blackbody radiation and photon counting
(`radiometry`), fiber-optic and diffraction physics (`photonics`), and geometric-optics lens,
refraction and reflection formulas (`optics`). None of these are simulators — each function is a
single textbook formula (Snell's law, the Stefan-Boltzmann law, the Sabine reverberation
equation, the sonar/medical-ultrasound equations) evaluated on scalar `Float64` inputs. There is
no shared struct or engine state between them; every module reads its own docstring header as its
complete public API.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Reflection coefficient at a soft-tissue/bone interface (typical values in Rayl)
runtime.execute("ultrasonics", "reflection_coefficient", [1.63e6, 7.8e6])["result"]
# 0.4281016903027161 — roughly 43% of incident intensity reflects back toward the transducer,
# which is why bone shows up bright and casts an acoustic shadow on B-mode images

runtime.execute("optics", "thin_lens_equation", [10.0, 30.0])["result"]
# 15.0 — object at 3x the focal length forms a real image at 1.5x the focal length
```

## The modules

| Module | What it does |
| --- | --- |
| `acoustics` | Sound-pressure/intensity/power decibel levels, the inverse-square law, pipe resonance, wavelength, Doppler shift, Sabine reverberation time, and combining two decibel sources. |
| `ultrasonics` | Medical/industrial ultrasound physics: acoustic impedance and interface reflection, tissue attenuation, Doppler blood-flow shift, imaging depth/PRF trade-offs, axial/lateral resolution, and a simplified thermal safety index. |
| `radiometry` | Blackbody and photon-counting radiometry: Planck spectral radiance, Stefan-Boltzmann exitance, photon energy/flux, solid angle, Lambertian irradiance, luminous efficacy, and detector noise-equivalent power. |
| `photonics` | Fiber-optic and wave-optics formulas in **radians and meters**: Snell's law, critical/Brewster angle, Fresnel reflectance, fiber numerical aperture, photon energy, Beer-Lambert absorption, diffraction-grating and Rayleigh-resolution angles. |
| `optics` | Geometric-optics formulas in **degrees and nanometers**: Snell's law (with a total-internal-reflection guard), critical/Brewster angle, thin-lens imaging, magnification, diffraction-limited resolution in arcseconds, and objective-lens numerical aperture. |

## `photonics` and `optics` are not duplicates — they disagree on units

Both modules implement Snell's law, the critical angle, the Brewster angle, Fresnel reflectance
at normal incidence, numerical aperture, and photon energy, and five of those pairs even share a
function name. Reading `mojo/engine/photonics.mojo` and `mojo/engine/optics.mojo` side by side
shows they are two independent implementations with incompatible calling conventions, not one
formula called twice:

| Function (shared name) | `photonics` | `optics` |
| --- | --- | --- |
| Angle units | radians in, radians out | degrees in, degrees out |
| Wavelength units | meters | nanometers |
| `numerical_aperture(a, b)` | fiber NA: `sqrt(n_core² - n_clad²)` from core/cladding index | objective NA: `n·sin(half_angle_deg)` from medium index and half-angle |
| `critical_angle(n1, n2)` beyond validity (`n2 ≥ n1`) | no guard — passes `asin(n2/n1)` straight through with an out-of-domain ratio | explicit guard — returns `-1.0` |
| `snells_law*` at angles past total internal reflection | no guard — same out-of-domain `asin` exposure | explicit guard — returns `-1.0` |

Calling `photonics.numerical_aperture(1.5, 0.85)` expecting the objective-lens formula computes
`sqrt(1.5² - 0.85²) = 1.236` — a fiber NA, not the `optics.numerical_aperture(1.5, 0.85)` result of
`1.5·sin(0.85°) ≈ 0.0222`. The two modules exist because they were built for different domains
(fiber/waveguide photonics vs. classical lens design) and neither refers to the other's constants
or helpers — `photonics` uses `PLANCK = 6.626e-34` and `SPEED_OF_LIGHT = 3.0e8` as module-level
`comptime` values, `optics` redeclares the same two constants plus `EV_JOULE` independently.

{% hint style="warning" %}
**`photonics.critical_angle` and `photonics.snells_law_angle` have no domain guard.** Both compute
an `asin()` of a ratio that can legitimately exceed `1.0` in magnitude — `critical_angle(n1, n2)`
whenever `n2 ≥ n1` (there is no total internal reflection going from a less-dense to a more-dense
medium), and `snells_law_angle` whenever the incidence angle is past the critical angle for the
given index pair. `optics.critical_angle` and `optics.snells_law` both check for exactly this case
and return the sentinel `-1.0` instead. Code calling the `photonics` versions with medium indices
it does not control should check `n1 > n2` (and, for `snells_law_angle`, that the input angle is
below `photonics.critical_angle(n1, n2)`) itself before calling.
{% endhint %}

## Worked examples

Every number below was computed independently in Python from the real formulas in
`mojo/engine/acoustics.mojo`, `ultrasonics.mojo`, `radiometry.mojo`, `photonics.mojo`, and
`optics.mojo` — see [Verification](#verification) for why, and reproduce any of them with the
same formula.

**Acoustics — combining two equal noise sources.** `decibel_sum_2` adds levels in the power
domain, not linearly:

```python
runtime.execute("acoustics", "decibel_sum_2", [70.0, 70.0])["result"]
# 73.01029995663981 — two 70 dB sources combine to ~73 dB, not 140 dB;
# L = 10*log10(10^7 + 10^7) = 10*log10(2) + 70
```

`resonant_frequency_pipe_open` and `_closed` give the two ends of the same organ-pipe/HVAC-duct
problem — a 0.5 m pipe with `c = 343` m/s (speed of sound in air) resonates at `343/(2·0.5) =
343.0` Hz open at both ends, but `343/(4·0.5) = 171.5` Hz — exactly one octave lower — with one
end closed, because a closed pipe only fits a quarter-wavelength standing wave instead of a half.

**Ultrasonics — a soft-tissue/bone reflection and a diagnostic thermal index.** Continuing the
opening example: `acoustic_impedance(1060.0, 1570.0)` (liver density and sound speed) gives
`1,664,200` Rayl, close to the `~1.63` MRayl and `~7.8` MRayl textbook values for soft tissue and
cortical bone used above. At a 5 MHz transducer with 0.72 W of acoustic output and a tissue
attenuation coefficient of 0.3 dB/cm/MHz:

```python
runtime.execute("ultrasonics", "thermal_index", [0.72, 5.0, 0.3])["result"]
# 0.005142857142857143 — TIS = P*f*alpha/210, well under the TI <= 1 diagnostic-safety guideline
```

`axial_resolution(1540.0, 2.0e6)` (tissue sound speed, 2 MHz pulse bandwidth) gives `0.000385` m
— 0.385 mm, the depth-direction resolution limit set by pulse bandwidth, independent of
frequency; `lateral_resolution` at the same 5 MHz center frequency, a 5 cm focal depth and a 1 cm
aperture gives `wavelength(0.000308 m) * 0.05 / 0.01 = 0.00154` m (1.54 mm) — coarser than axial
resolution, which is the reason B-mode ultrasound images are sharper along the beam axis than
across it.

**Radiometry — a blackbody at skin temperature and the sun.** `stefan_boltzmann_radiance(0.98,
310.0)` (human skin emissivity, body temperature in kelvin) gives `513.1998808832` W/m² of
thermal exitance — the physical basis for a thermal (IR) camera reading. `planck_spectral_radiance`
at 0.5 μm (green light) and the sun's 5778 K photosphere temperature gives `82,855,556.4` (W/sr/m²/μm
on the module's simplified scale) — the module's own docstring calls this a "simplified form," so
treat it as relative spectral shape, not an SI-calibrated radiance.

```python
runtime.execute("radiometry", "photon_energy", [532.0])["result"]
# 2.330820966273361 — a 532 nm (green laser) photon carries about 2.33 eV

runtime.execute("radiometry", "solid_angle_cone", [0.5235987755982988])["result"]
# 0.8417872144769325 — a 30-degree half-angle cone subtends about 0.84 steradian,
# roughly 1/15 of the full 4*pi sr sphere
```

**Photonics vs. optics — the same physical Snell's-law question, two unit systems.** Light going
from air (`n=1.0`) into glass (`n=1.5`) at 30 degrees of incidence:

```python
import math
runtime.execute("optics", "snells_law", [1.5, 30.0, 1.0])["result"]
# 48.59037789072913 — degrees, going glass (1.5) -> air (1.0) at 30 deg incidence

runtime.execute("photonics", "snells_law_angle", [1.0, 1.5, math.radians(45.0)])["result"]
# 0.4908826782893113 rad (28.13 deg) — radians, air (1.0) -> glass (1.5) at 45 deg incidence
```

`fresnel_reflectance_normal(1.0, 1.5)` — identical formula and identical `1.0`/`1.5` inputs in
both modules — returns `0.04` either way: 4% of light reflects at a normal-incidence air/glass
interface, the textbook value for an uncoated lens surface.

## Guards and edge cases

* Every division-prone function in `acoustics` (`sound_pressure_level`, `_intensity_level`,
  `_power_level`, `inverse_square_law_pressure`, `wavelength`, `resonant_frequency_pipe_open`/
  `_closed`, `doppler_frequency`, `reverberation_time_sabine`) checks its denominator against
  `1e-30` and returns `0.0` (or, for `inverse_square_law_pressure`, the unmodified reference SPL)
  rather than dividing by a near-zero value.
* `radiometry.absorptance_from_reflectance` clamps its result at a floor of `0.0` — passing
  `reflectance=0.6, transmittance=0.6` (a physically inconsistent pair that sums past `1.0`) gives
  `0.0` rather than the negative value the raw `1 - R - T` energy-balance formula would produce.
  It does not clamp or warn on the upper end, so `R = T = 0.0` returns `1.0` (fully absorbing)
  without checking that assumption either.
* `radiometry.planck_spectral_radiance` returns `0.0` for non-positive wavelength or temperature,
  and again if the Planck exponent `c2 / (wavelength_um * temperature)` exceeds `700.0` — the
  point past which `exp()` would overflow `Float64` before the division ever happens.
* `optics.thin_lens_equation` returns a sentinel `1.0e18` ("effectively infinity") instead of
  dividing by zero when `1/f - 1/do_` lands on exactly `0.0` — the physical case of an object
  placed exactly at the focal point, which forms an image at infinity.
* `ultrasonics.reflection_coefficient` returns `0.0` if `z1 + z2 <= 0.0` (impedances cannot be
  negative in the source physics, but the guard fires on a literal zero sum from two zero inputs
  too), and `pulse_repetition_frequency`/`axial_resolution`/`lateral_resolution` all return `0.0`
  for a non-positive depth, bandwidth, or aperture rather than dividing by it.

## Verification

The five `mojo/tests/libs/test_{acoustics,ultrasonics,radiometry,photonics,optics}.mojo` files are
auto-generated coverage smoke tests, matching the pattern documented on
[Classical ML algorithms](ml-classical-algorithms.md): every function in each module is called
exactly once against a shared, arbitrary `0.5`-valued fixture, and the only assertion is that the
result is finite (`not isnan(x) and not isinf(x)`) — none of the five files pin a specific numeric
output. Every number in this page's worked examples was instead computed independently against
the real formulas in `mojo/engine/{acoustics,ultrasonics,radiometry,photonics,optics}.mojo` and can
be reproduced by re-running the same arithmetic in plain Python.

**Next:** see the [engine catalog](catalog.md) for how these five modules are exposed as engines,
or [Classical ML algorithms](ml-classical-algorithms.md) for the same "auto-generated smoke test,
worked examples verified independently" documentation pattern applied to a different module family.
