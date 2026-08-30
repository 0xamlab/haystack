---
icon: gem
description: Cave hydrology, speleothem dating, and cave-radio physics; mineral identification and crystal chemistry; X-ray diffraction and unit-cell geometry; and the trace-element, isotope, and elemental-cycling arithmetic of geochemistry and biogeochemistry, across five independent modules.
---

# Speleology, mineralogy, and geochemistry kernels

Five small, stateless modules for the closed-form arithmetic behind identifying and dating solid
earth materials and tracking the elements that move through them: `speleology` (cave passage
geometry, karst hydrology, speleothem growth and uranium-series dating, cave-radio propagation),
`mineralogy` (density, hardness, Bragg d-spacing, formula weight, solubility products, optical
birefringence), `crystallography` (unit-cell volumes, atomic packing factors, Scherrer
crystallite sizing, structure-factor magnitude), `geochemistry` (trace-element partitioning
during melting, chondrite-normalized rare-earth ratios, isotope mixing, weathering indices,
carbonate saturation), and `biogeochemistry` (net ecosystem production, nitrogen and phosphorus
cycling, soil carbon turnover, the global carbon budget). None of these five simulate a process
over time or hold state between calls — each function is one textbook or literature formula,
evaluated on plain `Float64` scalars, with no shared struct and no cross-module imports.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Silicon's (111) planes: real lattice parameter 5.4310 Angstrom, Miller indices (1,1,1)
runtime.execute("crystallography", "d_spacing_cubic", [5.4310, 1, 1, 1])["result"]
# 3.135589311968858 -- matches the textbook d-spacing for Si(111), 3.1356 Angstrom

