---
icon: bolt
description: Corrosion rate and cathodic protection, electrochemical cell and battery equations, classical electrostatics and magnetism, metallurgical strengthening/hardenability, and semiconductor device physics across six independent Float64 kernel modules.
---

# Corrosion and electrochemical materials kernels

Six small, independent modules for the electrical and chemical behavior of materials: how fast a
metal corrodes and how to slow it down (`corrosion`), the electrochemical reactions underneath
batteries and electroplating (`electrochemistry`), the classical field equations for static charge
(`electrostatics`) and moving charge (`magnetism`), the strengthening/hardenability/fatigue
equations metallurgists use to process and specify alloys (`metallurgy`), and the carrier-transport
and junction equations that describe a diode or MOSFET (`semiconductors`). Every function is a pure
`Float64 -> Float64` formula — no shared state, no Python, and (with one exception noted below) no
struct crossing a module boundary. Two of the six modules independently implement the Nernst
equation and a "corrosion rate" calculation, using different physics and different guard behavior —
covered in detail below rather than glossed over.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# ASTM G1 weight-loss method: a coupon lost 500 mg of mass over one week (168 h) of exposure
runtime.execute("corrosion", "corrosion_rate_mpy", [500.0, 7.86, 10.0, 168.0])["result"]
# 20.219920029080326 — mils per year, from a 7.86 g/cm^3 (steel), 10 in^2 coupon

# Faraday's law: a 2 A plating current run for one hour onto a copper (63.55 g/mol, n=2) cathode
runtime.execute("electrochemistry", "faraday_mass_deposited", [63.55, 2.0, 3600.0, 2.0])["result"]
# 2.3711457739545008 — grams of copper deposited
```

## The modules

| Module | What it does |
| --- | --- |
| `corrosion` | weight-loss corrosion rate (mpy and mm/yr), pitting rate and pitting factor, galvanic potential difference, a Nernst potential, a Tafel overpotential, passivation current density, cathodic-protection current, and remaining-wall-thickness/service-life estimation |
| `electrochemistry` | Nernst cell potential, Faraday electrolysis mass, battery capacity and gravimetric energy density, a second (current-density-based) corrosion rate, Tafel slope, Butler-Volmer exchange current density, charge-transfer resistance, diffusion-limiting current, and coulombic efficiency |
| `electrostatics` | Coulomb's law, point-charge field and potential, parallel-plate capacitance and stored energy, electric flux, surface charge density, dielectric polarization, dielectric breakdown voltage, and the method-of-images force on a charge above a grounded conductor |
| `magnetism` | Biot-Savart field from an infinite wire, force on a current-carrying wire, solenoid and toroid field, magnetic flux, solenoid inductance, magnetic field energy density, cyclotron radius, Larmor frequency, and Hall voltage |
| `metallurgy` | Hall-Petch grain-size strengthening, Johnson-Cook flow stress, Brinell-to-tensile conversion, IIW weld carbon equivalent, Jominy end-quench hardenability decay, Avrami (JMAK) phase-transformation fraction, Grossmann quench severity, Hollomon-Jaffe tempering parameter, alloy density by rule of mixtures, Wiedemann-Franz thermal conductivity, strain-hardening exponent from two stress-strain points, and Basquin fatigue life |
| `semiconductors` | intrinsic carrier concentration, drift velocity, resistivity/conductivity, depletion width and built-in potential, thermal voltage, Shockley diode current, MOSFET saturation current, junction capacitance, minority-carrier diffusion length, and Varshni band-gap-vs-temperature |

## Two independent Nernst equations, with different guard postures

`corrosion.mojo`'s own docstring lists "electrochemistry (Nernst, Tafel)" among what it provides —
the overlap with the `electrochemistry` module is by design, not an accident, and the two
implementations diverge in a way worth knowing before calling either:

- `corrosion.nernst_potential(e0, n, q_ratio, temperature)` computes `E = E0 - (RT/nF)*ln(Q)`
  directly, with **no guard clauses at all**. Pass `n = 0.0` or a non-positive `q_ratio` and the
  division and `log()` propagate `inf`/`nan` straight through to the return value.
- `electrochemistry.nernst_cell_potential(e0, n_electrons, temperature, reaction_quotient)` computes
  the identical formula but checks `n_electrons <= 0.0 or reaction_quotient <= 0.0 or temperature <=
  0.0` first and returns `e0` unchanged rather than a non-finite result.

The two signatures also order their last two arguments differently — `corrosion` takes
`(q_ratio, temperature)`, `electrochemistry` takes `(temperature, reaction_quotient)` — so porting a
call from one module to the other by position rather than by name silently swaps the reaction
quotient and the temperature:

```python
runtime.execute("corrosion", "nernst_potential", [0.34, 2.0, 0.01, 298.15])["result"]
# 0.3991562616768297

