---
icon: landmark
description: Radiocarbon/stratigraphic dating and artifact statistics for archaeology, NIOSH/Fitts's-law/Hick's-law human-factors formulas for ergonomics, time-of-death/toxicology/ballistics calculations for forensics, and MIDI-frequency/interval arithmetic for music theory -- four unrelated scalar-formula libraries.
---

# Humanities and social science kernels

Four modules that share no code and no data shape, only the fact that each formalizes a slice of
an applied human-facing discipline into plain `Float64`/`Int`/`Bool` arithmetic. `archaeology` turns
lab measurements and excavation notes into dates, volumes, and assemblage statistics. `ergonomics`
turns a workstation, a lift, or a noisy shift into a NIOSH-style risk number. `forensics` turns a
body's temperature, a bloodstain's shape, or a bullet's velocity into an estimate a death or crime
investigation can use. `music_theory` turns a MIDI note number or a frequency into the interval,
scale, and rhythm arithmetic a tuner or a sequencer needs. None of the four modules calls another,
and none takes a struct or a status code — every function here is a small, checkable formula over
scalars.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# a C14/C12 ratio of 0.5 -- half of the modern standard -- is one radiocarbon half-life old
runtime.execute("archaeology", "radiocarbon_age_bp", [0.5, 1.21e-4])["result"]
# 5728.489095536738 -- the textbook "~5730 year" C14 half-life, recovered from -ln(ratio)/lambda

