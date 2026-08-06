"""
esrnn.global_residual — an ES-RNN-CLASS additive residual-correction stage over the
frozen Holt/Damped/Theta point-forecast backbone (`forecasting.fitted`). Zero Python
imports.

Why this module exists, in one measured sentence
--------------------------------------------------
The M4 statistical pool's GBDT meta-learner over ten point-forecast candidates
plateaued at 0.843 Total OWA; a per-series oracle over that SAME pool caps at 0.6663 —
the wall is method-class capacity, not selection quality. What the pool does not
contain is Smyl's actual ES-RNN insight (2020, the M4 winner): a SINGLE shared neural
model, trained ACROSS the whole corpus, that learns to correct a classical
exponential-smoothing backbone's per-step residual as a function of the series' own
recent, per-series-normalised history. This module is the nearest defensible reduction
of that idea buildable from what this tree already has: the frozen fitted-forecast
drivers as the deterministic backbone, and the frozen sequence trainer
(`seq_training.bptt_train_lstm`) as the shared corrector — no GPU, no external ML
framework, no per-series fitting of the corrector.

Backbone selection (`esrnn_select_backbone` / `esrnn_backbone_forecast`)
-------------------------------------------------------------------------
Three frozen drivers are already shipped for exactly this per-series choice: `holt_fitted`,
`damped_fitted`, `theta_fitted`. `esrnn_select_backbone` fits all three on ONE series and
returns the lowest-`insample_mae` survivor (ties, or an entirely refused set, resolved
holt < damped < theta — declaration order, matching `forecasting.select`'s own tie rule).
`esrnn_backbone_forecast` fits exactly one NAMED method, with no selection — the caller
uses it to reapply THE SAME chosen method at a second truncation point (see below), which
is a second call to an unmodified frozen driver, not a second implementation of one.

The leak-free training signal (caller's responsibility; this module supplies the arithmetic)
-----------------------------------------------------------------------------------------------
The corrector is trained on the residual the backbone makes on the TRAINING series' own
held-back tail — the identical `u = n - horizon` / fit-on-prefix / score-on-suffix split
`forecasting.pool` established and this module's own suite exercises structurally. No
function here takes a test-window argument, so a caller has nothing to leak even by
mistake: `esrnn_residual` and `esrnn_apply_correction` are pure elementwise arithmetic
over two already-computed value lists, refusing (empty output) rather than silently
truncating on any length mismatch.

Per-series-adaptive input, GLOBALLY shared weights
----------------------------------------------------
The real ES-RNN insight is TRAINING ONE MODEL ACROSS EVERY SERIES while still adapting its
INPUT per series — exactly what `seq_training.bptt_train_lstm` already does once its
windows are built correctly: pool windows from many different series into one
`x_flat`/`y` call and the trainer fits ONE shared weight vector over all of them. This
module supplies the per-series-adaptive half of that input: `esrnn_window_scale` computes
a LOCAL scale (mean absolute value) from a single already-sliced window so two series a
thousand-fold apart in magnitude present comparable inputs to the shared model, and
`esrnn_scaled_window` divides that window by its own scale and appends one extra
pseudo-timestep encoding WHICH future step is being predicted (`step / horizon`, a
fraction in `(0, 1]`) — the multi-horizon reduction that lets the trainer's existing
single-scalar output head (`bptt_train_lstm` predicts one `Float64` per window) predict
every step of a multi-step horizon without any change to its signature: one window per
`(series, horizon step)` pair, all pooled into the same global training call.

Refusal, not a crash, on a bad shape
-------------------------------------
Every function here that receives caller-supplied parallel lists checks their lengths
match BEFORE indexing either — `esrnn_residual`/`esrnn_apply_correction` refuse (return an
EMPTY list) on a mismatch rather than iterating `min(len(a), len(b))`, which would silently
drop the tail of whichever list is longer instead of surfacing the caller's defect. No
function in this module takes a separate `Int` element count paired with a `List` it
indexes with that count — the abort class documented in `mojo_capability_manifest.py`
("a kernel that takes an explicit element count and trusts it can read past the end of a
`List`, an UNCATCHABLE bounds assertion that kills the whole worker process") has no
foothold here: `horizon` bounds only the OUTPUT this module allocates (`dim`, like
`holt_fitted`'s own declaration), never an index into a caller-supplied list, and every
other list-shaped input is consumed by its own `len()`, never by a second, separately
supplied count.

Status codes 300-319 via `forecasting.contract`; no table here.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64, int64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_esrnn_global_residual.mojo
benchmark: none
docs: none
version_introduced: 0.10.0
deprecation_state: active
@endcapability
"""
from std.math import abs as fabs

from forecasting.contract import (
    FC_ERR_ALL_UNDEFINED,
    FC_ERR_METHOD,
    FC_OK,
    fc_finite,
    fc_status_name,
)
from forecasting.fitted import damped_fitted, holt_fitted, theta_fitted