runtime.execute("electrochemistry", "nernst_cell_potential", [0.34, 2.0, 298.15, 0.01])["result"]
# 0.3991562616768297 — same answer, but note temperature and Q traded places in the argument list
```

## Two `corrosion_rate` functions, two different physical routes

Both modules also expose a function that returns a corrosion rate in mils per year, and neither
is a wrapper around the other:

- `corrosion.corrosion_rate_mpy(weight_loss, density, area, time_hours)` is the ASTM G1 weight-loss
  method: `CR = 534*W / (D*A*T)`. It needs no electrochemical data at all — just a mass loss, a
  density, an area, and an exposure time.
- `electrochemistry.corrosion_rate(current_density, molar_mass, density, n_electrons)` derives the
  same physical quantity from Faraday's law applied to a measured corrosion current density:
  `CR = (i*M / (n*F*rho)) * 1.288e5`.

```python
# Same iron coupon, two unrelated ways of estimating its corrosion rate:
runtime.execute("corrosion", "corrosion_rate_mpy", [500.0, 7.86, 10.0, 168.0])["result"]
# 20.219920029080326 mpy — from a measured 500 mg weight loss

runtime.execute("electrochemistry", "corrosion_rate", [5.0, 55.85, 7.86, 2.0])["result"]
# 23.713556972889695 mpy — from a measured 5 A/m^2 corrosion current density
```

Nothing in either function checks the two answers against each other — that reconciliation (a
current density implies a mass loss rate through Faraday's law, and vice versa) is a real
electrochemical relationship, but it lives in the caller's head, not in either kernel.

## `corrosion_rate_mpy` and `corrosion_rate_mmpy` don't share an area unit

Within `corrosion` itself, the two weight-loss functions use the same `534`/`87600` ASTM constants
that convert the same physical formula to different output units, but their docstrings specify
**different area units**: `corrosion_rate_mpy`'s `area` is in in², `corrosion_rate_mmpy`'s `area`
is in cm². Neither function converts or validates the unit — passing the same in² measurement to
both, expecting the mm/yr answer to just be a unit-converted version of the mpy one, produces a
number that is wrong by the roughly 6.45x ratio between the two area units on top of the intended
534-vs-87600 scaling, with no error raised:

```python
# Same coupon, area given once as 10 in^2 (correct for _mpy, wrong unit for _mmpy):
runtime.execute("corrosion", "corrosion_rate_mpy", [500.0, 7.86, 10.0, 168.0])["result"]
# 20.219920029080326  — correct: mils/year from a 10 in^2 coupon

runtime.execute("corrosion", "corrosion_rate_mmpy", [500.0, 7.86, 10.0, 168.0])["result"]
# 3316.97564521992    — silently wrong: this function expects area in cm^2, not in^2
```

## Worked examples

Every number below was hand-derived from the real formula in the module's `.mojo` source and
independently checked with a plain Python calculation (see
[Verification](#verification)) — none are lifted from the module's own test file, which pins
nothing.

**Corrosion — galvanic couple, Tafel overpotential, and service life.** Standard reduction
potentials for iron (-0.44 V) and copper (+0.34 V) give the classic galvanic driving force between
the two metals; a small Tafel slope example and a wall-thickness projection chain follow the same
module's remaining functions:

```python
runtime.execute("corrosion", "galvanic_potential_difference", [-0.44, 0.34])["result"]
# 0.78 — volts of galvanic driving force between iron and copper

runtime.execute("corrosion", "tafel_overpotential", [0.1, 0.06, 1e-3])["result"]
# -0.07999999999999996 — eta = 0.1 + 0.06*log10(1e-3) = 0.1 + 0.06*(-3)

