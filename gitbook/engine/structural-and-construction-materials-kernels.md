---
icon: trowel-bricks
description: Adhesive bond strength and cure kinetics, fiber-composite mechanics, concrete mix design and curing, ceramic fracture statistics, polymer chain/molecular-weight science, and rubber/elastomer testing, across six independent modules.
---

# Structural and construction materials kernels

Six small, independent modules for the arithmetic behind materials selection and testing in
construction and manufacturing: how much adhesive a bonded joint needs and how long it takes to
cure, how a fiber and a matrix combine into a composite's stiffness, how a concrete mix's
water-cement ratio drives its strength and shrinkage, how a ceramic's measured strength translates
into a failure probability at a different stress, how a polymer's molecular weight and chain
statistics are computed from raw synthesis numbers, and how a rubber compound's hardness, set, and
aging are quantified. Every function takes plain scalars — no shared struct, no cross-module
imports — and returns a single `Float64`.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("concrete", "water_cement_ratio", [175.0, 350.0])["result"]
# 0.5 — 175 kg water over 350 kg cement, a mid-range structural mix

runtime.execute("concrete", "modulus_of_elasticity", [32.0])["result"]
# 26587.214972614187 — ACI Ec = 4700 * sqrt(fc), fc = 32 MPa
```

## The modules

| Module | What it does |
| --- | --- |
| `adhesives` | Lap-shear and peel strength, bond-area sizing, coverage rate, temperature-adjusted pot life and cure time, Arrhenius viscosity, contact-angle surface energy, and a simplified thermal-cycle-life estimate |
| `composites` | Rule-of-mixtures and Halpin-Tsai modulus, composite density, fiber volume fraction, laminate thickness, specific stiffness/strength, critical fiber length, shear-lag stress transfer, Charpy impact energy, and void content |
| `concrete` | Water-cement ratio, Abrams'-law compressive strength, mix-volume accounting, slump and Nurse-Saul maturity estimates, ACI modulus of elasticity and splitting tensile strength, drying shrinkage, carbonation depth, and rebar development length |
| `ceramics` | Weibull failure probability and characteristic strength, thermal shock resistance, porosity effects on modulus, sintering shrinkage, Archimedes/relative density, indentation fracture toughness, dielectric mixing, CTE, and a Kauzmann glass-transition estimate |
| `polymer` | Molecular-weight averages (Mn, Mw, PDI), degree of polymerization, Mark-Houwink intrinsic viscosity, Fox-equation blend Tg, Flory-Huggins mixing free energy, freely-jointed-chain end-to-end distance and radius of gyration, Carothers conversion, and melt-flow-index approximation |
| `rubber` | Shore A to Young's modulus, Mooney viscosity, tensile/compression set, elongation at break, tear strength, rebound resilience, aging hardness change, swelling, crosslink density, abrasion loss, and hysteresis heat buildup |

## Adhesives: bonding is sized by load, not just glued by feel

`bond_area_from_load` inverts the lap-shear formula to answer the design question directly — given
a load and a safety factor, how much bonded area does the joint need:

```python
runtime.execute("adhesives", "lap_shear_strength", [5000.0, 2500.0])["result"]
# 2.0 MPa — 5000 N over 2500 mm²

runtime.execute("adhesives", "bond_area_from_load", [5000.0, 15.0, 2.0])["result"]
# 666.6666666666666 mm² — a 5000 N load, 15 MPa allowable stress, 2× safety factor
```

Temperature enters two of the module's functions through algebraically the same Q10-style rate
law, just written two different ways. `cure_time_temperature` divides by `acceleration^((temp -
ref_temp)/10)`; `pot_life_temperature_adjusted` multiplies by `factor^((ref_temp - temp)/10)` —
dividing by `x^y` and multiplying by `x^(-y)` are the same operation, and `(temp - ref_temp)` is
`-(ref_temp - temp)`, so the two formulas are identical in shape with the sign folded into which
side of the ratio is on top. Both quantities shrink as temperature rises above the reference — heat
speeds up cure and shortens working time together, which is physically the same phenomenon (faster
reaction kinetics) showing up in both numbers:

```python
runtime.execute("adhesives", "cure_time_temperature", [120.0, 60.0, 23.0, 2.0])["result"]
# 9.233583100086873 minutes — a 120-minute cure at 23C drops to ~9.2 min at 60C, accel factor 2

