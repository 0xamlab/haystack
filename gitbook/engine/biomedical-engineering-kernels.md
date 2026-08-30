---
icon: stethoscope
description: Bedside cardiovascular/renal/respiratory/pharmacokinetic formulas, gait and joint-mechanics equations, and human sound-perception models — three unrelated small physics/physiology libraries, not one "biomedical engineering" suite.
---

# Biomedical, biomechanics, and psychoacoustics kernels

Three small, stateless formula modules that apply closed-form physics and physiology equations to
the human body: bedside clinical calculations (`biomedical`), the mechanics of joints, limbs, and
gait (`biomechanics`), and how the ear and brain perceive loudness, pitch, and masking
(`psychoacoustics`). None of these are simulators — each function is a single named formula
(Cockcroft-Gault, the Fick principle, the Hill muscle model, the Bark scale) evaluated on scalar
`Float64` inputs, the same shape as every other kernel family in this corpus. `biomedical` is not
the only clinical-formula module in the runtime library — the section below on its overlap with
`cardiology`, `nephrology`, and `pulmonology` covers exactly which functions duplicate each other
and how the signatures disagree.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Fick principle: 250 mL/min VO2, arterial/venous O2 content 20 and 15 mL/dL
runtime.execute("biomedical", "fick_cardiac_output", [250.0, 20.0, 15.0])["result"]
# 5.0 — L/min, a normal resting cardiac output

# Hill muscle model: Fmax=1000 N, shortening at 0.1 (of Vmax), Vmax=1.0, a=0.25
runtime.execute("biomechanics", "muscle_force_hill", [1000.0, 0.1, 1.0, 0.25])["result"]
# 642.857... — force drops off from Fmax as contraction velocity rises, per Hill's 1938 curve
```

## The modules

| Module | What it does |
| --- | --- |
| `biomedical` | Cardiovascular, renal, respiratory, and pharmacokinetic bedside formulas: cardiac output (both the SV×HR and Fick-principle routes), mean arterial and pulse pressure, Du Bois body surface area, Cockcroft-Gault creatinine clearance (named `glomerular_filtration_rate`), oxygen delivery, the alveolar gas equation, BMI, drug clearance, anion gap, and Bazett-corrected QT. |
| `biomechanics` | Joint and gait mechanics: joint torque and power, angular velocity/acceleration, limb moment of inertia, ground-reaction-force ratio, stride length and cadence, walking metabolic cost, tendon elastic energy, two-segment center of mass, and the Hill muscle force-velocity model. |
| `psychoacoustics` | Human auditory *perception*, not physical sound propagation: phon↔sone loudness conversion, the Bark scale and critical bandwidth (ERB), a simplified simultaneous-masking spreading function, the Speech Intelligibility Index, an A-weighting approximation, frequency JND, post-masking temporal decay, and binaural masking level difference. |

## `biomedical` duplicates part of `cardiology`, `nephrology`, and `pulmonology` — same formulas, different signatures

`biomedical.mojo`'s own docstring frames it as covering "cardiovascular, renal, respiratory, and
pharmacokinetic calculations," and the runtime library also ships three dedicated clinical-specialty
modules — `cardiology`, `nephrology`, and `pulmonology` — that are not documented on this page (a
grep of `gitbook/` finds no page for any of the three, only the auto-generated
[Runtime library catalog](runtime-library-catalog.md)). Reading all four `.mojo` files side by side
shows real, function-level overlap, not just a shared subject area:

| Concept | `biomedical` | Overlapping specialty module |
| --- | --- | --- |
| Cardiac output (SV×HR) | `cardiac_output(stroke_volume_ml, heart_rate)` | `cardiology.cardiac_output(heart_rate, stroke_volume_ml)` — **same formula, arguments swapped** |
| Mean arterial pressure | `mean_arterial_pressure(systolic, diastolic)` | `cardiology.mean_arterial_pressure(systolic_mmhg, diastolic_mmhg)` — identical formula and order |
| Pulse pressure | `pulse_pressure(systolic, diastolic)` | `cardiology.pulse_pressure(systolic_mmhg, diastolic_mmhg)` — identical formula and order |
| Fick cardiac output | `fick_cardiac_output(vo2, cao2, cvo2)` | `cardiology.fick_cardiac_output(vo2_ml_per_min, cao2, cvo2)` — same formula, **different zero/negative guard** (below) |
| Creatinine clearance | `glomerular_filtration_rate(creatinine, age, weight, is_female: Bool)` | `nephrology.creatinine_clearance_cockroft(age, weight_kg, creatinine_mg_dl, is_female: Float64)` — same Cockcroft-Gault formula, reordered args, **different type for the sex flag** |
| Alveolar gas equation | `alveolar_gas_equation(fio2, patm, ph2o, paco2, rq)` — fully parameterized | `pulmonology.alveolar_oxygen(fio2, paco2_mmhg, barometric_mmhg)` — same equation with `ph2o` and `rq` hardcoded to `47.0` and `0.8` |

Two of these differences are worth calling out precisely rather than just noting "they differ":

* **`glomerular_filtration_rate` is a misnomer inherited from its own docstring, not just this
  page's framing.** The function computes Cockcroft-Gault **creatinine clearance** —
  `((140-age)*weight) / (72*creatinine)`, optionally ×0.85 for a female patient — which is exactly
  what `nephrology.creatinine_clearance_cockroft` computes and correctly names. Cockcroft-Gault CrCl
  is a weight-based *estimate* of renal clearance, not a measurement of glomerular filtration itself,
  and it is a clinically distinct quantity from the modern CKD-EPI eGFR equation that
  `nephrology.gfr_ckd_epi` implements separately (`141 × min(Scr/κ,1)^α × max(Scr/κ,1)^-1.209 ×
  0.993^age [× 1.018 female]`, normalized to mL/min/1.73m² body-surface area — a different formula
  family entirely, using different inputs and no weight term at all). `biomedical`'s own docstring
  header calls this "Cockcroft-Gault GFR," conflating the two concepts in the same breath the
  function name does.
* **The two `fick_cardiac_output` implementations disagree on which inputs they refuse.**
  `biomedical`'s guards `fabs(cao2 - cvo2) < 1e-30` and returns `0.0` — it only catches a
  content difference that is *exactly* (to floating-point tolerance) zero. `cardiology`'s guards
  `cao2 - cvo2 <= 0.0` — it also catches a *negative* difference (venous content exceeding arterial,
  which is not physiologically possible but is not excluded by the arguments' types). Calling
  `biomedical.fick_cardiac_output(250.0, 15.0, 20.0)` (arterial and venous swapped by mistake) returns
  `-5.0` — a negative "cardiac output" — where `cardiology.fick_cardiac_output(250.0, 15.0, 20.0)`
  returns `0.0` for the same inputs.

## Worked examples — `biomedical`

Every number below is lifted directly from the real pinned assertions in
`tests/mojo/test_wave75.mojo` ("Tests for Wave 75 — Biomedical, Ceramics, Wind Energy"), not
hand-invented — see [Verification](#verification) for why that distinction matters here.

```python
runtime.execute("biomedical", "cardiac_output", [70.0, 72.0])["result"]
# 5.04 — CO = SV(70 mL) * HR(72 bpm) / 1000

