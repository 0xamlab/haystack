---
icon: battery-three-quarters
description: Track an asset whose performance decays with usage age — a two-state filter with wear clamping, load correction and a cliff term for the non-linear end of life.
---

# Asset degradation state

`degradation_state` estimates how an asset's performance is decaying as it accumulates usage, from noisy
observations arriving one at a time. Battery capacity against charge cycles, tool accuracy against
runtime, pump throughput against hours, print quality against page count — the shape is the same: a
level, a slope against usage age, and a non-linear collapse near end of life.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# two-state filter: [level, slope-per-unit-age]
state = runtime.execute("degradation_state", "pace_state_init", [100.0, 0.0])["result"]

# observe a measurement of 99.2 at usage age 12
state = runtime.execute(
    "degradation_state", "pace_kalman_update", [state, 99.2, 12.0, 0.25, 0.01]
)["result"]

runtime.execute("degradation_state", "pace_predict", [state, 30.0])["result"]  # project to age 30
```

## Functions

| Function | What it does |
|---|---|
| `pace_state_init(level, slope)` | Initialise the two-state filter `[level, slope-per-unit-age]`. |
| `pace_kalman_update(state, obs, age, obs_noise, proc_noise)` | One filtered observation. Handles irregular arrival — no fixed sampling interval assumed. |
| `pace_kalman_run(...)` | Run a whole observation series through the filter. |
| `pace_predict(state, age)` | Project performance to a future usage age. |
| `pace_reset_for_compound(state)` | Reset after the asset is replaced or serviced — usage age returns to zero. |
| `pace_offset_stderr(...)` / `pace_slope_stderr(...)` | Standard errors, so the estimate carries its own uncertainty. |
| `wear_clamp(slope)` / `wear_clamp_bounds()` | Clamp the fitted decay slope to a physically possible range. |
| `load_corrected_rate(observed, remaining_load, effect)` | Remove a depleting-load effect so the residual reflects wear rather than a lightening asset. |
| `sample_is_usable(flags)` | Reject observations taken under conditions that do not reflect steady-state performance. |

## Why the slope needs clamping

Fit a decay slope on noisy data over a short window and it frequently comes out **negative** — the asset
appears to improve with use. A planner that trusts it will happily schedule an infinitely long service
interval. `wear_clamp` bounds the slope to what is physically possible, so an unlucky window produces a
conservative estimate instead of an impossible one.

## Load correction, and the sign that catches people

If the asset gets lighter, emptier or cooler as it is used, raw observations conflate that improvement
with wear, and the fitted slope is biased toward zero or negative. `load_corrected_rate` removes it.

The sign convention is worth stating explicitly because getting it backwards is silent: the function
**removes** the benefit to recover the wear signal, so a generator producing synthetic observations must
**add** it back. Reverse that and every measurement still looks plausible while the model has the asset
improving as it depletes.

## The cliff

Linear decay under-describes most real assets. Performance holds roughly flat, then falls away sharply
past a threshold. A purely linear fit averages the flat phase with the collapse and describes neither —
and it will systematically underestimate the value of servicing, because the payoff is concentrated
entirely in the part of the curve the line smooths away. Model the knee explicitly, and fit the threshold
rather than assuming it.

## Verification

The filter is checked against irregular observation intervals, which is where a fixed-`dt` shortcut
diverges. Clamping is asserted at both bounds, and the load-correction sign is pinned by a test so the
generator and the estimator cannot drift apart.

**Next:** decide *when* to service with [contest strategy](contest-strategy.md), or filter richer state
with [Kalman and state-space models](runtime-library-catalog.md).
