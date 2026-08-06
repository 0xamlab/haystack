"""test_feature_hashing.mojo — known-value tests for feature_hashing.

Expected buckets/signs were hand-computed with an independent reference
implementation of seeded 64-bit FNV-1a (seed folded as 8 LE bytes, then the
UTF-8 bytes of the name; bucket = h mod n_buckets; sign = bit 63 of h).
"""
from feature_hashing import (
    hash_feature,
    hash_sign,
    hash_features_row,
    collision_rate_estimate,
)
from std.math import exp, abs as fabs


def check(cond: Bool, name: String, mut passed: Int, mut failed: Int):
    if cond:
        passed += 1
        print("  ✅ feature_hashing::" + name)
    else:
        failed += 1
        print("  ❌ feature_hashing::" + name)


def _close(a: Float64, b: Float64, tol: Float64) -> Bool:
    return fabs(a - b) <= tol


def main() raises:
    var passed: Int = 0
    var failed: Int = 0

    # ── hash_feature: reference known values ─────────────────────────────
    # seed=42, n_buckets=1000: reference h64("price")=15582674013810968360,
    # h64("volume")=8193776429501787049, h64("side=buy")=6468076673693469017.
    check(
        hash_feature("price", 1000, 42) == 360
        and hash_feature("volume", 1000, 42) == 49
        and hash_feature("side=buy", 1000, 42) == 17,
        "hash_feature reference buckets seed=42 m=1000",
        passed,
        failed,
    )
    # Pin 32 low bits of the raw hash via a 2^32 modulus.
    check(
        hash_feature("price", 4294967296, 42) == 2078918440
        and hash_feature("volume", 4294967296, 42) == 158084009,
        "hash_feature pins h64 mod 2^32 reference values",
        passed,
        failed,
    )
    # seed=0 differs from seed=42: reference buckets at m=8.
    check(
        hash_feature("price", 8, 0) == 2 and hash_feature("price", 8, 42) == 0,
        "hash_feature seed changes bucket (reference: 2 vs 0)",
        passed,
        failed,
    )

    # ── determinism / same name -> same bucket ───────────────────────────
    var same = True
    for _ in range(3):
        if hash_feature("sym=SPY", 1000, 42) != 281:
            same = False
        if hash_sign("sym=SPY", 42) != -1:
            same = False
    check(
        same,
        "determinism: repeated calls identical (bucket 281, sign -1)",
        passed,
        failed,
    )
    var in_range = True
    var toks = List[String]()
    toks.append("a")
    toks.append("b")
    toks.append("c")
    toks.append("d")
    toks.append("e")
    toks.append("f")
    for i in range(len(toks)):
        var b = hash_feature(toks[i], 7, 123)
        if b < 0 or b >= 7:
            in_range = False
        if b != hash_feature(toks[i], 7, 123):
            in_range = False
    check(in_range, "buckets always in [0, n_buckets) and stable", passed, failed)

    # ── hash_sign: reference known values, only +1/-1 ────────────────────
    check(
        hash_sign("price", 42) == -1
        and hash_sign("volume", 42) == 1
        and hash_sign("side=sell", 42) == -1
        and hash_sign("a", 42) == 1
        and hash_sign("side=buy", 0) == -1,
        "hash_sign reference signs",
        passed,
        failed,
    )

    # ── hash_features_row: signed accumulation hand case ─────────────────
    # seed=7, m=4 reference (bucket, sign):
    #   price -> (3, +1), volume -> (0, -1), side=buy -> (0, +1),
    #   bid -> (1, -1), qty -> (2, -1).
    # Expected row: [ -3.0 + 1.0, -4.0, -0.5, +2.0 ] = [-2, -4, -0.5, 2].
    var names = List[String]()
    var vals = List[Float64]()
    names.append("price")
    vals.append(2.0)
    names.append("volume")
    vals.append(3.0)
    names.append("side=buy")
    vals.append(1.0)
    names.append("bid")
    vals.append(4.0)
    names.append("qty")
    vals.append(0.5)
    var row = hash_features_row(names, vals, 4, 7)
    check(
        len(row) == 4
        and _close(row[0], -2.0, 1e-12)
        and _close(row[1], -4.0, 1e-12)
        and _close(row[2], -0.5, 1e-12)
        and _close(row[3], 2.0, 1e-12),
        "hash_features_row signed accumulation hand case",
        passed,
        failed,
    )
    # Exact cancellation: volume (sign -1) and side=buy (sign +1) share
    # bucket 0 at seed=7, m=4; equal values must cancel to 0.
    var cn = List[String]()
    var cv = List[Float64]()
    cn.append("volume")
    cv.append(5.0)
    cn.append("side=buy")
    cv.append(5.0)
    var crow = hash_features_row(cn, cv, 4, 7)
    check(
        _close(crow[0], 0.0, 1e-12)
        and _close(crow[1], 0.0, 1e-12)
        and _close(crow[2], 0.0, 1e-12)
        and _close(crow[3], 0.0, 1e-12),
        "hash_features_row opposite-sign collision cancels",
        passed,
        failed,
    )
    # Row agrees with hash_feature/hash_sign composition.
    var agree = True
    for i in range(len(names)):
        var b = hash_feature(names[i], 4, 7)
        var s = hash_sign(names[i], 7)
        var solo_names = List[String]()
        var solo_vals = List[Float64]()
        solo_names.append(names[i])
        solo_vals.append(1.0)
        var solo = hash_features_row(solo_names, solo_vals, 4, 7)
        if not _close(solo[b], Float64(s), 1e-12):
            agree = False
    check(
        agree,
        "hash_features_row consistent with hash_feature + hash_sign",
        passed,
        failed,
    )

    # ── edge cases ────────────────────────────────────────────────────────
    var eb = hash_feature("", 1000, 42)
    check(
        eb == 255 and eb >= 0 and eb < 1000,
        "empty-string name hashes to reference bucket 255",
        passed,
        failed,
    )
    check(
        hash_feature("anything", 1, 9) == 0
        and hash_feature("else", 1, 9) == 0,
        "n_buckets=1 maps everything to bucket 0",
        passed,
        failed,
    )
    check(
        hash_feature("x", 0, 1) == 0 and hash_feature("x", -3, 1) == 0,
        "n_buckets<=0 returns 0",
        passed,
        failed,
    )
    var empty_row = hash_features_row(List[String](), List[Float64](), 5, 1)
    var all_zero = len(empty_row) == 5
    for i in range(len(empty_row)):
        if empty_row[i] != 0.0:
            all_zero = False
    check(all_zero, "empty input row -> all-zero row of n_buckets", passed, failed)
    check(
        len(hash_features_row(List[String](), List[Float64](), 0, 1)) == 0,
        "row with n_buckets<=0 -> empty list",
        passed,
        failed,
    )
    # Mismatched lengths: extra values ignored (min length processed).
    var mn = List[String]()
    mn.append("price")
    var mv = List[Float64]()
    mv.append(1.0)
    mv.append(99.0)
    var mrow = hash_features_row(mn, mv, 4, 7)
    check(
        _close(mrow[3], 1.0, 1e-12)
        and _close(mrow[0], 0.0, 1e-12)
        and _close(mrow[1], 0.0, 1e-12)
        and _close(mrow[2], 0.0, 1e-12),
        "mismatched lengths process min(len(names), len(values))",
        passed,
        failed,
    )
    # Ties/all-equal: repeated identical name accumulates in one bucket.
    var rn = List[String]()
    var rv = List[Float64]()
    for _ in range(3):
        rn.append("price")
        rv.append(2.0)
    var rrow = hash_features_row(rn, rv, 4, 7)  # price -> (3, +1)
    check(
        _close(rrow[3], 6.0, 1e-12) and _close(rrow[0], 0.0, 1e-12),
        "repeated identical name accumulates 3 * 2.0 = 6.0",
        passed,
        failed,
    )

    # ── collision_rate_estimate ──────────────────────────────────────────
    # Birthday paradox: 23 features, 365 buckets -> 1 - exp(-23*22/730)
    # = 0.5000017521827107.
    check(
        _close(collision_rate_estimate(23, 365), 0.5000017521827107, 1e-12),
        "collision estimate matches birthday formula (23, 365)",
        passed,
        failed,
    )
    check(
        _close(collision_rate_estimate(100, 1000), 0.9929165910709479, 1e-12),
        "collision estimate matches formula (100, 1000)",
        passed,
        failed,
    )
    check(
        collision_rate_estimate(50, 1000) < collision_rate_estimate(100, 1000),
        "collision estimate monotone in n_features",
        passed,
        failed,
    )
    check(
        collision_rate_estimate(0, 100) == 0.0
        and collision_rate_estimate(1, 100) == 0.0,
        "n_features<=1 -> 0.0",
        passed,
        failed,
    )
    check(
        collision_rate_estimate(101, 100) == 1.0
        and collision_rate_estimate(2, 0) == 1.0
        and collision_rate_estimate(2, -5) == 1.0,
        "pigeonhole / no-bucket cases -> 1.0",
        passed,
        failed,
    )

    print("  [feature_hashing] Passed:", passed, "Failed:", failed)
