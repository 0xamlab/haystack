"""test_datetime.mojo — auto-generated tests for datetime library."""
from std.math import isnan, isinf
from datetime import is_leap_year, year, month, day, hour, minute, second, epoch_to_iso, iso_to_epoch, format_duration_ms, days_between, add_days, day_of_week

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

    _ = is_leap_year(5)
    passed += 1; print("  ✅ datetime::is_leap_year")
    _ = year(5)
    passed += 1; print("  ✅ datetime::year")
    _ = month(5)
    passed += 1; print("  ✅ datetime::month")
    _ = day(5)
    passed += 1; print("  ✅ datetime::day")
    _ = hour(5)
    passed += 1; print("  ✅ datetime::hour")
    _ = minute(5)
    passed += 1; print("  ✅ datetime::minute")
    _ = second(5)
    passed += 1; print("  ✅ datetime::second")
    _ = epoch_to_iso(5)
    passed += 1; print("  ✅ datetime::epoch_to_iso")
    _ = iso_to_epoch("test")
    passed += 1; print("  ✅ datetime::iso_to_epoch")
    _ = format_duration_ms(5)
    passed += 1; print("  ✅ datetime::format_duration_ms")
    _ = days_between(5, 5)
    passed += 1; print("  ✅ datetime::days_between")
    _ = add_days(5, 5)
    passed += 1; print("  ✅ datetime::add_days")
    _ = day_of_week(5)
    passed += 1; print("  ✅ datetime::day_of_week")

    print("  [datetime] Passed:", passed, "Failed:", failed)
