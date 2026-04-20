"""bench_cartography.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cartography import scale_factor, representative_fraction, ground_distance_from_map, map_distance_from_ground, latitude_to_utm_zone, mercator_y, equirectangular_x, equirectangular_y, great_circle_distance, map_area_at_scale, contour_interval_suggestion, declination_correction
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_scale_factor: Float64 = 0.0
    var _t0_scale_factor = perf_counter_ns()
    for _ in range(N):
        _acc_scale_factor += scale_factor(0.5, 0.5)
    var _t1_scale_factor = perf_counter_ns()
    var _ns_scale_factor = Float64(_t1_scale_factor - _t0_scale_factor) / Float64(N)
    print("MOJO_TIMING cartography::scale_factor", _ns_scale_factor, _acc_scale_factor)
    var _acc_representative_fraction: Float64 = 0.0
    var _t0_representative_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_representative_fraction += representative_fraction(0.5, 0.5)
    var _t1_representative_fraction = perf_counter_ns()
    var _ns_representative_fraction = Float64(_t1_representative_fraction - _t0_representative_fraction) / Float64(N)
    print("MOJO_TIMING cartography::representative_fraction", _ns_representative_fraction, _acc_representative_fraction)
    var _acc_ground_distance_from_map: Float64 = 0.0
    var _t0_ground_distance_from_map = perf_counter_ns()
    for _ in range(N):
        _acc_ground_distance_from_map += ground_distance_from_map(0.5, 0.5)
    var _t1_ground_distance_from_map = perf_counter_ns()
    var _ns_ground_distance_from_map = Float64(_t1_ground_distance_from_map - _t0_ground_distance_from_map) / Float64(N)
    print("MOJO_TIMING cartography::ground_distance_from_map", _ns_ground_distance_from_map, _acc_ground_distance_from_map)
    var _acc_map_distance_from_ground: Float64 = 0.0
    var _t0_map_distance_from_ground = perf_counter_ns()
    for _ in range(N):
        _acc_map_distance_from_ground += map_distance_from_ground(0.5, 0.5)
    var _t1_map_distance_from_ground = perf_counter_ns()
    var _ns_map_distance_from_ground = Float64(_t1_map_distance_from_ground - _t0_map_distance_from_ground) / Float64(N)
    print("MOJO_TIMING cartography::map_distance_from_ground", _ns_map_distance_from_ground, _acc_map_distance_from_ground)
    var _acc_latitude_to_utm_zone: Float64 = 0.0
    var _t0_latitude_to_utm_zone = perf_counter_ns()
    for _ in range(N):
        _acc_latitude_to_utm_zone += Float64(latitude_to_utm_zone(0.5))
    var _t1_latitude_to_utm_zone = perf_counter_ns()
    var _ns_latitude_to_utm_zone = Float64(_t1_latitude_to_utm_zone - _t0_latitude_to_utm_zone) / Float64(N)
    print("MOJO_TIMING cartography::latitude_to_utm_zone", _ns_latitude_to_utm_zone, _acc_latitude_to_utm_zone)
    var _acc_mercator_y: Float64 = 0.0
    var _t0_mercator_y = perf_counter_ns()
    for _ in range(N):
        _acc_mercator_y += mercator_y(0.5)
    var _t1_mercator_y = perf_counter_ns()
    var _ns_mercator_y = Float64(_t1_mercator_y - _t0_mercator_y) / Float64(N)
    print("MOJO_TIMING cartography::mercator_y", _ns_mercator_y, _acc_mercator_y)
    var _acc_equirectangular_x: Float64 = 0.0
    var _t0_equirectangular_x = perf_counter_ns()
    for _ in range(N):
        _acc_equirectangular_x += equirectangular_x(0.5, 0.5, 0.5)
    var _t1_equirectangular_x = perf_counter_ns()
    var _ns_equirectangular_x = Float64(_t1_equirectangular_x - _t0_equirectangular_x) / Float64(N)
    print("MOJO_TIMING cartography::equirectangular_x", _ns_equirectangular_x, _acc_equirectangular_x)
    var _acc_equirectangular_y: Float64 = 0.0
    var _t0_equirectangular_y = perf_counter_ns()
    for _ in range(N):
        _acc_equirectangular_y += equirectangular_y(0.5)
    var _t1_equirectangular_y = perf_counter_ns()
    var _ns_equirectangular_y = Float64(_t1_equirectangular_y - _t0_equirectangular_y) / Float64(N)
    print("MOJO_TIMING cartography::equirectangular_y", _ns_equirectangular_y, _acc_equirectangular_y)
    var _acc_great_circle_distance: Float64 = 0.0
    var _t0_great_circle_distance = perf_counter_ns()
    for _ in range(N):
        _acc_great_circle_distance += great_circle_distance(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_great_circle_distance = perf_counter_ns()
    var _ns_great_circle_distance = Float64(_t1_great_circle_distance - _t0_great_circle_distance) / Float64(N)
    print("MOJO_TIMING cartography::great_circle_distance", _ns_great_circle_distance, _acc_great_circle_distance)
    var _acc_map_area_at_scale: Float64 = 0.0
    var _t0_map_area_at_scale = perf_counter_ns()
    for _ in range(N):
        _acc_map_area_at_scale += map_area_at_scale(0.5, 0.5)
    var _t1_map_area_at_scale = perf_counter_ns()
    var _ns_map_area_at_scale = Float64(_t1_map_area_at_scale - _t0_map_area_at_scale) / Float64(N)
    print("MOJO_TIMING cartography::map_area_at_scale", _ns_map_area_at_scale, _acc_map_area_at_scale)
    var _acc_contour_interval_suggestion: Float64 = 0.0
    var _t0_contour_interval_suggestion = perf_counter_ns()
    for _ in range(N):
        _acc_contour_interval_suggestion += contour_interval_suggestion(0.5, 0.5)
    var _t1_contour_interval_suggestion = perf_counter_ns()
    var _ns_contour_interval_suggestion = Float64(_t1_contour_interval_suggestion - _t0_contour_interval_suggestion) / Float64(N)
    print("MOJO_TIMING cartography::contour_interval_suggestion", _ns_contour_interval_suggestion, _acc_contour_interval_suggestion)
    var _acc_declination_correction: Float64 = 0.0
    var _t0_declination_correction = perf_counter_ns()
    for _ in range(N):
        _acc_declination_correction += declination_correction(0.5, 0.5)
    var _t1_declination_correction = perf_counter_ns()
    var _ns_declination_correction = Float64(_t1_declination_correction - _t0_declination_correction) / Float64(N)
    print("MOJO_TIMING cartography::declination_correction", _ns_declination_correction, _acc_declination_correction)
