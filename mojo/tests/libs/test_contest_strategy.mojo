"""test_contest_strategy.mojo — the CRN option board.

The load-bearing assertions are DETERMINISM, CRN PAIRING and ABSTENTION. Directional sanity (old tyres
favour boxing, four laps left do not) matters too, but those would still pass with broken pairing; the
variance-ratio and identical-world checks are what prove the invariant actually holds.
"""
from std.math import isnan, isinf
from contest_strategy import (
    option_board,
    default_contest_params,
    option_service_round,
    contest_strategy_version,
    OPT_STAY,
    OPT_BOX_NOW,
    OPT_BOX_1,
    OPT_BOX_2,
    N_OPTIONS,
    VERDICT_RECOMMENDED,
    VERDICT_INCONCLUSIVE,
    P_PIT_LOSS,
    P_EPSILON,
    N_PARAMS,
)


fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)


fn field(focal_age: Float64, rival_age: Float64) -> List[List[Float64]]:
    """Eight-car field; focal index 3, rival index 2 directly ahead by 1.5 s."""
    var pace = List[Float64]()
    var deg = List[Float64]()
    var el = List[Float64]()
    var age = List[Float64]()
    var act = List[Float64]()
    var bases = List[Float64]()
    bases.append(83.8)
    bases.append(83.9)
    bases.append(84.0)
    bases.append(84.0)
    bases.append(84.2)
    bases.append(84.4)
    bases.append(84.6)
    bases.append(84.9)
    for i in range(8):
        pace.append(bases[i])
        deg.append(0.06)
        act.append(1.0)
        if i == 3:
            age.append(focal_age)
            el.append(11.5)
        elif i == 2:
            age.append(rival_age)
            el.append(10.0)
        else:
            age.append(rival_age)
            el.append(10.0 + Float64(i) * 4.0)
    var out = List[List[Float64]]()
    out.append(pace^)
    out.append(deg^)
    out.append(el^)
    out.append(age^)
    out.append(act^)
    return out^


