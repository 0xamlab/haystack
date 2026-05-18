"""
decision_analysis.mojo — Decision analysis under uncertainty. Zero Python imports.

Replaces custom decision-analysis Python code with pure Mojo implementations
for expected value, expected utility, decision matrices, minimax regret,
Hurwicz criterion, value of perfect information, and sensitivity analysis.

Public API:
  expected_value        — Weighted expected value
  expected_utility      — Expected utility with CRRA
  decision_matrix_best  — Best alternative by max expected payoff
  minimax_regret        — Minimax regret criterion
  hurwicz_criterion     — Hurwicz α-criterion
  value_of_perfect_info — EVPI
  sensitivity_range     — Sensitivity on one state probability
  maximin               — Pessimistic criterion
  maximax               — Optimistic criterion
  laplace_criterion     — Equal probability criterion
"""
from std.math import log, abs as fabs


# ── expected_value ────────────────────────────────────────────────────────────


fn expected_value(outcomes: List[Float64], probabilities: List[Float64]) -> Float64:
    """Weighted expected value: Σ(outcome_i * prob_i)."""
    var n = len(outcomes)
    var result: Float64 = 0.0
    for i in range(n):
        result += outcomes[i] * probabilities[i]
    return result


# ── expected_utility ──────────────────────────────────────────────────────────


fn expected_utility(
    outcomes: List[Float64],
    probabilities: List[Float64],
    risk_aversion: Float64,
) -> Float64:
    """Expected utility with CRRA utility function.

    u(x) = x^(1-γ)/(1-γ) for γ≠1, log(x) for γ=1.
    Returns Σ(prob_i * u(outcome_i)).
    """
    var n = len(outcomes)
    var result: Float64 = 0.0
    var gamma = risk_aversion
    if fabs(gamma - 1.0) < 1e-12:
        # Log utility
        for i in range(n):
            var x = outcomes[i]
            if x <= 0.0:
                x = 1e-15
            result += probabilities[i] * log(x)
    else:
        var exp = 1.0 - gamma
        for i in range(n):
            var x = outcomes[i]
            if x <= 0.0:
                x = 1e-15
            # x^(1-γ) = exp(ln(x)*(1-γ))
            var util = _pow_pos(x, exp) / exp
            result += probabilities[i] * util
    return result


fn _pow_pos(base: Float64, exp: Float64) -> Float64:
    """Positive base raised to real exponent: base^exp = e^(exp*ln(base))."""
    if base <= 0.0:
        return 0.0
    var ln_base = log(base)
    return _exp_approx(exp * ln_base)


fn _exp_approx(x: Float64) -> Float64:
    """Fast exp via Taylor series (30 terms)."""
    var clamped = x
    if clamped > 20.0:
        clamped = 20.0
    if clamped < -20.0:
        clamped = -20.0
    var result: Float64 = 1.0
    var term: Float64 = 1.0
    for i in range(1, 30):
        term *= clamped / Float64(i)
        result += term
    return result


# ── _row_ev (helper) ──────────────────────────────────────────────────────────


fn _row_ev(payoffs: List[List[Float64]], row: Int, probs: List[Float64]) -> Float64:
    """Expected value of a single alternative (row)."""
    var n_states = len(probs)
    var ev: Float64 = 0.0
    for j in range(n_states):
        ev += payoffs[row][j] * probs[j]
    return ev


# ── decision_matrix_best ──────────────────────────────────────────────────────


fn decision_matrix_best(
    payoffs: List[List[Float64]], probabilities: List[Float64]
) -> Int:
    """Best alternative by maximum expected payoff."""
    var n_alts = len(payoffs)
    var best_idx = 0
    var best_ev = _row_ev(payoffs, 0, probabilities)
    for i in range(1, n_alts):
        var ev = _row_ev(payoffs, i, probabilities)
        if ev > best_ev:
            best_ev = ev
            best_idx = i
    return best_idx


# ── minimax_regret ────────────────────────────────────────────────────────────


fn minimax_regret(payoffs: List[List[Float64]]) -> Int:
    """Minimax regret: minimize the maximum regret across states."""
    var n_alts = len(payoffs)
    var n_states = len(payoffs[0])
    # Find best payoff per state
    var best_per_state = List[Float64]()
    for j in range(n_states):
        var best = payoffs[0][j]
        for i in range(1, n_alts):
            if payoffs[i][j] > best:
                best = payoffs[i][j]
        best_per_state.append(best)
    # Compute max regret per alternative
    var best_idx = 0
    var best_max_regret = 1e300
    for i in range(n_alts):
        var max_regret: Float64 = 0.0
        for j in range(n_states):
            var regret = best_per_state[j] - payoffs[i][j]
            if regret > max_regret:
                max_regret = regret
        if max_regret < best_max_regret:
            best_max_regret = max_regret
            best_idx = i
    return best_idx


