"""Tests for Wave 44 — Feature Selection, ChaCha20, Supply Chain."""

from feature_selection import (
    column_mean,
    column_variance,
    variance_threshold,
    correlation_filter,
    f_test_scores,
    select_k_best,
    forward_selection_greedy,
    information_gain,
    feature_importance_permutation,
)
from crypto.chacha20 import (
    rotl32,
    quarter_round,
    chacha20_init_state,
    add_states,
    xor_states,
    chacha20_block,
    chacha20_encrypt,
    chacha20_decrypt,
)
from supply_chain import (
    lead_time_demand,
    bullwhip_effect,
    forecast_error_mae,
    forecast_error_mape,
    forecast_bias,
    tracking_signal,
    economic_production_qty,
    total_cost_of_ownership,
    service_level_type1,
    fill_rate_type2,
    moving_average_forecast,
    exponential_smoothing_forecast,
)

from std.math import abs as fabs


# ── Helpers ──────────────────────────────────────────────────────────────────


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


def _flist2(a: Float64, b: Float64) -> List[Float64]:
    var v = List[Float64]()
    v.append(a); v.append(b)
    return v^


def _flist3(a: Float64, b: Float64, c: Float64) -> List[Float64]:
    var v = List[Float64]()
    v.append(a); v.append(b); v.append(c)
    return v^


def _contains(lst: List[Int], val: Int) -> Bool:
    for i in range(len(lst)):
        if lst[i] == val:
            return True
    return False


# ── Feature Selection Tests ──────────────────────────────────────────────────


def test_column_mean() raises:
    var data = List[List[Float64]]()
    data.append(_flist2(1.0, 2.0))
    data.append(_flist2(3.0, 4.0))
    data.append(_flist2(5.0, 6.0))

    var means = column_mean(data)
    _assert_close(means[0], 3.0, 1e-9, "column_mean col 0 = 3.0")        # 1
    _assert_close(means[1], 4.0, 1e-9, "column_mean col 1 = 4.0")        # 2
    _assert(len(means) == 2, "column_mean returns 2 means")                # 3
    print("  ✓ column_mean")


def test_column_variance() raises:
    var data = List[List[Float64]]()
    for i in range(5):
        data.append(_flist2(3.0, Float64(i + 1)))

    var variances = column_variance(data)
    _assert_close(variances[0], 0.0, 1e-9, "const col var=0")             # 4
    _assert(variances[1] > 0.0, "varying col var > 0")                    # 5
    _assert(len(variances) == 2, "2 variances returned")                   # 6
    print("  ✓ column_variance")


def test_variance_threshold() raises:
    var data = List[List[Float64]]()
    for i in range(5):
        data.append(_flist2(5.0, Float64(i) * 10.0))

    var selected = variance_threshold(data)
    _assert(len(selected) == 1, "only 1 col above threshold=0")           # 7
    _assert(selected[0] == 1, "col 1 is selected")                        # 8

    var sel2 = variance_threshold(data, 99999.0)
    _assert(len(sel2) == 0, "no cols above high threshold")                # 9
    print("  ✓ variance_threshold")


def test_correlation_filter() raises:
    # Col 0 and Col 1 identical (corr=1.0), Col 2 alternating (low corr)
    var data = List[List[Float64]]()
    for i in range(10):
        var fi = Float64(i)
        var alt: Float64 = 1.0
        if i % 2 == 0:
            alt = -1.0
        data.append(_flist3(fi, fi, alt))

    var selected = correlation_filter(data, 0.95)
    _assert(_contains(selected, 0), "col 0 kept")                         # 10
    _assert(not _contains(selected, 1), "col 1 removed (corr with 0)")    # 11
    _assert(_contains(selected, 2), "col 2 kept")                         # 12
    _assert(len(selected) == 2, "2 cols remain")                           # 13
    print("  ✓ correlation_filter")