# The backbone-local method vocabulary. Order IS the tie-break order in
# `esrnn_select_backbone` (declaration order, first-fitted-wins on an exact tie), the
# same convention `forecasting.pool`'s candidate list and `forecasting.select` both use.
comptime ESRNN_METHOD_HOLT: Int = 0
comptime ESRNN_METHOD_DAMPED: Int = 1
comptime ESRNN_METHOD_THETA: Int = 2
comptime ESRNN_N_METHODS: Int = 3


def esrnn_method_name(method_id: Int) -> String:
    """The backbone-local method vocabulary, one place. Unknown ids are loud, never blank.

    @capability esrnn_method_name
    complexity: O(1)
    counts: none
    @endcapability
    """
    if method_id == ESRNN_METHOD_HOLT:
        return "holt"
    if method_id == ESRNN_METHOD_DAMPED:
        return "damped"
    if method_id == ESRNN_METHOD_THETA:
        return "theta"
    return "unknown_method"


@fieldwise_init
struct BackboneFit(Copyable, Movable):
    """One backbone point-forecast: which method, its path, and the statistic that
    picked it (or that a caller can use to reapply the SAME method elsewhere).

    `values` holds steps 1..horizon on the series' OWN scale (deseasonalised, if the
    caller passed a deseasonalised series — this module reseasonalises nothing, exactly
    like the frozen drivers it calls); EMPTY on any refusal (`has_forecast` is the
    authority). `method_id` is `-1` on a total refusal (`esrnn_select_backbone` when no
    candidate fit) and the fitted method's id from `esrnn_backbone_forecast`'s own
    argument otherwise, win or refuse — so a caller can always see WHICH method it asked
    for even when that method itself refused.
    """

    var status: Int
    var method_id: Int
    var has_forecast: Bool
    var values: List[Float64]
    var insample_mae: Float64
    var status_name: String


def _no_backbone(status: Int, method_id: Int) -> BackboneFit:
    """A refusal: no path, no statistic, the method id preserved for the caller's audit."""
    return BackboneFit(status, method_id, False, List[Float64](), -1.0, fc_status_name(status))


def esrnn_backbone_forecast(
    y: List[Float64], method_id: Int, horizon: Int
) -> BackboneFit:
    """Fit exactly ONE named backbone method on `y`; no selection.

    `method_id` must be one of `ESRNN_METHOD_HOLT`/`_DAMPED`/`_THETA`; anything else
    refuses with `FC_ERR_METHOD` before any fit runs. This is the call a caller uses to
    reapply the SAME method `esrnn_select_backbone` chose at one truncation of a series
    to a SECOND truncation (typically the full series, after the choice was made on the
    training-held-back prefix) — two calls to the unmodified frozen driver, never a
    second implementation of one.

    @capability esrnn_backbone_forecast
    complexity: O(n) -- one frozen fitted-driver call
    counts:
    - dim horizon [kernel_validated]
    - dim method_id <= 2 [kernel_validated]
    @endcapability
    """
    if method_id == ESRNN_METHOD_HOLT:
        var f = holt_fitted(y, horizon)
        return BackboneFit(
            f.status, ESRNN_METHOD_HOLT, f.has_forecast, f.values.copy(),
            f.insample_mae, fc_status_name(f.status),
        )
    if method_id == ESRNN_METHOD_DAMPED:
        var f2 = damped_fitted(y, horizon)
        return BackboneFit(
            f2.status, ESRNN_METHOD_DAMPED, f2.has_forecast, f2.values.copy(),
            f2.insample_mae, fc_status_name(f2.status),
        )
    if method_id == ESRNN_METHOD_THETA:
        var f3 = theta_fitted(y, horizon)
        return BackboneFit(
            f3.status, ESRNN_METHOD_THETA, f3.has_forecast, f3.values.copy(),
            f3.insample_mae, fc_status_name(f3.status),
        )
    return _no_backbone(FC_ERR_METHOD, method_id)


