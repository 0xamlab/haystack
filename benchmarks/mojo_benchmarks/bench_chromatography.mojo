"""bench_chromatography.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from chromatography import retention_factor, selectivity_factor, plate_count, plate_height, resolution, van_deemter_h, peak_capacity, separation_number, retention_index_kovats, mobile_phase_velocity
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

    var _acc_retention_factor: Float64 = 0.0
    var _t0_retention_factor = perf_counter_ns()
    for _ in range(N):
        _acc_retention_factor += retention_factor(0.5, 0.5)
    var _t1_retention_factor = perf_counter_ns()
    var _ns_retention_factor = Float64(_t1_retention_factor - _t0_retention_factor) / Float64(N)
    print("MOJO_TIMING chromatography::retention_factor", _ns_retention_factor, _acc_retention_factor)
    var _acc_selectivity_factor: Float64 = 0.0
    var _t0_selectivity_factor = perf_counter_ns()
    for _ in range(N):
        _acc_selectivity_factor += selectivity_factor(0.5, 0.5)
    var _t1_selectivity_factor = perf_counter_ns()
    var _ns_selectivity_factor = Float64(_t1_selectivity_factor - _t0_selectivity_factor) / Float64(N)
    print("MOJO_TIMING chromatography::selectivity_factor", _ns_selectivity_factor, _acc_selectivity_factor)
    var _acc_plate_count: Float64 = 0.0
    var _t0_plate_count = perf_counter_ns()
    for _ in range(N):
        _acc_plate_count += plate_count(0.5, 0.5)
    var _t1_plate_count = perf_counter_ns()
    var _ns_plate_count = Float64(_t1_plate_count - _t0_plate_count) / Float64(N)
    print("MOJO_TIMING chromatography::plate_count", _ns_plate_count, _acc_plate_count)
    var _acc_plate_height: Float64 = 0.0
    var _t0_plate_height = perf_counter_ns()
    for _ in range(N):
        _acc_plate_height += plate_height(0.5, 0.5)
    var _t1_plate_height = perf_counter_ns()
    var _ns_plate_height = Float64(_t1_plate_height - _t0_plate_height) / Float64(N)
    print("MOJO_TIMING chromatography::plate_height", _ns_plate_height, _acc_plate_height)
    var _acc_resolution: Float64 = 0.0
    var _t0_resolution = perf_counter_ns()
    for _ in range(N):
        _acc_resolution += resolution(0.5, 0.5, 0.5, 0.5)
    var _t1_resolution = perf_counter_ns()
    var _ns_resolution = Float64(_t1_resolution - _t0_resolution) / Float64(N)
    print("MOJO_TIMING chromatography::resolution", _ns_resolution, _acc_resolution)
    var _acc_van_deemter_h: Float64 = 0.0
    var _t0_van_deemter_h = perf_counter_ns()
    for _ in range(N):
        _acc_van_deemter_h += van_deemter_h(0.5, 0.5, 0.5, 0.5)
    var _t1_van_deemter_h = perf_counter_ns()
    var _ns_van_deemter_h = Float64(_t1_van_deemter_h - _t0_van_deemter_h) / Float64(N)
    print("MOJO_TIMING chromatography::van_deemter_h", _ns_van_deemter_h, _acc_van_deemter_h)
    var _acc_peak_capacity: Float64 = 0.0
    var _t0_peak_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_peak_capacity += peak_capacity(0.5, 0.5, 0.5)
    var _t1_peak_capacity = perf_counter_ns()
    var _ns_peak_capacity = Float64(_t1_peak_capacity - _t0_peak_capacity) / Float64(N)
    print("MOJO_TIMING chromatography::peak_capacity", _ns_peak_capacity, _acc_peak_capacity)
    var _acc_separation_number: Float64 = 0.0
    var _t0_separation_number = perf_counter_ns()
    for _ in range(N):
        _acc_separation_number += separation_number(0.5, 0.5, 0.5, 0.5)
    var _t1_separation_number = perf_counter_ns()
    var _ns_separation_number = Float64(_t1_separation_number - _t0_separation_number) / Float64(N)
    print("MOJO_TIMING chromatography::separation_number", _ns_separation_number, _acc_separation_number)
    var _acc_retention_index_kovats: Float64 = 0.0
    var _t0_retention_index_kovats = perf_counter_ns()
    for _ in range(N):
        _acc_retention_index_kovats += retention_index_kovats(0.5, 0.5, 0.5, 0.5)
    var _t1_retention_index_kovats = perf_counter_ns()
    var _ns_retention_index_kovats = Float64(_t1_retention_index_kovats - _t0_retention_index_kovats) / Float64(N)
    print("MOJO_TIMING chromatography::retention_index_kovats", _ns_retention_index_kovats, _acc_retention_index_kovats)
    var _acc_mobile_phase_velocity: Float64 = 0.0
    var _t0_mobile_phase_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_mobile_phase_velocity += mobile_phase_velocity(0.5, 0.5)
    var _t1_mobile_phase_velocity = perf_counter_ns()
    var _ns_mobile_phase_velocity = Float64(_t1_mobile_phase_velocity - _t0_mobile_phase_velocity) / Float64(N)
    print("MOJO_TIMING chromatography::mobile_phase_velocity", _ns_mobile_phase_velocity, _acc_mobile_phase_velocity)