def test_f_test_scores() raises:
    var X = List[List[Float64]]()
    var y = List[Float64]()
    for i in range(20):
        var fi = Float64(i)
        X.append(_flist2(fi, 5.0))
        y.append(fi * 2.0 + 1.0)

    var scores = f_test_scores(X, y)
    _assert(len(scores) == 2, "2 F-scores")                               # 14
    _assert(scores[0] > scores[1], "informative feat > constant")          # 15
    _assert(scores[0] > 1.0, "informative feat has large F")              # 16
    _assert_close(scores[1], 0.0, 1e-6, "constant feat F ≈ 0")            # 17
    print("  ✓ f_test_scores")


def test_select_k_best() raises:
    var scores = List[Float64]()
    scores.append(10.0); scores.append(50.0); scores.append(30.0); scores.append(5.0)

    var top2 = select_k_best(scores, 2)
    _assert(len(top2) == 2, "returns k=2 indices")                        # 18
    _assert(_contains(top2, 1), "index 1 (score=50) in top 2")            # 19
    _assert(_contains(top2, 2), "index 2 (score=30) in top 2")            # 20

    var top1 = select_k_best(scores, 1)
    _assert(len(top1) == 1, "returns k=1")                                # 21
    _assert(top1[0] == 1, "best is index 1")                              # 22
    print("  ✓ select_k_best")


def test_forward_selection_greedy() raises:
    var X = List[List[Float64]]()
    var y = List[Float64]()
    for i in range(20):
        var fi = Float64(i)
        X.append(_flist3(fi, 5.0, fi * 0.5))
        y.append(fi * 3.0)

    var selected = forward_selection_greedy(X, y, 2)
    _assert(len(selected) == 2, "returns k=2 features")                   # 23
    _assert(_contains(selected, 0) or _contains(selected, 2), "picks informative feature")  # 24
    print("  ✓ forward_selection_greedy")


def test_information_gain() raises:
    var feat_informative = List[Float64]()
    var feat_noise = List[Float64]()
    var target = List[Float64]()
    for i in range(50):
        var v = Float64(i)
        feat_informative.append(v)
        feat_noise.append(Float64(i % 3))
        target.append(v * 2.0)

    var ig_good = information_gain(feat_informative, target, 10)
    var ig_noise = information_gain(feat_noise, target, 10)
    _assert(ig_good >= 0.0, "IG >= 0")                                    # 25
    _assert(ig_good > ig_noise, "informative IG > noise IG")              # 26
    print("  ✓ information_gain")


def test_feature_importance_permutation() raises:
    var X = List[List[Float64]]()
    var y = List[Float64]()
    for i in range(20):
        var fi = Float64(i)
        X.append(_flist2(fi * 10.0, 1.0))
        y.append(fi * 5.0)

    var imp = feature_importance_permutation(X, y, 3)
    _assert(len(imp) == 2, "2 importances")                               # 27
    _assert(imp[0] > imp[1], "varying feature more important")            # 28
    _assert(imp[0] >= 0.0, "importance non-negative")                     # 29
    print("  ✓ feature_importance_permutation")


# ── ChaCha20 Tests ───────────────────────────────────────────────────────────


def test_rotl32() raises:
    _assert(rotl32(1, 1) == 2, "rotl32(1,1)==2")                          # 30
    _assert(rotl32(1, 31) == (1 << 31), "rotl32(1,31)==2^31")             # 31
    _assert(rotl32(0xFF, 8) == 0xFF00, "rotl32(0xFF,8)==0xFF00")          # 32
    _assert(rotl32(0, 5) == 0, "rotl32(0,5)==0")                          # 33
    print("  ✓ rotl32")


def test_quarter_round() raises:
    var state = List[Int]()
    for i in range(16):
        state.append(i)
    var orig0 = state[0]
    var orig1 = state[1]
    quarter_round(state, 0, 1, 2, 3)
    var changed = (state[0] != orig0) or (state[1] != orig1)
    _assert(changed, "quarter_round changes state")                        # 34
    _assert(len(state) == 16, "state still 16 words")                     # 35
    print("  ✓ quarter_round")


