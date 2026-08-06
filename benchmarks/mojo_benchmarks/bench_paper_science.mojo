"""bench_paper_science.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from paper_science import basis_weight, caliper_to_density, bulk, tearing_resistance_index, tensile_index, burst_index, freeness_csf, kappa_number_to_lignin, pulp_yield, moisture_content_paper, stiffness_index, recycled_fiber_content
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

    var _acc_basis_weight: Float64 = 0.0
    var _t0_basis_weight = perf_counter_ns()
    for _ in range(N):
        _acc_basis_weight += basis_weight(0.5, 0.5)
    var _t1_basis_weight = perf_counter_ns()
    var _ns_basis_weight = Float64(_t1_basis_weight - _t0_basis_weight) / Float64(N)
    print("MOJO_TIMING paper_science::basis_weight", _ns_basis_weight, _acc_basis_weight)
    var _result_basis_weight = basis_weight(0.5, 0.5)
    var _summary_basis_weight = _summary_float64(_result_basis_weight)
    print("MOJO_RESULT paper_science::basis_weight", _summary_basis_weight)
    var _acc_caliper_to_density: Float64 = 0.0
    var _t0_caliper_to_density = perf_counter_ns()
    for _ in range(N):
        _acc_caliper_to_density += caliper_to_density(0.5, 0.5)
    var _t1_caliper_to_density = perf_counter_ns()
    var _ns_caliper_to_density = Float64(_t1_caliper_to_density - _t0_caliper_to_density) / Float64(N)
    print("MOJO_TIMING paper_science::caliper_to_density", _ns_caliper_to_density, _acc_caliper_to_density)
    var _result_caliper_to_density = caliper_to_density(0.5, 0.5)
    var _summary_caliper_to_density = _summary_float64(_result_caliper_to_density)
    print("MOJO_RESULT paper_science::caliper_to_density", _summary_caliper_to_density)
    var _acc_bulk: Float64 = 0.0
    var _t0_bulk = perf_counter_ns()
    for _ in range(N):
        _acc_bulk += bulk(0.5, 0.5)
    var _t1_bulk = perf_counter_ns()
    var _ns_bulk = Float64(_t1_bulk - _t0_bulk) / Float64(N)
    print("MOJO_TIMING paper_science::bulk", _ns_bulk, _acc_bulk)
    var _result_bulk = bulk(0.5, 0.5)
    var _summary_bulk = _summary_float64(_result_bulk)
    print("MOJO_RESULT paper_science::bulk", _summary_bulk)
    var _acc_tearing_resistance_index: Float64 = 0.0
    var _t0_tearing_resistance_index = perf_counter_ns()
    for _ in range(N):
        _acc_tearing_resistance_index += tearing_resistance_index(0.5, 0.5)
    var _t1_tearing_resistance_index = perf_counter_ns()
    var _ns_tearing_resistance_index = Float64(_t1_tearing_resistance_index - _t0_tearing_resistance_index) / Float64(N)
    print("MOJO_TIMING paper_science::tearing_resistance_index", _ns_tearing_resistance_index, _acc_tearing_resistance_index)
    var _result_tearing_resistance_index = tearing_resistance_index(0.5, 0.5)
    var _summary_tearing_resistance_index = _summary_float64(_result_tearing_resistance_index)
    print("MOJO_RESULT paper_science::tearing_resistance_index", _summary_tearing_resistance_index)
    var _acc_tensile_index: Float64 = 0.0
    var _t0_tensile_index = perf_counter_ns()
    for _ in range(N):
        _acc_tensile_index += tensile_index(0.5, 0.5)
    var _t1_tensile_index = perf_counter_ns()
    var _ns_tensile_index = Float64(_t1_tensile_index - _t0_tensile_index) / Float64(N)
    print("MOJO_TIMING paper_science::tensile_index", _ns_tensile_index, _acc_tensile_index)
    var _result_tensile_index = tensile_index(0.5, 0.5)
    var _summary_tensile_index = _summary_float64(_result_tensile_index)
    print("MOJO_RESULT paper_science::tensile_index", _summary_tensile_index)
    var _acc_burst_index: Float64 = 0.0
    var _t0_burst_index = perf_counter_ns()
    for _ in range(N):
        _acc_burst_index += burst_index(0.5, 0.5)
    var _t1_burst_index = perf_counter_ns()
    var _ns_burst_index = Float64(_t1_burst_index - _t0_burst_index) / Float64(N)
    print("MOJO_TIMING paper_science::burst_index", _ns_burst_index, _acc_burst_index)
    var _result_burst_index = burst_index(0.5, 0.5)
    var _summary_burst_index = _summary_float64(_result_burst_index)
    print("MOJO_RESULT paper_science::burst_index", _summary_burst_index)
    var _acc_freeness_csf: Float64 = 0.0
    var _t0_freeness_csf = perf_counter_ns()
    for _ in range(N):
        _acc_freeness_csf += freeness_csf(0.5)
    var _t1_freeness_csf = perf_counter_ns()
    var _ns_freeness_csf = Float64(_t1_freeness_csf - _t0_freeness_csf) / Float64(N)
    print("MOJO_TIMING paper_science::freeness_csf", _ns_freeness_csf, _acc_freeness_csf)
    var _result_freeness_csf = freeness_csf(0.5)
    var _summary_freeness_csf = _summary_float64(_result_freeness_csf)
    print("MOJO_RESULT paper_science::freeness_csf", _summary_freeness_csf)
    var _acc_kappa_number_to_lignin: Float64 = 0.0
    var _t0_kappa_number_to_lignin = perf_counter_ns()
    for _ in range(N):
        _acc_kappa_number_to_lignin += kappa_number_to_lignin(0.5)
    var _t1_kappa_number_to_lignin = perf_counter_ns()
    var _ns_kappa_number_to_lignin = Float64(_t1_kappa_number_to_lignin - _t0_kappa_number_to_lignin) / Float64(N)
    print("MOJO_TIMING paper_science::kappa_number_to_lignin", _ns_kappa_number_to_lignin, _acc_kappa_number_to_lignin)
    var _result_kappa_number_to_lignin = kappa_number_to_lignin(0.5)
    var _summary_kappa_number_to_lignin = _summary_float64(_result_kappa_number_to_lignin)
    print("MOJO_RESULT paper_science::kappa_number_to_lignin", _summary_kappa_number_to_lignin)
    var _acc_pulp_yield: Float64 = 0.0
    var _t0_pulp_yield = perf_counter_ns()
    for _ in range(N):
        _acc_pulp_yield += pulp_yield(0.5, 0.5)
    var _t1_pulp_yield = perf_counter_ns()
    var _ns_pulp_yield = Float64(_t1_pulp_yield - _t0_pulp_yield) / Float64(N)
    print("MOJO_TIMING paper_science::pulp_yield", _ns_pulp_yield, _acc_pulp_yield)
    var _result_pulp_yield = pulp_yield(0.5, 0.5)
    var _summary_pulp_yield = _summary_float64(_result_pulp_yield)
    print("MOJO_RESULT paper_science::pulp_yield", _summary_pulp_yield)
    var _acc_moisture_content_paper: Float64 = 0.0
    var _t0_moisture_content_paper = perf_counter_ns()
    for _ in range(N):
        _acc_moisture_content_paper += moisture_content_paper(0.5, 0.5)
    var _t1_moisture_content_paper = perf_counter_ns()
    var _ns_moisture_content_paper = Float64(_t1_moisture_content_paper - _t0_moisture_content_paper) / Float64(N)
    print("MOJO_TIMING paper_science::moisture_content_paper", _ns_moisture_content_paper, _acc_moisture_content_paper)
    var _result_moisture_content_paper = moisture_content_paper(0.5, 0.5)
    var _summary_moisture_content_paper = _summary_float64(_result_moisture_content_paper)
    print("MOJO_RESULT paper_science::moisture_content_paper", _summary_moisture_content_paper)
    var _acc_stiffness_index: Float64 = 0.0
    var _t0_stiffness_index = perf_counter_ns()
    for _ in range(N):
        _acc_stiffness_index += stiffness_index(0.5, 0.5)
    var _t1_stiffness_index = perf_counter_ns()
    var _ns_stiffness_index = Float64(_t1_stiffness_index - _t0_stiffness_index) / Float64(N)
    print("MOJO_TIMING paper_science::stiffness_index", _ns_stiffness_index, _acc_stiffness_index)
    var _result_stiffness_index = stiffness_index(0.5, 0.5)
    var _summary_stiffness_index = _summary_float64(_result_stiffness_index)
    print("MOJO_RESULT paper_science::stiffness_index", _summary_stiffness_index)
    var _acc_recycled_fiber_content: Float64 = 0.0
    var _t0_recycled_fiber_content = perf_counter_ns()
    for _ in range(N):
        _acc_recycled_fiber_content += recycled_fiber_content(0.5, 0.5)
    var _t1_recycled_fiber_content = perf_counter_ns()
    var _ns_recycled_fiber_content = Float64(_t1_recycled_fiber_content - _t0_recycled_fiber_content) / Float64(N)
    print("MOJO_TIMING paper_science::recycled_fiber_content", _ns_recycled_fiber_content, _acc_recycled_fiber_content)
    var _result_recycled_fiber_content = recycled_fiber_content(0.5, 0.5)
    var _summary_recycled_fiber_content = _summary_float64(_result_recycled_fiber_content)
    print("MOJO_RESULT paper_science::recycled_fiber_content", _summary_recycled_fiber_content)
