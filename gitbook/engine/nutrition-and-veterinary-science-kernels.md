---
icon: weight-scale
description: Human energy-balance and body-composition formulas (BMI, Mifflin-St Jeor BMR, TDEE, macros) alongside weight-based veterinary dosing, fluid therapy, and per-species reference constants for dogs, cats, horses, and cattle.
---

# Nutrition and veterinary science kernels

Two modules for weight-driven clinical arithmetic in two different patients. `nutrition` is human
energy balance and body composition — the formulas behind a BMI reading, a daily calorie target, a
macro split, and a cardio zone. `veterinary` is the small-animal-practice equivalent: a per-kg drug
dose, a fluid-therapy rate, a caloric requirement, and a set of per-species reference constants
(gestation length, normal heart-rate range, packed-cell volume, blood volume, anesthetic MAC) keyed
by an integer species code. Both modules take and return plain `Float64`/`Int`/`List[Float64]`
values — no structs, no status-code vocabulary — so every function is a single formula that either
returns the right number or a visibly wrong one; neither module validates its inputs beyond what the
arithmetic itself happens to guard against, which matters more here than in most of this corpus
because a caller building a real dosing or diet tool on top of these numbers has no status code to
check.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("nutrition", "bmi", [70.0, 1.75])["result"]
# 22.857142857142858 -- BMI = weight_kg / height_m^2

runtime.execute("nutrition", "bmr_mifflin", [70.0, 175.0, 30, True])["result"]
# 1648.75 -- Mifflin-St Jeor, male: 10*70 + 6.25*175 - 5*30 + 5

