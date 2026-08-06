"""Tests for Wave 29 — PID Control, Scoring Models, PBKDF2."""

from control import (
    PIDState,
    create_pid,
    pid_update,
    pid_simulate,
    bang_bang,
    step_response,
    ramp_response,
    settling_time,
    overshoot,
    steady_state_error,
)
from scoring import (
    sigmoid,
    logit,
    log_odds_to_score,
    score_to_log_odds,
    woe,
    iv,
    gini_coefficient,
    ks_statistic,
    score_band,
    linear_score,
    normalize_score,
)
from crypto.pbkdf2 import (
    sha256_bytes,
    hmac_sha256_bytes,
    pbkdf2_hmac_sha256,
    bytes_from_string,
    bytes_to_hex,
    xor_byte_lists,
    int_to_bytes_be,
)
from std.math import abs as fabs, log


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Control tests ────────────────────────────────────────────────────────────


def test_create_pid() raises:
    var state = create_pid(1.0, 0.1, 0.01)
    _assert_close(state.kp, 1.0, 1e-12, "create_pid kp")
    _assert_close(state.ki, 0.1, 1e-12, "create_pid ki")
    _assert_close(state.kd, 0.01, 1e-12, "create_pid kd")
    _assert_close(state.integral, 0.0, 1e-12, "create_pid integral init")
    _assert_close(state.prev_error, 0.0, 1e-12, "create_pid prev_error init")
    print("  ✓ create_pid")


def test_pid_update() raises:
    var state = create_pid(1.0, 0.0, 0.0)
    var u1 = pid_update(state, 10.0, 0.0, 0.1)
    # P-only: output = kp * error = 1.0 * 10.0 = 10.0
    _assert_close(u1, 10.0, 1e-9, "pid_update P-only first step")
    # Second step: measured closer to setpoint
    var u2 = pid_update(state, 10.0, 5.0, 0.1)
    _assert_close(u2, 5.0, 1e-9, "pid_update P-only second step")
    # Output should move toward reducing error
    _assert(u2 < u1, "pid_update output decreases as error shrinks")
    print("  ✓ pid_update")


def test_pid_simulate() raises:
    var traj = pid_simulate(2.0, 0.5, 0.1, 100.0, 0.0, 1.0, 0.01, 500)
    _assert(len(traj) == 501, "pid_simulate trajectory length")
    _assert_close(traj[0], 0.0, 1e-12, "pid_simulate starts at initial")
    # Should converge near setpoint=100
    var final_val = traj[500]
    _assert(fabs(final_val - 100.0) < 5.0, "pid_simulate converges to setpoint")
    print("  ✓ pid_simulate")


def test_bang_bang() raises:
    # Below threshold
    _assert_close(bang_bang(100.0, 90.0, 5.0), 1.0, 1e-12, "bang_bang below")
    # Above threshold
    _assert_close(bang_bang(100.0, 110.0, 5.0), 0.0, 1e-12, "bang_bang above")
    # Within hysteresis band
    _assert_close(bang_bang(100.0, 100.0, 5.0), 0.5, 1e-12, "bang_bang within band")
    # No hysteresis, exactly at setpoint
    _assert_close(bang_bang(100.0, 99.0, 0.0), 1.0, 1e-12, "bang_bang below no hyst")
    _assert_close(bang_bang(100.0, 101.0, 0.0), 0.0, 1e-12, "bang_bang above no hyst")
    print("  ✓ bang_bang")


def test_step_response() raises:
    var resp = step_response(10.0, 1.0, 0.01, 1000)
    _assert(len(resp) == 1000, "step_response length")
    _assert_close(resp[0], 0.0, 1e-12, "step_response starts at 0")
    # After many time constants, should approach gain
    _assert(resp[999] > 9.9, "step_response approaches gain")
    # Monotonically increasing
    var monotonic = True
    for i in range(1, len(resp)):
        if resp[i] < resp[i - 1] - 1e-15:
            monotonic = False
    _assert(monotonic, "step_response monotonic")
    print("  ✓ step_response")


def test_ramp_response() raises:
    var resp = ramp_response(1.0, 1.0, 0.1, 100)
    _assert(len(resp) == 100, "ramp_response length")
    _assert_close(resp[0], 0.0, 1e-12, "ramp_response starts at 0")
    # Should be positive and growing
    _assert(resp[99] > resp[50], "ramp_response grows")
    print("  ✓ ramp_response")


