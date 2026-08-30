---
icon: scale-balanced
description: Trainable soft-margin SVM classifier via simplified SMO with linear and RBF kernels.
---

# Trainable SVM classifier (simplified SMO)

`svm_solver` trains soft-margin SVM classifiers in pure Mojo — replacing
`sklearn.svm.SVC` / `LinearSVC` fit + predict with zero Python imports.
The solver is simplified sequential minimal optimization (Platt) with the
random second-choice heuristic, driven by a seeded deterministic
xorshift64 RNG. Labels must be in {−1.0, +1.0}; X is a flat row-major
matrix. It complements `svm_kernel.mojo` (kernel functions only) but is
fully self-contained.

## The modules

| Module | What it does |
| --- | --- |
| `svm_solver` | Trains soft-margin SVM classifiers (linear or RBF kernel) via simplified SMO and predicts labels from the fitted model — fit, decision function, and single/batch predict. |

## Functions

| Function | What it does |
|---|---|
| `svm_fit_linear(X, y, n_features, C, tol, max_passes, seed)` | Train a soft-margin linear SVM via simplified SMO; returns an `SVMModel` with dual alphas, bias `b`, and primal weights `w` (decision = `w·x + b`). |
| `svm_fit_rbf(X, y, n_features, C, tol, max_passes, gamma, seed)` | Train an RBF-kernel SVM (`K = exp(−γ‖a−b‖²)`); the model keeps support vectors and their `α·y` coefficients. |
| `svm_decision(model, x)` | Raw decision value `f(x) = Σ αᵢyᵢK(xᵢ,x) + b` — a single dot product for linear models. |
| `svm_predict(model, x)` | Class label: +1.0 if the decision value ≥ 0, else −1.0. |
| `svm_predict_batch(model, X)` | One label per complete row of a flat row-major query matrix; empty list for an empty model. |

## Determinism and cost

- **Deterministic per seed.** The only randomness is the seeded
  second-choice heuristic; refitting with the same seed reproduces `b`,
  `w`, and every alpha bit-for-bit (verified in the tests for RBF seed=7
  and linear seed=42).
- Fitting is `O(passes · n² · d)` worst case and will exceed 1 ms for n in
  the thousands — acceptable because fitting is an offline /
  per-recalibration step. `svm_decision` / `svm_predict` are `O(d)`
  (linear) or `O(n_support · d)` (RBF) and stay sub-millisecond for any
  realistic model.
- Termination is `max_passes` consecutive no-change passes, with a hard
  cap of `100 · max_passes` total passes guarding pathological cases.
- Infeasible input (shape mismatch, `C ≤ 0`, `max_passes ≤ 0`, n = 0)
  yields an empty model whose decision is identically 0.

## Verification

Known-value tests pin the optimizer against hand-computed solutions:

- Two-point 1D problem (X = [−1, +1], y = [−1, +1], C = 10): SMO reaches
  the exact max-margin solution — alphas [0.5, 0.5], b = 0, w = [1.0],
  and `decision(2.0) = 2.0`, all to 1e-9. The dual constraint
  `Σ αᵢyᵢ = 0` holds to 1e-9.
- Linearly separable 2D set (true boundary `x0 + x1 = 4`): 100% train
  accuracy, minimum functional margin ≥ 0.9 (~1 at the optimum), correct
  side-of-boundary signs, and 100% accuracy again under a different seed
  (99).
- XOR clusters with the RBF kernel (γ = 2, C = 10): ≥ 15/16 train
  accuracy, exact labels at all four corners, and support coefficients
  summing to 0 within 1e-6.
- Edge cases proven: n = 1 and all-equal labels leave all alphas at zero
  (no KKT-violating pair exists), and batch predictions match per-row
  predictions exactly.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
