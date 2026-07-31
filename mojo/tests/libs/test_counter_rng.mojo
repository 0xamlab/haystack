"""test_counter_rng.mojo — hand-written tests for counter_rng (philox4x64-10/v1).

Not auto-generated. The critical test here is CRN order-independence: a draw must be a pure
function of its coordinates, so the same logical draw is identical no matter what a trajectory
did beforehand. That is the property valid common random numbers rest on, and it is the one
that silently breaks if the layout or word selection ever changes.

Known-answer vectors are cross-validated against a spec-faithful Python Philox4x64-10 and,
under a documented pre-increment offset, against numpy's reference bit generator — see
scripts/timing/validate_rng.py.
"""
from std.math import isnan, isinf, sqrt
from counter_rng import (
    philox_word,
    rng_uniform,
    rng_uniform_left_open,
    rng_normal,
    rng_bernoulli,
    rng_exponential,
    rng_version,
    rng_global_sentinel,
    rng_selftest,
    PROCESS_LAP_NOISE,
    PROCESS_PIT_SERVICE,
    PROCESS_SAFETY_CAR,
)

# Reference vectors: master_seed=1 scenario=2 replication=3 lap=4 car=5 process=4, draw 0..7
alias EXPECT_0: UInt64 = 5544217767837969664
alias EXPECT_1: UInt64 = 2756644627510874722
alias EXPECT_2: UInt64 = 11377611935976986105
alias EXPECT_3: UInt64 = 707596276828718816
alias EXPECT_4: UInt64 = 3838836558764994255
alias EXPECT_5: UInt64 = 5772761546685886677
alias EXPECT_6: UInt64 = 502729060365814170
alias EXPECT_7: UInt64 = 8147541987183208929
alias EXPECT_SELFTEST: UInt64 = 13066461341573311292


fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)


