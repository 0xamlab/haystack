---
icon: arrows-rotate
description: Full BPTT training loop for LSTM regressors, gradient-checked against finite differences.
---

# LSTM sequence training (BPTT)

`seq_training` is a complete sequence-model training loop — sliding
windows, full backpropagation-through-time, MSE loss, global-norm
gradient clipping, and a locally implemented Adam optimizer — with zero
Python imports. It replaces torch/keras LSTM training loops (`nn.LSTM` +
Adam + `clip_grad_norm_`) for small univariate/low-dimensional sequence
forecasting, and is fully deterministic given the seed.

## Functions

| Function | What it does |
|---|---|
| `make_windows(series, lookback, forward)` | Series -> `WindowedDataset` of sliding lookback windows plus forward-step targets (n − lookback − forward + 1 windows). |
| `lstm_weight_count(input_dim, hidden)` | Flat weight-vector length for a 1-layer LSTM + linear head: `4*(H*D + H*H + H) + H + 1`. |
| `bptt_train_lstm(x_flat, y, input_dim, hidden, epochs, lr, seed, clip_norm)` | Full-batch BPTT training -> `TrainResult` (flat weights + one mean MSE per epoch). |
| `lstm_predict(weights, window, input_dim, hidden)` | Run trained flat weights over one window -> scalar forecast. |

## Training guarantees

Per epoch: forward + full BPTT on every window, gradients averaged,
global-L2-norm clipped to `clip_norm` (<= 0 disables clipping), then a
bias-corrected Adam update (beta1 = 0.9, beta2 = 0.999, eps = 1e-8)
implemented locally. Weights are seeded uniform in ±0.5/sqrt(hidden)
with the forget-gate bias initialised to 1.0. `loss_history[e]` is the
mean MSE measured at the start of epoch e, before that epoch's update.
`epochs <= 0` returns the seeded initial weights with empty history;
invalid shapes return an empty result, and `lstm_predict` returns 0.0 on
invalid input. The tests assert bit-identical weights and loss history
for the same seed, and a different init for a different seed.

## Verification

Forward reference values in the tests were computed with an independent
scalar Python implementation of the same equations: `lstm_predict`
case B gives 0.46339948438905243 (1 step) and 0.49815726481608846
(2 steps); the recurrent case C gives 0.17925881009843325 — all matched
at 1e-12. The first bias-corrected Adam step is −lr·sign(grad) per
weight, and the tests confirm every step's sign matches a central
finite-difference gradient of the MSE computed independently through
`lstm_predict`. The flagship convergence test (0.5·sin series,
lookback 8, 200 epochs, lr 0.02, seed 42, clip 5.0) requires final loss
< 0.25 × initial loss and > 70% sign agreement between predictions and
targets, and the epoch-0 training loss must match an independent
`lstm_predict`-based MSE to 1e-9.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
