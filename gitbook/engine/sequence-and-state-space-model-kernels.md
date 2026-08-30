---
icon: repeat
description: A 2-layer LSTM training loop with full BPTT and Adam, the per-element linear recurrence math behind Mamba/S4/RetNet-style state-space models, and the scalar heuristics a stateful agent runtime scores session and long-term memory with.
---

# Sequence and state-space model kernels

Three modules grouped by one theme — carrying state forward across steps — that otherwise have
little to do with each other. `seq2_trainer` is a complete, production training loop for a fixed
2-layer LSTM regressor: mini-batch Adam, full backpropagation-through-time, dropout, gradient
clipping, and early stopping with best-validation-weight restore. `state_space_models` is the
per-element arithmetic behind linear state-space sequence models — Mamba's selective scan, S4's
convolution kernel, RetNet's decay, HiPPO's coefficient update — a fundamentally different
mathematical object from the classical hidden Markov model in [`ml.hmm`](ml-hmm.md): a continuous
hidden state updated by a linear recurrence, not a finite set of discrete states updated by a
transition matrix. `stateful_runtime` is ten independent scalar formulas (memory relevance, decay,
consolidation, replay priority, compression ratio, replayability) for the bookkeeping an agent
runtime does around a conversation's session and long-term memory — it holds no state itself and
defines no session struct; it is a scoring layer a caller composes on top of whatever state it
already tracks.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

D, H, Dh = 2, 3, 2
runtime.execute("seq2_trainer", "seq2_weight_count", [D, H, Dh])["result"]
# 167 -- 4H(D+H+1) + 4H(2H+1) + Dh(H+2) + 1 for the fixed LSTM -> LSTM -> Dense(relu) -> Dense(1)

flat = [0.0] * 167
flat[-1] = 0.7                              # d2_b: the last weight in the export layout
params = runtime.execute("seq2_trainer", "seq2_from_flat", [flat, D, H, Dh])["result"]