# Same reflection, Cu-K-alpha X-rays (1.5406 Angstrom): what Bragg angle produces it?
runtime.execute("crystallography", "bragg_angle", [1, 1.5406, 3.135589311968858])["result"]
# 0.24820415988534122 radians = 14.221 degrees -- matches the published Si(111) Bragg angle
```

## The modules

| Module | What it does |
| --- | --- |
| `speleology` | Cave passage volume, stalactite growth from drip-water calcite deposition, calcite saturation index in drip water, cave-air temperature with depth, Reynolds number for passage flow, karst spring recession discharge, cave-radio skin depth, PWP-model limestone dissolution rate, ²³⁰Th/²³⁴U speleothem age, and equilibrium radon concentration. |
| `mineralogy` | Density, Mohs hardness comparison, Bragg d-spacing from a measured angle, two-element formula weight, ion-activity-product solubility, Debye-Hückel ion activity, saturation index, specific gravity, geometric-mean thermal-conductivity mixing, and optical birefringence. |
| `crystallography` | Bragg angle, cubic d-spacing and its inverse (lattice parameter from d), cubic/tetragonal/orthorhombic unit-cell volume, the FCC and BCC atomic packing factors, Scherrer crystallite size from XRD peak broadening, the interplanar angle between two cubic Miller-index planes, crystal density from `Z`/molar mass/unit-cell volume, and structure-factor magnitude. |
| `geochemistry` | Solid/liquid distribution coefficient, two identically-implemented batch-melting trace-element models, CI-chondrite-normalized rare-earth ratios, two-component isotope mixing, the Chemical Index of Alteration (weathering index), Eh-to-pe conversion, carbonate saturation state, Henry's-law dissolved-gas concentration, and total organic carbon (TC − TIC). |
| `biogeochemistry` | Net ecosystem production, carbon-use efficiency, nitrogen mineralisation, Michaelis-Menten denitrification, Langmuir phosphorus sorption, first-order methane oxidation, first-order soil-carbon turnover, silicate-weathering CO₂ consumption, acetylene-reduction nitrogen-fixation estimate, and the global atmospheric carbon-growth budget. |

## `speleology`: cave hydrology, speleothem dating, and cave-radio physics

| Function | What it does |
| --- | --- |
| `cave_passage_volume(length_m, width_m, height_m)` | Elliptical cross-section estimate, `V = π/4 · W · H · L`. |
| `stalactite_growth_rate(drip_rate_ml_per_min, calcite_per_ml_mg, density_g_cm3)` | Annualizes drip-water calcite deposition (`× 525,960` minutes/year) into a linear growth rate. |
| `drip_water_calcite_saturation(ca_mmol_l, co3_mmol_l, ksp)` | Saturation index `SI = log10([Ca²⁺][CO₃²⁻] / Ksp)` from millimolar concentrations; `0.0` if `ksp <= 0` or the ion product is non-positive. |
| `cave_climate_temperature(surface_maat, depth_m, lapse_rate)` | `T_cave = MAAT + depth × lapse_rate`. |
| `turbulent_flow_cave(velocity, hydraulic_diameter, kinematic_viscosity)` | Reynolds number `Re = v·Dh/ν`; `0.0` if viscosity is non-positive. |
| `karst_spring_discharge(storage_m3, recession_coefficient)` | Exponential-recession discharge evaluated at normalized `t = 1`: `Q = storage × α`. |
| `cave_radio_signal_depth(frequency_hz, conductivity)` | Electromagnetic skin depth `δ = √(2/(ωμσ))` through rock, using free-space permeability. |
| `dissolution_rate_limestone(saturation_index, rate_constant)` | PWP-model rate `r = k(1 − Ω)`, `Ω = 10^SI`; `0.0` once the water is already saturated or supersaturated. |
| `age_uranium_series(activity_ratio_230_234)` | Secular-equilibrium ²³⁰Th/²³⁴U age, `-ln(1 − ratio)/λ₂₃₀`; refuses (`0.0`) for a ratio at or outside `(0, 1)`. |
| `radon_in_cave_air(radon_flux, ventilation_rate, decay_constant)` | Equilibrium concentration `flux / (ventilation + λ_Rn)`. |

**Worked example: a slow-growing stalactite.** A drip of `0.05` mL/min carrying `0.003` mg
calcite per mL, depositing calcite of density `2.71` g/cm³ (real calcite):

```python
runtime.execute("speleology", "stalactite_growth_rate", [0.05, 0.003, 2.71])["result"]
# 0.2911217712177122 mm/yr
```

Tracing the formula: `0.05 × 0.003 × 525,960 = 78.894` mg of calcite deposited per year;
`78.894 / (2.71 × 1000) = 0.02911...` cm³/yr of calcite volume; the final `× 10.0` converts that
volume into a linear growth rate in mm/yr **by implicitly assuming the depositing area is exactly
1 cm²** (1 cm³ spread over 1 cm² is 1 cm = 10 mm of length). That assumption is stated in the code
comment ("cm3 to mm, assuming 1 cm² area") but the function's own docstring return line says
"assuming 1 mm² tip area" instead — the two in-source descriptions of the same assumption
disagree by two orders of magnitude in area, though only one of them (1 cm²) is the one the
arithmetic actually implements. `0.29` mm/yr lands inside the commonly cited real-world range for
slow-growing temperate-cave speleothems (roughly `0.01`-`1` mm/yr).

**Worked example: dating a speleothem.** A measured (²³⁰Th/²³⁴U) activity ratio of `0.5`:

```python
runtime.execute("speleology", "age_uranium_series", [0.5])["result"]
# 75687.61526096804 years
```

`-ln(0.5) / 9.158e-6 = 0.693147.../9.158e-6`. The function's decay constant implies a ²³⁰Th
half-life of `ln(2)/9.158e-6 ≈ 75,688` years — close to, but not identical to, the `75,380` years
the docstring states outright; both are in the right neighborhood of the accepted value
(≈75,584 years, Cheng et al. 2013), so the discrepancy is a rounding artifact of the constant
used, not a wrong formula.

{% hint style="warning" %}
**`age_uranium_series` refuses at both ends of the physically meaningful range, silently.**
A ratio `>= 1.0` (which a secular-equilibrium model treats as infinite age) or `<= 0.0` both
return exactly `0.0` — indistinguishable from "the sample is zero years old." A ratio of exactly
`1.0` from real analytical data should be treated as "too old to date with this simplified model,"
not as a fresh deposit.
{% endhint %}

## `mineralogy`: identification and crystal-chemistry arithmetic

| Function | What it does |
| --- | --- |
| `mineral_density(mass_g, volume_cm3)` | `ρ = m/V`; `0.0` if volume is non-positive. |
| `mohs_hardness_scratch(hardness_a, hardness_b)` | `hardness_a - hardness_b`; positive means A scratches B. |
| `crystal_d_spacing(n, wavelength_angstrom, theta_rad)` | Bragg's law solved for spacing, `d = nλ/(2 sinθ)`; `0.0` if `sin θ <= 0`. |
| `mineral_formula_weight(atomic_weight1, count1, atomic_weight2, count2)` | Sum of two atomic contributions, `n1·Aw1 + n2·Aw2`. |
| `solubility_product(cation_conc, anion_conc, cation_stoich, anion_stoich)` | Ion activity product `[M]^m·[X]^x`; `0.0` if either concentration is negative. |
| `geochemical_activity(concentration, activity_coefficient)` | `a = γ·c`. |
| `mineral_saturation_index(ion_activity_product, ksp)` | `SI = log10(IAP/Ksp)`; `0.0` if either input is non-positive. |
| `specific_gravity_ratio(mineral_density_g_cm3)` | Returns its input unchanged (see below). |
| `thermal_conductivity_mixing(k1, k2, vol_fraction1)` | Geometric-mean mixing, `κ1^f · κ2^(1-f)`; `0.0` if either conductivity is non-positive. |
| `birefringence(n_extraordinary, n_ordinary)` | `Δn = \|ne - no\|`. |

**Worked examples, cross-checked against real minerals:**

```python
runtime.execute("mineralogy", "mineral_density", [26.5, 10.0])["result"]
# 2.65 g/cm3 -- the textbook density of quartz

