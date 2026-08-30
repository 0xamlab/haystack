---
icon: arrows-split-up-and-left
description: Preference-optimization losses for RLHF/DPO alignment, diffusion noise schedules and denoising steps, InfoNCE-style contrastive losses, one-sample-at-a-time online learning updates, and Pareto/TOPSIS multi-objective scoring, across five independent kernel modules.
---

# RLHF and generative training kernels

Five small, self-contained modules for training-time math that does not reduce to a single
cross-entropy loss over labeled examples: the preference-optimization objectives behind RLHF-style
LLM alignment (DPO, IPO, ORPO, PPO, GRPO), the noise schedules and denoising steps that drive
diffusion models, the label-free losses used to train encoders by pulling together and pushing
apart pairs of embeddings (InfoNCE, SimCLR, MoCo, BYOL, VICReg, Barlow Twins), the update rules a
model applies one observation at a time when it can never revisit the data (streaming mean/variance,
online SGD, AdaGrad, FTRL-Proximal, concept-drift detection), and the scoring functions used to rank
alternatives against several objectives at once (Pareto dominance, weighted sum, TOPSIS). None of
the five share code with each other or with the single-estimator pages elsewhere in this section —
each is a flat set of `Float64` (or `List[Float64]`) functions with no shared state and no training
loop; the loop lives in the caller, one call per step or per batch.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("rlhf_dpo", "dpo_loss", [2.0, -1.0, 0.1])["result"]
# 0.554355244468527 — chosen log-ratio 2.0, rejected log-ratio -1.0, beta=0.1:
# still more than half a nat of loss even though the policy already prefers the chosen response

runtime.execute("multi_objective", "pareto_front",
                [[[10.0, 5.0], [20.0, 9.0], [25.0, 7.0], [15.0, 6.0]], [False, True]])["result"]
# [0, 1, 3] — four (cost, quality) solutions, cost minimized and quality maximized;
# solution 2 (cost 25, quality 7) is Pareto-dominated by solution 1 (cost 20, quality 9) and drops out
```

## The modules

| Module | What it does |
| --- | --- |
| `rlhf_dpo` | Direct/Identity/ORPO preference-optimization losses, PPO's clipped surrogate objective, GAE and GRPO advantage estimators, a Bradley-Terry reward-model loss, a KL penalty term, token-level SFT cross-entropy, and a margin-based preference hinge loss |
| `diffusion_models` | Linear and cosine noise (beta) schedules, the cumulative alpha_bar recurrence, the forward diffusion sample q(x_t\|x0), the DDPM reverse-process mean and posterior variance, a DDIM step with adjustable stochasticity, signal-to-noise ratio, epsilon-to-x0 conversion, and EDM's sigma-based preconditioning |
| `contrastive_learning` | InfoNCE/NT-Xent loss terms, SimCLR's temperature-scaled cosine similarity, triplet margin loss, MoCo and BYOL/DINO momentum-encoder EMA updates, and the VICReg variance/covariance and Barlow Twins cross-correlation regularizers |
| `online_learning` | EMA and EMA-variance, Welford streaming mean/variance, one-sample-at-a-time SGD/Perceptron/Passive-Aggressive/AdaGrad/FTRL-Proximal updates, and the DDM concept-drift alert signal |
| `multi_objective` | Pareto dominance and front extraction, weighted-sum scoring, min-max objective normalization, ideal/nadir points, and TOPSIS closeness ranking |

## Preference optimization: DPO, IPO, ORPO, PPO and GRPO

`rlhf_dpo.dpo_loss(log_ratio_chosen, log_ratio_rejected, beta)` implements Rafailov et al.'s Direct
Preference Optimization directly from its closed form, `-log σ(β × (log-ratio_chosen -
log-ratio_rejected))`, with no reward model and no RL loop — the two log-ratios are
`log(π(y|x)/π_ref(y|x))` for the preferred and rejected responses, already computed by the caller
from the policy and reference model's own log-probabilities:

```python
runtime.execute("rlhf_dpo", "dpo_loss", [0.5, 0.5, 0.5])["result"]
# 0.6931471805599453 — ln(2): when both responses have the identical log-ratio, the logit
# is exactly 0 and -log(sigmoid(0)) is -log(0.5), independent of beta
```

`ipo_loss` (Azar et al.'s Identity Preference Optimization) replaces DPO's sigmoid with a squared
distance to a target margin `1/(2τ)`, which removes DPO's tendency to push the log-ratio gap to
infinity as training continues:

```python
runtime.execute("rlhf_dpo", "ipo_loss", [2.0, -1.0, 0.5])["result"]
# 4.0 — gap (2.0 - (-1.0)) = 3.0, target margin 1/(2*0.5) = 1.0, squared residual (3.0-1.0)^2
```

`ppo_clip_objective(ratio, advantage, clip_eps)` takes the importance-sampling ratio
`π(a|s)/π_old(a|s)` and returns `min(ratio × A, clip(ratio, 1-ε, 1+ε) × A)`. Which term wins depends
on the sign of the advantage, not just how far the ratio has drifted:

```python
runtime.execute("rlhf_dpo", "ppo_clip_objective", [1.5, 1.0, 0.2])["result"]
# 1.2 — positive advantage: the clipped term (1.2 * 1.0) wins, capping the reward for
# over-committing to an action that was already good

