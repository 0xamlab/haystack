"""test_automl.mojo — known-value tests for automl (SHA / Hyperband / LHS)."""
from automl import (
    HalvingRound,
    Bracket,
    successive_halving_schedule,
    hyperband_brackets,
    promote_top_k,
    random_search_configs,
)


def _rounds_equal(
    rounds: List[HalvingRound], ns: List[Int], bs: List[Int]
) -> Bool:
    if len(rounds) != len(ns) or len(ns) != len(bs):
        return False
    for i in range(len(rounds)):
        if rounds[i].n_survivors != ns[i] or rounds[i].budget != bs[i]:
            return False
    return True


def _ints_equal(a: List[Int], b: List[Int]) -> Bool:
    if len(a) != len(b):
        return False
    for i in range(len(a)):
        if a[i] != b[i]:
            return False
    return True


def check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ automl::" + name)
    else:
        failed += 1
        print("  ❌ automl::" + name)


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── successive_halving_schedule: spec case n=27, eta=3 ──────────────────
    # Exactly (27,1), (9,3), (3,9), (1,27).
    var sha = successive_halving_schedule(27, 1, 3)
    var ns27: List[Int] = [27, 9, 3, 1]
    var bs27: List[Int] = [1, 3, 9, 27]
    check(len(sha) == 4, "sha n=27 eta=3 has 4 rounds", passed, failed)
    check(
        _rounds_equal(sha, ns27, bs27),
        "sha n=27 eta=3 rounds exact (27,1)(9,3)(3,9)(1,27)",
        passed,
        failed,
    )

    # min_budget scales every round: min_budget=2 -> budgets 2,6,18,54
    var sha2 = successive_halving_schedule(27, 2, 3)
    var bs27x2: List[Int] = [2, 6, 18, 54]
    check(
        _rounds_equal(sha2, ns27, bs27x2),
        "sha min_budget=2 scales budgets exact",
        passed,
        failed,
    )

    # non-power-of-eta n floors: n=10 eta=3 -> (10,1),(3,3),(1,9)
    var sha10 = successive_halving_schedule(10, 1, 3)
    var ns10: List[Int] = [10, 3, 1]
    var bs10: List[Int] = [1, 3, 9]
    check(
        _rounds_equal(sha10, ns10, bs10),
        "sha n=10 eta=3 floors to (10,1)(3,3)(1,9)",
        passed,
        failed,
    )

    # n=1 -> single round at min_budget; n < eta -> single round
    var sha1 = successive_halving_schedule(1, 5, 3)
    var sha_small = successive_halving_schedule(2, 1, 3)
    check(
        len(sha1) == 1
        and sha1[0].n_survivors == 1
        and sha1[0].budget == 5
        and len(sha_small) == 1
        and sha_small[0].n_survivors == 2
        and sha_small[0].budget == 1,
        "sha n=1 and n<eta -> single round",
        passed,
        failed,
    )

    # invalid inputs -> empty schedule
    check(
        len(successive_halving_schedule(0, 1, 3)) == 0
        and len(successive_halving_schedule(27, 0, 3)) == 0
        and len(successive_halving_schedule(27, 1, 1)) == 0,
        "sha invalid inputs -> empty",
        passed,
        failed,
    )

    # ── hyperband_brackets: spec case max_budget=81, eta=3 ──────────────────
    # s_max = 4 -> exactly 5 brackets, ordered s = 4,3,2,1,0.
    var hb = hyperband_brackets(81, 3)
    check(len(hb) == 5, "hyperband R=81 eta=3 -> 5 brackets", passed, failed)
    check(
        hb[0].s == 4
        and hb[1].s == 3
        and hb[2].s == 2
        and hb[3].s == 1
        and hb[4].s == 0,
        "hyperband bracket order s=4..0",
        passed,
        failed,
    )
    # canonical (n_s, r_s): (81,1), (34,3), (15,9), (8,27), (5,81)
    check(
        hb[0].n_configs == 81
        and hb[0].min_budget == 1
        and hb[1].n_configs == 34
        and hb[1].min_budget == 3
        and hb[2].n_configs == 15
        and hb[2].min_budget == 9
        and hb[3].n_configs == 8
        and hb[3].min_budget == 27
        and hb[4].n_configs == 5
        and hb[4].min_budget == 81,
        "hyperband (n_s, r_s) exact (81,1)(34,3)(15,9)(8,27)(5,81)",
        passed,
        failed,
    )
    # bracket s=4 embeds the full SHA schedule (81,1)(27,3)(9,9)(3,27)(1,81)
    var ns_b0: List[Int] = [81, 27, 9, 3, 1]
    var bs_b0: List[Int] = [1, 3, 9, 27, 81]
    check(
        _rounds_equal(hb[0].rounds, ns_b0, bs_b0),
        "hyperband s=4 rounds exact (81,1)..(1,81)",
        passed,
        failed,
    )
    # bracket s=3: n=34 -> (34,3)(11,9)(3,27)(1,81); every bracket's final
    # round runs at max_budget
    var ns_b1: List[Int] = [34, 11, 3, 1]
    var bs_b1: List[Int] = [3, 9, 27, 81]
    check(
        _rounds_equal(hb[1].rounds, ns_b1, bs_b1),
        "hyperband s=3 rounds exact (34,3)(11,9)(3,27)(1,81)",
        passed,
        failed,
    )
    var all_final_81 = True
    for i in range(len(hb)):
        var last_i = len(hb[i].rounds) - 1
        if (
            hb[i].rounds[last_i].budget != 81
            or hb[i].rounds[last_i].n_survivors < 1
        ):
            all_final_81 = False
    check(
        all_final_81,
        "hyperband every bracket ends at budget=81 with >=1 survivor",
        passed,
        failed,
    )
    # s=0 bracket is plain random search: 1 round of (5, 81)
    check(
        len(hb[4].rounds) == 1
        and hb[4].rounds[0].n_survivors == 5
        and hb[4].rounds[0].budget == 81,
        "hyperband s=0 bracket = single round (5,81)",
        passed,
        failed,
    )
    # R=1 -> single bracket (s=0, n=1, r=1); invalid -> empty
    var hb1 = hyperband_brackets(1, 3)
    check(
        len(hb1) == 1
        and hb1[0].s == 0
        and hb1[0].n_configs == 1
        and hb1[0].min_budget == 1
        and len(hyperband_brackets(0, 3)) == 0
        and len(hyperband_brackets(81, 1)) == 0,
        "hyperband R=1 single bracket; invalid -> empty",
        passed,
        failed,
    )

    # ── promote_top_k: deterministic tie-break by index ──────────────────────
    # scores [0.5, 0.9, 0.5, 0.7], k=3: 0.9@1, 0.7@3, then tie 0.5@{0,2}
    # broken toward lower index -> [1, 3, 0]
    var scores: List[Float64] = [0.5, 0.9, 0.5, 0.7]
    var top3 = promote_top_k(scores, 3)
    var want3: List[Int] = [1, 3, 0]
    check(_ints_equal(top3, want3), "promote_top_k tie-break -> [1,3,0]", passed, failed)

    # all-equal scores: rank order degenerates to index order
    var flat: List[Float64] = [1.0, 1.0, 1.0]
    var top2 = promote_top_k(flat, 2)
    var want2: List[Int] = [0, 1]
    check(
        _ints_equal(top2, want2),
        "promote_top_k all-tied -> [0,1]",
        passed,
        failed,
    )

    # k clamps to n; k=0 -> empty
    var topall = promote_top_k(scores, 99)
    var wantall: List[Int] = [1, 3, 0, 2]
    check(
        _ints_equal(topall, wantall) and len(promote_top_k(scores, 0)) == 0,
        "promote_top_k k>n clamps, k=0 empty",
        passed,
        failed,
    )

    # ── random_search_configs: LHS properties ────────────────────────────────
    var n = 8
    var dims = 3
    var cfg = random_search_configs(n, dims, 42)
    check(
        len(cfg) == n and len(cfg[0]) == dims,
        "lhs shape 8x3",
        passed,
        failed,
    )
    var in_bounds = True
    for i in range(n):
        for d in range(dims):
            if cfg[i][d] < 0.0 or cfg[i][d] >= 1.0:
                in_bounds = False
    check(in_bounds, "lhs all values in [0,1)", passed, failed)

    # stratification: per dim, floor(v * n) hits each stratum exactly once
    var stratified = True
    for d in range(dims):
        var seen = List[Int]()
        for _ in range(n):
            seen.append(0)
        for i in range(n):
            var stratum = Int(cfg[i][d] * Float64(n))
            if stratum < 0 or stratum >= n:
                stratified = False
            else:
                seen[stratum] += 1
        for j in range(n):
            if seen[j] != 1:
                stratified = False
    check(
        stratified,
        "lhs each of n strata hit exactly once per dim",
        passed,
        failed,
    )

    # determinism: same seed -> identical matrix; different seed -> differs
    var cfg_same = random_search_configs(n, dims, 42)
    var cfg_diff = random_search_configs(n, dims, 43)
    var same = True
    var diff = False
    for i in range(n):
        for d in range(dims):
            if cfg[i][d] != cfg_same[i][d]:
                same = False
            if cfg[i][d] != cfg_diff[i][d]:
                diff = True
    check(same, "lhs seed=42 reproducible", passed, failed)
    check(diff, "lhs seed=43 differs from seed=42", passed, failed)

    # degenerate inputs -> empty
    check(
        len(random_search_configs(0, 3, 1)) == 0
        and len(random_search_configs(3, 0, 1)) == 0,
        "lhs n=0 or dims=0 -> empty",
        passed,
        failed,
    )

    print("  [automl] Passed:", passed, "Failed:", failed)
