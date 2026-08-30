---
icon: globe
description: Spherical-Earth navigation math, textbook DC/AC circuit-theory formulas, and the biophysics of neuron membranes and action potentials, across three unrelated small Float64 kernel modules.
---

# Earth, electrical, and neurophysics kernels

Three small, unrelated modules that share nothing but scale: sphere-and-angle navigation
(`earth`), the equations from an introductory circuits course (`electrical`), and the biophysics
that turns an ion-concentration gradient into a nerve impulse (`neurophysics`). Every function
across all three is a pure `Float64 -> Float64` (or `Float64 -> List[Float64]`) formula — no
struct, no shared state, no Python. Two of the three overlap with modules documented elsewhere in
this corpus in ways that matter to know before calling either side: `earth` duplicates part of
`geodesy`'s spherical-navigation math under a different set of names and, in one case, a different
argument order, and `electrical`'s AC power-factor formula reappears — independently implemented,
different module, different function name — in `power_systems`.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Great-circle distance London -> Paris (the exact pair pinned in tests/mojo/test_wave35.mojo)
runtime.execute("earth", "haversine", [51.5074, -0.1278, 48.8566, 2.3522])["result"]
# 343.55606034104164 km — the test asserts this within 5 km of 344

# Nernst reversal potential for K+ (out=5 mM, in=140 mM, body temperature 310.15 K)
runtime.execute("neurophysics", "nernst_potential", [1.0, 5.0, 140.0, 310.15])["result"]
# -89.05404533864952 mV — close to the textbook E_K of about -90 mV
```

## The modules

| Module | What it does |
| --- | --- |
| `earth` | Spherical-Earth navigation: great-circle distance (haversine), initial bearing, geographic midpoint, a destination point from a start, bearing and distance, a lat/lon bounding box around a point, cross-track distance from a great-circle path, coordinate validation, degree/radian conversion, and the underlying unit-sphere haversine angle |
| `electrical` | Textbook circuit theory: Ohm's law in all three forms, DC power, series and parallel resistance, RC time constant and charging-voltage curve, RLC resonant frequency, impedance magnitude, power factor, capacitive and inductive reactance, and a two-resistor voltage divider |
| `neurophysics` | Biophysics of neurons and neural signals: Nernst and Goldman-Hodgkin-Katz reversal/resting potentials, membrane time constant, dendritic cable length constant, the current needed to reach action-potential threshold, a refractory-period firing-rate ceiling, synaptic current, leaky integrate-and-fire sub-threshold voltage, 1/f^β EEG spectral power, and a myelinated-axon conduction-velocity estimate |

## `earth` reimplements part of `geodesy` — same formulas, different names, one reordered argument list

`earth.mojo`'s docstring bills it as a replacement for the Python `geopy` package. The
already-documented `geodesy` module (see
[Solid-Earth geophysics kernels](solid-earth-geophysics-kernels.md)) covers overlapping ground, and
reading both `.mojo` files side by side shows the overlap is real, not superficial:

- **`earth.midpoint(lat1, lon1, lat2, lon2)` and `geodesy.midpoint(lat1, lon1, lat2, lon2)` are the
  same algorithm, statement for statement** — only the local variable names differ (`phi1`/`p1`,
  `bx`/`bx`, and so on). Same for `earth.destination_point(lat, lon, bearing_deg, distance_km)` and
  `geodesy.destination_point` — identical formula, identical signature.
- **`earth.haversine` and `geodesy.haversine_distance` compute the same great-circle formula**
  (same `EARTH_RADIUS_KM = 6371.0`, same clamp of the `asin` argument to `1.0`) under different
  names; likewise `earth.bearing` and `geodesy.initial_bearing`.
- **`cross_track_distance` exists in both modules with the same six-`Float64` arity, but the two
  argument orders put the off-path point in a different slot.** `earth.cross_track_distance(lat1,
  lon1, lat2, lon2, lat3, lon3)` takes the path endpoints first and the off-path point last;
  `geodesy.cross_track_distance(lat, lon, start_lat, start_lon, end_lat, end_lon)` takes the
  off-path point first and the path endpoints after. Porting a call from one module to the other by
  position, rather than checking the parameter names, silently swaps which point is "on the path"
  and which is being measured against it:

```python
# earth: path is (0,0)->(0,90), off-path point is (10,45)
runtime.execute("earth", "cross_track_distance", [0.0, 0.0, 0.0, 90.0, 10.0, 45.0])["result"]
# 1111.9492664455872 km

