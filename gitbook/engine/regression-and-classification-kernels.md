---
icon: square-root-variable
description: Closed-form OLS/ridge regression, a recursive CART regression tree, four SVM kernel functions with Gram-matrix diagnostics, and ten scalar loss functions for classical supervised learning.
---

# Regression and classification kernels

Four independent modules for the arithmetic underneath classical supervised learning: fitting a
line or hyperplane in closed form, building an actual decision tree by recursive splitting, scoring
how similar two feature vectors are under a kernel, and grading a prediction against a label with a
named loss formula. None of the four import each other or share code, and — despite names that echo
several already-documented pages elsewhere in this section — each covers ground the others do not:
`regression` is the closed-form sibling to `linear_models`'s iterative fits, `regression_tree` is a
real multi-level CART builder that `ml.random_forest`'s bagged single-split stumps never call,
`svm_kernel` is a kernel-function toolbox that `svm_solver` does not import and reimplements on its
own, and `loss_functions`'s per-sample scalar losses are a different computation entirely from
`lossk`'s chunked, tensor-shaped LLM training cross-entropy. Each relationship is verified below
against the real source rather than assumed from the name.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("regression", "ols_simple", [[1.0, 2.0, 3.0, 4.0], [3.0, 5.0, 7.0, 9.0]])["result"]
# {"coefficients": [2.0], "intercept": 1.0, "r_squared": 1.0,
#  "residuals": [0.0, 0.0, 0.0, 0.0]} -- y = 2x + 1 exactly, no noise

runtime.execute("svm_kernel", "kernel_rbf", [[0.0, 0.0], [3.0, 4.0], 0.02])["result"]
# 0.6065306597126334 -- exp(-0.02 * 5^2), the same 3-4-5 right triangle
# ml-classical-algorithms.md's euclidean_distance_knn example measures, fed through an RBF kernel
```

## The modules

| Module | What it does |
| --- | --- |
| `regression` | Closed-form least squares: simple and multiple OLS via Gaussian elimination on the normal equations, L2-penalized ridge regression, polynomial feature expansion, prediction, and the R², MSE, and RMSE metrics used to grade a fit. |
| `regression_tree` | A real recursive CART regression tree: exhaustive best-split search by MSE reduction over sorted midpoints, flat-array tree storage, single and batch prediction, and depth/leaf-count/dataset-MSE introspection on a built tree. |
| `svm_kernel` | The four standard SVM kernel functions (linear, RBF, polynomial, sigmoid), NxN Gram-matrix construction, feature-space centering, kernel alignment, Frobenius norm, and a diagonal-dominance PSD check. |
| `loss_functions` | Ten scalar loss formulas spanning classification, regression, and metric learning: binary and categorical cross-entropy, label-smoothed cross-entropy, focal loss, Huber loss, KL divergence, contrastive and triplet loss, and plain MSE/MAE, plus the `pow_approx` helper focal loss uses for a non-integer exponent. |

## `regression`: closed-form least squares, and its relationship to `linear_models`

`ols_simple` (one predictor) and `ols_multiple` (many predictors, via the normal equations
`β = (XᵀX)⁻¹Xᵀy` solved by Gaussian elimination with partial pivoting) both return a
`RegressionResult`: `coefficients`, `intercept`, `r_squared`, and `residuals`. `ridge_regression`
adds an L2 penalty `α` to every diagonal entry of `XᵀX` except the intercept's own — the same normal
equations, shrunk. On perfectly linear data (`x = [1,2,3,4]`, `y = [3,5,7,9]`, the true line
`y = 2x + 1`), `ols_simple` recovers the line exactly, as shown above. Ridge shrinks that exact fit
toward the intercept as soon as `α > 0`:

```python
X = [[1.0], [2.0], [3.0], [4.0]]
y = [3.0, 5.0, 7.0, 9.0]