# a "perfect fifth" tuned in just intonation (a pure 3:2 frequency ratio) lands 2 cents sharp
# of the equal-tempered fifth every piano and guitar fret actually uses
runtime.execute("music_theory", "cents_between", [440.0, 660.0])["result"]
# 701.9550008653874 -- not the 700.0 cents an equal-tempered fifth would measure
```

## The modules

| Module | What it does |
| --- | --- |
| `archaeology` | Radiocarbon and stratigraphic dating, site-formation and survey-coverage arithmetic, and artifact-assemblage statistics (density, diversity, seriation similarity, discard rate) for excavation and cultural-heritage analysis. |
| `ergonomics` | Human-factors and industrial-hygiene formulas: NIOSH lifting limits, noise-dose and decibel summation, visual angle, Fitts's-law/Hick's-law human-performance models, simplified thermal comfort, and body mass index. |
| `forensics` | Physical and biological evidence-analysis formulas for death investigation and criminalistics: time-of-death cooling models, blood-alcohol pharmacokinetics, rigor-mortis staging, ballistic drop, bloodstain-pattern angle, DNA match probability, fingerprint minutiae scoring, glass refractive-index comparison, and decomposition/toxicology arithmetic. |
| `music_theory` | MIDI-note/frequency conversion, cents and semitone intervals, major/minor scale membership, just-intonation ratios, beat frequency, tempo-to-duration conversion, transposition, octave numbering, and pitch-class (enharmonic) equivalence. |

## `archaeology`: from the trench to a calendar date

| Function | What it does |
| --- | --- |
| `radiocarbon_age_bp(ratio, lambda_val=1.21e-4)` | Age before present from a C14/C12 ratio, `-ln(ratio) / λ`; `0.0` if `ratio <= 0` or `λ <= 0`. |
| `calibrated_date_linear(age_bp, offset=0.0)` | A deliberately **simplified linear** calendar-date conversion, `1950 - age_bp + offset` — a stand-in for a real (nonlinear) calibration curve, not IntCal itself. |
| `stratigraphy_depth_to_age_linear(depth, sedimentation_rate)` | Depth to age assuming one constant deposition rate, `depth / rate`; `0.0` if `rate <= 0`. |
| `artifact_density(n_artifacts, excavation_volume)` | Artifacts per cubic metre excavated, `n / V`; `0.0` if `V <= 0`. |
| `site_area_from_scatter(length, width)` | Surface-scatter area, `L * W`. |
| `ceramic_seriation_similarity(shared_types, total_types_a, total_types_b)` | Sørensen/Dice similarity between two assemblages' ceramic-type inventories, `2*shared / (A + B)`; `0.0` if the denominator is `<= 0`. |
| `dating_uncertainty_combined(sigma1, sigma2)` | Combined dating error in quadrature, `sqrt(σ1² + σ2²)`. |
| `occupation_span(earliest_date, latest_date)` | `latest - earliest`, in whatever calendar convention the caller uses (negative years for BCE). |
| `discard_rate(n_artifacts, occupation_years, population)` | Ethnographic-analogy discard rate, `n / (years * population)`; `0.0` if the denominator is `<= 0`. |
| `surveyed_area_coverage(surveyed, total)` | Percent of a site's total extent actually surveyed, `surveyed / total * 100`; `0.0` if `total <= 0`. |
| `excavation_volume(length, width, depth)` | Excavated volume, `L * W * D`. |
| `artifact_diversity_index(n_types, n_total)` | Margalef richness index, `(S - 1) / ln(N)`; `0.0` if `N <= 1`. |

A single excavation season, worked end to end: a `5m x 3m` trench dug `0.5m` deep is
`excavation_volume(5.0, 3.0, 0.5) = 7.5` m³. Two ceramic assemblages sharing 5 of their types, with
10 and 8 types total respectively, score `ceramic_seriation_similarity(5.0, 10.0, 8.0) = 2*5/18 =
0.5556` — Ford-style seriation treats a higher score as evidence the two contexts are closer in
time. Ten distinct artifact types among 100 total finds give a Margalef diversity of
`artifact_diversity_index(10.0, 100.0) = 9 / ln(100) = 1.9543`. Two independent lab dates with
1-sigma errors of 30 and 40 years combine to `dating_uncertainty_combined(30.0, 40.0) = sqrt(900 +
1600) = 50` years — a 3-4-5 triangle in the error-propagation arithmetic every combined radiocarbon
date uses. A site occupied from 500 BCE to 200 CE spans `occupation_span(-500.0, 200.0) = 700`
years. Across a 200-year occupation with an estimated population of 50, 1,000 recovered artifacts
give a discard rate of `discard_rate(1000.0, 200.0, 50.0) = 1000 / (200*50) = 0.1` artifacts per
person-year — an ethnoarchaeological-analogy figure (after Schiffer) for comparing discard
intensity across sites. `discard_rate` takes whatever occupation-years figure the excavator
supplies as a separate argument; it does not call `occupation_span` itself to derive it, so the two
numbers can disagree if the caller is inconsistent about which span it means.

**`radiocarbon_age_bp` only guards `ratio <= 0`, not `ratio > 1`.** A measured ratio above the modern
standard — post-bomb-pulse enrichment, or lab contamination — is physically nonsensical for an
archaeological sample, but the function does not reject it: `radiocarbon_age_bp(2.0, 1.21e-4) =
-ln(2.0)/1.21e-4 = -5728.489`, a negative "age before present" (i.e., in the future), returned
without complaint. A caller has to apply its own sanity check on the input ratio before trusting the
output.

**`calibrated_date_linear` is explicitly a placeholder, not a calibration curve.** Its own docstring
calls it a "simplified linear calibrated date." Real radiocarbon calibration (IntCal20 and its
predecessors) corrects for historical variation in atmospheric C14 production using a measured,
non-linear tree-ring/varve curve; this function instead does `1950 - age_bp + offset`, a straight
line. `calibrated_date_linear(5000.0)` returns `-3050` (3050 BCE) — useful for a rough estimate or a
test fixture, not for a publication-grade date.

### `archaeology` vs. `taphonomy`: dating a deposit is not fossilizing a bone

[Paleobiology and archaeobotany kernels](paleobiology-and-archaeobotany-kernels.md) documents
`taphonomy`, and the two modules' names invite the same "site formation processes" umbrella —
archaeologists do sometimes call the study of how a deposit forms "site taphonomy." Reading both
`.mojo` sources side by side, though, they implement disjoint arithmetic over disjoint subject
matter. `taphonomy`'s ten functions (`organic_decay_rate`, `bone_density_loss`,
`fossil_completeness`, `permineralisation_rate`, `trampling_abrasion_index`,
`hydraulic_sorting_index`, `time_averaged_assemblage`, `preservation_potential`,
`diagenetic_alteration_index`, `carbon_nitrogen_ratio_bone`) are about what happens to organic and
skeletal *material* after death and burial — soft-tissue decay, mineral leaching or infill,
crystallinity change — largely on paleontological timescales and with no dating arithmetic at all.
`archaeology`'s twelve functions are about *when* a human-occupation deposit formed and what its
artifact content looks like statistically — radiocarbon and stratigraphic dating, survey coverage,
seriation, discard rate — with no bone-diagenesis or fossilization arithmetic at all. The one place
they brush against the same physical process from two different angles:
`stratigraphy_depth_to_age_linear(depth, sedimentation_rate)` here converts a depth straight to an
age assuming one constant rate, while `taphonomy.time_averaged_assemblage(sedimentation_rate,
mixing_depth)` asks a different question about the same rate — how much time-blurring a
bioturbation mixing zone introduces into an assemblage, not what date a given depth represents. No
function name, parameter list, or formula is shared between the two modules; they are complementary
tools for adjacent questions, not a duplicate pair.

## `ergonomics`: human factors and industrial hygiene

| Function | What it does |
| --- | --- |
| `niosh_rwl(lc, hm, vm, dm, am, fm, cm)` | NIOSH Recommended Weight Limit, `LC * HM * VM * DM * AM * FM * CM` — a load constant times six task multipliers. |
| `lifting_index(load_weight, rwl)` | `load / RWL`; values above `1.0` indicate elevated injury risk. |
| `metabolic_rate_walking(body_mass, speed, grade)` | Simplified walking energy expenditure (W), `mass * (2.0 + 3.0*speed + grade*speed*0.5)`. |
| `heat_stress_index(metabolic_heat, evaporative_capacity)` | `M_heat / E_max * 100`; above `100` means the environment cannot dissipate the required heat. |
| `decibel_addition(db1, db2)` | Incoherent sound-pressure-level summation, `10*log10(10^(L1/10) + 10^(L2/10))`. |
| `noise_dose(exposure_time, allowed_time)` | Single-exposure noise dose fraction, `T / T_allowed`. |
| `cumulative_noise_dose_2(t1, ta1, t2, ta2)` | Two-exposure mixed noise dose, `t1/ta1 + t2/ta2`. |
| `visual_angle_minutes(object_size, distance)` | Subtended visual angle in arc-minutes, `2*atan(size/(2*dist)) * (180/π) * 60`. |
| `fitts_law_movement_time(a, b, distance, width)` | Fitts's-law pointing time, `a + b*log2(2*D/W)`. |
| `hicks_law_reaction_time(a, b, n_choices)` | Hick's-law choice-reaction time, `a + b*log2(n+1)`. |
| `comfort_temperature_pmv_simplified(met, clo, air_temp)` | A reduced thermal-comfort estimate; returns `air_temp` minus an estimated neutral temperature — negative means the environment reads cooler than neutral. |
| `body_mass_index(weight_kg, height_m)` | `weight / height²`. |

A doubling of sound energy always adds a fixed `10*log10(2) = 3.0103` dB, independent of the
starting level: `decibel_addition(80.0, 80.0) = 83.0103` and, for two *different* levels,
`decibel_addition(90.0, 80.0) = 90.4139` — the louder source dominates and the quieter one adds
only a fraction of a decibel. A worker exposed at 6 of 8 allowed hours has `noise_dose(6.0, 8.0) =
0.75`; combined across two different exposure segments (4 of 8 allowed hours, then 2 of 4),
`cumulative_noise_dose_2(4.0, 8.0, 2.0, 4.0) = 0.5 + 0.5 = 1.0` — exactly the 100%-dose threshold
occupational-noise standards use to flag a shift as at the exposure limit.

A lift with every NIOSH multiplier at its ideal value of `1.0` returns the load constant itself,
`niosh_rwl(23.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0) = 23.0` kg; degrading every multiplier
(`0.5, 0.8, 0.9, 1.0, 0.7, 0.95`) drops the recommended limit to `niosh_rwl(23.0, 0.5, 0.8, 0.9, 1.0,
0.7, 0.95) = 5.5062` kg. A 25 kg lift against that reduced limit gives `lifting_index(25.0, 5.5062) >
1`, well past the risk threshold, while the same 25 kg against the ideal `23.0` kg limit
(`lifting_index(25.0, 23.0) = 1.087`) is only marginally elevated. `niosh_rwl` does not clamp any
multiplier to the `[0, 1]` range the real NIOSH tables always produce — it trusts the caller to
supply valid values.

A pointing task covering 20 units to a 5-unit-wide target takes
`fitts_law_movement_time(0.1, 0.15, 20.0, 5.0) = 0.1 + 0.15*log2(8) = 0.55` seconds; a 4-choice
reaction takes `hicks_law_reaction_time(0.2, 0.15, 4.0) = 0.2 + 0.15*log2(5) = 0.5483` seconds. A
1 cm object viewed from 1 m subtends `visual_angle_minutes(0.01, 1.0) = 34.377` arc-minutes. At
`met=1.0, clo=0.5, air_temp=22.0`, `comfort_temperature_pmv_simplified` reports exactly `0.0` —
22 °C is this model's neutral point for that activity and clothing level — and at 18 °C it reports
`-4.0`, meaning the room reads 4 degrees cooler than neutral.

**`comfort_temperature_pmv_simplified` is a reduced model, per its own name.** The real Fanger
Predicted Mean Vote incorporates air velocity, humidity, and mean radiant temperature through a
nonlinear equation; this function uses only metabolic rate, clothing insulation, and air
temperature in a linear estimate (`neutral = 22 + (clo - 0.5)*3 - (met - 1.0)*2`), which is why its
own docstring calls the return value an "approximate neutral temperature," not a PMV score on the
standard -3-to-+3 scale.

## `forensics`: physical and biological evidence arithmetic

This is the corpus's only module named `forensics` — among all 643 documented modules there is no
separate "digital forensics" library; every function here is physical or biological criminalistics:
time-of-death and decomposition modeling, toxicology, ballistics, bloodstain-pattern geometry, and
trace-evidence (DNA, fingerprint, glass) comparison statistics. There is nothing here about file
carving, log analysis, or chain-of-custody metadata — that scope simply does not exist in this
codebase.

| Function | What it does |
| --- | --- |
| `time_of_death_newton(t_body, t_ambient, t_normal, k)` | Newton's-cooling-law time since death, `-ln((T_body - T_amb)/(T_norm - T_amb)) / k`; `0.0` if the temperature ratio is non-positive or `k` is `0`. |
| `algor_mortis_rate(body_temp, ambient_temp)` | Simplified linear cooling rate, `(body - ambient) / 10` °C/hr. |
| `blood_alcohol_widmark(alcohol_g, body_weight_kg, r_factor)` | Widmark BAC formula, `A / (W * r)`; `0.0` if the denominator is `0`. |
| `alcohol_elimination_rate(bac, elapsed_hours, beta)` | BAC after linear elimination, `max(0, bac - beta*t)`. |
| `rigor_mortis_stage(hours_since_death)` | Stage `0`-`4` (none, onset, full, passing, resolved) by hours-postmortem thresholds. |
| `ballistic_drop(velocity, distance, gravity)` | Flat-trajectory bullet drop, `0.5 * g * (distance/velocity)²`; `0.0` if `velocity` is `0`. |
| `bloodstain_impact_angle(width, length)` | Impact angle from stain geometry, `asin(width/length)` radians, clamped to `[-1, 1]` before the `asin`. |
| `dna_match_probability(allele_freq1, allele_freq2)` | Hardy-Weinberg heterozygote match probability, `2 * p1 * p2`. |
| `fingerprint_minutiae_score(matching_points, total_points)` | `matching / total`; `0.0` if `total` is `0`. |
| `glass_refractive_index_match(ri1, ri2, tolerance)` | `True` if `\|ri1 - ri2\| < tolerance`. |
| `decomposition_add(accumulated_degree_days, temp, hours)` | Updates accumulated degree-days, `ADD + max(0, temp) * hours / 24`. |
| `toxicology_lethal_dose(ld50, body_weight)` | Estimated lethal dose, `LD50 * body_weight`. |

A body at 30 °C in a 20 °C room, normal temperature 37 °C, cooling constant `k = 0.1`, gives
`time_of_death_newton(30.0, 20.0, 37.0, 0.1) = -ln(10/17)/0.1 = 5.3063` hours since death. A blood
sample with 40 g of alcohol in an 80 kg body at the typical male Widmark factor gives
`blood_alcohol_widmark(40.0, 80.0, 0.68) = 0.7353` g/100mL; two hours later, at a `0.015`/hr
elimination rate, `alcohol_elimination_rate(0.7353, 2.0, 0.015) = 0.7053`. A rifle round at 800 m/s
dropping over 100 m falls `ballistic_drop(800.0, 100.0, 9.81) = 0.5 * 9.81 * 0.125² = 0.0766` m — a
flat-trajectory, no-drag approximation, valid for the kind of short-range reconstruction it is used
for and not a substitute for a full exterior-ballistics solve. A 5 cm-wide, 10 cm-long bloodstain
gives `bloodstain_impact_angle(5.0, 10.0) = asin(0.5) = 0.5236` rad (30°) — a stain that wide
relative to its length came from blood striking the surface at a shallow angle, not perpendicular.
Two alleles at population frequencies 0.1 and 0.2 give a Hardy-Weinberg heterozygote match
probability of `dna_match_probability(0.1, 0.2) = 2*0.1*0.2 = 0.04`. A body accumulating 25 °C for
48 hours adds `decomposition_add(100.0, 25.0, 48.0) = 100 + 25*48/24 = 150` accumulated degree-days;
if the temperature is negative (below freezing), the contribution is clamped to `0` rather than
subtracted, so an ADD total can only climb or hold steady, never fall.

## `music_theory`: pitch, interval, and rhythm arithmetic

| Function | What it does |
| --- | --- |
| `frequency_from_midi(midi_note)` | MIDI note number to Hz, `440 * 2^((n - 69)/12)`. |
| `midi_from_frequency(freq)` | Hz to the nearest MIDI note number, `round(69 + 12*log2(freq/440))`; `0` if `freq <= 0`. |
| `cents_between(freq1, freq2)` | Interval in cents, `1200 * log2(f2/f1)`; `0.0` if either frequency is non-positive. |
| `semitones_between(midi1, midi2)` | Absolute semitone distance between two MIDI notes. |
| `note_in_scale(note_class, scale_root, scale_pattern_idx)` | Whether a pitch class (0-11) is in the major (`0`) or natural-minor (`1`) scale rooted at `scale_root`. |
| `interval_ratio_just(semitones)` | Just-intonation frequency ratio for 0-12 semitones; falls back to the equal-tempered ratio outside that range. |
| `beat_frequency(freq1, freq2)` | Acoustic beat frequency, `\|f1 - f2\|`. |
| `tempo_to_beat_duration(bpm)` | Seconds per beat, `60 / bpm`; `0.0` if `bpm <= 0`. |
| `measures_duration(bpm, beats_per_measure, num_measures)` | Total duration of a run of measures at a fixed tempo and time signature. |
| `transpose_midi(midi_note, semitones)` | `midi_note + semitones`. |
| `octave_from_midi(midi_note)` | MIDI octave number, `(note // 12) - 1` — MIDI 0 is C-1, MIDI 60 is C4. |
| `is_enharmonic(midi1, midi2)` | Whether two MIDI notes share a pitch class, `(midi1 % 12) == (midi2 % 12)`. |

MIDI note 69 (A4, concert pitch) is exactly `frequency_from_midi(69) = 440.0` Hz by construction —
the exponent is `0`, so `2^0 = 1`. Middle C, MIDI 60, is `frequency_from_midi(60) ≈ 261.63` Hz, and
converting back, `midi_from_frequency(261.63) == 60`, round-trips. An octave measures exactly
`cents_between(440.0, 880.0) = 1200.0` cents by definition; the perfect fifth in the opening
example measures `701.955`, not `700.0`, because `cents_between` computes a real logarithmic
interval from the two frequencies given, and `interval_ratio_just(7)` returns the *pure* 3:2 ratio
(`1.5`) rather than the equal-tempered semitone ratio `2^(7/12) = 1.49831` — the same 2-cent gap a
piano tuner hears as "just intonation runs sharp of equal temperament" on the fifth. Outside the
0-12-semitone range the function's own docstring says it falls back to that equal-tempered ratio
instead of a just-intonation one, since there is no single canonical just ratio past an octave.

Four measures of 4/4 time at 120 BPM take `measures_duration(120.0, 4, 4) = (60/120) * 4 * 4 = 8.0`
seconds; a note transposed up a perfect fifth, `transpose_midi(60, 7) = 67`, moves C4 to G4; and
`octave_from_midi(60) == 4` while `octave_from_midi(0) == -1`, matching the MIDI standard's own
`C-1`-at-note-0 convention.

**`is_enharmonic` tests octave-equivalent pitch class, not spelling.** In standard music theory,
"enharmonic" describes two *different note names* for the same sounding pitch — C# and Db, or F#
and Gb. MIDI note numbers cannot represent that distinction at all: C# and Db are both MIDI 61,
with no separate encoding for how the note is spelled. So `is_enharmonic`, working from MIDI
numbers alone, can only ever test the one thing MIDI still exposes — whether two notes share a
pitch class mod 12 — and its own test cases exercise exactly that: `is_enharmonic(60, 72)` (C4 vs.
C5, same letter name two octaves apart) and `is_enharmonic(69, 57)` (A4 vs. A3) both return `True`,
not because those pairs are enharmonically respelled but because they are octave transpositions of
the same note. There is no bug here — a true spelling-level enharmonic check is simply not
expressible from a bare MIDI integer, and the function's real behavior (octave-equivalent pitch
class) is the closest useful proxy.

