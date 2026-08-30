---
icon: industry
description: Small scalar-formula libraries for eight process and organic-materials domains — brewing, bioprocess fermentation, food science, fragrance chemistry, pulp and paper, timber, textiles, and combustion.
---

# Process and organic-materials science kernels

Eight modules, none of which import each other, covering the arithmetic a process or materials
engineer reaches for by hand: converting a hydrometer reading to alcohol content, sizing a hop
addition's bitterness, working out a thermal-processing schedule's lethality, converting yarn
count between unit systems, or estimating a fuel's stoichiometric air requirement. Every function
takes and returns plain `Float64` (one, `perfumery.fragrance_strength_scale`, returns `Int`) — there
are no structs and no shared status-code vocabulary, and nothing is imported between modules, so a
formula duplicated across two domains (there is exactly one, below) is duplicated in full rather
than shared.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# 200 g of glucose fermented to completion: ethanol and CO2 masses sum to exactly
# the glucose consumed, because the yield coefficients (0.511 + 0.489) equal 1.000
runtime.execute("fermentation", "ethanol_yield", [200.0])["result"]
# 102.2
runtime.execute("fermentation", "carbon_dioxide_produced", [200.0])["result"]
# 97.8

# stoichiometric air-fuel ratio for methane (mass fractions C=0.75, H=0.25, no
# fuel-bound oxygen) -- the formula lands on the textbook 17.2:1 value
runtime.execute("combustion", "stoichiometric_air_fuel_ratio", [0.75, 0.25, 0.0])["result"]
# 17.167381974248926
```

## The modules

| Module | What it does |
| --- | --- |
| `brewing` | Homebrewing calculations: gravity/Plato conversion, ABV, apparent and real attenuation, Tinseth hop bitterness (IBU) and utilization, mash water volume, strike water temperature, SRM color, calorie estimation, and priming sugar. |
| `fermentation` | Bioprocess and fermentation kinetics: ethanol/CO2 yield from glucose (Gay-Lussac), Monod growth with ethanol inhibition, substrate consumption, volumetric productivity, fermentation efficiency, oxygen transfer (kLa), buffer capacity (van Slyke), and metabolic heat generation. |
| `food_science` | Food processing and preservation: water activity, pH from [H+], Q10 shelf-life scaling, thermal death time, D-value and pasteurization-unit temperature scaling, °Brix to sugar concentration, Atwater caloric density, wet/dry-basis moisture content, freezing-point depression, and blanching time. |
| `perfumery` | Fragrance formulation: parfum concentration, dilution ratio, relative evaporation rate, the three fixed note-duration constants, triangle-accord balance, tenacity, sillage, cost per mL, a 0-4 fragrance-strength scale, and ingredient proportion. |
| `paper_science` | Pulp and paper testing: basis weight, caliper-derived density and bulk, tearing/tensile/burst indices, Canadian Standard Freeness, kappa-number-to-lignin, pulp yield, moisture content, stiffness index, and recycled fiber content. |
| `wood_science` | Timber and wood material science: moisture content, fiber saturation point, shrinkage coefficient, modulus of rupture and elasticity (three-point bending), density-at-moisture-content, thermal conductivity, fire-exposure charring rate, section modulus, and Janka hardness. |
| `textile` | Yarn and fabric metrology: tex/denier conversion, English cotton count, fiber tex from diameter and density, twist per meter and twist multiplier, fabric GSM and cover factor, pilling resistance, moisture regain, shrinkage percentage, and breaking tenacity. |
| `combustion` | Combustion thermodynamics and emissions: stoichiometric air-fuel ratio, equivalence ratio, excess air, adiabatic flame temperature, methane LHV, thermal and Carnot efficiency, brake-specific fuel consumption, combustion efficiency, laminar flame speed, a Zeldovich-style NOx rate, and heat release rate. |

## One formula, two modules

`brewing.abv_from_og_fg(og, fg)` and `fermentation.alcohol_by_volume(original_gravity,
final_gravity)` are the identical formula, `(og - fg) * 131.25`, defined independently in two
files with different parameter names. Calling either with the same two gravities returns the same
number:

```python
runtime.execute("brewing", "abv_from_og_fg", [1.050, 1.010])["result"]
# 5.250000000000004
runtime.execute("fermentation", "alcohol_by_volume", [1.050, 1.010])["result"]
# 5.250000000000004
```

`5.250000000000004`, not exactly `5.25` — `0.04 * 131.25` does not land on an exact binary
fraction in `Float64`, the same kind of last-bit rounding noted elsewhere in this corpus for
transcendental functions. This is the classic simplified homebrewing ABV formula (a linear
approximation, good to roughly ±0.2 percentage points against the denser true-gravity formula);
neither module implements the more precise version.

## Brewing: attenuation, color, and a percent that means a fraction

Chaining the gravity-based functions on a 1.050 → 1.010 batch:

```python
runtime.execute("brewing", "apparent_attenuation", [1.050, 1.010])["result"]
# 80.0  -- (1.050 - 1.010) / (1.050 - 1.0) * 100, exact
runtime.execute("brewing", "real_attenuation", [80.0])["result"]
# 65.536  -- 80.0 * 0.8192 (Balling correction), also exact
```

`ibu_tinseth`'s docstring labels its second argument `AA%`, and the parameter itself is named
`alpha_acid_pct`, but the arithmetic — `(utilization * alpha_acid_pct * weight_oz * 7490.0) /
volume_gal` — expects that value as a **decimal fraction**, not the raw percent number printed on a
hop package. A real 5.5%-alpha-acid hop passed as `5.5` inflates the result 100x:

```python
u = runtime.execute("brewing", "utilization_tinseth", [1.050, 60.0])["result"]
# 0.2306640772510991  -- ~23% utilization at 60 min in a 1.050 wort

