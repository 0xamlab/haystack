---
icon: vial
description: One-compartment drug pharmacokinetics and dose-response pharmacology, CNS-specific receptor math, the parallel toxicokinetics/toxicology pair for toxic and environmental substances, and radiation dosimetry.
---

# Pharmacology and toxicology kernels

Six modules for the arithmetic under drug dosing, receptor pharmacology, and chemical/radiation risk
assessment. `pharmacokinetics` and `pharmacology` both model how a drug's concentration rises and falls
and what that concentration does at a receptor, but they are two independently-written modules that
happen to share several function names — `steady_state_concentration`, `loading_dose`, and
`time_to_peak` exist in both, with different argument lists or different edge-case guards, which this
page calls out explicitly rather than papering over. `neuropharmacology` narrows to the CNS-specific
half of that same problem: how much of a drug actually reaches brain receptors past the blood-brain
barrier, not just how much is in the plasma. `toxicokinetics` and `toxicology` are the mirror pair for
substances nobody is dosing on purpose — the first is absorption/distribution/elimination math for
toxicants and environmental contaminants (bioconcentration, tissue equivalency, exposure margins), the
second is the population-level risk-assessment layer built on top of it (LD50, hazard quotients,
reference doses, cancer slope-factor risk). `dosimetry` is unrelated to any of the above: it is
genuinely and exclusively radiation physics — absorbed dose in Gray, equivalent and effective dose in
Sievert, activity decay, shielding — not a sixth way to compute a drug dose, confirming rather than
overturning what its name suggests.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# ke = 0.1/h -> t1/2 = ln(2)/0.1, a real pinned value from mojo/tests/mojo/test_wave65.mojo
runtime.execute("pharmacokinetics", "half_life", [0.1])["result"]
# 6.931471805599453 -- hours