def esrnn_select_backbone(y: List[Float64], horizon: Int) -> BackboneFit:
    """Fit Holt, Damped and Theta on the SAME `y`; return the lowest-`insample_mae`
    survivor among the ones that produced a forecast.

    Ties (equal `insample_mae`, including the all-refused case) resolve holt < damped <
    theta by construction: each later candidate only replaces the incumbent on a STRICT
    improvement (`<`, never `<=`). `FC_ERR_ALL_UNDEFINED` with `method_id = -1` when none
    of the three fit — a selection among nothing is not a naive fallback.

    @capability esrnn_select_backbone
    complexity: O(n) -- three frozen fitted-driver calls
    counts:
    - dim horizon [kernel_validated]
    @endcapability
    """
    var h = holt_fitted(y, horizon)
    var d = damped_fitted(y, horizon)
    var t = theta_fitted(y, horizon)

    var best_id = -1
    var best_mae = 0.0
    if h.status == FC_OK and h.has_forecast and fc_finite(h.insample_mae) and h.insample_mae >= 0.0:
        best_id = ESRNN_METHOD_HOLT
        best_mae = h.insample_mae
    if d.status == FC_OK and d.has_forecast and fc_finite(d.insample_mae) and d.insample_mae >= 0.0:
        if best_id == -1 or d.insample_mae < best_mae:
            best_id = ESRNN_METHOD_DAMPED
            best_mae = d.insample_mae
    if t.status == FC_OK and t.has_forecast and fc_finite(t.insample_mae) and t.insample_mae >= 0.0:
        if best_id == -1 or t.insample_mae < best_mae:
            best_id = ESRNN_METHOD_THETA
            best_mae = t.insample_mae

    if best_id == ESRNN_METHOD_HOLT:
        return BackboneFit(FC_OK, best_id, True, h.values.copy(), best_mae, fc_status_name(FC_OK))
    if best_id == ESRNN_METHOD_DAMPED:
        return BackboneFit(FC_OK, best_id, True, d.values.copy(), best_mae, fc_status_name(FC_OK))
    if best_id == ESRNN_METHOD_THETA:
        return BackboneFit(FC_OK, best_id, True, t.values.copy(), best_mae, fc_status_name(FC_OK))
    return _no_backbone(FC_ERR_ALL_UNDEFINED, -1)


def esrnn_window_scale(window: List[Float64]) -> Float64:
    """Mean absolute value of an already-sliced window; `0.0` on an empty window.

    The per-series normaliser that lets a single GLOBALLY-shared model see comparable
    inputs from series a thousand-fold apart in magnitude — the same role Smyl (2020)
    assigns a per-series level normalisation before the shared RNN, done here with the
    window's own recent history rather than a whole-series statistic, so training-time and
    inference-time windows are normalised the same way (both are "the most recent
    `lookback` values before the forecast origin", whichever origin the caller sliced).

    @capability esrnn_window_scale
    complexity: O(len(window))
    counts: none
    @endcapability
    """
    var n = len(window)
    if n == 0:
        return 0.0
    var s = 0.0
    for i in range(n):
        s += fabs(window[i])
    return s / Float64(n)


def esrnn_scaled_window(
    window: List[Float64], scale: Float64, step_frac: Float64
) -> List[Float64]:
    """`[window[i] / scale for i in window] + [step_frac]` — the corrector's raw input.

    Appending `step_frac` (the fraction `step / horizon` of the horizon step being
    predicted, caller-computed) as one extra pseudo-timestep is the multi-horizon
    reduction: `seq_training.bptt_train_lstm`'s trained head predicts a single scalar per
    window, so ONE window per `(series, horizon step)` pair — differing only in this last
    entry — lets the SAME shared model predict every step of a multi-step horizon with no
    change to the trainer's signature. Refuses (empty) when `scale` is non-finite or not
    strictly positive — a window that never varied has nothing to normalise by, and
    dividing by zero or a negative scale would silently invert or blow up every input.

    @capability esrnn_scaled_window
    complexity: O(len(window))
    counts: none
    @endcapability
    """
    var out = List[Float64]()
    if not fc_finite(scale) or scale <= 0.0 or not fc_finite(step_frac):
        return out^
    var n = len(window)
    out = List[Float64](capacity=n + 1)
    for i in range(n):
        out.append(window[i] / scale)
    out.append(step_frac)
    return out^


def esrnn_residual(actual: List[Float64], forecast: List[Float64]) -> List[Float64]:
    """`actual[i] - forecast[i]` elementwise; refuses (empty) on a length mismatch or any
    non-finite input rather than iterating `min(len(actual), len(forecast))`, which would
    silently drop the tail of whichever list ran longer instead of surfacing the caller's
    shape defect.

    @capability esrnn_residual
    complexity: O(len(actual))
    counts: none
    @endcapability
    """
    var out = List[Float64]()
    var n = len(actual)
    if n != len(forecast):
        return out^
    out = List[Float64](capacity=n)
    for i in range(n):
        var a = actual[i]
        var f = forecast[i]
        if not fc_finite(a) or not fc_finite(f):
            return List[Float64]()
        out.append(a - f)
    return out^


def esrnn_apply_correction(
    backbone: List[Float64], residual_hat: List[Float64]
) -> List[Float64]:
    """`backbone[i] + residual_hat[i]` elementwise — the shipped, corrected forecast.
    Refuses (empty) on a length mismatch or any non-finite input, the same discipline as
    `esrnn_residual`: a shape defect here must be visible, not silently truncated.

    @capability esrnn_apply_correction
    complexity: O(len(backbone))
    counts: none
    @endcapability
    """
    var out = List[Float64]()
    var n = len(backbone)
    if n != len(residual_hat):
        return out^
    out = List[Float64](capacity=n)
    for i in range(n):
        var b = backbone[i]
        var r = residual_hat[i]
        if not fc_finite(b) or not fc_finite(r):
            return List[Float64]()
        out.append(b + r)
    return out^