runtime.execute("brewing", "ibu_tinseth", [u, 0.055, 1.0, 5.0])["result"]  # 0.055, not 5.5
# 19.004413324718055  -- matches published Tinseth-calculator output for
#                        1 oz of 5.5% AA hops, 60 min boil, 5 gal batch

runtime.execute("brewing", "ibu_tinseth", [u, 5.5, 1.0, 5.0])["result"]   # the tempting mistake
# 1900.4413324718055 -- not a plausible IBU for any real beer
```

The parameter name and docstring shorthand do nothing to prevent that mistake; this is the
real-world Tinseth-formula convention (percent-as-decimal), not an error specific to this
implementation, but it is easy to get backwards on a first read.

`color_srm_from_mcu` (the Morey equation, `1.4922 * MCU^0.6859`) and `utilization_tinseth` both
compute their non-integer power as `exp(exponent * log(x))` rather than calling a `pow` function —
`color_srm_from_mcu(8.0)` returns `6.212357754455404`. `food_science.d_value_from_z`,
`pasteurization_units`, `shelf_life_q10`, and `combustion.flame_speed_laminar` use the identical
`exp`/`log` idiom for their own exponentiation; only `wood_science` imports a real `pow` from
`std.math` and calls it directly. Both approaches give the same answer up to floating-point
rounding — it is a style difference between modules, not a behavioral one.

## Fermentation: a mass balance that sums to exactly one

`ethanol_yield(glucose_g) = 0.511 * glucose_g` and `carbon_dioxide_produced(glucose_g) = 0.489 *
glucose_g` are independent one-line functions with no shared code, but their coefficients are the
Gay-Lussac stoichiometric split of glucose fermentation (`C6H12O6 → 2 C2H5OH + 2 CO2`) and sum to
`1.000` exactly, so for any input the two outputs always add back up to the glucose consumed (the
`200.0` example above: `102.2 + 97.8 = 200.0`, not an approximation).

`yeast_growth_rate(mu_max, substrate_conc, ks, ethanol_conc)` combines Monod substrate limitation
with a linear ethanol-inhibition term capped at zero — above `100.0` g/L ethanol (the function's
hardcoded `pm`), growth stops rather than going negative:

```python
runtime.execute("fermentation", "yeast_growth_rate", [0.4, 10.0, 2.0, 30.0])["result"]
# 0.23333333333333334  -- mu_max=0.4/h, S=10 g/L, Ks=2 g/L, ethanol=30 g/L

