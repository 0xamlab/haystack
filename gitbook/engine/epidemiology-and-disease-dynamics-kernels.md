---
icon: virus
description: Compartmental disease-spread models and outbreak metrics, the risk-factor and diagnostic-test statistics used to argue a cause, and molecular assay quantification for gene regulation that never touches the DNA sequence.
---

# Epidemiology and disease dynamics kernels

Three modules that share a Greek prefix and little else. `epidemiology` is population-level disease
spread — SIR/SEIR compartmental simulation, the reproduction number, herd immunity, doubling time,
attack rate, case-fatality and incidence rates: the arithmetic behind "how fast is this spreading and
when does it stop." `etiology` is the statistics a study uses to argue a factor causes a disease —
relative risk, odds ratio, attributable risk, population attributable risk, number needed to treat —
bundled together with a second, related toolkit: the Bayesian performance metrics of a diagnostic test
(sensitivity, specificity, predictive values, likelihood ratio) that a screening or etiologic study
also has to report. `epigenetics` is neither population-level nor a study design — it is molecular
assay quantification: methylation fractions from bisulfite sequencing, ChIP-seq fold-enrichment for
histone marks, ATAC-seq chromatin accessibility, a simplified epigenetic-clock age estimate, CpG-island
detection, and gene-silencing efficiency, computed from raw read counts and signal intensities at a
single locus or gene. None of the ten `epigenetics` functions take a population size, an incidence, or
a study-design argument; they operate one assay result at a time. The three modules are grouped on
this page because they all carry the "epi-" prefix (Greek *epi-*, "upon/around") and all describe
disease biology, not because they share formulas, inputs, or a level of analysis — see
["Three different scales sharing one page"](#three-different-scales-sharing-one-page) below.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# One Euler step of an SIR outbreak: 990 susceptible, 10 infected, 0 recovered,
# beta=0.4 (transmission rate), gamma=0.1 (recovery rate), dt=0.1 days
runtime.execute("epidemiology", "sir_step", [990.0, 10.0, 0.0, 0.4, 0.1, 0.1])["result"]
# [989.604, 10.296, 0.1] -- S+I+R is still exactly 1000.0, population is conserved

# Same beta/gamma as a screening test's Bayes update: sensitivity=0.8, specificity=0.9,
# prevalence=0.01 (a mammography-style scenario)
runtime.execute("etiology", "positive_predictive_value", [0.8, 0.9, 0.01])["result"]
# 0.07476635514018692 -- most positive results are still false positives at 1% prevalence
```

## The modules

| Module | What it does |
| --- | --- |
| `epidemiology` | SIR and SEIR compartmental simulation (single-step and multi-step), basic and effective reproduction number, herd-immunity threshold, exponential doubling time, final-epidemic-size attack rate, case-fatality rate, and incidence rate. |
| `etiology` | Cohort and case-control risk-factor statistics for arguing causation (relative risk, odds ratio, attributable risk, population attributable risk, number needed to treat), plus the diagnostic-test performance metrics a study reports alongside them (sensitivity, specificity, positive/negative predictive value, positive likelihood ratio). |
| `epigenetics` | Per-locus molecular assay quantification for gene regulation that does not alter the DNA sequence: methylation fraction, a simplified epigenetic-clock age estimate, histone acetylation and H3K27ac/H3K4me3 enhancer-vs-promoter ratios, ATAC-seq chromatin accessibility, allelic imprinting ratio, CpG observed/expected ratio, siRNA/miRNA gene-silencing efficiency, Polycomb (H3K27me3) fold-enrichment, and a composite transcription-factor occupancy score. |

## `epidemiology`: compartments, thresholds, and outbreak metrics

| Function | What it does |
| --- | --- |
| `sir_step(S, I, R, beta, gamma, dt)` | One forward-Euler step of the SIR ODEs. Returns `[S', I', R']`; `N = S+I+R` is held fixed and recomputed each call, never passed in. |
| `sir_simulate(S0, I0, R0, beta, gamma, dt, n_steps)` | Runs `sir_step` `n_steps` times, returning `n_steps + 1` rows (`[S,I,R]`), the first being the unmodified initial condition. |
| `seir_step(S, E, I, R, beta, sigma, gamma, dt)` | One Euler step of the SEIR ODEs, adding an exposed-but-not-yet-infectious compartment with progression rate `sigma`. Returns `[S', E', I', R']`. |
| `basic_reproduction_number(beta, gamma)` | `R0 = beta / gamma`; `0.0` if `gamma == 0`. |
| `herd_immunity_threshold(R0)` | `HIT = 1 - 1/R0`; `0.0` if `R0 <= 0`. |
| `effective_reproduction(R0, vaccinated_fraction)` | `Re = R0 * (1 - vaccinated_fraction)` — assumes 100% vaccine efficacy; there is no separate efficacy argument. |
| `doubling_time(growth_rate)` | `ln(2) / growth_rate`; `0.0` if `growth_rate == 0`. |
| `attack_rate(R0)` | Final epidemic size `z` solving `z = 1 - exp(-R0*z)` by 200 fixed-point iterations from `z=0.99`; returns `0.0` outright for `R0 <= 1` (a subcritical outbreak never takes off). |
| `case_fatality_rate(deaths, cases)` | `deaths / cases`; `0.0` if `cases == 0`. |
| `incidence_rate(new_cases, population, time_period)` | `new_cases / (population * time_period)`; `0.0` if the denominator is `0`. |

`sir_step` and `seir_step` conserve population by construction: `dS + dI + dR` (or `dS+dE+dI+dR`) sums
to `0.0` for any inputs, because every term that leaves one compartment is added to exactly one other —
`beta*S*I/N*dt` leaves `S` and enters `I` (via `E` in the SEIR case), `gamma*I*dt` leaves `I` and enters
`R`. Running `sir_step(990.0, 10.0, 0.0, 0.4, 0.1, 0.1)` gives `[989.604, 10.296, 0.1]`; the sum is
`1000.000000000000...1`, matching the input `N=1000.0` to floating-point roundoff, and `mojo/tests/mojo/test_wave51.mojo::test_sir_step_conservation` asserts exactly this.

**`attack_rate` is the classic Kermack–McKendrick final-size relation, solved by fixed-point
iteration, not a closed form.** There is no algebraic solution for `z` in `z = 1 - exp(-R0*z)`, so
the function iterates the same substitution 200 times regardless of how quickly it converges. For
`R0 = 2.0`, iterating from `z0 = 0.99` converges to `z ≈ 0.79681213`, matching the textbook value of
"about 80% ultimately infected" for `R0=2`, and `test_wave51.mojo::test_attack_rate` pins this to
`0.7968` at a `0.01` tolerance. For `R0 = 4.0` it converges to `z ≈ 0.98017`, and for any `R0 <= 1.0`
the function returns `0.0` immediately without iterating at all — `test_attack_rate_subcritical` checks
`attack_rate(0.5) == 0.0`.

```python
runtime.execute("epidemiology", "basic_reproduction_number", [0.4, 0.1])["result"]
# 4.0
runtime.execute("epidemiology", "herd_immunity_threshold", [4.0])["result"]
# 0.75 -- 75% of the population needs immunity to bring Re below 1
runtime.execute("epidemiology", "effective_reproduction", [4.0, 0.75])["result"]
# 1.0 -- vaccinating exactly the herd-immunity fraction drives Re to precisely 1.0
runtime.execute("epidemiology", "attack_rate", [2.0])["result"]
# 0.7968121300200202
```

{% hint style="info" %}
**`effective_reproduction` assumes a perfectly effective vaccine.** The formula is `R0 * (1 -
vaccinated_fraction)`, which is the textbook `Re = R0(1 - vp*e)` special-cased to vaccine efficacy
`e = 1.0` — there is no separate efficacy parameter, so a caller modeling an imperfect vaccine (say,
70% effective) has to pre-multiply `vaccinated_fraction` by that efficacy before calling this function,
not pass the raw vaccination coverage.
{% endhint %}

## `etiology`: causal-association statistics and diagnostic-test performance

| Function | What it does |
| --- | --- |
| `relative_risk(incidence_exposed, incidence_unexposed)` | `RR = I_e / I_u` from a cohort study; `0.0` if `I_u <= 0`. |
| `odds_ratio(cases_exposed, cases_unexposed, controls_exposed, controls_unexposed)` | Cross-product ratio from a 2×2 case-control table: `(cases_exposed × controls_unexposed) / (cases_unexposed × controls_exposed)`; `0.0` if the denominator is `<= 0`. |
| `attributable_risk(incidence_exposed, incidence_unexposed)` | `AR = I_e - I_u`, the absolute risk difference. |
| `population_attributable_risk(exposure_prevalence, relative_risk)` | `PAF = p(RR-1) / (p(RR-1)+1)`; `0.0` if the denominator is `<= 0`. |
| `number_needed_to_treat(control_event_rate, treatment_event_rate)` | `NNT = 1 / (control_event_rate - treatment_event_rate)`; `0.0` if the treatment does not reduce the event rate (`ARR <= 0`). |
| `sensitivity_test(true_positive, false_negative)` | `Se = TP / (TP + FN)`. |
| `specificity_test(true_negative, false_positive)` | `Sp = TN / (TN + FP)`. |
| `positive_predictive_value(sensitivity, specificity, prevalence)` | Bayes' theorem: `Se·p / (Se·p + (1-Sp)(1-p))`. |
| `negative_predictive_value(sensitivity, specificity, prevalence)` | Bayes' theorem: `Sp(1-p) / (Sp(1-p) + (1-Se)p)`. |
| `likelihood_ratio_positive(sensitivity, specificity)` | `LR+ = Se / (1 - Sp)`; `0.0` if `Sp >= 1.0`. |

**These ten functions are two related toolkits, not one.** `relative_risk`, `odds_ratio`,
`attributable_risk`, `population_attributable_risk`, and `number_needed_to_treat` take incidences or
2×2 table counts and answer "how much does the exposure change the outcome" — the actual causal
question etiology studies. `sensitivity_test`, `specificity_test`, `positive_predictive_value`,
`negative_predictive_value`, and `likelihood_ratio_positive` take true/false positive/negative counts
or a prevalence and answer a different question — "how much should a test result change what I
believe" — which is diagnostic epidemiology, not causal-association epidemiology, but is conventionally
reported by the same case-control and cohort studies that etiology designs, which is presumably why
both toolkits live in one module here.

A cross-product worked example, matching a textbook case-control table (90 lung-cancer cases who
smoked, 60 who didn't; 60 smoking controls, 140 non-smoking controls):

```python
runtime.execute("etiology", "odds_ratio", [90.0, 60.0, 60.0, 140.0])["result"]
# 3.5 -- (90*140) / (60*60)
```

And a screening-test Bayes update at 1% prevalence, sensitivity 80%, specificity 90% (a classic
mammography-style teaching example):

```python
se, sp, prev = 0.8, 0.9, 0.01
runtime.execute("etiology", "positive_predictive_value", [se, sp, prev])["result"]
# 0.07476635514018692 -- most positives are false positives when prevalence is low
runtime.execute("etiology", "negative_predictive_value", [se, sp, prev])["result"]
# 0.9977603583426652
runtime.execute("etiology", "likelihood_ratio_positive", [se, sp])["result"]
# 8.000000000000002
```

A relative-risk and NNT scenario for a hypothetical exposure that quadruples incidence
(`incidence_exposed=0.04`, `incidence_unexposed=0.01`), then a separate treatment that cuts an event
rate from 5% to 2%:

```python
runtime.execute("etiology", "relative_risk", [0.04, 0.01])["result"]
# 4.0
runtime.execute("etiology", "attributable_risk", [0.04, 0.01])["result"]
# 0.03
runtime.execute("etiology", "population_attributable_risk", [0.3, 4.0])["result"]
# 0.47368421052631576 -- 30% exposure prevalence, RR=4.0
runtime.execute("etiology", "number_needed_to_treat", [0.05, 0.02])["result"]
# 33.33333333333333 -- treat 34 patients to prevent one event
```

## `epigenetics`: per-locus assay quantification

| Function | What it does |
| --- | --- |
| `methylation_index(methylated_reads, total_reads)` | Bisulfite-sequencing β-value: `methylated / total`; `0.0` if `total_reads <= 0`. |
| `dna_methylation_age(beta_value, intercept, slope)` | `age = intercept + slope × β` — a single-CpG linear stand-in for a Horvath-style epigenetic clock, not the real multi-CpG model (see below). |
| `histone_acetylation_ratio(acetylated_signal, total_histone_signal)` | `acetylated / total`; `0.0` if the denominator is `<= 0`. |
| `chromatin_accessibility(atac_reads, background_reads, library_size)` | `(atac_reads - background_reads) / sqrt(library_size)` — a z-score-like ATAC-seq openness score; `0.0` if `library_size <= 0`. |
| `imprinting_ratio(maternal_expr, paternal_expr)` | `maternal / (maternal + paternal)`; `0.5` (biallelic) if both are `0`. |
| `cpg_observed_expected(cpg_count, c_count, g_count, length)` | `(CpG × length) / (C × G)`, the Gardiner-Garden & Frommer CpG-island O/E ratio; `0.0` if either denominator term or `length` is `<= 0`. |
| `gene_silencing_efficiency(control_expression, treated_expression)` | `1 - treated/control`, clamped to `0.0` on the low end (silencing cannot be negative); `0.0` if `control_expression <= 0`. |
| `enhancer_activity_index(h3k27ac_signal, h3k4me3_signal)` | `H3K27ac / (H3K27ac + H3K4me3)`; `0.0` if both are `0`. |
| `polycomb_enrichment(h3k27me3_chip, h3k27me3_input)` | `chip / input` fold-enrichment; `0.0` if `input <= 0`. |
| `transcription_factor_occupancy(chip_enrichment, motif_score, accessibility)` | `chip_enrichment × motif_score × accessibility` — an unguarded product of three factors, no denominator to protect. |

A CpG-island detection contrast: a typical bulk-genome 1 kb window (250 C, 250 G, 15 observed CpG
dinucleotides against 62.5 expected under independence) scores well below the island cutoff, while a
GC-rich 1 kb window with less CpG suppression (280 C, 280 G, 55 observed CpG) clears it:

```python
runtime.execute("epigenetics", "cpg_observed_expected", [15.0, 250.0, 250.0, 1000.0])["result"]
# 0.24 -- typical genome-wide CpG suppression (real bulk-genome O/E runs roughly 0.2-0.25)
runtime.execute("epigenetics", "cpg_observed_expected", [55.0, 280.0, 280.0, 1000.0])["result"]
# 0.7015306122448980 -- clears the conventional >0.6 CpG-island threshold
```

An ATAC-seq accessibility score and a Polycomb-repression fold-enrichment, chained the way a real
ChIP-seq/ATAC-seq pipeline would report them for the same locus:

```python
runtime.execute("epigenetics", "chromatin_accessibility", [1200.0, 200.0, 25.0])["result"]
# 200.0 -- (1200-200) / sqrt(25)
runtime.execute("epigenetics", "polycomb_enrichment", [450.0, 90.0])["result"]
# 5.0 -- fold enrichment over input, above the >3 "enriched domain" threshold noted in its docstring
```

{% hint style="warning" %}
**`dna_methylation_age` is explicitly a simplified stand-in, not the real Horvath clock.** The actual
Horvath (2013) epigenetic clock regresses age on the methylation β-values of 353 specific CpG sites
using an elastic-net model, then passes the result through a nonlinear log/linear transform that
treats ages above and below 20 years differently. `dna_methylation_age` here takes one `beta_value`
and returns a plain `intercept + slope * beta_value` — a single-locus linear model. The module's own
docstring calls this "Horvath-style" and "simplified," so this is not a misrepresentation, but it is
worth being explicit that plugging a real Horvath-clock intercept/slope pair into this function for a
single CpG will not reproduce a real clock's age estimate, which needs all 353 sites and the nonlinear
transform to work.
{% endhint %}

## Three different scales sharing one page

`epidemiology` operates on a population's compartment sizes (`S`, `I`, `R`, or `S`, `E`, `I`, `R`) and
never touches an individual read count or assay signal. `etiology` operates one level down, on
group-level incidences, 2×2 table counts, or a study's true/false positive counts — still aggregate
numbers, but describing a sample or study rather than a live epidemic. `epigenetics` operates another
level down still, on a single locus's raw molecular measurements — read counts, ChIP signal, allelic
expression — and none of its ten functions accept a population size, an incidence, or a study-design
count of any kind. Grepping the rest of `gitbook/` for `epidemiology`, `etiology`, and `epigenetics`
by name turns up nothing outside the machine-generated
[Runtime library catalog](runtime-library-catalog.md), so there is no existing page these three
duplicate; the general-purpose statistical machinery each rests on lives in
[Causal inference](causal-inference.md) (identification, backdoor adjustment, sensitivity analysis —
the graph-level reasoning underneath what `etiology`'s risk-ratio functions assume is already
identified) and [Survival analysis](survival-analysis.md) (time-to-event and censoring, the piece of
outbreak and cohort data that compartmental SIR/SEIR models and simple incidence rates do not model at
all).

## Verification

All three `mojo/tests/libs/test_*.mojo` files behind this page (`test_epidemiology.mojo`,
`test_etiology.mojo`, `test_epigenetics.mojo`) are auto-generated coverage smoke tests: each calls
every function once with literal `0.5` arguments and checks only that the result is finite. `etiology`
and `epigenetics` have no other numeric tests in this codebase — their worked examples above were
hand-derived from the real formulas in `mojo/engine/etiology.mojo` and `mojo/engine/epigenetics.mojo`
and independently checked against standard epidemiology/molecular-biology reference calculations
(cross-product odds ratio, Bayes'-theorem predictive values, and the Gardiner-Garden & Frommer CpG
O/E ratio) before being presented here. `epidemiology` is the exception: `tests/mojo/test_wave51.mojo`
carries real pinned numeric assertions — SIR/SEIR population conservation, `basic_reproduction_number(0.4,
0.1) == 4.0`, `herd_immunity_threshold(4.0) == 0.75`, `attack_rate(2.0) ≈ 0.7968` (tolerance `0.01`),
and `attack_rate(0.5) == 0.0` for a subcritical epidemic — and every `epidemiology` number in this page
was lifted directly from that file rather than hand-computed.

**Next:** see [Causal inference](causal-inference.md) for the identification machinery behind a causal
risk-ratio claim, or browse the [Runtime library catalog](runtime-library-catalog.md) for every module
and function.
