---
icon: microscope
description: Antibody/immune-response, blood-cell-index, viral-kinetics, cell-biology, and flow-cytometry formulas across five independent clinical and lab-science modules.
---

# Immunology, hematology, and virology kernels

Five small, independent modules for the arithmetic behind blood, immune-system, and cell-level lab
science: how an ELISA titer or a vaccine's efficacy is computed from raw immunoassay counts
(`immunology`), how a complete blood count's raw cell volumes and hemoglobin readings become the
red-cell indices a hematologist actually reads off a report (`hematology`), how a plaque assay or an
epidemic curve turns into a viral titer or a reproduction number (`virology`), how a single cell's
geometry, division, and death are quantified under a microscope (`cytology`), and how a flow
cytometer's raw gated event counts become percentages, ratios, and separation-quality metrics
(`cytometry`). Every function takes plain `Float64` scalars — no shared struct, no cross-module
imports — and returns a single `Float64`, guarding division by zero with an explicit `<= 0.0` check
rather than letting the runtime propagate a `NaN` or `inf`.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("immunology", "herd_immunity_threshold", [15.0])["result"]
# 0.9333333333333333 -- a measles-like R0 of 15 needs >93% of the population immune
# before the epidemic can no longer sustain itself

runtime.execute("hematology", "mean_corpuscular_volume", [0.45, 5.0])["result"]
# 900.0 -- not 90.0. A hematocrit of 45% and an RBC count of 5 million/uL is a
# textbook-normal CBC; the standard clinical formula (Hct% x 10 / RBC count) returns
# 90 fL for these inputs. The kernel is a decimal order of magnitude too high --
# see "A real scaling bug" below.
```

## The modules

| Module | What it does |
| --- | --- |
| `immunology` | Antibody and cellular immune-response formulas: ELISA titer and avidity index, seroconversion rate, antigen-antibody equilibrium binding, complement activation, T-cell logistic proliferation, innate cytokine decay, vaccine efficacy, herd immunity threshold, and opsonisation index |
| `hematology` | Blood-cell indices and coagulation from a CBC-style panel: hematocrit, the three red-cell indices (MCV, MCH, MCHC), RDW, oxygen-carrying capacity, INR, a platelet index, relative blood viscosity, and an ESR estimate |
| `virology` | Viral infection dynamics and lab titration: basic reproduction number, viral doubling time, plaque-forming-unit titre, burst size, eclipse period, neutralisation titre, antiviral IC50, first-order decay rate, dose-response infection probability, and herd immunity threshold |
| `cytology` | Cell-biology geometry and physiology: spherical cell volume, nuclear:cytoplasmic ratio, membrane permeability, doubling time, mitotic index, viability, apoptosis rate, phagocytic index, cell adhesion strength, and osmotic fragility |
| `cytometry` | Flow-cytometry-style measurement and gating: percent-positive gate, MFI ratio, staining index, peak CV%, cell-cycle phase fraction, combined apoptosis percentage, CD4:CD8 ratio, absolute count from a differential, spillover compensation, and limit of detection |

Each module has exactly 10 functions (50 total), and every one is a leaf function — no module in
this family imports another, and nothing outside `mojo/engine/runtime_library_dispatch_generated.mojo`
wires them together. Grepping the rest of `gitbook/` for these five module names before writing this
page turned up nothing but their auto-generated row in
[Runtime library catalog](runtime-library-catalog.md) — no existing narrative page duplicates this
content.

## `immunology`: antibody assays and the immune response over time

| Function | What it does |
| --- | --- |
| `antibody_titer(dilution_factor, od_ratio)` | Reciprocal ELISA titer, `1 / (dilution × OD_ratio)`; `0.0` if either input is `<= 0`. |
| `seroconversion_rate(n_seroconverted, n_total)` | `n_seroconverted / n_total`; `0.0` if `n_total <= 0`. |
| `antigen_antibody_binding(ka, antigen_conc, antibody_conc)` | Equilibrium bound fraction, `Ka·[Ab] / (1 + Ka·[Ab])`; `0.0` if the denominator is `<= 0`. |
| `complement_activation(antibody_conc, threshold, rate_constant)` | `rate_constant × (antibody_conc - threshold)` once `antibody_conc` clears `threshold`, else a hard `0.0`. |
| `t_cell_proliferation(n0, max_cells, growth_rate, time)` | Logistic clonal expansion, `K / (1 + ((K-N0)/N0)·exp(-r·t))`; returns `n0` if `max_cells` or `n0` is `<= 0`. |
| `innate_response_decay(c0, decay_rate, time)` | First-order cytokine clearance, `C0·exp(-k·t)`. |
| `vaccine_efficacy(attack_rate_vaccinated, attack_rate_unvaccinated)` | `1 - (ARV / ARU)`; `0.0` if `ARU <= 0`. |
| `herd_immunity_threshold(r0)` | `1 - 1/R0`; `0.0` for `r0 <= 1` (an epidemic that can't sustain itself needs no threshold). |
| `antibody_avidity_index(od_urea, od_pbs)` | `(OD_urea / OD_pbs) × 100`; `0.0` if `od_pbs <= 0`. |
| `opsonisation_index(phagocytosis_immune, phagocytosis_control)` | `(FI_immune / FI_control) - 1`; `0.0` if the control reading is `<= 0`. |

**`antigen_antibody_binding` takes `antigen_conc` but never uses it.** Reading the body directly
(`mojo/engine/immunology.mojo:69-72`): `denom = 1.0 + ka * antibody_conc; return ka * antibody_conc /
denom` — the true equilibrium binding equation is a quadratic in both `[Ag]` and `[Ab]`, but the
docstring is explicit that this is "Simplified: bound_fraction ≈ Ka·[Ab] / (1 + Ka·[Ab])", i.e. the
free-antigen term is dropped from the approximation on purpose. `antigen_conc` stays in the
signature (and the contract) but plays no part in the returned number — the same disclosed-but-unused
pattern documented for `moe_routing.expert_choice_gate`'s `token_score` on the
[mixture-of-experts page](mixture-of-experts-and-routing-kernels.md).

A realistic chain, hand-traced against the formulas above: a serum sample seroconverts
(`seroconversion_rate(184, 200) = 0.92`), its titer comes back at a 1:1000 dilution with an OD ratio
of `2.0` (`antibody_titer(0.001, 2.0) = 500`), and an avidity ELISA on the same sample reads
`antibody_avidity_index(0.3, 1.0) = 30.0` — low avidity, consistent with a recent rather than a past
infection. `t_cell_proliferation(1000.0, 100000.0, 0.15, 24.0)` (1,000 starting cells, a carrying
capacity of 100,000, a net growth rate of 0.15/h, 24 hours) returns `26990.199831015794`.

## `hematology`: red-cell indices, coagulation, and a real scaling bug

| Function | What it does |
| --- | --- |
| `hematocrit(rbc_volume, total_blood_volume)` | `V_RBC / V_total`; `0.0` if the total volume is `<= 0`. |
| `mean_corpuscular_volume(hematocrit_fraction, rbc_count_millions)` | `hematocrit_fraction × 10 / rbc_count_millions × 1000` — see below; `0.0` if RBC count is `<= 0`. |
| `mean_corpuscular_hemoglobin(hemoglobin_g_dl, rbc_count_millions)` | `Hgb / RBC × 10`, pg; `0.0` if RBC count is `<= 0`. |
| `mchc(hemoglobin_g_dl, hematocrit_fraction)` | `Hgb / Hct`, g/dL; `0.0` if `Hct <= 0`. |
| `red_cell_distribution_width(std_mcv, mean_mcv)` | `(std / mean) × 100`, RDW-CV%; `0.0` if the mean is `<= 0`. |
| `oxygen_carrying_capacity(hemoglobin_g_dl)` | `1.34 × Hgb`, mL O₂/dL blood (Hüfner's constant), no guard. |
| `coagulation_inr(patient_pt, mean_normal_pt, isi)` | `(PT_patient / PT_mean_normal)^ISI`; `0.0` if the mean normal PT is `<= 0`. |
| `platelet_count_index(mean_platelet_volume, platelet_count_k)` | `MPV × PLT_count / 100`, no guard — see naming note below. |
| `blood_viscosity_relative(hematocrit_fraction)` | `(1 - Hct)^-2.5`; falls back to `1.0` (plasma-like) outside `[0, 1)`. |
| `erythrocyte_sedimentation(fibrinogen_g_l, age, sex_factor)` | `fibrinogen × 0.4 + age × 0.065 + sex_factor`, clamped at `0.0` — an explicitly-labeled simplified estimator, not an actual Westergren-tube measurement. |

### A real scaling bug: `mean_corpuscular_volume` is 10x too high

The standard clinical formula for mean corpuscular volume is `MCV (fL) = Hct(%) × 10 / RBC count
(millions/µL)`. This module's `hematocrit_fraction` parameter is documented and used everywhere
else in the module as a **fraction** (`hematocrit`'s own docstring: "fraction 0–1, multiply by 100
for %"; `blood_viscosity_relative`'s: "Hematocrit fraction (0–0.6)"), so converting a fraction to a
percentage for MCV requires multiplying by 100 before applying the standard formula's `× 10`, for a
combined constant of `1000` (`Hct_fraction × 1000 / RBC_millions`). Reading the function body at
`mojo/engine/hematology.mojo:34-48` instead:

```mojo
def mean_corpuscular_volume(
    hematocrit_fraction: Float64, rbc_count_millions: Float64
) -> Float64:
    """Mean corpuscular volume: MCV = HCT / RBC_count × 10. ..."""
    if rbc_count_millions <= 0.0:
        return 0.0
    return hematocrit_fraction * 10.0 / rbc_count_millions * 1000.0
