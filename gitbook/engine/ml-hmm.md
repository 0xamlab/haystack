---
icon: diagram-project
description: Hidden Markov models — forward/backward likelihood, Viterbi decoding and Baum-Welch training.
---

# Hidden Markov models

`hmm` adds hidden-state sequence modeling with training — zero Python
imports — replacing hmmlearn (`MultinomialHMM`) and pomegranate discrete
HMMs. It fills the engine's HMM gap: `markov` covers observed chains only;
this kernel adds hidden states with discrete emissions — log-space
forward/backward inference, Viterbi decoding, and Baum–Welch (EM)
parameter estimation.

## The modules

| Module | What it does |
| --- | --- |
| `hmm` | discrete-emission hidden Markov models in pure Mojo — log-space forward/backward likelihood, Viterbi decoding, and Baum–Welch (EM) training — replacing hmmlearn's `MultinomialHMM` and pomegranate discrete HMMs |

## Functions

| Function | What it does |
|---|---|
| `hmm_forward(obs, a, b, pi)` | Log-space forward pass: `log_alpha` (T × n_states) with `log_alpha[t][i] = log P(o_0..o_t, x_t = i)`, plus `loglik = log P(O)`. |
| `hmm_backward(obs, a, b, pi)` | Log-space backward pass: `log_beta[t][i] = log P(o_{t+1}..o_{T-1} \| x_t = i)`; the last row is all zeros (log 1). |
| `hmm_viterbi(obs, a, b, pi)` | Most likely hidden state path (log-space DP with backpointers); exact ties break toward the lower state index. |
| `hmm_baum_welch(obs, n_states, n_symbols, max_iter, seed)` | Baum–Welch (EM) training from a seeded random init → `HMMModel(a, b, pi, loglik_history)`, using Rabiner-scaled forward–backward recursions (linear space, no underflow on long sequences). |

Conventions: `a[i][j] = P(state i → state j)` and
`b[i][k] = P(symbol k \| state i)` are row-stochastic matrices;
`pi[i] = P(initial state i)`; observations are symbol indices in
`[0, n_symbols)`.

## Guarantees

- **Deterministic for a given seed.** Training initializes from a seeded
  xorshift64 RNG; the tests confirm two runs with seed 7 produce identical
  `loglik_history` entry for entry, and degenerate inputs (empty obs,
  non-positive dims, out-of-range symbols) return the seeded initial model
  with an empty history instead of aborting.
- **Monotone EM.** `loglik_history` has `max_iter + 1` entries (entry 0 =
  random init) and is monotone non-decreasing — verified over 30
  iterations within 1e-9, with the final value strictly improving on the
  random init.
- **Valid distributions out.** Trained `a`/`b` rows and `pi` sum to 1
  (verified to 1e-9 after 30 EM updates).
- **Accurate logs.** `std.math` log/exp in this toolchain are ~1e-10
  approximations — too coarse for log-likelihoods that gate decisions —
  so the kernel ships its own `_ln`/`_exp` (exact frexp/ldexp range
  reduction, ~1 ulp).

## Verification

The tests pin the recursions to hand-computed values against
correctly-rounded ln references: the 3-step forward pass on a
2-state/2-symbol model matches `ln(0.152544) = -1.8803021999597218`
within 1e-9, with every `log_alpha` cell exact to 1e-12; backward cells
(`ln(0.58)`, `ln(0.55)`, `ln(0.2364)`, `ln(0.252)`) match to 1e-12; and
`log_alpha[t][i] + log_beta[t][i]` reproduces the known joint
probabilities at every t. Viterbi recovers the classic weather-model path
`[Sunny, Rainy, Rainy]` (best-path probability 0.01344) and tie-breaks an
all-equal model to state 0. On 10 repeats of `[0,0,0,1,1,1]` (T = 60),
Baum–Welch's final scaled log-likelihood agrees with `hmm_forward` on the
trained model to 1e-9, and an all-equal observation sequence drives the
log-likelihood to 0 (probability → 1) within 1e-6 while staying monotone.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
