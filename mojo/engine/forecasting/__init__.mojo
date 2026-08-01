"""
forecasting — evaluation-first time-series forecasting. Zero Python imports.

What this package is
--------------------
The tree already forecasts. `series`, `timeseries_stats`, `arima`, `state_space_models`,
`kalman`, `time_series_decompose` and `interpolate` hold naive/drift/SMA/SES/Holt/AR
point forecasts, an ACF/PACF/ADF battery, additive decomposition and a Kalman filter.
Every one of them is frozen and every number this package returns comes out of one of
them or out of `stats`, `risk`, `sorting` and `determinism`.

What the tree did NOT hold is the part that decides whether a forecast is worth anything:

  * a ROLLING-ORIGIN BACKTEST. `series.forecast_accuracy(actual, predicted)` scores a
    forecast against actuals the caller supplies, and nothing stops those actuals being
    the very points the model was fitted to. A forecast evaluated on its own training data
    is not evidence, and no status in the tree said so. `forecasting.backtest` runs the fit
    and the forecast separately per origin, over expanding or sliding windows, and returns
    the PER-ORIGIN errors rather than only their mean — a single averaged error hides which
    origins failed, and the origin that failed is usually the recent one.

  * ETS and THETA point forecasts (`forecasting.point`), built on the frozen
    `timeseries_stats.holt_linear`, `series.exponential_forecast`, `series._ols_fit` and
    `time_series_decompose`.

  * INTERMITTENT demand (`forecasting.intermittent`) — Croston, SBA, SBJ and the
    Syntetos-Boylan demand classification, for series where most periods are zero and the
    ordinary error measures mislead.

  * HIERARCHICAL RECONCILIATION (`forecasting.hierarchy`) — child forecasts that must sum
    to their parent, with the coherence residual measured and reported rather than
    rescaled away.

  * PREDICTION INTERVALS from backtest residuals (`forecasting.interval`), seeded through
    `determinism/counter_rng` so a band reproduces bit-for-bit.

`forecasting.contract` is the package's single vocabulary: the status codes 300-319, the
one definition of "finite", the one tolerance builder, the one empirical quantile, and the
ceilings. Nothing in this package carries a second copy of any of those (rule 3 applies
inside a package too).

The four Rule-4 absences this family is about
---------------------------------------------
1. *A horizon longer than the data can support has no answer.* `fc_horizon_defect` refuses
   `horizon > n_obs`: you cannot forecast further ahead than the record reaches back, and
   you certainly cannot backtest it. The frozen kernels happily extrapolate a 5-point
   series 500 steps; that is a number where none exists.

2. *An error measure that divides by an actual of ZERO is undefined at that point.* MAPE on
   intermittent demand is the canonical case. This package reports the measure ABSENT and
   COUNTS the undefined points, because the count is the only thing that tells a caller the
   measure was inapplicable rather than merely small. The frozen
   `series.forecast_accuracy` instead skips those points and still divides by the FULL
   length, which silently understates MAPE by the zero fraction; the suite asserts that
   exact relationship, so the difference is documented rather than discovered.

3. *A backtest with fewer complete origins than the configuration asks for must say how
   many it actually ran.* `BacktestReport` carries `n_origins_requested` and
   `n_origins_run` separately, plus `n_origins_refused`, because a forecaster can decline
   an origin (a seasonal method inside its first period, Croston in a window with no
   positive demand) and a mean over the survivors is a different statistic from the one
   requested.

4. *Reconciliation that cannot make children sum to their parent within tolerance reports
   the residual.* It does not rescale silently, and it does not split a parent equally
   among children whose own forecasts are all zero — that is an invented answer.

Determinism
-----------
Nothing here calls `random_float64` or `seed(`. The only sampled surface is
`forecasting.interval`'s bootstrap band, which draws through
`determinism.sampling_keyed.bootstrap_keyed` over `determinism.counter_rng`'s counter-based
generator: a draw is a pure function of its coordinates, so the same `(seed, stream, step)`
gives the same band whatever ran before it, on any machine. `IntervalBand` carries
`rng_version()` back so a stored band names the generator that produced it. A band that
changed between runs could not be used in a decision that has to be explained, which is
the whole premise.

Status codes
------------
This package owns 300-319 and uses no other range. `forecasting.contract.fc_status_name`
is the ONE vocabulary; there is no per-file status table (rule 4e — `optimization.integer`
and `optimization.explain` both claimed 80-84 and one integer acquired two meanings).

Modules
-------
  contract     — status codes, ceilings, tolerances, guards, the empirical quantile
  point        — ETS(A,N,N) / ETS(A,A,N) damped / ETS(A,A,A), Theta, checked AR, deseasonalise
  fitted       — Holt/Damped/ETS(A,A,A) with FITTED smoothing parameters and initial
                 state (the closed-form 2x2 initial-state solve plus the reference
                 Nelder-Mead), closing the measured M4 fixed-init defect
  select       — per-series selection and inverse-MAE combination over {SES, Damped, Theta}
  backtest     — rolling-origin backtest and the honest error measures
  intermittent — Croston / SBA / SBJ and demand classification
  hierarchy    — bottom-up and top-down reconciliation, plus a coherence audit
  interval     — empirical and seeded-bootstrap prediction bands, plus coverage
"""