# LD50 = 50 mg/kg, a 70 kg subject -> a real pinned value from test_wave81.mojo
runtime.execute("toxicology", "ld50_dose", [50.0, 70.0])["result"]
# 3500.0 -- mg, the lethal dose for this body weight at this LD50
```

## The modules

| Module | What it does |
| --- | --- |
| `pharmacokinetics` | One-compartment oral and IV concentration-time models, half-life/elimination-rate conversion, clearance, bioavailability, loading and maintenance dosing, steady-state concentration, time-to-peak, multiple-dose accumulation, and trapezoidal AUC. |
| `pharmacology` | Dose-response and receptor math for therapeutic drugs: the Hill equation, therapeutic index, absolute bioavailability from paired oral/IV doses, receptor occupancy, free (unbound) plasma fraction, volume of distribution, clearance from half-life, steady-state concentration, loading dose, and the Chou-Talalay drug-combination index. |
| `neuropharmacology` | CNS-specific extensions of the same receptor math: brain receptor occupancy and Kp,uu (unbound brain-to-plasma exposure ratio), blood-brain-barrier P-gp efflux ratio, Cheng-Prusoff Ki from competition binding, steady-state synaptic neurotransmitter level, D2 receptor occupancy for antipsychotics, minimal effective CNS dose, off-target side-effect threshold from selectivity, and drug-modulated neuronal firing rate. |
| `toxicokinetics` | The same absorption/distribution/elimination shape as `pharmacokinetics`, applied to toxicants and environmental contaminants instead of therapeutic drugs: internal dose from bioavailability, peak concentration, time-to-peak, trapezoidal AUC, apparent volume of distribution, elimination half-life, systemic clearance, bioconcentration factor, dioxin-family toxic equivalency, and margin of exposure. |
| `toxicology` | Population-level dose-response and risk assessment built on exposure data: LD50 lethal dose, therapeutic index, margin of safety, bioconcentration factor, hazard quotient/index, cancer risk from a slope factor, EPA-style average daily dose, NOAEL-from-LOAEL, reference dose, the Hill dose-response equation, and acute exposure ratio. |
| `dosimetry` | Radiation dose and protection physics — genuinely radiation, not drug dosing: absorbed dose (Gray), equivalent and effective dose (Sievert) via radiation- and tissue-weighting factors, point-source dose rate, radioactive activity decay and specific activity, half-value/tenth-value shielding layers, buildup factor, kerma, and ICRP particle-type radiation weighting. |

## `pharmacokinetics`: one-compartment models, worked against real pinned tests

Every number in this section is lifted from `tests/mojo/test_wave65.mojo`, which pins exact expected
values for this module — not the auto-generated smoke test in `mojo/tests/libs/test_pharmacokinetics.mojo`,
which only checks that each function returns a finite number.

`one_compartment_iv(dose, ke, vd, t)` implements `C(t) = (dose/vd) * exp(-ke*t)`. At `t=0` it is just
`dose/vd`; a 500 mg IV bolus into a 50 L volume of distribution gives `C(0) = 10.0` mg/L, and at
`t=10` h with `ke=0.1`/h, `C(10) = 10.0 * exp(-1.0) = 3.6787944117144233` mg/L — the test pins exactly
this value to `1e-4`.

`one_compartment_oral(dose, ka, ke, vd, t)` implements the two-exponential Bateman function
`C(t) = (dose*ka)/(vd*(ka-ke)) * (exp(-ke*t) - exp(-ka*t))`, and is guarded twice: if `ka == ke` (or
`vd == 0`) the denominator is zero, so the function returns `0.0` rather than propagating a divide;
and if the arithmetic itself overflows to `inf`, a self-check (`c - c != 0.0`, true only for `NaN`/`inf`)
catches it and also returns `0.0`. At `t=0` both exponentials equal 1, so `C(0) = 0` by construction —
verified in the test.

`half_life` and `elimination_rate` are exact inverses through the constant `LN2 = 0.6931471805599453`:
`half_life(0.1) = ln2/0.1 = 6.931471805599453`, and `elimination_rate` of that same value round-trips
back to `0.1` to `1e-9`. `accumulation_factor(ke, tau)` — `R = 1/(1 - exp(-ke*tau))` — evaluated at
`tau` equal to one half-life makes `exp(-ke*tau) = 0.5` by definition, so `R = 1/(1-0.5) = 2.0`: one
half-life of dosing interval doubles the accumulation ratio, independent of what `ke` actually is.

`time_to_peak(ka, ke)` computes `tmax = ln(ka/ke)/(ka-ke)`, guarded against `ka == ke`, either rate
being exactly `0.0`, or `ka/ke < 0.0` (opposite-signed rate constants, which are not physically
meaningful). At `ka=1.0`, `ke=0.1`, `tmax = ln(10)/0.9 = 2.5584278811044956` h — pinned in the test.
Critically, this guard accepts `ka < ke` as long as the ratio is non-negative — see the
`toxicokinetics.time_to_peak` comparison below, which does not.

## `pharmacology`: dose-response and dosing math, not the same code as `pharmacokinetics`

`pharmacology` has no pinned wave test (only the finite-check smoke test in
`mojo/tests/libs/test_pharmacology.mojo`), so the worked numbers below were hand-derived from the
formulas in `mojo/engine/pharmacology.mojo` and checked against the textbook identity each one is
named for.

`hill_equation(emax, concentration, ec50, hill_n)` computes `E = Emax * C^n / (EC50^n + C^n)` and
guards `concentration <= 0.0` or `ec50 <= 0.0` to `0.0` before calling `pow`. At the defining point of
any Hill curve — concentration exactly at EC50 — the two power terms are equal and the effect is
exactly half of Emax: `hill_equation(100.0, 50.0, 50.0, 1.0) = 100 * 50 / (50 + 50) = 50.0`, matching
the same identity `toxicology.dose_response_hill` is tested against in `test_wave81.mojo`.

`drug_bioavailability(auc_oral, auc_iv, dose_oral, dose_iv)` is the *general* absolute-bioavailability
formula, `F = (AUC_oral/AUC_iv) * (dose_iv/dose_oral)`, which corrects for the oral and IV doses being
different. `pharmacokinetics.bioavailability(auc_oral, auc_iv)` is the special case where both doses
are equal, so the dose-ratio term drops to `1` and the formula collapses to a plain AUC ratio — the
two are not competing implementations of the same idea, one is a simplification of the other with an
implicit assumption baked in.

{% hint style="warning" %}
**`clearance_from_halflife` uses the literal `0.693`, not the exact `ln(2)`.** `pharmacokinetics.mojo`
defines `LN2 = 0.6931471805599453` as a named constant and uses it everywhere; `pharmacology.mojo`'s
`clearance_from_halflife(volume_of_dist, half_life) = 0.693 * Vd / t½` uses the truncated literal
instead. For `Vd = 50` L and `t½ = 6.931471805599453` h (exactly one `LN2`-derived half-life), the
exact answer is `CL = 5.0` L/h, but this function returns `4.998938316680258` — about `0.021%` low.
Clinically immaterial at this magnitude, but it is a real, verifiable inconsistency in constant
precision between two sibling modules that both claim to compute the same clearance.
{% endhint %}

`therapeutic_index(td50, ed50)` guards `ed50 <= 0.0` and returns `0.0` — see the `toxicology` section
below, where the *same-named* function has no such guard.

## `neuropharmacology`: the CNS-specific half of drug exposure

None of these ten functions has a pinned wave test either; the worked numbers below follow directly
from `mojo/engine/neuropharmacology.mojo` and a real clinical reference point cited in its own
docstring.

`d2_receptor_occupancy(plasma_conc, ec50) = 100 * Cp / (EC50 + Cp)` is the Emax model antipsychotic
dosing is titrated against. Its docstring names the real clinical target: 60-80% D2 occupancy is the
literature's accepted therapeutic window (below it, sub-therapeutic; above roughly 80%, extrapyramidal
side effects become likely). At `Cp = 10` nM against `EC50 = 5` nM, `d2_receptor_occupancy(10.0, 5.0)
= 100 * 10 / 15 = 66.67`% — inside that window.

{% hint style="warning" %}
**`minimal_effective_dose_cns` divides by `kp_uu` before its only guard runs.** The function computes
`c_plasma_free = ec20_nM / kp_uu` as its *first* line, then checks `if fu_plasma <= 0.0: return 0.0` —
a guard that says nothing about `kp_uu`. A drug with `kp_uu = 0.0` (a compound the brain fully excludes
— zero unbound brain-to-plasma ratio) with any positive `fu_plasma` produces `c_plasma_free = inf`,
which the guard does not catch, and the function returns `inf * clearance_l_per_h` as the "minimum
effective dose." Every other division in this module (`receptor_occupancy_brain`,
`blood_brain_barrier_efflux`, `synapse_neurotransmitter_level`, `bbb_penetration_ratio`,
`cns_drug_exposure`, `d2_receptor_occupancy`, `cns_side_effect_threshold`) checks its own denominator
before dividing; this is the one exception.
{% endhint %}

`receptor_binding_ki` implements the real Cheng-Prusoff equation, `Ki = IC50 / (1 + [L]/Kd_L)`, used to
convert a competition-binding IC50 into a radioligand-independent Ki — a standard correction in
receptor pharmacology, not a simplification invented for this codebase.

## `toxicokinetics` vs `pharmacokinetics`: same shape, different subject, one guard is stricter

`toxicokinetics` mirrors `pharmacokinetics` function-for-function — `apparent_volume_distribution` ~
`volume_of_distribution`, `elimination_half_life` ~ `half_life`, `systemic_clearance` ~ `clearance`,
`plasma_auc` ~ `drug_auc_trapezoidal` — but every function takes toxicant exposure/concentration
arguments rather than therapeutic dosing arguments, and the module adds toxicant-specific math
(`bioconcentration_factor`, `toxic_equivalency_factor`, `margin_of_exposure`) that has no
`pharmacokinetics` counterpart at all. This confirms the hint's expected split: `pharmacokinetics` is
"how does a therapeutic drug I chose to give someone rise and fall"; `toxicokinetics` is "how does a
substance nobody dosed on purpose move through a body or an ecosystem."

{% hint style="danger" %}
**`toxicokinetics.time_to_peak` refuses a case `pharmacokinetics.time_to_peak` accepts, for the
identical formula.** Both compute `tmax = ln(ka/ke)/(ka-ke)`. `pharmacokinetics.time_to_peak`'s guard
is `ka == ke or ke == 0.0 or ka == 0.0 or ka/ke < 0.0` — it accepts `ka < ke` as long as the ratio is
non-negative. `toxicokinetics.time_to_peak`'s guard is `absorption_rate <= elimination_rate or
elimination_rate <= 0.0` — it refuses *any* case where absorption is not strictly faster than
elimination. At `ka = 0.1`, `ke = 1.0` (elimination faster than absorption — "flip-flop" kinetics,
physiologically real for extended-release formulations and poorly-absorbed compounds), the formula's
actual value is `ln(0.1/1.0)/(0.1-1.0) = 2.5584278811044947` h — a well-defined, positive time to
peak, independently verified in Python against the closed-form equation. Called on
`pharmacokinetics.time_to_peak(0.1, 1.0)`, that value is exactly what comes back.
`toxicokinetics.time_to_peak(0.1, 1.0)` returns `0.0` instead, silently — the same input, the same
underlying math, a different, more conservative refusal boundary in the sibling module.
{% endhint %}

## `toxicology`: population risk assessment, and the one module that mostly doesn't guard

`toxicology`'s twelve functions are pinned with real numbers in `tests/mojo/test_wave81.mojo` (not
just the finite-check smoke test). `average_daily_dose(conc, intake_rate, exposure_freq, exposure_dur,
body_weight, averaging_time)` is EPA's standard chronic-exposure equation,
`ADD = (C*IR*EF*ED)/(BW*AT)` — at `C=0.1` mg/L, `IR=2` L/day, `EF=350` days/yr, `ED=30` yr, `BW=70` kg,
`AT=25550` days (70 yr in days), `ADD = 2100/1,788,500 ≈ 0.001174` mg/kg-day, pinned in the test to
within 1%. `dose_response_hill(dose, emax, ec50, n)` implements the same Hill equation as
`pharmacology.hill_equation` above, but via `exp(n*log(x))` rather than `pow`, and guards only
`dose <= 0.0`; at `dose=100`, `emax=100`, `ec50=50`, `n=1`, the test pins `100*100/(50+100) =
66.6667`.

{% hint style="warning" %}
**`toxicology.mojo` guards almost nothing.** Of its twelve functions, only `dose_response_hill` checks
an input before dividing (`dose <= 0.0`). `ld50_dose`, `margin_of_safety`, `bioconcentration_factor`,
`hazard_quotient`, `cancer_risk`, `no_observed_adverse_effect_level`, `reference_dose`, and
`acute_exposure_ratio` are all bare divisions with no denominator check — a zero or negative
`ed99`/`conc_water`/`reference_dose`/`total_uf`/`acute_toxicity_value` propagates `inf` or `NaN`
straight through to the caller. This is a real, structural difference from `pharmacokinetics`,
`pharmacology`, `neuropharmacology`, and `toxicokinetics`, every one of which guards nearly every
division with a `0.0` sentinel. Concretely: **`therapeutic_index(td50, ed50)` in this module has no
guard at all** — `therapeutic_index(100.0, 0.0)` returns `+inf` — while `pharmacology.therapeutic_index`,
computing the identical `TD50/ED50` ratio, guards `ed50 <= 0.0` and returns `0.0` instead. Same name,
same formula, different failure mode depending on which module a caller reaches for.
{% endhint %}

`margin_of_exposure` (in `toxicokinetics`, not `toxicology` — `toxicology` has no function of this
name) implements `MOE = NOAEL/human_dose`, and its docstring cites the real risk-assessment convention
that `MOE > 10,000` is generally considered an acceptable safety margin (the threshold used by
bodies like EFSA and JECFA for genotoxic-carcinogen exposures). At `NOAEL = 50` mg/kg/day and a human
exposure estimate of `0.001` mg/kg/day, `margin_of_exposure(50.0, 0.001) = 50,000` — comfortably above
that threshold. `toxic_equivalency_factor(congener_conc, tef)` is a plain multiply,
`TEQ = concentration * TEF`; using the real WHO (2005) toxic-equivalency factor for
2,3,4,7,8-pentachlorodibenzofuran (`TEF = 0.3`, relative to TCDD's own `TEF = 1`) at a measured
congener concentration of `2.0` pg/g gives `toxic_equivalency_factor(2.0, 0.3) = 0.6` pg TEQ/g.

## `dosimetry`: radiation physics, not a sixth dosing module

This page's hint asked for explicit verification that `dosimetry` is genuinely about radiation and not
another drug-dosing module in disguise, given this corpus's history of misleading module names.
Reading `mojo/engine/dosimetry.mojo` confirms it: every one of its ten functions is ICRP-style
radiation-protection physics — none accepts a drug concentration, receptor, or plasma argument. The
one other place in this codebase that mentions "dosimetry" by name is a warning in
[Cartography and planetary & cosmic sciences kernels](cartography-and-planetary-cosmic-sciences-kernels.md),
which explicitly says its own `radiation_dose_rate` (a coarse cosmic-ray proportionality) is "not a
substitute for a real particle-transport dosimetry calculation" — i.e. it points *at* this module's
subject matter without implementing it, which is independent confirmation of the same conclusion.

The three dose quantities chain, each building on the last:

```python
runtime.execute("dosimetry", "absorbed_dose", [0.02, 1.0])["result"]
# 0.02 -- Gy (J/kg): 0.02 J deposited in 1 kg of tissue

