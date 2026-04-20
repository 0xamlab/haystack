"""test_cartography.mojo — auto-generated tests for cartography library."""
from std.math import isnan, isinf
from cartography import scale_factor, representative_fraction, ground_distance_from_map, map_distance_from_ground, latitude_to_utm_zone, mercator_y, equirectangular_x, equirectangular_y, great_circle_distance, map_area_at_scale, contour_interval_suggestion, declination_correction

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

    var _v_scale_factor = scale_factor(0.5, 0.5)
    if is_finite(_v_scale_factor): passed += 1; print("  ✅ cartography::scale_factor =", _v_scale_factor)
    else: failed += 1; print("  ❌ cartography::scale_factor → non-finite:", _v_scale_factor)
    var _v_representative_fraction = representative_fraction(0.5, 0.5)
    if is_finite(_v_representative_fraction): passed += 1; print("  ✅ cartography::representative_fraction =", _v_representative_fraction)
    else: failed += 1; print("  ❌ cartography::representative_fraction → non-finite:", _v_representative_fraction)
    var _v_ground_distance_from_map = ground_distance_from_map(0.5, 0.5)
    if is_finite(_v_ground_distance_from_map): passed += 1; print("  ✅ cartography::ground_distance_from_map =", _v_ground_distance_from_map)
    else: failed += 1; print("  ❌ cartography::ground_distance_from_map → non-finite:", _v_ground_distance_from_map)
    var _v_map_distance_from_ground = map_distance_from_ground(0.5, 0.5)
    if is_finite(_v_map_distance_from_ground): passed += 1; print("  ✅ cartography::map_distance_from_ground =", _v_map_distance_from_ground)
    else: failed += 1; print("  ❌ cartography::map_distance_from_ground → non-finite:", _v_map_distance_from_ground)
    _ = latitude_to_utm_zone(0.5)
    passed += 1; print("  ✅ cartography::latitude_to_utm_zone")
    var _v_mercator_y = mercator_y(0.5)
    if is_finite(_v_mercator_y): passed += 1; print("  ✅ cartography::mercator_y =", _v_mercator_y)
    else: failed += 1; print("  ❌ cartography::mercator_y → non-finite:", _v_mercator_y)
    var _v_equirectangular_x = equirectangular_x(0.5, 0.5, 0.5)
    if is_finite(_v_equirectangular_x): passed += 1; print("  ✅ cartography::equirectangular_x =", _v_equirectangular_x)
    else: failed += 1; print("  ❌ cartography::equirectangular_x → non-finite:", _v_equirectangular_x)
    var _v_equirectangular_y = equirectangular_y(0.5)
    if is_finite(_v_equirectangular_y): passed += 1; print("  ✅ cartography::equirectangular_y =", _v_equirectangular_y)
    else: failed += 1; print("  ❌ cartography::equirectangular_y → non-finite:", _v_equirectangular_y)
    var _v_great_circle_distance = great_circle_distance(0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_great_circle_distance): passed += 1; print("  ✅ cartography::great_circle_distance =", _v_great_circle_distance)
    else: failed += 1; print("  ❌ cartography::great_circle_distance → non-finite:", _v_great_circle_distance)
    var _v_map_area_at_scale = map_area_at_scale(0.5, 0.5)
    if is_finite(_v_map_area_at_scale): passed += 1; print("  ✅ cartography::map_area_at_scale =", _v_map_area_at_scale)
    else: failed += 1; print("  ❌ cartography::map_area_at_scale → non-finite:", _v_map_area_at_scale)
    var _v_contour_interval_suggestion = contour_interval_suggestion(0.5, 0.5)
    if is_finite(_v_contour_interval_suggestion): passed += 1; print("  ✅ cartography::contour_interval_suggestion =", _v_contour_interval_suggestion)
    else: failed += 1; print("  ❌ cartography::contour_interval_suggestion → non-finite:", _v_contour_interval_suggestion)
    var _v_declination_correction = declination_correction(0.5, 0.5)
    if is_finite(_v_declination_correction): passed += 1; print("  ✅ cartography::declination_correction =", _v_declination_correction)
    else: failed += 1; print("  ❌ cartography::declination_correction → non-finite:", _v_declination_correction)

    print("  [cartography] Passed:", passed, "Failed:", failed)