def test_chacha20_init_state() raises:
    var key = List[Int]()
    for i in range(8):
        key.append(i + 1)
    var nonce = List[Int]()
    nonce.append(0x09); nonce.append(0x0A); nonce.append(0x0B)

    var state = chacha20_init_state(key, 1, nonce)
    _assert(len(state) == 16, "init state has 16 words")                   # 36
    _assert(state[0] == 0x61707865, "const[0] correct")                    # 37
    _assert(state[1] == 0x3320646E, "const[1] correct")                    # 38
    _assert(state[2] == 0x79622D32, "const[2] correct")                    # 39
    _assert(state[3] == 0x6B206574, "const[3] correct")                    # 40
    _assert(state[12] == 1, "counter = 1")                                 # 41
    _assert(state[13] == 0x09, "nonce[0]")                                 # 42
    print("  ✓ chacha20_init_state")


def test_chacha20_block() raises:
    var key = List[Int]()
    for i in range(8):
        key.append(i + 1)
    var nonce = List[Int]()
    nonce.append(0); nonce.append(0); nonce.append(1)

    var block = chacha20_block(key, 0, nonce)
    _assert(len(block) == 16, "block output 16 words")                     # 43
    var state = chacha20_init_state(key, 0, nonce)
    var different = False
    for i in range(16):
        if block[i] != state[i]:
            different = True
            break
    _assert(different, "block differs from init state")                    # 44
    print("  ✓ chacha20_block")


def test_add_xor_states() raises:
    var a = List[Int]()
    a.append(1); a.append(2); a.append(3)
    var b = List[Int]()
    b.append(10); b.append(20); b.append(30)

    var sum_s = add_states(a, b)
    _assert(sum_s[0] == 11, "add_states[0]")                              # 45
    _assert(sum_s[1] == 22, "add_states[1]")                              # 46

    var xor_s = xor_states(a, b)
    _assert(xor_s[0] == (1 ^ 10), "xor_states[0]")                       # 47
    _assert(xor_s[2] == (3 ^ 30), "xor_states[2]")                       # 48
    print("  ✓ add_states / xor_states")


def test_chacha20_roundtrip() raises:
    var key = List[Int]()
    for i in range(8):
        key.append((i + 1) * 0x01010101)
    var nonce = List[Int]()
    nonce.append(0); nonce.append(0); nonce.append(42)

    # Plaintext: "Hello, ChaCha20!" as bytes
    var plaintext = List[Int]()
    plaintext.append(72); plaintext.append(101); plaintext.append(108)
    plaintext.append(108); plaintext.append(111); plaintext.append(44)
    plaintext.append(32); plaintext.append(67); plaintext.append(104)
    plaintext.append(97); plaintext.append(67); plaintext.append(104)
    plaintext.append(97); plaintext.append(50); plaintext.append(48)
    plaintext.append(33)

    var ciphertext = chacha20_encrypt(plaintext, key, nonce)
    _assert(len(ciphertext) == len(plaintext), "ciphertext same length")   # 49

    var differs = False
    for i in range(len(plaintext)):
        if ciphertext[i] != plaintext[i]:
            differs = True
            break
    _assert(differs, "ciphertext ≠ plaintext")                            # 50

    var decrypted = chacha20_decrypt(ciphertext, key, nonce)
    _assert(len(decrypted) == len(plaintext), "decrypted same length")     # 51
    var all_match = True
    for i in range(len(plaintext)):
        if decrypted[i] != plaintext[i]:
            all_match = False
            break
    _assert(all_match, "decrypt recovers plaintext")                       # 52
    print("  ✓ chacha20 encrypt/decrypt roundtrip")


