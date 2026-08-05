"""
fuzzy_logic.mojo — Fuzzy logic operations. Zero Python imports.

Replaces scikit-fuzzy with pure Mojo implementations of membership
functions (triangular, trapezoidal, gaussian), fuzzy operators
(AND, OR, NOT), defuzzification methods (centroid, bisector, MoM),
rule evaluation, and alpha-cut.

Public API:
  triangular_mf        — Triangular membership function
  trapezoidal_mf       — Trapezoidal membership function
  gaussian_mf          — Gaussian membership function
  fuzzy_and            — Fuzzy AND (min)
  fuzzy_or             — Fuzzy OR (max)
  fuzzy_not            — Fuzzy NOT (1 - a)
  defuzzify_centroid   — Centroid defuzzification
  defuzzify_bisector   — Bisector defuzzification
  defuzzify_mom        — Mean of Maximum defuzzification
  fuzzy_rule_eval      — Evaluate fuzzy rule (AND/OR)
  alpha_cut            — Return x values where membership >= alpha
"""

from std.math import exp, abs as fabs, isnan, isinf


# ── triangular_mf ────────────────────────────────────────────────────────────


fn triangular_mf(x: Float64, a: Float64, b: Float64, c: Float64) -> Float64:
    """Triangular membership function. Peak at b, zero at a and c.

    Args:
        x: Input value.
        a: Left foot (membership 0).
        b: Peak (membership 1).
        c: Right foot (membership 0).

    Returns:
        Membership value in [0, 1].
    """
    if x <= a or x >= c:
        return 0.0
    if x == b:
        return 1.0
    if a == b:
        # Degenerate left side
        if x < b:
            return 0.0
        return (c - x) / (c - b)
    if b == c:
        # Degenerate right side
        if x > b:
            return 0.0
        return (x - a) / (b - a)
    if x < b:
        return (x - a) / (b - a)
    return (c - x) / (c - b)


# ── trapezoidal_mf ───────────────────────────────────────────────────────────


fn trapezoidal_mf(x: Float64, a: Float64, b: Float64, c: Float64, d: Float64) -> Float64:
    """Trapezoidal membership function. Rises a→b, flat b→c, falls c→d.

    Args:
        x: Input value.
        a: Left foot (membership 0).
        b: Left shoulder (membership 1).
        c: Right shoulder (membership 1).
        d: Right foot (membership 0).

    Returns:
        Membership value in [0, 1].
    """
    if x <= a or x >= d:
        return 0.0
    if x >= b and x <= c:
        return 1.0
    if x < b:
        if a == b:
            return 1.0
        return (x - a) / (b - a)
    # x > c
    if c == d:
        return 1.0
    return (d - x) / (d - c)


# ── gaussian_mf ──────────────────────────────────────────────────────────────


fn gaussian_mf(x: Float64, mean: Float64, sigma: Float64) -> Float64:
    """Gaussian membership function: exp(-(x-mean)^2 / (2*sigma^2)).

    Args:
        x: Input value.
        mean: Center of the Gaussian.
        sigma: Standard deviation.

    Returns:
        Membership value in [0, 1].
    """
    if sigma == 0.0:
        if x == mean:
            return 1.0
        return 0.0
    var diff = x - mean
    return exp(-(diff * diff) / (2.0 * sigma * sigma))


# ── fuzzy_and ─────────────────────────────────────────────────────────────────


fn fuzzy_and(a: Float64, b: Float64) -> Float64:
    """Fuzzy AND (minimum t-norm).

    Args:
        a: First membership value.
        b: Second membership value.

    Returns:
        min(a, b).
    """
    if a < b:
        return a
    return b


# ── fuzzy_or ──────────────────────────────────────────────────────────────────


fn fuzzy_or(a: Float64, b: Float64) -> Float64:
    """Fuzzy OR (maximum s-norm).

    Args:
        a: First membership value.
        b: Second membership value.

    Returns:
        max(a, b).
    """
    if a > b:
        return a
    return b


# ── fuzzy_not ─────────────────────────────────────────────────────────────────


fn fuzzy_not(a: Float64) -> Float64:
    """Fuzzy NOT (complement).

    Args:
        a: Membership value.

    Returns:
        1.0 - a.
    """
    return 1.0 - a


# ── defuzzify_centroid ────────────────────────────────────────────────────────