# A 6 mm wall corroding at 0.129 mm/yr: loss after 20 years, thickness remaining, and life estimate
runtime.execute("corrosion", "metal_loss_from_rate", [0.129, 20.0])["result"]        # 2.58 mm
runtime.execute("corrosion", "remaining_wall_thickness", [6.0, 2.58])["result"]      # 3.42 mm
runtime.execute("corrosion", "service_life_estimate", [6.0, 0.129])["result"]
# 46.51162790697674 — years until a 6 mm wall reaches zero at this rate
```

**Electrochemistry — batteries and Butler-Volmer kinetics.** A 2 A, 5-hour discharge and a nominal
3.7 V, 0.5 kg lithium cell, followed by an exchange current density and the charge-transfer
resistance it implies:

```python
runtime.execute("electrochemistry", "battery_capacity", [2.0, 5.0])["result"]        # 10.0 Ah
runtime.execute("electrochemistry", "energy_density", [3.7, 10.0, 0.5])["result"]     # 74.0 Wh/kg

runtime.execute("electrochemistry", "exchange_current_density",
                [1e-5, 10.0, 10.0, 0.5])["result"]
# 9.648500000000002 — A/m^2, from Butler-Volmer with equal oxidized/reduced concentrations

runtime.execute("electrochemistry", "charge_transfer_resistance",
                [9.648500000000002, 1.0, 298.15])["result"]
# 0.0026627183516890656 — Ohm*m^2
```

**Electrostatics — Coulomb's law and a parallel-plate capacitor.** Two 1 microcoulomb charges one
meter apart, and a 1 cm² plate pair 1 mm apart in air:

```python
runtime.execute("electrostatics", "coulomb_force", [1e-6, 1e-6, 1.0])["result"]
# 0.008987551792299998 N — matches k = 8.9875517923e9 N*m^2/C^2 exactly

runtime.execute("electrostatics", "capacitance_parallel_plate", [0.01, 0.001, 1.0])["result"]
# 8.854187817e-11 F — reduces to epsilon0*A/d when epsilon_r = 1

runtime.execute("electrostatics", "energy_stored_capacitor", [1e-6, 12.0])["result"]
# 7.2e-05 J — U = 0.5 * 1 uF * (12 V)^2
```

**Magnetism — a solenoid field and an electron's cyclotron motion.** A 500-turn, 20 cm solenoid
carrying 2 A, and a 1 MeV-scale electron in a 0.01 T field:

```python
runtime.execute("magnetism", "solenoid_field", [2.0, 500.0, 0.2])["result"]
# 0.006283185306999999 T — B = mu0 * (N/L) * I

runtime.execute("magnetism", "cyclotron_radius",
                [9.10938356e-31, 1e6, 1.60217663e-19, 0.01])["result"]
# 0.0005685630029443133 m — ~0.57 mm radius for an electron at 1e6 m/s in 0.01 T

runtime.execute("magnetism", "larmor_frequency",
                [1.60217663e-19, 0.01, 9.10938356e-31])["result"]
# 279924902.37266356 Hz — same electron and field, its cyclotron frequency
```

**Metallurgy — Hall-Petch strengthening and fatigue life.** A 10 micron grain size in a mild steel
(sigma0 = 70 MPa, ky = 0.74 MPa*sqrt(m)) and a Basquin fatigue-life projection:

```python
runtime.execute("metallurgy", "hall_petch", [70.0, 0.74, 1e-5])["result"]
# 304.0085468524601 MPa — yield strength at a 10 micron grain size

runtime.execute("metallurgy", "hardness_to_tensile", [200.0])["result"]
# 690.0 MPa — sigma_uts ~= 3.45 * 200 HB

runtime.execute("metallurgy", "fatigue_life_basquin", [900.0, 300.0, -0.09])["result"]
# 200146.16576372102 cycles — Nf = (300/900)^(1/-0.09)
```

**Semiconductors — the Shockley diode equation and Varshni's band gap.** A silicon-like junction at
300 K (kT/q = 25.85 mV) and the real Varshni fit constants for silicon's temperature-dependent band
gap (`Eg0 = 1.166 eV`, `alpha = 4.73e-4 eV/K`, `beta = 636 K`):

```python
runtime.execute("semiconductors", "thermal_voltage",
                [1.380649e-23, 300.0, 1.602176634e-19])["result"]
# 0.025851999786435535 V — the textbook ~25.85 mV thermal voltage at room temperature

runtime.execute("semiconductors", "diode_current", [1e-12, 0.7, 0.025852, 1.0])["result"]
# 0.5747545691036834 A — I = Is*(exp(V/(n*Vt)) - 1) at 0.7 V forward bias

