---
icon: plane
description: Orbital and rocket mechanics plus atmospheric aerodynamics (aerospace), aircraft-specific performance (aviation), UAV power/range/imaging (drones), self-driving-car safety physics (autonomous_vehicles), and general-purpose robot kinematics and control (robotics).
---

# Aerospace and autonomous systems kernels

Five modules for the physics underneath things that fly or drive themselves: how much lift and
drag a wing generates, how much delta-v a rocket burn buys, how far behind the car in front of you
is safe to follow, how long a quadcopter's battery keeps it airborne, and where a robot arm's
end-effector ends up for a given pair of joint angles. All ten to twelve functions per module take
and return plain `Float64` scalars — no structs, no shared status-code vocabulary — so each one is
a single, checkable formula, in the same style as the [mixture-of-experts and routing
kernels](mixture-of-experts-and-routing-kernels.md).

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Earth's GM and a 400 km-altitude LEO radius (Earth radius + altitude)
mu, r = 3.986e14, 6.771e6

v_orbit = runtime.execute("aerospace", "orbital_velocity", [mu, r])["result"]
v_escape = runtime.execute("aerospace", "escape_velocity", [mu, r])["result"]

v_orbit, v_escape, v_escape / v_orbit
# (7909.788019132537, 11186.129492153452, 1.4142135623730951)
# escape velocity is always exactly sqrt(2) times circular orbital velocity
# at the same radius -- true for any (mu, r), not just this one
```

## The modules

| Module | What it does |
| --- | --- |
| `aerospace` | Aerodynamic forces from a precomputed dynamic pressure, propulsion (specific impulse, the Tsiolkovsky rocket equation), and orbital mechanics (circular orbital velocity, escape velocity, total Hohmann-transfer delta-v). |
| `autonomous_vehicles` | Road-vehicle safety and perception physics: safe following distance, time-to-collision, grade-aware braking distance, lane-change and perception-latency distances, sensor-range and V2X-range requirements, GPS localization error, and two fixed comfort/emergency deceleration constants. |
| `aviation` | Aircraft performance built directly from raw air density, velocity, wing area, and coefficients: lift, drag, L/D, thrust required for level flight, the Breguet range and endurance equations, indicated/true airspeed conversion, an air-specific Mach number, and rate of climb. |
| `drones` | UAV-specific power, endurance, and imaging math: thrust-to-weight ratio, rotor disk loading and induced hover power, flight time and range from battery capacity, payload capacity, propeller tip speed and advance ratio, battery energy density, radio line-of-sight range, and ground sampling distance for aerial photography. |
| `robotics` | General kinematics and control building blocks: forward/inverse kinematics and one Jacobian element for a 2-DOF planar arm, a manipulability index, a PID controller output, dead-reckoning position update, wheel odometry, and differential-drive forward/inverse velocity kinematics. |

## `aerospace` vs. `aviation`: a real overlap, not a naming accident

The hint that prompted this page asked whether `aerospace` is really scoped to orbital/rocket
mechanics as its name suggests. Reading `mojo/engine/aerospace.mojo`'s own header answers that
directly — its docstring says it provides "aerodynamics, propulsion, orbital mechanics, and flight
performance calculations," and seven of its twelve functions
(`dynamic_pressure`, `lift_force`, `drag_force`, `lift_to_drag_ratio`, `thrust_required`,
`mach_number`, `speed_of_sound`) are atmospheric-flight formulas, the same subject `aviation`
covers. Only the remaining five (`specific_impulse`, `tsiolkovsky_delta_v`, `orbital_velocity`,
`escape_velocity`, `hohmann_delta_v`) are the orbital/rocket-mechanics functions the module's name
implies.

That overlap is real but not a duplicate — the two modules take different inputs for the same
physics:

* **`aerospace` expects a precomputed dynamic pressure; `aviation` computes it internally.**
  `aerospace.lift_force(cl, q, wing_area)` and `aerospace.drag_force(cd, q, wing_area)` take `q`
  as an argument, produced by the module's own `dynamic_pressure(density, velocity) = 0.5·ρ·v²`.
  `aviation.lift_force(air_density, velocity, wing_area, cl)` and `aviation.drag_force(...)` take
  raw `ρ` and `v` and compute `0.5·ρ·v²` themselves. Same formula, different call shape — you
  cannot pass one module's arguments to the other's function of the same name.
* **`aerospace.mach_number` is medium-agnostic; `aviation.mach_number` is air-only.**
  `aerospace.mach_number(velocity, speed_of_sound_val)` divides by a caller-supplied speed of
  sound, meant to be paired with `aerospace.speed_of_sound(gamma, gas_constant, temperature)` — so
  it works for any gas, not just Earth's atmosphere. `aviation.mach_number(velocity,
  temperature_k)` hardcodes air's `γ = 1.4` and `R = 287.058 J/(kg·K)` inside the function and
  takes temperature directly; it only ever computes Mach number in air.
* **`thrust_required` is the same physical relation with a different zero-guard.** Both compute
  `T = W/(L/D) = W·Cd/Cl` for level flight, but `aerospace.thrust_required(weight, ld_ratio)`
  returns `0.0` when `ld_ratio == 0.0`, while `aviation.thrust_required(weight, cl, cd)` returns
  the full `weight` (not `0.0`) when `cl <= 0.0` — treating "no lift" as "thrust must counter the
  entire weight" rather than as an unresolvable division.

Verified independently in Python and against the calling convention:

```python
runtime.execute("aerospace", "thrust_required", [100000.0, 50.0])["result"]
# 2000.0
```

```python
runtime.execute("aviation", "thrust_required", [100000.0, 1.0, 0.02])["result"]
# 2000.0 -- cl/cd = 1.0/0.02 = 50, the same L/D ratio, same answer, different guard on cl<=0
```

There is no third module reconciling the two — a caller who has raw `ρ`, `v` and wants `aerospace`'s
orbital-adjacent formulas has to compute `q = dynamic_pressure(density, velocity)` first, exactly
as `aviation`'s functions do it internally.

## Orbital and rocket mechanics, checked against real orbital parameters

`mojo/tests/libs/test_wave64.mojo` pins `aerospace`'s orbital functions against real values — Earth's
gravitational parameter `μ = 3.986 × 10¹⁴ m³/s²`, a LEO radius of `6.771 × 10⁶ m` (roughly 400 km
altitude), and a GEO radius of `42.164 × 10⁶ m`:

```python
runtime.execute("aerospace", "hohmann_delta_v", [3.986e14, 6.771e6, 42.164e6])["result"]
# 3856.6867363736833 -- between the test's asserted bounds of 3000 and 4500 m/s,
# consistent with the ~3.9 km/s a real LEO-to-GEO transfer costs
```

`tsiolkovsky_delta_v` is the rocket equation, `ΔV = Isp·g₀·ln(m₀/m_f)`, using the standard gravity
constant `g₀ = 9.80665 m/s²` baked into the module (`comptime G0`, not a parameter):

```python
runtime.execute("aerospace", "tsiolkovsky_delta_v", [300.0, 10000.0, 3000.0])["result"]
# 3542.0819704628825 -- Isp=300s (a decent chemical rocket), burning from 10 t to 3 t
```

Both guard clauses return `0.0` rather than propagating a `NaN` or `-inf`: `orbital_velocity` and
`escape_velocity` return `0.0` for `radius <= 0.0`, `hohmann_delta_v` returns `0.0` if either radius
is non-positive, and `tsiolkovsky_delta_v` returns `0.0` if either mass is non-positive — none of
these raise, so a caller passing a bad radius or mass gets a silent `0.0` instead of an exception.

## `aviation`'s Breguet range and endurance are the same formula, verified

Reading `range_breguet` and `endurance_breguet` in `mojo/engine/aviation.mojo` side by side: both
take the identical four arguments (`ld_ratio, sfc, weight_initial, weight_final`), both apply the
identical guard (`sfc <= 0.0 or weight_final <= 0.0 or weight_initial <= weight_final` → `0.0`),
and both return the identical expression, `(ld_ratio / sfc) * log(weight_initial / weight_final)`.
There is no `mojo/tests/libs/test_aviation.mojo` pinned numeric case that would have caught this —
that file is the auto-generated coverage smoke test (see Verification below) — so this was
independently hand-computed in this session:

```python
runtime.execute("aviation", "range_breguet", [10.0, 0.5, 1000.0, 800.0])["result"]
# 4.462871026284195

