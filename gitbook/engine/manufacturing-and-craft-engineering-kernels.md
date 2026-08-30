---
icon: screwdriver-wrench
description: Joint-strength and heat-control physics for arc welding, mechanical-watch gear trains and escapement timing, press production math for printing, corrugated-box and container engineering, and textile-care process physics for laundry.
---

# Manufacturing and craft engineering kernels

Five modules for the physics and production math behind making and finishing physical goods, at
scales from a wristwatch movement to a shipping pallet. `welding` covers how much heat an arc weld
puts into a joint and whether that joint is strong enough and cool enough to avoid cracking.
`watchmaking` covers the mechanical engineering of a wound mainspring driving a gear train through
an escapement at a fixed beat rate. `printing` covers the press-production arithmetic between a
digital file and a printed, bound, bled, and colour-matched sheet. `packaging` covers the geometry
and mechanical strength of the box or container something ships in. `laundry` covers the water,
heat, and mechanical-energy budget of a wash-and-dry cycle and what that cycle does to the fabric
and the stain in it. None of the five turned out to be a different subject wearing its name — a
real possibility elsewhere in this corpus — and two sections below confirm that explicitly against
the source rather than the docstring alone.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("welding", "heat_input", [25.0, 200.0, 5.0])["result"]
# 1000.0 -- 25 V, 200 A, 5 mm/s travel speed: HI = V*I/speed (J/mm)

runtime.execute("watchmaking", "case_diameter_mm", [11.5])["result"]
# 25.9417 -- an 11.5-ligne movement (ETA 2824-2 scale) converted to mm, ligne = 2.2558 mm
```

## The modules

| Module | What it does |
| --- | --- |
| `welding` | Arc-welding joint and process physics: heat input in J/mm and kJ/mm, the IIW carbon-equivalent formula, a simplified cooling-rate model, weld dilution, electrode consumption, deposition-based travel speed, joint efficiency, fillet-weld throat and allowable shear, maximum interpass temperature, and a hydrogen-cracking risk index. |
| `watchmaking` | Mechanical-watch engineering: gear-train ratios, beats-per-hour and frequency conversions, mainspring torque and power reserve, balance-wheel period, escapement timing error in seconds/day, minimum jewel count, water-resistance ATM rating, case-diameter unit conversion, and crown winding turns. |
| `printing` | Press and publishing production math: DPI-to-LPI screening, pixel counts and raw uncompressed file size, bleed area, book spine width, CMYK ink coverage, paper basis-weight conversion, sheets per ream, cost per page, imposition sheet count, CIE76 colour difference, and apparent dot gain. |
| `packaging` | Box and container engineering: box and cylinder volume/surface area, material utilization, McKee corrugated-board compression strength, stacking load, a simplified cushion-curve G-factor, pallet-area efficiency, Arrhenius shelf-life kinetics, fill percentage, and dimensional (volumetric) weight. |
| `laundry` | Textile-care process physics and chemistry: water usage, soil-scaled detergent dosing, wash-water heating energy, spin-cycle centrifugal G-force, moisture retention and drying-time estimate, energy and cost per cycle, fabric wear-cycle life, stain-removal efficiency, CIE colour-fastness ΔE, and water-hardness dose compensation. |

## `welding`: heat input, carbon equivalent, and fillet sizing

Every worked number below is pinned in `tests/mojo/test_wave93.mojo` ("Tests for Wave 93 —
Welding, Apiculture, Color Science"), not the auto-generated smoke test.

```python
runtime.execute("welding", "heat_input", [25.0, 200.0, 5.0])["result"]
# 1000.0 J/mm -- HI = V*I/speed, travel_speed in mm/s

runtime.execute("welding", "preheat_carbon_equivalent",
                [0.15, 1.2, 0.5, 0.3, 0.05, 0.4, 0.2])["result"]
# 0.56 -- IIW formula: CE = C + Mn/6 + (Cr+Mo+V)/5 + (Ni+Cu)/15
#       = 0.15 + 0.2 + 0.17 + 0.04

