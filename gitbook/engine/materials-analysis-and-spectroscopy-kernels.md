---
icon: flask-vial
description: Generic mechanics-of-materials formulas, chromatographic separation science, optical/analytical spectroscopy, treatment-plant water chemistry, and structural timber engineering across five independent modules.
---

# Materials analysis and spectroscopy kernels

Five independent modules for turning a raw lab or field measurement into an engineering or
chemistry answer: a stress-strain reading becomes an elastic modulus and a safety factor
(`materials`), a chromatogram's retention times and peak widths become a resolution and a plate
count (`chromatography`), an absorbance or a Raman-shifted wavelength becomes a concentration or a
vibrational shift (`spectroscopy`), a water sample's ion concentrations become a hardness, an
alkalinity, and a corrosion tendency (`water_chemistry`), and a board's dimensions and a species'
adjustment factors become an allowable design stress (`timber`). Every function takes plain
`Float64` scalars and returns a single `Float64` — no shared struct, no cross-module imports, and
(as documented per-module below) no accidental overlap with the materials-science, water-chemistry,
or wood-science modules already documented elsewhere in this corpus.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("materials", "youngs_modulus", [100.0, 0.001])["result"]
# 100000.0 -- E = sigma/epsilon; 100 Pa of stress producing 0.001 strain

runtime.execute("chromatography", "resolution", [12.4, 10.1, 0.5, 0.6])["result"]
# 4.181818181818182 -- Rs = 2*(12.4-10.1)/(0.5+0.6); well past the Rs > 1.5
#                       baseline-separation threshold
```

## The modules

| Module | What it does |
| --- | --- |
| `materials` | Generic mechanics of materials: Young's/shear/bulk modulus and the Poisson's-ratio identity linking them, stress from force, strain from deformation, thermal expansion, safety factor, stress-concentration factor, Basquin's-law fatigue life, cantilever beam deflection, rectangular-section moment of inertia. |
| `chromatography` | Chemical separation science: retention factor, selectivity factor, theoretical plate count and plate height, chromatographic resolution, the Van Deemter equation, peak capacity, the Trennzahl separation number, the Kovats retention index, and mobile-phase linear velocity. |
| `spectroscopy` | Analytical optical spectroscopy: wavenumber/wavelength conversion, photon energy, absorbance/transmittance (Beer-Lambert), molar-absorptivity concentration, spectrometer resolving power, scan-averaged SNR, Raman shift, fluorescence quantum yield, Stokes shift, and spectral bandwidth. |
| `water_chemistry` | Drinking-water and wastewater treatment-plant chemistry: pH/[H+] conversion, hardness and alkalinity as CaCO3, the Langelier Saturation Index, a turbidity-to-Secchi-depth estimate, chlorine demand, dissolved-oxygen deficit, conductivity-to-TDS, and BOD removal efficiency. |
| `timber` | Structural timber engineering and log/lumber yield: NDS-style allowable stress adjustment, board-feet and Doyle-rule log volume, moisture content, moment capacity and section modulus, column slenderness, wood density from specific gravity, a shrinkage estimate, and a linear fire-charring model. |

## `materials`: mechanics-of-materials formulas, not a duplicate of the construction-materials page

[Structural and construction materials kernels](structural-and-construction-materials-kernels.md)
(`adhesives`, `composites`, `concrete`, `ceramics`, `polymer`, `rubber`) documents formulas specific
to *particular* material families — a concrete mix's water-cement ratio, a ceramic's Weibull failure
probability, a polymer's Mark-Houwink intrinsic viscosity. `materials.mojo` is one level more
generic: plain isotropic-elasticity and beam formulas (`E = σ/ε`, `G = E/(2(1+ν))`,
`K = E/(3(1-2ν))`, `δ = PL³/(3EI)`, Basquin's fatigue law) that any of those six material types would
plug numbers into, but none of the six modules import it or reimplement its formulas. Grepping
`gitbook/` for `` `materials` `` in backticks turns up nothing narrative outside this page and the
machine-generated [Runtime library catalog](runtime-library-catalog.md), so this is genuinely
unclaimed territory, not a page documenting the same ground twice.

The twelve functions cross-check each other. `mojo/tests/libs/test_wave58.mojo` (a real,
hand-verified suite — not the auto-generated smoke test) pins:

```python
runtime.execute("materials", "shear_modulus", [200e9, 0.3])["result"]
# 76923076923.07692 -- G = 200e9 / (2*1.3)

