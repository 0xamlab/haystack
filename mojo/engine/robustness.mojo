"""
robustness.mojo — Robustness & Sensitivity Testing. Zero Python imports.

Replaces custom robustness/sensitivity analysis code with pure Mojo
implementations for perturbation testing, Morris screening, Sobol indices,
tornado charts, and input sweeps.

Public API:
  perturbation_test           — Add random perturbation to values
  sensitivity_one_at_a_time   — OAT sensitivity analysis
  morris_screening            — Morris elementary effects screening
  sobol_first_order_estimate  — Simplified Sobol first-order indices
  input_range_sweep           — Sweep one input and record outputs
  tornado_data                — Tornado chart data generation
  robustness_score            — Coefficient of variation
  eval_test_func              — Built-in test functions
"""

from std.math import sqrt, abs as fabs
from random import random_float64


# ── eval_test_func ───────────────────────────────────────────────────────────


fn eval_test_func(x: List[Float64], func_id: Int) -> Float64:
    """Built-in test functions.

    func_id 0: sum of x
    func_id 1: product of x
    func_id 2: weighted sum (x0 + 2*x1 + 3*x2 + ...)
    """
    var n = len(x)
    if func_id == 0:
        var s: Float64 = 0.0
        for i in range(n):
            s += x[i]
        return s
    elif func_id == 1:
        if n == 0:
            return 0.0
        var p: Float64 = 1.0
        for i in range(n):
            p *= x[i]
        return p
    else:
        var s: Float64 = 0.0
        for i in range(n):
            s += Float64(i + 1) * x[i]
        return s


# ── perturbation_test ────────────────────────────────────────────────────────


fn perturbation_test(values: List[Float64],
                     perturbation: Float64) -> List[Float64]:
    """Add random perturbation (+-perturbation) to each value."""
    var n = len(values)
    var result = List[Float64]()
    for i in range(n):
        var r = random_float64() * 2.0 - 1.0
        result.append(values[i] + r * perturbation)
    return result^


# ── sensitivity_one_at_a_time ────────────────────────────────────────────────


fn sensitivity_one_at_a_time(baseline: List[Float64], index: Int,
                             delta: Float64, func_id: Int) -> Float64:
    """OAT sensitivity: change one input by delta, measure output change."""
    var f0 = eval_test_func(baseline, func_id)
    var perturbed = List[Float64]()
    for i in range(len(baseline)):
        if i == index:
            perturbed.append(baseline[i] + delta)
        else:
            perturbed.append(baseline[i])
    var f1 = eval_test_func(perturbed, func_id)
    if fabs(delta) < 1e-15:
        return 0.0
    return (f1 - f0) / delta


# ── morris_screening ─────────────────────────────────────────────────────────


fn morris_screening(n_inputs: Int, func_id: Int, n_trajectories: Int,
                    delta: Float64) -> List[Float64]:
    """Morris elementary effects screening.

    Returns mean absolute elementary effect per input.
    """
    var effects = List[Float64]()
    for i in range(n_inputs):
        effects.append(0.0)

    for _t in range(n_trajectories):
        var base = List[Float64]()
        for i in range(n_inputs):
            base.append(random_float64())
        var f_base = eval_test_func(base, func_id)

        for i in range(n_inputs):
            var perturbed = List[Float64]()
            for j in range(n_inputs):
                if j == i:
                    perturbed.append(base[j] + delta)
                else:
                    perturbed.append(base[j])
            var f_pert = eval_test_func(perturbed, func_id)
            var ee = fabs((f_pert - f_base) / delta)
            effects[i] = effects[i] + ee

    if n_trajectories > 0:
        for i in range(n_inputs):
            effects[i] = effects[i] / Float64(n_trajectories)
    return effects^


# ── sobol_first_order_estimate ───────────────────────────────────────────────


