---
icon: satellite-dish
description: LiDAR point-cloud geometry and vegetation-return metrics, LiDAR-derived terrain/canopy mapping and survey QA, and the core radar range/Doppler/link-budget equations.
---

# Ranging and remote-sensing kernels

Three modules for active-sensing systems that measure distance by timing a reflected pulse.
`lidar` is airborne-survey geometry — footprint size, swath width, ground sampling distance,
point density, and the vegetation and terrain metrics (canopy height, slope, a Beer-Lambert-style
vegetation index) derived from first and last laser returns. `lidar_mapping` covers the same
physical instrument from the production/QA side of turning a point cloud into a terrain model —
a ground-classification threshold, a canopy-height model, leaf area index from gap fraction, and
the vertical-accuracy and surface-roughness checks a mapping deliverable is validated against; it
is not a SLAM or pose-graph module — there is no odometry, no scan matching, and no pose state
anywhere in it. `radar` is the separate physics of a radio-frequency system: the range equation,
Doppler frequency and velocity, range/velocity ambiguity limits, range resolution, antenna gain,
radar cross section, thermal noise power, and signal-to-clutter ratio. All three take and return
plain `Float64` scalars — no structs, no status-code vocabulary — so every function is a single
formula that either lands on the right number or a visibly wrong one.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# range_from_tof: 1 microsecond round-trip time-of-flight, default c = 3.0e8 m/s
runtime.execute("lidar", "range_from_tof", [1.0e-6, 3.0e8])["result"]
# 150.0 -- R = c*t/2, pinned in tests/mojo/test_wave87.mojo

# doppler_frequency: a 300 m/s closing target at a 0.03 m (X-band-ish) wavelength
runtime.execute("radar", "doppler_frequency", [300.0, 0.03])["result"]
# 20000.0 -- fd = 2*v/lambda, pinned in tests/mojo/test_wave86.mojo
```

## The modules

| Module | What it does |
| --- | --- |
| `lidar` | Airborne LiDAR survey geometry and return-based metrics: range from time-of-flight, point density, scan swath width, laser footprint diameter, point rate from PRF, ground sampling distance, a first/last-return vegetation index, canopy height (DSM − DTM, unclamped), slope from elevation difference, range-squared intensity normalization, strip overlap percentage, and estimated point-cloud file size. |
| `lidar_mapping` | The point-cloud-to-terrain-model production and QA side of the same instrument: range from time-of-flight (nanosecond input, fixed `c`), point density, a canopy-height model (DSM − DTM, clamped at 0), leaf area index from gap fraction via Beer-Lambert, a ground-filter height threshold, laser beam footprint diameter, pulse return intensity from reflectance and range, along-track scan-line spacing, a vertical-accuracy residual against check points, and RMS surface roughness from plane-fit residuals. |
| `radar` | Core radar-systems equations: a simplified radar-range factor, Doppler frequency and velocity, range from round-trip time, pulse repetition interval, maximum unambiguous range and velocity, range resolution from bandwidth, antenna gain from aperture area, the radar cross section of a sphere, thermal noise power, and signal-to-clutter ratio. |

## Three ways to turn a travel time into a range, three different signatures

All three modules include a "range from a pulse's round-trip time" function, and the three do
not agree on units, on where `c` comes from, or on whether it is even a parameter:

| Function | Input unit | Speed of light | How `c` is supplied |
| --- | --- | --- | --- |
| `lidar.range_from_tof(time_of_flight, c)` | seconds | `3.0e8` | optional parameter, defaults to `3.0e8` |
| `lidar_mapping.range_from_time_of_flight(time_ns)` | **nanoseconds** | `2.998e8` | hardcoded inside the function, not a parameter at all |
| `radar.range_from_time(round_trip_time, c)` | seconds | caller's choice | required parameter, no default |

For the same physical round-trip time — one microsecond, i.e. 1000 ns — the three calls diverge
by exactly the precision of `c` each one uses, not by any difference in the underlying formula
(all three compute `R = c·t / 2`):

```python
runtime.execute("lidar", "range_from_tof", [1.0e-6])["result"]
# 150.0 -- default c = 3.0e8

