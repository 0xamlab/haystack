---
icon: tree
description: Tree-ring dating and climate-signal statistics, forest-mensuration biometrics, quantitative pollen/spore analysis, and fossil preservation and decay-process formulas across four independent historical-biology kernel modules.
---

# Paleobiology and archaeobotany kernels

Four modules for reconstructing history from what a living or dead organism physically left behind:
the annual growth rings in a tree trunk, the tree's own size and shape as measured in the field, the
pollen grains buried in a lake or peat core, and the slow physical and chemical changes that turn a
carcass or a plant into a fossil. `dendrochronology` and `dendrology` share a subject (trees) but not
a purpose — one dates and cross-correlates ring-width series against climate, the other measures a
standing tree's dimensions and biomass. `palynology` and `taphonomy` are the corresponding tools for,
respectively, pollen assemblages preserved in sediment and skeletal or organic remains preserved in
rock or soil. All forty functions take and return plain `Float64` scalars, matching the calling
convention used across the rest of this corpus.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Two ring-width series overlap 50 years with a Pearson correlation of 0.6 --
# is that a real cross-date or a coincidence?
runtime.execute("dendrochronology", "crossdating_t_value", [0.6, 50.0])["result"]
# 5.196152422706631 -- comfortably past the ~3.5 t-value COFECHA-style
# crossdating treats as a confident match at this overlap length

# A field hypsometer reading for a tree whose real height is independently
# known to be 15 m: 20 m horizontal distance, 33.822 deg up to the top,
# 4.574 deg *down* to the base (the observer's eye is 1.6 m above the ground)
runtime.execute("dendrology", "tree_height_from_hypsometer",
                [20.0, 33.82208521749396, -4.573921259900861])["result"]