runtime.execute("adhesives", "pot_life_temperature_adjusted", [60.0, 35.0, 23.0, 2.0])["result"]
# 26.116516898883724 minutes — a 60-minute pot life at 23C shrinks to ~26 min at 35C
```

`viscosity_temperature` is a real Arrhenius model, `eta = eta_ref * exp(Ea/R * (1/T - 1/T_ref))`,
using absolute temperature in kelvin rather than the `/10` empirical shortcut the other two
functions use:

```python
runtime.execute("adhesives", "viscosity_temperature", [1.0, 50000.0, 8.314, 333.0, 298.0])["result"]
# 0.11989592618812282 Pa·s — a 1.0 Pa·s adhesive at 298K (25C) thins to ~0.12 Pa·s at 333K (60C)
```

## Composites: the same fiber and matrix give two different moduli

`rule_of_mixtures_modulus` (Voigt, loading parallel to the fibers) and `inverse_rule_of_mixtures`
(Reuss, loading transverse to them) take identical inputs and diverge sharply, because a
fiber-reinforced composite is genuinely anisotropic — it is not one modulus, it is two:

```python
# 60% by volume carbon fiber (Ef = 230 GPa) in an epoxy matrix (Em = 3.5 GPa)
runtime.execute("composites", "rule_of_mixtures_modulus", [0.6, 230.0, 3.5])["result"]
# 139.4 GPa — longitudinal (Voigt): E1 = Vf*Ef + (1-Vf)*Em

runtime.execute("composites", "inverse_rule_of_mixtures", [0.6, 230.0, 3.5])["result"]
# 8.554729011689691 GPa — transverse (Reuss): 1/E2 = Vf/Ef + (1-Vf)/Em
```

`halpin_tsai` is a third, semi-empirical model for the same transverse direction, tunable through a
reinforcement-geometry factor `xi` (2.0 is the textbook value for circular fibers) rather than the
Reuss bound's implicit assumption of perfectly uniform stress:

```python
runtime.execute("composites", "halpin_tsai", [0.6, 230.0, 3.5, 2.0])["result"]
# 17.614243323442132 GPa — more than double the Reuss estimate for the same Vf, Ef, Em
```

The gap between 8.55 GPa and 17.61 GPa is not a bug in either function — Reuss is a lower-bound
approximation that assumes equal stress in fiber and matrix, and Halpin-Tsai's `xi` corrects for
the fact that real transverse loading does not actually split stress that way. Composite density
and specific stiffness follow directly from the same `Vf`:

```python
runtime.execute("composites", "composite_density", [0.6, 1.8, 1.2])["result"]
# 1.56 g/cm³ — 1.8 g/cm³ carbon fiber, 1.2 g/cm³ epoxy

runtime.execute("composites", "specific_stiffness", [139.4, 1.56])["result"]
# 89.35897435897436 — E1 / density, the stiffness-to-weight ratio composites are chosen for
```

## Concrete: one ratio drives strength, slump, and shrinkage together

Water-cement ratio is the input every strength and workability function in this module keys off:

```python
runtime.execute("concrete", "compressive_strength_abrams", [96.5, 3.4, 0.5])["result"]
# 17.628960071088894 MPa — Abrams' law, fc = a * exp(-b * wc), with representative a/b constants

runtime.execute("concrete", "slump_estimate", [0.5])["result"]
# 60.0 mm — slump_mm = 300 * (wc - 0.3), clamped at 0 below wc = 0.3