runtime.execute("lidar_mapping", "range_from_time_of_flight", [1000.0])["result"]
# 149.9 -- fixed c = 2.998e8, and the input is nanoseconds, not seconds

runtime.execute("radar", "range_from_time", [1.0e-6, 3.0e8])["result"]
# 150.0 -- same formula, c supplied explicitly since there is no default
```

A caller reading `lidar_mapping`'s number as "the same range `lidar.range_from_tof` would give
for the same instant" is off by 0.1 m at this range purely from `2.998e8` vs `3.0e8` — small at
150 m, but the gap scales linearly with range, and passing seconds instead of nanoseconds into
`lidar_mapping.range_from_time_of_flight` (there is no unit tag on the argument) produces a
number nine orders of magnitude wrong with no error raised.

## `lidar`: survey geometry and return-based metrics

| Function | What it does |
| --- | --- |
| `range_from_tof(time_of_flight, c=3.0e8)` | `c * t / 2`. |
| `point_density(n_points, area)` | `n_points / area`; `0.0` if `area <= 0`. |
| `scan_swath_width(altitude, scan_angle_deg)` | `2 * altitude * tan(scan_angle_deg / 2)` — `scan_angle_deg` is the *full* scan angle, so the function halves it before converting to radians and taking the tangent. |
| `footprint_diameter(altitude, divergence_mrad)` | `altitude * divergence_mrad / 1000`. |
| `pulse_repetition_frequency_to_point_rate(prf, scan_lines_per_sec=1.0, points_per_line=1.0)` | Returns `prf` unchanged. Its own docstring calls this "simplified" — `scan_lines_per_sec` and `points_per_line` are accepted and defaulted but never referenced in the function body. |
| `ground_sampling_distance(altitude, focal_length, pixel_size)` | `altitude * pixel_size / focal_length`; `0.0` if `focal_length <= 0`. |
| `vegetation_index_from_returns(first_returns, last_returns)` | `(first - last) / first * 100`; `0.0` if `first_returns <= 0`. |
| `canopy_height(dsm, dtm)` | `dsm - dtm` — **not clamped**; a DTM point above the matched DSM point returns a negative canopy height. |
| `slope_from_elevation(dz, dx)` | `atan(dz / dx) * 180 / pi`; returns `90.0` (vertical) if `\|dx\| < 1e-15` rather than dividing by zero. |
| `intensity_normalization(intensity, range_val, ref_range)` | `intensity * (range_val / ref_range)^2`; `0.0` if `ref_range <= 0`. |
| `overlap_percentage(swath_width, strip_spacing)` | `(swath_width - strip_spacing) / swath_width * 100`; `0.0` if `swath_width <= 0`. |
| `point_cloud_file_size_mb(n_points, bytes_per_point)` | `n_points * bytes_per_point / 1e6`. |

All twelve values below are pinned exactly (not merely range-checked) in
`tests/mojo/test_wave87.mojo`, so they are load-bearing, reproducible numbers rather than
illustrations:

```python
runtime.execute("lidar", "canopy_height", [120.0, 100.0])["result"]
# 20.0 -- CHM = DSM - DTM

runtime.execute("lidar", "vegetation_index_from_returns", [1000.0, 300.0])["result"]
# 70.0 -- 70% of first returns did not reach a hard last-return target (canopy present)

runtime.execute("lidar", "point_cloud_file_size_mb", [5.0e6, 34.0])["result"]
# 170.0 -- 5M points at 34 bytes/point (XYZ + intensity + classification + GPS time, roughly)