# geodesy: same six numbers reinterpreted with the off-path point FIRST — a different query
runtime.execute("geodesy", "cross_track_distance", [0.0, 0.0, 0.0, 90.0, 10.0, 45.0])["result"]
# asks "how far off the (0,90)->(10,45) path is the point (0,0)?" — not the same question
```

What `earth` has that `geodesy` doesn't: public `deg_to_rad`/`rad_to_deg` conversions,
`is_valid_coordinate` range checking, the underlying `distance_on_unit_sphere` angle (in radians,
before the `EARTH_RADIUS_KM` multiply), and `bounding_box`. What `geodesy` has that `earth` doesn't:
`vincenty_distance` (ellipsoidal, more accurate than haversine), `rhumb_distance` (constant-bearing
line), `along_track_distance`, and `geodetic_to_ecef`/`ecef_to_geodetic` coordinate conversion. In
practice `earth` is the simpler spherical-approximation toolkit; `geodesy` is the more complete one
that also knows about the WGS84 ellipsoid — but for the functions both modules do implement, they
agree to floating-point precision, since they're computing the same trigonometry.

## `electrical`'s power factor has a twin in `power_systems`, and a cousin of its Nernst equation lives in `corrosion`

`electrical.power_factor(real_power, apparent_power)` computes `PF = P/S` with no guard. The
already-documented `power_systems` module (in
[Industrial fluid power and energy systems kernels](industrial-fluid-power-and-energy-systems-kernels.md))
has `power_factor_from_pq(p, s)` — the identical formula, same argument order, but it guards
`s == 0.0` and returns `0.0` instead of `inf`. Different module, different name, same math, opposite
guard posture. `electrical` otherwise stays in circuit-theory territory that the other
already-documented electricity modules don't touch: `electrochemistry` and `corrosion` are about
redox reactions and batteries, `electrostatics` is static-charge field theory, `semiconductors` is
solid-state device physics, and none of the four has an Ohm's-law, RC-transient, or RLC-resonance
function.

Separately, `neurophysics.nernst_potential(z, conc_outside, conc_inside, temperature)` is the third
Nernst-equation implementation this corpus documents (after `corrosion.nernst_potential` and
`electrochemistry.nernst_cell_potential`, covered in
[Corrosion and electrochemical materials kernels](corrosion-and-electrochemical-materials-kernels.md)).
It's a real, independent implementation — not a duplicate — of the same underlying physics applied
to a different system: the corrosion/electrochemistry versions compute a redox half-cell potential
relative to a standard potential `E0` (`E = E0 - (RT/nF)*ln(Q)`, in volts), while the neurophysics
version computes a single-ion membrane reversal potential with no `E0` term and the opposite sign
convention on the log (`E = (RT/zF)*ln([out]/[in])`, in millivolts because it multiplies by `1000`
at the end). Same equation family, three separate call sites, none sharing code.

## `neurophysics` is membrane biophysics, not CNS pharmacology

The already-documented `neuropharmacology` module (in
[Pharmacology and toxicology kernels](pharmacology-and-toxicology-kernels.md)) has a
"drug-modulated neuronal firing rate" function and talks about synaptic neurotransmitter levels,
which sounds adjacent to `neurophysics`'s `firing_rate_simple` and `synaptic_current` — but reading
both source files shows no function overlap. `neuropharmacology` models how a drug's receptor
occupancy shifts a firing rate or a brain-exposure ratio; `neurophysics` models the underlying
electrical machinery of the neuron itself — ion-channel reversal potentials, membrane and cable time
constants, and the leaky integrate-and-fire voltage equation — with no drug, dose, or receptor
anywhere in the file. The two modules are complementary layers of the same subject, not a
duplication.

## Worked examples

`earth` and `electrical` both have real, pinned numeric assertions in `tests/mojo/test_wave35.mojo`
and `tests/mojo/test_wave60.mojo` respectively (not the auto-generated `0.5`-fixture smoke tests —
see [Verification](#verification)). The values below are drawn from those pinned assertions and
independently recomputed in plain Python before being written down:

```python
# earth — pinned in test_wave35.mojo
runtime.execute("earth", "haversine", [0.0, 0.0, 0.0, 90.0])["result"]
# 10007.543398010284 km — a quarter of Earth's circumference, test tolerance ±10 km of 10007.5
runtime.execute("earth", "haversine", [90.0, 0.0, -90.0, 0.0])["result"]
# 20015.086796020572 km — pole to pole, half the circumference
runtime.execute("earth", "midpoint", [0.0, 0.0, 0.0, 90.0])["result"]
# [0.0, 45.0] — equator midpoint between (0,0) and (0,90)

