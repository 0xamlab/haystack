---
icon: compass-drafting
description: Classical point mechanics, beam/column structural analysis, Newtonian pipe-and-body fluid dynamics, non-Newtonian and viscoelastic rheology, and soil engineering split across its geotechnical and agronomic uses, across six independent scalar-formula modules.
---

# Continuum and structural mechanics kernels

Six modules for the hand-calculation formulas an engineer reaches for when a body, a beam, a
fluid, or a patch of ground has to carry a load or move under one: how a point mass accelerates,
falls, and collides (`physics`); how a beam or column bends, deflects, buckles, and vibrates under
that load (`structural`); how a Newtonian fluid moves through a pipe or around a body (`fluid`);
how a fluid or soft solid whose viscosity depends on shear rate or time behaves instead
(`rheology`); how soil itself bears a footing's load, settles, and consolidates (`soil_mechanics`);
and how that same soil behaves as a physical and hydrological medium for water and roots rather
than as a construction material (`soil_science`). Every function across all six takes and returns
plain `Float64` (two exceptions return `Bool`) — no structs, no shared status-code vocabulary, and
none of the six modules imports another or anything outside `std.math`.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# A pin-ended column, EI = 1000, L = 1: Pcr = pi^2 * EI / (k*L)^2
runtime.execute("structural", "euler_buckling_load", [1000.0, 1.0, 1.0])["result"]
# 9869.604401089358

# A 2 m strip footing, 1.5 m deep, in a c'=10 kPa, gamma=18 kN/m3, phi=30 deg soil
runtime.execute("soil_mechanics", "bearing_capacity_terzaghi",
                [10.0, 18.0, 1.5, 2.0, 0.5235987755982988])["result"]