runtime.execute("materials", "poisson_ratio_from_moduli", [200e9, 76923076923.07692])["result"]
# 0.3 -- feeding G back through nu = E/(2G) - 1 recovers the original Poisson's ratio
#        to 1e-6, confirming the two formulas are true inverses of each other
```

Every division-shaped function guards its own zero: `youngs_modulus` returns `0.0` for
`|strain| < 1e-30` rather than dividing by it, and `beam_deflection_cantilever` returns `0.0` if
`3EI` underflows the same threshold. `fatigue_life` is Basquin's law taken literally —
`fatigue_life(200e6, 900e6, -0.1)` (a stress amplitude at about 22% of the fatigue-strength
coefficient, with a typical negative Basquin exponent) computes `(200e6/900e6)^(1/-0.1)`, which is
`(0.2222...)^-10 ≈ 3,405,063` cycles — the test only asserts this is positive and finite, but the
formula itself is exact and reproducible by hand.

## `chromatography`: a full separation-science module with no page elsewhere

Grepping `gitbook/engine/` for `` `chromatography` `` finds only this page and the auto-generated
[Runtime library catalog](runtime-library-catalog.md) row — the hinted possibility that
[Process and organic materials science kernels](process-and-organic-materials-science-kernels.md)
covered it as an unfulfilled forward-reference does not hold up: that page's `wood_science` /
`textile` / `combustion` / `paper_science` modules never mention retention time, plate count, or
any chromatographic term. `chromatography.mojo`'s ten functions are the standard analytical-
chemistry toolkit for characterizing a column and a separation, and they chain together on one
real analysis:

```python
rt   = runtime.execute("chromatography", "retention_factor", [12.0, 2.0])["result"]
# 5.0 -- k = (tR - t0)/t0 for a 12-minute peak on a 2-minute dead-time column

sel  = runtime.execute("chromatography", "selectivity_factor", [5.0, 3.0])["result"]
# 1.6666666666666667 -- alpha = k2/k1, how well-separated two analytes' k values are

n    = runtime.execute("chromatography", "plate_count", [12.0, 0.4])["result"]
# 14400.0 -- N = 16*(tR/w)^2 for a 12-minute peak 0.4 minutes wide at the base

h    = runtime.execute("chromatography", "plate_height", [25.0, 14400.0])["result"]
# 0.001736111111111111 -- H = L/N for a 25 cm column: each plate is under 2 microns tall

vd   = runtime.execute("chromatography", "van_deemter_h", [0.5, 0.02, 0.001, 2.0])["result"]
# 0.512 -- H = A + B/u + C*u = 0.5 + 0.01 + 0.002 at a mobile-phase velocity of 2

nc   = runtime.execute("chromatography", "peak_capacity", [14400.0, 20.0, 2.0])["result"]
# 70.07755278982138 -- roughly 70 resolvable peaks fit between the first eluter at
#                       2 min and the last at 20 min, given that plate count
```

`retention_index_kovats` is the one function with four independent inputs rather than a running
chain: `retention_index_kovats(6.5, 5.0, 8.0, 6)` — an unknown eluting at 6.5 minutes bracketed by
the C6 and C7 n-alkanes at 5.0 and 8.0 minutes — returns `655.82`, placing the unknown a bit past
60% of the way from the C6 to the C7 index. Every function in the module guards its own division:
`retention_factor` and `mobile_phase_velocity` return `0.0` for `dead_time <= 0.0`,
`selectivity_factor` returns `0.0` for `k1 <= 0.0`, and `peak_capacity` returns exactly `1.0`
(rather than `0.0`) when `tr_first <= 0.0` or the peaks are out of order — a single resolvable peak
is the correct floor for a capacity, not zero. The only test file behind this module,
`mojo/tests/libs/test_chromatography.mojo`, is auto-generated: it calls every function once with
literal `0.5`/`0.5`/`0.5`/`0.5` arguments and checks only that the result is finite, so every worked
number above was hand-traced from `mojo/engine/chromatography.mojo`'s real formulas and independently
recomputed, not copied from a pinned test.

## `spectroscopy`: analytical instrument formulas, and where they touch `radiometry`

[Acoustics, optics, and radiative materials kernels](acoustics-optics-and-radiative-materials-kernels.md)
already documents `radiometry`'s "blackbody and photon-counting radiometry," including its own
`photon_energy(wavelength_nm)`. That function and `spectroscopy.energy_from_wavelength(wavelength_m)`
compute the identical physics, `E = hc/λ`, but for different instruments and in different units:
`radiometry.photon_energy` takes nanometers, uses `c = 2.998e8`, and returns **electron-volts** (it
divides by `1.602e-19` at the end) — the natural unit for detector photon-counting. `spectroscopy`'s
version takes meters, uses the rounder `c = 3.0e8`, and returns **joules** with no eV conversion —
the natural unit for a Beer-Lambert-style optical-instrument calculation. Calling
`energy_from_wavelength(500e-9)` gives `3.9756e-19` J (`≈2.482` eV); calling
`photon_energy(500.0)` gives `≈2.480` eV directly — the two-thousandths-of-an-eV gap is entirely the
`c = 3.0e8` vs `c = 2.998e8` rounding choice, not a different formula. Neither module imports the
other or shares a constant.

The rest of `spectroscopy` is Beer-Lambert/UV-Vis and Raman-adjacent arithmetic that `radiometry`
never touches at all:

```python
runtime.execute("spectroscopy", "wavenumber_from_wavelength", [2.5])["result"]
# 4000.0 -- nu = 10000/lambda_um; round-trips exactly back through
#           wavelength_from_wavenumber(4000.0) == 2.5