runtime.execute("regression", "ridge_regression", [X, y, 1.0])["result"]
# {"coefficients": [1.6666666666666667], "intercept": 1.8333333333333335,
#  "r_squared": 0.9722222222222222, ...}
```

The penalized normal equations for this data are `[[4, 10], [10, 31]] · β = [24, 70]` (the `31`
is the unpenalized `30` plus `α = 1`), which solves to `intercept ≈ 1.8333`, `coefficient ≈ 1.6667`
— pulled off the exact `(1.0, 2.0)` OLS solution toward flatter, smaller-magnitude coefficients, and
`r_squared` drops from `1.0` to `0.9722` as the price of that shrinkage. `polynomial_features(x,
degree)` is a plain feature-expansion helper (`polynomial_features([2.0], 3) == [[2.0, 4.0, 8.0]]`,
i.e. `[x, x², x³]`) with no fitting of its own — it feeds its output into `ols_multiple` or
`ridge_regression` as `X`. `mse`/`rmse`/`r_squared` are the shared metrics: on the ridge predictions
above (`[3.5, 5.1667, 6.8333, 8.5]` against the true `[3,5,7,9]`), `mse = 0.1388888888888889` and
`rmse = 0.37267799624996495`.

**This is the closed-form counterpart to `linear_models`, not a duplicate of it.**
[Trainable linear models](ml-linear-models.md) states the relationship from its own side: elastic-net
and L2-logistic regression there are fit iteratively (coordinate descent, damped Newton/IRLS)
because neither has a closed form; `regression`'s OLS and ridge exist *because* the ordinary and
L2-penalized least-squares problems do have one, and grepping `linear_models.mojo` confirms it calls
nothing here — the two modules solve genuinely different optimization problems that happen to
overlap only at the ridge special case, computed by entirely different arithmetic (one Gaussian
elimination, the other iterative). Elsewhere in this corpus, [Partial least squares
regression](ml-pls.md) and the ES-RNN forecaster (`ml-esrnn.md`) both call `regression.mojo`'s
`ridge_regression`/`predict` directly and unmodified as a building block, rather than reimplementing
least squares themselves — this module is the one other pages depend on, not a second copy of one.

## `regression_tree`: a real recursive CART, not the random-forest stumps

`build_tree(X, y, max_depth=5, min_samples=2)` grows an actual multi-level regression tree:
`best_split` tries every feature and every midpoint between sorted distinct values, scores each by
`mse_reduction` (parent MSE minus the sample-weighted MSE of the two children), and recurses until a
node runs out of samples, hits `max_depth` (silently capped at 64 regardless of what is requested),
or every remaining label is already identical. The tree itself is flat-array storage — parallel
`split_feature`/`split_value`/`left_child`/`right_child`/`leaf_value` lists indexed by node number,
with `split_feature[i] == -1` marking a leaf.

A hand-traceable example: two clusters of labels separated by one feature.

```python
X = [[1.0], [2.0], [3.0], [4.0]]
y = [10.0, 10.0, 20.0, 20.0]

tree = runtime.execute("regression_tree", "build_tree", [X, y, 5, 2])["result"]