# electrical — pinned in test_wave60.mojo
runtime.execute("electrical", "rc_voltage", [10.0, 1000.0, 0.001, 1.0])["result"]
# 6.321205588285577 — at t == tau (1000 ohm * 0.001 F), ~63.2% of V0 as expected
runtime.execute("electrical", "rlc_resonance", [0.001, 0.000001])["result"]
# 5032.921210448703 Hz — a 1 mH, 1 uF tank circuit's resonant frequency
runtime.execute("electrical", "voltage_divider", [9.0, 1000.0, 2000.0])["result"]
# 6.0 — a 1k/2k divider carries 2/3 of the input to the output
```

`neurophysics` has no pinned wave test (see [Verification](#verification)), so these are hand-worked
from the formulas in `mojo/engine/neurophysics.mojo` and cross-checked in plain Python:

```python
# Goldman-Hodgkin-Katz resting potential with real physiological permeability ratios
# Pk:Pna:Pcl = 1:0.04:0.45, K_out=5, Na_out=145, Cl_in=10, K_in=140, Na_in=15, Cl_out=110 (mM)
runtime.execute("neurophysics", "goldman_equation",
                [1.0, 0.04, 0.45, 5.0, 145.0, 10.0, 140.0, 15.0, 110.0])["result"]
# -67.33957885620973 mV — close to the textbook resting potential of about -70 mV

# Leaky integrate-and-fire: -70 mV rest, 0.2 nA injected, 100 MOhm input R, 20 ms tau, 10 ms elapsed
runtime.execute("neurophysics", "integrate_and_fire_voltage", [-70.0, 0.2, 100.0, 20.0, 10.0])["result"]
# -62.13061319425267 mV — has climbed 62% of the way to its steady-state depolarization at t = tau/2

