"""
game_theory.mojo — Game theory algorithms. Zero Python imports.

Replaces custom Python game theory code with pure Mojo implementations
of Nash equilibrium finding, minimax, dominated strategies, expected
payoff, Prisoner's Dilemma, iterated PD, Shapley values, and Pareto
optimality.

Public API:
  nash_2x2                   — Mixed strategy Nash equilibrium for 2×2
  minimax_value              — Minimax value for zero-sum game
  dominated_strategy_check   — Check for strictly dominated rows
  expected_payoff            — Expected payoff under mixed strategies
  prisoners_dilemma_payoff   — Standard PD payoffs
  iterated_pd                — Iterated Prisoner's Dilemma
  shapley_value_3player      — Shapley value for 3-player game
  pareto_optimal_outcomes    — Mark Pareto optimal outcomes
"""

from std.math import abs as fabs


# ── nash_2x2 ─────────────────────────────────────────────────────────────────


fn nash_2x2(payoff_a: List[List[Float64]], payoff_b: List[List[Float64]]) -> List[Float64]:
    """Find mixed strategy Nash equilibrium for a 2×2 game.

    Uses indifference equations. Player 1 mixes so player 2 is indifferent,
    and vice versa.

    Args:
        payoff_a: 2×2 payoff matrix for player A (row player).
        payoff_b: 2×2 payoff matrix for player B (column player).

    Returns:
        [p1_play_row0, p2_play_col0]. Clamped to [0, 1].
    """
    # Player 1 chooses p so that player 2 is indifferent between columns:
    # p*b[0][0] + (1-p)*b[1][0] = p*b[0][1] + (1-p)*b[1][1]
    var b00 = payoff_b[0][0]
    var b01 = payoff_b[0][1]
    var b10 = payoff_b[1][0]
    var b11 = payoff_b[1][1]
    var denom_p = (b00 - b01 - b10 + b11)
    var p: Float64 = 0.5
    if fabs(denom_p) > 1e-12:
        p = (b11 - b10) / denom_p
    if p < 0.0:
        p = 0.0
    if p > 1.0:
        p = 1.0

    # Player 2 chooses q so that player 1 is indifferent between rows:
    # q*a[0][0] + (1-q)*a[0][1] = q*a[1][0] + (1-q)*a[1][1]
    var a00 = payoff_a[0][0]
    var a01 = payoff_a[0][1]
    var a10 = payoff_a[1][0]
    var a11 = payoff_a[1][1]
    var denom_q = (a00 - a01 - a10 + a11)
    var q: Float64 = 0.5
    if fabs(denom_q) > 1e-12:
        q = (a11 - a01) / denom_q
    if q < 0.0:
        q = 0.0
    if q > 1.0:
        q = 1.0

    var result = List[Float64]()
    result.append(p)
    result.append(q)
    return result^


# ── minimax_value ─────────────────────────────────────────────────────────────


fn minimax_value(payoff: List[List[Float64]]) -> Float64:
    """Minimax value for a zero-sum game (row player's perspective).

    Row player maximizes the minimum payoff across columns.

    Args:
        payoff: m×n payoff matrix.

    Returns:
        Minimax value.
    """
    var rows = len(payoff)
    if rows == 0:
        return 0.0
    var best = -1e300
    for i in range(rows):
        var row = payoff[i].copy()
        var cols = len(row)
        if cols == 0:
            continue
        var row_min = row[0]
        for j in range(1, cols):
            if row[j] < row_min:
                row_min = row[j]
        if row_min > best:
            best = row_min
    return best


# ── dominated_strategy_check ─────────────────────────────────────────────────


fn dominated_strategy_check(payoff: List[List[Float64]]) -> List[Bool]:
    """Check if each row is strictly dominated by some other row.

    Args:
        payoff: m×n payoff matrix.

    Returns:
        List of Bool per row — True if that row is strictly dominated.
    """
    var rows = len(payoff)
    var result = List[Bool]()
    if rows == 0:
        return result^
    var cols = len(payoff[0])
    for i in range(rows):
        var dominated = False
        for j in range(rows):
            if i == j:
                continue
            # Check if row j strictly dominates row i
            var all_better = True
            for k in range(cols):
                if payoff[j][k] <= payoff[i][k]:
                    all_better = False
                    break
            if all_better:
                dominated = True
                break
        result.append(dominated)
    return result^


# ── expected_payoff ───────────────────────────────────────────────────────────


fn expected_payoff(payoff: List[List[Float64]], p_row: List[Float64], p_col: List[Float64]) -> Float64:
    """Expected payoff given mixed strategies for both players.

    Args:
        payoff: m×n payoff matrix.
        p_row: Probability distribution over rows.
        p_col: Probability distribution over columns.

    Returns:
        Expected payoff = sum_i sum_j p_row[i] * p_col[j] * payoff[i][j].
    """
    var rows = len(payoff)
    var total = 0.0
    for i in range(rows):
        var row = payoff[i].copy()
        var cols = len(row)
        for j in range(cols):
            total += p_row[i] * p_col[j] * row[j]
    return total


# ── prisoners_dilemma_payoff ──────────────────────────────────────────────────