runtime.execute("regression_tree", "predict_single", [tree, [1.5]])["result"]   # 10.0
runtime.execute("regression_tree", "predict_single", [tree, [3.5]])["result"]   # 20.0
runtime.execute("regression_tree", "tree_depth", [tree])["result"]              # 2
runtime.execute("regression_tree", "tree_n_leaves", [tree])["result"]           # 2
```

Working the split search by hand: splitting at `2.5` (`{10,10}` left, `{20,20}` right) gives
`mse_reduction = 25.0` — the parent's own variance (mean `15`, MSE `25`) minus zero, since both
children are pure. Splitting at `1.5` or `3.5` instead gives only `8.333...`, so `2.5` wins outright
and the tree ends up two levels deep: a root split on feature 0 at `2.5`, and two pure leaves at
`10.0` and `20.0`. `mse_reduction` itself is directly callable and reproduces the `25.0` above given
the same `y` and the two index lists `[0, 1]`/`[2, 3]`.

**Genuinely distinct from `ml.random_forest`, verified by reading both sources.** [Loss functions and
resident-context kernels](loss-functions-and-resident-context-kernels.md) is not where random forest
lives — it is documented in [Classical ML algorithms](ml-classical-algorithms.md), whose own
`ml.random_forest` module is described there as "bootstrap aggregation of **single-split decision
stumps**." Reading `mojo/engine/ml/random_forest.mojo` directly confirms it: `tree_predict_simple`
picks one best split from five candidate thresholds and stops — a depth-1 stump, not a recursive
tree — and the module's own imports (`std.math`, `std.random`) never reach `regression_tree.mojo`.
`regression_tree.build_tree`, by contrast, recurses to real depth (capped at 64, not 1) and is never
imported by `random_forest.mojo` either. The two are complementary, not overlapping: a forest of
`regression_tree`-style deep trees would cost more per tree and need a bagging layer neither module
provides; `ml.random_forest` gets its ensemble diversity from bootstrap resampling and feature
subsampling around many *shallow, cheap* stumps instead.

Malformed input never reaches the recursion: `build_tree` refuses ragged rows, a length-mismatched
`y`, or any non-finite label by returning a single always-`0.0` leaf rather than aborting, and
`best_split`/`mse_reduction` return a `[-1.0, 0.0, 0.0]` no-split sentinel (or `0.0`) under the same
conditions — each guard exists because Mojo's `List` indexing aborts uncatchably past its own bounds,
not because a well-formed empty dataset is itself an error.

## `svm_kernel`: kernel functions and Gram-matrix diagnostics, not a trainer

Four kernels share one calling convention — `kernel_linear(a, b)`, `kernel_rbf(a, b, gamma)`,
`kernel_polynomial(a, b, degree, coef0)`, `kernel_sigmoid(a, b, gamma, coef0)` — plus `kernel_matrix`
to build the full NxN Gram matrix for a dataset (`kernel_type`: 0=linear, 1=rbf, 2=poly, 3=sigmoid),
and four diagnostics over an already-built Gram matrix: `kernel_center` (center in feature space),
`frobenius_norm`, `kernel_alignment` (cosine similarity between two Gram matrices under the Frobenius
inner product), and `is_positive_semidefinite`.

```python
runtime.execute("svm_kernel", "kernel_linear", [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])["result"]
# 32.0 -- plain dot product

runtime.execute("svm_kernel", "kernel_polynomial", [[1.0, 2.0], [3.0, 4.0], 2, 1.0])["result"]
# 144.0 -- (dot([1,2],[3,4]) + 1)^2 = (11 + 1)^2