runtime.execute("welding", "hydrogen_cracking_risk", [0.45, 5.0, 3.0])["result"]
# 10.0 -- risk index = CE*10 + hydrogen_ml*0.5 + restraint_level
```

`heat_input` and `heat_input_kj` compute the same physical quantity in different units and with
different travel-speed conventions: `heat_input` expects `travel_speed` in **mm/s** and returns
**J/mm**; `heat_input_kj` expects `travel_speed_mm_min` in **mm/min** and returns **kJ/mm**
(`V*I*60/(speed*1000)`). Both are pinned against each other's scale: `heat_input(25, 200, 5) =
1000.0` J/mm and `heat_input_kj(25, 200, 300) = 1.0` kJ/mm describe compatible weld conditions (5
mm/s = 300 mm/min) and 1000 J/mm = 1.0 kJ/mm, so the two functions agree once the unit conversion
is done by hand — the module does not convert between them itself.

`preheat_carbon_equivalent` implements the standard IIW (International Institute of Welding)
formula exactly, used to decide whether a steel needs preheat before welding to avoid hydrogen
cracking. Downstream, `interpass_temperature_max(ce)` turns that same CE into a simplified linear
cap (`350 - 200*CE`, so `interpass_temperature_max(0.45) = 260`°C) and `hydrogen_cracking_risk`
folds CE together with diffusible hydrogen content and joint restraint into a single risk index —
both are explicitly simplified heuristics in their docstrings, not standards-body formulas the way
the CE calculation itself is.

`throat_thickness_fillet(leg_size) = leg_size * 0.707` (the standard `1/√2` fillet-weld throat
approximation) and `allowable_shear_fillet(throat, length, allowable_stress) = throat * length *
allowable_stress` chain directly: a 10 mm leg gives a 7.07 mm throat
(`throat_thickness_fillet(10.0) = 7.07`), and that throat over a 100 mm weld length at 100 MPa
allowable stress carries `allowable_shear_fillet(7.07, 100.0, 100.0) = 70,700` N.

## `watchmaking`: confirmed — genuine gear-train and escapement physics

The hint for this batch asked to verify whether `watchmaking` really covers gear-train and
escapement physics rather than something else. Reading `mojo/engine/watchmaking.mojo` directly
confirms it does: every one of its twelve functions is a real mechanical-horology formula —
gear ratios, beats-per-hour, mainspring torque, balance-wheel period, escapement timing error,
jewel count, water-resistance rating, and case/crown geometry. Numbers below are pinned in
`tests/mojo/test_wave98.mojo` ("Wave 98 tests -- geomorphology, watchmaking, pest_control").

```python
runtime.execute("watchmaking", "gear_ratio", [10.0, 80.0])["result"]
# 8.0 -- GR = driven_teeth / driver_teeth

runtime.execute("watchmaking", "beats_per_hour", [4.0])["result"]
# 28800.0 -- a 4 Hz ("high-beat") movement: BPH = freq * 3600 * 2

runtime.execute("watchmaking", "balance_wheel_period", [1e-7, 1e-3])["result"]
# 0.0628318... s -- T = 2*pi*sqrt(inertia / spring_constant)
```

`beats_per_hour` and `frequency_from_bph` are exact inverses: `beats_per_hour(4.0) = 28800.0` and
`frequency_from_bph(28800.0) = 4.0` round-trip cleanly, and 28,800 bph is a real, common mechanical
movement rate (a 4 Hz balance). `escapement_error_spd(actual_bph, nominal_bph)` converts a beat-rate
deviation into a timing error in seconds per day — `escapement_error_spd(28810.0, 28800.0) = 30.0`
(a movement beating 10 bph fast runs 30 seconds/day fast), and the sign flips correctly for a slow
movement: `escapement_error_spd(28790.0, 28800.0) = -30.0`.

`case_diameter_mm(movement_diameter_ligne) = ligne * 2.2558` uses the real ligne-to-millimetre
conversion factor used across the Swiss watch industry for movement sizing —
`case_diameter_mm(12.0) = 27.0696` and `case_diameter_mm(11.5) = 25.9417`. `jewel_count_minimum`
(`gear_trains * 2 + 1`) and `water_resistance_atm` (`meters / 10 + 1`) are both explicitly labeled
"simplified" in their docstrings: real jewel counts and depth ratings depend on movement design
choices this single-formula heuristic does not model, but the approximations are the standard rule
of thumb for both (roughly two jewels per gear-train pivot plus the balance, and one atmosphere per
10 m of rated depth).

## `printing`: press production math, and a paper-weight conversion worth double-checking

Numbers below are pinned in `tests/mojo/test_wave82.mojo` ("Tests for Wave 82 — Printing, Fire
Safety, Procurement").

```python
runtime.execute("printing", "pixel_count", [8.5, 11.0, 300.0])["result"]
# 8415000.0 -- an 8.5x11in page scanned at 300 DPI: (8.5*300) * (11*300)