# 11.799176774345243 -- see "A sign the source gets backwards" below; the
# true answer this reading should produce is 15.0
```

## The modules

| Module | What it does |
| --- | --- |
| `dendrochronology` | Tree-ring dating and climate-signal statistics: ring-width indexing and negative-exponential detrending, basal-area increment, mean sensitivity, lag-1 autocorrelation, the Expressed Population Signal and a signal-free chronology step, pointer-year thresholds, cross-dating significance, and a ring-width-vs-temperature regression slope. |
| `dendrology` | Forest-mensuration biometrics for a standing tree: clinometer/hypsometer height, crown area and competition factor, stem taper (form quotient), heartwood ratio, sapwood area, coarse-root and leaf biomass allometry, ring-count age, and area-based foliar nitrogen from specific leaf area. |
| `palynology` | Quantitative pollen and spore analysis: exotic-spike concentration counting, pollen accumulation rate, a Shannon-style taxa diversity index, relative pollen percentage and its R-value productivity correction, the arboreal/non-arboreal vegetation indicator, mass-normalised influx, a spore germination degree-day index, trap-based productivity estimation, and atmospheric transport distance. |
| `taphonomy` | Fossilisation and post-mortem decay-process formulas: first-order soft-tissue decay, exponential bone mineral density loss, skeletal completeness, permineralisation rate, trampling abrasion and hydraulic sorting indices, time-averaging from sedimentation and bioturbation, a preservation-potential score, bone crystallinity (diagenetic alteration) index, and the collagen-quality C:N ratio. |

## `dendrology`'s real scope is forest mensuration, not general tree biology

The academic subject "dendrology" ordinarily covers tree taxonomy, wood anatomy, and disease
pathology as well as biology proper. This module's ten functions do none of that — every one of them
is a field-forestry measurement formula: converting a clinometer/hypsometer reading into height,
turning crown radii into projected area, estimating a stand's crown competition factor from DBH and
stems-per-hectare, computing form quotient (stem taper), heartwood-to-sapwood ratios, allometric
sapwood-area/root-biomass/leaf-biomass estimates from DBH, an increment-core ring-count age, and
area-based foliar nitrogen from specific leaf area. It is a forest-mensuration and tree-allometry
toolkit specifically, not a general tree-science module — closer in spirit to a forester's field
manual than to a botany textbook.

## A sign the source gets backwards

`tree_height_from_hypsometer`'s docstring is explicit about its sign convention:
`angle_top_deg` is "positive upward" and `angle_base_deg` is "negative if below horizontal" — the
same above/below-horizontal convention applied to both angles. Given that convention, the
mathematically correct combination is `distance * (tan(angle_top) - tan(angle_base))`: when the
tree's base reads below horizontal (the ordinary case, since a standing observer's eye is always
above ground level), `angle_base_deg` is negative, so subtracting it *adds* the eye-height segment
back onto the tree's total height. The source instead computes `distance_m * (tan_top + tan_base)`
— addition, not subtraction.

Worked independently: a tree is really 15 m tall, the observer stands 20 m away with eyes 1.6 m
above the ground. That gives `angle_top_deg = 33.822...` and, following the module's own convention,
`angle_base_deg = -4.574...` (a depression of `atan(1.6/20)`). Plugging those two numbers into the
coded formula returns `11.799...` m — 21% short of the tree's actual, independently-known height.
Substituting the mathematically-required subtraction (`tan_top - tan_base`) into the same inputs
returns `15.000...` m, matching the true height to the last digit. The discrepancy is not a rounding
artifact of the `sin_approx`/`cos_approx` Taylor-series helpers (below): plugging the exact same
angles through Python's real `math.tan` into both formula variants reproduces the identical
`11.799` vs `15.000` split. Any caller feeding this function a genuine field reading — where the base
angle is a depression, as it is in nearly every real hypsometer sighting — gets a tree height that
runs low, silently, with no error and no out-of-range flag.

{% hint style="warning" %}
This is a real formula bug verified independently against the module's own stated sign convention,
not a fabricated finding — see `mojo/engine/dendrology.mojo`, `tree_height_from_hypsometer`. It has
not been patched here; this page documents the source as it actually behaves.
{% endhint %}

`sin_approx` and `cos_approx` are their own separate, smaller caveat: they are truncated Taylor
series (5th-order sine, 4th-order cosine), not calls into a real trig library. They track the true
`sin`/`cos` to within `3e-6` out to 45°, but the error grows fast past that — `2.7e-4` at 60°,
`1.4e-2` (1.4%) in `cos_approx` at 85°. A hypsometer sighting on a very tall, very close tree can
require a steep look angle where this approximation, independent of the sign issue above, starts to
matter.

## Worked examples, hand-verified against the source formulas

None of the four modules' `mojo/tests/libs/test_*.mojo` files pin any numeric output — like most of
this corpus, they are auto-generated coverage smoke tests that call every function once with literal
`0.5` arguments and check only that the result is finite (`test_dendrochronology.mojo`,
`test_dendrology.mojo`, `test_palynology.mojo`, `test_taphonomy.mojo`). No `tests/mojo/test_wave*.mojo`
suite touches any of these four module names either. Every number below was independently computed
in Python from the real formulas in `mojo/engine/{dendrochronology,dendrology,palynology,taphonomy}.mojo`.

**`dendrochronology`.** A 50-year cross-date at `r = 0.6` gives `crossdating_t_value(0.6, 50) =
5.196...` (shown above). `expressed_population_signal(0.6, 10)` — ten trees averaging `rbar = 0.6` —
returns `0.9375`, comfortably past the `0.85` threshold Wigley et al. (1984) treat as an adequately
replicated chronology; the same `rbar` with only 5 trees, `expressed_population_signal(0.6, 5)`,
drops to `0.882`, still adequate but with much less margin. `pointer_year_threshold(1.0, 0.3, 1.28)`
— mean ring-width index 1.0, std 0.3, the 90th-percentile multiplier the docstring names — returns
`0.616`, the index value a year's ring width must fall below to register as a negative pointer year.

**`dendrochronology`'s `first_order_autocorrelation` and `temperature_response` both accept
parameters their own arithmetic never touches.** `first_order_autocorrelation(mean, n,
sum_lag_product, sum_sq_dev)` documents `mean` and `n` in its signature, but the function body is a
single division, `sum_lag_product / sum_sq_dev` — `mean` and `n` are only needed by whatever computed
those two sums in the first place, not by this final step. `temperature_response(sum_rw_t_product,
sum_t_sq, n, mean_rw, mean_t)` has the same shape: the returned regression slope is
`sum_rw_t_product / sum_t_sq`, and `n`, `mean_rw`, `mean_t` play no part in the number produced. This
mirrors a pattern documented elsewhere in this corpus (`mixture_of_experts.router_z_loss`,
`moe_routing.expert_choice_gate`) where a function's signature preserves the full set of statistics a
caller is likely to be carrying around, even though only some of them feed this particular formula.

**`dendrology`.** `crown_competition_factor(35.0, 400)` — a 35 cm mean DBH stand at 400 stems/ha —
returns `211.99`, well past the `>100` threshold the docstring names for a closed, overlapping
canopy. `heartwood_ratio(12.0, 17.5)` (12 cm heartwood radius inside a 17.5 cm total stem radius)
returns `0.470` — heartwood is under half the cross-sectional area at this stage. `foliar_nitrogen_content(20.0,
10.0)` (20 mg N/g leaf dry weight, SLA 10 m²/kg) returns exactly `2.0` g N/m²: the mg/g-to-g/m²
unit factor of 1000 in the numerator and the kg-to-g factor of 1000 in SLA's denominator cancel
exactly, so the formula's stated units (`N_area = N_mass / SLA`) hold without any hidden scaling
error.

**`palynology`.** `pollen_concentration(850, 400, 12000, 1.0)` — 850 indigenous grains and 400 exotic
marker grains counted in a 1 cm³ sample spiked with 12,000 exotic grains (the standard Stockmarr
exotic-spike method) — returns `25500.0` grains/cm³. Feeding that concentration through
`pollen_accumulation_rate(25500.0, 0.05)` at a 0.05 cm/yr sedimentation rate gives `1275.0`
grains/cm²/yr. `taxa_diversity_index(1/8, 8)` — eight taxa each at exactly 1/8 relative abundance,
perfectly even — returns `2.0794415...`, which is `ln(8)` to every digit: the formula's own
`-n * p * ln(p)` collapses to `-n * (1/n) * ln(1/n) = ln(n)` at perfect evenness, the same
maximum-entropy identity that shows up as `sparse_gate_entropy`'s ceiling of `1.0` in the
mixture-of-experts kernels.

**`palynology`'s `pollen_influx` docstring formula does not match its own code.** The docstring
states `influx = PAR × bulk_density × 10`, but the function body is `par / bulk_density_g_cm3` — a
division, with no `× 10` factor anywhere in the implementation. Concretely,
`pollen_influx(1275.0, 1.2)` returns `1062.5` (division); the docstring's stated formula would give
`1275.0 * 1.2 * 10 = 15300.0` instead — nothing like the same order of magnitude. This page documents
what the code actually computes (division by bulk density); a caller relying on the docstring's
written formula instead of the real arithmetic will be off by more than an order of magnitude and a
different operation entirely.

**`taphonomy`.** `fossil_completeness(120, 206)` — 120 of a human skeleton's 206 total elements
preserved — returns `58.25`%. `carbon_nitrogen_ratio_bone(42.0, 15.3)` (42 wt% carbon, 15.3 wt%
nitrogen, using the code's more precise atomic weights of 12.011 and 14.007 rather than the
docstring's simplified "12"/"14") returns an atomic C:N of `3.201`, squarely inside the `3.0`–`3.6`
range the docstring calls well-preserved collagen. `bone_density_loss(1.9, 500, 0.0015)` — fresh
bone density 1.9 g/cm³, 500 years of diagenesis at a leaching-rate constant of 0.0015/yr — returns
`0.897` g/cm³, a 53% density loss over five centuries at that rate. `time_averaged_assemblage(0.5,
30)` (a 30 mm mixing/bioturbation depth against 0.5 mm/yr sedimentation) returns `60.0` years: a
death assemblage in that setting mixes together 60 years' worth of individual deaths before the
sediment finally buries it below the reworking zone.

## Edge-case behavior worth knowing

* `ring_width_index`, `standardise_negative_exp`, `sensitivity_coefficient`, `pointer_year_threshold`
  (via its callers), `crossdating_t_value`, and `temperature_response` all guard their denominators
  and return a sentinel (`0.0`, or `1.0` for `standardise_negative_exp`'s degenerate trend) rather
  than dividing by zero or producing NaN.
* `expressed_population_signal` returns `0.0` if `n_trees * rbar + (1 - rbar) <= 0` — a pathological
  input (very negative `rbar`, or zero trees) rather than an undefined ratio.
* `pollen_concentration`, `r_value_correction`, `pollen_influx`, and `pollen_productivity_estimate`
  all return `0.0` on a non-positive denominator input (exotic count, sample volume, R-value, bulk
  density, vegetation cover, or distance), rather than propagating an infinity.
* `permineralisation_rate`, `preservation_potential`, `diagenetic_alteration_index`, and
  `bone_density_loss` in `taphonomy` have no guards at all — they are plain arithmetic over inputs
  the docstrings assume are already sane (porosity in `[0,1]`, positive burial depth, and so on).

## Verification

`mojo/tests/libs/test_dendrochronology.mojo`, `test_dendrology.mojo`, `test_palynology.mojo`, and
`test_taphonomy.mojo` are auto-generated coverage smoke tests: each calls every function once with
literal `0.5` arguments (or `0.5`/`0.5`/`0.5`/`0.5` for four-argument functions) and checks only that
the result is finite — none of them pin a specific numeric output, and none of the four module names
appear in any `tests/mojo/test_wave*.mojo` hand-verified suite. Every worked number on this page,
including the `tree_height_from_hypsometer` and `pollen_influx` discrepancies, was independently
computed in Python from the real formulas in `mojo/engine/dendrochronology.mojo`, `dendrology.mojo`,
`palynology.mojo`, and `taphonomy.mojo`, and can be reproduced by re-running the same arithmetic.

**Next:** see [Historical geology and paleoclimate kernels](historical-geology-and-paleoclimate-kernels.md)
for the radiometric and sediment-dating methods these ring/pollen/bone records get calibrated
against, or browse the [Runtime library catalog](runtime-library-catalog.md) for every module and
function.
