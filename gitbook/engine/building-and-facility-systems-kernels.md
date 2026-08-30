---
icon: building
description: Vertical-transport and building-facility engineering -- elevator dispatch/sizing, fire-safety egress and suppression, HVAC heat load, plumbing hydraulics, refrigeration cycles, wastewater treatment design, and city-scale urban-planning ratios -- across seven independent kernel modules.
---

# Building and facility systems kernels

Seven small, self-contained modules for the engineering that sizes and operates the systems
inside and around a building: how many elevator cars a lobby needs and how long people wait for
one, how much time occupants have to escape a fire and how a sprinkler head decides to trip, how
much heating or cooling a room's airflow demands, how a water or drainage pipe is sized and what
pressure surge it can survive, the thermodynamic cycle a refrigeration or heat-pump compressor
runs, the retention times and loading ratios that size a wastewater treatment train, and the
density, zoning, and traffic ratios a city planner checks against code. None of the seven import
Python, none share code with each other, and every function takes and returns plain `Float64`
scalars (`co_concentration_danger` alone returns an `Int` classification) — there is no shared
struct or status-code vocabulary across this family, just one checkable formula per function.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# A 10-floor, 3 m-per-floor building, 2 m/s cars, 3 s door time, 8 passengers/trip
runtime.execute("elevator", "round_trip_time", [10.0, 3.0, 2.0, 1.0, 3.0, 8.0])["result"]
# 76.0 seconds -- 2*(10*3)/2 travel + 10*3 door time + 8*2 passenger transfer