def main() raises:
    var failures = 0

    if contest_strategy_version() != String("contest-strategy-crn/v1"):
        print("FAIL version", contest_strategy_version())
        failures += 1
    var p = default_contest_params()
    if len(p) != N_PARAMS or p[P_PIT_LOSS] != 21.0:
        print("FAIL default params")
        failures += 1
    if option_service_round(OPT_STAY) != -1 or option_service_round(OPT_BOX_NOW) != 0:
        print("FAIL option_service_round", option_service_round(OPT_STAY), option_service_round(OPT_BOX_NOW))
        failures += 1
    if option_service_round(OPT_BOX_1) != 1 or option_service_round(OPT_BOX_2) != 2:
        print("FAIL option_service_round offsets")
        failures += 1

    # ── determinism: identical inputs, identical board ────────────────────────
    var f = field(24.0, 10.0)
    var a = option_board(f[0], f[1], f[2], f[3], f[4], 3, 2, 25, p, 2000, 200, 42, 11)
    var b = option_board(f[0], f[1], f[2], f[3], f[4], 3, 2, 25, p, 2000, 200, 42, 11)
    for o in range(N_OPTIONS):
        if a.p_ahead[o] != b.p_ahead[o] or a.delta_vs_stay[o] != b.delta_vs_stay[o]:
            print("FAIL not deterministic at option", o)
            failures += 1
    if a.recommended != b.recommended or a.verdict != b.verdict:
        print("FAIL verdict not deterministic")
        failures += 1

    # a different scenario_id must draw a different world
    var c = option_board(f[0], f[1], f[2], f[3], f[4], 3, 2, 25, p, 2000, 200, 42, 12)
    var any_diff = False
    for o in range(N_OPTIONS):
        if a.p_ahead[o] != c.p_ahead[o]:
            any_diff = True
    if not any_diff:
        print("FAIL scenario_id did not change the sampled world")
        failures += 1

    # ── CRN pairing must reduce contrast variance ─────────────────────────────
    # Below 1.0 means the paired contrast is tighter than independent sampling would give. If the
    # option index ever leaked into the RNG coordinates this would sit at or above 1.0.
    if a.crn_variance_ratio > 1.0:
        print("FAIL CRN gave no variance reduction, ratio", a.crn_variance_ratio)
        failures += 1
    if not is_finite(a.crn_variance_ratio):
        print("FAIL CRN ratio not finite")
        failures += 1

    # ── stay is its own baseline ──────────────────────────────────────────────
    if a.delta_vs_stay[OPT_STAY] != 0.0:
        print("FAIL stay delta not zero", a.delta_vs_stay[OPT_STAY])
        failures += 1

    # ── output well-formedness ────────────────────────────────────────────────
    for o in range(N_OPTIONS):
        if a.p_ahead[o] < 0.0 or a.p_ahead[o] > 1.0:
            print("FAIL p_ahead out of range", o, a.p_ahead[o])
            failures += 1
        if a.p_win[o] < 0.0 or a.p_win[o] > 1.0 or a.p_podium[o] < a.p_win[o]:
            print("FAIL win/podium inconsistent at", o, a.p_win[o], a.p_podium[o])
            failures += 1
        if a.ci_lo[o] > a.ci_hi[o]:
            print("FAIL inverted interval at", o)
            failures += 1
        if a.expected_position[o] < 1.0:
            print("FAIL expected position below 1", a.expected_position[o])
            failures += 1
    if a.n_replications != 2000:
        print("FAIL replication count", a.n_replications)
        failures += 1

    # ── directional sanity ───────────────────────────────────────────────────
    # Four laps left: a ~21 s pit loss cannot be recovered, so boxing must not be recommended.
    var g = field(24.0, 10.0)
    var short = option_board(g[0], g[1], g[2], g[3], g[4], 3, 2, 4, p, 2000, 200, 42, 11)
    if short.recommended != OPT_STAY:
        print("FAIL recommended a stop with 4 laps left", short.recommended)
        failures += 1
    # and boxing must not look BETTER than staying over so short a horizon
    if short.delta_vs_stay[OPT_BOX_NOW] > 0.02:
        print("FAIL boxing looked good with 4 laps left", short.delta_vs_stay[OPT_BOX_NOW])
        failures += 1

    # ── abstention: an interval straddling epsilon must abstain ───────────────
    # Verified on a real configuration: delta +0.0218 with a simultaneous interval of
    # [0.0165, 0.0270] crosses epsilon = 0.02, so the practical bar genuinely cannot be called.
    var straddles = False
    for o in range(OPT_BOX_NOW, N_OPTIONS):
        if a.ci_lo[o] <= p[P_EPSILON] and a.ci_hi[o] >= p[P_EPSILON]:
            straddles = True
    if straddles and a.verdict != VERDICT_INCONCLUSIVE:
        print("FAIL interval straddles epsilon but verdict is not INCONCLUSIVE")
        failures += 1
    if a.verdict != VERDICT_RECOMMENDED and a.verdict != VERDICT_INCONCLUSIVE:
        print("FAIL unknown verdict", a.verdict)
        failures += 1

    # ── intervals must tighten with N ────────────────────────────────────────
    var lo_n = option_board(f[0], f[1], f[2], f[3], f[4], 3, 2, 25, p, 500, 200, 42, 11)
    var hi_n = option_board(f[0], f[1], f[2], f[3], f[4], 3, 2, 25, p, 8000, 200, 42, 11)
    var w_lo = lo_n.ci_hi[OPT_BOX_NOW] - lo_n.ci_lo[OPT_BOX_NOW]
    var w_hi = hi_n.ci_hi[OPT_BOX_NOW] - hi_n.ci_lo[OPT_BOX_NOW]
    if w_hi > w_lo:
        print("FAIL interval did not tighten with N:", w_lo, "->", w_hi)
        failures += 1

    if failures == 0:
        print("test_contest_strategy: PASS")
    else:
        print("test_contest_strategy: FAILURES =", failures)
        raise Error("test_contest_strategy failed")
