"""bench_chromatography.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from chromatography import retention_factor, selectivity_factor, plate_count, plate_height, resolution, van_deemter_h, peak_capacity, separation_number, retention_index_kovats, mobile_phase_velocity
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_retention_factor = retention_factor(0.5, 0.5)
    var _summary_retention_factor = _summary_float64(_result_retention_factor)
    print("MOJO_RESULT chromatography::retention_factor", _summary_retention_factor)
    var _acc_selectivity_factor: Float64 = 0.0
    var _t0_selectivity_factor = perf_counter_ns()
    for _ in range(N):
        _acc_selectivity_factor += selectivity_factor(0.5, 0.5)
    var _t1_selectivity_factor = perf_counter_ns()
    var _ns_selectivity_factor = Float64(_t1_selectivity_factor - _t0_selectivity_factor) / Float64(N)
    print("MOJO_TIMING chromatography::selectivity_factor", _ns_selectivity_factor, _acc_selectivity_factor)
    var _result_selectivity_factor = selectivity_factor(0.5, 0.5)
    var _summary_selectivity_factor = _summary_float64(_result_selectivity_factor)
    print("MOJO_RESULT chromatography::selectivity_factor", _summary_selectivity_factor)
    var _acc_plate_count: Float64 = 0.0
    var _t0_plate_count = perf_counter_ns()
    for _ in range(N):
        _acc_plate_count += plate_count(0.5, 0.5)
    var _t1_plate_count = perf_counter_ns()
    var _ns_plate_count = Float64(_t1_plate_count - _t0_plate_count) / Float64(N)
    print("MOJO_TIMING chromatography::plate_count", _ns_plate_count, _acc_plate_count)
    var _result_plate_count = plate_count(0.5, 0.5)
    var _summary_plate_count = _summary_float64(_result_plate_count)
    print("MOJO_RESULT chromatography::plate_count", _summary_plate_count)
    var _acc_plate_height: Float64 = 0.0
    var _t0_plate_height = perf_counter_ns()
    for _ in range(N):
        _acc_plate_height += plate_height(0.5, 0.5)
    var _t1_plate_height = perf_counter_ns()
    var _ns_plate_height = Float64(_t1_plate_height - _t0_plate_height) / Float64(N)
    print("MOJO_TIMING chromatography::plate_height", _ns_plate_height, _acc_plate_height)
    var _result_plate_height = plate_height(0.5, 0.5)
    var _summary_plate_height = _summary_float64(_result_plate_height)
    print("MOJO_RESULT chromatography::plate_height", _summary_plate_height)
    var _acc_resolution: Float64 = 0.0
    var _t0_resolution = perf_counter_ns()
    for _ in range(N):
        _acc_resolution += resolution(0.5, 0.5, 0.5, 0.5)
    var _t1_resolution = perf_counter_ns()
    var _ns_resolution = Float64(_t1_resolution - _t0_resolution) / Float64(N)
    print("MOJO_TIMING chromatography::resolution", _ns_resolution, _acc_resolution)
    var _result_resolution = resolution(0.5, 0.5, 0.5, 0.5)
    var _summary_resolution = _summary_float64(_result_resolution)
    print("MOJO_RESULT chromatography::resolution", _summary_resolution)
    var _acc_van_deemter_h: Float64 = 0.0
    var _t0_van_deemter_h = perf_counter_ns()
    for _ in range(N):
        _acc_van_deemter_h += van_deemter_h(0.5, 0.5, 0.5, 0.5)
    var _t1_van_deemter_h = perf_counter_ns()
    var _ns_van_deemter_h = Float64(_t1_van_deemter_h - _t0_van_deemter_h) / Float64(N)
    print("MOJO_TIMING chromatography::van_deemter_h", _ns_van_deemter_h, _acc_van_deemter_h)
    var _result_van_deemter_h = van_deemter_h(0.5, 0.5, 0.5, 0.5)
    var _summary_van_deemter_h = _summary_float64(_result_van_deemter_h)
    print("MOJO_RESULT chromatography::van_deemter_h", _summary_van_deemter_h)
    var _acc_peak_capacity: Float64 = 0.0
    var _t0_peak_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_peak_capacity += peak_capacity(0.5, 0.5, 0.5)
    var _t1_peak_capacity = perf_counter_ns()
    var _ns_peak_capacity = Float64(_t1_peak_capacity - _t0_peak_capacity) / Float64(N)
    print("MOJO_TIMING chromatography::peak_capacity", _ns_peak_capacity, _acc_peak_capacity)
    var _result_peak_capacity = peak_capacity(0.5, 0.5, 0.5)
    var _summary_peak_capacity = _summary_float64(_result_peak_capacity)
    print("MOJO_RESULT chromatography::peak_capacity", _summary_peak_capacity)
    var _acc_separation_number: Float64 = 0.0
    var _t0_separation_number = perf_counter_ns()
    for _ in range(N):
        _acc_separation_number += separation_number(0.5, 0.5, 0.5, 0.5)
    var _t1_separation_number = perf_counter_ns()
    var _ns_separation_number = Float64(_t1_separation_number - _t0_separation_number) / Float64(N)
    print("MOJO_TIMING chromatography::separation_number", _ns_separation_number, _acc_separation_number)
    var _result_separation_number = separation_number(0.5, 0.5, 0.5, 0.5)
    var _summary_separation_number = _summary_float64(_result_separation_number)
    print("MOJO_RESULT chromatography::separation_number", _summary_separation_number)
    var _acc_retention_index_kovats: Float64 = 0.0
    var _t0_retention_index_kovats = perf_counter_ns()
    for _ in range(N):
        _acc_retention_index_kovats += retention_index_kovats(0.5, 0.5, 0.5, 0.5)
    var _t1_retention_index_kovats = perf_counter_ns()
    var _ns_retention_index_kovats = Float64(_t1_retention_index_kovats - _t0_retention_index_kovats) / Float64(N)
    print("MOJO_TIMING chromatography::retention_index_kovats", _ns_retention_index_kovats, _acc_retention_index_kovats)
    var _result_retention_index_kovats = retention_index_kovats(0.5, 0.5, 0.5, 0.5)
    var _summary_retention_index_kovats = _summary_float64(_result_retention_index_kovats)
    print("MOJO_RESULT chromatography::retention_index_kovats", _summary_retention_index_kovats)
    var _acc_mobile_phase_velocity: Float64 = 0.0
    var _t0_mobile_phase_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_mobile_phase_velocity += mobile_phase_velocity(0.5, 0.5)
    var _t1_mobile_phase_velocity = perf_counter_ns()
    var _ns_mobile_phase_velocity = Float64(_t1_mobile_phase_velocity - _t0_mobile_phase_velocity) / Float64(N)
    print("MOJO_TIMING chromatography::mobile_phase_velocity", _ns_mobile_phase_velocity, _acc_mobile_phase_velocity)
    var _result_mobile_phase_velocity = mobile_phase_velocity(0.5, 0.5)
    var _summary_mobile_phase_velocity = _summary_float64(_result_mobile_phase_velocity)
    print("MOJO_RESULT chromatography::mobile_phase_velocity", _summary_mobile_phase_velocity)