runtime.execute("mineralogy", "mohs_hardness_scratch", [7, 6])["result"]
# 1.0 -- quartz (7) scratches orthoclase feldspar (6)

runtime.execute("mineralogy", "mineral_formula_weight", [28.0855, 1, 15.9994, 2])["result"]
# 60.0843 g/mol -- SiO2's real molar mass

runtime.execute("mineralogy", "birefringence", [1.486, 1.658])["result"]
# 0.17199999999999993 -- calcite's real birefringence (ne=1.486, no=1.658), a textbook value
```

`crystal_d_spacing` runs the same Bragg equation as `crystallography.bragg_angle` in the opposite
direction: given `theta_rad = 0.256563` (14.70°) and Cu-Kα (`1.5406` Å), it returns `d =
3.0355699848544706` Å — within a thousandth of an angstrom of calcite's real (104) d-spacing,
`3.035` Å.

{% hint style="info" %}
**`specific_gravity_ratio` is an identity function.** Its docstring frames it as "density divided
by the density of water at 4°C," but water's reference density is `1.0` g/cm³, and the source
divides by that constant literally: `return mineral_density_g_cm3` with a comment noting the
`/ 1.0 g/cm³` step rather than performing a division. Calling it does not fail or misbehave — it
genuinely returns specific gravity, since 1.0 is the correct divisor — but the function has no
computational content of its own; it exists to give the ratio a distinct, self-documenting name at
the call site.
{% endhint %}

## `crystallography`: unit cells, XRD geometry, and packing

| Function | What it does |
| --- | --- |
| `bragg_angle(n, wavelength, d_spacing)` | `θ = asin(nλ/(2d))`; `0.0` if `d` is ~zero or the arcsine argument falls outside `[-1, 1]`. |
| `d_spacing_cubic(a, h, k, l)` | `d = a/√(h²+k²+l²)`; `0.0` for `(000)`. |
| `lattice_parameter_from_d(d, h, k, l)` | Inverse of the above: `a = d·√(h²+k²+l²)`. |
| `unit_cell_volume_cubic(a)` | `V = a³`. |
| `unit_cell_volume_tetragonal(a, c)` | `V = a²c`. |
| `unit_cell_volume_orthorhombic(a, b, c)` | `V = abc`. |
| `atomic_packing_factor_fcc()` | Constant, `π√2/6 ≈ 0.7405`. |
| `atomic_packing_factor_bcc()` | Constant, `π√3/8 ≈ 0.6802`. |
| `scherrer_crystallite_size(k, wavelength, fwhm_rad, theta)` | `L = Kλ/(β cos θ)`; `0.0` if the denominator is ~zero. |
| `interplanar_angle_cubic(h1,k1,l1,h2,k2,l2)` | `cos φ = (dot product)/(‖1‖‖2‖)`, clamped to `[-1,1]` before the `acos`; `0.0` if either plane is `(000)`. |
| `density_from_crystal(z, molar_mass, avogadro, volume)` | `ρ = ZM/(Nₐ·V)`; `0.0` if the denominator is ~zero. |
| `structure_factor_magnitude(f_real, f_imag)` | `\|F\| = √(f_real² + f_imag²)`. |

**Every worked number below is a real crystal, not an arbitrary input**, cross-checked against
published lattice constants:

```python
# Silicon: cubic, a = 5.4310 Angstrom
runtime.execute("crystallography", "unit_cell_volume_cubic", [5.4310])["result"]
# 160.191477991 cubic Angstrom -- real Si unit cell volume is ~160.1 A^3

