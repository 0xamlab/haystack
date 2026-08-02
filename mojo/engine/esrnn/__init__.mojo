"""
esrnn — the ES-RNN-CLASS additive residual-correction plane over `forecasting`'s point
forecasters.

`forecasting/` already holds the deterministic backbone (`fitted.holt_fitted`,
`fitted.damped_fitted`, `fitted.theta_fitted`) and the per-series selection/combination
machinery over it (`select`, `pool`). None of that is a per-series-adaptive,
GLOBALLY-shared neural correction of a backbone's residual — Smyl's (2020) ES-RNN
insight, the M4 competition's individual winner. `global_residual` is that missing
composition, additive-only:

  global_residual — backbone selection over Holt/Damped/Theta by in-sample MAE
      (`esrnn_select_backbone`, `esrnn_backbone_forecast`), the per-series-adaptive
      window normalisation and multi-horizon pseudo-timestep encoding that lets
      `seq_training.bptt_train_lstm`'s single-scalar head predict a whole horizon
      (`esrnn_window_scale`, `esrnn_scaled_window`), and the residual/correction
      arithmetic that composes a backbone forecast with the corrector's prediction
      (`esrnn_residual`, `esrnn_apply_correction`).

  bias_correction — the simplest possible non-zero correction over the SAME backbone:
      a single scalar additive bias equal to the mean training-holdout residual, no
      shared weights and no LSTM at all (`esrnn_bias_mean`, `esrnn_apply_bias`). Built to
      measure, in isolation, whether `global_residual`'s measured regression (0.9768 vs
      the 0.8786 backbone-alone baseline) is a corrector-capacity problem or a residual-
      transfer problem — a claim the LSTM's own confounds cannot isolate by itself.

Frozen kernels are called, never reimplemented: every backbone number is
`forecasting.fitted`'s own fit, and the shared corrector this package's functions feed is
`seq_training`'s own trainer — this package supplies the composition between them, not a
second copy of either.
"""