fn prisoners_dilemma_payoff(p1_cooperate: Bool, p2_cooperate: Bool) -> List[Float64]:
    """Standard Prisoner's Dilemma payoffs.

    CC=(3,3), CD=(0,5), DC=(5,0), DD=(1,1).

    Args:
        p1_cooperate: Player 1 cooperates.
        p2_cooperate: Player 2 cooperates.

    Returns:
        [p1_payoff, p2_payoff].
    """
    var result = List[Float64]()
    if p1_cooperate and p2_cooperate:
        result.append(3.0)
        result.append(3.0)
    elif p1_cooperate and not p2_cooperate:
        result.append(0.0)
        result.append(5.0)
    elif not p1_cooperate and p2_cooperate:
        result.append(5.0)
        result.append(0.0)
    else:
        result.append(1.0)
        result.append(1.0)
    return result^


# ── iterated_pd ───────────────────────────────────────────────────────────────


fn iterated_pd(strategy1: Int, strategy2: Int, rounds: Int) -> List[Float64]:
    """Iterated Prisoner's Dilemma.

    Strategies: 0=always cooperate, 1=always defect, 2=tit-for-tat.
    Tit-for-tat starts by cooperating, then copies opponent's last move.

    Args:
        strategy1: Player 1's strategy code.
        strategy2: Player 2's strategy code.
        rounds: Number of rounds.

    Returns:
        [total_p1, total_p2].
    """
    var total1 = 0.0
    var total2 = 0.0
    var last_p1 = True  # last move of player 1 (True = cooperate)
    var last_p2 = True  # last move of player 2

    for r in range(rounds):
        var p1_coop: Bool
        var p2_coop: Bool

        # Determine player 1's move
        if strategy1 == 0:
            p1_coop = True
        elif strategy1 == 1:
            p1_coop = False
        else:  # tit-for-tat
            if r == 0:
                p1_coop = True
            else:
                p1_coop = last_p2

        # Determine player 2's move
        if strategy2 == 0:
            p2_coop = True
        elif strategy2 == 1:
            p2_coop = False
        else:  # tit-for-tat
            if r == 0:
                p2_coop = True
            else:
                p2_coop = last_p1

        var pay = prisoners_dilemma_payoff(p1_coop, p2_coop)
        total1 += pay[0]
        total2 += pay[1]
        last_p1 = p1_coop
        last_p2 = p2_coop

    var result = List[Float64]()
    result.append(total1)
    result.append(total2)
    return result^


# ── shapley_value_3player ─────────────────────────────────────────────────────


fn shapley_value_3player(v: List[Float64]) -> List[Float64]:
    """Shapley value for 3-player cooperative game.

    v has 8 entries indexed by subset bitmask:
      v[0]=v({}), v[1]=v({1}), v[2]=v({2}), v[3]=v({1,2}),
      v[4]=v({3}), v[5]=v({1,3}), v[6]=v({2,3}), v[7]=v({1,2,3}).

    Args:
        v: Coalition values indexed by bitmask.

    Returns:
        [phi_1, phi_2, phi_3] Shapley values.
    """
    # All 6 permutations of 3 players: (0-indexed internally)
    # Permutation orderings and marginal contributions
    var phi = List[Float64]()
    phi.append(0.0)
    phi.append(0.0)
    phi.append(0.0)

    # 6 permutations of players {0,1,2} (representing players 1,2,3)
    # Each perm is stored as 3 consecutive ints
    var perms = List[Int]()
    perms.append(0); perms.append(1); perms.append(2)
    perms.append(0); perms.append(2); perms.append(1)
    perms.append(1); perms.append(0); perms.append(2)
    perms.append(1); perms.append(2); perms.append(0)
    perms.append(2); perms.append(0); perms.append(1)
    perms.append(2); perms.append(1); perms.append(0)

    for p in range(6):
        var coalition = 0  # bitmask
        for pos in range(3):
            var player = perms[p * 3 + pos]
            var bit = 1 << player
            var new_coalition = coalition | bit
            var marginal = v[new_coalition] - v[coalition]
            phi[player] = phi[player] + marginal
            coalition = new_coalition

    # Average over 6 permutations
    phi[0] = phi[0] / 6.0
    phi[1] = phi[1] / 6.0
    phi[2] = phi[2] / 6.0

    return phi^


# ── pareto_optimal_outcomes ───────────────────────────────────────────────────


fn pareto_optimal_outcomes(payoffs_a: List[Float64], payoffs_b: List[Float64]) -> List[Bool]:
    """Mark Pareto optimal outcomes.

    An outcome i is Pareto optimal if no other outcome j exists where
    payoffs_a[j] >= payoffs_a[i] AND payoffs_b[j] >= payoffs_b[i]
    with at least one strict inequality.

    Args:
        payoffs_a: Player A payoffs for each outcome.
        payoffs_b: Player B payoffs for each outcome.

    Returns:
        List of Bool — True if outcome is Pareto optimal.
    """
    var n = len(payoffs_a)
    var result = List[Bool]()
    for i in range(n):
        var is_optimal = True
        for j in range(n):
            if i == j:
                continue
            # Check if j dominates i
            if payoffs_a[j] >= payoffs_a[i] and payoffs_b[j] >= payoffs_b[i]:
                if payoffs_a[j] > payoffs_a[i] or payoffs_b[j] > payoffs_b[i]:
                    is_optimal = False
                    break
        result.append(is_optimal)
    return result^
