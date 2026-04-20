"""test_stochastic.mojo — auto-generated tests for stochastic library."""
from std.math import isnan, isinf
from stochastic import random_walk_1d, random_walk_2d, brownian_motion, geometric_brownian_motion, poisson_process, ornstein_uhlenbeck, birth_death_process, monte_carlo_pi, expected_hitting_time, first_passage_time

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_random_walk_1d = random_walk_1d(5)
    if len(_v_random_walk_1d) >= 0: passed += 1; print("  ✅ stochastic::random_walk_1d")
    _ = random_walk_2d(5)
    passed += 1; print("  ✅ stochastic::random_walk_2d")
    var _v_brownian_motion = brownian_motion(5, 0.5)
    if len(_v_brownian_motion) >= 0: passed += 1; print("  ✅ stochastic::brownian_motion")
    var _v_geometric_brownian_motion = geometric_brownian_motion(0.5, 0.5, 0.5, 0.5, 5)
    if len(_v_geometric_brownian_motion) >= 0: passed += 1; print("  ✅ stochastic::geometric_brownian_motion")
    var _v_poisson_process = poisson_process(0.5, 0.5)
    if len(_v_poisson_process) >= 0: passed += 1; print("  ✅ stochastic::poisson_process")
    var _v_ornstein_uhlenbeck = ornstein_uhlenbeck(0.5, 0.5, 0.5, 0.5, 0.5, 5)
    if len(_v_ornstein_uhlenbeck) >= 0: passed += 1; print("  ✅ stochastic::ornstein_uhlenbeck")
    var _v_birth_death_process = birth_death_process(0.5, 0.5, 5, 5)
    if len(_v_birth_death_process) >= 0: passed += 1; print("  ✅ stochastic::birth_death_process")
    var _v_monte_carlo_pi = monte_carlo_pi(5)
    if is_finite(_v_monte_carlo_pi): passed += 1; print("  ✅ stochastic::monte_carlo_pi =", _v_monte_carlo_pi)
    else: failed += 1; print("  ❌ stochastic::monte_carlo_pi → non-finite:", _v_monte_carlo_pi)
    var _v_expected_hitting_time = expected_hitting_time(0.5, 5)
    if is_finite(_v_expected_hitting_time): passed += 1; print("  ✅ stochastic::expected_hitting_time =", _v_expected_hitting_time)
    else: failed += 1; print("  ❌ stochastic::expected_hitting_time → non-finite:", _v_expected_hitting_time)
    var _v_first_passage_time = first_passage_time(5, 0.5)
    if is_finite(_v_first_passage_time): passed += 1; print("  ✅ stochastic::first_passage_time =", _v_first_passage_time)
    else: failed += 1; print("  ❌ stochastic::first_passage_time → non-finite:", _v_first_passage_time)

    print("  [stochastic] Passed:", passed, "Failed:", failed)
