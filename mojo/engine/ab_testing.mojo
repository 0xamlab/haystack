"""
ab_testing.mojo — A/B Testing Framework. Zero Python imports.

Replaces scipy.stats A/B testing with pure Mojo implementations of
sample size calculation, z-tests, confidence intervals, sequential
testing, and multi-arm bandit selection.

Public API:
  sample_size_proportion       — Required sample size per group
  z_test_proportions           — Two-proportion z-test
  confidence_interval_proportion — Wilson score interval
  relative_uplift              — Relative uplift
  is_significant               — Significance check
  power_analysis               — Statistical power
  mde                          — Minimum detectable effect
  sequential_test              — Sequential testing
  epsilon_greedy_select        — Epsilon-greedy bandit
  ucb1_select                  — UCB1 bandit
"""
from std.math import sqrt, abs as fabs, exp, log
from std.random import random_float64


# ── Internal helpers ──────────────────────────────────────────────────────────


fn _norm_cdf(x: Float64) -> Float64:
    """Approximation of standard normal CDF using Abramowitz & Stegun."""
    var t = 1.0 / (1.0 + 0.2316419 * fabs(x))
    var d = 0.3989422804014327  # 1/sqrt(2*pi)
    var p = d * exp(-x * x / 2.0) * (
        t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    )
    if x >= 0.0:
        return 1.0 - p
    return p


fn _norm_ppf(p: Float64) -> Float64:
    """Approximation of standard normal inverse CDF (quantile function).

    Uses rational approximation (Beasley-Springer-Moro).
    """
    if p <= 0.0:
        return -6.0
    if p >= 1.0:
        return 6.0
    if p == 0.5:
        return 0.0

    var t: Float64
    if p < 0.5:
        t = sqrt(-2.0 * log(p))
    else:
        t = sqrt(-2.0 * log(1.0 - p))

    # Rational approximation coefficients
    var c0: Float64 = 2.515517
    var c1: Float64 = 0.802853
    var c2: Float64 = 0.010328
    var d1: Float64 = 1.432788
    var d2: Float64 = 0.189269
    var d3: Float64 = 0.001308

    var result = t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)

    if p < 0.5:
        return -result
    return result


# ── sample_size_proportion ────────────────────────────────────────────────────


fn sample_size_proportion(
    p1: Float64, p2: Float64, alpha: Float64 = 0.05, power: Float64 = 0.8
) -> Int:
    """Required sample size per group for a two-proportion test.

    Args:
        p1: Baseline proportion.
        p2: Expected proportion under alternative.
        alpha: Significance level (default 0.05).
        power: Statistical power (default 0.8).

    Returns:
        Minimum sample size per group.
    """
    var z_alpha = _norm_ppf(1.0 - alpha / 2.0)
    var z_beta = _norm_ppf(power)
    var p_bar = (p1 + p2) / 2.0
    var diff = p2 - p1
    if fabs(diff) < 1e-15:
        return 1000000  # Infinite sample needed for zero effect
    var numer = (z_alpha * sqrt(2.0 * p_bar * (1.0 - p_bar)) + z_beta * sqrt(p1 * (1.0 - p1) + p2 * (1.0 - p2)))
    var n = (numer * numer) / (diff * diff)
    var ni = Int(n) + 1
    if ni < 1:
        ni = 1
    return ni


# ── z_test_proportions ───────────────────────────────────────────────────────


fn z_test_proportions(
    successes_a: Int, n_a: Int, successes_b: Int, n_b: Int
) -> List[Float64]:
    """Two-proportion z-test.

    Args:
        successes_a: Successes in group A.
        n_a: Total observations in group A.
        successes_b: Successes in group B.
        n_b: Total observations in group B.

    Returns:
        [z_statistic, p_value].
    """
    var p_a = Float64(successes_a) / Float64(n_a)
    var p_b = Float64(successes_b) / Float64(n_b)
    var p_pool = Float64(successes_a + successes_b) / Float64(n_a + n_b)
    var se = sqrt(p_pool * (1.0 - p_pool) * (1.0 / Float64(n_a) + 1.0 / Float64(n_b)))
    var z: Float64 = 0.0
    if se > 1e-15:
        z = (p_a - p_b) / se
    var p_value = 2.0 * (1.0 - _norm_cdf(fabs(z)))
    var result = List[Float64]()
    result.append(z)
    result.append(p_value)
    return result^


# ── confidence_interval_proportion ────────────────────────────────────────────


fn confidence_interval_proportion(
    successes: Int, n: Int, confidence: Float64 = 0.95
) -> List[Float64]:
    """Wilson score confidence interval for a proportion.

    Args:
        successes: Number of successes.
        n: Total trials.
        confidence: Confidence level (default 0.95).

    Returns:
        [lower, upper] bounds.
    """
    var p_hat = Float64(successes) / Float64(n)
    var z = _norm_ppf(1.0 - (1.0 - confidence) / 2.0)
    var z2 = z * z
    var nf = Float64(n)
    var denom = 1.0 + z2 / nf
    var center = (p_hat + z2 / (2.0 * nf)) / denom
    var margin = (z / denom) * sqrt(p_hat * (1.0 - p_hat) / nf + z2 / (4.0 * nf * nf))
    var result = List[Float64]()
    result.append(center - margin)
    result.append(center + margin)
    return result^


# ── relative_uplift ──────────────────────────────────────────────────────────


fn relative_uplift(control_rate: Float64, treatment_rate: Float64) -> Float64:
    """Relative uplift: (treatment - control) / control.

    Args:
        control_rate: Control group rate.
        treatment_rate: Treatment group rate.

    Returns:
        Relative uplift as a fraction.
    """
    if fabs(control_rate) < 1e-15:
        return 0.0
    return (treatment_rate - control_rate) / control_rate