def test_settling_time() raises:
    var resp = step_response(1.0, 0.5, 0.01, 1000)
    var st = settling_time(resp, 1.0, 0.02)
    _assert(st >= 0.0, "settling_time non-negative")
    _assert(st < 1000.0, "settling_time finite for stable system")
    print("  ✓ settling_time")


def test_overshoot() raises:
    # Aggressive PID should produce overshoot
    var traj = pid_simulate(5.0, 1.0, 0.1, 10.0, 0.0, 1.0, 0.01, 500)
    var os_val = overshoot(traj, 10.0)
    _assert(os_val > 0.0, "overshoot with aggressive PID > 0")
    print("  ✓ overshoot")


def test_steady_state_error() raises:
    # PID with integral term should have ~0 steady state error
    var traj = pid_simulate(2.0, 1.0, 0.1, 10.0, 0.0, 1.0, 0.01, 1000)
    var sse = steady_state_error(traj, 10.0)
    _assert(sse < 1.0, "steady_state_error with I term small")
    print("  ✓ steady_state_error")


# ── Scoring tests ────────────────────────────────────────────────────────────


def test_sigmoid() raises:
    _assert_close(sigmoid(0.0), 0.5, 1e-12, "sigmoid(0) = 0.5")
    _assert(sigmoid(100.0) > 0.999, "sigmoid(100) ≈ 1.0")
    _assert(sigmoid(-100.0) < 0.001, "sigmoid(-100) ≈ 0.0")
    # Symmetry
    _assert_close(sigmoid(2.0) + sigmoid(-2.0), 1.0, 1e-12, "sigmoid symmetry")
    print("  ✓ sigmoid")


def test_logit() raises:
    _assert_close(logit(0.5), 0.0, 1e-12, "logit(0.5) = 0")
    # Roundtrip: logit(sigmoid(x)) ≈ x
    _assert_close(logit(sigmoid(1.5)), 1.5, 1e-9, "logit(sigmoid(1.5)) roundtrip")
    _assert_close(logit(sigmoid(-2.3)), -2.3, 1e-9, "logit(sigmoid(-2.3)) roundtrip")
    print("  ✓ logit")


def test_log_odds_score() raises:
    # At log_odds=0, score = base_score
    _assert_close(log_odds_to_score(0.0), 600.0, 1e-9, "log_odds_to_score(0) = 600")
    # Roundtrip
    var lo = 1.5
    var sc = log_odds_to_score(lo)
    var lo2 = score_to_log_odds(sc)
    _assert_close(lo2, lo, 1e-9, "score_to_log_odds roundtrip")
    # Higher log-odds = lower score (more risky)
    _assert(log_odds_to_score(1.0) < log_odds_to_score(0.0), "higher log_odds = lower score")
    print("  ✓ log_odds_to_score / score_to_log_odds")


def test_woe() raises:
    # Equal distributions: woe ≈ 0
    var w = woe(10, 10, 100, 100)
    _assert_close(w, 0.0, 1e-9, "woe equal distributions")
    # More non-events than events: positive WoE
    var w2 = woe(5, 15, 100, 100)
    _assert(w2 > 0.0, "woe more non-events positive")
    print("  ✓ woe")


def test_iv() raises:
    var woe_vals = List[Float64]()
    woe_vals.append(0.5)
    woe_vals.append(-0.3)
    var de = List[Float64]()
    de.append(0.3)
    de.append(0.7)
    var dne = List[Float64]()
    dne.append(0.5)
    dne.append(0.5)
    var result = iv(woe_vals, de, dne)
    # IV = (0.5-0.3)*0.5 + (0.5-0.7)*(-0.3) = 0.1 + 0.06 = 0.16
    _assert_close(result, 0.16, 1e-9, "iv calculation")
    _assert(result >= 0.0, "iv non-negative for valid inputs")
    print("  ✓ iv")


def test_gini_ks() raises:
    # Perfect predictor
    var actual = List[Float64]()
    actual.append(0.0); actual.append(0.0); actual.append(1.0); actual.append(1.0)
    var predicted = List[Float64]()
    predicted.append(0.1); predicted.append(0.2); predicted.append(0.8); predicted.append(0.9)
    var g = gini_coefficient(actual, predicted)
    _assert(g > 0.5, "gini_coefficient good predictor > 0.5")
    var ks = ks_statistic(actual, predicted)
    _assert(ks > 0.5, "ks_statistic good predictor > 0.5")
    _assert(ks <= 1.0, "ks_statistic <= 1.0")
    print("  ✓ gini_coefficient / ks_statistic")