x = [0.3 * i - 0.5 for i in range(6)]       # 1 sequence, seq_len 3, input_dim 2
runtime.execute("seq2_trainer", "seq2_forward", [params, x, 1, 3, 2])["result"]
# [0.7] -- every weight but the output bias is zero, so both LSTM layers and the
# relu dense layer collapse to zero and the network just returns its own bias
```

## The modules

| Module | What it does |
| --- | --- |
| `seq2_trainer` | mini-batch Adam + full BPTT trainer for a fixed 2-layer LSTM -> LSTM -> Dense(relu) -> Dense(1) regressor, with inverted dropout, global-norm gradient clipping, early stopping with best-validation restore, and a flat weight export/import a Python caller can reshape into keras conventions |
| `state_space_models` | the per-element recurrence math behind linear state-space sequence models — ZOH discretization, the linear scan `h = Āh + B̄x`, Mamba's selective (input-dependent) variant, S4's convolution kernel, HiPPO-LegT's coefficient update, and RetNet's exponential decay |
| `stateful_runtime` | ten scalar scoring formulas for agent session/long-term memory bookkeeping — relevance, decay, consolidation, replay priority, compression ratio, replayability, working-memory pressure, session continuity |

## `seq2_trainer`: a 2-layer LSTM trained end to end

The architecture is fixed, not configurable: `LSTM(H) -> LSTM(H) -> Dense(Dh, relu) -> Dense(1)`,
gates `i, f, g, o` with sigmoid/sigmoid/tanh/sigmoid activations, `c = f*c_prev + i*g`,
`h = o*tanh(c)` — the same cell math as [`seq_nn`](ml-sequence-cells.md), and `seq2_init` calls
`seq_nn.xavier_flat` directly for every weight block rather than re-deriving Xavier init. Where it
differs from the single-layer trainer in [`seq_training`](ml-sequence-training.md) is architecture
depth and production features: a second LSTM layer, a relu dense head, inverted dropout on both the
inter-layer hidden sequence and the dense activation, mini-batching, early stopping, and parallel
gradient accumulation across workers. `seq2_trainer` is the module to reach for when replacing a
real keras/CPU-TF training loop over dense multi-feature sequences (lookback ~18-22 steps, ~8-12
features, hidden ~32); `seq_training` stays the smaller single-layer/single-feature case.

Every parameter lives in one of ten flat blocks (`l1_wx`, `l1_wh`, `l1_b`, `l2_wx`, `l2_wh`, `l2_b`,
`d1_w`, `d1_b`, `d2_w`, `d2_b`), each row-major with the four LSTM gate rows stacked `i, f, g, o` —
keras's own gate order. `seq2_export`/`seq2_from_flat` are exact inverses, and the module docstring
gives the numpy reshape recipe a Python caller uses to turn the flat blocks into keras's
`kernel`/`recurrent_kernel`/`bias` tensors directly (e.g. `kernel_1 = flat[l1_wx].reshape(4*H,
D).T`).

### The dense head, worked by hand

`test_seq2_trainer.mojo` pins the head wiring against hand-computed values on an all-zero-weight
network with `input_dim=2, hidden=3, dense_h=2` (matching `seq2_weight_count(2, 3, 2) == 167`
above):

```python
# all weights zero except: d2_b = 0.1; d1_b = 1.0 and d2_w = 2.0 on both dense-hidden units
flat = [0.0] * 167
flat[162], flat[163] = 1.0, 1.0   # d1_b (2 elements, offset 162)
flat[164], flat[165] = 2.0, 2.0   # d2_w (2 elements, offset 164)
flat[166] = 0.1                  # d2_b (offset 166, the last weight)
params = runtime.execute("seq2_trainer", "seq2_from_flat", [flat, D, H, Dh])["result"]
runtime.execute("seq2_trainer", "seq2_forward", [params, x, 1, 3, 2])["result"]
# [4.1] -- both LSTM layers still output exactly zero (zero recurrent/input weights),
# so the dense-hidden pre-activation is just d1_b = 1.0; relu(1.0) = 1.0;
# y = d2_b + 2 * (1.0 + 1.0) = 0.1 + 4.0 = 4.1
```

Flip `d1_b` to `-1.0` instead and the test gets exactly `0.1` back — relu clamps the negative
pre-activation to zero before the output weights ever see it, so the dense-hidden contribution
vanishes and only the output bias survives. Both numbers are lifted directly from
`test_seq2_trainer.mojo`, not invented.

### Determinism, parallel workers, and early stopping

Per epoch: a seeded Fisher-Yates shuffle, then per mini-batch a forward + full BPTT pass over the
batch split into contiguous per-worker chunks (`parallelize`), a mean-MSE gradient, a global-L2-norm
clip at `5.0`, and a locally implemented bias-corrected Adam step (`beta1=0.9`, `beta2=0.999`,
`eps=1e-8`) — zero Python anywhere in the loop. Per-worker gradient accumulators are summed in fixed
worker order, so a run is bit-identical to another run with the same seed and worker count; only the
floating-point summation order (and so the last few ulps) can differ **between** worker counts.
Dropout masks are derived from `(seed, epoch, sample-index)`, independent of shuffle order and
worker partitioning, so the same sample gets the same mask regardless of which worker processes it
or in what batch order. `seq2_train_workers` exposes the worker count explicitly (`1` is fully
single-threaded); `seq2_train` picks it from `info.num_physical_cores()`; `seq2_train_scalar` is a
non-SIMD single-thread build kept as the benchmark baseline. The module docstring reports 8 workers
at ~8.1x over single-threaded scalar BPTT on a realistic slice (2000 sequences, seq_len 22,
input_dim 11, hidden 32, batch 64) — see `mojo/tests/bench_seq2_trainer.mojo`.

When `n_val > 0`, clean (no-dropout) validation MSE is recorded every epoch, the best-validation
weights are snapshotted, and training stops once `patience` consecutive epochs pass without a new
best — the returned `Seq2TrainResult.params` are the **restored** best-validation weights, not the
final ones. `test_seq2_trainer.mojo` confirms this with an independent recomputation:
`seq2_loss(eres.params, vx, vy, 8, 5, 2)` reproduces `eres.val_loss[eres.best_epoch]` to `1e-12`,
i.e. the weights actually returned are the ones that produced that recorded loss, not merely close
to it. The same test file confirms the BPTT gradient (`seq2_grad`) matches central finite
differences on the full 2-layer stack to a worst-case relative error under `1e-6`.

## `state_space_models`: linear recurrence, not a hidden Markov chain

Every function here is a single element of the classic SSM recurrence
`h_t = Āh_{t-1} + B̄x_t`, `y_t = Ch_t`, worked one scalar at a time rather than as matrices — the
caller loops over state dimensions and timesteps itself. `ssm_discretize_zoh(a, delta)` computes the
exact zero-order-hold discretization `Ā = exp(Δ·A)`; `ssm_discretize_b(a, b, delta)` computes the
matching exact `B̄ = (Ā - 1)/A · B` (falling back to the first-order `Δ·B` only when `a == 0`, where
the exact form divides by zero); `ssm_recurrence_step` and `ssm_output_step` are the two lines of
the recurrence itself.

`mamba_selective_scan_step` is a distinct discretization, not a call to the two functions above —
it recomputes `Ā = exp(Δ·A)` (same exact form) but takes `B̄ = Δ·B` as a first-order approximation
unconditionally, which is the real simplification Mamba's paper makes (only `A`'s discretization
needs to be exact; `Δ`, `B` and `C` are already input-dependent per token). At a modest step size
the two disagree by more than rounding:

```python
# a = -1.0, delta = 0.5, b = 2.0, x = 1.0, h_prev = 0.0
runtime.execute("state_space_models", "ssm_discretize_zoh", [-1.0, 0.5])["result"]
# 0.6065306597126334 -- exact A-bar, shared by both paths