runtime.execute("lidar", "scan_swath_width", [1000.0, 40.0])["result"]
# 727.94... -- 2 * 1000 * tan(20 deg), a 1000 m AGL flight at a 40 deg full scan angle
```

## `lidar_mapping`: terrain-model production and survey QA

| Function | What it does |
| --- | --- |
| `range_from_time_of_flight(time_ns)` | `2.998e8 * time_ns * 1e-9 / 2` — see the range-from-time comparison above for how this differs from `lidar.range_from_tof`. |
| `point_density(n_points, area_m2)` | `n_points / area_m2`; `0.0` if `area_m2 <= 0` — identical formula to `lidar.point_density`, just a renamed second parameter. |
| `canopy_height_model(dsm_elevation, dtm_elevation)` | `dsm_elevation - dtm_elevation`, **clamped to `0.0`** if negative — the opposite edge-case behavior from `lidar.canopy_height`, which returns the raw negative value. |
| `leaf_area_index_from_lidar(gap_fraction, zenith_angle_rad)` | `-cos(zenith_angle_rad) * ln(gap_fraction) / 0.5` (Beer-Lambert, `G ≈ 0.5` for a spherical leaf-angle distribution); `0.0` if `gap_fraction <= 0` or `>= 1`. |
| `ground_filter_threshold(scan_angle_rad, point_spacing)` | `point_spacing * tan(scan_angle_rad)` — a simplified stand-in for the height threshold a progressive-TIN ground filter would use. |
| `beam_divergence_footprint(range_m, beam_divergence_mrad)` | `range_m * beam_divergence_mrad * 1e-3` — same small-angle footprint formula as `lidar.footprint_diameter`, with the arguments swapped in order (range first here, altitude first there) and renamed. |
| `pulse_return_intensity(reflectance, range_m, system_constant)` | `system_constant * reflectance / range_m^2`; `0.0` if `range_m <= 0`. |
| `scan_line_spacing(altitude, scan_rate, flight_speed)` | `flight_speed / scan_rate`; `0.0` if `scan_rate <= 0`. `altitude` is accepted — the docstring says so explicitly ("unused in simplified model") — but never appears in the function body. |
| `vertical_accuracy(z_lidar, z_check)` | `z_lidar - z_check` — despite the function's name, this returns the **raw signed residual** for one point, not an accuracy statistic; the docstring calls it exactly that ("Point-wise vertical error: residual"). A caller wanting an actual accuracy figure (e.g. RMSE) has to square, average, and root this across a set of check points itself. |
| `surface_roughness_lidar(mean_residual, n_points)` | `sqrt(mean_residual)`; `0.0` if `mean_residual < 0`. `n_points` is accepted and documented ("RMS of plane fit residuals... approximated from mean_residual") but does not appear anywhere in the arithmetic — the caller is expected to have already divided the sum of squared residuals by `n_points` before calling this. |

None of `lidar_mapping`'s ten functions are pinned by a hand-verified wave suite (see
Verification below), so the worked examples here were computed independently in plain Python
against the module's own formulas, not copied from a test file:

```python
runtime.execute("lidar_mapping", "leaf_area_index_from_lidar", [0.5, 0.0])["result"]
# 1.3862943611198906 -- nadir-look (zenith=0) LAI from a 50% gap fraction:
# -cos(0)*ln(0.5)/0.5 = 0.6931471805599453/0.5

runtime.execute("lidar_mapping", "canopy_height_model", [95.0, 100.0])["result"]
# 0.0 -- DTM above DSM at this point is clamped to zero canopy height

runtime.execute("lidar", "canopy_height", [95.0, 100.0])["result"]
# -5.0 -- the sibling function in `lidar` returns the same inputs' negative result unclamped