# ── is_significant ───────────────────────────────────────────────────────────


fn is_significant(p_value: Float64, alpha: Float64 = 0.05) -> Bool:
    """Check if result is statistically significant.

    Args:
        p_value: The p-value from a test.
        alpha: Significance level (default 0.05).

    Returns:
        True if p_value < alpha.
    """
    return p_value < alpha


# ── power_analysis ───────────────────────────────────────────────────────────


fn power_analysis(
    effect_size: Float64, n: Int, alpha: Float64 = 0.05
) -> Float64:
    """Statistical power for given effect size and sample size.

    Uses normal approximation for a two-sample test.

    Args:
        effect_size: Standardized effect size (Cohen's h).
        n: Sample size per group.
        alpha: Significance level (default 0.05).

    Returns:
        Statistical power (probability of rejecting H0).
    """
    var z_alpha = _norm_ppf(1.0 - alpha / 2.0)
    var noncentrality = effect_size * sqrt(Float64(n) / 2.0)
    var power_val = _norm_cdf(noncentrality - z_alpha) + _norm_cdf(-noncentrality - z_alpha)
    if power_val < 0.0:
        power_val = 0.0
    if power_val > 1.0:
        power_val = 1.0
    return power_val


# ── mde ──────────────────────────────────────────────────────────────────────


fn mde(
    n: Int, baseline_rate: Float64, alpha: Float64 = 0.05, power: Float64 = 0.8
) -> Float64:
    """Minimum detectable effect size.

    Args:
        n: Sample size per group.
        baseline_rate: Baseline conversion rate.
        alpha: Significance level (default 0.05).
        power: Desired power (default 0.8).

    Returns:
        Minimum detectable absolute effect size.
    """
    var z_alpha = _norm_ppf(1.0 - alpha / 2.0)
    var z_beta = _norm_ppf(power)
    var se = sqrt(2.0 * baseline_rate * (1.0 - baseline_rate) / Float64(n))
    return (z_alpha + z_beta) * se


# ── sequential_test ──────────────────────────────────────────────────────────


fn sequential_test(
    successes_a: Int, n_a: Int, successes_b: Int, n_b: Int, alpha: Float64 = 0.05
) -> Int:
    """Sequential test with spending function boundary.

    Returns 0 (continue), 1 (A wins), 2 (B wins).

    Args:
        successes_a: Successes in group A.
        n_a: Total observations in group A.
        successes_b: Successes in group B.
        n_b: Total observations in group B.
        alpha: Significance level (default 0.05).

    Returns:
        0 = continue, 1 = A wins, 2 = B wins.
    """
    var result = z_test_proportions(successes_a, n_a, successes_b, n_b)
    var z_stat = result[0]
    var z_boundary = _norm_ppf(1.0 - alpha / 2.0)

    # Adjust boundary for sequential testing (O'Brien-Fleming-like)
    var total = Float64(n_a + n_b)
    var info_frac = total / (total + 100.0)  # Approximate info fraction
    var adj_boundary = z_boundary / sqrt(info_frac)
    if adj_boundary < z_boundary:
        adj_boundary = z_boundary

    if z_stat > adj_boundary:
        return 1  # A wins (higher proportion)
    if z_stat < -adj_boundary:
        return 2  # B wins
    return 0  # Continue


# ── epsilon_greedy_select ────────────────────────────────────────────────────


fn epsilon_greedy_select(
    rewards: List[Float64], counts: List[Int], epsilon: Float64
) -> Int:
    """Epsilon-greedy multi-arm bandit arm selection.

    With probability epsilon, selects a random arm.
    Otherwise, selects the arm with the highest mean reward.

    Args:
        rewards: Cumulative rewards for each arm.
        counts: Number of pulls for each arm.
        epsilon: Exploration probability.

    Returns:
        Index of the selected arm.
    """
    var n_arms = len(rewards)
    if n_arms == 0:
        return 0

    # Explore with probability epsilon
    var r = random_float64()
    if r < epsilon:
        # Random arm selection using random float
        var arm_f = random_float64() * Float64(n_arms)
        var arm = Int(arm_f)
        if arm >= n_arms:
            arm = n_arms - 1
        return arm

    # Exploit: pick arm with highest mean reward
    var best_arm = 0
    var best_mean: Float64 = -1e18
    for i in range(n_arms):
        var mean_r: Float64
        if counts[i] > 0:
            mean_r = rewards[i] / Float64(counts[i])
        else:
            mean_r = 1e18  # Prefer unexplored arms
        if mean_r > best_mean:
            best_mean = mean_r
            best_arm = i
    return best_arm


# ── ucb1_select ──────────────────────────────────────────────────────────────


fn ucb1_select(
    rewards: List[Float64], counts: List[Int], total: Int
) -> Int:
    """UCB1 arm selection: argmax(mean_reward + sqrt(2*ln(total)/count)).

    Explores unvisited arms first.

    Args:
        rewards: Cumulative rewards for each arm.
        counts: Number of pulls for each arm.
        total: Total number of pulls across all arms.

    Returns:
        Index of the selected arm.
    """
    var n_arms = len(rewards)
    if n_arms == 0:
        return 0

    # First, explore any arm with zero pulls
    for i in range(n_arms):
        if counts[i] == 0:
            return i

    var best_arm = 0
    var best_ucb: Float64 = -1e18
    var ln_total = log(Float64(total))

    for i in range(n_arms):
        var mean_r = rewards[i] / Float64(counts[i])
        var explore = sqrt(2.0 * ln_total / Float64(counts[i]))
        var ucb = mean_r + explore
        if ucb > best_ucb:
            best_ucb = ucb
            best_arm = i
    return best_arm
