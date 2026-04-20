"""
test_wave10.mojo — Tests for Wave 10 libraries: Interpolation, Random Sampling, Signal Processing.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_wave10.mojo
"""
from interpolate import (
    linear_interp,
    nearest_interp,
    cubic_spline_natural,
    lagrange_interp,
    interp_array,
    extrapolate_linear,
)
from random_utils import (
    random_choice,
    random_shuffle,
    random_sample,
    random_bootstrap,
    random_uniform_int,
    random_permutation,
    stratified_sample,
)
from signal.dsp import (
    moving_average,
    exponential_moving_average,
    diff,
    cumsum,
    convolve,
    autocorrelation,
    detrend_linear,
    normalize_signal,
    zero_crossings,
    peak_detect,
)
from std.math import abs as fabs
from testing import assert_true


def main() raises:
    print("━━━ Wave 10 test suite (Interpolation, Random, Signal) ━━━")
    print("")

    # ── Interpolation ─────────────────────────────────────────────────────
    var x = List[Float64]()
    x.append(0.0)
    x.append(1.0)
    x.append(2.0)
    x.append(3.0)
    var y = List[Float64]()
    y.append(0.0)
    y.append(1.0)
    y.append(4.0)
    y.append(9.0)

    # Linear interp at x=0.5 should give 0.5 (between 0 and 1)
    var li05 = linear_interp(x, y, 0.5)
    assert_true(fabs(li05 - 0.5) < 0.01, "linear_interp(0.5) should be ~0.5, got " + String(li05))

    # Linear interp at x=1.5 should give 2.5 (between 1 and 4)
    var li15 = linear_interp(x, y, 1.5)
    assert_true(fabs(li15 - 2.5) < 0.01, "linear_interp(1.5) should be ~2.5, got " + String(li15))

    # Nearest interp at x=0.3 → nearest to 0.0 → y=0
    var ni03 = nearest_interp(x, y, 0.3)
    assert_true(fabs(ni03 - 0.0) < 0.01, "nearest_interp(0.3) should be ~0.0, got " + String(ni03))

    # Nearest interp at x=0.7 → nearest to 1.0 → y=1
    var ni07 = nearest_interp(x, y, 0.7)
    assert_true(fabs(ni07 - 1.0) < 0.01, "nearest_interp(0.7) should be ~1.0, got " + String(ni07))

    # Lagrange at exact point should return exact value
    var lag2 = lagrange_interp(x, y, 2.0)
    assert_true(fabs(lag2 - 4.0) < 0.01, "lagrange_interp(2.0) should be ~4.0, got " + String(lag2))

    # Lagrange on x^2 data — at x=1.5, should give 2.25 (exact for degree 2 polynomial through 4 pts of x^2)
    var lag15 = lagrange_interp(x, y, 1.5)
    assert_true(fabs(lag15 - 2.25) < 0.01, "lagrange_interp(1.5) should be ~2.25, got " + String(lag15))

    # Cubic spline at exact points
    var cs2 = cubic_spline_natural(x, y, 2.0)
    assert_true(fabs(cs2 - 4.0) < 0.01, "cubic_spline(2.0) should be ~4.0, got " + String(cs2))

    # interp_array: linear method
    var x_new = List[Float64]()
    x_new.append(0.5)
    x_new.append(1.5)
    x_new.append(2.5)
    var arr = interp_array(x, y, x_new, "linear")
    assert_true(len(arr) == 3, "interp_array should return 3 values")
    assert_true(fabs(arr[0] - 0.5) < 0.01, "interp_array[0] should be ~0.5")
    assert_true(fabs(arr[1] - 2.5) < 0.01, "interp_array[1] should be ~2.5")

    # extrapolate_linear beyond right edge
    var ext = extrapolate_linear(x, y, 4.0)
    # Last slope = (9-4)/(3-2) = 5, so at x=4: 9 + 5*1 = 14
    assert_true(fabs(ext - 14.0) < 0.01, "extrapolate_linear(4.0) should be ~14.0, got " + String(ext))

    # extrapolate_linear beyond left edge
    var ext_l = extrapolate_linear(x, y, -1.0)
    # First slope = (1-0)/(1-0) = 1, so at x=-1: 0 + 1*(-1) = -1
    assert_true(fabs(ext_l - (-1.0)) < 0.01, "extrapolate_linear(-1.0) should be ~-1.0, got " + String(ext_l))

    print("✅ Interpolation")

    # ── Random Utils ──────────────────────────────────────────────────────
    var weights = List[Float64]()
    weights.append(0.1)
    weights.append(0.9)
    var choice = random_choice(weights)
    assert_true(choice == 0 or choice == 1, "random_choice should return 0 or 1")

    var perm = random_permutation(5)
    assert_true(len(perm) == 5, "random_permutation(5) should have 5 elements")
    # Check all elements 0..4 are present (sum check)
    var perm_sum = 0
    for i in range(5):
        perm_sum += perm[i]
    assert_true(perm_sum == 10, "permutation sum should be 0+1+2+3+4=10")

    var data2 = List[Float64]()
    data2.append(1.0)
    data2.append(2.0)
    data2.append(3.0)
    data2.append(4.0)
    data2.append(5.0)

    var sampled = random_sample(data2, 3)
    assert_true(len(sampled) == 3, "random_sample(3) should have 3 elements")

    var bootstrapped = random_bootstrap(data2, 10)
    assert_true(len(bootstrapped) == 10, "random_bootstrap(10) should have 10 elements")
    # All bootstrapped values should be from original data [1,5]
    for i in range(len(bootstrapped)):
        assert_true(bootstrapped[i] >= 1.0 and bootstrapped[i] <= 5.0, "bootstrap value out of range")

    var ri = random_uniform_int(10, 20)
    assert_true(ri >= 10 and ri < 20, "random_uniform_int should be in [10, 20)")

    # Shuffle test — length preserved
    var shuf = List[Float64]()
    shuf.append(1.0)
    shuf.append(2.0)
    shuf.append(3.0)
    shuf.append(4.0)
    shuf.append(5.0)
    random_shuffle(shuf)
    assert_true(len(shuf) == 5, "shuffle should preserve length")
    # Sum preserved (elements just reordered)
    var shuf_sum: Float64 = 0.0
    for i in range(len(shuf)):
        shuf_sum += shuf[i]
    assert_true(fabs(shuf_sum - 15.0) < 0.01, "shuffle should preserve sum")

    # Stratified sample
    var strat = stratified_sample(data2, 3)
    assert_true(len(strat) == 3, "stratified_sample(3) should return 3 elements")

    print("✅ Random utils")

    # ── Signal Processing ─────────────────────────────────────────────────
    var sig = List[Float64]()
    sig.append(1.0)
    sig.append(3.0)
    sig.append(5.0)
    sig.append(7.0)
    sig.append(9.0)

    var ma = moving_average(sig, 3)
    assert_true(len(ma) == 5, "moving_average should return same length")
    assert_true(fabs(ma[1] - 3.0) < 0.01, "ma[1] should be ~3.0 (avg of 1,3,5), got " + String(ma[1]))
    assert_true(fabs(ma[2] - 5.0) < 0.01, "ma[2] should be ~5.0 (avg of 3,5,7), got " + String(ma[2]))

    var ema = exponential_moving_average(sig, 0.5)
    assert_true(len(ema) == 5, "EMA should return same length")
    assert_true(fabs(ema[0] - 1.0) < 0.01, "EMA[0] should be 1.0")

    var cs = cumsum(sig)
    assert_true(fabs(cs[0] - 1.0) < 0.01, "cumsum[0] should be 1.0")
    assert_true(fabs(cs[4] - 25.0) < 0.01, "cumsum[4] should be 25.0 (1+3+5+7+9)")

    var d = diff(sig)
    assert_true(len(d) == 4, "diff should return n-1 elements")
    assert_true(fabs(d[0] - 2.0) < 0.01, "diff[0] should be 2.0 (3-1)")
    assert_true(fabs(d[1] - 2.0) < 0.01, "diff[1] should be 2.0 (5-3)")

    # Convolution: signal [1, 2, 3] * kernel [1, 1] = [1, 3, 5, 3]
    var conv_sig = List[Float64]()
    conv_sig.append(1.0)
    conv_sig.append(2.0)
    conv_sig.append(3.0)
    var conv_kern = List[Float64]()
    conv_kern.append(1.0)
    conv_kern.append(1.0)
    var conv_result = convolve(conv_sig, conv_kern)
    assert_true(len(conv_result) == 4, "convolve output length should be 3+2-1=4")
    assert_true(fabs(conv_result[0] - 1.0) < 0.01, "conv[0] should be 1.0")
    assert_true(fabs(conv_result[1] - 3.0) < 0.01, "conv[1] should be 3.0")
    assert_true(fabs(conv_result[2] - 5.0) < 0.01, "conv[2] should be 5.0")
    assert_true(fabs(conv_result[3] - 3.0) < 0.01, "conv[3] should be 3.0")

    # Autocorrelation: lag 0 should be 1.0
    var ac = autocorrelation(sig, 3)
    assert_true(fabs(ac[0] - 1.0) < 0.01, "autocorrelation[0] should be 1.0")

    # Detrend: constant slope signal → ~zero after detrend
    var detrended = detrend_linear(sig)
    assert_true(len(detrended) == 5, "detrend should return same length")
    # Mean of detrended should be ~0
    var dt_mean: Float64 = 0.0
    for i in range(len(detrended)):
        dt_mean += detrended[i]
    dt_mean /= Float64(len(detrended))
    assert_true(fabs(dt_mean) < 0.01, "detrended mean should be ~0, got " + String(dt_mean))
    # Max absolute value should be small for a perfect linear signal
    var dt_max: Float64 = 0.0
    for i in range(len(detrended)):
        if fabs(detrended[i]) > dt_max:
            dt_max = fabs(detrended[i])
    assert_true(dt_max < 0.01, "detrended max abs should be ~0 for linear signal")

    # Normalize
    var normed = normalize_signal(sig)
    assert_true(fabs(normed[0] - (-1.0)) < 0.01, "normalize_signal[0] should be -1.0")
    assert_true(fabs(normed[4] - 1.0) < 0.01, "normalize_signal[4] should be 1.0")

    # Zero crossings: signal [-1, 1, -1, 1] has 3 crossings
    var zc_data = List[Float64]()
    zc_data.append(-1.0)
    zc_data.append(1.0)
    zc_data.append(-1.0)
    zc_data.append(1.0)
    var zc = zero_crossings(zc_data)
    assert_true(zc == 3, "zero_crossings should be 3, got " + String(zc))

    # Peak detection: [0, 5, 1, 8, 2] with threshold 3 → peaks at indices 1 and 3
    var pk_data = List[Float64]()
    pk_data.append(0.0)
    pk_data.append(5.0)
    pk_data.append(1.0)
    pk_data.append(8.0)
    pk_data.append(2.0)
    var peaks = peak_detect(pk_data, 3.0)
    assert_true(len(peaks) == 2, "peak_detect should find 2 peaks, got " + String(len(peaks)))
    assert_true(peaks[0] == 1, "first peak at index 1")
    assert_true(peaks[1] == 3, "second peak at index 3")

    print("✅ Signal processing")

    print("")
    print("✅ All Wave 10 tests passed")