runtime.execute("biomedical", "mean_arterial_pressure", [120.0, 80.0])["result"]
# 93.333... — MAP = 80 + (120-80)/3, a normal reading

runtime.execute("biomedical", "glomerular_filtration_rate", [1.0, 40.0, 70.0, False])["result"]
# 97.222... — Cockcroft-Gault CrCl for a 40-year-old, 70 kg man, Scr=1.0 mg/dL
runtime.execute("biomedical", "glomerular_filtration_rate", [1.0, 40.0, 70.0, True])["result"]
# 82.639... — the same patient's values with the 0.85 female factor applied

runtime.execute("biomedical", "oxygen_delivery", [5.0, 15.0, 98.0])["result"]
# 999.9 — DO2 at CO=5 L/min, Hb=15 g/dL, SaO2=98%: a normal ~1000 mL O2/min

runtime.execute("biomedical", "alveolar_gas_equation", [0.21, 760.0, 47.0, 40.0, 0.8])["result"]
# 99.73 — room air at sea level, PaCO2=40 mmHg, RQ=0.8: a normal PAO2

runtime.execute("biomedical", "corrected_qt_bazett", [400.0, 0.8])["result"]
# 447.2 ms — QTc at HR=75 bpm (RR=0.8 s), the Bazett over-correction above HR 60
```

{% hint style="warning" %}
**`oxygen_delivery` and `fick_cardiac_output`'s docstrings both omit a real ×10 unit-conversion
factor that the code applies.** `oxygen_delivery`'s docstring states `DO2 = CO * (1.34*Hb*SaO2/100 +
0.003*100)`; the function body actually returns `co * content * 10.0`. Likewise
`fick_cardiac_output`'s docstring states `CO = VO2 / (CaO2 - CvO2)`; the body returns
`vo2 / (diff * 10.0)`. The ×10 converts an O2-content term expressed per deciliter of blood
(`mL O2/dL`, the standard clinical unit) into per-liter, which `CO` (L/min) needs to combine with
correctly. This is not a bug — the code's numbers match real physiology (`oxygen_delivery(5.0, 15.0,
98.0) = 999.9` mL O2/min, squarely in the normal ~950-1150 mL/min range; `fick_cardiac_output(250.0,
20.0, 15.0) = 5.0` L/min, a normal resting value) — but taking either docstring's formula literally,
without the ×10, understates both results by exactly 10x (`99.99` and `50.0` respectively), which
is not a plausible clinical number for either quantity. Anyone re-deriving these formulas from the
docstring alone rather than reading the function body would introduce that factor-of-10 error.
{% endhint %}

## Worked examples — `biomechanics`

These are lifted directly from `tests/mojo/test_wave92.mojo` ("Tests for Wave 92 — Laundry,
Volcanology, Biomechanics"), the file that carries this module's real pinned numeric assertions
(23 of them), separate from the auto-generated smoke test.

```python
runtime.execute("biomechanics", "joint_torque", [100.0, 0.3])["result"]
# 30.0 — tau = F(100 N) * moment_arm(0.3 m)

