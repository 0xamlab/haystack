"""Tests for Wave 21 — Kalman Filter, Queueing Theory, LZ77 Compression."""

from kalman import (
    KalmanState,
    kalman_predict,
    kalman_update,
    kalman_smooth_1d,
    mat_mul,
    mat_transpose,
    mat_add,
    mat_sub,
    mat_scale,
    mat_identity,
    mat_inv_2x2,
    matvec,
)
from queueing import (
    mm1_utilization,
    mm1_avg_queue_length,
    mm1_avg_system_size,
    mm1_avg_wait_time,
    mm1_avg_system_time,
    mmc_erlang_c,
    mmc_avg_wait_time,
    erlang_b,
    factorial,
    littles_law_L,
    littles_law_W,
)
from compression.lz77 import (
    LZ77Token,
    lz77_encode,
    lz77_decode,
    bytes_to_ints,
    ints_to_string,
    compression_ratio,
    find_longest_match,
)
from std.math import abs as fabs


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


fn test_kalman() raises:
    print("── Kalman Filter tests ──")
    var n_pass: Int = 0

    # 1. mat_identity(3) — 3×3 with 1s on diagonal, 0s off
    var I3 = mat_identity(3)
    _assert(len(I3) == 3, "identity rows == 3")
    n_pass += 1
    _assert(len(I3[0]) == 3, "identity cols == 3")
    n_pass += 1
    _assert_close(I3[0][0], 1.0, 1e-12, "I[0][0] == 1")
    n_pass += 1
    _assert_close(I3[0][1], 0.0, 1e-12, "I[0][1] == 0")
    n_pass += 1
    _assert_close(I3[1][1], 1.0, 1e-12, "I[1][1] == 1")
    n_pass += 1
    _assert_close(I3[2][2], 1.0, 1e-12, "I[2][2] == 1")
    n_pass += 1
    _assert_close(I3[1][0], 0.0, 1e-12, "I[1][0] == 0")
    n_pass += 1

    # 2. mat_mul of identity with any matrix — returns same matrix
    var A = List[List[Float64]]()
    var a_r0 = List[Float64]()
    a_r0.append(1.0)
    a_r0.append(2.0)
    a_r0.append(3.0)
    A.append(a_r0^)
    var a_r1 = List[Float64]()
    a_r1.append(4.0)
    a_r1.append(5.0)
    a_r1.append(6.0)
    A.append(a_r1^)
    var a_r2 = List[Float64]()
    a_r2.append(7.0)
    a_r2.append(8.0)
    a_r2.append(9.0)
    A.append(a_r2^)
    var IA = mat_mul(I3, A)
    _assert_close(IA[0][0], 1.0, 1e-12, "I*A [0][0] == 1")
    n_pass += 1
    _assert_close(IA[1][1], 5.0, 1e-12, "I*A [1][1] == 5")
    n_pass += 1
    _assert_close(IA[2][2], 9.0, 1e-12, "I*A [2][2] == 9")
    n_pass += 1

    # 3. mat_transpose of 2×3 — returns 3×2
    var B = List[List[Float64]]()
    var b_r0 = List[Float64]()
    b_r0.append(1.0)
    b_r0.append(2.0)
    b_r0.append(3.0)
    B.append(b_r0^)
    var b_r1 = List[Float64]()
    b_r1.append(4.0)
    b_r1.append(5.0)
    b_r1.append(6.0)
    B.append(b_r1^)
    var Bt = mat_transpose(B)
    _assert(len(Bt) == 3, "transpose of 2x3 has 3 rows")
    n_pass += 1
    _assert(len(Bt[0]) == 2, "transpose of 2x3 has 2 cols")
    n_pass += 1
    _assert_close(Bt[0][0], 1.0, 1e-12, "Bt[0][0] == 1")
    n_pass += 1
    _assert_close(Bt[2][1], 6.0, 1e-12, "Bt[2][1] == 6")
    n_pass += 1

    # 4. mat_inv_2x2 of known matrix — verify A * A_inv ≈ I
    var M = List[List[Float64]]()
    var m_r0 = List[Float64]()
    m_r0.append(4.0)
    m_r0.append(7.0)
    M.append(m_r0^)
    var m_r1 = List[Float64]()
    m_r1.append(2.0)
    m_r1.append(6.0)
    M.append(m_r1^)
    var M_inv = mat_inv_2x2(M)
    var prod = mat_mul(M, M_inv)
    _assert_close(prod[0][0], 1.0, 1e-10, "M*M_inv [0][0] ≈ 1")
    n_pass += 1
    _assert_close(prod[0][1], 0.0, 1e-10, "M*M_inv [0][1] ≈ 0")
    n_pass += 1
    _assert_close(prod[1][0], 0.0, 1e-10, "M*M_inv [1][0] ≈ 0")
    n_pass += 1
    _assert_close(prod[1][1], 1.0, 1e-10, "M*M_inv [1][1] ≈ 1")
    n_pass += 1

    # 5. matvec with identity — returns same vector
    var v3 = List[Float64]()
    v3.append(3.0)
    v3.append(7.0)
    v3.append(11.0)
    var Iv = matvec(I3, v3)
    _assert_close(Iv[0], 3.0, 1e-12, "I*v[0] == 3")
    n_pass += 1
    _assert_close(Iv[1], 7.0, 1e-12, "I*v[1] == 7")
    n_pass += 1
    _assert_close(Iv[2], 11.0, 1e-12, "I*v[2] == 11")
    n_pass += 1

    # 6. kalman_predict — state changes, covariance grows
    var x0 = List[Float64]()
    x0.append(0.0)
    x0.append(1.0)
    var P0 = mat_identity(2)
    var state0 = KalmanState(x0, P0)

    # F = [[1, 1], [0, 1]] (constant velocity model)
    var F = List[List[Float64]]()
    var f_r0 = List[Float64]()
    f_r0.append(1.0)
    f_r0.append(1.0)
    F.append(f_r0^)
    var f_r1 = List[Float64]()
    f_r1.append(0.0)
    f_r1.append(1.0)
    F.append(f_r1^)

    var Q = mat_scale(mat_identity(2), 0.1)
    var pred = kalman_predict(state0, F, Q)
    # x' = F*x = [0+1, 0+1] = [1, 1]
    _assert_close(pred.x[0], 1.0, 1e-10, "predict x[0] == 1")
    n_pass += 1
    _assert_close(pred.x[1], 1.0, 1e-10, "predict x[1] == 1")
    n_pass += 1
    # P grows: P' = F*P*F^T + Q, should be > P
    _assert(pred.P[0][0] > P0[0][0], "predict P[0][0] grows")
    n_pass += 1

    # 7. kalman_update with measurement — state moves toward measurement
    var z = List[Float64]()
    z.append(2.0)  # measurement: position = 2.0
    var H = List[List[Float64]]()
    var h_r0 = List[Float64]()
    h_r0.append(1.0)
    h_r0.append(0.0)
    H.append(h_r0^)
    var R = List[List[Float64]]()
    var r_r0 = List[Float64]()
    r_r0.append(0.5)
    R.append(r_r0^)
    var upd = kalman_update(pred, z, H, R)
    # Updated position should be between predicted (1.0) and measurement (2.0)
    _assert(upd.x[0] > 1.0, "update x[0] > predicted")
    n_pass += 1
    _assert(upd.x[0] < 2.0, "update x[0] < measurement")
    n_pass += 1

    # 8. kalman_smooth_1d on noisy signal
    var measurements = List[Float64]()
    measurements.append(1.0)
    measurements.append(1.2)
    measurements.append(0.8)
    measurements.append(1.1)
    measurements.append(0.9)
    measurements.append(1.0)
    measurements.append(1.3)
    measurements.append(0.7)
    measurements.append(1.1)
    measurements.append(0.95)
    var filtered = kalman_smooth_1d(measurements, 0.01, 0.5)

    # 9. Output length equals input length
    _assert(len(filtered) == len(measurements), "smooth_1d output length == input length")
    n_pass += 1

    # Filtered values should have less variance
    var mean_m: Float64 = 0.0
    var mean_f: Float64 = 0.0
    for i in range(len(measurements)):
        mean_m += measurements[i]
        mean_f += filtered[i]
    mean_m /= Float64(len(measurements))
    mean_f /= Float64(len(filtered))

    var var_m: Float64 = 0.0
    var var_f: Float64 = 0.0
    for i in range(len(measurements)):
        var dm = measurements[i] - mean_m
        var df = filtered[i] - mean_f
        var_m += dm * dm
        var_f += df * df
    var_m /= Float64(len(measurements))
    var_f /= Float64(len(filtered))

    _assert(var_f < var_m, "filtered variance < measurement variance")
    n_pass += 1

    # 10. mat_add and mat_sub
    var S = mat_add(I3, I3)
    _assert_close(S[0][0], 2.0, 1e-12, "I+I [0][0] == 2")
    n_pass += 1
    var D = mat_sub(S, I3)
    _assert_close(D[1][1], 1.0, 1e-12, "(I+I)-I [1][1] == 1")
    n_pass += 1

    # 11. mat_scale
    var Sc = mat_scale(I3, 5.0)
    _assert_close(Sc[0][0], 5.0, 1e-12, "5*I [0][0] == 5")
    n_pass += 1
    _assert_close(Sc[0][1], 0.0, 1e-12, "5*I [0][1] == 0")
    n_pass += 1

    print("  Kalman: " + String(n_pass) + " assertions passed")