runtime.execute("veterinary", "dose_mg", [25.0, 10.0])["result"]
# 250.0 -- a 25 kg dog at 10 mg/kg
```

## The modules

| Module | What it does |
| --- | --- |
| `nutrition` | Human energy-balance and body-composition formulas: BMI and its WHO-style category, Mifflin-St Jeor BMR, activity-scaled TDEE, a caloric-deficit target, an Atwater-factor macro split, Devine ideal body weight, Deurenberg body-fat percentage, a water-intake rule of thumb, and heart-rate-based cardio metrics (max HR, target zone, VO2max estimate). |
| `veterinary` | Weight-based small-animal dosing and fluid therapy (drug dose, fluid rate, dehydration deficit, canine maintenance fluids, canine resting energy requirement) plus per-species reference constants — gestation length, normal heart-rate range, packed-cell-volume midpoint, blood-volume estimate, and anesthetic MAC — addressed by an integer species code that only one of the seven species-coded functions actually implements for all four species the module documents. |

## `nutrition`: energy balance and body composition

| Function | What it does |
| --- | --- |
| `bmi(weight_kg, height_m)` | `weight_kg / height_m^2`. |
| `bmi_category(bmi_val)` | WHO-style classification: `0` underweight (`< 18.5`), `1` normal (`< 25.0`), `2` overweight (`< 30.0`), `3` obese (`>= 30.0`). |
| `bmr_mifflin(weight_kg, height_cm, age, is_male)` | Mifflin-St Jeor: `10*W + 6.25*H - 5*A + 5` for men, `10*W + 6.25*H - 5*A - 161` for women. |
| `tdee(bmr_val, activity_level)` | `bmr_val * activity_level`. The docstring names the intended range as `1.2`-`1.9` (sedentary to very active); the function does not clamp or validate it. |
| `caloric_deficit(tdee_val, target_loss_kg_per_week)` | `target_loss_kg_per_week * 7700 / 7` — the standard ~7700-kcal-per-kg-of-fat rule of thumb, spread over 7 days. `tdee_val` is accepted but never referenced in the arithmetic. |
| `macro_split(calories, protein_pct, fat_pct)` | `[protein_g, fat_g, carb_g]` from Atwater factors (protein and carb at 4 kcal/g, fat at 9 kcal/g). `carb_pct = 1 - protein_pct - fat_pct` is not clamped, so percentages that sum past `1.0` silently produce a negative carb figure rather than an error. |
| `ideal_body_weight(height_cm, is_male)` | Devine formula: `50 + 2.3*(inches - 60)` for men, `45.5 + 2.3*(inches - 60)` for women, where `inches = height_cm / 2.54`. The Devine formula is defined for adult heights at or above 60 inches (152.4 cm); below that the function still returns a number, just one the original formula was never validated for. |
| `body_fat_estimate(bmi_val, age, is_male)` | Deurenberg (1991): `1.20*BMI + 0.23*age - 10.8*sex - 5.4`, `sex = 1` for male, `0` for female. |
| `water_intake(weight_kg)` | `weight_kg * 0.033` liters/day — the common 33 mL/kg/day rule of thumb. |
| `heart_rate_max(age)` | `220 - age` (the Fox formula). |
| `target_heart_rate(hr_max, intensity_low, intensity_high)` | `[hr_max*intensity_low, hr_max*intensity_high]` — a percentage-of-max-HR zone, not the heart-rate-reserve (Karvonen) method, so it takes no resting heart rate. |
| `vo2max_estimate(hr_rest, hr_max)` | `15.3 * (hr_max / hr_rest)` (the Uth-Sørensen-Overgaard-Pedersen estimate). `hr_rest = 0` divides by zero rather than being guarded. |

**The formulas are the textbook ones, not simplifications of them.** Checking each against its
published source: Mifflin-St Jeor's `+5`/`-161` sex offset, Devine's `50`/`45.5` base weights and
`2.3` per-inch slope, and Deurenberg's `1.20`/`0.23`/`10.8`/`5.4` coefficients all match the original
equations exactly — nothing here is a rounded-off or partial reimplementation.

`tests/mojo/test_wave60.mojo` ("Wave 60 — Optics, Electrical Engineering, Nutrition Science", the
250-library-milestone wave) pins several of these against hand-worked values rather than just
range-checking them: `bmr_mifflin(70.0, 175.0, 30, True)` must equal `1648.75` exactly
(`10*70 + 6.25*175 - 5*30 + 5`), `tdee(1800.0, 1.55)` must equal `2790.0`, and
`macro_split(2000.0, 0.3, 0.3)` must split into `protein_g = 150.0`, `fat_g = 66.667`,
`carb_g = 200.0` — a split whose three components, fed back through the Atwater factors
(`150*4 + 66.667*9 + 200*4`), sum back to `2000.0` kcal to within the test's own `0.1` tolerance.

**`macro_split`'s missing clamp is reachable with ordinary-looking inputs.** A caller asking for a
40%-protein, 40%-fat plan — each individually plausible — gets `carb_pct = 1 - 0.4 - 0.4 = 0.2`, fine.
But 60%-protein, 50%-fat (a caller stacking two "high" targets without checking they still sum under
1.0) gives `carb_pct = -0.1`, and `macro_split` returns that as a genuine negative `carb_g` rather
than refusing — nothing in the function's `def` name or return type signals that the third slot can
go negative.

## `veterinary`: weight-based dosing and species reference constants

| Function | What it does |
| --- | --- |
| `dose_mg(weight_kg, dose_per_kg)` | `weight_kg * dose_per_kg` — a linear per-kg drug dose. |
| `fluid_rate_ml_hr(total_ml, hours)` | `total_ml / hours`. |
| `fluid_deficit(weight_kg, dehydration_pct)` | `weight_kg * dehydration_pct / 100 * 1000` mL — the standard fluid-deficit estimate; `dehydration_pct` is taken as a whole number (`8` for 8% dehydrated), not a fraction. |
| `maintenance_fluid_dog(weight_kg)` | `60 * weight_kg` mL/day. The module's own docstring calls this "simplified" — it is a flat per-kg rate rather than the allometric-scaling maintenance formulas (e.g. `~132 * weight^0.75`) veterinary practice uses across a wider weight range. |
| `caloric_requirement_dog(weight_kg)` | `70 * weight_kg^0.75` kcal/day — the standard interspecies Resting Energy Requirement (RER) allometric formula. Despite the `_dog` suffix, the `70*BW^0.75` equation itself is not dog-specific in veterinary nutrition (the same formula is the standard RER for cats and other mammals too); `_dog` names this module's one entry point for it, not a species restriction in the math. `weight_kg^0.75` is computed as `sqrt(sqrt(weight_kg^3))` via 20 fixed iterations of a private Newton's-method square root (`_sqrt_approx`), not a general power or logarithm routine. |
| `body_condition_score_ideal(species_code)` | Always returns `5.0` on the 1-9 BCS scale, regardless of `species_code` — the docstring's "Dog(0)=5.0, Cat(1)=5.0" describes the two species the rest of the module supports, but this particular function does not branch on its input at all. |
| `anesthesia_mac(species_code, agent_code)` | Typical minimum alveolar concentration: Dog/isoflurane `1.3`, Dog/sevoflurane `2.4`, Cat/isoflurane `1.6`, Cat/sevoflurane `3.1`. The branch is `species_code == 0` (Dog) vs. everything else (Cat) — Horse (`2`) and Cow (`3`), both named in the module's own species-code comment, silently receive Cat's MAC values. |
| `gestation_period_days(species_code)` | Dog `63`, Cat `65`, Horse `340`, Cow `283` days; any other code returns `0.0`. |
| `heart_rate_normal_range_low(species_code)` / `heart_rate_normal_range_high(species_code)` | Dog `60`-`140`, Cat `120`-`220`, Horse `28`-`44` bpm; Cow and any other code return `0.0` for both bounds. |
| `packed_cell_volume_normal(species_code)` | Dog `46.0`, Cat `37.5`; Horse, Cow, and any other code return `0.0`. |
| `blood_volume_estimate(weight_kg, species_code)` | Dog `90` mL/kg, Cat `60` mL/kg; Horse, Cow, and any other code return `0.0` regardless of `weight_kg`. |

**Seven of the twelve functions take a `species_code`; only one of those seven covers all four
species the module's header comment lists.** The file opens with `# Species codes: 0=Dog, 1=Cat,
2=Horse, 3=Cow`, and `gestation_period_days` is the only species-coded function that actually branches
on all four — every other one recognizes at most three (`heart_rate_normal_range_low`/`_high`, which
cover Dog/Cat/Horse and fall through to `0.0` for Cow) or just two (`packed_cell_volume_normal` and
`blood_volume_estimate`, Dog/Cat only; Horse and Cow both return `0.0`). `body_condition_score_ideal`
ignores `species_code` entirely.

**`anesthesia_mac` is the one case where the fallback is a wrong number, not an obviously-empty one.**
Every other species-coded function's fallback for an unlisted species is `0.0` — a value a caller
checking "did I get a real reading back" can catch. `anesthesia_mac` has no such tell: its `if
species_code == 0` branch means any non-zero code, including Horse (`2`) and Cow (`3`), falls through
to the Cat branch and returns a real-looking MAC value (`1.6` for isoflurane, `3.1` for sevoflurane)
that belongs to a different species. `anesthesia_mac(2, 0)` — Horse, isoflurane — returns `1.6`, Cat's
value, with nothing in the return distinguishing it from a genuine Horse reading.

A worked chain from `tests/mojo/test_wave86.mojo` ("Wave 86 — Paper Science, Radar, Veterinary"),
which pins exact values rather than just checking they're finite:

```python
runtime.execute("veterinary", "fluid_deficit", [10.0, 8.0])["result"]
# 800.0 -- a 10 kg patient, 8% dehydrated: 10 * 8 / 100 * 1000

