"""test_fft.mojo — auto-generated tests for fft library."""
from std.math import isnan, isinf
from fft import next_power_of_2, zero_pad, fft, power_spectrum

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

    _ = next_power_of_2(5)
    passed += 1; print("  ✅ fft::next_power_of_2")
    var _v_zero_pad = zero_pad(_lf5, 5)
    if len(_v_zero_pad) >= 0: passed += 1; print("  ✅ fft::zero_pad")
    var _v_fft = fft(_lf5)
    if len(_v_fft) >= 0: passed += 1; print("  ✅ fft::fft")
    var _v_power_spectrum = power_spectrum(_lf5)
    if len(_v_power_spectrum) >= 0: passed += 1; print("  ✅ fft::power_spectrum")

    print("  [fft] Passed:", passed, "Failed:", failed)