fn sobol_first_order_estimate(n_inputs: Int, func_id: Int,
                              n_samples: Int) -> List[Float64]:
    """Simplified Sobol first-order indices via Monte Carlo."""
    var indices = List[Float64]()
    for i in range(n_inputs):
        indices.append(0.0)

    var a_mat = List[List[Float64]]()
    var b_mat = List[List[Float64]]()
    var f_a = List[Float64]()
    var f_b = List[Float64]()

    for s in range(n_samples):
        var row_a = List[Float64]()
        var row_b = List[Float64]()
        for j in range(n_inputs):
            row_a.append(random_float64())
            row_b.append(random_float64())
        f_a.append(eval_test_func(row_a, func_id))
        f_b.append(eval_test_func(row_b, func_id))
        a_mat.append(row_a^)
        b_mat.append(row_b^)

    var mean_a: Float64 = 0.0
    for s in range(n_samples):
        mean_a += f_a[s]
    mean_a /= Float64(n_samples)
    var var_total: Float64 = 0.0
    for s in range(n_samples):
        var d = f_a[s] - mean_a
        var_total += d * d
    var_total /= Float64(n_samples)

    if var_total < 1e-15:
        return indices^

    for i in range(n_inputs):
        var cov_sum: Float64 = 0.0
        for s in range(n_samples):
            var ab_i = List[Float64]()
            for j in range(n_inputs):
                if j == i:
                    ab_i.append(b_mat[s][j])
                else:
                    ab_i.append(a_mat[s][j])
            var f_ab_i = eval_test_func(ab_i, func_id)
            cov_sum += f_b[s] * (f_ab_i - f_a[s])
        var si = cov_sum / (Float64(n_samples) * var_total)
        if si < 0.0:
            si = 0.0
        if si > 1.0:
            si = 1.0
        indices[i] = si
    return indices^


# ── input_range_sweep ────────────────────────────────────────────────────────


fn input_range_sweep(baseline: List[Float64], index: Int,
                     lo: Float64, hi: Float64, n_points: Int,
                     func_id: Int) -> List[List[Float64]]:
    """Sweep one input from lo to hi and record [input_value, output] pairs."""
    var result = List[List[Float64]]()
    if n_points <= 1:
        var x = List[Float64]()
        for j in range(len(baseline)):
            if j == index:
                x.append(lo)
            else:
                x.append(baseline[j])
        var row = List[Float64]()
        row.append(lo)
        row.append(eval_test_func(x, func_id))
        result.append(row^)
        return result^
    var step = (hi - lo) / Float64(n_points - 1)
    for i in range(n_points):
        var val = lo + Float64(i) * step
        var x = List[Float64]()
        for j in range(len(baseline)):
            if j == index:
                x.append(val)
            else:
                x.append(baseline[j])
        var row = List[Float64]()
        row.append(val)
        row.append(eval_test_func(x, func_id))
        result.append(row^)
    return result^


# ── tornado_data ─────────────────────────────────────────────────────────────


fn tornado_data(baseline: List[Float64], deltas: List[Float64],
                func_id: Int) -> List[List[Float64]]:
    """Tornado chart data: for each input, [low_output, high_output]."""
    var n = len(baseline)
    var result = List[List[Float64]]()
    for i in range(n):
        var d: Float64 = 0.1
        if i < len(deltas):
            d = deltas[i]
        var x_low = List[Float64]()
        var x_high = List[Float64]()
        for j in range(n):
            if j == i:
                x_low.append(baseline[j] - d)
                x_high.append(baseline[j] + d)
            else:
                x_low.append(baseline[j])
                x_high.append(baseline[j])
        var row = List[Float64]()
        row.append(eval_test_func(x_low, func_id))
        row.append(eval_test_func(x_high, func_id))
        result.append(row^)
    return result^


# ── robustness_score ─────────────────────────────────────────────────────────


fn robustness_score(results: List[Float64]) -> Float64:
    """Coefficient of variation: std / |mean|."""
    var n = len(results)
    if n == 0:
        return 0.0
    var mean: Float64 = 0.0
    for i in range(n):
        mean += results[i]
    mean /= Float64(n)
    if fabs(mean) < 1e-15:
        return 0.0
    var var_sum: Float64 = 0.0
    for i in range(n):
        var d = results[i] - mean
        var_sum += d * d
    var_sum /= Float64(n)
    return sqrt(var_sum) / fabs(mean)