runtime.execute("concrete", "drying_shrinkage_estimate", [0.5, 70.0])["result"]
# 9.000000000000001e-05 — higher wc and lower aggregate fraction both increase shrinkage strain
```

`compressive_strength_abrams` takes `a` and `b` as caller-supplied coefficients rather than
hardcoding a single calibration — the module's own docstring lists no default values, so the
constants above (`a = 96.5`, `b = 3.4`) are representative of a normal-strength mix, not a fixed
constant the kernel assumes; a real mix design calibrates `a`/`b` against trial batches first.
Once a strength is known, the module's other functions derive stiffness and durability from it:

```python
runtime.execute("concrete", "modulus_of_elasticity", [32.0])["result"]
# 26587.214972614187 MPa — Ec = 4700 * sqrt(fc), the ACI 318 formula

runtime.execute("concrete", "splitting_tensile_strength", [32.0])["result"]
# 3.1678383797157332 MPa — ft = 0.56 * sqrt(fc)

runtime.execute("concrete", "carbonation_depth", [3.0, 25.0])["result"]
# 15.0 mm — d = k * sqrt(t); a k of 3 mm/sqrt(year) reaches 15 mm of carbonation front at 25 years

runtime.execute("concrete", "rebar_development_length", [20.0, 420.0, 32.0])["result"]
# 662.9126073623883 mm — a 20 mm bar at 420 MPa yield needs ~663 mm of embedment in fc = 32 MPa concrete
```

`slump_estimate` and `maturity_nurse_saul` both clamp: slump never goes negative (returns `0.0`
below `wc = 0.3` rather than a negative slump), and maturity returns `0.0` rather than a negative
value when the curing temperature is below the datum temperature — a batch curing below freezing
(with a typical -10C datum) is reported as gaining zero maturity, not negative maturity.

## Ceramics: the same mean strength implies different failure odds at different stresses

`weibull_failure_probability` is the module's central function — brittle ceramics fail
statistically because of pre-existing flaws, not at one fixed stress, and the Weibull modulus `m`
controls how sharply the failure probability rises once stress passes the characteristic strength:

```python
runtime.execute("ceramics", "weibull_failure_probability", [240.0, 300.0, 10.0])["result"]
# 0.10181047660792186 — at 80% of characteristic strength, m=10: ~10% failure probability

runtime.execute("ceramics", "weibull_failure_probability", [300.0, 300.0, 10.0])["result"]
# 0.6321205588285577 — at exactly the characteristic strength: 1 - 1/e, true for any m

runtime.execute("ceramics", "weibull_failure_probability", [360.0, 300.0, 10.0])["result"]
# 0.9979537295233215 — at 120% of characteristic strength: essentially certain failure
```

The `stress == sigma0` case always returns `1 - exp(-1) = 0.6321205588285577` regardless of `m` —
that is the definition of the characteristic strength, not a coincidence of the numbers chosen
above. Porosity's effect on stiffness is a separate exponential decay, not tied to the Weibull
statistics:

```python
runtime.execute("ceramics", "youngs_modulus_porosity", [380.0, 0.05, 3.5])["result"]
# 318.9936678922988 GPa — dense alumina (E0=380 GPa) at 5% porosity

runtime.execute("ceramics", "youngs_modulus_porosity", [380.0, 0.20, 3.5])["result"]
# 188.7024154407356 GPa — the same material at 20% porosity loses more than half its stiffness
```

`thermal_shock_resistance` folds strength, stiffness, expansion, and Poisson's ratio into a single
number in kelvin — the higher it is, the larger a sudden temperature change the material can
survive without cracking:

```python
runtime.execute("ceramics", "thermal_shock_resistance", [300.0, 380000.0, 8e-6, 0.22])["result"]
# 76.97368421052632 K — alumina: 300 MPa strength, 380 GPa modulus, 8e-6/K expansion, nu=0.22
```

`weibull_characteristic_strength` is explicitly the simplified case: its docstring and body both
say the `1.1x` mean-to-characteristic conversion factor is calibrated for `m ~ 10`, and the
function does not actually use its own `m` argument in the computation — it is accepted for
interface symmetry with the rest of the module, not read.

## Polymer: molecular weight, chain size, and conversion from the same handful of ratios

`degree_of_polymerization`, `number_average_mw`, and `weight_average_mw` chain together the way a
real characterization workflow does — monomer molecular weight and Mn in, PDI out, Mw derived:

```python
runtime.execute("polymer", "degree_of_polymerization", [100000.0, 100.16])["result"]
# 998.4025559105431 — Mn = 100,000 g/mol over an MMA-like 100.16 g/mol monomer