runtime.execute("spectroscopy", "beer_lambert_concentration", [0.5, 1.0, 100.0])["result"]
# 0.005 -- c = A/(epsilon*l): absorbance 0.5 through a 1 cm cell at
#          molar absorptivity 100 L/(mol*cm) is a 5 mM solution

runtime.execute("spectroscopy", "raman_shift", [532.0, 580.0])["result"]
# 1556.1697247706424 cm^-1 -- (1/532 - 1/580) * 1e7, a 532 nm excitation
#                              Stokes-shifted to 580 nm scattered light

runtime.execute("spectroscopy", "snr_coadd", [10.0, 16.0])["result"]
# 40.0 -- SNR grows with sqrt(n_scans): 16 co-added scans quadruple a
#          single-scan SNR of 10
```

`absorbance_from_transmittance` and `transmittance_from_absorbance` are exact inverses of the same
`A = -log10(T/100)` relationship — `absorbance_from_transmittance(50.0) = 0.30103`, and feeding that
back through `transmittance_from_absorbance` returns `50.0` to five decimal places, the same
round-trip self-check pattern used for RoPE in
[Attention kernels](attention-kernels.md). `spectral_bandwidth` is a literal pass-through (it returns
its `fwhm` argument unchanged) rather than a derived quantity — it exists so callers have a named
function for "the FWHM value is the bandwidth" instead of inlining the identity themselves.
`mojo/tests/libs/test_spectroscopy.mojo` is auto-generated (finite-check only); the real pinned
numbers above come from `tests/mojo/test_wave96.mojo`, which hand-verifies twelve `spectroscopy`
functions to `1e-3`–`1e-6` tolerance alongside `timber` and `project_management`.

## `water_chemistry`: treatment-plant process control, not `limnochemistry`'s lake biogeochemistry

[Hydrology & water systems kernels](hydrology-and-water-systems-kernels.md) already documents
`limnochemistry` as "freshwater ionic chemistry" for lakes and rivers — carbonate alkalinity, the
Davies activity coefficient, a calcite saturation index, silica export flux, Eh/pe conversion,
nutrient fractionation. `water_chemistry.mojo` computes some of the same *named* quantities but for
an entirely different setting — a drinking-water or wastewater treatment plant — using different
formulas:

* **Alkalinity.** `limnochemistry.carbonate_alkalinity` is a charge-balance equation in milli-
  equivalents per liter, `Alk = [HCO3⁻] + 2[CO3²⁻] + [OH⁻] - [H⁺]`, meant for natural-water titration
  data. `water_chemistry.alkalinity_as_caco3` is a mass-based industry-standard conversion in
  mg/L-as-CaCO3, `Alk = 0.82·HCO3⁻ + 1.67·CO3²⁻ + 2.94·OH⁻`, with no proton term at all (standard
  practice for near-neutral treated water, where free H⁺ is negligible). `alkalinity_as_caco3(120.0,
  0.0, 0.0)` returns `98.4` mg/L for a purely bicarbonate-buffered sample — a different number, a
  different unit, and a different intended input than the lake formula.
* **Saturation index.** `limnochemistry.saturation_index_calcite` *derives* its own saturation pH
  from calcium, alkalinity, and temperature (`pH_sat = 11.73 - 0.053·T - log(Ca) - log(Alk)`) before
  subtracting it from the measured pH. `water_chemistry.langelier_saturation_index(ph,
  ph_saturation)` takes `ph_saturation` as an already-known input and only does the subtraction —
  it assumes a plant has already looked up or computed `pHs` from standard water-treatment tables,
  rather than deriving it from raw ion concentrations itself.

```python
runtime.execute("water_chemistry", "water_hardness", [150.0, 30.0])["result"]
# 498.09 -- 2.497*150 + 4.118*30 mg/L as CaCO3 (the module's docstring rounds these
#           gravimetric factors to 2.5/4.12, but the code uses the precise
#           CaCO3/Ca and CaCO3/Mg molar-mass ratios, 100.09/40.08 and 100.09/24.305)