def test_linear_score() raises:
    var features = List[Float64]()
    features.append(1.0); features.append(2.0); features.append(3.0)
    var weights = List[Float64]()
    weights.append(0.5); weights.append(0.3); weights.append(0.2)
    var result = linear_score(features, weights, 1.0)
    # 1*0.5 + 2*0.3 + 3*0.2 + 1.0 = 0.5 + 0.6 + 0.6 + 1.0 = 2.7
    _assert_close(result, 2.7, 1e-9, "linear_score dot product + intercept")
    print("  ✓ linear_score")


def test_normalize_score() raises:
    _assert_close(normalize_score(75.0, 50.0, 100.0), 0.5, 1e-12, "normalize 75 in [50,100]")
    _assert_close(normalize_score(50.0, 50.0, 100.0), 0.0, 1e-12, "normalize min")
    _assert_close(normalize_score(100.0, 50.0, 100.0), 1.0, 1e-12, "normalize max")
    print("  ✓ normalize_score")


def test_score_band() raises:
    var boundaries = List[Float64]()
    boundaries.append(300.0); boundaries.append(500.0); boundaries.append(700.0)
    var labels = List[String]()
    labels.append("Poor"); labels.append("Fair"); labels.append("Good"); labels.append("Excellent")
    _assert(score_band(250.0, boundaries, labels) == "Poor", "score_band Poor")
    _assert(score_band(400.0, boundaries, labels) == "Fair", "score_band Fair")
    _assert(score_band(600.0, boundaries, labels) == "Good", "score_band Good")
    _assert(score_band(800.0, boundaries, labels) == "Excellent", "score_band Excellent")
    print("  ✓ score_band")


# ── PBKDF2 / Crypto tests ───────────────────────────────────────────────────


def test_bytes_from_string() raises:
    var b = bytes_from_string("abc")
    _assert(len(b) == 3, "bytes_from_string length")
    _assert(b[0] == 97, "bytes_from_string a=97")
    _assert(b[1] == 98, "bytes_from_string b=98")
    _assert(b[2] == 99, "bytes_from_string c=99")
    print("  ✓ bytes_from_string")


def test_bytes_to_hex() raises:
    var data = List[Int]()
    data.append(0); data.append(255)
    _assert(bytes_to_hex(data) == "00ff", "bytes_to_hex [0,255]")
    var data2 = List[Int]()
    data2.append(0xDE); data2.append(0xAD); data2.append(0xBE); data2.append(0xEF)
    _assert(bytes_to_hex(data2) == "deadbeef", "bytes_to_hex deadbeef")
    print("  ✓ bytes_to_hex")


def test_xor_byte_lists() raises:
    var a = List[Int]()
    a.append(1); a.append(2); a.append(3)
    var b = List[Int]()
    b.append(3); b.append(2); b.append(1)
    var result = xor_byte_lists(a, b)
    _assert(result[0] == 2, "xor [0] = 2")
    _assert(result[1] == 0, "xor [1] = 0")
    _assert(result[2] == 2, "xor [2] = 2")
    print("  ✓ xor_byte_lists")


def test_int_to_bytes_be() raises:
    var b = int_to_bytes_be(1, 4)
    _assert(b[0] == 0, "int_to_bytes_be [0]=0")
    _assert(b[1] == 0, "int_to_bytes_be [1]=0")
    _assert(b[2] == 0, "int_to_bytes_be [2]=0")
    _assert(b[3] == 1, "int_to_bytes_be [3]=1")
    var b2 = int_to_bytes_be(256, 4)
    _assert(b2[2] == 1, "int_to_bytes_be 256 [2]=1")
    _assert(b2[3] == 0, "int_to_bytes_be 256 [3]=0")
    print("  ✓ int_to_bytes_be")


def test_sha256_bytes_empty() raises:
    var empty = List[Int]()
    var h = sha256_bytes(empty)
    _assert(len(h) == 32, "sha256_bytes empty length = 32")
    var hex = bytes_to_hex(h)
    # SHA-256("") = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
    _assert(hex == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "sha256_bytes empty hash")
    print("  ✓ sha256_bytes empty")