fn test_queueing() raises:
    print("── Queueing Theory tests ──")
    var n_pass: Int = 0

    # 1. mm1_utilization(4.0, 5.0) ≈ 0.8
    _assert_close(mm1_utilization(4.0, 5.0), 0.8, 1e-10, "mm1 rho == 0.8")
    n_pass += 1

    # 2. mm1_avg_system_size(4.0, 5.0) ≈ 4.0
    _assert_close(mm1_avg_system_size(4.0, 5.0), 4.0, 1e-10, "mm1 L == 4.0")
    n_pass += 1

    # 3. mm1_avg_system_time(4.0, 5.0) ≈ 1.0
    _assert_close(mm1_avg_system_time(4.0, 5.0), 1.0, 1e-10, "mm1 W == 1.0")
    n_pass += 1

    # 4. mm1_avg_wait_time(4.0, 5.0) ≈ 0.8
    _assert_close(mm1_avg_wait_time(4.0, 5.0), 0.8, 1e-10, "mm1 Wq == 0.8")
    n_pass += 1

    # 5. mm1_avg_queue_length(4.0, 5.0) ≈ 3.2
    _assert_close(mm1_avg_queue_length(4.0, 5.0), 3.2, 1e-10, "mm1 Lq == 3.2")
    n_pass += 1

    # 6. littles_law_L(4.0, 1.0) ≈ 4.0
    _assert_close(littles_law_L(4.0, 1.0), 4.0, 1e-10, "Little L = 4")
    n_pass += 1

    # 7. littles_law_W(4.0, 4.0) ≈ 1.0
    _assert_close(littles_law_W(4.0, 4.0), 1.0, 1e-10, "Little W = 1")
    n_pass += 1

    # 8. erlang_b(1.0, 1) — between 0 and 1
    var eb = erlang_b(1.0, 1)
    _assert(eb > 0.0, "erlang_b > 0")
    n_pass += 1
    _assert(eb < 1.0, "erlang_b < 1")
    n_pass += 1
    # B(1,1) = 1/(1+1) = 0.5
    _assert_close(eb, 0.5, 1e-10, "erlang_b(1,1) == 0.5")
    n_pass += 1

    # 9. mmc_erlang_c — probability between 0 and 1
    var ec = mmc_erlang_c(4.0, 5.0, 2)
    _assert(ec >= 0.0, "erlang_c >= 0")
    n_pass += 1
    _assert(ec <= 1.0, "erlang_c <= 1")
    n_pass += 1

    # 10. mmc_avg_wait_time — smaller with more servers
    var wq2 = mmc_avg_wait_time(4.0, 5.0, 2)
    var wq3 = mmc_avg_wait_time(4.0, 5.0, 3)
    _assert(wq3 < wq2, "more servers -> less wait")
    n_pass += 1

    # 11. factorial(0) == 1.0, factorial(5) == 120.0
    _assert_close(factorial(0), 1.0, 1e-10, "0! == 1")
    n_pass += 1
    _assert_close(factorial(5), 120.0, 1e-10, "5! == 120")
    n_pass += 1
    _assert_close(factorial(1), 1.0, 1e-10, "1! == 1")
    n_pass += 1
    _assert_close(factorial(10), 3628800.0, 1e-6, "10! == 3628800")
    n_pass += 1

    # 12. Little's law consistency check: L = λ * W for M/M/1
    var lam = 4.0
    var mu = 5.0
    var W_mm1 = mm1_avg_system_time(lam, mu)
    var L_mm1 = mm1_avg_system_size(lam, mu)
    _assert_close(L_mm1, littles_law_L(lam, W_mm1), 1e-10, "Little's law consistent with M/M/1")
    n_pass += 1

    print("  Queueing: " + String(n_pass) + " assertions passed")


