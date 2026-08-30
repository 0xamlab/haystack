---
icon: stethoscope
description: Textbook clinical formulas for seven specialties -- cardiac hemodynamics, dental/oral-health indices, hormone physiology, kidney function, eye optics, orthodontic biomechanics, and lung function -- as plain scalar-in, scalar-out arithmetic.
---

# Clinical specialty kernels

Seven modules, one per medical specialty, each a direct implementation of the named-equation
formulas a clinician already uses on paper: Cockcroft-Gault and CKD-EPI for kidney function, the
alveolar gas equation for lung function, HOMA-IR for insulin resistance, Snellen-to-decimal
conversion for visual acuity, DMFT for dental caries burden, and Euler beam theory for orthodontic
wire force. Every function takes and returns plain `Float64` (dental counts also take/return `Int`)
— there are no patient records, no structs, and no clinical-decision output; each call is one named
formula evaluated on the numbers you already measured; interpreting the result against a reference
range is left to the caller.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# CKD-EPI eGFR: 60-year-old woman, serum creatinine 1.0 mg/dL
runtime.execute("nephrology", "gfr_ckd_epi", [1.0, 60.0, 1.0])["result"]
# 61.18505161746657 -- mL/min/1.73m^2, stage G2 (mildly reduced)

# the alveolar gas equation on room air at sea level
runtime.execute("pulmonology", "alveolar_oxygen", [0.21, 40.0, 760.0])["result"]
# 99.73 -- PAO2 in mmHg, the textbook ~100 mmHg room-air value
```

## The modules

| Module | What it does |
| --- | --- |
| `cardiology` | Hemodynamics: cardiac output (rate * volume and Fick's principle), stroke volume, ejection fraction, MAP, pulse pressure, systemic vascular resistance, rate-pressure product, LV stroke work, and coronary perfusion pressure. |
| `dentistry` | General dental/oral-health metrics: the DMFT caries index and its population prevalence, plaque and gingival indices, clinical attachment loss, alveolar bone loss, local-anesthetic dosing, restoration-longevity and treatment-cost estimates. |
| `endocrinology` | Hormone physiology: HOMA-IR insulin resistance, cortisol's diurnal cosine rhythm, free-hormone fractions (thyroid, testosterone), closed-loop feedback gain, receptor Bmax from Scatchard analysis, and IGF-1-driven growth rate. |
| `nephrology` | Kidney function: eGFR (CKD-EPI) and creatinine clearance (Cockcroft-Gault), fractional excretion of sodium, urine anion gap, TTKG, renal plasma flow, filtration fraction, osmolar and free-water clearance, and urine protein/creatinine ratio. |
| `ophthalmology` | Eye optics: Snellen-to-decimal visual acuity, spherical refractive error, the lensmaker's equation, Goldmann IOP with corneal-thickness correction, keratometry-to-corneal-radius, retinal image size, depth of focus, CFF, contrast sensitivity, and dark-adaptation kinetics. |
| `orthodontics` | Tooth-movement biomechanics: force/optimal-force movement rate, moment-to-force ratio, anchorage load per tooth, Euler-beam arch-wire force and bracket torque, Bolton and Pont indices, Little's-irregularity arch perimeter, cephalometric growth discrepancy, and viscoelastic retainer-force decay. |
| `pulmonology` | Lung function: predicted (ARDSnet) tidal volume, minute and alveolar ventilation, FEV1/FVC, %-predicted PEF, the alveolar gas equation, A-a gradient, respiratory quotient, static compliance, and airway resistance. |

## Two mismatches with a naive reading of the specialty names

**`cardiology` is entirely hemodynamics — there is no ECG or QT-interval arithmetic here at all.**
Reading `mojo/engine/cardiology.mojo`'s ten functions end to end: cardiac output (two ways — rate *
stroke volume, and the Fick principle from oxygen consumption), stroke volume, ejection fraction,
mean arterial pressure, pulse pressure, systemic vascular resistance, rate-pressure product, left
ventricular stroke work, and coronary perfusion pressure. Every input and output is a pressure,
volume, flow, or rate — QT correction (Bazett/Fridericia), heart-rate-corrected intervals, or any
other electrophysiology formula simply is not part of this module's scope, contrary to what its name
alone might suggest to someone expecting ECG arithmetic. If a corrected-QT formula exists anywhere
in this codebase it is not here.

**`dentistry` and `orthodontics` are real siblings, but they share zero functions.** Both files'
docstrings frame themselves as dental: `dentistry.mojo` is "Dental Science Library," and
`orthodontics.mojo` is "Dental and orthodontic biomechanics calculations." Reading both source files
in full confirms the split is clean rather than accidental duplication: `dentistry` is general
oral-health epidemiology and restorative dentistry — DMFT caries scoring, plaque/gingival indices,
periodontal attachment loss, fluoride dosing, anesthetic dosing, restoration longevity, treatment
cost — none of it involves an applied force or a wire. `orthodontics` is exclusively the physics of
moving teeth — PDL force response, moment-to-force ratios, anchorage load, Euler-beam wire
deflection force, bracket torque, Bolton/Pont arch-size indices, Little's irregularity index,
cephalometric growth prediction, and viscoelastic retainer relaxation — none of it involves an index
score, a caries count, or a drug dose. There is no name collision and no formula computed twice under
two names; the hint's framing of orthodontics as "a specialization of dentistry" holds at the level
of medical taxonomy, but at the code level these are two disjoint, non-overlapping libraries that
happen to sit in adjacent files.

## A docstring that omits a real unit-conversion factor

`ophthalmology.depth_of_focus`'s docstring states the formula as
`DoF ~= 2 * VA_arcmin / (3438 * pupil_mm)` diopters, but the code itself computes
`2.0 * visual_acuity_arcmin / (3438.0 * pupil_diameter_mm / 1000.0)` — which is exactly `1000x`
larger than what the docstring's own algebraic expression describes. Deriving the formula
independently from thin-lens defocus geometry confirms the *code* is the one that is dimensionally
correct, not the docstring: a defocus of `delta` diopters spreads a blur circle of diameter
`c = f' * a * delta` on the retina (`f'` the eye's ~17 mm posterior focal length, `a` the pupil
diameter), and setting that blur circle's angular subtense equal to the eye's minimum angle of
resolution and solving for `delta` reproduces the code's `2000 * VA_arcmin / (3438 * pupil_mm)`
term-for-term — the `1000` comes from converting the 17 mm focal length into millimeters twice over
in the derivation, a step the docstring's shorthand silently drops. Numerically, a 3 mm pupil at
20/20 acuity (`VA_arcmin = 1`) gives `depth_of_focus(3.0, 1.0) = 0.1939` diopters under the code —
physiologically the right order of magnitude for a photopic pupil — while the docstring's literal
formula, evaluated the same way, would give `0.000194` diopters, three orders of magnitude too small
to be a real depth-of-focus value. The function is correct; its docstring's written-out formula is
missing the conversion factor that makes it correct, the same category of docstring/code mismatch
flagged in earlier kernel-family write-ups in this corpus.

## Two independent formulas for the same measurement, deliberately kept simple

`nephrology` carries both `gfr_ckd_epi` and `creatinine_clearance_cockroft` rather than picking one.
The CKD-EPI implementation is the original 2009 Levey et al. coefficients (`kappa`, `alpha = -0.411`
male / `-0.329` female, the `0.993^age` term, `*1.018` for female) with the race multiplier simply
omitted rather than replaced — it is not the separately re-calibrated 2021 race-free refit (which
uses different constants, `142` / `-1.200` / `0.9938` / `*1.012`). Cockcroft-Gault is the plain
1976 formula, `(140-age) * weight / (72 * Scr)`, with `*0.85` for female and no upper weight cap or
lean-body-weight substitution. Both are simplifications of formulas that, in full clinical use,
carry adjustments this module does not implement; the docstrings do not claim otherwise.

## Guards and refusal behavior

Every division in all seven modules is guarded against its degenerate input, and every guard
returns a plain `0.0` sentinel rather than propagating `inf` or `nan`:

| Function | Guard | Returns |
| --- | --- | --- |
| `cardiology.ejection_fraction`, `.systemic_vascular_resistance`, `.fick_cardiac_output` | `edv_ml <= 0`, `co_l_per_min <= 0`, `cao2 - cvo2 <= 0` | `0.0` |
| `cardiology.stroke_volume` | `edv_ml - esv_ml < 0` | `0.0` (never negative) |
| `dentistry.dmft_prevalence`, `.plaque_index_score`, `.gingival_index`, `.bone_loss_percentage`, `.fluoride_concentration_ppm`, `.restoration_longevity_estimate` | denominator `<= 0` | `0.0` |
| `endocrinology.hormone_clearance_rate`, `.hormone_pulsatility` | `auc <= 0`, `observation_hours <= 0` | `0.0` |
| `endocrinology.receptor_binding_bmax` | `free_conc <= 0` | `0.0` |
| `endocrinology.feedback_gain` | `1 + G_ol * f <= 0` | `0.0` |
| `endocrinology.thyroid_free_fraction` | `1 + Ka * [TBG] <= 0` | `1.0` (all hormone free) |
| `endocrinology.testosterone_free` | `1 + Ka_SHBG * SHBG + Ka_Alb * Alb <= 0` | `total_t` (all hormone free) |
| `nephrology.creatinine_clearance_cockroft`, `.fractional_excretion_sodium`, `.transtubular_potassium_gradient`, `.renal_plasma_flow`, `.filtration_fraction`, `.osmolar_clearance`, `.protein_creatinine_ratio` (7 of the module's 10 functions) | the relevant plasma/urine denominator `<= 0` | `0.0` |
| `ophthalmology.visual_acuity_decimal`, `.corneal_radius_from_keratometry`, `.retinal_image_size`, `.depth_of_focus`, `.contrast_sensitivity` | denominator `<= 0` | `0.0` |
| `ophthalmology.refractive_error_spherical` | `far_point_m == 0` | `0.0` |
| `ophthalmology.critical_flicker_frequency` | `luminance_cd_m2 <= 0` | `k` (the intercept alone) |
| `orthodontics.tooth_movement_rate`, `.moment_to_force_ratio`, `.anchorage_loss_estimate`, `.arch_wire_force`, `.levelling_torque`, `.bolton_ratio` | the relevant force/span/tooth-count denominator `<= 0` | `0.0` |
| `pulmonology.alveolar_ventilation` | `tidal_volume_ml - dead_space_ml <= 0` | `0.0` (dead space exceeding tidal volume is refused, not made negative) |
| `pulmonology.fev1_fvc_ratio`, `.peak_expiratory_flow`, `.respiratory_quotient`, `.compliance_static`, `.airway_resistance` | denominator `<= 0` | `0.0` |

`endocrinology.thyroid_free_fraction` and `.testosterone_free` are the asymmetric cases in the
table: every other guard answers "no signal" with `0.0`, but a non-positive binding denominator in
either of these two means no carrier protein is binding the hormone at all, so the physically
correct answer is that all of it is free — `thyroid_free_fraction` returns `1.0` (100% free
fraction) and `testosterone_free` returns the input `total_t` unchanged (all of it free), neither
one the `0.0` every division-guard elsewhere in this family falls back to.

**`nephrology.gfr_ckd_epi` is the one function in this family whose division has no guard at all.**
Every other nephrology function with a denominator or power base that can vanish returns an early
`0.0`; `gfr_ckd_epi` does not — its formula raises `min(Scr/kappa, 1)` to a negative power
(`alpha = -0.411` male, `-0.329` female), and a `creatinine_mg_dl` of `0.0` makes that base exactly
`0.0`, i.e. `0.0` raised to a negative exponent, a divide-by-zero one level up inside `pow` rather
than in a plain division the source could check with an `if`. Confirming this independently in
Python — the same IEEE-754 arithmetic Mojo's `pow` is built on — `0.0 ** -0.411` raises a
domain/zero-division error rather than silently returning a finite number (`math.pow(0.0, -0.411)`
raises `ValueError: math domain error`; some C libm implementations instead return `+inf` for the
identical input). Either behavior is a crash or an `inf`, not the `0.0` sentinel every sibling
function in this module falls back to — and `creatinine_clearance_cockroft`, defined immediately
below `gfr_ckd_epi` in the same file, guards its own identical zero-creatinine input explicitly. That
makes the missing guard here a genuine gap in this specific function, not a stylistic inconsistency
across the module.

## Worked examples, hand-verified against textbook values

None of these seven modules has a pinned numeric test (see Verification below), so every number
below was computed independently from the real formulas in `mojo/engine/*.mojo` and checked, where a
standard clinical reference value exists, against that value.

**Cardiology — a full hemodynamic profile from EDV/ESV and blood pressure.** EDV 120 mL, ESV 50 mL,
heart rate 72 bpm, BP 120/80 mmHg, LVEDP 10 mmHg:

```python
sv  = runtime.execute("cardiology", "stroke_volume", [120.0, 50.0])["result"]        # 70.0 mL
ef  = runtime.execute("cardiology", "ejection_fraction", [120.0, 50.0])["result"]    # 0.5833... (58.3%, normal)
co  = runtime.execute("cardiology", "cardiac_output", [72.0, sv])["result"]          # 5.04 L/min
map_ = runtime.execute("cardiology", "mean_arterial_pressure", [120.0, 80.0])["result"]  # 93.333... mmHg
cpp = runtime.execute("cardiology", "coronary_perfusion_pressure", [80.0, 10.0])["result"]  # 70.0 mmHg
```

`ejection_fraction` recomputes `(EDV-ESV)/EDV` from its own two arguments rather than taking a
precomputed stroke volume, so it agrees with a separately-called `stroke_volume` only because both
start from the same `EDV`/`ESV` pair — the two functions do not call each other.

**Nephrology — Cockcroft-Gault vs. CKD-EPI on the same patient.** A 60-year-old woman, 70 kg, serum
creatinine 1.0 mg/dL:

```python
runtime.execute("nephrology", "creatinine_clearance_cockroft", [60.0, 70.0, 1.0, 1.0])["result"]
# 66.11111111111111 mL/min  ((140-60)*70/(72*1.0) * 0.85)

runtime.execute("nephrology", "gfr_ckd_epi", [1.0, 60.0, 1.0])["result"]
# 61.18505161746657 mL/min/1.73m^2
```

The two formulas estimate different quantities (creatinine clearance overestimates true GFR because
some creatinine is also secreted, not just filtered) and use different equations entirely, so their
~5 mL/min gap on this patient is not evidence either one is wrong — it is exactly the kind of
discrepancy both formulas are known to produce against each other, and against measured GFR, in real
patients. A prerenal-vs-intrinsic AKI check on the same patient with urine studies (Na 40 mEq/L,
creatinine 60 mg/dL against plasma Na 140 mEq/L, creatinine 1.2 mg/dL):

```python
runtime.execute("nephrology", "fractional_excretion_sodium", [40.0, 140.0, 60.0, 1.2])["result"]
# 0.5714285714285714 % -- below the 1% prerenal threshold
```

**Pulmonology — the alveolar gas equation and A-a gradient at sea level.** FiO2 = 0.21 (room air),
PaCO2 = 40 mmHg, barometric pressure = 760 mmHg, measured arterial PaO2 = 95 mmHg:

```python
pao2_alv = runtime.execute("pulmonology", "alveolar_oxygen", [0.21, 40.0, 760.0])["result"]
# 99.73 mmHg -- FiO2*(760-47) - 40/0.8, the textbook ~100 mmHg room-air value

runtime.execute("pulmonology", "a_a_gradient", [pao2_alv, 95.0])["result"]
# 4.72999999999999 mmHg -- well under the normal <15 mmHg threshold
```

**Endocrinology — HOMA-IR at the insulin-resistance boundary.** Fasting glucose 5.5 mmol/L, fasting
insulin 60 pmol/L:

```python
runtime.execute("endocrinology", "insulin_sensitivity_index", [5.5, 60.0])["result"]
# 2.4444444444444446 -- (5.5 * (60/6)) / 22.5, just under the >2.5 insulin-resistance cutoff
```

**Ophthalmology — pupil size and depth of focus.** At 20/20 acuity (`visual_acuity_arcmin = 1.0`),
a 3 mm photopic pupil and a 6 mm scotopic pupil:

```python
runtime.execute("ophthalmology", "depth_of_focus", [3.0, 1.0])["result"]   # 0.19391118867558657 diopters
runtime.execute("ophthalmology", "depth_of_focus", [6.0, 1.0])["result"]   # 0.09695559433779329 diopters
```

Halving the pupil diameter doubles the depth of focus, matching the formula's direct inverse
proportionality — a large pupil admits a narrower range of in-focus object distances, which is why
pinhole optics (an extremely small effective pupil) produces the deepest focus of all.

**Orthodontics — arch-wire force from Euler beam theory.** A 0.016 in (0.4064 mm) round NiTi wire
(`E` = 41 GPa), 10 mm interbracket span, deflected 1 mm:

```python
runtime.execute("orthodontics", "arch_wire_force", [1.0, 0.4064, 41.0, 10.0])["result"]
# 2.6351769916138204 N -- about 269 gf, in the light continuous-force range orthodontic literature targets
```

**Dentistry — DMFT and treatment cost, lifted directly from the real pinned test.** These two are
not hand-computed; they are read straight from `tests/mojo/test_wave91.mojo`'s `test_dentistry`:

```python
runtime.execute("dentistry", "dmft_index", [3, 2, 5])["result"]                        # 10
runtime.execute("dentistry", "treatment_cost_estimate", [3, 200.0, 1.5])["result"]      # 900.0
```

## Verification

Six of these seven modules (`cardiology`, `endocrinology`, `nephrology`, `ophthalmology`,
`orthodontics`, `pulmonology`) have only the auto-generated smoke test found at
`mojo/tests/libs/test_<module>.mojo`: each calls every function once with literal `0.5` arguments
and asserts only that the result is finite (`not isnan and not isinf`), matching the pattern
documented for the mixture-of-experts family — no specific numeric output is pinned by these files.

`dentistry` is the exception: `tests/mojo/test_wave91.mojo`'s `test_dentistry` function pins 24 real
assertions against exact expected values (`dmft_index(3, 2, 5) == 10`,
`treatment_cost_estimate(3, 200.0, 1.5) == 900.0`, and 22 more), which is where the two dentistry
numbers above come from verbatim. Every other worked example in this page was hand-traced against
the formula as written in the corresponding `mojo/engine/*.mojo` file and cross-checked, where a
standard textbook or clinical-reference value exists (CKD-EPI, Cockcroft-Gault, the alveolar gas
equation, HOMA-IR), against that value.

**Next:** see [Runtime library catalog](runtime-library-catalog.md) for every module and function,
or [Engine health & verification](health.md) for confirming the runtime executing these formulas is
live.