def test_chacha20_different_nonces() raises:
    var key = List[Int]()
    for i in range(8):
        key.append(i * 111)
    var nonce1 = List[Int]()
    nonce1.append(1); nonce1.append(0); nonce1.append(0)
    var nonce2 = List[Int]()
    nonce2.append(2); nonce2.append(0); nonce2.append(0)

    var plaintext = List[Int]()
    for i in range(10):
        plaintext.append(i + 65)

    var ct1 = chacha20_encrypt(plaintext, key, nonce1)
    var ct2 = chacha20_encrypt(plaintext, key, nonce2)

    var any_diff = False
    for i in range(len(ct1)):
        if ct1[i] != ct2[i]:
            any_diff = True
            break
    _assert(any_diff, "different nonces -> different ciphertext")          # 53
    print("  ✓ chacha20 different nonces")


# ── Supply Chain Tests ───────────────────────────────────────────────────────


def test_lead_time_demand() raises:
    _assert_close(lead_time_demand(10.0, 5.0), 50.0, 1e-9, "LTD=50")     # 54
    _assert_close(lead_time_demand(0.0, 5.0), 0.0, 1e-9, "LTD=0")        # 55
    _assert_close(lead_time_demand(100.0, 0.5), 50.0, 1e-9, "LTD=50 v2") # 56
    print("  ✓ lead_time_demand")


def test_bullwhip_effect() raises:
    _assert_close(bullwhip_effect(10.0, 20.0), 2.0, 1e-9, "bullwhip=2.0")  # 57
    _assert_close(bullwhip_effect(10.0, 10.0), 1.0, 1e-9, "bullwhip=1.0")  # 58
    _assert_close(bullwhip_effect(10.0, 5.0), 0.5, 1e-9, "bullwhip=0.5")   # 59
    print("  ✓ bullwhip_effect")


def test_forecast_error_mae() raises:
    var actual = List[Float64]()
    actual.append(10.0); actual.append(20.0); actual.append(30.0)
    var forecast = List[Float64]()
    forecast.append(12.0); forecast.append(18.0); forecast.append(33.0)

    var mae = forecast_error_mae(actual, forecast)
    _assert(mae > 0.0, "MAE positive")                                     # 60
    _assert_close(mae, 7.0 / 3.0, 1e-9, "MAE = 7/3")                     # 61
    print("  ✓ forecast_error_mae")


def test_forecast_error_mape() raises:
    var actual = List[Float64]()
    actual.append(100.0); actual.append(200.0)
    var forecast = List[Float64]()
    forecast.append(110.0); forecast.append(190.0)

    var mape = forecast_error_mape(actual, forecast)
    _assert(mape > 0.0, "MAPE positive")                                   # 62
    _assert_close(mape, 7.5, 1e-6, "MAPE = 7.5%")                        # 63
    print("  ✓ forecast_error_mape")


def test_forecast_bias() raises:
    var actual = List[Float64]()
    actual.append(10.0); actual.append(20.0); actual.append(30.0)
    var forecast = List[Float64]()
    forecast.append(12.0); forecast.append(22.0); forecast.append(32.0)

    var bias = forecast_bias(actual, forecast)
    _assert(bias > 0.0, "positive bias = over-forecasting")                # 64
    _assert_close(bias, 2.0, 1e-9, "bias = 2.0")                         # 65
    print("  ✓ forecast_bias")


def test_tracking_signal() raises:
    var actual = List[Float64]()
    actual.append(100.0); actual.append(100.0); actual.append(100.0)
    var forecast = List[Float64]()
    forecast.append(105.0); forecast.append(110.0); forecast.append(103.0)

    var ts = tracking_signal(actual, forecast)
    _assert_close(ts, 3.0, 1e-9, "tracking signal = 3.0")                 # 66
    _assert(ts > 0.0, "tracking signal finite positive")                   # 67
    print("  ✓ tracking_signal")


def test_economic_production_qty() raises:
    var epq = economic_production_qty(1000.0, 100.0, 2.0, 5000.0)
    _assert(epq > 0.0, "EPQ positive")                                     # 68
    _assert(epq > 300.0 and epq < 400.0, "EPQ approx 353.55")             # 69
    print("  ✓ economic_production_qty")