runtime.execute("veterinary", "caloric_requirement_dog", [10.0])["result"]
# 393.6389276332444 -- RER = 70 * 10^0.75

runtime.execute("veterinary", "blood_volume_estimate", [25.0, 0])["result"]
# 2250.0 -- a 25 kg dog at 90 mL/kg
```

`caloric_requirement_dog(10.0)`'s expected value is independently reproducible outside the test file
too: `70 * 10**0.75 == 393.6389276332444` and `70 * 5**0.75 == 234.0591067417477` in plain Python,
matching the test's `393.64`/`234.06` comments to four significant figures — the module's
sqrt-of-sqrt-of-cube approximation of a fractional power reproduces the closed-form result to full
double precision for both weights checked.

## Verification

`mojo/tests/libs/test_nutrition.mojo` and `mojo/tests/libs/test_veterinary.mojo` are auto-generated
coverage smoke tests: each calls every function once with fixed placeholder arguments (`0.5`, small
integers) and checks only that a `Float64` result is finite, or that a list has non-negative length —
they pin no specific numeric output and would not catch a sign error or a swapped coefficient.

The real numeric assertions live in the wave-suite files instead: `tests/mojo/test_wave60.mojo` pins
`bmi`, `bmr_mifflin`, `tdee`, `caloric_deficit`, `macro_split`, `water_intake`, `heart_rate_max`,
`target_heart_rate`, and `vo2max_estimate` against exact hand-computed values (plus range checks on
`ideal_body_weight` and `body_fat_estimate`), and `tests/mojo/test_wave86.mojo` pins all twelve
`veterinary` functions, including every species/agent combination `anesthesia_mac`, `gestation_period_days`,
`heart_rate_normal_range_low`, `heart_rate_normal_range_high`, and `packed_cell_volume_normal` actually
implement. The worked examples in this page are drawn from those pinned assertions, and the
`caloric_requirement_dog` values were independently re-derived in plain Python (`70 * w**0.75`) to
confirm the module's iterative square-root approximation of the fractional power is not losing
precision anywhere the test tolerance would hide.

**Next:** see the full function list in the [Runtime library catalog](runtime-library-catalog.md), or
browse the [Engine catalog](catalog.md) for how `nutrition` and `veterinary` are exposed alongside
every other engine.
