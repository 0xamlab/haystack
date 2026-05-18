"""
lottery.mojo — Lottery / Combinatorial Probability Library. Zero Python imports.

Provides combinatorics, odds, expected value, and payout calculations.

Public API:
  combinations              — C(n,k) iterative
  permutations              — P(n,k) iterative
  lottery_odds              — Odds = C(total,drawn) * bonus
  expected_value            — EV = prize * probability
  expected_value_net        — Net EV = Σ(EV) - cost
  house_edge                — HE = (cost - return) / cost * 100
  probability_at_least_one_win — P = 1 - (1-p)^n
  annuity_vs_lump_sum       — PV = payment * (1-(1+r)^(-n))/r
  tax_after_winnings        — Net = gross * (1 - fed - state)
  odds_to_probability       — P = 1 / (odds + 1)
  probability_to_odds       — Odds = (1 - p) / p
  jackpot_ev_threshold      — Threshold = odds * cost
"""
from std.math import exp, log, abs as fabs


# ── combinations ─────────────────────────────────────────────────────────────


fn combinations(n: Int, k: Int) -> Float64:
    """C(n,k) = n! / (k!(n-k)!) computed iteratively to avoid overflow.

    Args:
        n: Total items.
        k: Items chosen.

    Returns:
        Number of combinations as Float64.
    """
    if k < 0 or k > n:
        return 0.0
    var kk = k
    if kk > n - kk:
        kk = n - kk
    var result: Float64 = 1.0
    for i in range(kk):
        result = result * Float64(n - i) / Float64(i + 1)
    return result


# ── permutations ─────────────────────────────────────────────────────────────


fn permutations(n: Int, k: Int) -> Float64:
    """P(n,k) = n! / (n-k)! computed iteratively.

    Args:
        n: Total items.
        k: Items chosen.

    Returns:
        Number of permutations as Float64.
    """
    if k < 0 or k > n:
        return 0.0
    var result: Float64 = 1.0
    for i in range(k):
        result = result * Float64(n - i)
    return result


# ── lottery_odds ─────────────────────────────────────────────────────────────


fn lottery_odds(
    total_numbers: Int, drawn: Int, bonus: Int
) -> Float64:
    """Lottery odds: Odds = C(total, drawn) * bonus.

    Args:
        total_numbers: Total numbers in the pool.
        drawn: Numbers drawn.
        bonus: Bonus pool size (use 1 for no bonus ball).

    Returns:
        Total number of possible outcomes (1-in-X odds).
    """
    return combinations(total_numbers, drawn) * Float64(bonus)


# ── expected_value ───────────────────────────────────────────────────────────


fn expected_value(prize: Float64, probability: Float64) -> Float64:
    """Expected value: EV = prize * probability.

    Args:
        prize: Prize amount.
        probability: Probability of winning.

    Returns:
        Expected value.
    """
    return prize * probability


# ── expected_value_net ───────────────────────────────────────────────────────


fn expected_value_net(
    prizes_ev_sum: Float64, ticket_cost: Float64
) -> Float64:
    """Net expected value: Net EV = Σ(EV) - cost.

    Args:
        prizes_ev_sum: Sum of all prize expected values.
        ticket_cost: Cost of one ticket.

    Returns:
        Net expected value per ticket.
    """
    return prizes_ev_sum - ticket_cost


# ── house_edge ───────────────────────────────────────────────────────────────


fn house_edge(
    expected_return: Float64, ticket_cost: Float64
) -> Float64:
    """House edge: HE = (cost - return) / cost * 100 (%).

    Args:
        expected_return: Expected return per ticket.
        ticket_cost: Ticket cost.

    Returns:
        House edge (%).
    """
    if fabs(ticket_cost) < 1e-30:
        return 0.0
    return (ticket_cost - expected_return) / ticket_cost * 100.0


# ── probability_at_least_one_win ─────────────────────────────────────────────


fn probability_at_least_one_win(
    p_single: Float64, n_tickets: Int
) -> Float64:
    """P(at least one win) = 1 - (1 - p)^n.

    Args:
        p_single: Probability of winning with one ticket.
        n_tickets: Number of tickets purchased.

    Returns:
        Probability of at least one win.
    """
    if n_tickets <= 0:
        return 0.0
    var q = 1.0 - p_single
    # Use exp/log for large n to avoid precision loss
    return 1.0 - exp(Float64(n_tickets) * log(q))


# ── annuity_vs_lump_sum ─────────────────────────────────────────────────────


fn annuity_vs_lump_sum(
    annual_payment: Float64, years: Float64, discount_rate: Float64
) -> Float64:
    """Present value of annuity: PV = payment * (1 - (1+r)^(-n)) / r.

    Args:
        annual_payment: Annual payment amount.
        years: Number of years.
        discount_rate: Annual discount rate (e.g. 0.05 for 5%).

    Returns:
        Present value of the annuity.
    """
    if fabs(discount_rate) < 1e-30:
        return annual_payment * years
    var factor = 1.0 - exp(-years * log(1.0 + discount_rate))
    return annual_payment * factor / discount_rate


# ── tax_after_winnings ───────────────────────────────────────────────────────


fn tax_after_winnings(
    gross: Float64, federal_rate: Float64, state_rate: Float64
) -> Float64:
    """Net after taxes: Net = gross * (1 - federal - state).

    Args:
        gross: Gross winnings.
        federal_rate: Federal tax rate (e.g. 0.24).
        state_rate: State tax rate (e.g. 0.05).

    Returns:
        Net winnings after taxes.
    """
    return gross * (1.0 - federal_rate - state_rate)


# ── odds_to_probability ─────────────────────────────────────────────────────


fn odds_to_probability(odds_against: Float64) -> Float64:
    """Convert odds-against to probability: P = 1 / (odds + 1).

    Args:
        odds_against: Odds against winning (e.g. 9 means 9-to-1).

    Returns:
        Probability of winning.
    """
    return 1.0 / (odds_against + 1.0)


# ── probability_to_odds ─────────────────────────────────────────────────────


fn probability_to_odds(probability: Float64) -> Float64:
    """Convert probability to odds-against: Odds = (1 - p) / p.

    Args:
        probability: Probability of winning.

    Returns:
        Odds against winning.
    """
    if fabs(probability) < 1e-30:
        return 0.0
    return (1.0 - probability) / probability


# ── jackpot_ev_threshold ─────────────────────────────────────────────────────


fn jackpot_ev_threshold(
    jackpot_odds: Float64, ticket_cost: Float64
) -> Float64:
    """Jackpot threshold for +EV: Threshold = odds * cost.

    The jackpot must exceed this value for positive expected value.

    Args:
        jackpot_odds: 1-in-X odds of jackpot.
        ticket_cost: Ticket cost.

    Returns:
        Minimum jackpot for +EV play.
    """
    return jackpot_odds * ticket_cost
