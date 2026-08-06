"""bench_timber.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from timber import board_feet, moisture_content, allowable_stress, modulus_of_rupture_adjusted, section_modulus_beam, moment_capacity, column_slenderness, wood_density_from_sg, shrinkage_estimate, fire_char_rate, remaining_section, log_volume_doyle
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_board_feet: Float64 = 0.0
    var _t0_board_feet = perf_counter_ns()
    for _ in range(N):
        _acc_board_feet += board_feet(0.5, 0.5, 0.5)
    var _t1_board_feet = perf_counter_ns()
    var _ns_board_feet = Float64(_t1_board_feet - _t0_board_feet) / Float64(N)
    print("MOJO_TIMING timber::board_feet", _ns_board_feet, _acc_board_feet)
    var _result_board_feet = board_feet(0.5, 0.5, 0.5)
    var _summary_board_feet = _summary_float64(_result_board_feet)
    print("MOJO_RESULT timber::board_feet", _summary_board_feet)
    var _acc_moisture_content: Float64 = 0.0
    var _t0_moisture_content = perf_counter_ns()
    for _ in range(N):
        _acc_moisture_content += moisture_content(0.5, 0.5)
    var _t1_moisture_content = perf_counter_ns()
    var _ns_moisture_content = Float64(_t1_moisture_content - _t0_moisture_content) / Float64(N)
    print("MOJO_TIMING timber::moisture_content", _ns_moisture_content, _acc_moisture_content)
    var _result_moisture_content = moisture_content(0.5, 0.5)
    var _summary_moisture_content = _summary_float64(_result_moisture_content)
    print("MOJO_RESULT timber::moisture_content", _summary_moisture_content)
    var _acc_allowable_stress: Float64 = 0.0
    var _t0_allowable_stress = perf_counter_ns()
    for _ in range(N):
        _acc_allowable_stress += allowable_stress(0.5, 0.5, 0.5, 0.5)
    var _t1_allowable_stress = perf_counter_ns()
    var _ns_allowable_stress = Float64(_t1_allowable_stress - _t0_allowable_stress) / Float64(N)
    print("MOJO_TIMING timber::allowable_stress", _ns_allowable_stress, _acc_allowable_stress)
    var _result_allowable_stress = allowable_stress(0.5, 0.5, 0.5, 0.5)
    var _summary_allowable_stress = _summary_float64(_result_allowable_stress)
    print("MOJO_RESULT timber::allowable_stress", _summary_allowable_stress)
    var _acc_modulus_of_rupture_adjusted: Float64 = 0.0
    var _t0_modulus_of_rupture_adjusted = perf_counter_ns()
    for _ in range(N):
        _acc_modulus_of_rupture_adjusted += modulus_of_rupture_adjusted(0.5, 0.5)
    var _t1_modulus_of_rupture_adjusted = perf_counter_ns()
    var _ns_modulus_of_rupture_adjusted = Float64(_t1_modulus_of_rupture_adjusted - _t0_modulus_of_rupture_adjusted) / Float64(N)
    print("MOJO_TIMING timber::modulus_of_rupture_adjusted", _ns_modulus_of_rupture_adjusted, _acc_modulus_of_rupture_adjusted)
    var _result_modulus_of_rupture_adjusted = modulus_of_rupture_adjusted(0.5, 0.5)
    var _summary_modulus_of_rupture_adjusted = _summary_float64(_result_modulus_of_rupture_adjusted)
    print("MOJO_RESULT timber::modulus_of_rupture_adjusted", _summary_modulus_of_rupture_adjusted)
    var _acc_section_modulus_beam: Float64 = 0.0
    var _t0_section_modulus_beam = perf_counter_ns()
    for _ in range(N):
        _acc_section_modulus_beam += section_modulus_beam(0.5, 0.5)
    var _t1_section_modulus_beam = perf_counter_ns()
    var _ns_section_modulus_beam = Float64(_t1_section_modulus_beam - _t0_section_modulus_beam) / Float64(N)
    print("MOJO_TIMING timber::section_modulus_beam", _ns_section_modulus_beam, _acc_section_modulus_beam)
    var _result_section_modulus_beam = section_modulus_beam(0.5, 0.5)
    var _summary_section_modulus_beam = _summary_float64(_result_section_modulus_beam)
    print("MOJO_RESULT timber::section_modulus_beam", _summary_section_modulus_beam)
    var _acc_moment_capacity: Float64 = 0.0
    var _t0_moment_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_moment_capacity += moment_capacity(0.5, 0.5)
    var _t1_moment_capacity = perf_counter_ns()
    var _ns_moment_capacity = Float64(_t1_moment_capacity - _t0_moment_capacity) / Float64(N)
    print("MOJO_TIMING timber::moment_capacity", _ns_moment_capacity, _acc_moment_capacity)
    var _result_moment_capacity = moment_capacity(0.5, 0.5)
    var _summary_moment_capacity = _summary_float64(_result_moment_capacity)
    print("MOJO_RESULT timber::moment_capacity", _summary_moment_capacity)
    var _acc_column_slenderness: Float64 = 0.0
    var _t0_column_slenderness = perf_counter_ns()
    for _ in range(N):
        _acc_column_slenderness += column_slenderness(0.5, 0.5)
    var _t1_column_slenderness = perf_counter_ns()
    var _ns_column_slenderness = Float64(_t1_column_slenderness - _t0_column_slenderness) / Float64(N)
    print("MOJO_TIMING timber::column_slenderness", _ns_column_slenderness, _acc_column_slenderness)
    var _result_column_slenderness = column_slenderness(0.5, 0.5)
    var _summary_column_slenderness = _summary_float64(_result_column_slenderness)
    print("MOJO_RESULT timber::column_slenderness", _summary_column_slenderness)
    var _acc_wood_density_from_sg: Float64 = 0.0
    var _t0_wood_density_from_sg = perf_counter_ns()
    for _ in range(N):
        _acc_wood_density_from_sg += wood_density_from_sg(0.5, 0.5)
    var _t1_wood_density_from_sg = perf_counter_ns()
    var _ns_wood_density_from_sg = Float64(_t1_wood_density_from_sg - _t0_wood_density_from_sg) / Float64(N)
    print("MOJO_TIMING timber::wood_density_from_sg", _ns_wood_density_from_sg, _acc_wood_density_from_sg)
    var _result_wood_density_from_sg = wood_density_from_sg(0.5, 0.5)
    var _summary_wood_density_from_sg = _summary_float64(_result_wood_density_from_sg)
    print("MOJO_RESULT timber::wood_density_from_sg", _summary_wood_density_from_sg)
    var _acc_shrinkage_estimate: Float64 = 0.0
    var _t0_shrinkage_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_shrinkage_estimate += shrinkage_estimate(0.5, 0.5, 0.5, 0.5)
    var _t1_shrinkage_estimate = perf_counter_ns()
    var _ns_shrinkage_estimate = Float64(_t1_shrinkage_estimate - _t0_shrinkage_estimate) / Float64(N)
    print("MOJO_TIMING timber::shrinkage_estimate", _ns_shrinkage_estimate, _acc_shrinkage_estimate)
    var _result_shrinkage_estimate = shrinkage_estimate(0.5, 0.5, 0.5, 0.5)
    var _summary_shrinkage_estimate = _summary_float64(_result_shrinkage_estimate)
    print("MOJO_RESULT timber::shrinkage_estimate", _summary_shrinkage_estimate)
    var _acc_fire_char_rate: Float64 = 0.0
    var _t0_fire_char_rate = perf_counter_ns()
    for _ in range(N):
        _acc_fire_char_rate += fire_char_rate(0.5, 0.5)
    var _t1_fire_char_rate = perf_counter_ns()
    var _ns_fire_char_rate = Float64(_t1_fire_char_rate - _t0_fire_char_rate) / Float64(N)
    print("MOJO_TIMING timber::fire_char_rate", _ns_fire_char_rate, _acc_fire_char_rate)
    var _result_fire_char_rate = fire_char_rate(0.5, 0.5)
    var _summary_fire_char_rate = _summary_float64(_result_fire_char_rate)
    print("MOJO_RESULT timber::fire_char_rate", _summary_fire_char_rate)
    var _acc_remaining_section: Float64 = 0.0
    var _t0_remaining_section = perf_counter_ns()
    for _ in range(N):
        _acc_remaining_section += remaining_section(0.5, 0.5)
    var _t1_remaining_section = perf_counter_ns()
    var _ns_remaining_section = Float64(_t1_remaining_section - _t0_remaining_section) / Float64(N)
    print("MOJO_TIMING timber::remaining_section", _ns_remaining_section, _acc_remaining_section)
    var _result_remaining_section = remaining_section(0.5, 0.5)
    var _summary_remaining_section = _summary_float64(_result_remaining_section)
    print("MOJO_RESULT timber::remaining_section", _summary_remaining_section)
    var _acc_log_volume_doyle: Float64 = 0.0
    var _t0_log_volume_doyle = perf_counter_ns()
    for _ in range(N):
        _acc_log_volume_doyle += log_volume_doyle(0.5, 0.5)
    var _t1_log_volume_doyle = perf_counter_ns()
    var _ns_log_volume_doyle = Float64(_t1_log_volume_doyle - _t0_log_volume_doyle) / Float64(N)
    print("MOJO_TIMING timber::log_volume_doyle", _ns_log_volume_doyle, _acc_log_volume_doyle)
    var _result_log_volume_doyle = log_volume_doyle(0.5, 0.5)
    var _summary_log_volume_doyle = _summary_float64(_result_log_volume_doyle)
    print("MOJO_RESULT timber::log_volume_doyle", _summary_log_volume_doyle)
