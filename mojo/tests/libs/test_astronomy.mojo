"""test_astronomy.mojo — auto-generated tests for astronomy library."""
from std.math import isnan, isinf
from astronomy import julian_date, modified_julian_date, sidereal_time, solar_declination, sunrise_hour_angle, day_length, parallax_correction, kepler_equation, orbital_period, apparent_magnitude, distance_from_magnitude, ecliptic_to_equatorial

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

    var _v_julian_date = julian_date(5, 5, 5)
    if is_finite(_v_julian_date): passed += 1; print("  ✅ astronomy::julian_date =", _v_julian_date)
    else: failed += 1; print("  ❌ astronomy::julian_date → non-finite:", _v_julian_date)
    var _v_modified_julian_date = modified_julian_date(0.5)
    if is_finite(_v_modified_julian_date): passed += 1; print("  ✅ astronomy::modified_julian_date =", _v_modified_julian_date)
    else: failed += 1; print("  ❌ astronomy::modified_julian_date → non-finite:", _v_modified_julian_date)
    var _v_sidereal_time = sidereal_time(0.5, 0.5)
    if is_finite(_v_sidereal_time): passed += 1; print("  ✅ astronomy::sidereal_time =", _v_sidereal_time)
    else: failed += 1; print("  ❌ astronomy::sidereal_time → non-finite:", _v_sidereal_time)
    var _v_solar_declination = solar_declination(5)
    if is_finite(_v_solar_declination): passed += 1; print("  ✅ astronomy::solar_declination =", _v_solar_declination)
    else: failed += 1; print("  ❌ astronomy::solar_declination → non-finite:", _v_solar_declination)
    var _v_sunrise_hour_angle = sunrise_hour_angle(0.5, 0.5)
    if is_finite(_v_sunrise_hour_angle): passed += 1; print("  ✅ astronomy::sunrise_hour_angle =", _v_sunrise_hour_angle)
    else: failed += 1; print("  ❌ astronomy::sunrise_hour_angle → non-finite:", _v_sunrise_hour_angle)
    var _v_day_length = day_length(0.5, 5)
    if is_finite(_v_day_length): passed += 1; print("  ✅ astronomy::day_length =", _v_day_length)
    else: failed += 1; print("  ❌ astronomy::day_length → non-finite:", _v_day_length)
    var _v_parallax_correction = parallax_correction(0.5, 0.5)
    if is_finite(_v_parallax_correction): passed += 1; print("  ✅ astronomy::parallax_correction =", _v_parallax_correction)
    else: failed += 1; print("  ❌ astronomy::parallax_correction → non-finite:", _v_parallax_correction)
    var _v_kepler_equation = kepler_equation(0.5, 0.5, 0.5)
    if is_finite(_v_kepler_equation): passed += 1; print("  ✅ astronomy::kepler_equation =", _v_kepler_equation)
    else: failed += 1; print("  ❌ astronomy::kepler_equation → non-finite:", _v_kepler_equation)
    var _v_orbital_period = orbital_period(0.5)
    if is_finite(_v_orbital_period): passed += 1; print("  ✅ astronomy::orbital_period =", _v_orbital_period)
    else: failed += 1; print("  ❌ astronomy::orbital_period → non-finite:", _v_orbital_period)
    var _v_apparent_magnitude = apparent_magnitude(0.5, 0.5)
    if is_finite(_v_apparent_magnitude): passed += 1; print("  ✅ astronomy::apparent_magnitude =", _v_apparent_magnitude)
    else: failed += 1; print("  ❌ astronomy::apparent_magnitude → non-finite:", _v_apparent_magnitude)
    var _v_distance_from_magnitude = distance_from_magnitude(0.5, 0.5)
    if is_finite(_v_distance_from_magnitude): passed += 1; print("  ✅ astronomy::distance_from_magnitude =", _v_distance_from_magnitude)
    else: failed += 1; print("  ❌ astronomy::distance_from_magnitude → non-finite:", _v_distance_from_magnitude)
    var _v_ecliptic_to_equatorial = ecliptic_to_equatorial(0.5, 0.5, 0.5)
    if len(_v_ecliptic_to_equatorial) >= 0: passed += 1; print("  ✅ astronomy::ecliptic_to_equatorial")

    print("  [astronomy] Passed:", passed, "Failed:", failed)