# ── hurwicz_criterion ─────────────────────────────────────────────────────────


fn hurwicz_criterion(payoffs: List[List[Float64]], alpha: Float64) -> Int:
    """Hurwicz: α*max + (1-α)*min for each alternative. Returns best index."""
    var n_alts = len(payoffs)
    var best_idx = 0
    var best_val = -1e300
    for i in range(n_alts):
        var n_states = len(payoffs[i])
        var row_min = payoffs[i][0]
        var row_max = payoffs[i][0]
        for j in range(1, n_states):
            if payoffs[i][j] < row_min:
                row_min = payoffs[i][j]
            if payoffs[i][j] > row_max:
                row_max = payoffs[i][j]
        var val = alpha * row_max + (1.0 - alpha) * row_min
        if val > best_val:
            best_val = val
            best_idx = i
    return best_idx


# ── value_of_perfect_info ─────────────────────────────────────────────────────


fn value_of_perfect_info(
    payoffs: List[List[Float64]], probabilities: List[Float64]
) -> Float64:
    """EVPI = EV with perfect info - EV of best alternative."""
    var n_alts = len(payoffs)
    var n_states = len(probabilities)
    # EV of best alternative
    var best_ev = _row_ev(payoffs, 0, probabilities)
    for i in range(1, n_alts):
        var ev = _row_ev(payoffs, i, probabilities)
        if ev > best_ev:
            best_ev = ev
    # EV with perfect info: Σ prob_j * max_i(payoff[i][j])
    var ev_pi: Float64 = 0.0
    for j in range(n_states):
        var best = payoffs[0][j]
        for i in range(1, n_alts):
            if payoffs[i][j] > best:
                best = payoffs[i][j]
        ev_pi += probabilities[j] * best
    return ev_pi - best_ev


# ── sensitivity_range ─────────────────────────────────────────────────────────


fn sensitivity_range(
    payoffs: List[List[Float64]], state_idx: Int, n_steps: Int = 100
) -> List[List[Float64]]:
    """Vary probability of one state from 0→1, distribute rest equally.

    Returns [[p, best_alternative_idx], ...].
    """
    var n_states = len(payoffs[0])
    var result = List[List[Float64]]()
    for s in range(n_steps):
        var p = Float64(s) / Float64(n_steps - 1) if n_steps > 1 else 0.5
        var probs = List[Float64]()
        var remaining = 1.0 - p
        for j in range(n_states):
            if j == state_idx:
                probs.append(p)
            else:
                probs.append(remaining / Float64(n_states - 1))
        var best = decision_matrix_best(payoffs, probs)
        var row = List[Float64]()
        row.append(p)
        row.append(Float64(best))
        result.append(row^)
    return result^


# ── maximin ───────────────────────────────────────────────────────────────────


fn maximin(payoffs: List[List[Float64]]) -> Int:
    """Maximin (pessimistic): maximize the minimum payoff."""
    var n_alts = len(payoffs)
    var best_idx = 0
    var best_min = -1e300
    for i in range(n_alts):
        var n_states = len(payoffs[i])
        var row_min = payoffs[i][0]
        for j in range(1, n_states):
            if payoffs[i][j] < row_min:
                row_min = payoffs[i][j]
        if row_min > best_min:
            best_min = row_min
            best_idx = i
    return best_idx


# ── maximax ───────────────────────────────────────────────────────────────────


fn maximax(payoffs: List[List[Float64]]) -> Int:
    """Maximax (optimistic): maximize the maximum payoff."""
    var n_alts = len(payoffs)
    var best_idx = 0
    var best_max = -1e300
    for i in range(n_alts):
        var n_states = len(payoffs[i])
        var row_max = payoffs[i][0]
        for j in range(1, n_states):
            if payoffs[i][j] > row_max:
                row_max = payoffs[i][j]
        if row_max > best_max:
            best_max = row_max
            best_idx = i
    return best_idx


# ── laplace_criterion ─────────────────────────────────────────────────────────


fn laplace_criterion(payoffs: List[List[Float64]]) -> Int:
    """Laplace (equal probability): best average payoff."""
    var n_alts = len(payoffs)
    var best_idx = 0
    var best_avg = -1e300
    for i in range(n_alts):
        var n_states = len(payoffs[i])
        var total: Float64 = 0.0
        for j in range(n_states):
            total += payoffs[i][j]
        var avg = total / Float64(n_states)
        if avg > best_avg:
            best_avg = avg
            best_idx = i
    return best_idx
