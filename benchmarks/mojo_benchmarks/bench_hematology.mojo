"""bench_hematology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from hematology import hematocrit, mean_corpuscular_volume, mean_corpuscular_hemoglobin, mchc, red_cell_distribution_width, oxygen_carrying_capacity, coagulation_inr, platelet_count_index, blood_viscosity_relative, erythrocyte_sedimentation
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

    var _acc_hematocrit: Float64 = 0.0
    var _t0_hematocrit = perf_counter_ns()
    for _ in range(N):
        _acc_hematocrit += hematocrit(0.5, 0.5)
    var _t1_hematocrit = perf_counter_ns()
    var _ns_hematocrit = Float64(_t1_hematocrit - _t0_hematocrit) / Float64(N)
    print("MOJO_TIMING hematology::hematocrit", _ns_hematocrit, _acc_hematocrit)
    var _result_hematocrit = hematocrit(0.5, 0.5)
    var _summary_hematocrit = _summary_float64(_result_hematocrit)
    print("MOJO_RESULT hematology::hematocrit", _summary_hematocrit)
    var _acc_mean_corpuscular_volume: Float64 = 0.0
    var _t0_mean_corpuscular_volume = perf_counter_ns()
    for _ in range(N):
        _acc_mean_corpuscular_volume += mean_corpuscular_volume(0.5, 0.5)
    var _t1_mean_corpuscular_volume = perf_counter_ns()
    var _ns_mean_corpuscular_volume = Float64(_t1_mean_corpuscular_volume - _t0_mean_corpuscular_volume) / Float64(N)
    print("MOJO_TIMING hematology::mean_corpuscular_volume", _ns_mean_corpuscular_volume, _acc_mean_corpuscular_volume)
    var _result_mean_corpuscular_volume = mean_corpuscular_volume(0.5, 0.5)
    var _summary_mean_corpuscular_volume = _summary_float64(_result_mean_corpuscular_volume)
    print("MOJO_RESULT hematology::mean_corpuscular_volume", _summary_mean_corpuscular_volume)
    var _acc_mean_corpuscular_hemoglobin: Float64 = 0.0
    var _t0_mean_corpuscular_hemoglobin = perf_counter_ns()
    for _ in range(N):
        _acc_mean_corpuscular_hemoglobin += mean_corpuscular_hemoglobin(0.5, 0.5)
    var _t1_mean_corpuscular_hemoglobin = perf_counter_ns()
    var _ns_mean_corpuscular_hemoglobin = Float64(_t1_mean_corpuscular_hemoglobin - _t0_mean_corpuscular_hemoglobin) / Float64(N)
    print("MOJO_TIMING hematology::mean_corpuscular_hemoglobin", _ns_mean_corpuscular_hemoglobin, _acc_mean_corpuscular_hemoglobin)
    var _result_mean_corpuscular_hemoglobin = mean_corpuscular_hemoglobin(0.5, 0.5)
    var _summary_mean_corpuscular_hemoglobin = _summary_float64(_result_mean_corpuscular_hemoglobin)
    print("MOJO_RESULT hematology::mean_corpuscular_hemoglobin", _summary_mean_corpuscular_hemoglobin)
    var _acc_mchc: Float64 = 0.0
    var _t0_mchc = perf_counter_ns()
    for _ in range(N):
        _acc_mchc += mchc(0.5, 0.5)
    var _t1_mchc = perf_counter_ns()
    var _ns_mchc = Float64(_t1_mchc - _t0_mchc) / Float64(N)
    print("MOJO_TIMING hematology::mchc", _ns_mchc, _acc_mchc)
    var _result_mchc = mchc(0.5, 0.5)
    var _summary_mchc = _summary_float64(_result_mchc)
    print("MOJO_RESULT hematology::mchc", _summary_mchc)
    var _acc_red_cell_distribution_width: Float64 = 0.0
    var _t0_red_cell_distribution_width = perf_counter_ns()
    for _ in range(N):
        _acc_red_cell_distribution_width += red_cell_distribution_width(0.5, 0.5)
    var _t1_red_cell_distribution_width = perf_counter_ns()
    var _ns_red_cell_distribution_width = Float64(_t1_red_cell_distribution_width - _t0_red_cell_distribution_width) / Float64(N)
    print("MOJO_TIMING hematology::red_cell_distribution_width", _ns_red_cell_distribution_width, _acc_red_cell_distribution_width)
    var _result_red_cell_distribution_width = red_cell_distribution_width(0.5, 0.5)
    var _summary_red_cell_distribution_width = _summary_float64(_result_red_cell_distribution_width)
    print("MOJO_RESULT hematology::red_cell_distribution_width", _summary_red_cell_distribution_width)
    var _acc_oxygen_carrying_capacity: Float64 = 0.0
    var _t0_oxygen_carrying_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_oxygen_carrying_capacity += oxygen_carrying_capacity(0.5)
    var _t1_oxygen_carrying_capacity = perf_counter_ns()
    var _ns_oxygen_carrying_capacity = Float64(_t1_oxygen_carrying_capacity - _t0_oxygen_carrying_capacity) / Float64(N)
    print("MOJO_TIMING hematology::oxygen_carrying_capacity", _ns_oxygen_carrying_capacity, _acc_oxygen_carrying_capacity)
    var _result_oxygen_carrying_capacity = oxygen_carrying_capacity(0.5)
    var _summary_oxygen_carrying_capacity = _summary_float64(_result_oxygen_carrying_capacity)
    print("MOJO_RESULT hematology::oxygen_carrying_capacity", _summary_oxygen_carrying_capacity)
    var _acc_coagulation_inr: Float64 = 0.0
    var _t0_coagulation_inr = perf_counter_ns()
    for _ in range(N):
        _acc_coagulation_inr += coagulation_inr(0.5, 0.5, 0.5)
    var _t1_coagulation_inr = perf_counter_ns()
    var _ns_coagulation_inr = Float64(_t1_coagulation_inr - _t0_coagulation_inr) / Float64(N)
    print("MOJO_TIMING hematology::coagulation_inr", _ns_coagulation_inr, _acc_coagulation_inr)
    var _result_coagulation_inr = coagulation_inr(0.5, 0.5, 0.5)
    var _summary_coagulation_inr = _summary_float64(_result_coagulation_inr)
    print("MOJO_RESULT hematology::coagulation_inr", _summary_coagulation_inr)
    var _acc_platelet_count_index: Float64 = 0.0
    var _t0_platelet_count_index = perf_counter_ns()
    for _ in range(N):
        _acc_platelet_count_index += platelet_count_index(0.5, 0.5)
    var _t1_platelet_count_index = perf_counter_ns()
    var _ns_platelet_count_index = Float64(_t1_platelet_count_index - _t0_platelet_count_index) / Float64(N)
    print("MOJO_TIMING hematology::platelet_count_index", _ns_platelet_count_index, _acc_platelet_count_index)
    var _result_platelet_count_index = platelet_count_index(0.5, 0.5)
    var _summary_platelet_count_index = _summary_float64(_result_platelet_count_index)
    print("MOJO_RESULT hematology::platelet_count_index", _summary_platelet_count_index)
    var _acc_blood_viscosity_relative: Float64 = 0.0
    var _t0_blood_viscosity_relative = perf_counter_ns()
    for _ in range(N):
        _acc_blood_viscosity_relative += blood_viscosity_relative(0.5)
    var _t1_blood_viscosity_relative = perf_counter_ns()
    var _ns_blood_viscosity_relative = Float64(_t1_blood_viscosity_relative - _t0_blood_viscosity_relative) / Float64(N)
    print("MOJO_TIMING hematology::blood_viscosity_relative", _ns_blood_viscosity_relative, _acc_blood_viscosity_relative)
    var _result_blood_viscosity_relative = blood_viscosity_relative(0.5)
    var _summary_blood_viscosity_relative = _summary_float64(_result_blood_viscosity_relative)
    print("MOJO_RESULT hematology::blood_viscosity_relative", _summary_blood_viscosity_relative)
    var _acc_erythrocyte_sedimentation: Float64 = 0.0
    var _t0_erythrocyte_sedimentation = perf_counter_ns()
    for _ in range(N):
        _acc_erythrocyte_sedimentation += erythrocyte_sedimentation(0.5, 0.5, 0.5)
    var _t1_erythrocyte_sedimentation = perf_counter_ns()
    var _ns_erythrocyte_sedimentation = Float64(_t1_erythrocyte_sedimentation - _t0_erythrocyte_sedimentation) / Float64(N)
    print("MOJO_TIMING hematology::erythrocyte_sedimentation", _ns_erythrocyte_sedimentation, _acc_erythrocyte_sedimentation)
    var _result_erythrocyte_sedimentation = erythrocyte_sedimentation(0.5, 0.5, 0.5)
    var _summary_erythrocyte_sedimentation = _summary_float64(_result_erythrocyte_sedimentation)
    print("MOJO_RESULT hematology::erythrocyte_sedimentation", _summary_erythrocyte_sedimentation)