runtime.execute("biomechanics", "stride_length", [1.5, 120.0])["result"]
# 1.5 — 1.5 m/s at 120 steps/min; round-tripping through cadence_from_velocity(1.5, 1.5)
# returns 120.0, the two functions are exact inverses of each other

runtime.execute("biomechanics", "metabolic_cost_walking", [70.0, 1.4])["result"]
# 586.6 W — a 70 kg walker at 1.4 m/s: 2.5*70 + 3.0*70*1.4^2

runtime.execute("biomechanics", "muscle_force_hill", [1000.0, 0.1, 1.0, 0.25])["result"]
# 642.857... N — Fmax=1000 N, v=0.1, Vmax=1.0, a_hill=0.25
runtime.execute("biomechanics", "muscle_force_hill", [500.0, 0.0, 1.0, 0.25])["result"]
# 500.0 — at zero contraction velocity the Hill model reduces to exactly Fmax, by construction
```

`center_of_mass_two_segments(5.0, 0.2, 3.0, 0.6)` gives `0.35` — the weighted position between a
5 kg segment at 0.2 m and a 3 kg segment at 0.6 m, `(5*0.2 + 3*0.6)/(5+3)`.

## `biomechanics` has no divide-by-zero guards at all — `biomedical` guards nearly every division

Every division in `biomedical.mojo` is guarded: `bmi`, `drug_clearance`, `corrected_qt_bazett`,
`fick_cardiac_output`, and `alveolar_gas_equation` all check their denominator against `1e-30` (or,
for `corrected_qt_bazett`, an explicit `rr_s <= 0.0`) and return `0.0` instead of dividing. Reading
`biomechanics.mojo` end to end, none of its four dividing functions do this:
`ground_reaction_force_ratio(grf, body_weight)` divides by `body_weight` unconditionally,
`stride_length` divides by `cadence_steps_per_min / 2.0`, `cadence_from_velocity` divides by
`stride_len`, and `muscle_force_hill`'s denominator `vmax + velocity / a_hill` can reach zero for a
negative `velocity` equal to `-vmax * a_hill`. Calling any of these with a zero denominator returns
Mojo's IEEE-754 `inf` (or `nan` for `0.0/0.0`) rather than a sentinel `0.0` — a caller feeding this
module live sensor data (a runner momentarily airborne with `body_weight` measured as `0.0`, say)
gets an infinite ratio back with no guard to catch it, unlike the equivalent situation in
`biomedical`.

## `psychoacoustics`: the module's real subject is perception, not the physics of sound

The hint that motivated this page's scope groups `psychoacoustics` with "physical acoustics," but
reading `psychoacoustics.mojo`'s docstring header ("Human perception of sound calculations") and its
ten functions confirms it covers exclusively how a listener's ear and brain perceive a sound signal
— loudness in phons/sones, the Bark psychoacoustic frequency scale, simultaneous and temporal
masking, speech intelligibility, and binaural masking — never sound pressure, intensity, or power in
physical units. The `acoustics` module documented in
[Acoustics, optics, and radiative materials kernels](acoustics-optics-and-radiative-materials-kernels.md)
covers the complementary physical side (decibel arithmetic, the inverse-square law, room
reverberation, Doppler shift). The two modules share no function names and neither imports the
other; `acoustics.sound_pressure_level` computes a physical dB SPL from a pressure ratio,
`psychoacoustics.loudness_phon_to_sone` converts a perceptual loudness *level* (which already
accounts for the ear's frequency-dependent sensitivity) into a perceptual loudness *magnitude* — an
entirely different measurement chain with no shared formula between them.

### Loudness and critical bands

```python
runtime.execute("psychoacoustics", "loudness_phon_to_sone", [70.0])["result"]
# 8.0 — the sone scale is built so loudness doubles every 10 phon above 40 phon:
# 40 phon = 1 sone, 50 = 2, 60 = 4, 70 = 8, matching the standard equal-loudness table