runtime.execute("aviation", "endurance_breguet", [10.0, 0.5, 1000.0, 800.0])["result"]
# 4.462871026284195 -- byte-for-byte the same number
```

The real Breguet range equation is `R = (V/c)·(L/D)·ln(Wi/Wf)` and endurance is `E = (1/c)·(L/D)·ln(Wi/Wf)`
— range differs from endurance by a factor of true airspeed `V`. `range_breguet`'s own docstring
acknowledges this with "Note: v is embedded in sfc units," meaning the function expects the caller
to have already folded `V` into whatever `sfc` value it's given. But since neither function does
anything different with that `sfc` argument, the distinction between "range" (meters) and
"endurance" (seconds) exists entirely in which of two differently-scaled `sfc` values the caller
chooses to pass in — the kernel itself computes the same number under both names.

## Drones: hover power and line-of-sight range, hand-verified

`mojo/tests/libs/test_wave91.mojo` pins `hover_power`'s induced-power formula, `P = W^1.5 /
sqrt(2·ρ·A)`, against a small quadcopter-scale case:

```python
runtime.execute("drones", "hover_power", [10.0, 0.5, 1.225])["result"]
# 28.57142857142857 -- 10 N weight, 0.5 m² total rotor disk area, sea-level air density
```

The same test file pins `communication_range_los`'s line-of-sight formula, `R = sqrt(2·Re·h + h²)`,
using Earth's mean radius:

```python
runtime.execute("drones", "communication_range_los", [100.0, 6371000.0])["result"]
# 35696.07821596092 -- radio/visual line-of-sight at 100 m altitude, roughly 35.7 km
```

`gsd_from_altitude` (ground sampling distance, the real-world size a pixel covers in an aerial
photo) is also pinned: `gsd_from_altitude(8.8, 13.2, 4000.0, 100.0) = 37.5` cm/px for an 8.8 mm
focal length, 13.2 mm sensor width, 4000 px image width, at 100 m altitude — a realistic
mapping-drone camera setup.

## Autonomous vehicles: following distance and time-to-collision, hand-verified

`mojo/tests/libs/test_wave80.mojo` pins the core safety-distance formulas:

```python
runtime.execute("autonomous_vehicles", "safe_following_distance", [30.0, 1.5, 5.0])["result"]
# 135.0 -- 30 m/s (108 km/h), 1.5 s reaction time, 5 m/s² deceleration:
# 45 m of reaction distance + 90 m of braking distance