fn defuzzify_centroid(x_values: List[Float64], memberships: List[Float64]) -> Float64:
    """Centroid defuzzification: sum(x*mu) / sum(mu).

    Args:
        x_values: Universe of discourse sample points.
        memberships: Membership values for each x.

    Returns:
        Centroid x value. Returns 0.0 if all memberships are zero.
    """
    var n = len(x_values)
    # memberships[i] is read for every x, and a NaN/inf input would flow into
    # the JSON result: refuse mismatched or non-finite series.
    if len(memberships) != n:
        return 0.0
    for i in range(n):
        if isnan(x_values[i]) or isinf(x_values[i]):
            return 0.0
        if isnan(memberships[i]) or isinf(memberships[i]):
            return 0.0
    if n == 0:
        return 0.0
    var num = 0.0
    var den = 0.0
    for i in range(n):
        num += x_values[i] * memberships[i]
        den += memberships[i]
    if den == 0.0:
        return 0.0
    return num / den


# ── defuzzify_bisector ────────────────────────────────────────────────────────


fn defuzzify_bisector(x_values: List[Float64], memberships: List[Float64]) -> Float64:
    """Bisector defuzzification: find x where area is split in half.

    Args:
        x_values: Universe of discourse sample points.
        memberships: Membership values for each x.

    Returns:
        Bisector x value. Returns 0.0 if empty.
    """
    var n = len(x_values)
    # memberships[i] is read for every x, and a NaN/inf input would flow into
    # the JSON result: refuse mismatched or non-finite series.
    if len(memberships) != n:
        return 0.0
    for i in range(n):
        if isnan(x_values[i]) or isinf(x_values[i]):
            return 0.0
        if isnan(memberships[i]) or isinf(memberships[i]):
            return 0.0
    if n == 0:
        return 0.0
    var total = 0.0
    for i in range(n):
        total += memberships[i]
    if total == 0.0:
        return 0.0
    var half = total / 2.0
    var cumsum = 0.0
    for i in range(n):
        cumsum += memberships[i]
        if cumsum >= half:
            return x_values[i]
    return x_values[n - 1]


# ── defuzzify_mom ─────────────────────────────────────────────────────────────


fn defuzzify_mom(x_values: List[Float64], memberships: List[Float64]) -> Float64:
    """Mean of Maximum defuzzification: average of x at max membership.

    Args:
        x_values: Universe of discourse sample points.
        memberships: Membership values for each x.

    Returns:
        Mean of x values with maximum membership. 0.0 if empty.
    """
    var n = len(x_values)
    # memberships[i] is read for every x, and a NaN/inf input would flow into
    # the JSON result: refuse mismatched or non-finite series.
    if len(memberships) != n:
        return 0.0
    for i in range(n):
        if isnan(x_values[i]) or isinf(x_values[i]):
            return 0.0
        if isnan(memberships[i]) or isinf(memberships[i]):
            return 0.0
    if n == 0:
        return 0.0
    var max_mu = memberships[0]
    for i in range(1, n):
        if memberships[i] > max_mu:
            max_mu = memberships[i]
    var total = 0.0
    var count = 0
    for i in range(n):
        if fabs(memberships[i] - max_mu) < 1e-12:
            total += x_values[i]
            count += 1
    if count == 0:
        return 0.0
    return total / Float64(count)


# ── fuzzy_rule_eval ───────────────────────────────────────────────────────────


fn fuzzy_rule_eval(inputs: List[Float64], rule_type: Int) -> Float64:
    """Evaluate a fuzzy rule by combining inputs.

    Args:
        inputs: List of membership values.
        rule_type: 0 for AND (min), 1 for OR (max).

    Returns:
        Combined firing strength.
    """
    var n = len(inputs)
    if n == 0:
        return 0.0
    var result = inputs[0]
    for i in range(1, n):
        if rule_type == 0:
            if inputs[i] < result:
                result = inputs[i]
        else:
            if inputs[i] > result:
                result = inputs[i]
    return result


# ── alpha_cut ─────────────────────────────────────────────────────────────────


fn alpha_cut(x_values: List[Float64], memberships: List[Float64], alpha: Float64) -> List[Float64]:
    """Alpha-cut: return x values where membership >= alpha.

    Args:
        x_values: Universe of discourse sample points.
        memberships: Membership values for each x.
        alpha: Threshold level.

    Returns:
        List of x values with membership >= alpha.
    """
    var result = List[Float64]()
    var n = len(x_values)
    # memberships[i] is read for every x, and a NaN x would flow into the JSON
    # result: refuse mismatched or non-finite series.
    if len(memberships) != n:
        return result^
    for i in range(n):
        if isnan(x_values[i]) or isinf(x_values[i]):
            return result^
    for i in range(n):
        if memberships[i] >= alpha:
            result.append(x_values[i])
    return result^
