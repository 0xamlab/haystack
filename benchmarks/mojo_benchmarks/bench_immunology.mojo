"""bench_immunology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from immunology import antibody_titer, seroconversion_rate, antigen_antibody_binding, complement_activation, t_cell_proliferation, innate_response_decay, vaccine_efficacy, herd_immunity_threshold, antibody_avidity_index, opsonisation_index
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

    var _acc_antibody_titer: Float64 = 0.0
    var _t0_antibody_titer = perf_counter_ns()
    for _ in range(N):
        _acc_antibody_titer += antibody_titer(0.5, 0.5)
    var _t1_antibody_titer = perf_counter_ns()
    var _ns_antibody_titer = Float64(_t1_antibody_titer - _t0_antibody_titer) / Float64(N)
    print("MOJO_TIMING immunology::antibody_titer", _ns_antibody_titer, _acc_antibody_titer)
    var _result_antibody_titer = antibody_titer(0.5, 0.5)
    var _summary_antibody_titer = _summary_float64(_result_antibody_titer)
    print("MOJO_RESULT immunology::antibody_titer", _summary_antibody_titer)
    var _acc_seroconversion_rate: Float64 = 0.0
    var _t0_seroconversion_rate = perf_counter_ns()
    for _ in range(N):
        _acc_seroconversion_rate += seroconversion_rate(0.5, 0.5)
    var _t1_seroconversion_rate = perf_counter_ns()
    var _ns_seroconversion_rate = Float64(_t1_seroconversion_rate - _t0_seroconversion_rate) / Float64(N)
    print("MOJO_TIMING immunology::seroconversion_rate", _ns_seroconversion_rate, _acc_seroconversion_rate)
    var _result_seroconversion_rate = seroconversion_rate(0.5, 0.5)
    var _summary_seroconversion_rate = _summary_float64(_result_seroconversion_rate)
    print("MOJO_RESULT immunology::seroconversion_rate", _summary_seroconversion_rate)
    var _acc_antigen_antibody_binding: Float64 = 0.0
    var _t0_antigen_antibody_binding = perf_counter_ns()
    for _ in range(N):
        _acc_antigen_antibody_binding += antigen_antibody_binding(0.5, 0.5, 0.5)
    var _t1_antigen_antibody_binding = perf_counter_ns()
    var _ns_antigen_antibody_binding = Float64(_t1_antigen_antibody_binding - _t0_antigen_antibody_binding) / Float64(N)
    print("MOJO_TIMING immunology::antigen_antibody_binding", _ns_antigen_antibody_binding, _acc_antigen_antibody_binding)
    var _result_antigen_antibody_binding = antigen_antibody_binding(0.5, 0.5, 0.5)
    var _summary_antigen_antibody_binding = _summary_float64(_result_antigen_antibody_binding)
    print("MOJO_RESULT immunology::antigen_antibody_binding", _summary_antigen_antibody_binding)
    var _acc_complement_activation: Float64 = 0.0
    var _t0_complement_activation = perf_counter_ns()
    for _ in range(N):
        _acc_complement_activation += complement_activation(0.5, 0.5, 0.5)
    var _t1_complement_activation = perf_counter_ns()
    var _ns_complement_activation = Float64(_t1_complement_activation - _t0_complement_activation) / Float64(N)
    print("MOJO_TIMING immunology::complement_activation", _ns_complement_activation, _acc_complement_activation)
    var _result_complement_activation = complement_activation(0.5, 0.5, 0.5)
    var _summary_complement_activation = _summary_float64(_result_complement_activation)
    print("MOJO_RESULT immunology::complement_activation", _summary_complement_activation)
    var _acc_t_cell_proliferation: Float64 = 0.0
    var _t0_t_cell_proliferation = perf_counter_ns()
    for _ in range(N):
        _acc_t_cell_proliferation += t_cell_proliferation(0.5, 0.5, 0.5, 0.5)
    var _t1_t_cell_proliferation = perf_counter_ns()
    var _ns_t_cell_proliferation = Float64(_t1_t_cell_proliferation - _t0_t_cell_proliferation) / Float64(N)
    print("MOJO_TIMING immunology::t_cell_proliferation", _ns_t_cell_proliferation, _acc_t_cell_proliferation)
    var _result_t_cell_proliferation = t_cell_proliferation(0.5, 0.5, 0.5, 0.5)
    var _summary_t_cell_proliferation = _summary_float64(_result_t_cell_proliferation)
    print("MOJO_RESULT immunology::t_cell_proliferation", _summary_t_cell_proliferation)
    var _acc_innate_response_decay: Float64 = 0.0
    var _t0_innate_response_decay = perf_counter_ns()
    for _ in range(N):
        _acc_innate_response_decay += innate_response_decay(0.5, 0.5, 0.5)
    var _t1_innate_response_decay = perf_counter_ns()
    var _ns_innate_response_decay = Float64(_t1_innate_response_decay - _t0_innate_response_decay) / Float64(N)
    print("MOJO_TIMING immunology::innate_response_decay", _ns_innate_response_decay, _acc_innate_response_decay)
    var _result_innate_response_decay = innate_response_decay(0.5, 0.5, 0.5)
    var _summary_innate_response_decay = _summary_float64(_result_innate_response_decay)
    print("MOJO_RESULT immunology::innate_response_decay", _summary_innate_response_decay)
    var _acc_vaccine_efficacy: Float64 = 0.0
    var _t0_vaccine_efficacy = perf_counter_ns()
    for _ in range(N):
        _acc_vaccine_efficacy += vaccine_efficacy(0.5, 0.5)
    var _t1_vaccine_efficacy = perf_counter_ns()
    var _ns_vaccine_efficacy = Float64(_t1_vaccine_efficacy - _t0_vaccine_efficacy) / Float64(N)
    print("MOJO_TIMING immunology::vaccine_efficacy", _ns_vaccine_efficacy, _acc_vaccine_efficacy)
    var _result_vaccine_efficacy = vaccine_efficacy(0.5, 0.5)
    var _summary_vaccine_efficacy = _summary_float64(_result_vaccine_efficacy)
    print("MOJO_RESULT immunology::vaccine_efficacy", _summary_vaccine_efficacy)
    var _acc_herd_immunity_threshold: Float64 = 0.0
    var _t0_herd_immunity_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_herd_immunity_threshold += herd_immunity_threshold(0.5)
    var _t1_herd_immunity_threshold = perf_counter_ns()
    var _ns_herd_immunity_threshold = Float64(_t1_herd_immunity_threshold - _t0_herd_immunity_threshold) / Float64(N)
    print("MOJO_TIMING immunology::herd_immunity_threshold", _ns_herd_immunity_threshold, _acc_herd_immunity_threshold)
    var _result_herd_immunity_threshold = herd_immunity_threshold(0.5)
    var _summary_herd_immunity_threshold = _summary_float64(_result_herd_immunity_threshold)
    print("MOJO_RESULT immunology::herd_immunity_threshold", _summary_herd_immunity_threshold)
    var _acc_antibody_avidity_index: Float64 = 0.0
    var _t0_antibody_avidity_index = perf_counter_ns()
    for _ in range(N):
        _acc_antibody_avidity_index += antibody_avidity_index(0.5, 0.5)
    var _t1_antibody_avidity_index = perf_counter_ns()
    var _ns_antibody_avidity_index = Float64(_t1_antibody_avidity_index - _t0_antibody_avidity_index) / Float64(N)
    print("MOJO_TIMING immunology::antibody_avidity_index", _ns_antibody_avidity_index, _acc_antibody_avidity_index)
    var _result_antibody_avidity_index = antibody_avidity_index(0.5, 0.5)
    var _summary_antibody_avidity_index = _summary_float64(_result_antibody_avidity_index)
    print("MOJO_RESULT immunology::antibody_avidity_index", _summary_antibody_avidity_index)
    var _acc_opsonisation_index: Float64 = 0.0
    var _t0_opsonisation_index = perf_counter_ns()
    for _ in range(N):
        _acc_opsonisation_index += opsonisation_index(0.5, 0.5)
    var _t1_opsonisation_index = perf_counter_ns()
    var _ns_opsonisation_index = Float64(_t1_opsonisation_index - _t0_opsonisation_index) / Float64(N)
    print("MOJO_TIMING immunology::opsonisation_index", _ns_opsonisation_index, _acc_opsonisation_index)
    var _result_opsonisation_index = opsonisation_index(0.5, 0.5)
    var _summary_opsonisation_index = _summary_float64(_result_opsonisation_index)
    print("MOJO_RESULT immunology::opsonisation_index", _summary_opsonisation_index)