# 643.4719587392588 kPa ultimate bearing capacity
```

## The modules

| Module | What it does |
| --- | --- |
| `physics` | Classical point mechanics: kinematics under constant acceleration, kinetic and gravitational potential energy, linear momentum, Newton's law of gravitation, projectile range/max-height/flight-time, work and power, and the post-collision velocity of a 1-D elastic collision. |
| `structural` | Beam and column structural analysis: bending and shear stress, a rectangle's moment of inertia and section modulus, cantilever and simply-supported deflection, Euler critical buckling load, slenderness ratio, axial stress, von Mises combined stress, safety factor, and a cantilever's first natural frequency. |
| `fluid` | Newtonian fluid dynamics: Reynolds number and its turbulent threshold, Bernoulli velocity, the laminar friction factor, Darcy-Weisbach pressure drop, flow rate and pipe velocity, hydraulic diameter for a rectangular duct, Mach number, quadratic drag force, buoyancy force, and Stokes drag on a sphere. |
| `rheology` | Flow and deformation of matter beyond the Newtonian case: shear stress, shear rate, and dynamic viscosity; power-law (shear-thinning/thickening) apparent viscosity; Bingham-plastic yield stress; a generalized Reynolds number for power-law fluids; viscoelastic creep compliance and stress-relaxation modulus; Arrhenius temperature-dependence of viscosity; and a thixotropy index. |
| `soil_mechanics` | Geotechnical engineering calculations for soil as a load-bearing construction material: Terzaghi ultimate bearing capacity (deriving its own Nc/Nq/Nγ factors from the friction angle), elastic settlement, Terzaghi 1-D degree of consolidation, void ratio and relative density, the Atterberg plasticity index, Mohr-Coulomb shear strength, the Rankine active earth-pressure coefficient, Skempton's compression index, and Hazen's hydraulic conductivity. |
| `soil_science` | Soil as a physical, hydrological, and chemical medium rather than a construction material: texture validation, bulk and particle density, total porosity, volumetric and gravimetric water content, field-capacity and wilting-point pedotransfer estimates, plant-available water, cation exchange capacity, soil organic carbon, and Horton's infiltration-rate decay. |

## Where these six do — and don't — overlap with what's already documented

Three of these six were flagged for a real overlap check against pages from earlier batches, and
the answer is different for each one.

**`soil_mechanics` and `geotechnical`** (batch 5, [Surface processes: landforms, soils, and
sediment](surface-processes-and-geomorphology-kernels.md)) share three function names —
`bearing_capacity_terzaghi`, `settlement_elastic`, `void_ratio` — and reading both real
`mojo/engine/*.mojo` files shows they are companions at different points in the same calculation,
not duplicates:

* `soil_mechanics.bearing_capacity_terzaghi(cohesion, unit_weight, depth, width, phi_rad)` derives
  its own Terzaghi bearing-capacity factors Nc, Nq, Nγ from `phi_rad` in the same call.
  `geotechnical.bearing_capacity_terzaghi(c, gamma, d, b, nc, nq, ngamma)` instead takes those three
  factors as arguments and only does the final weighted sum — it expects the caller already has
  them, typically from a published Terzaghi table. Feeding `soil_mechanics`'s own derived factors
  (`Nc = 19.5157`, `Nq = 12.2674`, `Nγ = 6.5052`, from `phi_rad = 0.5235987755982988`, i.e. 30°)
  into `geotechnical`'s version reproduces `soil_mechanics`'s answer exactly: both return
  `643.4719587392588` kPa for the footing above. One module derives the factors; the other only
  combines them.
* `soil_mechanics.settlement_elastic` bakes in a fixed influence factor `Iw = 0.82` for a square
  footing; `geotechnical.settlement_elastic` has no influence factor at all
  (`s = q·B·(1-ν²)/E`). For identical inputs (`pressure=150, width=2, modulus=20000, poisson=0.3`),
  `soil_mechanics` returns `0.011193` m and `geotechnical` returns `0.01365` m — and
  `0.01365 × 0.82 = 0.011193` exactly, confirming the two differ by precisely that one baked-in
  factor and nothing else.
* `void_ratio` is a real false cognate. `soil_mechanics.void_ratio(specific_gravity, water_content,
  saturation) = Gs·w/Sr` is a three-phase relationship computed from specific gravity, water
  content, and degree of saturation. `geotechnical.void_ratio(porosity) = n/(1-n)` computes the same
  named quantity from porosity alone. Both are legitimate textbook formulas for void ratio, but they
  take unrelated inputs and are not interchangeable — there's no conversion in either module from one
  set of inputs to the other.

**`soil_science` and `pedology`** (batch 5, same page) turn out to be genuinely disjoint, with no
shared function names at all. `soil_science` computes present-tense physical and hydraulic
properties an agronomist or hydrologist reads off a sample today: bulk density, porosity, water
content, field capacity, CEC, organic carbon, infiltration decay. `pedology` computes how a soil
profile got the way it is over geologic time: composite development indices, clay illuviation,
Munsell-colour rubification, element translocation, and an inverse soil-age estimate. Reading both
`mojo/engine/soil_science.mojo` and `mojo/engine/pedology.mojo` end to end confirms zero overlapping
formulas — the earlier batch's own framing ("soil formation and classification science" vs. the
`geotechnical` module's "soil and rock mechanics for construction") already drew this boundary
correctly, and `soil_science` sits in neither of those buckets: it's the agronomic/hydrologic
reading of the same physical material.

**`rheology`** was flagged as possibly already covered by batch 5's [Process and organic-materials
science kernels](process-and-organic-materials-science-kernels.md). It isn't. That page's own module
table lists eight modules (`brewing`, `fermentation`, `food_science`, `perfumery`, `paper_science`,
`wood_science`, `textile`, `combustion`) and never mentions `rheology`; grepping every file under
`gitbook/` for the literal string `rheology` turns up exactly one hit outside this page —
`runtime-library-catalog.md`, the machine-generated module/function-count table, which is not a
narrative page. So the earlier hint's "already-documented reference" was itself the open question it
flagged, and the real answer is that this page is `rheology`'s first narrative documentation.

**`fluid` and `rheology`, both on this page, are a genuine generalization pair.** `fluid.mojo`
assumes a Newtonian fluid throughout — every function that needs a viscosity takes it as a single
constant. `rheology.mojo` is what a fluid dynamics module needs once viscosity stops being constant:
`power_law_viscosity` for shear-thinning or shear-thickening fluids, `bingham_yield_stress` for
fluids that don't flow at all below a threshold stress. The two modules' Reynolds numbers make the
relationship precise: `fluid.reynolds_number(velocity, length, viscosity) = v·L/ν` is the classic
kinematic form (density folded into a kinematic viscosity ν).
`rheology.reynolds_number_non_newton(density, velocity, diameter, consistency_k, flow_index_n) =
ρ·v^(2-n)·D^n/K` generalizes it for a power-law fluid, and collapses back to the ordinary
dynamic-viscosity Reynolds number ρvD/μ exactly when `n = 1` (the consistency index `K` then plays
the role of the dynamic viscosity μ) — verified directly:
`reynolds_number_non_newton(1000.0, 2.0, 0.1, 1.0, 1.0) = 200.0`, matching ρvD/μ = 1000·2·0.1/1.

## Worked examples, traced against real tests where they exist

`physics`, `fluid`, `structural`, and `soil_science` each have a real, hand-verified numeric test
suite in `tests/mojo/` — `test_wave33.mojo`, `test_wave48.mojo`, `test_wave89.mojo`, and
`test_wave80.mojo` respectively — in addition to the auto-generated single-call smoke test every
module gets in `mojo/tests/libs/`. The examples below for those four modules are pulled directly
from those pinned wave tests.

**`physics`** — free fall from rest, `a = 10`, `t = 2`: `kinematic_distance(0.0, 10.0, 2.0) =
0 + 0.5·10·4 = 20.0` m. An equal-mass 1-D elastic collision swaps velocities:
`elastic_collision_v1(1.0, 1.0, 5.0, 0.0) = 0.0` — the moving mass stops and (by momentum
conservation, computed the same way for the second body) the stationary one leaves at `5.0`.

**`fluid`** — a pipe run: `flow_rate(2.0, 5.0) = 10.0` m³/s, and `darcy_weisbach(0.02, 100.0, 0.5,
2.0, 1000.0) = 0.02·(100/0.5)·(1000·4/2) = 8000.0` Pa pressure drop over that run.
`bernoulli_velocity(200000.0, 100000.0, 1000.0) = √(2·100000/1000) = √200 ≈ 14.142` m/s — and if
`p2` exceeded `p1` enough to make the term under the square root negative, the function clamps to
`0.0` rather than returning `NaN`.

**`structural`** — a cantilever, `EI = 9000`, `L = 3`, tip load `100`:
`deflection_cantilever_point(100.0, 3.0, 9000.0) = 100·27/(3·9000) = 0.1` m. Pure shear stress
state (`sx=sy=0`, `txy=50`): `combined_stress_von_mises(0.0, 0.0, 50.0) = √(3·50²) ≈ 86.6025` — the
familiar `√3` factor between shear and von Mises stress. Doubling the effective length factor `k`
from 1 to 2 quarters the Euler buckling load: `euler_buckling_load(1000.0, 1.0, 1.0) ≈ 9869.60` vs.
`euler_buckling_load(1000.0, 1.0, 2.0) ≈ 2467.40`, because `Pcr` is proportional to `1/(kL)²`.

**`soil_science`** — Horton's infiltration decay from `f0=100`, `fc=10`, `k=2` mm/hr: at `t=0`,
`infiltration_rate_horton(100.0, 10.0, 2.0, 0.0) = 100.0` (the initial rate, unattenuated); at
`t=1`, it has decayed to `10 + 90·e⁻² ≈ 22.18` mm/hr; by `t=100` it has settled to the steady-state
`fc = 10.0` mm/hr to within `1e-3`. `total_porosity(1.5, 2.65) = 1 - 1.5/2.65 ≈ 0.4340`, and a
fully-dense sample (`bulk_density_val == particle_density_val`) correctly reports `0.0` porosity —
there's no pore space left to report.

`soil_mechanics` and `rheology` have **only** the auto-generated smoke test in `mojo/tests/libs/`
(`test_soil_mechanics.mojo`, `test_rheology.mojo`), which calls every function once with literal
`0.5`-valued arguments and checks only that the result is finite — it pins no specific numeric
output. The examples below were hand-traced independently against the real formulas in
`mojo/engine/soil_mechanics.mojo` and `rheology.mojo`, reproducing the module's own arithmetic in
plain Python; every number can be regenerated the same way.

**`soil_mechanics`** — `phi_rad = 0.5235987755982988` (30°) makes
`lateral_earth_pressure_ka(phi_rad) = tan²(45° - 15°) = tan²(30°) = 1/3` exactly
(`0.3333333333333334`) — the textbook result that a 30° friction angle gives an active
earth-pressure coefficient of exactly one-third. `consolidation_degree` switches formulas at
`time_factor = 0.217`: below that, a parabolic early-time approximation
(`consolidation_degree(0.1) ≈ 0.3568`); at or above it, Terzaghi's exponential series truncated to
its first term (`consolidation_degree(0.5) ≈ 0.7640`).

**`rheology`** — a shear-thickening (dilatant) suspension, `K=0.1`, `n=2`, at `shear_rate=10`:
`power_law_viscosity(0.1, 10.0, 2.0) = 0.1·10¹ = 1.0` Pa·s of apparent viscosity — higher than its
own consistency index `K`, because `n > 1` means viscosity rises with shear rate. A Bingham plastic
under `50` Pa total stress, `2` Pa·s plastic viscosity, at `shear_rate=10`:
`bingham_yield_stress(50.0, 2.0, 10.0) = 50 - 2·10 = 30.0` Pa — the stress in excess of what
plastic flow alone accounts for. `creep_compliance` and `stress_relaxation_modulus` are the same
exponential shape run in opposite directions: at exactly one retardation time,
`creep_compliance(1.0, 2.0, 2.0) = 1·(1 - e⁻¹) ≈ 0.63212` (63.2% of final compliance reached, the
same universal fraction an RC circuit reaches after one time constant); at exactly one relaxation
time, `stress_relaxation_modulus(100.0, 5.0, 5.0) = 100·e⁻¹ ≈ 36.7879` (36.8% of the initial
modulus remains).

## Edge-case behavior differs sharply within this page

`physics`, `fluid` (`bernoulli_velocity`'s clamp aside), and `structural` are **bare arithmetic**:
none of their other functions guard against division by a caller-supplied zero. `power(work, 0.0)`,
`friction_factor_laminar(0.0)`, and `bending_stress(m, 0.0)` all propagate whatever `Float64`
division by zero produces (`inf` or `NaN`) rather than returning a sentinel — reading
`structural.mojo` end to end, there isn't a single `if` statement in the file. `soil_mechanics`,
`soil_science` (bar its own texture validator), and `rheology` take the opposite approach and guard
nearly every division: `rheology.shear_stress` returns `0.0` if `area <= 0.0`;
`dynamic_viscosity`, `shear_rate`, `power_law_viscosity`, and `reynolds_number_non_newton` all
return `0.0` on a non-positive rate, consistency index, or diameter; `soil_mechanics.settlement_elastic`
returns `0.0` if `modulus <= 0.0`, and `void_ratio` returns `0.0` if `saturation <= 0.0`. One
`rheology` guard returns something other than zero on purpose: `creep_compliance` with a
non-positive `retardation_time` returns `j0` itself, not `0.0` — physically, a retardation time of
zero means the material responds instantaneously, so the compliance jumps straight to its
instantaneous value `j0` rather than staying at zero. `soil_mechanics` also clamps rather than
merely guarding in two places: `relative_density` clips its result to `[0, 1]` even if
`void_ratio_e` falls outside `[e_min, e_max]`, and `liquid_limit_plasticity` and
`compression_index` both floor a formula that would otherwise go negative at `0.0`, since neither a
negative plasticity index nor a negative compression index is physically meaningful. `soil_science`
itself has no division guards in its own physical-property formulas (`bulk_density`,
`total_porosity`, and the water-content functions all divide unguarded); its only conditional logic
is the `±1.0` tolerance check inside `soil_texture_sand_silt_clay`.

## Verification

`mojo/tests/libs/test_physics.mojo`, `test_fluid.mojo`, `test_structural.mojo`,
`test_soil_mechanics.mojo`, `test_soil_science.mojo`, and `test_rheology.mojo` are all
auto-generated coverage smoke tests, calling every function once with fixed literal arguments and
checking only that the result is finite. Four of the six modules additionally have real,
hand-verified numeric suites — `tests/mojo/test_wave33.mojo` (physics), `test_wave48.mojo` (fluid),
`test_wave89.mojo` (structural), and `test_wave80.mojo` (soil_science) — which is where the pinned
values in the worked-examples section above come from. `soil_mechanics` and `rheology` have no such
wave-test coverage; their worked examples were independently hand-traced against
`mojo/engine/soil_mechanics.mojo` and `rheology.mojo`, and the overlap comparisons against
`geotechnical` were computed the same way against `mojo/engine/geotechnical.mojo`.

**Next:** [Surface processes: landforms, soils, and sediment](surface-processes-and-geomorphology-kernels.md)
for `geotechnical` and `pedology`, or the [Runtime library catalog](runtime-library-catalog.md) for
every module and function.