runtime.execute("psychoacoustics", "bark_scale", [1000.0])["result"]
# 8.527432... Bark — Traunmüller's (1990) formula, 26.81*f/(1960+f) - 0.53

runtime.execute("psychoacoustics", "critical_bandwidth", [1000.0])["result"]
# 132.639 Hz — the Glasberg & Moore ERB approximation, 24.7*(4.37*f/1000 + 1), at 1 kHz
```

### Masking and the A-weighting approximation

```python
# A 1000 Hz masker at 80 dB SPL, evaluated at a target 200 Hz above it (upper spreading slope)
runtime.execute("psychoacoustics", "masking_threshold", [80.0, 1000.0, 1200.0])["result"]
# 41.910... dB SPL

# The same masker evaluated at its own frequency (delta_bark = 0)
runtime.execute("psychoacoustics", "masking_threshold", [80.0, 1000.0, 1000.0])["result"]
# 70.0 dB SPL — exactly masker_spl - 10, the module's self-masking offset

runtime.execute("psychoacoustics", "equal_loudness_correction", [1000.0, 80.0])["result"]
# 80.002 dB(A) — the A-weighting polynomial is normalized to ~0 dB correction at 1 kHz by
# construction; at 100 Hz the same 80 dB SPL corrects down to 60.76 dB(A), reflecting the
# ear's reduced low-frequency sensitivity
```

{% hint style="info" %}
`equal_loudness_correction`'s polynomial (`-145.528 + 98.262*log10(f) - 19.509*log10(f)^2 +
0.975*log10(f)^3`) is a curve-fit approximation to the standard A-weighting response, not the
IEC 61672 reference transfer function computed from four corner frequencies. It reproduces the
reference curve closely at the two points checked here (0 dB at 1 kHz; approximately -19 dB at
100 Hz, against a published reference value of about -19.1 dB) but should be read as an
engineering approximation, matching how the module's own docstring frames it ("ITU-R 468
approximation using polynomial").
{% endhint %}

## Verification

`mojo/tests/libs/test_biomedical.mojo` and `test_biomechanics.mojo` are auto-generated coverage
smoke tests, matching the pattern documented on
[Classical ML algorithms](ml-classical-algorithms.md): every function is called once against a
shared `0.5`-valued fixture and the only assertion is that the result is finite — neither file pins
a specific numeric output. The real pinned assertions for these two modules live elsewhere, in
`tests/mojo/test_wave75.mojo` (12 biomedical functions, 24 assertions) and
`tests/mojo/test_wave92.mojo` (12 biomechanics functions, 23 assertions including two zero/edge
cases) — every worked example in the `biomedical` and `biomechanics` sections above is lifted
directly from those two files, not invented for this page.

`psychoacoustics` has no equivalent pinned-numeric wave file: a search of every
`tests/mojo/test_wave*.mojo` file for the string `psychoacoustics` returns no match, so
`mojo/tests/libs/test_psychoacoustics.mojo`'s auto-generated finite-check smoke test is the only
test coverage this module has. Every number in the `psychoacoustics` section above was instead
computed independently in Python from the real formulas in `mojo/engine/psychoacoustics.mojo`, and
cross-checked against a published reference value where one exists (the phon/sone doubling law, the
A-weighting curve's 0 dB point at 1 kHz and its published ≈-19.1 dB value at 100 Hz, and the cited
Traunmüller and Glasberg-Moore formulas) — reproduce any of them by re-running the same arithmetic.

**Next:** see [Acoustics, optics, and radiative materials kernels](acoustics-optics-and-radiative-materials-kernels.md)
for the physical-sound counterpart to `psychoacoustics`, or the
[Runtime library catalog](runtime-library-catalog.md) for every module and function, including the
`cardiology`, `nephrology`, and `pulmonology` modules this page's first section compares `biomedical`
against.