runtime.execute("state_space_models", "ssm_discretize_b", [-1.0, 2.0, 0.5])["result"]
# 0.7869386805747332 -- exact ZOH B-bar: (A-bar - 1)/A * b
runtime.execute("state_space_models", "ssm_recurrence_step", [0.0, 0.6065306597126334, 0.7869386805747332, 1.0])["result"]
# 0.7869386805747332 -- h_1 via the exact path

runtime.execute("state_space_models", "mamba_selective_scan_step", [0.0, -1.0, 2.0, 1.0, 0.5])["result"]
# 1.0 -- h_1 via Mamba's Euler-approximated B-bar = delta * b = 1.0 exactly
```

{% hint style="info" %}
**~27% apart at this step size, not a rounding difference.** `0.7869...` vs `1.0` is the real cost
of Mamba's first-order `B̄` approximation at `Δ = 0.5` — it only converges to the exact ZOH value as
`Δ -> 0`. Calling `mamba_selective_scan_step` and expecting it to agree with
`ssm_discretize_b` + `ssm_recurrence_step` to machine precision would be checking the wrong oracle.
{% endhint %}

`mamba_delta_softplus(delta_raw)` is `log(1 + exp(delta_raw))` — the activation that keeps Mamba's
per-token `Δ` positive (`softplus(0.0) = 0.6931471805599453`, `softplus(1.0) = 1.3132616875182228`).
`s4_kernel_element(c, a_power, b)` is one lag of S4's convolution kernel `K_l = C·A^l·B`, a single
multiply the caller sums over `l` itself: with `A^2 = exp(-1.0) = 0.36787944117144233` (`Ā` from
above, squared — the same `exp(delta*a)` composes exactly), `s4_kernel_element(1.0, 0.36787944117144233,
2.0) = 0.7357588823428847`. `ssm_shift_register_step(state, decay, input_val)` is the simplest
possible exponential-decay update, `decay*state + input`, with no discretization step at all.
`retnet_decay(dim, n_dims)` computes RetNet's per-dimension decay `γ_d = 1 - exp(-5 - 8d/D)`
(attributed to Sun et al. 2023 in the source docstring): `retnet_decay(0, 8) = 0.9932620530009145`
for the slowest-decaying dimension and `retnet_decay(7, 8) = 0.9999938557876467` for the fastest —
both close to 1, RetNet's decay factors by design.

`hippo_legt_update(h_n, h_prev_n, x, n, t)` updates one HiPPO-LegT coefficient — but note that
`h_prev_n` is accepted and never read in the formula (`h_n - a_nn*h_n + a_nn*x` where
`a_nn = (2n+1)/t`); the docstring itself calls this "a simplified recurrence," and with
`n=0, t=2.0, h_n=0.3, x=1.0` the result is `0.65` regardless of what `h_prev_n` is passed. A full
HiPPO-LegT update mixes every lower-order coefficient through a skew-symmetric matrix; this
per-element kernel updates coefficient `n` from its own current value only.

None of the functions above train anything — there is no gradient, no fitting loop, and no discrete
state count anywhere in this module, which is the real distinction from
[`ml.hmm`](ml-hmm.md): `hmm` models a **finite** set of discrete hidden states with a learned
row-stochastic transition matrix and trains that matrix with Baum-Welch; `state_space_models`
models a **continuous**-valued hidden state advanced by a linear recurrence with parameters the
caller already has (from a trained Mamba/S4 checkpoint, typically), and supplies no training path
of its own.

## `stateful_runtime`: scoring heuristics, not a session store

All ten functions are independent scalars — `structs: []` in the runtime contract, no `SessionState`
or `MemoryStore` type anywhere in the module. A caller passes in whatever numbers it already tracks
(an embedding dot product, an access count, an elapsed step count) and gets back one score; nothing
here allocates, retrieves, or persists memory itself. That is a deliberate contrast with the actual
persistent state elsewhere in this engine: the KV cache `llmk.generate` grows
(`kv_cache_append_flat`, see [LLM inference kernels](llm-inference-kernels.md)) and the KV cache and
per-layer weights that persist across calls on a Metal decode session (see
[Metal LLM decode](qwen3-metal-decode.md)) are real state containers with real memory behind them;
`stateful_runtime`'s functions are the scoring layer a caller builds a memory-management *policy*
on top of, not the state itself.

A few of the ten worth walking through for their edge-case behavior:

```python
# session_memory_relevance: embedding_sim * recency_weight * log(1 + access_count)
runtime.execute("stateful_runtime", "session_memory_relevance", [0.8, 0.6, 0.9, 4.0])["result"]
# 0.6952771781715313
runtime.execute("stateful_runtime", "session_memory_relevance", [-0.5, 0.5, 0.9, 4.0])["result"]
# 0.0 -- a negative similarity (opposite-direction embeddings) is clamped to 0, never
# allowed to go negative and cancel out a more relevant memory in a summed ranking

