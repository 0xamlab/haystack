---
icon: industry
description: Hydraulic (pressurized-liquid) power transmission, pneumatic (compressed-air) power transmission, and grid-scale AC power engineering — three independent kernel modules, none of which overlap with the separate circuit-theory module `electrical`.
---

# Industrial fluid power and energy systems kernels

Three independent modules for moving power around a plant or a grid without a shaft connecting the source to the load. `hydraulics` is force and motion carried by a pressurized, effectively incompressible liquid — Pascal's law, cylinder sizing, pump displacement, accumulator sizing. `pneumatics` is the same job done with a compressible gas instead — Boyle's law, orifice and pipe flow, compressor sizing, air receivers and dryers. `power_systems` is a level up from both: it is not fluid power at all, but AC/DC electrical power engineering at the scale of a transformer, a feeder line, or a whole grid's demand curve — three-phase power, transformer ratios, line loss, power factor, and load factor. All thirty-six functions across the three modules take and return plain `Float64` scalars, so each one is a single checkable formula with no struct or status-code layer in between.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# Pascal's law: a 100 kPa pressure over a 0.01 m^2 piston
runtime.execute("hydraulics", "pascals_law_force", [100000.0, 0.01])["result"]
# 1000.0 -- F = P * A, in newtons

# Boyle's law: 10 L of gas at 200 kPa, compressed to 400 kPa
runtime.execute("pneumatics", "ideal_gas_volume", [200.0, 10.0, 400.0])["result"]
# 5.0 -- V2 = P1*V1/P2, isothermal

