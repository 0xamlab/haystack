"""
sports_analytics.mojo — Sports Analytics Library. Zero Python imports.

Pure Mojo implementations of fundamental sports analytics equations
including baseball statistics, NFL passer rating, Pythagorean wins,
Elo ratings, and basketball efficiency metrics.

Public API:
  batting_average                  — BA = H/AB
  on_base_percentage               — OBP = (H+BB+HBP)/(AB+BB+HBP+SF)
  slugging_percentage              — SLG = TB/AB
  ops                              — OPS = OBP + SLG
  era                              — ERA = (ER/IP) * 9
  whip                             — WHIP = (BB+H)/IP
  passer_rating_nfl                — simplified NFL passer rating
  pythagorean_wins                 — W% = RS^e / (RS^e + RA^e)
  elo_expected_score               — E = 1/(1+10^((Rb-Ra)/400))
  elo_new_rating                   — R' = R + K*(S-E)
  true_shooting_percentage         — TS% = PTS/(2*(FGA+0.44*FTA))
  player_efficiency_rating_approx  — simplified PER
"""
from std.math import sqrt, exp, log, abs as fabs


# ── batting_average ──────────────────────────────────────────────────────────


def batting_average(hits: Float64, at_bats: Float64) -> Float64:
    """BA = H / AB."""
    if at_bats == 0.0:
        return 0.0
    return hits / at_bats


# ── on_base_percentage ───────────────────────────────────────────────────────


def on_base_percentage(
    hits: Float64,
    walks: Float64,
    hbp: Float64,
    at_bats: Float64,
    sf: Float64,
) -> Float64:
    """OBP = (H + BB + HBP) / (AB + BB + HBP + SF)."""
    var denom = at_bats + walks + hbp + sf
    if denom == 0.0:
        return 0.0
    return (hits + walks + hbp) / denom


# ── slugging_percentage ──────────────────────────────────────────────────────


def slugging_percentage(total_bases: Float64, at_bats: Float64) -> Float64:
    """SLG = TB / AB."""
    if at_bats == 0.0:
        return 0.0
    return total_bases / at_bats


# ── ops ──────────────────────────────────────────────────────────────────────


def ops(obp: Float64, slg: Float64) -> Float64:
    """OPS = OBP + SLG."""
    return obp + slg


# ── era ──────────────────────────────────────────────────────────────────────


def era(earned_runs: Float64, innings_pitched: Float64) -> Float64:
    """ERA = (ER / IP) * 9."""
    if innings_pitched == 0.0:
        return 0.0
    return (earned_runs / innings_pitched) * 9.0


# ── whip ─────────────────────────────────────────────────────────────────────


def whip(
    walks: Float64, hits: Float64, innings_pitched: Float64
) -> Float64:
    """WHIP = (BB + H) / IP."""
    if innings_pitched == 0.0:
        return 0.0
    return (walks + hits) / innings_pitched


# ── passer_rating_nfl ────────────────────────────────────────────────────────


def passer_rating_nfl(
    comp: Float64,
    att: Float64,
    yards: Float64,
    td: Float64,
    interceptions: Float64,
) -> Float64:
    """Simplified NFL passer rating.
    a = (comp/att - 0.3) * 5
    b = (yards/att - 3) * 0.25
    c = (td/att) * 20
    d = 2.375 - (int/att) * 25
    Each clamped [0, 2.375]. Rating = (a+b+c+d)/6 * 100."""
    if att == 0.0:
        return 0.0
    var a = (comp / att - 0.3) * 5.0
    var b = (yards / att - 3.0) * 0.25
    var c = (td / att) * 20.0
    var d = 2.375 - (interceptions / att) * 25.0
    # Clamp each component to [0, 2.375]
    if a < 0.0:
        a = 0.0
    if a > 2.375:
        a = 2.375
    if b < 0.0:
        b = 0.0
    if b > 2.375:
        b = 2.375
    if c < 0.0:
        c = 0.0
    if c > 2.375:
        c = 2.375
    if d < 0.0:
        d = 0.0
    if d > 2.375:
        d = 2.375
    return (a + b + c + d) / 6.0 * 100.0


# ── pythagorean_wins ─────────────────────────────────────────────────────────


def pythagorean_wins(
    runs_scored: Float64, runs_allowed: Float64, exponent: Float64
) -> Float64:
    """W% = RS^e / (RS^e + RA^e)."""
    if runs_scored <= 0.0 and runs_allowed <= 0.0:
        return 0.0
    if runs_scored <= 0.0:
        return 0.0
    if runs_allowed <= 0.0:
        return 1.0
    var rs_e = exp(exponent * log(runs_scored))
    var ra_e = exp(exponent * log(runs_allowed))
    var denom = rs_e + ra_e
    if denom == 0.0:
        return 0.0
    return rs_e / denom


# ── elo_expected_score ───────────────────────────────────────────────────────


def elo_expected_score(rating_a: Float64, rating_b: Float64) -> Float64:
    """E = 1 / (1 + 10^((Rb - Ra) / 400))."""
    var exponent = (rating_b - rating_a) / 400.0
    return 1.0 / (1.0 + exp(exponent * log(10.0)))


# ── elo_new_rating ───────────────────────────────────────────────────────────


def elo_new_rating(
    old_rating: Float64,
    k: Float64,
    actual_score: Float64,
    expected_score: Float64,
) -> Float64:
    """R' = R + K * (S - E)."""
    return old_rating + k * (actual_score - expected_score)


# ── true_shooting_percentage ─────────────────────────────────────────────────


def true_shooting_percentage(
    points: Float64, fga: Float64, fta: Float64
) -> Float64:
    """TS% = PTS / (2 * (FGA + 0.44 * FTA))."""
    var denom = 2.0 * (fga + 0.44 * fta)
    if denom == 0.0:
        return 0.0
    return points / denom


# ── player_efficiency_rating_approx ─────────────────────────────────────────


def player_efficiency_rating_approx(
    points: Float64,
    rebounds: Float64,
    assists: Float64,
    steals: Float64,
    blocks: Float64,
    turnovers: Float64,
    minutes: Float64,
    pace: Float64,
) -> Float64:
    """Simplified PER ≈ (PTS+REB+AST+STL+BLK-TO) / MIN * pace_factor.
    pace_factor normalises to league pace (e.g., pace/100)."""
    if minutes == 0.0:
        return 0.0
    var raw = points + rebounds + assists + steals + blocks - turnovers
    var pace_factor = pace / 100.0
    return (raw / minutes) * pace_factor