runtime.execute("rlhf_dpo", "ppo_clip_objective", [1.5, -1.0, 0.2])["result"]
# -1.5 — same ratio, negative advantage: the UNCLIPPED term (1.5 * -1.0 = -1.5) wins, because
# min() picks the more pessimistic of the two — PPO's clip only ever caps the optimistic direction
```

`advantage_gae` implements the GAE-λ recurrence `δ = r + γV(s') - V(s)`, `GAE_t = δ + γλ ×
GAE_{t+1}`, computed backward through a trajectory one step at a time by threading `prev_gae`
through successive calls:

```python
g1 = runtime.execute("rlhf_dpo", "advantage_gae", [1.0, 0.5, 0.6, 0.99, 0.95, 0.0])["result"]
g1
# 1.0939999999999999 — delta = 1.0 + 0.99*0.6 - 0.5 = 1.094, plus gamma*lam*0 (first step)

runtime.execute("rlhf_dpo", "advantage_gae", [0.0, 0.6, 0.7, 0.99, 0.95, g1])["result"]
# 1.1219069999999998 — delta = 0.0 + 0.99*0.7 - 0.6 = 0.093, plus 0.99*0.95*1.094
```

`grpo_group_advantage(reward, group_mean, group_std)` is DeepSeek-R1-style GRPO's
group-relative advantage — a plain z-score of one response's reward against the mean and standard
deviation of a group of responses sampled for the same prompt, with no learned value function at
all:

```python
# four sampled responses to the same prompt, rewards [0.8, 0.5, 0.9, 0.3]
# group_mean = 0.625, group_std (population) = 0.23848480035423644
runtime.execute("rlhf_dpo", "grpo_group_advantage", [0.9, 0.625, 0.23848480035423644])["result"]
# 1.15311332039411 — the best-of-four response gets the largest positive advantage
runtime.execute("rlhf_dpo", "grpo_group_advantage", [0.3, 0.625, 0.23848480035423644])["result"]
# -1.3627702877384937 — the worst gets the largest negative one
```

If `group_std <= 0.0` (every sampled response scored identically), `grpo_group_advantage` falls back
to the raw, un-normalized gap `reward - group_mean` rather than dividing by zero.

{% hint style="warning" %}
**`orpo_ratio` refuses instead of computing `log(negative)`.** ORPO's odds-ratio objective needs
`log(1 - p)` for a probability `p = exp(log_prob)`, which only exists for `log_prob <= 0.0` (a valid
log-probability). If either `chosen_log_prob` or `rejected_log_prob` is greater than `0.0` — not a
valid log-probability, and the kind of value a caller passes by mistake if it hands in a raw
probability instead of its log — the function returns `0.0` rather than propagating a NaN or inf
through `log(1 - e^{log_prob})` with `log_prob > 0`:

```python
runtime.execute("rlhf_dpo", "orpo_ratio", [-0.2, -1.0, 10.0, 12.0, 0.1])["result"]
# 0.012120052107208464 — valid inputs

runtime.execute("rlhf_dpo", "orpo_ratio", [0.1, -1.0, 10.0, 12.0, 0.1])["result"]
# 0.0 — chosen_log_prob = 0.1 is not <= 0.0, refused before the log
```
{% endhint %}

`reward_model_score` is the Bradley-Terry pairwise loss `-log σ(r_chosen - r_rejected)` used to
train the reward model itself (as opposed to `dpo_loss`, which trains the policy directly without
one); `kl_penalty_term` is the plain `β × (log π - log π_ref)` penalty subtracted from a reward in
RLHF-with-PPO; `sft_loss_token(log_prob)` is `-log_prob` — ordinary token cross-entropy, exposed here
because the same SFT warm-start loss is threaded through every alignment pipeline in this module;
and `preference_margin_loss(chosen_reward, rejected_reward, margin)` is the hinge
`max(0, margin - (chosen - rejected))`, `0.0` once the reward gap already clears the margin:

```python
runtime.execute("rlhf_dpo", "sft_loss_token", [-0.2231435513142097])["result"]
# 0.2231435513142097 — log(0.8): a token the reference assigned 80% probability costs -log(0.8) nats

runtime.execute("rlhf_dpo", "preference_margin_loss", [0.9, -0.5, 1.0])["result"]
# 0.0 — gap of 1.4 already exceeds the margin of 1.0
```

## Diffusion noise schedules and the reverse process

`linear_beta_schedule` and `cosine_beta_schedule` (Nichol & Dhariwal's Improved DDPM) both return a
noise-schedule value at timestep `t`, but at different levels: linear returns `β_t` directly, cosine
returns the cumulative `ᾱ_t` and clamps to `[0, 1]` before returning:

```python
runtime.execute("diffusion_models", "cosine_beta_schedule", [0.0, 1000.0, 0.008])["result"]
# 1.0    — t=0: no noise added yet
runtime.execute("diffusion_models", "cosine_beta_schedule", [500.0, 1000.0, 0.008])["result"]
# 0.49384359044063775 — halfway through, roughly half the signal remains
runtime.execute("diffusion_models", "cosine_beta_schedule", [1000.0, 1000.0, 0.008])["result"]
# 3.749982237642683e-33 — t=T: essentially pure noise
```

For the linear schedule, `alpha_from_beta(beta, prev_alpha_bar)` folds one step's `β_t` into the
running product `ᾱ_t = ᾱ_{t-1} × (1 - β_t)` — the caller threads the cumulative product through
successive timesteps exactly the way `advantage_gae` above threads `prev_gae`:

```python
# linear_beta_schedule(t, 1000, 0.0001, 0.02) at t = 1..5, folded through alpha_from_beta
# betas:       [0.0001199, 0.0001398, 0.0001597, 0.0001796, 0.0001995]
# alpha_bars:  [0.9998801, 0.99974032, 0.99958066, 0.99940113, 0.99920175]
```

`forward_diffusion_sample(x0, noise, alpha_bar)` is the closed-form single-step sampler
`q(x_t|x_0) = √ᾱ × x0 + √(1-ᾱ) × ε`, and `noise_prediction_to_x0` is its algebraic inverse. Given
the *true* noise that produced `x_t`, the round trip is exact:

```python
xt = runtime.execute("diffusion_models", "forward_diffusion_sample", [2.0, 0.5, 0.9])["result"]
xt
# 2.0554804791094465

runtime.execute("diffusion_models", "noise_prediction_to_x0", [xt, 0.5, 0.9])["result"]
# 2.0 — recovers x0 exactly, because a denoising model that predicted the noise
# perfectly reconstructs the clean sample by definition of how x_t was built
```

In practice the model's `predicted_noise` is an estimate, not the true `ε`, so
`noise_prediction_to_x0` only recovers `x0` exactly in this synthetic case — the function is the
same one step-samplers use to turn a noisy sample plus a noise estimate into an `x0` estimate at
every reverse step.

`ddim_step` (Song et al.'s DDIM) takes an `eta` parameter that interpolates between the fully
deterministic DDIM path (`eta=0`) and DDPM-like stochasticity (`eta=1`), holding everything else
fixed:

```python
runtime.execute("diffusion_models", "ddim_step", [1.5, 0.3, 0.5, 0.55, 0.0])["result"]
# 1.5519734356173385 — eta=0, deterministic
runtime.execute("diffusion_models", "ddim_step", [1.5, 0.3, 0.5, 0.55, 1.0])["result"]
# 1.5327612805074327 — eta=1, same inputs, different step because sigma now eats into dir_xt
```

`snr(alpha_bar)` returns `ᾱ/(1-ᾱ)` — 98.99999999999991 near the start of the forward process
(`ᾱ=0.99`), 1.0 exactly at the midpoint (`ᾱ=0.5`), and `1e9` once `ᾱ >= 1.0` rather than a division
by zero. `edm_preconditioning(sigma, sigma_data)` (Karras et al.'s EDM) returns the `c_skip`
scaling term `σ_data²/(σ²+σ_data²)`: at `σ = σ_data` it is exactly `0.5`
(`edm_preconditioning(0.5, 0.5) == 0.5`), splitting the skip connection evenly between the noisy
input and the model's prediction.

{% hint style="info" %}
**Every denominator that can hit zero returns the input unchanged, not NaN.** `ddpm_reverse_mean`
and `ddim_step` both divide by `sqrt(1 - ᾱ_t)` or `sqrt(ᾱ_t)`; both refuse whenever `alpha_bar_t <=
0.0 or alpha_bar_t >= 1.0` (and `ddim_step` checks `alpha_bar_prev` the same way), returning `x_t`
untouched rather than the `inf`/`NaN` that would otherwise cross the JSON result wire.
`ddpm_posterior_variance` does the same for its own `1 - ᾱ_t` denominator, falling back to
`beta_t` — `ddpm_posterior_variance(0.02, 1.0, 0.99)` returns `0.02`, the bare `β_t`, instead of
dividing by zero.
{% endhint %}

## Contrastive and self-supervised losses

`infonce_loss(positive_score, sum_exp_scores)` is the per-example InfoNCE term
`-log(exp(pos)/Σexp(scores))`, computed from a positive similarity and the sum of `exp(similarity)`
over the positive and every negative — the sum is expected to already include the positive's own
`exp(pos)` term:

```python
# one positive (score 2.0) and three negatives (0.5, 0.3, -1.0)
sum_exp = 10.755515618378224   # exp(2.0) + exp(0.5) + exp(0.3) + exp(-1.0)
runtime.execute("contrastive_learning", "infonce_loss", [2.0, sum_exp])["result"]
# 0.3754187037721044
```

`simclr_positive_score(dot, norm_a, norm_b, temperature)` divides cosine similarity by temperature
in one call; `simclr_temperature_scale(similarity, temperature)` does the second half alone, for a
caller that already has cosine similarity from elsewhere:

```python
runtime.execute("contrastive_learning", "simclr_positive_score", [8.0, 4.0, 2.0, 0.07])["result"]
# 14.285714285714285 — cos(a,b) = 8/(4*2) = 1.0 (identical direction), scaled by 1/0.07
```

`triplet_margin_loss(anchor_pos_dist, anchor_neg_dist, margin)` is `max(0, d(a,p) - d(a,n) +
margin)`: zero once the negative is far enough past the margin, positive otherwise —

```python
runtime.execute("contrastive_learning", "triplet_margin_loss", [0.2, 0.9, 1.0])["result"]
# 0.30000000000000004 — negative only 0.7 farther than the positive; margin of 1.0 not yet cleared
runtime.execute("contrastive_learning", "triplet_margin_loss", [0.2, 1.5, 1.0])["result"]
# 0.0 — negative is 1.3 farther than the positive, clearing the margin
```

`moco_momentum_update` and `byol_ema_update` are the same EMA shape,
`θ_target = m × θ_target + (1-m) × θ_online`, under two names for two papers, at their respective
papers' typical momentum values:

```python
runtime.execute("contrastive_learning", "moco_momentum_update", [1.0, 1.05, 0.999])["result"]
# 1.00005  — MoCo's typical momentum, 0.999: the target barely moves toward the online encoder
runtime.execute("contrastive_learning", "byol_ema_update", [1.0, 1.05, 0.996])["result"]
# 1.0002   — BYOL/DINO's typical decay, 0.996: a slightly larger step at the same online value
```

`vicreg_variance_loss(variance, gamma)` penalizes an embedding dimension whose standard deviation
falls short of a target `γ` (`max(0, γ - std)`, floored at `std = sqrt(variance + 1e-4)` to avoid a
zero-variance singularity); `vicreg_covariance_term` squares the normalized off-diagonal covariance
between two dimensions; and `barlow_twins_cross_corr` computes one element of the batch-normalized
cross-correlation matrix between two encoder branches — all three collapse to `0.0` on a degenerate
input (non-positive batch size or standard deviation) rather than dividing by it.

## Streaming and online learning

`streaming_mean_update` and `streaming_variance_update` are Welford's one-pass algorithm — the
running mean and the M2 accumulator update from a single new observation with no need to revisit
past data. Run four observations through both and the running statistics land exactly on the
textbook population mean and variance computed over the same four numbers directly:

```python
# data = [4.0, 8.0, 6.0, 10.0], processed one at a time
# n=1  mean=4.0  m2=0.0
# n=2  mean=6.0  m2=8.0
# n=3  mean=6.0  m2=8.0
# n=4  mean=7.0  m2=20.0  ->  variance = m2 / n = 5.0

sum([4.0, 8.0, 6.0, 10.0]) / 4          # 7.0  — matches the streaming mean
20.0 / 4                                 # 5.0  — matches m2/n, the population variance
```

`exponential_moving_average`/`exponential_moving_variance` are the EMA analogue — geometrically
decaying weight on the past instead of Welford's equal weight on every sample — and
`concept_drift_ddm_error` implements Gama et al.'s DDM: it adds an error rate to its own standard
deviation, compares that signal against the historical-minimum signal plus a multiple of the
historical minimum's standard deviation, and returns a three-level alert:

```python
# min_error=0.08, min_std=0.02 (min_signal = 0.10); warning_level=2.0, drift_level=3.0
runtime.execute("online_learning", "concept_drift_ddm_error", [0.09, 0.02, 0.08, 0.02, 2.0, 3.0])["result"]
# 0.0 — normal: signal 0.11 is below min_signal + 2*min_std = 0.14
runtime.execute("online_learning", "concept_drift_ddm_error", [0.13, 0.02, 0.08, 0.02, 2.0, 3.0])["result"]
# 1.0 — warning: signal 0.15 clears 0.14 but not min_signal + 3*min_std = 0.16
runtime.execute("online_learning", "concept_drift_ddm_error", [0.20, 0.02, 0.08, 0.02, 2.0, 3.0])["result"]
# 2.0 — drift: signal 0.22 clears 0.16
```

The remaining five functions are one update rule each, all `weight_new = f(weight, gradient-or-loss,
...)`: `river_sgd_update` is plain `w - lr*g`; `perceptron_update` is the classic mistake-driven rule
`w + lr*(y_true - y_pred)*x`; `passive_aggressive_step` returns the PA-I step size `min(C, loss /
||x||²)`, capped at `C` rather than growing unbounded on a large loss; `adagrad_online_update`
accumulates squared gradients into its own per-call `G` and divides the step by `sqrt(G + ε)`; and
`ftrl_step` reconstructs a single FTRL-Proximal weight from `z`/`n` accumulators, returning exactly
`0.0` whenever `|z|` has not yet crossed the L1 threshold `λ1` — the sparsifying dead zone that makes
FTRL-Proximal produce genuinely sparse weights rather than merely small ones:

```python
runtime.execute("online_learning", "ftrl_step", [0.05, 4.0, 0.1, 1.0, 0.1, 1.0])["result"]
# 0.0 — |z|=0.05 does not clear l1=0.1; weight stays exactly zero
runtime.execute("online_learning", "ftrl_step", [0.5, 4.0, 0.1, 1.0, 0.1, 1.0])["result"]
# -0.012903225806451613 — |z|=0.5 clears l1; a nonzero weight is reconstructed
```

## Multi-objective scoring and ranking

`is_dominated(a, b, maximize)` asks whether solution `b` dominates solution `a`: at least as good
on every objective and strictly better on at least one, where `maximize[i]` says whether objective
`i` is maximized or minimized. `pareto_front` runs every pair through it and returns the indices
that survive:

```python
solutions = [[10.0, 5.0], [20.0, 9.0], [25.0, 7.0], [15.0, 6.0]]  # (cost, quality)
maximize = [False, True]   # minimize cost, maximize quality

runtime.execute("multi_objective", "is_dominated", [solutions[2], solutions[1], maximize])["result"]
# True — solution 2 (cost 25, quality 7) is dominated by solution 1 (cost 20, quality 9):
# strictly cheaper AND strictly higher quality

runtime.execute("multi_objective", "pareto_front", [solutions, maximize])["result"]
# [0, 1, 3] — solution 2 drops out; the other three are mutually non-dominated
```

`weighted_score(values, weights)` is a plain dot product with **no** `maximize` argument — a caller
minimizing cost has to pre-negate that objective's weight itself (`weighted_score([10.0, 5.0],
[-0.5, 2.0]) == 5.0`, cost penalized and quality rewarded by the sign the caller chose), unlike
`is_dominated`/`pareto_front`/`ideal_point`/`nadir_point`/`topsis_rank`, which all take the direction
explicitly. `normalize_objectives` min-max scales every column to `[0, 1]` independently of
`maximize` (`solutions` above normalizes to `[[0.0, 0.0], [0.667, 1.0], [1.0, 0.5], [0.333,
0.25]]`); `ideal_point`/`nadir_point` return the best/worst value *per objective* across the whole
set (`ideal_point(solutions, maximize) == [10.0, 9.0]`, `nadir_point(...) == [25.0, 5.0]` — the
ideal point is not itself one of the four solutions, since the cheapest and the highest-quality
solutions are different rows).

`topsis_rank` scores every alternative by closeness to the ideal point relative to the negative-ideal
one, after vector-normalizing and weighting the decision matrix:

```python
runtime.execute("multi_objective", "topsis_rank", [solutions, [0.4, 0.6], maximize])["result"]
# [0.4846292223091632, 0.6257031991959192, 0.31948553442976385, 0.45363702270047623]
# solution 1 (cost 20, quality 9) ranks highest; the Pareto-dominated solution 2 ranks lowest
```

{% hint style="info" %}
**`multi_objective` is not the same module as `optimization.multiobjective`.** The optimization
family documented in [Routing, scheduling & trade-offs](optimization-heuristics.md) has its own,
much larger `optimization.multiobjective` module (14 functions: `nondominated_sort`,
`pareto_certify`, NSGA-II crowding-distance selection, hypervolume against an explicit reference
point, a genetic search, and exact lexicographic optimization) built for the row-major-matrix,
status-coded conventions the rest of that solver family shares. `multi_objective` here is the
smaller, general-purpose decision-analysis toolbox — plain `List[List[Float64]]` in, no status
codes, no search — and the two share no function names or code. Reach for `multi_objective` to rank
or filter a fixed set of already-evaluated alternatives (vendor bids, model checkpoints, sensor
configurations); reach for `optimization.multiobjective` when a Pareto front itself has to be
searched for, certified, or reduced by crowding distance or hypervolume.
{% endhint %}

## Verification

All five `mojo/tests/libs/test_*.mojo` files behind this page (`test_rlhf_dpo.mojo`,
`test_diffusion_models.mojo`, `test_contrastive_learning.mojo`, `test_online_learning.mojo`,
`test_multi_objective.mojo`) are auto-generated coverage smoke tests: each calls a function once on
a shared, arbitrary fixture value (`0.5` for most `Float64` parameters) and checks only that the
result is finite — they do not pin any specific numeric output, so none of the worked numbers above
came from a test assertion. `test_multi_objective.mojo` additionally only exercises 2 of the
module's 7 functions (`is_dominated` and `weighted_score`); `pareto_front`, `normalize_objectives`,
`ideal_point`, `nadir_point` and `topsis_rank` are not called anywhere in the generated suite at all.
Every worked example above was hand-traced against the real formulas in `mojo/engine/rlhf_dpo.mojo`,
`diffusion_models.mojo`, `contrastive_learning.mojo`, `online_learning.mojo` and
`multi_objective.mojo`, and every number given can be reproduced by re-running the same arithmetic
(the Welford streaming example is additionally cross-checked against the textbook population
mean/variance formula computed directly over the same four numbers, above).

**Next:** see the more advanced Pareto/NSGA-II/hypervolume machinery that `multi_objective` above is
deliberately *not* — `optimization.multiobjective` in [Routing, scheduling & trade-offs](optimization-heuristics.md)
— or browse the [Runtime library catalog](runtime-library-catalog.md) for every module and function.
