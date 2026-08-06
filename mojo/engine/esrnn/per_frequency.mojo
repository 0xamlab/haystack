"""
esrnn.per_frequency — a LINEAR-class additive residual corrector over the frozen
Holt/Damped/Theta backbone, fit independently PER FREQUENCY, over the IDENTICAL
per-series-adaptive window feature `esrnn.global_residual` already supplies. Zero Python
imports.

Why this module exists, in one measured sentence
--------------------------------------------------
PR #487's GLOBAL corrector (one `seq_training.bptt_train_lstm` model per M4 frequency)
measured 0.9768 Total OWA against a 0.8786 backbone-alone baseline — a regression on
every frequency but Quarterly. A leak-free diagnosis of that shipped result, reconstructing
the EXACT shipped feature (`esrnn_window_scale` + `esrnn_scaled_window`) against the true
test-period target, found the LSTM corrector converges to ~0% in-sample R² — a genuine,
converged plateau across a 5-point hyperparameter sweep, not under-training — while a
trivial 8-parameter linear probe on the IDENTICAL feature recovers 1-15% R² depending on
frequency (10-15% for Weekly/Hourly). That gap — real, linearly-exploitable structure the
shipped trainer never reaches — is this module's target: the SAME per-frequency, six-
independent-models structure PR #487 already has (one frequency's own series pooled into
one fit, never mixed with another frequency's), but with the corrector itself replaced by
`regression.ridge_regression` / `regression.predict` — frozen, already-shipped multi-
predictor linear regression — in place of the LSTM that fails to reach even a linear
model's own ceiling on this same feature.

What this module supplies vs. reuses
---------------------------------------
Backbone selection, window construction and scaling, and the residual/correction
arithmetic are ALL `esrnn.global_residual`'s existing, unmodified functions — this module
adds nothing there. `regression.ridge_regression` and `regression.predict` are ALSO
reused unmodified — this module is the two-function composition between them:
`esrnn_fit_frequency_corrector` names the "fit one linear corrector over an already-
pooled window matrix" step (the LINEAR analogue of PR #487's single
`bptt_train_lstm` call), and `esrnn_apply_linear_correction` composes
`regression.predict` with `esrnn.global_residual.esrnn_apply_correction` so a caller
gets a corrected forecast in one call instead of two, rather than re-adding the predicted
residual to the backbone by hand at every call site.

Per-frequency, not per-series, not cross-frequency — the caller's pooling, unchanged
----------------------------------------------------------------------------------------
Neither function here knows what a "series" or a "frequency" is: `esrnn_fit_frequency_corrector`
takes whatever rows a caller already pooled into `X`/`y` (one row per `(series, horizon
step)` pair, matching `esrnn_scaled_window`'s own shape) and fits ONE linear model over
them. A driver that pools only ONE frequency's series into that call reproduces PR #487's
"six independent models, one per frequency" structure with a linear model class instead
of an LSTM; nothing in this module would stop a caller from pooling differently, exactly
like `esrnn.global_residual`'s own primitives take no position on pooling grain either.

Refusal, not a crash, on a bad shape
-------------------------------------
`esrnn_fit_frequency_corrector` refuses with an EMPTY `RegressionResult` (`coefficients`
and `residuals` both empty, `r_squared = 0.0`) on an empty pool or a length mismatch
between `X` and `y` — the SAME empty-result convention `regression.ridge_regression`,
`ols_multiple` and `ols_simple` already use for their own `n == 0` case (`RegressionResult`
carries no separate status field; a caller checks `len(coefficients) == 0`, exactly as it
already must for any of `regression`'s own fitting functions). This function adds the ONE
check those functions do not make on their own — `len(X) != len(y)` — rather than letting
`ridge_regression` iterate whichever list is shorter. `esrnn_apply_linear_correction`
refuses (empty) whenever `esrnn_apply_correction` itself would — a length mismatch between
`backbone` and the predicted residual, or any non-finite value in either — because it is
that same call, never a second, looser implementation of the same arithmetic.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_esrnn_per_frequency.mojo
benchmark: none
docs: none
version_introduced: 0.10.0
deprecation_state: active
@endcapability
"""
from esrnn.global_residual import esrnn_apply_correction
from regression import RegressionResult, predict, ridge_regression


def esrnn_fit_frequency_corrector(
    X: List[List[Float64]], y: List[Float64], alpha: Float64 = 1.0
) -> RegressionResult:
    """Fit ONE ridge-regression corrector over an already-pooled window matrix `X` (one
    row per `(series, horizon step)` pair, e.g. every row `esrnn_scaled_window` produced
    for a single frequency) against its target `y` — the LINEAR analogue of PR #487's
    single per-frequency `bptt_train_lstm` call. `alpha` is `regression.ridge_regression`'s
    own L2 penalty, passed through unchanged; this function adds no numerics of its own.

    Refuses with an empty `RegressionResult` (`coefficients` and `residuals` both empty,
    `r_squared = 0.0` — the same empty-result convention `ridge_regression` itself already
    uses for `len(X) == 0`) on an empty pool, and the same refusal when `len(X) != len(y)`
    — `ridge_regression` has no such check and would otherwise iterate whichever list is
    shorter.

    @capability esrnn_fit_frequency_corrector
    complexity: O(len(X) * p^2) -- one frozen ridge_regression call, p = feature width
    counts: none
    @endcapability
    """
    if len(X) == 0 or len(y) == 0:
        return RegressionResult(List[Float64](), 0.0, 0.0, List[Float64]())
    if len(X) != len(y):
        return RegressionResult(List[Float64](), 0.0, 0.0, List[Float64]())
    return ridge_regression(X, y, alpha)


def esrnn_apply_linear_correction(
    backbone: List[Float64], X: List[List[Float64]], coefficients: List[Float64], intercept: Float64
) -> List[Float64]:
    """`backbone[i] + (X[i] . coefficients + intercept)` for every `i` — the shipped,
    linearly-corrected forecast. Call-only: predicts the residual with
    `regression.predict` (unmodified), then hands the result to
    `esrnn.global_residual.esrnn_apply_correction` — the identical elementwise add (and
    identical non-finite/length-mismatch refusal) every corrector in this package already
    uses, never a second, separately-written addition.

    @capability esrnn_apply_linear_correction
    complexity: O(len(backbone) * p) -- one frozen predict call, p = feature width
    counts: none
    @endcapability
    """
    var residual_hat = predict(X, coefficients, intercept)
    return esrnn_apply_correction(backbone, residual_hat)