runtime.execute("semiconductors", "band_gap_temperature", [1.166, 4.73e-4, 636.0, 300.0])["result"]
# 1.1205192307692307 eV — matches silicon's known ~1.12 eV band gap at 300 K
```

`resistivity` and `conductivity` are exact reciprocals of the same three inputs
(`1/(n*q*mobility)` and `n*q*mobility`) — for any shared `n`, `q`, `mobility`, their product is
`1.0` to floating-point precision, which is a useful self-check if you call both.

{% hint style="info" %}
**`electrostatics.electric_flux` and `magnetism.magnetic_flux` share the identical shape.** Both
compute `field * area * cos(angle_rad)` — the geometric definition of flux through a tilted surface
doesn't care whether the field is electric or magnetic, and neither function has a guard clause,
since the formula has no division or logarithm to protect.
{% endhint %}

## Guarantees and refusal behavior

The six modules do not share a uniform guard policy — knowing which one you're calling matters:

- **`corrosion` has no guard clauses anywhere in the file.** Every function is the bare formula; a
  zero `time_hours`, `area`, or `avg_penetration` produces `inf`, and a non-positive `q_ratio` in
  `nernst_potential` produces `nan` — both propagate silently to the caller rather than being
  intercepted.
- **`electrochemistry` guards nine of its ten functions** (every one with a division or a
  logarithm) and returns a defined fallback — `0.0`, or `e0` for `nernst_cell_potential` — instead
  of a non-finite value. Only `battery_capacity` (a bare multiply) has nothing to guard.
- **`electrostatics` and `magnetism` guard every function that divides**, returning `0.0` for a
  non-positive distance, separation, length, radius, carrier density, or thickness. The two flux
  functions and `magnetic_force_wire`/`magnetic_energy_density`/`dielectric_polarization` have no
  guards because their formulas have nothing to divide by.
- **`metallurgy` guards the functions built on `log`, `exp`, or a ratio** — `hall_petch`,
  `johnson_cook_flow_stress`, `avrami_fraction`, `tempering_parameter`,
  `strain_hardening_exponent_from_points`, and `fatigue_life_basquin` all return a defined fallback
  (often the first argument, unchanged) rather than a non-finite result. `carbon_equivalent`,
  `quench_severity`, `density_of_alloy_rule_of_mixtures`, and
  `thermal_conductivity_wiedemann_franz` are unguarded linear combinations with nothing to protect.
- **`semiconductors` is the least consistently guarded of the six.** Only `junction_capacitance`
  checks its inputs — and thoroughly, per its own source comment: it refuses a zero `vbi`, a
  non-positive `1 - v/vbi` base (which would otherwise take `log` of a non-positive number), and a
  zero result from `exp(m*log(base))` before dividing by it, "since inf/nan cannot cross the result
  wire." `resistivity`, `depletion_width`, `built_in_potential`, `thermal_voltage`, and
  `diode_current` all divide or take a logarithm with no equivalent check — a zero `mobility`,
  `q`, or `ni` reaches the caller as `inf` or `nan`.

None of the functions in this family take a `List` or index into one, so unlike the tensor and ML
kernel families elsewhere in this catalog, there is no bounds-check-abort risk here — the worst
case for an unguarded call is a non-finite `Float64`, never a killed worker.

## Verification

All six `mojo/tests/libs/test_*.mojo` files behind this family (`test_corrosion.mojo`,
`test_electrochemistry.mojo`, `test_electrostatics.mojo`, `test_magnetism.mojo`,
`test_metallurgy.mojo`, `test_semiconductors.mojo`) are auto-generated coverage smoke tests: each
calls every function once on a shared, arbitrary `0.5`-valued fixture and checks only that the
result is finite — none pin a specific numeric output. Every worked example above was instead
hand-derived from the real formula in `mojo/engine/corrosion.mojo`, `electrochemistry.mojo`,
`electrostatics.mojo`, `magnetism.mojo`, `metallurgy.mojo`, and `semiconductors.mojo`, and
cross-checked with an independent plain-Python calculation of the same formula before being written
down here — the silicon band-gap and room-temperature thermal-voltage examples additionally match
well-known textbook reference values (~1.12 eV, ~25.85 mV) as a further check that the formulas and
constants are wired correctly.

**Next:** see [Runtime library catalog](runtime-library-catalog.md) for every module and function
in the full contract, or [Engine catalog](catalog.md) for how these kernel modules are grouped and
served as API-level engines.