runtime.execute("polymer", "carothers_conversion", [200.0])["result"]
# 0.995 — p = 1 - 1/DP; a step-growth polymer needs 99.5% monomer conversion to reach DP=200

runtime.execute("polymer", "mark_houwink", [0.0075, 100000.0, 0.70])["result"]
# 23.71708245126285 mL/g — [eta] = K * Mw^a, representative PMMA-in-acetone K/a values
```

`glass_transition_fox` blends two homopolymer Tg values by weight fraction — note the inputs are
absolute kelvin, and the blend's Tg sits between the two components, closer to whichever has the
larger weight fraction:

```python
runtime.execute("polymer", "glass_transition_fox", [0.5, 373.0, 0.5, 354.0])["result"]
# 363.25171939477303 K — 50/50 blend of Tg=373K and Tg=354K homopolymers
```

`end_to_end_distance` and `radius_of_gyration` model an ideal freely-jointed chain — `radius_of_gyration`
takes the *result* of `end_to_end_distance` as its own input, not the raw bond count, so the two
calls chain together:

```python
r_end = runtime.execute("polymer", "end_to_end_distance", [1000.0, 0.154])["result"]
r_end
# 4.869907596659304 nm — 1000 bonds of length 0.154 nm (a C-C backbone bond), R = l*sqrt(n)

runtime.execute("polymer", "radius_of_gyration", [r_end])["result"]
# 1.9881314510531407 nm — Rg = R / sqrt(6)
```

## Rubber: hardness, set, and swelling are all normalized-difference ratios

`shore_a_to_youngs_modulus` is a single empirical exponential — `E = 0.5 * exp(0.04 * shore_a)` —
and the curve is genuinely steep: going from a soft 40 Shore A compound to a hard 90 pushes the
estimated modulus up by a factor of roughly 7.4, not the roughly 2x a linear reading of the 40-90
scale would suggest:

```python
runtime.execute("rubber", "shore_a_to_youngs_modulus", [40.0])["result"]
# 2.4765162121975575 MPa

runtime.execute("rubber", "shore_a_to_youngs_modulus", [90.0])["result"]
# 18.299117221838994 MPa
```

`tensile_set`, `compression_set`, and `elongation_at_break` are all the same shape — a change in
length or thickness normalized against a reference span — but each module's docstring specifies a
*different* reference span, so the three are not interchangeable formulas with renamed arguments:

```python
runtime.execute("rubber", "tensile_set", [200.0, 100.0, 110.0])["result"]
# 10.0% — (recovered - original) / (stretched - original) * 100: normalizes against total stretch