fn test_lz77() raises:
    print("── LZ77 Compression tests ──")
    var n_pass: Int = 0

    # 1. bytes_to_ints("hello") — correct byte values
    var hello_ints = bytes_to_ints("hello")
    _assert(len(hello_ints) == 5, "bytes_to_ints('hello') len == 5")
    n_pass += 1
    _assert(hello_ints[0] == 104, "h == 104")
    n_pass += 1
    _assert(hello_ints[1] == 101, "e == 101")
    n_pass += 1
    _assert(hello_ints[4] == 111, "o == 111")
    n_pass += 1

    # 2. ints_to_string(bytes_to_ints("hello")) == "hello" (roundtrip)
    var rt = ints_to_string(hello_ints)
    _assert(rt == "hello", "string roundtrip == hello")
    n_pass += 1

    # 3. lz77_encode on simple data — verify tokens produced
    var simple_data = bytes_to_ints("ABCABC")
    var tokens = lz77_encode(simple_data)
    _assert(len(tokens) > 0, "encode produces tokens")
    n_pass += 1

    # 4. lz77_decode(lz77_encode(data)) — roundtrip
    var decoded = lz77_decode(tokens)
    _assert(len(decoded) == len(simple_data), "roundtrip length matches")
    n_pass += 1
    var all_eq = True
    for i in range(len(simple_data)):
        if decoded[i] != simple_data[i]:
            all_eq = False
    _assert(all_eq, "roundtrip ABCABC matches")
    n_pass += 1

    # 5. lz77_encode on "AAAAAA" — should have back-references
    var repeat_data = bytes_to_ints("AAAAAA")
    var rep_tokens = lz77_encode(repeat_data)
    var has_backref = False
    for i in range(len(rep_tokens)):
        if rep_tokens[i].offset > 0:
            has_backref = True
    _assert(has_backref, "AAAAAA has back-references")
    n_pass += 1

    # 6. Decode roundtrip of AAAAAA
    var rep_decoded = lz77_decode(rep_tokens)
    _assert(len(rep_decoded) == 6, "AAAAAA roundtrip len == 6")
    n_pass += 1
    var rep_eq = True
    for i in range(len(repeat_data)):
        if rep_decoded[i] != repeat_data[i]:
            rep_eq = False
    _assert(rep_eq, "AAAAAA roundtrip matches")
    n_pass += 1

    # 7. compression_ratio — positive value
    var cr = compression_ratio(100, 20)
    _assert(cr > 0.0, "compression ratio > 0")
    n_pass += 1
    _assert_close(cr, 100.0 / 60.0, 1e-10, "compression_ratio(100,20) == 100/60")
    n_pass += 1

    # 8. find_longest_match on known pattern
    var pattern_data = bytes_to_ints("ABCDABCE")
    var fmatch = find_longest_match(pattern_data, 4, 256, 16)
    _assert(fmatch[0] == 4, "match offset == 4 (ABCD at pos 0)")
    n_pass += 1
    _assert(fmatch[1] == 3, "match length == 3 (ABC)")
    n_pass += 1

    # 9. Encode/decode roundtrip on longer string with repeats
    var long_str = "the quick brown fox jumps over the lazy dog the quick brown fox"
    var long_data = bytes_to_ints(long_str)
    var long_tokens = lz77_encode(long_data)
    var long_decoded = lz77_decode(long_tokens)
    _assert(len(long_decoded) == len(long_data), "long roundtrip length")
    n_pass += 1
    var long_eq = True
    for i in range(len(long_data)):
        if long_decoded[i] != long_data[i]:
            long_eq = False
    _assert(long_eq, "long roundtrip matches")
    n_pass += 1

    # 10. String conversion roundtrip on the long string
    var long_rt = ints_to_string(long_decoded)
    _assert(long_rt == long_str, "long string roundtrip")
    n_pass += 1

    # 11. Empty data produces no tokens
    var empty = List[Int]()
    var empty_tokens = lz77_encode(empty)
    _assert(len(empty_tokens) == 0, "empty data -> 0 tokens")
    n_pass += 1

    # 12. Compression ratio edge case
    _assert_close(compression_ratio(0, 0), 0.0, 1e-12, "compression_ratio(0,0) == 0")
    n_pass += 1

    print("  LZ77: " + String(n_pass) + " assertions passed")


fn main() raises:
    print("=== Wave 21 Tests: Kalman, Queueing, LZ77 ===")
    test_kalman()
    test_queueing()
    test_lz77()
    print("=== All Wave 21 tests passed ===")