runtime.execute("autonomous_vehicles", "time_to_collision", [50.0, 10.0])["result"]
# 5.0 -- 50 m gap closing at 10 m/s relative speed
```

`time_to_collision` returns a sentinel `-1.0` (not `0.0`, and not an exception) whenever
`relative_speed <= 0.0` — the gap isn't closing, so "time to collision" isn't a meaningful positive
number, and the pinned test explicitly checks both a stationary (`0.0`) and a diverging (`-5.0`)
relative speed produce that same `-1.0`. `comfort_deceleration()` and `emergency_deceleration()`
are the two zero-argument functions in this family — matching their empty `params: []` entry in the
runtime contract — returning fixed constants (`3.0` and `8.0 m/s²`) rather than computing anything
from an input.

`braking_distance(speed, friction, grade)` has no guard against `friction + grade` being zero or
negative — a steep-enough downhill `grade` can drive the denominator through zero, at which point
the function returns `inf` or a negative distance rather than a bounded error. That reflects a
genuinely unsafe physical scenario (a vehicle that cannot brake to a stop on that grade with that
friction coefficient), so an unbounded result is at least the right kind of answer, but it is not
clamped or flagged the way `time_to_collision`'s `-1.0` sentinel is.

## Robotics: a forward/inverse round-trip, and what the module leaves for the caller

`forward_kinematics_2dof` and `forward_kinematics_2dof_y` give the end-effector position of a
2-link planar arm; `inverse_kinematics_2dof_theta2` recovers the elbow angle from a target
position, the same self-checking shape used elsewhere in this corpus (see the RoPE round-trip in
[Attention kernels](attention-kernels.md)):

```python
l1, l2, theta1, theta2 = 1.3, 0.9, 0.6, 1.1

x = runtime.execute("robotics", "forward_kinematics_2dof", [l1, l2, theta1, theta2])["result"]
y = runtime.execute("robotics", "forward_kinematics_2dof_y", [l1, l2, theta1, theta2])["result"]
# x=0.9569762545166096, y=1.6265335448207678

theta2_back = runtime.execute("robotics", "inverse_kinematics_2dof_theta2", [l1, l2, x, y])["result"]
# 1.0999999999999999 -- theta2 recovered to 15 significant figures
```

{% hint style="info" %}
**The round trip only recovers `|theta2|`.** `inverse_kinematics_2dof_theta2` computes
`cos(θ2) = (x²+y²-l1²-l2²)/(2·l1·l2)`, clamps it to `[-1, 1]` for numerical safety, and returns
`acos` of that — and `acos`'s range is `[0, π]`, so a genuinely negative `theta2` (the arm's elbow
bent the other way) comes back with its sign stripped. The module also has no companion function to
solve for `theta1`, and `manipulability_index` takes an already-computed `det_jacobian` as its only
argument rather than computing a determinant itself — the module supplies `jacobian_2dof_j11`, one
of the four elements of the 2×2 Jacobian, so a caller wanting the manipulability index has to derive
the other three elements and their determinant independently before calling it. `robotics` is a set
of individual formulas for a 2-DOF arm and a differential-drive base, not a complete
inverse-kinematics or Jacobian solver.
{% endhint %}

## Verification

`mojo/tests/libs/test_{aerospace,autonomous_vehicles,aviation,drones,robotics}.mojo` are the
auto-generated coverage smoke tests common across this corpus — each calls every function once with
literal `0.5` arguments and checks only that the result is finite. Four of the five modules also
have real, hand-verified pinned numeric suites sitting in the `tests/mojo/test_wave*.mojo` files:
`aerospace` in `test_wave64.mojo`, `autonomous_vehicles` in `test_wave80.mojo`, `drones` in
`test_wave91.mojo`, and `robotics` in `test_wave66.mojo` — all of the orbital-mechanics, hover-power,
following-distance, and kinematics numbers above are pinned there. `aviation` has no such wave file;
grepping `tests/` for `from aviation import` turns up nothing beyond its own smoke test, so the
Breguet-formula finding and the `thrust_required` cross-check above were independently computed in
this session (Python, no library, matching the real formulas read directly from
`mojo/engine/aviation.mojo` and `mojo/engine/aerospace.mojo`) rather than sourced from a pinned
test.

**Next:** see [Mixture-of-experts and routing kernels](mixture-of-experts-and-routing-kernels.md)
for another family of plain-`Float64`, no-status-code modules, or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