# Rutile (TiO2): tetragonal, a = 4.593, c = 2.959 Angstrom
runtime.execute("crystallography", "unit_cell_volume_tetragonal", [4.593, 2.959])["result"]
# 62.422025391 -- matches the published rutile cell volume, ~62.4 A^3

# Forsterite (Mg2SiO4): orthorhombic, a = 4.756, b = 10.207, c = 5.980 Angstrom
runtime.execute("crystallography", "unit_cell_volume_orthorhombic", [4.756, 10.207, 5.980])["result"]
# 290.2960621600001 -- matches the published forsterite cell volume, ~290 A^3

# Angle between the (100) and (110) planes in any cubic crystal
runtime.execute("crystallography", "interplanar_angle_cubic", [1,0,0, 1,1,0])["result"]
# 0.7853981633974484 radians = 45.00000000000001 degrees -- the standard cubic-system result

# NaCl: Z=4 formula units/cell, M=58.44 g/mol, a=5.6402 Angstrom -> V=1.79425e-22 cm3
runtime.execute("crystallography", "density_from_crystal",
                [4, 58.44, 6.022e23, 1.79425230436808e-22])["result"]
# 2.163445378008093 g/cm3 -- real NaCl density is 2.165 g/cm3
```

`structure_factor_magnitude(3, 4)` returns `5.0` — the same 3-4-5 right triangle used elsewhere in
this corpus (`ml.knn.euclidean_distance_knn`) as a distance sanity check, here applied to a
complex structure factor's real and imaginary parts instead of a 2-D point.

`atomic_packing_factor_fcc` and `atomic_packing_factor_bcc` take no arguments at all — they are
compile-time constants (`π√2/6` and `π√3/8`) wrapped as functions purely so a caller can look them
up by name through `runtime.execute` rather than hardcoding the irrational value.

## `geochemistry`: trace elements, isotopes, and weathering

| Function | What it does |
| --- | --- |
| `distribution_coefficient(conc_solid, conc_liquid)` | `Kd = C_solid/C_liquid`; `0.0` if the liquid concentration is non-positive. |
| `partition_melt(c0, d0, melt_fraction)` | Batch-melting trace-element model, `Cl = C0/(D + F(1-D))`. |
| `batch_melting(c0, d0, melt_fraction)` | Byte-for-byte the same formula as `partition_melt` (see below). |
| `rare_earth_normalization(sample_conc, chondrite_conc)` | `sample/chondrite`; `0.0` if the chondrite reference is non-positive. |
| `isotope_mass_balance(delta_a, fraction_a, delta_b)` | Two-component mixing, `f·δA + (1-f)·δB`. |
| `weathering_index(al2o3, cao, na2o, k2o)` | Chemical Index of Alteration, `Al₂O₃/(Al₂O₃+CaO+Na₂O+K₂O) × 100`. |
| `redox_potential_pe(eh_mv)` | `pe = Eh(mV)/59.16` (25°C Nernst conversion). |
| `carbonate_saturation(ca_conc, co3_conc, ksp)` | `Ω = [Ca²⁺][CO₃²⁻]/Ksp`; `0.0` if `ksp <= 0`. |
| `henry_law_gas(partial_pressure, henry_constant)` | `C = KH·P`. |
| `organic_carbon_toc(total_carbon, inorganic_carbon)` | `TOC = TC - TIC`, floored at `0.0`. |

{% hint style="info" %}
**`partition_melt` and `batch_melting` are the same function under two names.** Reading both
bodies in `mojo/engine/geochemistry.mojo` side by side: identical guard (`denom <= 0.0`),
identical formula (`c0 / (d0 + melt_fraction * (1.0 - d0))`), identical return. The docstrings
differ cosmetically — `batch_melting`'s claims a `p` term "simplified (p = D for modal melting)" —
but no `p` parameter exists in either signature, and no code distinguishes batch from fractional
(perfect Rayleigh) melting here; both compute the standard **batch**-melting equation. A caller
who wants true incremental/fractional melting needs a different formula than either of these two.
{% endhint %}

**Worked example: incompatible-element enrichment during partial melting.** A trace element with
bulk solid/liquid distribution coefficient `D = 0.01` (strongly incompatible, e.g. La in mantle
peridotite), source concentration `C0 = 1` ppm, at `5%` partial melting:

```python
runtime.execute("geochemistry", "partition_melt", [1.0, 0.01, 0.05])["result"]
# 16.806722689075627 ppm
```

A roughly 17-fold enrichment in the melt relative to the source — the low-`F`, low-`D` regime
where incompatible-element enrichment is strongest, matching the qualitative behavior taught for
this equation in igneous petrology.

**Worked example: ocean surface-water carbonate saturation.** Typical open-ocean surface values —
`[Ca²⁺] = 0.0103` mol/kg, `[CO₃²⁻] = 2.5×10⁻⁴` mol/kg, aragonite `Ksp = 6.65×10⁻⁷`:

```python
runtime.execute("geochemistry", "carbonate_saturation", [0.0103, 2.5e-4, 6.65e-7])["result"]
# 3.8721804511278193
```

An aragonite saturation state (`Ω_arag`) around `3`-`4` is exactly the range reported for modern
open-ocean surface water — supersaturated, which is why aragonite-shelled organisms can
biomineralize there at all; the same function applied to deeper, colder, more CO₂-rich water
(higher `[H⁺]`, lower `[CO₃²⁻]`) would push `Ω` below `1`, the real chemical basis of the
"aragonite saturation horizon" that shoals as the ocean acidifies.

**Worked example: real CI-chondrite normalization.** Lanthanum in a sample at `30` ppm, against
the CI-chondrite reference value of `0.237` ppm (McDonough & Sun, 1995):

```python
runtime.execute("geochemistry", "rare_earth_normalization", [30.0, 0.237])["result"]
# 126.58227848101266
```

## `biogeochemistry`: element cycling between biosphere and geosphere

| Function | What it does |
| --- | --- |
| `net_ecosystem_production(gpp, ecosystem_respiration)` | `NEP = GPP - Re`; positive means a carbon sink. |
| `carbon_use_efficiency(npp, gpp)` | `CUE = NPP/GPP`; `0.0` if `gpp <= 0`. |
| `nitrogen_mineralisation(organic_n, mineralisation_rate, temperature_factor)` | `k × Norg × Q10_factor`. |
| `denitrification_rate(nitrate_conc, denitrifier_biomass, anaerobic_fraction)` | Michaelis-Menten form, `0.1 × [NO3]/(10+[NO3]) × biomass × anaerobic_frac`. |
| `phosphorus_sorption(dissolved_p, max_sorption, binding_constant)` | Langmuir isotherm, `Qmax·KL·C/(1+KL·C)`. |
| `methane_oxidation(ch4_conc, oxidation_rate)` | First-order removal, `k × [CH4]`. |
| `soil_carbon_turnover(soc_pool, decomposition_rate, clay_protection)` | `k × SOC × (1 - clay_protection)`. |
| `weathering_co2_consumption(cation_flux, charge_equivalents)` | `cation_flux × charge_equivalents × 44/2 / 1e6`, converting river cation flux into CO₂ drawdown. |
| `nitrogen_fixation_estimate(acetylene_reduction)` | Acetylene-reduction assay's fixed 3:1 stoichiometry, `ARA/3`. |
| `global_carbon_budget(fossil_emissions, land_use_change, land_sink, ocean_sink)` | `ΔC_atm = emissions + LUC - land_sink - ocean_sink`. |

**Worked example: the recent real global carbon budget.** Using figures of the right order for
the mid-2020s (Global Carbon Project-style annual means, in Gt C/yr): fossil emissions `9.9`,
land-use-change emissions `1.1`, land sink `3.1`, ocean sink `2.9`:

```python
runtime.execute("biogeochemistry", "global_carbon_budget", [9.9, 1.1, 3.1, 2.9])["result"]
# 5.0 Gt C/yr
```

`5.0` Gt C/yr lands exactly on the "~5 Gt C/yr recently" figure the function's own docstring
cites, and matches the broad range the annual Global Carbon Budget has reported for atmospheric
CO₂ growth in recent years.

**Worked example: a productive temperate forest's carbon balance.** `GPP = 1200`, ecosystem
respiration `= 1000` g C/m²/yr:

```python
runtime.execute("biogeochemistry", "net_ecosystem_production", [1200.0, 1000.0])["result"]
# 200.0 g C/m2/yr -- a net carbon sink, in the range reported for productive temperate forests
```

At `NPP = 600` for the same `GPP = 1200`, `carbon_use_efficiency` returns `0.5`, squarely inside
the `0.3`-`0.6` range the function's own docstring cites as typical for terrestrial plants.

## No status-code vocabulary; every guard returns a plain `0.0`

Unlike `attnk`, `tensorx`, `gemm`, and other families in this corpus that carry a numbered
status-code range alongside their results, none of these five modules define one. Every guarded
function across all five — `turbulent_flow_cave`, `karst_spring_discharge`, `dissolution_rate_limestone`,
`age_uranium_series`, `mineral_density`, `mineral_saturation_index`, `bragg_angle`,
`density_from_crystal`, `distribution_coefficient`, `carbonate_saturation`, and the rest — returns
a bare sentinel `Float64` directly on invalid input: `0.0` for a zero or negative denominator, a
non-positive concentration, an out-of-domain ratio, or an arcsine/√ argument outside its valid
range. There is no separate error code to distinguish "the input was physically nonsensical" from
"the true answer happens to be zero" — a caller that needs to tell those apart has to validate its
own inputs before calling.

That validation burden is sharper for the three saturation-index-style functions this family
carries: `mineralogy.mineral_saturation_index`, `geochemistry.carbonate_saturation`, and
`speleology.drip_water_calcite_saturation` all compute essentially the same calcite/carbonate
equilibrium, but take different unit conventions and return different quantities — mineralogy
takes a pre-computed ion-activity product and returns `log10(IAP/Ksp)`; geochemistry takes raw
molar ion concentrations and returns the linear ratio `Ω` rather than its log; speleology takes
millimolar concentrations and returns `log10` SI directly, like mineralogy. Passing the wrong
module's expected units into another's function produces a plausible-looking number rather than an
error.

## Verification

The five `mojo/tests/libs/test_*.mojo` files behind this page (`test_speleology.mojo`,
`test_mineralogy.mojo`, `test_crystallography.mojo`, `test_geochemistry.mojo`,
`test_biogeochemistry.mojo`) are auto-generated coverage smoke tests: each calls every function
once on a shared, arbitrary fixture (`0.5` for every scalar argument) and checks only that the
result is finite — none of the five pins a specific numeric output. Every worked number in this
page was instead hand-traced against the real formulas in `mojo/engine/speleology.mojo`,
`mineralogy.mojo`, `crystallography.mojo`, `geochemistry.mojo`, and `biogeochemistry.mojo`,
cross-checked against real published mineral/crystal constants (quartz density and hardness,
calcite birefringence, silicon and rutile and forsterite lattice geometry, NaCl density, CI-chondrite
La, modern seawater aragonite saturation state, and the Global Carbon Project's recent annual
budget) and independently reproduced with plain Python arithmetic — every number given can be
regenerated by re-running the same computation.

**Next:** see [Acoustics, optics, and radiative materials kernels](acoustics-optics-and-radiative-materials-kernels.md)
and [Structural and construction materials kernels](structural-and-construction-materials-kernels.md)
for the same "one closed-form formula per function, no shared state" style applied to physical and
engineering materials instead of earth materials, or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