runtime.execute("elevator", "handling_capacity", [10.0, 76.0])["result"]
# 39.473684210526315 -- a 10-person car on a 76 s round trip moves ~39.5 people per 5 minutes
```

## The modules

| Module | What it does |
| --- | --- |
| `elevator` | Round-trip time, handling capacity, interval time, probable-stops traffic estimation, motor power, counterweight sizing, shaft area, annual energy consumption, average waiting time, traffic intensity, rope factor of safety, and pit depth. |
| `fire_safety` | Fire load density, heat release rate, the Thomas flashover correlation, sprinkler activation time, smoke-layer descent, evacuation time, safe egress time (RSET), fire-resistance rating, ventilation factor, fire severity, CO-concentration danger classification, and occupant load. |
| `hvac` | Sensible, latent, and total heat load, sensible heat ratio, cooling-tonnage conversion, air changes per hour, duct velocity, COP↔EER conversion, and heating/cooling degree-days. |
| `plumbing` | Pipe flow velocity, Reynolds number, laminar friction factor, Darcy-Weisbach and minor head loss, total dynamic head, pump power, fixture-unit water demand, velocity-method pipe sizing, thermal pipe expansion, water-hammer pressure, and minimum drainage slope. |
| `refrigeration` | Actual and Carnot COP for both refrigeration and heat-pump cycles, tons-of-refrigeration conversion, superheat, subcooling, mass flow rate, compressor work, EER, SEER↔COP conversion, and refrigerant-charge estimation. |
| `wastewater` | BOD removal efficiency, hydraulic and solids retention time, food-to-microorganism ratio, sludge volume index, oxygen demand, chlorine demand, CT value, alkalinity consumption, sludge production, trickling-filter efficiency (simplified NRC), and settling detention time. |
| `urban_planning` | Population density, floor-area ratio, lot coverage, green-space ratio, walk-score distance decay, vehicle-miles traveled, parking requirement, traffic level-of-service, housing affordability ratio, jobs-housing balance, infrastructure cost per unit, and impervious-surface ratio. |

## Verification: two very different test suites behind this page

Six of these seven `mojo/tests/libs/test_*.mojo` files are auto-generated coverage smoke
tests — each calls every function once with the literal argument `0.5` and checks only that the
result is finite, pinning no specific numeric output. But **all seven modules also have real,
hand-verified pinned test suites**, living not next to the library file but bundled into
`tests/mojo/test_wave*.mojo` alongside two unrelated modules that happened to ship the same week:
`test_wave81.mojo` (elevator, with antenna and toxicology), `test_wave82.mojo` (fire_safety, with
printing and procurement), `test_wave73.mojo` (hvac, with corrosion and paleontology —
the file that marks the engine's 300th library milestone), `test_wave85.mojo` (plumbing, with
crystallography and pension), `test_wave88.mojo` (refrigeration, with cartography and
bioinformatics), `test_wave77.mojo` (wastewater, with polymer science and sports analytics), and
`test_wave79.mojo` (urban_planning, with food science and cryogenics). Those wave files assert
specific numbers against hand-worked arithmetic, not just finiteness, and every worked example
below is drawn from them (or independently recomputed in Python against the real formula in
`mojo/engine/*.mojo` where a wave test didn't already cover the case).

## Elevator: round-trip time drives everything else

`round_trip_time` (RTT) is the seed value the rest of the module builds on. For a 10-floor
building with 3 m floors, 2 m/s cars, 1 m/s² acceleration (accepted but not used by this
simplified formula), a 3 s door cycle, and 8 passengers per trip, `round_trip_time(10, 3, 2, 1, 3,
8)` returns `76.0` s — `2*(10*3)/2` travel time, plus `10*3` door time, plus `8*2` passenger
transfer time. Feed that RTT into `handling_capacity(car_capacity, rtt)` and a 10-person car
manages `10*300/76 = 39.4737` people per 5 minutes; feed it into `interval_time(rtt, n_cars)` with
4 cars and the wait between car arrivals is `76/4 = 19.0` s, and `waiting_time_average` halves that
to `9.5` s. `traffic_intensity(arrivals_per_5min, handling_cap)` then compares a measured arrival
rate against that handling capacity — a value above `1.0` means the bank of cars cannot clear the
crowd as fast as it arrives.

`probable_stops(floors, passengers)` implements the standard elevator-traffic formula
`S = N*(1-(1-1/N)^P)` using `exp`/`log` rather than a `pow` intrinsic — for a 10-floor building
carrying 8 passengers, `probable_stops(10, 8) = 10*(1-0.9^8) = 5.6953`, meaning a full car making a
down trip is expected to stop at roughly 5.7 of the 10 floors, not all 10.

{% hint style="info" %}
**`pit_depth_requirement` hardcodes gravity; `motor_power` in the same module does not.**
`motor_power(load_kg, speed_mps, gravity, efficiency)` takes gravity as an explicit argument, so
a caller can size a motor for a non-Earth installation or a different `g` convention.
`pit_depth_requirement(speed_mps)`, the last function defined in the same file, computes
`0.5*v²/(2*9.81) + 0.5` with `9.81` baked into the formula and no `gravity` parameter in its
signature at all (confirmed against the contract: `pit_depth_requirement` takes only
`speed_mps`). For a 2.5 m/s car this gives `0.5*6.25/19.62 + 0.5 = 0.6593` m, matching the pinned
test — but there is no way to ask this particular function for a pit depth under any other value
of `g`.
{% endhint %}

## Fire safety: several formulas are explicitly labeled "simplified"

The module docstring is direct about this: `flashover_mfo` is "the Thomas correlation,
simplified," `sprinkler_activation_time` "ignores temperature ratio for simplicity," and
`smoke_layer_height` and `fire_severity` are both marked "simplified" too. Taking
`flashover_mfo(area_vent=2.0, height_vent=2.5, area_total=100.0)` at face value:
`Q_fo = 750*2*sqrt(2.5) + 378*100 = 40171.71` kW, matching the pinned test to five figures.
`ventilation_factor(2.0, 2.0) = 2.0*sqrt(2.0) = 2.8284`, and `fire_severity(500.0, 2.8284) =
176.777` — a ratio of fire load to ventilation opening, not the full Kawagoe compartment-fire
severity model.

`co_concentration_danger` is the one function in this module returning an `Int`, and its
boundaries are exact rather than approximate: `ppm > 200.0` is danger (`2`), `35.0 <= ppm <= 200.0`
is warning (`1`, closed on both ends — `co_concentration_danger(200.0)` returns `1`, not `2`), and
anything below `35.0` is safe (`0`). `smoke_layer_height` clamps at the floor: a small room with a
large fire (`ceiling_height=3.0, time_s=100.0, hrr=100.0`) computes a negative descent past the
ceiling and the function returns `0.0` rather than a nonsensical negative smoke-layer height.

## HVAC: the standard sea-level air constants, and a chain that has to balance

`sensible_heat_load` and `latent_heat_load` use the textbook ASHRAE constants for standard air at
sea level — `1.08` and `0.68` — not a derived or configurable air-density term. Chaining `cfm=500,
delta_t=15` and `delta_w=25` gives `sensible = 1.08*500*15 = 8100` BTU/hr and
`latent = 0.68*500*25 = 8500` BTU/hr; `total_heat_load(8100, 8500) = 16600`, and
`sensible_heat_ratio(8100, 16600) = 0.48795` — multiplying that ratio back by the total recovers
the original sensible load to the last representable bit, which is the same "recompute and
compare" self-check shape used elsewhere in this corpus, just for a heat balance instead of a
gradient. `cop_to_eer` and `eer_to_cop` use the constant `3.412` (BTU/Wh) and are exact inverses of
each other (`cop_to_eer(4.0) = 13.648`, `eer_to_cop(13.648) = 4.0`); `refrigeration.seer_to_cop`
uses the identical `3.412` constant independently, in a separate file, with no shared code between
the two modules.

## Plumbing: every division guards its own denominator

Every function in `plumbing.mojo` that divides by a caller-supplied value checks
`fabs(denominator) < 1e-30` first and returns `0.0` rather than propagating an infinity — a
stricter, floating-point-aware guard than the plain `== 0.0` checks used in `fire_safety` and
`wastewater`. `pipe_sizing_velocity_method(flow_rate, max_velocity)` inverts
`pipe_flow_velocity`: sizing a pipe for `Q = 0.05` m³/s at a maximum velocity of `1.5` m/s gives
`d = sqrt(4*0.05/(π*1.5)) = 0.2060` m, and running that diameter back through
`pipe_flow_velocity(0.05, 0.2060)` recovers `1.5` m/s, confirming the two are algebraic inverses.
`water_hammer_pressure(density, velocity, wave_speed)` is the (simplified, single-term) Joukowsky
surge equation — `1000 * 2.0 * 1400.0 = 2,800,000` Pa for a 2 m/s velocity change and a 1400 m/s
wave speed in the pipe, roughly 28 atmospheres, which is why real systems fit surge arrestors
rather than relying on pipe wall strength alone.

## Refrigeration: two Carnot functions, two different argument orders

`carnot_cop_refrigeration(tc, th)` takes the **cold** reservoir first; the very next function in
the same file, `carnot_cop_heat_pump(th, tc)`, takes the **hot** reservoir first — confirmed against both the
contract's parameter lists and the source. Called correctly, `carnot_cop_heat_pump(300.0, 250.0) =
300/(300-250) = 6.0`, matching the pinned test. But a caller who assumes both twin functions share
one argument order and passes temperatures as `(cold, hot)` out of habit from the refrigeration
side — `carnot_cop_heat_pump(250.0, 300.0)` — gets `th=250, tc=300, dt=-50`, and the function
returns `250/-50 = -5.0`. Unlike some of the parameter-order footguns documented elsewhere in this
corpus, this one is mostly self-flagging: a negative COP is physically meaningless and an obvious
tell that the arguments were swapped, rather than a plausible-looking wrong number.

`cop_refrigeration`, `cop_heat_pump`, `mass_flow_rate`, and `energy_efficiency_ratio` all guard
their denominator at `fabs(x) < 1e-30`, the same tolerance-based style `plumbing` uses (both files
share the `abs as fabs` import convention), returning `0.0` on a zero work input, enthalpy
difference, or power draw rather than an infinity.

## Wastewater: a real stoichiometric constant, one worked retention-time chain

`alkalinity_consumption(ammonia_removed) = 7.14 * ammonia_removed` — `7.14` mg CaCO₃ consumed per
mg of NH₄⁺-N nitrified is the standard textbook stoichiometric ratio for biological nitrification,
not an arbitrary tuning constant. `solids_retention_time` is the module's most-parameterized
function (six arguments: tank volume, mixed-liquor suspended solids, waste flow and its solids
concentration, effluent flow and its solids concentration) — for `volume=1000, mlss=3000,
waste_flow=50, waste_ss=8000, effluent_flow=950, effluent_ss=20`, the denominator
`50*8000 + 950*20 = 419,000` and `SRT = 1000*3000/419000 = 7.1599` days, matching the pinned test.
`trickling_filter_efficiency`'s docstring is explicit that its formula is a "simplified NRC" —
the real NRC design equation includes a recirculation factor computed from `R`, not `R` used
directly inside the square root, and this function's `bod_in <= 0.0` guard covers the zero-load
case but not a (physically meaningless) `recirculation_ratio` of exactly `-1.0`, which would still
divide by zero inside the square root.

## Urban planning: no denominator is guarded at all

Ten of `urban_planning.mojo`'s twelve functions perform a division, and every one of those ten —
`population_density`, `floor_area_ratio`, `lot_coverage`, `green_space_ratio`,
`walk_score_distance_decay`, `traffic_level_of_service`, `housing_affordability_ratio`,
`jobs_housing_balance`, `infrastructure_cost_per_unit`, and `impervious_surface_ratio` — divides
its caller-supplied denominator directly, with no zero check anywhere in the file (only
`walk_score_distance_decay` clamps the *result* to `0.0` when the ratio goes negative; it never
checks whether `max_distance` itself is zero). `traffic_level_of_service(1500.0,
0.0)` and `housing_affordability_ratio(400000.0, 0.0)` both return `inf` rather than the `0.0`
sentinel that `fire_safety`, `plumbing`, `refrigeration`, and `wastewater` return for the
equivalent situation elsewhere in this same page. `elevator` shares this same unguarded
convention for its own ratio functions (`handling_capacity`, `interval_time`,
`traffic_intensity`, `rope_factor_of_safety` all divide without a zero check; only
`probable_stops` guards its edge case), and three of `hvac`'s twelve functions
(`sensible_heat_ratio`, `air_changes_per_hour`, `duct_velocity`) are unguarded the same way. The
"return `0.0` on a zero denominator" convention that the worked examples above rely on for
`fire_safety`, `plumbing`, `refrigeration`, and `wastewater` is real, but it is not universal
across this page — a caller feeding a zero plot area, zero capacity, or zero housing-unit count
into `urban_planning` or the bulk of `elevator` gets an unguarded `inf` or `nan` back, not a clean
zero.

**Next:** see [Hydrology and water-systems kernels](hydrology-and-water-systems-kernels.md) for
the open-channel and groundwater hydraulics `plumbing`'s pipe-flow formulas sit beside, or browse
the [Runtime library catalog](runtime-library-catalog.md) for every module and function.