runtime.execute("printing", "bleed_area", [210.0, 297.0, 3.0])["result"]
# 65448.0 -- A4 (210x297mm) with a 3mm bleed on every edge: (210+6)*(297+6)

runtime.execute("printing", "color_delta_e", [50.0, 20.0, -10.0, 51.0, 22.0, -7.0])["result"]
# 3.7416573867739413 -- CIE76 delta-E = sqrt(1^2 + 2^2 + 3^2) = sqrt(14)
```

`spine_width(pages, paper_thickness_mm) = pages * thickness / 2` (halving because a page count is
twice the sheet count) gives a 200-page book on 0.1 mm stock a 10 mm spine
(`spine_width(200.0, 0.1) = 10.0`), and `imposition_pages(finished_pages, pages_per_sheet)` turns a
64-page finished job printed 16-up per sheet into 4 press sheets. `ink_coverage` is a plain sum of
the four CMYK channel percentages with no cap (`ink_coverage(100, 100, 100, 100) = 400.0`) — real
offset presses have a practical total-area-coverage ceiling around 240–320% before ink won't dry or
set properly, and this function reports the raw sum for the caller to compare against whatever
ceiling their process and substrate allow, rather than enforcing one itself.

{% hint style="warning" %}
**`paper_weight_gsm_to_lb`'s docstring says "bond basis," but the coefficient it uses matches
text-weight paper, and an extra `/10.0` in the body puts the result off the real scale by 10x
either way.** The function is `gsm * 0.67 / 10.0`. Checked against published gsm↔lb equivalency
tables: 90 gsm text stock is conventionally listed as 60 lb text (ratio `60/90 = 0.6667`, matching
the `0.67` coefficient almost exactly) — but 90 gsm on the **bond** basis the docstring names is
conventionally ~24 lb bond (ratio `24/90 = 0.267`, not `0.67`). Either way, the function's actual
output — `paper_weight_gsm_to_lb(90.0) = 6.03` — lands a further 10x below whichever real reference
point it's compared against (60 lb text or 24 lb bond), because of the trailing `/10.0`. The
pinned test (`paper_weight_gsm_to_lb(80.0) == 5.36`) confirms this is the function's actual,
committed behavior, not a typo introduced after the test was written — but a caller who wants a
number that matches a real paper mill's basis-weight chart, in either the bond or text system,
should not use this function's output directly.
{% endhint %}

## `packaging`: confirmed — box, container, and shipping engineering

The hint for this batch asked to verify whether `packaging` is genuinely box/material sizing.
It is: all twelve functions in `mojo/engine/packaging.mojo` are real corrugated-box and shipping
formulas, with no unrelated domain hiding behind the name. Numbers below are pinned in
`tests/mojo/test_wave74.mojo` ("Tests for Wave 74 — Geotechnical, Cosmology, Packaging").

```python
runtime.execute("packaging", "compression_strength_mckee", [6.0, 100.0, 0.4])["result"]
# 222.75083838226064 -- CS = 5.87 * ECT * sqrt(perimeter * thickness), the real McKee formula