runtime.execute("lidar_mapping", "surface_roughness_lidar", [0.04, 500.0])["result"]
# 0.2 -- sqrt(0.04); the 500.0 for n_points changes nothing about this call's output
```

## `radar`: range, Doppler, and link-budget equations

| Function | What it does |
| --- | --- |
| `radar_range_equation(pt, gt, gr, wavelength, sigma, noise_factor, bandwidth, snr_min)` | `pt*gt*gr*wavelength^2*sigma / (snr_min*noise_factor*bandwidth)`. Its own module docstring labels this a "Simplified R⁴ computation" — it is **not** the classical `Rmax = [Pt·Gt·Gr·λ²·σ / ((4π)³·Pmin·SNRmin)]^(1/4)`: there is no `(4π)³` term, `Pmin` is replaced by the product `noise_factor * bandwidth`, and the result is never raised to the `1/4` power, so the return value is a dimensionless intermediate factor, not a range in meters. |
| `doppler_frequency(velocity, wavelength)` | `2 * velocity / wavelength`. |
| `doppler_velocity(fd, wavelength)` | `fd * wavelength / 2`. |
| `range_from_time(round_trip_time, c)` | `c * round_trip_time / 2` — `c` is required here, unlike `lidar.range_from_tof`'s defaulted `c`. |
| `pulse_repetition_interval(prf)` | `1 / prf`. |
| `max_unambiguous_range(prf, c)` | `c / (2 * prf)`. |
| `max_unambiguous_velocity(prf, wavelength)` | `prf * wavelength / 4`. |
| `range_resolution(bandwidth)` | `C_LIGHT / (2 * bandwidth)`, where `C_LIGHT = 3.0e8` is a module-level constant, **not a parameter** — unlike `range_from_time` and `max_unambiguous_range` a few lines above it in the same file, which both take `c` explicitly. |
| `antenna_gain_from_area(aperture_area, wavelength)` | `4 * pi * aperture_area / wavelength^2`. |
| `radar_cross_section_sphere(radius)` | `pi * radius^2` — the optical-region RCS of a large conducting sphere. |
| `noise_power(bandwidth, noise_figure, temperature)` | `K_BOLTZMANN * temperature * bandwidth * noise_figure`, with `K_BOLTZMANN = 1.38e-23` likewise hardcoded rather than passed in. |
| `signal_to_clutter(signal_power, clutter_power)` | `signal_power / clutter_power`. |

Every one of these twelve is pinned exactly in `tests/mojo/test_wave86.mojo`, including a
round-trip consistency check that composes two of them:

```python
runtime.execute("radar", "range_resolution", [1.0e6])["result"]
# 150.0 -- a 1 MHz bandwidth gives 150 m range resolution: C_LIGHT / (2*B)

runtime.execute("radar", "radar_cross_section_sphere", [2.0])["result"]
# 12.566... -- pi * 2^2

runtime.execute("radar", "noise_power", [1.0e6, 4.0, 290.0])["result"]
# 1.6008e-14 -- k*T*B*F at room temperature (290 K), 1 MHz, noise figure 4

runtime.execute("radar", "radar_range_equation",
                [1000.0, 30.0, 30.0, 0.03, 1.0, 4.0, 1.0e6, 10.0])["result"]
# 2.025e-05 -- Pt=1000, Gt=Gr=30, lambda=0.03m, sigma=1 m^2, Fn=4, B=1MHz, SNRmin=10
```

The test file also checks `doppler_velocity(doppler_frequency(150.0, 0.05), 0.05) == 150.0` — a
velocity converted to a Doppler shift and back recovers the original value, since the two
functions are exact algebraic inverses of each other (`fd = 2v/λ` and `v = fd·λ/2`).

## Verification

`mojo/tests/libs/test_lidar.mojo`, `test_lidar_mapping.mojo`, and `test_radar.mojo` are all
auto-generated coverage smoke tests: each calls every function once with the literal argument
`0.5` (or `0.5` repeated for multi-argument functions) and checks only that the `Float64` result
is finite — none of the three pins a specific numeric output.

Real, hand-worked numeric assertions exist for two of the three modules, in the wave-suite files
instead: `tests/mojo/test_wave87.mojo` ("Wave 87 — Distillation, LiDAR, Archaeology") pins all
twelve `lidar` functions across 26 assertions, and `tests/mojo/test_wave86.mojo` ("Wave 86 —
Paper Science, Radar, Veterinary") pins all twelve `radar` functions, including the Doppler
round-trip check above. `lidar_mapping` has no equivalent wave-suite coverage anywhere in
`tests/mojo/` — grepping the whole directory for `lidar_mapping` turns up only its own
auto-generated smoke test — so every worked example for that module on this page was computed
independently in plain Python against the formulas read directly out of
`mojo/engine/lidar_mapping.mojo`, not copied from a pinned assertion.

`gitbook/engine/nutrition-and-veterinary-science-kernels.md` also references
`tests/mojo/test_wave86.mojo` by name, since that file's third module is `veterinary`. That page
documents `veterinary`'s own functions and does not describe any `radar` function — the two pages
draw worked examples from the same wave file without duplicating each other's coverage.

**Next:** see [Nutrition and veterinary science kernels](nutrition-and-veterinary-science-kernels.md)
for the other two modules pinned in `test_wave86.mojo`/`test_wave87.mojo`, or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
