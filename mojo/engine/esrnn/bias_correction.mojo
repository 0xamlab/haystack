"""
esrnn.bias_correction — the simplest possible non-zero residual correction over the
frozen Holt/Damped/Theta backbone: a single scalar additive bias (no LSTM, no per-series
window, no shared weights) equal to the MEAN of the backbone's own training-holdout
residual. Zero Python imports.

Why this module exists, in one measured sentence
--------------------------------------------------
`esrnn.global_residual` + `seq_training.bptt_train_lstm` shipped a per-frequency SHARED
LSTM corrector (#487) that measured 0.9768 Total OWA on all 100,000 M4 series — WORSE
than the 0.8786 backbone-alone baseline on every frequency but Quarterly. Diagnosis (see
the PR trailer for the full numeric trail) found the LSTM converges to ~0% in-sample R2
in every frequency (a real optimizer/feature-reduction plateau, not under-training — a
5-point hyperparameter sweep already ruled that out) — i.e. the trained corrector is
already CLOSE to a constant equal to its own training-tail residual mean, and that mean
is measurably backward relative to the true future test period's mean residual for 4 of
6 frequencies. This module builds and measures the constant itself, directly, with no
LSTM in the loop at all: if the plain mean-residual bias ALSO fails to beat 0.8786, that
is a different, honestly-reportable finding ("a training-tail-derived constant does not
transfer to the true future period") from "our LSTM is bad" — the two are not the same
claim and this module is what lets a caller measure the first without the second's
confound.

Two granularities, one arithmetic primitive
----------------------------------------------
`esrnn_bias_mean` computes the mean of ANY caller-pooled residual list — a caller decides
the pool: every residual from every series in a frequency (the FREQUENCY-level bias, one
scalar shared across the whole frequency, the direct analogue of #487's one-model-per-
frequency granularity) or just one series' own residuals (the SERIES-level bias, as noisy
as that series' own horizon is short, but adaptive per series with no shared weights at
all). Both are the SAME function; only what the caller pools differs. `esrnn_apply_bias`
broadcasts that one scalar across an entire forecast row — the whole "correction" is one
add per output element, deliberately with no capacity to react to horizon step, series
history, or anything else a caller did not already fold into the residual pool.

Reuse, not reimplementation
-------------------------------
Building the training-holdout residual itself reuses `esrnn.global_residual`'s own
`esrnn_residual` (the caller assembles the two same-length value lists — actual
training-tail observations and the backbone's holdout-period forecast — and this
module's neighbour does the elementwise subtract and non-finite refusal); this file adds
only the two functions that are genuinely new: reducing a residual list to one number,
and broadcasting one number back onto a forecast. Backbone selection, backbone
refitting, and the residual sign convention are unchanged from `global_residual` and are
not called a second time by anything here.

Refusal, not a crash, on a bad shape
-------------------------------------
`esrnn_apply_bias` refuses (empty list) on a non-finite bias or any non-finite backbone
element, the same discipline `esrnn_apply_correction` already established — a defect here
must be visible to the caller, never silently absorbed as a zero correction dressed up as
success. `esrnn_bias_mean` cannot refuse in the same way (a scalar has no "empty"); a
non-finite element anywhere in its input, or an empty input, returns `0.0` — the neutral,
correction-is-a-no-op value — rather than propagating a NaN into every forecast this bias
would otherwise touch.

No new status codes; @capability-module below documents the two functions directly.

@capability-module
deterministic: true
stateful: false
batch_capable: true
stream_capable: false
seed_requirements: none
supported_dtypes: float64
backend: mojo
surfaces: library_execute, batch_execute
golden_vectors: mojo/tests/libs/test_esrnn_bias_correction.mojo
benchmark: none
docs: none
version_introduced: 0.10.0
deprecation_state: active
@endcapability
"""
from forecasting.contract import fc_finite


fn esrnn_bias_mean(residuals: List[Float64]) -> Float64:
    """The mean of a caller-pooled residual list — the entire "training" step of a
    bias-only corrector. `0.0` (a neutral, correction-is-a-no-op value) on an empty list
    or on ANY non-finite element, rather than propagating an average that a single bad
    input could have poisoned into every forecast this bias will later touch.

    @capability esrnn_bias_mean
    complexity: O(len(residuals))
    counts: none
    @endcapability
    """
    var n = len(residuals)
    if n == 0:
        return 0.0
    var s = 0.0
    for i in range(n):
        var r = residuals[i]
        if not fc_finite(r):
            return 0.0
        s += r
    return s / Float64(n)


fn esrnn_apply_bias(backbone: List[Float64], bias: Float64) -> List[Float64]:
    """`backbone[i] + bias` for every `i` — the shipped, bias-corrected forecast.
    Refuses (empty) when `bias` is non-finite or any `backbone` element is non-finite,
    the same discipline `esrnn_apply_correction` uses for its per-element correction: a
    shape/value defect here must be visible to the caller, never silently absorbed as a
    zero correction dressed up as success.

    @capability esrnn_apply_bias
    complexity: O(len(backbone))
    counts: none
    @endcapability
    """
    var out = List[Float64]()
    if not fc_finite(bias):
        return out^
    var n = len(backbone)
    out = List[Float64](capacity=n)
    for i in range(n):
        var b = backbone[i]
        if not fc_finite(b):
            return List[Float64]()
        out.append(b + bias)
    return out^