runtime.execute("packaging", "dimensional_weight", [60.0, 40.0, 30.0, 5000.0])["result"]
# 14.4 kg -- L*W*H / dim_factor, the volumetric-weight formula carriers bill against
```

`compression_strength_mckee` implements the actual McKee box-compression-test formula (`5.87 * ECT
* sqrt(perimeter * caliper)`, the constant `5.87` itself is the standard McKee coefficient, not a
tuning choice this module made). `stacking_load(weight, layers) = weight * (layers - 1)` gives the
bottom box in a stack of 5, each weighing 20 kg, a load of 80 kg — the bottom box carries every
layer above it but not its own weight, so a single-layer "stack" of 1 correctly loads it with 0.
`cushion_curve_g` and `pallet_efficiency` are both pinned exactly against hand-worked arithmetic:
`cushion_curve_g(0.75, 0.05, 2.0) = 25.0` and `pallet_efficiency(0.12, 1.2, 8.0) = 80.0`
(8 boxes at 0.12 m² each over a 1.2 m² pallet footprint).

`shelf_life_arrhenius(a, ea, r, temperature)` is worth reading carefully by name: it returns the
Arrhenius **reaction-rate constant** `k = A * exp(-Ea/(R*T))`, not a shelf-life duration in days or
months. `shelf_life_arrhenius(1.0e10, 80000.0, 8.314, 300.0) = 1.1756e-4` is a rate constant; a
caller estimating actual shelf life (e.g. days until a quality attribute crosses a threshold) needs
to invert this rate against that threshold themselves — the function's real job, matching both its
docstring and its test, is computing the temperature-dependent rate that feeds a shelf-life
estimate, not the shelf life itself.

## `laundry`: confirmed — genuine textile-care physics and chemistry

The hint for this batch asked to verify whether `laundry` is genuinely textile-care physics and
chemistry, given past naming surprises elsewhere in this corpus. It is, without qualification:
`mojo/engine/laundry.mojo`'s docstring is "Laundry / Textile Care Science Library," and all twelve
functions match — water usage, detergent dosing, wash-water heating energy, spin-drum centrifugal
force, drying time, fabric wear life, stain removal, colour fastness, and water-hardness dose
compensation. Numbers below are pinned in `tests/mojo/test_wave92.mojo` ("Tests for Wave 92 —
Laundry, Volcanology, Biomechanics").

```python
runtime.execute("laundry", "spin_g_force", [1200.0, 0.25])["result"]
# 402.43 -- a 1200 RPM spin cycle, 0.25m drum radius: G = (2*pi*RPM/60)^2 * R / 9.81

runtime.execute("laundry", "water_hardness_compensation", [30.0, 200.0, 0.5])["result"]
# 33.0 -- 200 ppm hard water bumps a 30ml base detergent dose by 10%
```

`spin_g_force` converts drum RPM and radius into the actual centrifugal G-force a spin cycle
subjects laundry to — a real washing-machine spec (1200 RPM machines are a common mid-to-high-end
tier) computes to roughly 402 G here, consistent with published water-extraction G-force figures
for that RPM class. `fabric_wear_cycles(initial_strength, strength_per_wash, min_strength) =
(initial - min) / per_wash` gives fabric starting at strength 100, losing 0.5 per wash, down to a
minimum usable strength of 20, a service life of 160 washes before replacement. `detergent_dose_ml`
scales linearly with both load mass and a soil-level multiplier (`1.0` light, `1.5` normal, `2.0`
heavy, per its docstring), and `water_hardness_compensation` then adds a further linear correction
on top of whatever base dose that first call produced — the two are meant to compose, not to be
called as alternatives to each other.

## Verification

`mojo/tests/libs/test_welding.mojo`, `test_watchmaking.mojo`, `test_printing.mojo`,
`test_packaging.mojo`, and `test_laundry.mojo` are auto-generated coverage smoke tests (confirmed
by their own "auto-generated tests for `<module>`" docstrings): each calls every function once with
literal argument values and checks only that the result is finite, pinning no specific numeric
output. The real, hand-verified numeric suites for these five modules live instead in
`tests/mojo/test_wave74.mojo` (packaging), `test_wave82.mojo` (printing), `test_wave92.mojo`
(laundry), `test_wave93.mojo` (welding), and `test_wave98.mojo` (watchmaking) — every worked example
on this page is taken directly from one of those five files, and independently re-derived from the
formulas in the corresponding `mojo/engine/*.mojo` source (the McKee, IIW carbon-equivalent, and
Arrhenius formulas were additionally checked against their published real-world forms, not just
against this codebase's own test values).

**Next:** see [Process and organic materials science kernels](process-and-organic-materials-science-kernels.md)
for adjacent industrial-process physics, or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