**`_pow2` is a hand-written Taylor series, not a call to `exp`.** Unlike `ergonomics`'s `_pow10`,
which is built directly on `std.math.exp` (`_pow10(x) = exp(x * ln 10)`), `music_theory.mojo`
imports only `abs` and `log` — no `exp` — and instead computes `2^x` by summing the Taylor series
for `e^(x*ln2)` out to 29 terms by hand. For the exponent ranges this module actually produces
(roughly `-4` to `5`, spanning the full 128-note MIDI range), the series converges well inside
double precision by the 15th term or so, which is why `frequency_from_midi` and
`interval_ratio_just`'s equal-tempered fallback both agree with the closed-form values to within
the wave-test tolerances above — it is a stylistic choice in this module, not a source of extra
error.

## Verification

`mojo/tests/libs/test_archaeology.mojo`, `test_ergonomics.mojo`, `test_forensics.mojo`, and
`test_music_theory.mojo` are auto-generated coverage smoke tests — every function is called once
with fixed literal arguments and checked only for a finite/non-crashing result, with no numeric
value pinned. The real, hand-verified numeric coverage lives in four separate pinned test files:
`tests/mojo/test_wave87.mojo` (archaeology, alongside distillation and LiDAR), `test_wave69.mojo`
(ergonomics, alongside tribology and combustion), `test_wave72.mojo` (forensics, alongside
transportation and nuclear physics), and `test_wave63.mojo` (music theory, alongside cellular
automata and auction theory). Every worked number on this page is drawn from one of those four
files or independently re-derived in Python from the corresponding formula in
`mojo/engine/{archaeology,ergonomics,forensics,music_theory}.mojo`, and reproduces to the precision
shown.

**Next:** see [Paleobiology and archaeobotany kernels](paleobiology-and-archaeobotany-kernels.md)
for `taphonomy`'s disjoint post-mortem/diagenesis arithmetic, or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