def main() raises:
    var failures = 0

    # ── known-answer vectors ──────────────────────────────────────────────────
    var expected = List[UInt64]()
    expected.append(EXPECT_0)
    expected.append(EXPECT_1)
    expected.append(EXPECT_2)
    expected.append(EXPECT_3)
    expected.append(EXPECT_4)
    expected.append(EXPECT_5)
    expected.append(EXPECT_6)
    expected.append(EXPECT_7)
    for i in range(8):
        var got = philox_word(1, 2, 3, 4, 5, PROCESS_LAP_NOISE, UInt64(i))
        if got != expected[i]:
            print("FAIL known-answer draw", i, "got", got, "want", expected[i])
            failures += 1

    if rng_selftest() != EXPECT_SELFTEST:
        print("FAIL rng_selftest", rng_selftest(), "want", EXPECT_SELFTEST)
        failures += 1
    if rng_version() != String("philox4x64-10/v1"):
        print("FAIL rng_version", rng_version())
        failures += 1
    if rng_global_sentinel() != 0xFFFF:
        print("FAIL rng_global_sentinel", rng_global_sentinel())
        failures += 1

    # ── CRN order-independence: the load-bearing property ─────────────────────
    # Simulate two "options" that diverge. Option A walks laps 1..20 for car 5.
    # Option B walks the same laps but interleaves a different number of extra
    # draws for other cars first (as a pitting option would). The lap-noise value
    # for (car 5, lap L) must be identical under both.
    var a_vals = List[Float64]()
    for lap in range(1, 21):
        a_vals.append(rng_uniform(9, 77, 42, UInt64(lap), 5, PROCESS_LAP_NOISE, 0))

    var burned: Float64 = 0.0
    var b_vals = List[Float64]()
    for lap in range(1, 21):
        # burn a trajectory-dependent number of unrelated draws before the real one
        for extra in range(lap * 3):
            burned += rng_uniform(9, 77, 42, UInt64(lap), 7, PROCESS_PIT_SERVICE, UInt64(extra))
        b_vals.append(rng_uniform(9, 77, 42, UInt64(lap), 5, PROCESS_LAP_NOISE, 0))

    for i in range(20):
        if a_vals[i] != b_vals[i]:
            print("FAIL CRN divergence at lap", i + 1, a_vals[i], "!=", b_vals[i])
            failures += 1
    if not is_finite(burned):
        print("FAIL burned draws non-finite")
        failures += 1

    # ── exogenous global processes are shared across cars ─────────────────────
    # A global SC draw must not depend on car_id: it uses the sentinel.
    var sc1 = rng_uniform(9, 77, 42, 12, rng_global_sentinel(), PROCESS_SAFETY_CAR, 0)
    var sc2 = rng_uniform(9, 77, 42, 12, rng_global_sentinel(), PROCESS_SAFETY_CAR, 0)
    if sc1 != sc2:
        print("FAIL global SC draw not reproducible")
        failures += 1

    # ── process isolation: different process_id must not collide ──────────────
    var p_noise = rng_uniform(9, 77, 42, 12, 5, PROCESS_LAP_NOISE, 0)
    var p_pit = rng_uniform(9, 77, 42, 12, 5, PROCESS_PIT_SERVICE, 0)
    if p_noise == p_pit:
        print("FAIL process_id collision")
        failures += 1

    # ── uniform support and moments ───────────────────────────────────────────
    var n = 60000
    var s: Float64 = 0.0
    var lo: Float64 = 2.0
    var hi: Float64 = -1.0
    for i in range(n):
        var u = rng_uniform(11, 22, UInt64(i), 4, 5, PROCESS_LAP_NOISE, 0)
        s += u
        if u < lo:
            lo = u
        if u > hi:
            hi = u
    var umean = s / Float64(n)
    if umean < 0.49 or umean > 0.51:
        print("FAIL uniform mean", umean)
        failures += 1
    if lo < 0.0 or hi >= 1.0:
        print("FAIL uniform support", lo, hi)
        failures += 1

    # left-open variant must never be zero
    var min_left: Float64 = 2.0
    for i in range(n):
        var v = rng_uniform_left_open(11, 22, UInt64(i), 4, 5, PROCESS_LAP_NOISE, 0)
        if v < min_left:
            min_left = v
    if min_left <= 0.0:
        print("FAIL left-open produced zero")
        failures += 1

    # ── normal moments ────────────────────────────────────────────────────────
    var sm: Float64 = 0.0
    var sv: Float64 = 0.0
    for i in range(n):
        var z = rng_normal(11, 22, UInt64(i), 4, 5, PROCESS_LAP_NOISE, 0)
        sm += z
        sv += z * z
    var zmean = sm / Float64(n)
    var zsd = sqrt(sv / Float64(n) - zmean * zmean)
    if zmean < -0.03 or zmean > 0.03:
        print("FAIL normal mean", zmean)
        failures += 1
    if zsd < 0.97 or zsd > 1.03:
        print("FAIL normal sd", zsd)
        failures += 1

    # ── bernoulli rate ────────────────────────────────────────────────────────
    var hits = 0
    for i in range(n):
        if rng_bernoulli(11, 22, UInt64(i), 4, 5, PROCESS_LAP_NOISE, 0, 0.07):
            hits += 1
    var rate = Float64(hits) / Float64(n)
    if rate < 0.06 or rate > 0.08:
        print("FAIL bernoulli rate", rate)
        failures += 1

    # ── exponential mean, and the rate<=0 guard ───────────────────────────────
    var se: Float64 = 0.0
    for i in range(n):
        se += rng_exponential(11, 22, UInt64(i), 4, 5, PROCESS_PIT_SERVICE, 0, 1.0 / 2.4)
    var emean = se / Float64(n)
    if emean < 2.3 or emean > 2.5:
        print("FAIL exponential mean", emean)
        failures += 1
    if rng_exponential(1, 1, 1, 1, 1, PROCESS_PIT_SERVICE, 0, 0.0) != 0.0:
        print("FAIL exponential rate<=0 guard")
        failures += 1

    if failures == 0:
        print("test_counter_rng: PASS")
    else:
        print("test_counter_rng: FAILURES =", failures)
        raise Error("test_counter_rng failed")
