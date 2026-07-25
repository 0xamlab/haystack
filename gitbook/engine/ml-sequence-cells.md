---
icon: code-branch
description: LSTM and GRU cell forward passes with exact gate math for sequence models.
---

# LSTM and GRU cells

`seq_nn` provides recurrent cells (LSTM/GRU) with exact forward **and**
backward math — zero Python imports. It replaces `torch.nn.LSTMCell` /
`torch.nn.GRUCell` plus their autograd backward for single-step sequence
models, using the standard formulations: LSTM gates i,f,g,o with
`c = f*c_prev + i*g`, `h = o*tanh(c)`; GRU (Cho 2014) with candidate
`n = tanh(W_n x + U_n (r*h_prev) + b_n)`, `h = z*h_prev + (1-z)*n`. It
complements `nn_layers.mojo`, which has dense layers/activations but no
recurrence.

## Functions

| Function | What it does |
|---|---|
| `lstm_cell_forward(x, h_prev, c_prev, W_flat, U_flat, b, hidden)` | One LSTM step -> `LSTMState` (h, c plus gate caches for backward). |
| `lstm_cell_backward(dh, dc, cache, x, h_prev, c_prev, W_flat, U_flat, hidden)` | Exact grads -> `LSTMGrads` (dx, dh_prev, dc_prev, dW, dU, db). |
| `gru_cell_forward(x, h_prev, W_flat, U_flat, b, hidden)` | One GRU step -> `GRUState` (h plus gate caches). |
| `gru_cell_backward(dh, cache, x, h_prev, W_flat, U_flat, hidden)` | Exact grads -> `GRUGrads` (dx, dh_prev, dW, dU, db). |
| `lstm_param_count(input_size, hidden)` | Total LSTM cell parameters: `4*hidden*(input_size + hidden + 1)`. |
| `gru_param_count(input_size, hidden)` | Total GRU cell parameters: `3*hidden*(input_size + hidden + 1)`. |
| `xavier_flat(rows, cols, fan_in, fan_out, seed)` | Seeded Xavier/Glorot-uniform flat row-major matrix; values in ±sqrt(6/(fan_in+fan_out)). |
| `init_lstm_params(input_size, hidden, seed)` | Seeded Xavier W, U; b zero except forget-gate block = 1.0. |
| `init_gru_params(input_size, hidden, seed)` | Seeded Xavier W, U; b zero. |

## Layout, determinism, and failure policy

Parameters are flat row-major with gate blocks stacked i,f,g,o (LSTM) or
r,z,n (GRU): W is [n_gates*hidden x input], U is [n_gates*hidden x
hidden], b has length n_gates*hidden. Initialisation is deterministic —
a seeded xorshift64 RNG means the same seed reproduces bit-identical
parameters and a different seed provably differs (both asserted in the
tests). `init_lstm_params` sets the forget-gate bias block to 1.0, the
standard trick so early training does not forget. Invalid configurations
(hidden <= 0, inconsistent sizes) return empty states/grads rather than
trapping.

## Verification

Forward passes are pinned to independently hand-computed sigmoid/tanh
chains at 1e-12 tolerance: the LSTM known-value case yields
h = 0.20465357159216882, c = 0.4474491587609256 (all four gate
activations checked too); the GRU case yields h = 0.596051095464341.
Every backward output — dW, dU, db, dx, dh_prev, dc_prev — is checked
against central finite differences (eps = 1e-5) on a 3-input/2-hidden
cell with max relative error < 1e-4 required for **every** element
(24 dW + 16 dU + 8 db entries for LSTM; 18 + 12 + 6 for GRU).
Param-count identities are asserted exactly
(`lstm_param_count(3, 2) == 48`, `gru_param_count(3, 2) == 36`), and
`xavier_flat` values are verified to stay within
±sqrt(6/(fan_in+fan_out)).

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
