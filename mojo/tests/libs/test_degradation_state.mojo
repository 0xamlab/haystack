"""test_degradation_state.mojo — hand-written tests for the pace/degradation filter.

The load-bearing tests here are the EXCLUSION ones. Every modelling guard in this kernel exists to stop
one contaminated observation moving the whole board, and each was validated against a real session where
the unguarded version produced physically impossible output (mean tyre degradation of -0.6 s/lap, i.e.
tyres getting faster forever, which a plan optimizer exploits with an impossible stint).
"""
from std.math import isnan, isinf, sqrt
from degradation_state import (
    pace_state_init,
    pace_kalman_update,
    pace_kalman_run,
    pace_predict,
    pace_reset_for_compound,
    pace_offset_stderr,
    pace_slope_stderr,
    load_corrected_rate,
    wear_clamp,
    sample_is_usable,
    degradation_state_version,
    wear_clamp_bounds,
    degradation_state_selftest,
    LAP_GREEN,
    LAP_OUT,
    LAP_IN,
    LAP_NEUTRALISED,
    LAP_DIRTY_AIR,
)


def is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)


def main() raises:
    var failures = 0

    if degradation_state_version() != String("degradation-state/v1"):
        print("FAIL version", degradation_state_version())
        failures += 1

    var b = wear_clamp_bounds()
    if b[0] != 0.0 or b[1] != 0.22:
        print("FAIL clamp bounds", b[0], b[1])
        failures += 1

    # ── recovers a known linear degradation ───────────────────────────────────
    var st = degradation_state_selftest()
    if st < 0.045 or st > 0.055:
        print("FAIL selftest slope", st, "expected ~0.05")
        failures += 1

    var times = List[Float64]()
    var ages = List[Float64]()
    var fl = List[Int]()
    for i in range(25):
        var a = Float64(i)
        ages.append(a)
        times.append(88.5 + 0.08 * a)
        fl.append(LAP_GREEN)
    var fit = pace_kalman_run(times, ages, fl, 88.5, 0.0, 1.0, 0.01, 0.05, 0.0005)
    if fit.beta1 < 0.075 or fit.beta1 > 0.085:
        print("FAIL ramp slope", fit.beta1, "expected ~0.08")
        failures += 1
    if fit.beta0 < 88.4 or fit.beta0 > 88.6:
        print("FAIL ramp offset", fit.beta0, "expected ~88.5")
        failures += 1
    if fit.n_updates != 25:
        print("FAIL ramp update count", fit.n_updates)
        failures += 1
    var pred = pace_predict(fit, 10.0)
    if pred < 89.2 or pred > 89.4:
        print("FAIL predict@10", pred, "expected ~89.3")
        failures += 1
    if not is_finite(pace_offset_stderr(fit)) or not is_finite(pace_slope_stderr(fit)):
        print("FAIL stderr not finite")
        failures += 1

    # ── exclusions: an absurd observation must not move the state at all ──────
    # This is the guard that matters. An out-lap carries ~20 s of pit loss; a neutralised lap carries
    # a safety car. Both are ~105 s against an ~85 s green lap, and either one admitted into the filter
    # fits a steeply negative slope with a wildly inflated intercept.
    var base = pace_state_init(90.0, 0.0, 1.0, 0.01)
    var e1 = pace_kalman_update(base, 200.0, 5.0, LAP_NEUTRALISED, 0.18, 0.0005)
    var e2 = pace_kalman_update(e1, 200.0, 5.0, LAP_OUT, 0.18, 0.0005)
    var e3 = pace_kalman_update(e2, 200.0, 5.0, LAP_IN, 0.18, 0.0005)
    if e3.beta0 != 90.0 or e3.beta1 != 0.0:
        print("FAIL excluded laps moved the state", e3.beta0, e3.beta1)
        failures += 1
    if e3.n_updates != 0 or e3.n_excluded != 3:
        print("FAIL exclusion accounting", e3.n_updates, e3.n_excluded)
        failures += 1
    # combined flags must also exclude
    if sample_is_usable(LAP_OUT | LAP_DIRTY_AIR):
        print("FAIL out+dirty treated as usable")
        failures += 1
    if not sample_is_usable(LAP_GREEN) or not sample_is_usable(LAP_DIRTY_AIR):
        print("FAIL green or dirty-air treated as unusable")
        failures += 1

    # ── dirty air damps rather than discards ──────────────────────────────────
    var clean = pace_kalman_update(base, 92.0, 5.0, LAP_GREEN, 0.18, 0.0005)
    var dirty = pace_kalman_update(base, 92.0, 5.0, LAP_DIRTY_AIR, 0.18, 0.0005)
    if not ((dirty.beta0 - 90.0) < (clean.beta0 - 90.0)):
        print("FAIL dirty air did not damp the update", clean.beta0, dirty.beta0)
        failures += 1
    if dirty.n_updates != 1:
        print("FAIL dirty-air lap was discarded rather than damped")
        failures += 1

    # ── compound change carries pace, resets slope ────────────────────────────
    var reset = pace_reset_for_compound(fit, 0.0, 0.01)
    if reset.beta0 != fit.beta0:
        print("FAIL compound reset lost the pace offset")
        failures += 1
    if reset.beta1 != 0.0 or reset.p11 != 0.01 or reset.p01 != 0.0:
        print("FAIL compound reset did not reset the slope", reset.beta1, reset.p11)
        failures += 1

    # ── clamp keeps a plan optimizer honest ──────────────────────────────────
    # An unclamped negative slope means tyres improve forever. 19 of 65 real stints still fit negative
    # before fuel/track-evolution correction, so this clamp is load-bearing, not cosmetic.
    if wear_clamp(-0.3) != 0.0 or wear_clamp(0.9) != 0.22 or wear_clamp(0.1) != 0.1:
        print("FAIL clamp", wear_clamp(-0.3), wear_clamp(0.9), wear_clamp(0.1))
        failures += 1
    var neg = pace_state_init(90.0, -0.5, 1.0, 0.01)
    if pace_predict(neg, 20.0) != 90.0:
        print("FAIL negative slope leaked into prediction", pace_predict(neg, 20.0))
        failures += 1

    # ── fuel correction ──────────────────────────────────────────────────────
    if load_corrected_rate(90.0, 30.0, 0.05) != 88.5:
        print("FAIL fuel correction", load_corrected_rate(90.0, 30.0, 0.05))
        failures += 1

    # ── ragged inputs must not read past the shortest list ────────────────────
    var t2 = List[Float64]()
    var a2 = List[Float64]()
    var f2 = List[Int]()
    t2.append(90.0)
    t2.append(91.0)
    a2.append(0.0)
    f2.append(LAP_GREEN)
    var ragged = pace_kalman_run(t2, a2, f2, 90.0, 0.0, 1.0, 0.01, 0.18, 0.0005)
    if ragged.n_updates != 1:
        print("FAIL ragged input handling", ragged.n_updates)
        failures += 1

    if failures == 0:
        print("test_degradation_state: PASS")
    else:
        print("test_degradation_state: FAILURES =", failures)
        raise Error("test_degradation_state failed")