# state_transition_validity: in-bounds AND the mask bit, not either alone
runtime.execute("stateful_runtime", "state_transition_validity", [2.0, 5.0, 5.0, 1.0])["result"]
# 0.0 -- to_state (5) is out of range for n_states=5 (valid indices 0..4), so the
# mask bit of 1.0 saying "this transition is allowed" is never even consulted

# replay_buffer_priority: |td_error|^alpha, hard-capped
runtime.execute("stateful_runtime", "replay_buffer_priority", [100.0, 1.0, 5.0])["result"]
# 5.0 -- proportional priority (alpha=1) would be ~100; max_priority caps it

# state_compression_ratio: refuses to divide by zero
runtime.execute("stateful_runtime", "state_compression_ratio", [1000000.0, 0.0])["result"]
# 1.0 -- a reported compressed size of 0 is treated as "no compression achieved"
# (ratio 1.0), never a divide-by-zero infinity
```

`memory_consolidation_score` (`importance*frequency*(1+pressure) - 1.0`) is a genuine sign test —
positive means "move to long-term," and doubling capacity pressure alone doesn't guarantee crossing
zero if importance or frequency are low. `working_memory_capacity_used` caps at `1.0` and returns
`1.0` outright (not an error) when `reserved_output_tokens >= context_window`, so a context budget
that has already been fully claimed by reserved output reads as "completely full" rather than a
divide-by-zero or negative fraction. `replayability_score` and `session_continuity_score` are both
weighted blends (`0.5 + 0.5*rng_seed_fixed`, `0.5*overlap_ratio + 0.5*context_coverage`) rather than
products, so an experience that is only *partly* replayable or continuous still reports a nonzero
score, weighted down rather than gated to zero.

## Verification

`seq2_trainer` has real, hand-verified assertions in `test_seq2_trainer.mojo`: the weight-count
formula, the exact dense-head wiring values above, a full-stack BPTT gradient check against central
finite differences (worst relative error under `1e-6` across all 167 weights on a 4-sequence
dataset), an export/import round trip, a 32-sequence memorization/overfit run (final loss under
`5e-3` and under `2%` of its initial value), early-stopping best-weight restoration, and
determinism checks for both single-thread and fixed-worker-count parallel runs.

`test_state_space_models.mojo` and `test_stateful_runtime.mojo` are auto-generated smoke tests: each
one calls every public function once with fixed placeholder arguments (mostly `0.5`) and only
asserts the result is finite (not NaN or infinite) — there are no pinned numeric assertions in
either file, and no cross-check against an independent implementation. Every specific number in the
two sections above (`0.7869386805747332`, the `~27%` Mamba-vs-exact-ZOH gap, `0.9932620530009145`,
the `state_transition_validity`/`replay_buffer_priority`/`state_compression_ratio` edge cases, and
all ten `stateful_runtime` examples) was computed independently in this page directly from the
module's own formulas in `mojo/engine/state_space_models.mojo` and
`mojo/engine/stateful_runtime.mojo`, not lifted from a test oracle — because for these two modules,
no such oracle exists yet in the test suite.

**Next:** see the LSTM/GRU cell math `seq2_trainer` builds on in
[LSTM and GRU cells](ml-sequence-cells.md), the single-layer trainer it extends in
[LSTM sequence training](ml-sequence-training.md), or the discrete-state alternative in
[Hidden Markov models](ml-hmm.md).
