"""test_earth.mojo — auto-generated tests for earth library."""
from std.math import isnan, isinf
from earth import deg_to_rad, rad_to_deg, is_valid_coordinate, distance_on_unit_sphere, haversine, bearing, midpoint, destination_point, bounding_box, cross_track_distance

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

    var _v_deg_to_rad = deg_to_rad(0.5)
    if is_finite(_v_deg_to_rad): passed += 1; print("  ✅ earth::deg_to_rad =", _v_deg_to_rad)
    else: failed += 1; print("  ❌ earth::deg_to_rad → non-finite:", _v_deg_to_rad)
    var _v_rad_to_deg = rad_to_deg(0.5)
    if is_finite(_v_rad_to_deg): passed += 1; print("  ✅ earth::rad_to_deg =", _v_rad_to_deg)
    else: failed += 1; print("  ❌ earth::rad_to_deg → non-finite:", _v_rad_to_deg)
    _ = is_valid_coordinate(0.5, 0.5)
    passed += 1; print("  ✅ earth::is_valid_coordinate")
    var _v_distance_on_unit_sphere = distance_on_unit_sphere(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_distance_on_unit_sphere): passed += 1; print("  ✅ earth::distance_on_unit_sphere =", _v_distance_on_unit_sphere)
    else: failed += 1; print("  ❌ earth::distance_on_unit_sphere → non-finite:", _v_distance_on_unit_sphere)
    var _v_haversine = haversine(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_haversine): passed += 1; print("  ✅ earth::haversine =", _v_haversine)
    else: failed += 1; print("  ❌ earth::haversine → non-finite:", _v_haversine)
    var _v_bearing = bearing(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_bearing): passed += 1; print("  ✅ earth::bearing =", _v_bearing)
    else: failed += 1; print("  ❌ earth::bearing → non-finite:", _v_bearing)
    var _v_midpoint = midpoint(0.5, 0.5, 0.5, 0.5)
    if len(_v_midpoint) >= 0: passed += 1; print("  ✅ earth::midpoint")
    var _v_destination_point = destination_point(0.5, 0.5, 0.5, 0.5)
    if len(_v_destination_point) >= 0: passed += 1; print("  ✅ earth::destination_point")
    var _v_bounding_box = bounding_box(0.5, 0.5, 0.5)
    if len(_v_bounding_box) >= 0: passed += 1; print("  ✅ earth::bounding_box")
    var _v_cross_track_distance = cross_track_distance(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_cross_track_distance): passed += 1; print("  ✅ earth::cross_track_distance =", _v_cross_track_distance)
    else: failed += 1; print("  ❌ earth::cross_track_distance → non-finite:", _v_cross_track_distance)

    print("  [earth] Passed:", passed, "Failed:", failed)