def test_total_cost_of_ownership() raises:
    var tco = total_cost_of_ownership(100.0, 20.0, 10.0, 5.0)
    _assert_close(tco, 135.0, 1e-9, "TCO = 135")                          # 70
    var tco2 = total_cost_of_ownership(0.0, 0.0, 0.0, 0.0)
    _assert_close(tco2, 0.0, 1e-9, "TCO = 0")                            # 71
    print("  ✓ total_cost_of_ownership")


def test_service_level_type1() raises:
    _assert_close(service_level_type1(0.05), 0.95, 1e-9, "SL = 0.95")     # 72
    _assert_close(service_level_type1(0.0), 1.0, 1e-9, "SL = 1.0")       # 73
    _assert_close(service_level_type1(1.0), 0.0, 1e-9, "SL = 0.0")       # 74
    print("  ✓ service_level_type1")


def test_fill_rate_type2() raises:
    _assert_close(fill_rate_type2(5.0, 100.0), 0.95, 1e-9, "FR = 0.95")   # 75
    _assert_close(fill_rate_type2(0.0, 100.0), 1.0, 1e-9, "FR = 1.0")    # 76
    _assert_close(fill_rate_type2(50.0, 100.0), 0.5, 1e-9, "FR = 0.5")   # 77
    print("  ✓ fill_rate_type2")


def test_moving_average_forecast() raises:
    var data = List[Float64]()
    data.append(10.0); data.append(20.0); data.append(30.0); data.append(40.0)

    var ma3 = moving_average_forecast(data, 3)
    _assert_close(ma3, 30.0, 1e-9, "MA(3) = 30.0")                       # 78
    var ma2 = moving_average_forecast(data, 2)
    _assert_close(ma2, 35.0, 1e-9, "MA(2) = 35.0")                       # 79
    var ma_all = moving_average_forecast(data, 4)
    _assert_close(ma_all, 25.0, 1e-9, "MA(all) = 25.0")                  # 80
    print("  ✓ moving_average_forecast")


def test_exponential_smoothing_forecast() raises:
    var data = List[Float64]()
    data.append(10.0); data.append(20.0); data.append(30.0)

    var es = exponential_smoothing_forecast(data, 0.5)
    _assert_close(es, 22.5, 1e-9, "SES = 22.5")                          # 81
    _assert(es >= 10.0 and es <= 30.0, "SES between data values")         # 82

    var es_low = exponential_smoothing_forecast(data, 0.1)
    _assert(es_low >= 10.0 and es_low <= 30.0, "SES(a=0.1) in bounds")   # 83
    _assert(es_low < es, "lower alpha -> lower forecast")                  # 84
    print("  ✓ exponential_smoothing_forecast")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("=== Wave 44 Tests ===")

    print("\n-- Feature Selection --")
    test_column_mean()
    test_column_variance()
    test_variance_threshold()
    test_correlation_filter()
    test_f_test_scores()
    test_select_k_best()
    test_forward_selection_greedy()
    test_information_gain()
    test_feature_importance_permutation()

    print("\n-- ChaCha20 --")
    test_rotl32()
    test_quarter_round()
    test_chacha20_init_state()
    test_chacha20_block()
    test_add_xor_states()
    test_chacha20_roundtrip()
    test_chacha20_different_nonces()

    print("\n-- Supply Chain --")
    test_lead_time_demand()
    test_bullwhip_effect()
    test_forecast_error_mae()
    test_forecast_error_mape()
    test_forecast_bias()
    test_tracking_signal()
    test_economic_production_qty()
    test_total_cost_of_ownership()
    test_service_level_type1()
    test_fill_rate_type2()
    test_moving_average_forecast()
    test_exponential_smoothing_forecast()

    print("\n All 84 Wave 44 assertions passed!")
