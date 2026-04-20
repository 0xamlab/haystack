"""test_units.mojo — auto-generated tests for units library."""
from std.math import isnan, isinf
from units import convert_length, convert_mass, convert_temperature, convert_time, convert_area, convert_volume, convert_speed, convert_data

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

    var _v_convert_length = convert_length(0.5, "test", "test")
    if is_finite(_v_convert_length): passed += 1; print("  ✅ units::convert_length =", _v_convert_length)
    else: failed += 1; print("  ❌ units::convert_length → non-finite:", _v_convert_length)
    var _v_convert_mass = convert_mass(0.5, "test", "test")
    if is_finite(_v_convert_mass): passed += 1; print("  ✅ units::convert_mass =", _v_convert_mass)
    else: failed += 1; print("  ❌ units::convert_mass → non-finite:", _v_convert_mass)
    var _v_convert_temperature = convert_temperature(0.5, "test", "test")
    if is_finite(_v_convert_temperature): passed += 1; print("  ✅ units::convert_temperature =", _v_convert_temperature)
    else: failed += 1; print("  ❌ units::convert_temperature → non-finite:", _v_convert_temperature)
    var _v_convert_time = convert_time(0.5, "test", "test")
    if is_finite(_v_convert_time): passed += 1; print("  ✅ units::convert_time =", _v_convert_time)
    else: failed += 1; print("  ❌ units::convert_time → non-finite:", _v_convert_time)
    var _v_convert_area = convert_area(0.5, "test", "test")
    if is_finite(_v_convert_area): passed += 1; print("  ✅ units::convert_area =", _v_convert_area)
    else: failed += 1; print("  ❌ units::convert_area → non-finite:", _v_convert_area)
    var _v_convert_volume = convert_volume(0.5, "test", "test")
    if is_finite(_v_convert_volume): passed += 1; print("  ✅ units::convert_volume =", _v_convert_volume)
    else: failed += 1; print("  ❌ units::convert_volume → non-finite:", _v_convert_volume)
    var _v_convert_speed = convert_speed(0.5, "test", "test")
    if is_finite(_v_convert_speed): passed += 1; print("  ✅ units::convert_speed =", _v_convert_speed)
    else: failed += 1; print("  ❌ units::convert_speed → non-finite:", _v_convert_speed)
    var _v_convert_data = convert_data(0.5, "test", "test")
    if is_finite(_v_convert_data): passed += 1; print("  ✅ units::convert_data =", _v_convert_data)
    else: failed += 1; print("  ❌ units::convert_data → non-finite:", _v_convert_data)

    print("  [units] Passed:", passed, "Failed:", failed)