```

The combined multiplier is `10.0 * 1000.0 = 10000`, not `1000` — a decimal order of magnitude too
high, and it doesn't even match its own docstring's stated formula (`HCT / RBC_count × 10`, which
would itself be `100×` too *low* if `HCT` really means the fraction, since it's missing the
percent-conversion entirely). Verified against a textbook-normal CBC: `Hct = 0.45` (45%), `RBC = 5.0`
million/µL should return `MCV = 90` fL (mid-normal range is 80–100 fL). The kernel instead computes:

```
0.45 * 10.0 / 5.0 * 1000.0 = 900.0
```

— physiologically nonsensical (no human red cell is 900 femtolitres; that's roughly the volume of a
sphere 12 µm across, twice a normal RBC's diameter). Every call to `mean_corpuscular_volume` in this
build returns a value 10x the correct one; a caller layering their own normal-range check on top
(80–100 fL) would flag every normal patient as grossly macrocytic. `mean_corpuscular_hemoglobin` and
`mchc`, the other two red-cell indices in the same module, were independently checked against the
same textbook values and are correct (`MCH: 15 g/dL / 5M ×10 = 30` pg, mid-normal 27–33 pg; `MCHC: 15
/ 0.45 = 33.3` g/dL, normal 32–36 g/dL) — this is an isolated defect in one function, not a
module-wide unit convention problem.

**`platelet_count_index`'s docstring names a metric its formula doesn't compute.** The docstring
calls it "Platelet large cell ratio index" (evoking P-LCR, a real CBC parameter — the percentage of
platelets whose volume exceeds a threshold, derived from the platelet volume histogram), but the
function body is a plain `MPV × PLT_count / 100`, which is a composite index, not a percentage of
large platelets. Treat the return value as the documented formula computes it, not as clinical P-LCR.

A worked CBC panel, chained through the correct functions: `coagulation_inr(13.0, 12.0, 1.0) =
1.0833...` (mildly prolonged, below the ~2.0–3.0 therapeutic-anticoagulation range),
`oxygen_carrying_capacity(15.0) = 20.1` mL O₂/dL, `platelet_count_index(10.0, 250.0) = 25.0`,
`blood_viscosity_relative(0.45) = 4.457...` (relative to plasma), and
`erythrocyte_sedimentation(3.0, 50.0, 10.0) = 14.45` mm/h for a 50-year-old woman (`sex_factor = 10`)
— within the normal upper bound of roughly `(age + 10) / 2 = 30` mm/h for her demographic.

## `virology`: infection kinetics and lab titration

| Function | What it does |
| --- | --- |
| `basic_reproduction_number(beta, infectious_period, population)` | `β × N × D`, no guard. |
| `viral_doubling_time(growth_rate)` | `ln2 / r`; `0.0` if `r <= 0`. |
| `plaque_forming_units(plaque_count, dilution, volume_ml)` | `count / (dilution × volume)`; `0.0` if dilution or volume is `<= 0`. |
| `burst_size(progeny_particles, initial_infected_cells)` | `progeny / cells`; `0.0` if cells `<= 0`. |
| `eclipse_period(time_of_burst, adsorption_time)` | `t_burst - t_adsorption`, clamped at `0.0`. |
| `neutralisation_titre(log2_dilution_at_50_inhibition)` | `2^log2_dilution`, no guard. |
| `antiviral_ic50(conc_high, conc_low, inhibition_high, inhibition_low)` | Linear interpolation between two dose-response points to find 50% inhibition; falls back to the midpoint concentration if the two inhibition readings — or the resulting slope — are equal. |
| `virus_decay_rate(initial_titre, final_titre, time)` | `ln(N0/N) / t`; `0.0` if either titre or `time` is `<= 0`. |
| `infection_threshold(dose, id50, probit_slope)` | Linear probit approximation, `0.5 + slope·(dose - ID50)/ID50`, clamped to `[0, 1]`; `0.0` if `ID50 <= 0`. |
| `herd_immunity_threshold_viro(r0)` | `1 - 1/R0`; `0.0` for `r0 <= 1` — see the duplication note below. |

**`herd_immunity_threshold_viro` and `immunology.herd_immunity_threshold` are the same function
under two names.** Comparing `mojo/engine/virology.mojo:188-199` against
`mojo/engine/immunology.mojo:156-167`: identical guard (`r0 <= 1.0 → 0.0`), identical formula (`1.0 -
1.0 / r0`), identical return type. The contract lists both as separate entries because they live in
separate modules with separate names, but calling either one with the same `r0` returns the exact
same number — `herd_immunity_threshold(15.0)` and `herd_immunity_threshold_viro(15.0)` both return
`0.9333333333333333`. There is no cross-module import; the formula is simply duplicated verbatim,
once per module that plausibly needs it.

A worked chain ties the epidemiology and the lab-bench halves of this module together at a
measles-like reproduction number: `basic_reproduction_number(0.00003, 5.0, 100000.0) = 15.0` (a
transmission rate, infectious period, and population that combine to R0 = 15), which needs
`herd_immunity_threshold_viro(15.0) = 0.9333...` — over 93% immune coverage — to stop spreading.
Meanwhile, `infection_threshold(1000.0, 1000.0, 1.0)` — a dose exactly at the median infectious dose
— correctly returns `0.5` by construction (that's the definition of ID50), and `antiviral_ic50(10.0,
1.0, 80.0, 20.0)` (80% inhibition at 10 µM, 20% at 1 µM) interpolates to `5.5` µM. A plaque assay at a
10⁻⁶ dilution plating `0.1` mL that yields 45 plaques titers at `plaque_forming_units(45.0, 0.000001,
0.1) = 450000000.0` PFU/mL, and a first-order inactivation from `10^6` down to `10^4` PFU/mL over 24
hours gives `virus_decay_rate(1000000.0, 10000.0, 24.0) = 0.19189...` per hour.

## `cytology`: single-cell geometry and physiology

| Function | What it does |
| --- | --- |
| `cell_volume_sphere(radius_um)` | `(4/3)πr³`, no guard. |
| `nuclear_cytoplasmic_ratio(nucleus_volume, cell_volume)` | `V_nucleus / (V_cell - V_nucleus)`; `0.0` if the derived cytoplasm volume is `<= 0`. |
| `membrane_permeability(flux, area, delta_conc)` | `J / (A·ΔC)`; `0.0` if `A·ΔC <= 0`. |
| `cell_doubling_time(growth_rate)` | `ln2 / μ`; `0.0` if `μ <= 0`. |
| `mitotic_index(dividing_cells, total_cells)` | `dividing / total`; `0.0` if total is `<= 0`. |
| `cell_viability(live_cells, total_cells)` | `live / total`; `0.0` if total is `<= 0`. |
| `apoptosis_rate(annexin_positive, total_cells, time_h)` | `(annexin_positive / total_cells) / time_h`; `0.0` if total cells or duration is `<= 0`. |
| `phagocytic_index(particles_ingested, macrophage_count)` | `particles / macrophages`; `0.0` if macrophage count is `<= 0`. |
| `cell_adhesion_strength(detachment_force_pn, contact_area_um2)` | `force / area`; `0.0` if area is `<= 0`. |
| `osmotic_fragility(nacl_conc_g_dl, median_conc)` | `(median - test) / median`; `0.0` if `median <= 0`. |

A round-number chain: a 5 µm-radius cell (`cell_volume_sphere(5.0) = 523.5987...` µm³) with a nucleus
occupying 300 of a 500 µm³ total volume has `nuclear_cytoplasmic_ratio(300.0, 500.0) = 1.5` — an
elevated N:C ratio is a real cytopathology red flag (the docstring's own note: "elevated in cancer
cells"), because it means the nucleus (`300`) is one and a half times the size of the remaining
cytoplasm (`200`), not merely a large fraction of the whole cell. A culture with `μ = 0.1`/h divides
every `cell_doubling_time(0.1) = 6.931...` hours; a dye-exclusion viability check on that same culture
(`cell_viability(950.0, 1000.0) = 0.95`) and a parallel Annexin-V assay
(`apoptosis_rate(50.0, 1000.0, 4.0) = 0.0125` per hour) describe two different fates for two
different subpopulations of the same 1,000 cells, not a shared denominator that has to sum to `1.0`.

## `cytometry`: flow-cytometry gating and instrument QC

| Function | What it does |
| --- | --- |
| `percent_positive_gate(positive_events, total_events)` | `positive / total × 100`; `0.0` if total is `<= 0`. |
| `median_fluorescence_intensity(sample_mfi, control_mfi)` | `sample / control`; `0.0` if control is `<= 0`. |
| `staining_index(positive_mfi, negative_mfi, negative_sd)` | `(MFI_pos - MFI_neg) / (2 × SD_neg)`; `0.0` if `SD_neg <= 0`. |
| `coefficient_of_variation_peak(std_dev, mean_mfi)` | `(SD / mean) × 100`; `0.0` if the mean is `<= 0`. |
| `cell_cycle_g1_fraction(g1_events, s_events, g2m_events)` | `G1 / (G1 + S + G2M)`; `0.0` if the total is `<= 0`. |
| `apoptosis_annexin_pi(annexin_only, annexin_pi, total)` | `(annexin_only + annexin_pi) / total × 100`; `0.0` if total is `<= 0`. |
| `lymphocyte_subset_ratio(cd4_count, cd8_count)` | `CD4 / CD8`; `0.0` if `CD8 <= 0`. |
| `absolute_count(relative_percent, total_leukocytes_ul)` | `% × WBC_count / 100`, no guard. |
| `compensation_spillover(detector_signal, spillover_fraction, reference_signal)` | `signal - SF × reference`, no guard — can return a negative corrected signal. |
| `sensitivity_lod_cytometry(blank_mean, blank_sd, n_sigma)` | `blank_mean + n_sigma × blank_sd`, no guard. |

Gating a T-cell panel end to end: 450 of 10,000 acquired events fall in a positive gate
(`percent_positive_gate(450.0, 10000.0) = 4.5`%), that marker's sample MFI of 5,000 against an
unstained control of 50 gives `median_fluorescence_intensity(5000.0, 50.0) = 100.0` — far past the
`>2` threshold the docstring calls positive expression — and the same stain's separation quality is
`staining_index(5000.0, 50.0, 20.0) = 123.75`, well past the `>3` well-separated threshold. On the
same run, `lymphocyte_subset_ratio(800.0, 400.0) = 2.0` sits inside the normal 1.5–2.5 CD4:CD8 range,
and converting that CD4 percentage to an absolute count against a differential WBC of 8,000/µL
(`absolute_count(30.0, 8000.0) = 2400.0` cells/µL) is the number a clinician actually tracks for HIV
monitoring, not the raw percentage. Instrument QC on the same day: a CV of 3 around a bead peak mean
of 100 (`coefficient_of_variation_peak(3.0, 100.0) = 3.0`%) is within the `<5%` alignment target, and
a blank with mean 50 and SD 5 sets `sensitivity_lod_cytometry(50.0, 5.0, 3.0) = 65.0` as the 3-sigma
limit of detection.

## Verification

All five `mojo/tests/libs/test_*.mojo` files behind this family
(`test_immunology.mojo`, `test_hematology.mojo`, `test_virology.mojo`, `test_cytology.mojo`,
`test_cytometry.mojo`) are auto-generated coverage smoke tests: each calls every function once with
literal arguments of `0.5` (or `0.5`/`0.5`/`0.5`/`0.5` for four-argument functions) and checks only
that the result is finite — none of them pin a specific numeric output, and a targeted search of
`tests/mojo/test_wave*.mojo` for any function name from these five modules (`hematocrit`,
`antibody_titer`, `virus_decay_rate`, `mitotic_index`, `staining_index`, and others) turned up no
matches, so there is no pinned-numeric suite covering this family anywhere in the repository. Every
worked number in this page was hand-derived from the real formulas in `mojo/engine/immunology.mojo`,
`hematology.mojo`, `virology.mojo`, `cytology.mojo`, and `cytometry.mojo`, cross-checked in plain
Python arithmetic, and — where a standard reference value exists — checked against it directly: the
MCV/MCH/MCHC trio against textbook normal-CBC ranges (which is how the `mean_corpuscular_volume` bug
above was caught), Hüfner's constant (1.34 mL O₂/g Hb) for oxygen-carrying capacity, and the ID50
sanity identity that a dose exactly at the median infectious dose must return probability `0.5`.

**Next:** see [Mixture-of-experts and routing kernels](mixture-of-experts-and-routing-kernels.md) for
another disclosed-but-unused parameter in this same style, or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