def test_sha256_bytes_abc() raises:
    var data = bytes_from_string("abc")
    var h = sha256_bytes(data)
    var hex = bytes_to_hex(h)
    # SHA-256("abc") = ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
    _assert(hex == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            "sha256_bytes abc hash")
    print("  ✓ sha256_bytes abc")


def test_hmac_sha256_bytes() raises:
    var key = bytes_from_string("key")
    var msg = bytes_from_string("message")
    var h = hmac_sha256_bytes(key, msg)
    _assert(len(h) == 32, "hmac_sha256_bytes length = 32")
    # Deterministic: same inputs produce same output
    var h2 = hmac_sha256_bytes(key, msg)
    var hex1 = bytes_to_hex(h)
    var hex2 = bytes_to_hex(h2)
    _assert(hex1 == hex2, "hmac_sha256_bytes deterministic")
    # Known value: HMAC-SHA256("key", "message")
    # = 6e9ef29b75fffc5b7abae527d58fdadb2fe42e7219011976917343065f58ed4a
    _assert(hex1 == "6e9ef29b75fffc5b7abae527d58fdadb2fe42e7219011976917343065f58ed4a",
            "hmac_sha256_bytes known value")
    print("  ✓ hmac_sha256_bytes")


def test_pbkdf2() raises:
    var password = bytes_from_string("password")
    var salt = bytes_from_string("salt")
    var dk1 = pbkdf2_hmac_sha256(password, salt, 1, 32)
    _assert(len(dk1) == 32, "pbkdf2 length = 32")
    # Deterministic
    var dk1b = pbkdf2_hmac_sha256(password, salt, 1, 32)
    _assert(bytes_to_hex(dk1) == bytes_to_hex(dk1b), "pbkdf2 deterministic")
    # 1 iteration vs 2 iterations: different
    var dk2 = pbkdf2_hmac_sha256(password, salt, 2, 32)
    _assert(bytes_to_hex(dk1) != bytes_to_hex(dk2), "pbkdf2 1 iter != 2 iter")
    # Known value: PBKDF2-HMAC-SHA256("password", "salt", 1, 32)
    # = 120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b
    _assert(bytes_to_hex(dk1) == "120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b",
            "pbkdf2 known value 1 iter")
    print("  ✓ pbkdf2_hmac_sha256")


def test_pbkdf2_short_key() raises:
    var password = bytes_from_string("pass")
    var salt = bytes_from_string("sa")
    var dk = pbkdf2_hmac_sha256(password, salt, 3, 16)
    _assert(len(dk) == 16, "pbkdf2 short dk_len = 16")
    # Just ensure it's deterministic and non-zero
    var dk2 = pbkdf2_hmac_sha256(password, salt, 3, 16)
    _assert(bytes_to_hex(dk) == bytes_to_hex(dk2), "pbkdf2 short key deterministic")
    print("  ✓ pbkdf2 short key")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("=== Wave 29 Tests: PID Control, Scoring Models, PBKDF2 ===")
    var count = 0

    print("\n── Control ──")
    test_create_pid()
    count += 5
    test_pid_update()
    count += 3
    test_pid_simulate()
    count += 3
    test_bang_bang()
    count += 5
    test_step_response()
    count += 4
    test_ramp_response()
    count += 3
    test_settling_time()
    count += 2
    test_overshoot()
    count += 1
    test_steady_state_error()
    count += 1

    print("\n── Scoring ──")
    test_sigmoid()
    count += 4
    test_logit()
    count += 3
    test_log_odds_score()
    count += 3
    test_woe()
    count += 2
    test_iv()
    count += 2
    test_gini_ks()
    count += 3
    test_linear_score()
    count += 1
    test_normalize_score()
    count += 3
    test_score_band()
    count += 4

    print("\n── PBKDF2 / Crypto ──")
    test_bytes_from_string()
    count += 4
    test_bytes_to_hex()
    count += 2
    test_xor_byte_lists()
    count += 3
    test_int_to_bytes_be()
    count += 6
    test_sha256_bytes_empty()
    count += 2
    test_sha256_bytes_abc()
    count += 1
    test_hmac_sha256_bytes()
    count += 3
    test_pbkdf2()
    count += 4
    test_pbkdf2_short_key()
    count += 2

    print("\n✅ All " + String(count) + " assertions passed!")