runtime.execute("water_chemistry", "langelier_saturation_index", [7.8, 8.1])["result"]
# -0.3 -- pH below pHs: mildly corrosive (scale-forming is positive, corrosive is negative)

runtime.execute("water_chemistry", "bod_removal", [200.0, 20.0])["result"]
# 90.0 -- (200-20)/200 * 100, a 90% BOD removal efficiency across a treatment stage
```

Every subtraction-shaped function floors at zero rather than returning a negative: `chlorine_demand`
and `dissolved_oxygen_deficit` both clamp a negative difference to `0.0`, and `bod_removal` clamps a
negative removal rate to `0.0` too (an effluent BOD higher than the influent's would otherwise
report negative "removal"). `ph_from_hydrogen_ion` returns a sentinel `14.0` for
`h_concentration <= 0.0` rather than an undefined logarithm. Grepping `gitbook/` for
`` `water_chemistry` `` in backticks confirms no other narrative page claims this module; its only
tests are the auto-generated `mojo/tests/libs/test_water_chemistry.mojo` finite-check suite, so the
numbers above were independently hand-computed from `mojo/engine/water_chemistry.mojo`.

## `timber`: structural design and forestry yield, distinct from `wood_science`'s material testing

[Process and organic materials science kernels](process-and-organic-materials-science-kernels.md)
already documents `wood_science` as wood *material-testing* physics — modulus of rupture and
elasticity measured from a three-point bending test, fiber saturation point, a thermal-conductivity
estimate, Janka hardness. `timber.mojo` is a different scope: NDS-style structural *design* (an
allowable stress built from load-duration, size, and wet-service adjustment factors) and forestry
*yield accounting* (board-feet, the Doyle log-scaling rule) — neither of which `wood_science`
touches at all. Two of the ten `timber` functions do duplicate a `wood_science` formula exactly,
just under different parameter names and with neither module importing the other:
`timber.moisture_content(wet_weight, oven_dry_weight)` and
`wood_science.moisture_content(wet_mass, dry_mass)` are both `(wet - dry)/dry * 100`, and
`timber.section_modulus_beam(width, depth)` and `wood_science.section_modulus(width, depth)` are
both `b·h²/6`. Past those two, the modules diverge: `timber.fire_char_rate` is a flat linear model
(`depth = time * rate`), while `wood_science.charring_rate` is `wood_science`'s own power-law model
(`depth = β₀ · t^0.813`) — the same real phenomenon, two different fits, neither one calling the
other.

`mojo/tests/libs/test_timber.mojo` is auto-generated (finite-check only); the pinned numbers below
come from the real, hand-verified `tests/mojo/test_wave96.mojo`:

```python
runtime.execute("timber", "allowable_stress", [1000.0, 1.15, 1.0, 0.85])["result"]
# 977.5 -- F' = Fb * CD * CF * CM: base stress adjusted for a 1.15 load-duration
#          factor, no size adjustment, and an 0.85 wet-service reduction

runtime.execute("timber", "log_volume_doyle", [20.0, 16.0])["result"]
# 256.0 -- Doyle rule: (D-4)^2 * L / 16, board feet in a 20-inch-diameter,
#          16-foot log

runtime.execute("timber", "fire_char_rate", [60.0, 0.635])["result"]
# 38.1 -- 60 minutes of exposure at 0.635 mm/min char rate

runtime.execute("timber", "remaining_section", [200.0, 38.1])["result"]
# 123.8 -- a 200 mm member loses char on both faces: 200 - 2*38.1
```

`column_slenderness` and `board_feet` both guard a zero denominator/dimension by returning `0.0`
rather than dividing; `shrinkage_estimate` does the same for a zero fiber-saturation point.

## Verification

Two of these five modules have real, hand-verified test coverage beyond the auto-generated smoke
suite: `materials` in `mojo/tests/libs/test_wave58.mojo` and `timber`/`spectroscopy` together in
`tests/mojo/test_wave96.mojo`, both of which pin specific numeric outputs (not just "is finite")
and are the source of the exact figures quoted above for those three modules. `chromatography` and
`water_chemistry` have only the auto-generated `mojo/tests/libs/test_chromatography.mojo` and
`test_water_chemistry.mojo` — each calls every function once with literal `0.5`-shaped arguments and
checks solely that the result is finite, pinning no specific value. Every `chromatography` and
`water_chemistry` number in this page was therefore hand-traced against the real formulas in
`mojo/engine/chromatography.mojo` and `mojo/engine/water_chemistry.mojo` and independently
recomputed before being presented here.

**Next:** see [Process and organic materials science kernels](process-and-organic-materials-science-kernels.md)
for `wood_science`'s wood-testing physics, or [Hydrology & water systems kernels](hydrology-and-water-systems-kernels.md)
for `limnochemistry`'s natural-water chemistry.