runtime.execute("rubber", "elongation_at_break", [600.0, 100.0])["result"]
# 500.0% — (final - original) / original * 100: normalizes against original length only
```

`crosslink_density_estimate` is the one function in this family that reaches for the ideal-rubber
elasticity relation directly, `nu = E / (3*R*T)`, so its inputs are in SI base units (pascals,
kelvin) rather than the MPa/mm units the rest of the module favors:

```python
runtime.execute("rubber", "crosslink_density_estimate", [2.0e6, 298.0, 8.314])["result"]
# 269.08064293052496 mol/m³ — a 2 MPa modulus rubber at room temperature (298 K)
```

## Zero-denominator handling is not consistent across the family

These six modules do not share a common guard convention, and the difference is a real behavioral
gap rather than a stylistic one:

- **`adhesives` has no guards at all.** Every one of its twelve functions is a direct arithmetic
  expression — `lap_shear_strength(5000.0, 0.0)` divides by a zero bond area and returns `inf`,
  `bond_area_from_load` with a zero `allowable_stress` does the same, and nothing in the module
  catches it before returning.
- **`ceramics` guards every division with an epsilon tolerance**, `fabs(denominator) < 1e-30`,
  returning `0.0` rather than dividing — this catches an exact zero and anything close enough to
  round to it, but a legitimately tiny nonzero denominator (say `1e-25`) still passes through and
  can produce a very large but finite result rather than `inf`. **`concrete` mixes the same epsilon
  pattern with plain `<= 0.0` checks in the same file** — `water_cement_ratio` and `cement_content`
  use `fabs(x) < 1e-30`, while `modulus_of_elasticity`, `splitting_tensile_strength`,
  `carbonation_depth`, and `rebar_development_length` use `fc_mpa <= 0.0` / `time_years <= 0.0` /
  `fc <= 0.0` instead — stricter in one direction (a small positive `fc` is accepted where an
  epsilon guard would too) but with no epsilon band at all.
- **`composites` guards with a plain `<= 0.0` check** on densities, moduli, and areas — this is
  stricter than the epsilon versions (a small positive value is not zero and is accepted) but also
  refuses legitimate zero-and-below inputs uniformly by returning `0.0`, folding "invalid input" and
  "mathematically undefined" into the same sentinel.
- **`polymer` and `rubber` mix exact `== 0.0` checks with `<= 0.0` checks in the same module,** not
  an epsilon band anywhere. `polymer`'s `degree_of_polymerization` (`m0 == 0.0`),
  `polydispersity_index` (`mn == 0.0`), and `glass_transition_fox` (`tg1 == 0.0`/`tg2 ==
  0.0`/`inv_tg == 0.0`) all only catch a denominator that is *exactly* zero in floating point — a
  value like `1e-300` that is effectively zero for any physical purpose still divides through and
  returns a finite-looking but meaningless huge number instead of the `0.0` sentinel the exact-zero
  path would have produced. `polymer`'s own `mark_houwink` and `end_to_end_distance`, right next to
  those, guard with `<= 0.0` instead. `weight_average_mw` (a plain multiply, `mn * pdi`) has no
  guard at all, but also has no division to protect. `rubber`'s `tensile_set` and
  `compression_set` follow the exact `== 0.0` pattern on their length-difference denominators, while
  its `elongation_at_break`, `tear_strength`, `resilience_rebound`, `swelling_percentage`, and
  `abrasion_loss_volume` use `<= 0.0`, matching `composites`' stricter convention within the same
  module.

None of this is documented as a deliberate design choice in the source — it reads as each module
having been written independently against the same "return `0.0` instead of a garbage value"
intent, with the exact threshold left to whichever guard the author reached for.

## Verification

All six `mojo/tests/libs/test_{adhesives,composites,concrete,ceramics,polymer,rubber}.mojo` files
are auto-generated coverage smoke tests: each calls every function once with a shared fixture (most
arguments fixed at `0.5`) and checks only that the result is finite, never pinning a specific
numeric output. None of the worked examples above come from those files — every number was
hand-computed independently in Python against the real formulas in `mojo/engine/adhesives.mojo`,
`composites.mojo`, `concrete.mojo`, `ceramics.mojo`, `polymer.mojo`, and `rubber.mojo`, then
cross-checked against the physical relationships each formula is named for (the Weibull
`1 - exp(-1)` identity at `stress == sigma0`, the Voigt/Reuss bounds bracketing Halpin-Tsai, the
Arrhenius direction of viscosity with temperature) before being presented here. Every number given
can be reproduced by re-running the same arithmetic against the source.

**Next:** see metallurgical strengthening and hardenability in
[Corrosion and electrochemical materials kernels](corrosion-and-electrochemical-materials-kernels.md),
or browse the [Runtime library catalog](runtime-library-catalog.md) for every module and function.