# 230 V, 10 A, power factor 0.8
runtime.execute("power_systems", "active_power", [230.0, 10.0, 0.8])["result"]
# 1840.0 -- P = V*I*PF
```

## The modules

| Module | What it does |
| --- | --- |
| `hydraulics` | Pascal's-law force and pressure, cylinder sizing and velocity, pump displacement, hydraulic power, a simplified pressure-loss term, gas-charged accumulator sizing, relief-valve flow, oil compressibility, and cylinder bore from a target force. |
| `pneumatics` | Boyle's-law gas expansion, orifice and Darcy-Weisbach pipe flow, isothermal compressor power, cylinder force and speed for pneumatic actuators, air-receiver sizing, free-air-delivery normalization, specific power, and a simplified pressure-dew-point estimate. |
| `power_systems` | AC/DC active, reactive, and apparent power; power factor; three-phase power; transformer turns ratio and secondary voltage; line loss and voltage drop; power efficiency; capacitor reactive power; and demand load factor. |

## `hydraulics`: Pascal's law, cylinders, pumps, and accumulators

| Function | What it does |
| --- | --- |
| `pascals_law_force(pressure, area)` | `F = P * A`. |
| `pascals_law_pressure(force, area)` | `P = F / A`. |
| `hydraulic_advantage(area_output, area_input)` | `MA = A_out / A_in` — the force multiplication of a two-piston hydraulic jack. |
| `flow_rate_cylinder(area, velocity)` | `Q = A * v`. |
| `cylinder_velocity(flow_rate, area)` | `v = Q / A` — the inverse of `flow_rate_cylinder`. |
| `pump_displacement(flow_rate, rpm)` | `D = Q / RPM`, displacement per revolution. |
| `hydraulic_power(pressure, flow_rate)` | `P = pressure * Q`, watts when pressure is in Pa and flow in m³/s. |
| `system_pressure_loss(flow_rate, resistance)` | `ΔP = Q² * R` — the docstring itself calls this "simplified": a single lumped-resistance term standing in for the sum of a real circuit's line, fitting, and valve losses. |
| `accumulator_volume(gas_precharge, min_pressure, max_pressure)` | `V = Vp * (Pmax/Pmin - 1)` — see below. |
| `relief_valve_flow(pressure, cracking_pressure, gain)` | `(P - Pc) * gain` once `P` exceeds the cracking pressure, else `0.0`; at `P == Pc` exactly it also returns `0.0` (the comparison is strict `>`, not `>=`). |
| `oil_compressibility(volume, pressure_change, bulk_modulus)` | `ΔV = V * ΔP / B` — how much a trapped volume of hydraulic oil shrinks under a pressure rise, given the fluid's bulk modulus. |
| `cylinder_bore_from_force(force, pressure)` | `d = sqrt(4F / (π·P))` — the bore diameter needed to produce a target force at a given pressure. |

**None of these twelve functions guard a zero or negative denominator.** `hydraulics.mojo` has exactly one conditional in the whole file — the strict `>` in `relief_valve_flow` — and it exists to gate the valve, not to protect a division. `pascals_law_pressure(F, 0.0)`, `hydraulic_advantage(a, 0.0)`, `cylinder_velocity(q, 0.0)`, and `pump_displacement(q, 0.0)` all divide by their second argument with nothing stopping a `0.0` from producing `inf` or `-inf`, and `cylinder_bore_from_force` takes `sqrt` of `4*force/(π*pressure)` with no check that the argument under the root is non-negative — a negative `pressure` produces `NaN` rather than a refused call. This is a real, checkable contrast with `pneumatics.mojo` below, which guards every one of its divisions.

**`accumulator_volume`'s formula puts the wrong pressure on the bottom.** With only `gas_precharge`, `min_pressure`, and `max_pressure` as arguments and no separate precharge-pressure input, the only physically consistent reading is that `gas_precharge` (`Vp` in the docstring) is the gas volume at the state where the accumulator sits at `min_pressure` — the ordinary simplifying assumption for a two-pressure sizing problem. Boyle's law (`P·V = const`, the same relation `pneumatics.ideal_gas_volume` implements directly) then gives the usable oil volume swept between `min_pressure` and `max_pressure` as `Vp * (1 - min_pressure/max_pressure)`, not `Vp * (max_pressure/min_pressure - 1)` as implemented. The two agree only when `min_pressure == max_pressure` (both `0.0`); everywhere else the implemented formula returns more oil than Boyle's law allows, and the gap grows with the pressure ratio. Concretely, for `accumulator_volume(10.0, 100.0, 200.0)` (the module's own test case), Boyle's law gives `10.0 * (1 - 100/200) = 5.0`, while the implemented formula returns `10.0 * (200/100 - 1) = 10.0` — exactly double, because `200/100` and `1 - 100/200` are reciprocal-shaped ratios that only coincide when the pressure ratio is `1`. A caller sizing a real accumulator's precharge off this function's return would size it for half the delivered oil volume the number promises.

## `pneumatics`: Boyle's law, orifices, compressors, and air treatment

| Function | What it does |
| --- | --- |
| `ideal_gas_volume(pressure1, volume1, pressure2)` | Boyle's law: `V2 = P1*V1/P2`; `0.0` if `pressure2` is within `1e-30` of zero. |
| `flow_rate_orifice(cd, area, pressure_drop, density)` | `Q = Cd * A * sqrt(2*ΔP/ρ)`; `0.0` if `density` is near zero or the term under the root would be negative. |
| `compressor_power(flow_rate, p1, p2, efficiency)` | Isothermal compression power, `P = Q*P1*ln(P2/P1)/eff`; `0.0` if `efficiency` or `p1` is near zero, or the pressure ratio is non-positive. |
| `pressure_drop_pipe(f, length, diameter, density, velocity)` | Darcy-Weisbach: `ΔP = f*(L/D)*ρ*v²/2`; `0.0` if `diameter` is near zero. |
| `air_consumption(bore_diameter, stroke, pressure, cycles_per_min)` | Double-acting-cylinder air draw: `π/4*d²*stroke*2*(pressure/101.325)*cycles`, i.e. bore-swept volume per cycle times the ratio of working pressure to standard atmospheric pressure (`101.325` kPa), times cycles per minute. |
| `cylinder_force(bore_area, pressure)` | `F = A * P`, newtons. |
| `bore_area(diameter)` | `A = π*d²/4`. |
| `piston_speed(stroke, cycles_per_min)` | `v = 2*stroke*cycles/60`, m/s (the `2` counts both strokes of a double-acting cycle). |
| `receiver_volume(flow_rate, run_time, p_max, p_min)` | `V = Q*t/(Pmax - Pmin)`; `0.0` if the pressure band is within `1e-30` of zero. |
| `free_air_delivery(measured_flow, measured_pressure, atm_pressure)` | `FAD = flow * measured_pressure / atm_pressure`; `0.0` if `atm_pressure` is near zero. |
| `specific_power(power_kw, fad)` | `SP = power/FAD`, kW per m³/min of free air delivered; `0.0` if `fad` is near zero. |
| `dew_point_pressure(atm_dew_point, pressure_ratio)` | Its own docstring calls this "simplified": `DP ≈ atm_dp + 10*ln(ratio)`; returns `atm_dew_point` unchanged if `pressure_ratio <= 0.0`. |

**Every division in this module is guarded, and consistently** — eight of the twelve functions above check their denominator against `fabs(x) < 1e-30` (or an equivalent non-positive check on a ratio or a square-root argument) before dividing, returning `0.0` rather than `inf`/`NaN`. That is a deliberate, file-wide pattern, not incidental: `hydraulics.mojo` has no equivalent guard anywhere, and `power_systems.mojo` (below) guards with an exact `== 0.0` rather than an epsilon band.

**`air_consumption`'s docstring calls its pressure argument "gauge," but the module treats it as absolute.** The parameter comment reads "Working gauge pressure (kPa abs)" — gauge and absolute in the same phrase — and the arithmetic and the module's own test settle it: `air_consumption(0.1, 0.5, 101.325, 1.0)` (pressure passed as exactly one standard atmosphere) is verified against `π/4*0.01*0.5*2*(101.325/101.325)*1.0 ≈ 0.007854`, i.e. a pressure ratio of exactly `1.0` at atmospheric pressure — the ratio a gauge reading of `101.325` (which would mean roughly two atmospheres absolute) would not produce. The argument is an absolute pressure in kPa; the word "gauge" in the docstring is a naming error, not a unit convention a caller should follow.

**A worked compressor-sizing chain.** A double-acting cylinder with a 100 mm bore (`bore_area(0.1) = 0.0078540 m²`) driven at 600 kPa produces `cylinder_force(0.0078540, 600000.0) ≈ 4712.39` N per stroke. Cycling at 60 cycles/min with a 0.3 m stroke, `air_consumption(0.1, 0.3, 600.0, 60.0) = 0.0078540*0.3*2*(600/101.325)*60 ≈ 1.6743` m³/min of free air at working pressure. Sizing a receiver to ride out a 5-second compressor-off period between a 700 kPa and a 650 kPa band, `receiver_volume(1.6743, 5.0/60.0, 700.0, 650.0) ≈ 0.00279` m³ (about 2.8 liters) — the same shape of chained call as any other module in this corpus, each function's output feeding the next's input.

## `power_systems`: AC power, transformers, and grid-scale losses

| Function | What it does |
| --- | --- |
| `active_power(voltage, current, power_factor)` | `P = V*I*PF`, real (working) power. |
| `reactive_power(voltage, current, power_factor)` | `Q = V*I*sin(φ)`, computed as `sin(φ) = sqrt(1 - PF²)` — see below for what happens outside `PF ∈ [-1, 1]`. |
| `apparent_power(voltage, current)` | `S = V*I`, the vector sum of active and reactive power. |
| `power_factor_from_pq(p, s)` | `PF = P/S`; `0.0` if `s == 0.0` exactly. |
| `three_phase_power(v_line, i_line, pf)` | `P = √3 * V*I*PF`, balanced three-phase active power. |
| `transformer_turns_ratio(v_primary, v_secondary)` | `a = Vp/Vs`; `0.0` if `v_secondary == 0.0` exactly. |
| `transformer_secondary_voltage(v_primary, turns_ratio)` | `Vs = Vp/a`; `0.0` if `turns_ratio == 0.0` exactly. |
| `line_loss(current, resistance)` | `P_loss = I²*R`. |
| `voltage_drop(current, resistance, length)` | `V_drop = 2*I*R*L` — the `2` accounts for the round-trip conductor (out and back), so `resistance` is a per-unit-length figure. |
| `power_efficiency(output_power, input_power)` | `η = Pout/Pin`; `0.0` if `input_power == 0.0` exactly. |
| `capacitor_reactive_power(voltage, capacitance, frequency)` | `Qc = V² * 2πfC`. |
| `load_factor(avg_demand, peak_demand)` | `LF = avg/peak`; `0.0` if `peak_demand == 0.0` exactly. |

**Every guard here checks for exact `== 0.0`, not a near-zero band.** Unlike `pneumatics.mojo`'s `fabs(x) < 1e-30` epsilon guards, the five division guards in this module (`power_factor_from_pq`, both transformer functions, `power_efficiency`, `load_factor`) only trip on a denominator that is precisely `0.0`. A denominator of `1e-300` — non-zero in floating point, but not meaningfully different from zero for any real grid measurement — passes every guard here and produces a finite but enormous result rather than the module's own `0.0` sentinel.

**`reactive_power` has no domain guard on `power_factor`, and it is reachable with an ordinary-looking input.** `sin(φ)` is computed as `sqrt(1 - PF²)`, which is only real for `PF ∈ [-1, 1]`. A power factor is dimensionless and by convention stays in that range, but nothing in the function stops a caller from passing one outside it — a miscomputed `power_factor_from_pq` result greater than `1.0` (possible if a caller mixes up which value is `P` and which is `S`) flows straight into `reactive_power` and produces `1.0 - PF²` negative, so `sqrt` returns `NaN` with no guard to catch it, unlike every division in this same module.

A worked chain: `active_power(230.0, 10.0, 0.8) = 1840.0` W and `apparent_power(230.0, 10.0) = 2300.0` VA give back `power_factor_from_pq(1840.0, 2300.0) = 0.8` exactly — the three functions round-trip. `reactive_power(230.0, 10.0, 0.8)`, with `sin(φ) = sqrt(1 - 0.64) = 0.6`, is `1380.0` VAR, and `1840² + 1380² = 2300²` to floating-point precision — active and reactive power really do form the two legs of the right triangle apparent power is the hypotenuse of. For a 400 V line at 50 A and `PF = 0.9`, `three_phase_power(400.0, 50.0, 0.9) = √3 * 400 * 50 * 0.9 ≈ 31176.91` W.

## A distinct sibling module this page does not cover: `electrical`

The runtime library contract also defines a fourteen-function module named `electrical` — but reading its actual functions (`ohms_law_v`/`_i`/`_r`, `series_resistance`, `parallel_resistance`, `voltage_divider`, `rc_time_constant`, `rc_voltage`, `rlc_resonance`, `inductive_reactance`, `capacitive_reactance`, `impedance_magnitude`, `power_dc`, `power_factor`) shows it is component-level DC/AC circuit theory — Ohm's law, resistor networks, RC/RLC transient and resonant behavior, impedance — not grid-scale power engineering. It shares no functions and no formulas with `power_systems`: the two modules answer different questions at different scales, one about a single circuit element, the other about a transformer, a feeder, or a whole demand curve. `electrical` is not documented on this page or anywhere else in `gitbook/` as of this writing — grepping the corpus for it turns up only the runtime library catalog's function count and an unrelated mention of a wave-test file's title — so it remains a real gap, but a separate one from the three modules covered here.

## Verification

`mojo/tests/libs/test_hydraulics.mojo`, `test_pneumatics.mojo`, and `test_power_systems.mojo` are the auto-generated coverage smoke tests for these three modules: each calls every function once with literal `0.5` arguments (`0.5, 0.5, 0.5` for accumulator-style three-argument functions) and checks only that the result is finite. They do not pin any specific numeric output.

Real, hand-verified numeric suites exist for all three modules in `tests/mojo/`: `test_wave95.mojo` ("Wave 95: semiconductors, viticulture, hydraulics") checks `hydraulics` against independently worked values, including two explicit round-trips (`pascals_law_force` → `pascals_law_pressure` back to the original pressure, and `cylinder_bore_from_force` fed back through `π*d²/4*pressure` to recover the original force); `test_wave94.mojo` checks all twelve `pneumatics` functions against hand-computed values (22 assertions); and `test_wave66.mojo` ("Wave 66 — Robotics, Psychometrics, Power Systems") checks all twelve `power_systems` functions, including the active/reactive/apparent-power right-triangle relationship and a transformer round-trip. Every worked number in this page came from one of those three files or was independently recomputed in plain Python against the formula in the corresponding `mojo/engine/*.mojo` source, including the `accumulator_volume` discrepancy above, which was checked both symbolically and against the module's own `10.0`/`100.0`/`200.0` test case.

**Next:** see [Thermal, cryogenic, and energy kernels](thermal-and-energy-materials-kernels.md) for the battery and renewable-generation physics that sits on the other side of `power_systems`' grid, or browse the [Runtime library catalog](runtime-library-catalog.md) for every module and function.