runtime.execute("dosimetry", "equivalent_dose", [0.02, 1.0])["result"]
# 0.02 -- Sv: photon radiation weighting w_R = 1, so equivalent dose equals absorbed dose

runtime.execute("dosimetry", "effective_dose", [0.02, 0.12])["result"]
# 0.0024 -- Sv (2.4 mSv), using the real ICRP-103 tissue weighting factor w_T = 0.12 for lung
```

`absorbed_dose(energy_j, mass_kg) = E/m` is Gray by definition; `equivalent_dose(absorbed_dose_gy,
radiation_weighting) = D * w_R` converts to Sievert using `radiation_weighting`'s own particle-type
lookup (`1.0` for photons/electrons, `2.0` for protons, `20.0` for alpha particles and fast neutrons,
`5.0` for thermal neutrons — the same coarse ICRP Publication 60 banding used in dose-limit tables);
`effective_dose(equivalent_dose_sv, tissue_weighting) = H_T * w_T` sums (across tissues, at the
caller's side) into the whole-body effective dose used for regulatory dose limits.

`activity_decay(initial_activity, half_life, time) = A0 * exp(-(ln2/half_life)*time)` round-trips
exactly one half-life to half the activity, independent of the isotope: for Tc-99m (medical imaging's
most common isotope, physical half-life 6.0058 h), `activity_decay(1000.0, 6.0058, 6.0058) = 500.0`
Bq — verified directly, since `exp(-ln2) = 0.5` by construction. `tenth_value_layer(hvl) = hvl *
log(10)/log(2)` encodes the real shielding relationship `TVL/HVL = log2(10) ≈ 3.3219` (attenuation to
1/10 takes `log2(10)` times as much material as attenuation to 1/2) — `tenth_value_layer(1.0) =
3.3219280948873626`.

## Verification

`pharmacokinetics` and `toxicology` both have real pinned-value test suites —
`tests/mojo/test_wave65.mojo` and `tests/mojo/test_wave81.mojo` respectively — and every worked number
attributed to those two modules above is lifted directly from those files, not invented.
`pharmacology`, `neuropharmacology`, `toxicokinetics`, and `dosimetry` have no pinned wave test; their
only existing coverage is the auto-generated smoke test in each module's
`mojo/tests/libs/test_<module>.mojo`, which calls every function once with literal `0.5` arguments and
checks only that the result is finite. Every worked number attributed to those four modules above was
hand-derived from the real formula in `mojo/engine/<module>.mojo` and, where a textbook or regulatory
reference value exists (the Hill-equation half-max identity, the Cheng-Prusoff equation, the D2
60-80% therapeutic occupancy window, the EPA average-daily-dose equation, the WHO dioxin
toxic-equivalency factors, the ICRP tissue-weighting factor, the MOE > 10,000 acceptability
convention), checked against that reference independently rather than presented as self-evidently
correct.

**Next:** see [Epidemiology and disease dynamics kernels](epidemiology-and-disease-dynamics-kernels.md)
for the population-level disease-spread and diagnostic-test math this page's individual-subject dosing
and risk formulas feed into, or browse the [Runtime library catalog](runtime-library-catalog.md) for
every module and function.