runtime.execute("fermentation", "yeast_growth_rate", [0.4, 10.0, 2.0, 120.0])["result"]
# 0.0  -- same substrate state, but ethanol=120 g/L clears the 100 g/L cap; growth
#         is clamped to zero rather than returning a negative rate
```

## Food science: two functions sharing one temperature-scaling skeleton

`d_value_from_z(d_ref, z_value, temp, ref_temp)` and `pasteurization_units(time_min, temp,
z_value, ref_temp)` both compute a `10^(ΔT/z)` scaling factor via `exp(exponent * log(10))`, and
differ only in the sign of `ΔT` (`ref_temp - temp` for the D-value, `temp - ref_temp` for
pasteurization units) and in which argument the scaling factor multiplies. A thermal-processing
schedule at 65°C against a 60°C reference with `z = 7.5°C`:

```python
runtime.execute("food_science", "pasteurization_units", [10.0, 65.0, 7.5, 60.0])["result"]
# 46.41588833612779  -- 10 min * 10^((65-60)/7.5)
```

**None of `food_science`'s twelve functions guard a zero denominator.** `moisture_content_wet_basis`,
`moisture_content_dry_basis`, and `blanching_time_estimate` divide by their second argument with no
check; passed `0.0` they return `inf` rather than a defined sentinel. `paper_science` and
`perfumery` share the same property (see below) — three of this family's eight modules have zero
division guards anywhere in the module.

## Perfumery: three constants, and a threshold that zeroes the whole result

`top_note_duration()`, `middle_note_duration()`, and `base_note_duration()` take no arguments and
always return the same fixed values — `30.0`, `240.0`, `1440.0` minutes — regardless of what
fragrance is being modeled; they are named constants dressed as functions, not calculations.

`triangle_accord_balance(top_pct, mid_pct, base_pct)` returns `0.0` — not an error, not the closest
valid value — the instant any one of the three percentages is at or below `15.0`, even if the
other two are strongly balanced:

```python
runtime.execute("perfumery", "triangle_accord_balance", [30.0, 40.0, 30.0])["result"]
# 30.0  -- all three clear 15%; returns the minimum of the three
runtime.execute("perfumery", "triangle_accord_balance", [10.0, 60.0, 30.0])["result"]
# 0.0  -- top=10.0 fails the threshold alone, even though mid and base are well balanced
```

Two of perfumery's twelve functions do have an `if` check — `fragrance_strength_scale`'s
`concentration_pct <= 0.0` branch and `triangle_accord_balance`'s threshold above — but neither one
guards a division: `fragrance_strength_scale` has no division to protect, and
`triangle_accord_balance` returns a plain minimum. The six functions that do divide
(`concentration_parfum`, `dilution_ratio`, `evaporation_rate_relative`, `tenacity_hours`,
`cost_per_ml`, `ingredient_proportion`) all do so unguarded — `perfumery` joins `food_science` and
`paper_science` as a module with zero protection against a zero denominator.

## Paper science: an index family built on one denominator

Eight of `paper_science`'s twelve functions are a ratio against `basis_weight_gsm` (tearing,
tensile, and burst index, bulk, caliper-to-density, stiffness index) or against another simple
total (pulp yield, recycled fiber content) — the same normalize-by-basis-weight shape repeated with
a different numerator and unit-scaling constant each time:

```python
runtime.execute("paper_science", "basis_weight", [80.0, 1.0])["result"]
# 80.0 g/m^2 -- a standard 80 gsm office-paper sheet, 1 m^2, weighing 80 g
runtime.execute("paper_science", "caliper_to_density", [80.0, 0.1])["result"]
# 0.8 g/cm^3 at a 0.1 mm caliper -- a realistic bulk density for that paper grade
runtime.execute("paper_science", "pulp_yield", [480.0, 1000.0])["result"]
# 48.0 percent -- typical for kraft (chemical) pulping of 1000 kg of wood
```

`freeness_csf(drainage_ml)` is an identity function — it returns its input unchanged. The docstring
says as much ("Returns drainage value directly"); the function exists so callers go through the
same `runtime.execute("paper_science", ...)` path as every other freeness-adjacent calculation
rather than reading the raw drainage measurement directly.

## Wood science: density that falls as moisture rises

`wood_density_at_mc(basic_density, moisture_content_pct)` computes `basic_density * (1 + MC/100) /
(1 + MC/FSP)` with `FSP` hardcoded to `30.0` inside the function — it does not call this same
module's own `fiber_saturation_point(basic_density)`, so a species whose fiber saturation point
differs from 30% still gets divided by 30 regardless of its actual basic density. Because `MC/30`
grows faster than `MC/100` for any positive MC, the reported density **decreases** as moisture
content rises from oven-dry:

```python
runtime.execute("wood_science", "wood_density_at_mc", [0.45, 12.0])["result"]
# 0.3600000000000001  -- lower than the 0.45 basic (oven-dry) density it started from
runtime.execute("wood_science", "wood_density_at_mc", [0.45, 0.0])["result"]
# 0.45  -- at MC=0 the two correction terms cancel exactly, returning basic_density unchanged
```

Whether that direction matches how a specific wood species actually behaves near its own fiber
saturation point depends on how `basic_density` was measured (oven-dry mass over green vs. oven-dry
volume); the function itself just evaluates the formula as written, against a fixed `FSP = 30`, for
any `basic_density` passed in.

`wood_hardness_janka(density_g_cm3)` — `6139*ρ² - 766*ρ + 35`, a published empirical fit — and
`charring_rate(duration_min, charring_coeff)` — `charring_coeff * duration_min^0.813`, another
published power-law fit, whose own guard rejects a negative duration or coefficient before the
power is taken — round out the module alongside a standard three-point-bending pair,
`modulus_of_rupture` and `modulus_of_elasticity`, that both guard their bending-geometry denominator
against zero. Six of `wood_science`'s ten functions guard an input this way (`moisture_content`,
`shrinkage_coefficient`, `modulus_of_rupture`, `modulus_of_elasticity`, `wood_density_at_mc`, and
`charring_rate`) — the highest guard density in the family after `textile`.

## Textile: the most consistently guarded module in this family

Seven of `textile`'s twelve functions guard against a near-zero denominator, and most do it with an
epsilon threshold (`fabs(x) < 1e-30`) rather than an exact `== 0.0` comparison — `yarn_count_ne`,
`fabric_gsm`, `moisture_regain`, `shrinkage_percentage`, and `breaking_tenacity` all use this
pattern, catching a denominator that underflowed to a tiny non-zero value as well as an exact zero.
`twist_multiplier` and `fabric_cover_factor` instead guard with a plain `<= 0.0`.

```python
runtime.execute("textile", "tex_to_denier", [30.0])["result"]
# 270.0  -- D = tex * 9
runtime.execute("textile", "moisture_regain", [108.5, 100.0])["result"]
# 8.5  -- cotton's textbook 8.5% regain at standard atmosphere, wet=108.5 g, dry=100 g
```

## Combustion: a stoichiometric ratio that lands on the textbook value

`stoichiometric_air_fuel_ratio(c, h, o_fuel)` takes mass fractions of carbon, hydrogen, and
fuel-bound oxygen and returns `(c/12*32 + h/4*32 - o_fuel) / 0.233`. For methane (mass fractions
`C = 0.75`, `H = 0.25`, no fuel-bound oxygen), the function returns `17.167381974248926` — matching
the widely published `~17.2:1` stoichiometric air-fuel mass ratio for methane combustion, a real
external check the arithmetic passes rather than a value invented for this page.

`nox_formation_rate(temp, oxygen_fraction)` — `oxygen_fraction * exp(-38000.0 / temp)`, a
simplified Zeldovich-mechanism proxy — is extremely sensitive to temperature near typical flame
conditions:

```python
runtime.execute("combustion", "nox_formation_rate", [2200.0, 0.02])["result"]
# 6.303472372424238e-10
runtime.execute("combustion", "nox_formation_rate", [1800.0, 0.02])["result"]
# 1.3570346386032736e-11  -- 400 K cooler drops the rate roughly 46x
```

`heat_release_rate` is the only one of combustion's twelve functions with a guard (`gamma - 1.0 ==
0.0` returns `0.0` rather than dividing by zero); the other eleven — including `thermal_efficiency`,
`carnot_efficiency`, and `brake_specific_fuel_consumption` — divide their second argument unguarded.

## Refusal and edge-case behavior across the family

None of these eight modules can trigger the uncatchable worker-killing bounds abort documented
elsewhere in this corpus for out-of-range list indexing — every function here takes scalar
`Float64`/`Int` arguments, not lists, so there is no index to go out of range. The risk profile is
narrower: an unguarded division by zero is defined, IEEE-754 behavior (`inf` or `nan`), not a crash,
and it propagates silently through whatever the caller does with the result next. Guard density
varies sharply by module — of the functions in each module that actually perform a division (or, in
`charring_rate`'s case, a power whose base would go complex on a negative input), `textile` guards
7 of 12, `wood_science` guards 6 of 10, `fermentation` guards 5 of 10,
and `brewing` guards 4 of 12; `combustion` guards only 1 of 12 (`heat_release_rate`); and
`food_science`, `paper_science`, and `perfumery` guard **none** of their dividing functions — three
of the eight modules in this family will silently return `inf`/`nan` from a zero or near-zero
denominator rather than refuse it. A caller feeding user-supplied or measured data (a zero-area
fabric swatch, a zero-mass paper sample, a zero-volume fragrance batch) through one of those three
modules should validate denominators itself before the call, rather than relying on the kernel to
catch it.

## Verification

All eight `mojo/tests/libs/test_*.mojo` files behind this family (`test_brewing.mojo`,
`test_fermentation.mojo`, `test_food_science.mojo`, `test_perfumery.mojo`, `test_paper_science.mojo`,
`test_wood_science.mojo`, `test_textile.mojo`, `test_combustion.mojo`) are auto-generated coverage
smoke tests: each calls every function once with the literal argument `0.5` (repeated for each
declared parameter) and checks only that the result is finite — none pins a specific numeric
output. The worked examples above were hand-traced against the real formulas in
`mojo/engine/brewing.mojo`, `fermentation.mojo`, `food_science.mojo`, `perfumery.mojo`,
`paper_science.mojo`, `wood_science.mojo`, `textile.mojo`, and `combustion.mojo`, cross-checked
against independently-run Python arithmetic and, where one exists, a published real-world reference
value (Tinseth IBU, cotton moisture regain, methane's stoichiometric AFR) rather than against the
smoke tests' own `0.5` fixtures.

**Next:** see [Classical ML algorithms](ml-classical-algorithms.md) for a similarly self-contained,
independently-verified set of small formula modules, or the
[Runtime library catalog](runtime-library-catalog.md) for every module and function in the engine.