data = [[1.0, 0.0], [0.0, 1.0]]
K = runtime.execute("svm_kernel", "kernel_matrix", [data, 0])["result"]   # [[1,0],[0,1]]
runtime.execute("svm_kernel", "kernel_alignment", [K, K])["result"]
# 0.9999999999999998 -- a kernel matrix aligned with itself is 1.0, to float rounding
```

`kernel_alignment(K, K) ≈ 1.0` for any Gram matrix is not a coincidence of this example: it is
`⟨K,K⟩_F / (‖K‖_F · ‖K‖_F) = ‖K‖²_F / ‖K‖²_F = 1` by construction, so the identity is a property of
the formula, checkable on any square matrix. Centering the same identity matrix (`kernel_center`)
gives `[[0.5, -0.5], [-0.5, 0.5]]`, whose Frobenius norm is exactly `1.0`.

{% hint style="warning" %}
**`is_positive_semidefinite` is a sufficient, not necessary, heuristic — and it produces real false
negatives on genuinely PSD matrices.** Its own docstring says as much ("a sufficient (not necessary)
condition"), and it is checkable directly: any Gram matrix `K = [[a·a, a·b], [b·a, b·b]]` built from
real vectors is mathematically guaranteed PSD. Take `a = [1.0, 1.0]`, `b = [1.0, 1.01]`:
`K = [[2.0, 2.01], [2.01, 2.0201]]`. Its true eigenvalues are `~2.49e-5` and `~4.0201` — both
positive, so the matrix is genuinely (barely) positive definite. But row 0's diagonal (`2.0`) is
less than its off-diagonal sum (`2.01`), so the diagonal-dominance check `is_positive_semidefinite`
runs on row 0 fails, and it returns `False` on a matrix that is truly PSD. A caller using this
function to gate "is this a valid kernel" would wrongly reject a legitimate, if slightly
ill-conditioned, Gram matrix — the function is safe to trust when it returns `True`, but a `False`
is not proof the matrix isn't PSD.
{% endhint %}

The two kernels also disagree on how they handle mismatched-length inputs: `kernel_linear` and
`kernel_rbf` silently truncate to the shorter vector's length (`n = min(len(a), len(b))`) rather than
refusing, while `kernel_alignment` refuses outright with `0.0` the moment `K2` is shorter than `K1`
in either dimension. `kernel_polynomial` caps `degree` at 100 internally regardless of what is
requested, because `|base|^d` overflows `Float64` to infinity well before then.

**`svm_kernel` is the kernel-function toolbox `svm_solver` explicitly complements but does not
import.** [Trainable SVM classifier](ml-svm.md) states this from its own side — `svm_solver`
"complements `svm_kernel.mojo` (kernel functions only) but is fully self-contained" — and reading
`mojo/engine/svm_solver.mojo`'s imports confirms it: only `std.math`, never `svm_kernel`. The
solver's own `svm_fit_rbf` recomputes `exp(-γ‖a-b‖²)` inline rather than calling
`svm_kernel.kernel_rbf`, so the two modules never share a code path even though they compute the same
formula. `svm_kernel` is the wider toolbox — four kernels instead of the solver's two (linear, RBF),
plus the Gram-matrix diagnostics (`kernel_center`, `kernel_alignment`, `is_positive_semidefinite`)
a solver has no use for but a kernel-method researcher inspecting a Gram matrix does.

## `loss_functions`: ten scalar objectives, and how they differ from `lossk`

Every function here takes plain `Float64` scalars — one prediction, one label, sometimes a scale
parameter — and returns one scalar loss; there is no batching, no gradient, and no tensor shape
anywhere in this module. A caller sums or averages the per-sample values itself.

| Function | Formula | Worked value |
| --- | --- | --- |
| `binary_cross_entropy(y_true, y_pred)` | `-(y·log(p) + (1-y)·log(1-p))`, `p` clamped to `[1e-7, 1-1e-7]` | `bce(1, 0.8) = 0.2231435513142097` |
| `categorical_cross_entropy(y_true, y_pred)` | `-y·log(p)`, one class's contribution | `cce(1, 0.7) = 0.35667494393873245` |
| `label_smoothing_loss(y_true, y_pred, epsilon, n_classes)` | `-((1-ε)y + ε/K)·log(p)` | `label_smooth(1, 0.9, 0.1, 10) = 0.09587806924862192` |
| `focal_loss(y_true, y_pred, gamma, alpha)` | `-α_t·(1-p_t)^γ·log(p_t)` (Lin et al. 2017) | `focal(1, 0.9, 2, 0.25) = 0.00026340128914456557` |
| `huber_loss(y_true, y_pred, delta)` | `0.5d²` if `\|d\| ≤ δ`, else `δ\|d\| - 0.5δ²` | `huber(5, 2, 1) = 2.5`; `huber(5, 4.5, 1) = 0.125` |
| `kl_divergence(p, q)` | `p·log(p/q)`, one term of a full KL sum | `kl(0.6, 0.4) = 0.24327906486489853` |
| `contrastive_loss(distance, label, margin)` | `d²` if similar (`label < 0.5`), else `max(0, margin-d)²` | `contrastive(2, 0, _) = 4.0`; `contrastive(1, 1, 3) = 4.0` |
| `triplet_loss(dist_pos, dist_neg, margin)` | `max(0, d_pos - d_neg + margin)` | `triplet(0.3, 0.9, 0.2) = 0.0`; `triplet(0.9, 0.3, 0.2) = 0.8` |
| `mse_loss(y_true, y_pred)` / `mae_loss(y_true, y_pred)` | `(y-p)²` / `\|y-p\|` | `mse_loss(5, 3) = 4.0`; `mae_loss(5, 3) = 2.0` |
| `pow_approx(base, exponent)` | `exp(exponent·log(base))`, `0.0` if `base ≤ 0` | powers `focal_loss`'s `(1-p_t)^γ` term |

```python
runtime.execute("loss_functions", "huber_loss", [5.0, 2.0, 1.0])["result"]      # 2.5
runtime.execute("loss_functions", "huber_loss", [5.0, 4.5, 1.0])["result"]      # 0.125
runtime.execute("loss_functions", "triplet_loss", [0.3, 0.9, 0.2])["result"]    # 0.0 -- inside margin, no penalty
runtime.execute("loss_functions", "triplet_loss", [0.9, 0.3, 0.2])["result"]    # 0.8 -- positive farther than negative
```

`huber_loss` at `delta=1` on the two calls above shows the whole point of the formula: a `3.0`
residual (`5 - 2`) is past the threshold and costs `2.5` — linear in the residual, not quadratic — a
`0.5` residual (`5 - 4.5`) stays inside it and costs the plain squared-error `0.125`, so a huber-loss
optimizer is quadratic (MSE-like) near a good fit and linear (MAE-like, outlier-robust) far from one.
`triplet_loss` is zero whenever the anchor is already closer to the positive than to the negative by
at least `margin` — `0.3 - 0.9 + 0.2 = -0.4`, clamped to `0.0` — and only turns positive once that
margin is violated, which is what makes the loss stop pushing an already-good embedding further.

**This is a different computation from `lossk`, not a smaller version of it.** [Loss functions and
resident-context kernels](loss-functions-and-resident-context-kernels.md) documents `lossk`, whose
`ce_from_logits_flat`/`fused_linear_ce_flat` compute cross-entropy over a full `[n_tok][vocab]` logit
tensor — chunked specifically so that tensor, which is gigabytes at LLM training scale, never has to
be materialized all at once — and own their own 580-599 status-code range for shape and memory-budget
refusals. `loss_functions` has no chunking, no logit tensor, no status codes, and no shared code with
`lossk`: every function here takes a single already-computed prediction and label and returns one
number, the generic toolbox a classical classifier, regressor, or embedding model reaches for,
independent of whether the model behind it is an LLM at all.

## Verification

All four `mojo/tests/libs/test_*.mojo` files behind this page (`test_regression.mojo`,
`test_regression_tree.mojo`, `test_svm_kernel.mojo`, `test_loss_functions.mojo`) are auto-generated
coverage smoke tests: each calls a handful of functions once with the literal arguments `0.5` (or a
fixed five-element list) and checks only that the result is finite — none of them pin a specific
numeric output, and no hand-written suite for any of the four turned up in `tests/mojo/test_wave*.mojo`
either. Every worked value on this page was hand-derived independently from the real formulas in
`mojo/engine/regression.mojo`, `regression_tree.mojo`, `svm_kernel.mojo`, and `loss_functions.mojo`,
cross-checked in plain Python, and is reproducible by re-running the same arithmetic.

**Next:** see [Trainable linear models](ml-linear-models.md) and [Trainable SVM classifier](ml-svm.md)
for the iterative fitters these closed-form kernels complement, or browse the
[engine catalog](catalog.md) for everything else.