# Membrane time constant: Rm = 10,000 ohm*cm^2, Cm = 1 uF/cm^2 (both textbook-typical values)
runtime.execute("neurophysics", "membrane_time_constant", [10000.0, 1.0])["result"]
# 10.0 ms — a realistic passive-membrane time constant
```

**The `conduction_velocity` label is worth a second look.** Its docstring calls the `5.5 *
sqrt(axon_diameter_um)` formula a "myelinated axon conduction velocity estimate," but a `sqrt(d)`
functional form is the classical scaling law for *unmyelinated* fibers (the square-root relationship
Hodgkin and Huxley's squid-axon work established); myelinated fibers are usually modeled with an
approximately *linear* velocity-vs-diameter relationship instead (Hursh's rule, roughly `6 x
diameter_um` m/s). At a 10 μm diameter this module returns `5.5 * sqrt(10.0)` ≈ 17.4 m/s, while
Hursh's rule for the same diameter gives roughly 60 m/s — a real discrepancy between the label and
the commonly cited myelinated-fiber number, not a crash or a guard-clause bug, but worth knowing if
this function's output is compared against a physiology reference table.

## Guarantees and refusal behavior

The three modules take three different postures toward bad input:

- **`earth` only guards two of its ten functions, and both guards are numerical-domain clamps, not
  physical-input checks.** `distance_on_unit_sphere` (and therefore `haversine`, which calls it)
  clamps its `asin` argument to `1.0` if floating-point error pushes it slightly above that: without
  the clamp, an antipodal or near-antipodal pair could hand `asin` an out-of-domain value and return
  `nan`. `bounding_box` treats a point within `1e-10` of true north or south pole (`cos(phi) <=
  1e-10`) as needing a full 180-degree longitude half-band, since a normal cos-scaled longitude
  delta blows up near the pole. Every other function — `bearing`, `midpoint`, `destination_point`,
  `cross_track_distance`, `deg_to_rad`, `rad_to_deg` — runs the bare trigonometric formula with no
  check on its inputs; `is_valid_coordinate` exists to validate a `(lat, lon)` pair, but nothing in
  the module calls it automatically, so an out-of-range latitude passed straight to `haversine` or
  `bearing` is not intercepted.
- **`electrical` guards exactly one function.** `parallel_resistance` checks whether the summed
  reciprocal is `0.0` and returns `0.0` rather than dividing by it — though a single `0.0` resistor
  in the list already produces the physically correct answer by coincidence (`1.0 / 0.0` is `inf`,
  and `1.0 / inf` is `0.0`, i.e. a short circuit shorts the parallel combination). Every other
  function — both division forms of Ohm's law, `power_factor`, `capacitive_reactance`,
  `rc_voltage`, `rlc_resonance`, and `voltage_divider` — divides with no non-positive check, so a
  zero resistance, capacitance, frequency, or apparent power reaches the caller as `inf` or `nan`
  with no interception.
- **`neurophysics` takes the opposite posture: nine of its ten functions guard a non-physical input**
  and return a defined fallback (`0.0`, or the unchanged resting potential for
  `integrate_and_fire_voltage`) rather than propagating a non-finite result — a non-positive ion
  concentration or valence in `nernst_potential`, a non-positive permeability-weighted sum in
  `goldman_equation`, a negative resistance or capacitance in `membrane_time_constant`, a
  non-positive internal resistance in `cable_length_constant`, a non-positive input resistance in
  `action_potential_threshold`, a non-positive refractory-plus-integration time in
  `firing_rate_simple`, a non-positive time constant in `integrate_and_fire_voltage`, a non-positive
  frequency in `eeg_spectral_power`, and a non-positive diameter in `conduction_velocity`. Only
  `synaptic_current` is unguarded, and it needs no guard: it's a bare multiply-and-subtract with no
  division or logarithm to protect.

None of the nine functions in this family take or index into a `List` other than `earth`'s own
`midpoint`/`destination_point`/`bounding_box` (which only ever *build* a fixed-length two-or-four
element result) and `electrical`'s `series_resistance`/`parallel_resistance` (which iterate a
caller-supplied list but never index past its own length) — so unlike the tensor and ML kernel
families elsewhere in this catalog, there is no out-of-bounds abort risk anywhere in this page's
three modules.

## Verification

`mojo/tests/libs/test_earth.mojo`, `test_electrical.mojo`, and `test_neurophysics.mojo` are all
auto-generated coverage smoke tests: each calls every function once on a shared, arbitrary
`0.5`-valued fixture and checks only that the result is finite (or, for the two functions returning
`List[Float64]`, that the list exists) — none of the three pins a specific numeric output.

`earth` and `electrical` are additionally covered by real, hand-verified numeric assertions:
`tests/mojo/test_wave35.mojo`'s `test_earth()` (24 assertions — haversine at zero, quarter-Earth,
pole-to-pole, and a real London-Paris pair; bearing due east and due north; midpoint; coordinate
validation; degree/radian round-trips; a bounding box; destination point; and both an on-path and an
off-path cross-track-distance case) and `tests/mojo/test_wave60.mojo`'s `test_electrical()` (20
assertions — every Ohm's-law form, series and parallel resistance, the RC curve at `t=0`, `t>>tau`,
and `t=tau`, RLC resonance, the 3-4-5 impedance triangle, power factor, and the fact that capacitive
and inductive reactance are equal at the resonant frequency they're both derived from). `neurophysics`
has no equivalent pinned wave test — every neurophysics number in this page was instead hand-derived
from the formula in `mojo/engine/neurophysics.mojo` and cross-checked with an independent plain-Python
calculation, with the Nernst and Goldman examples additionally chosen to land close to their
well-known textbook reference values (~-90 mV for E_K, ~-70 mV resting potential) as a further check
that the formula and constants are wired correctly.

**Next:** see [Solid-Earth geophysics kernels](solid-earth-geophysics-kernels.md) for `geodesy`'s
more complete ellipsoidal navigation math, or [Runtime library catalog](runtime-library-catalog.md)
for every module and function in the full contract.
