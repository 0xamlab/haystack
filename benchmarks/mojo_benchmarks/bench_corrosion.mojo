"""bench_corrosion.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from corrosion import corrosion_rate_mpy, corrosion_rate_mmpy, pitting_rate, pitting_factor, galvanic_potential_difference, nernst_potential, passivation_current_density, tafel_overpotential, metal_loss_from_rate, remaining_wall_thickness, cathodic_protection_current, service_life_estimate
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

    var _acc_corrosion_rate_mpy: Float64 = 0.0
    var _t0_corrosion_rate_mpy = perf_counter_ns()
    for _ in range(N):
        _acc_corrosion_rate_mpy += corrosion_rate_mpy(0.5, 0.5, 0.5, 0.5)
    var _t1_corrosion_rate_mpy = perf_counter_ns()
    var _ns_corrosion_rate_mpy = Float64(_t1_corrosion_rate_mpy - _t0_corrosion_rate_mpy) / Float64(N)
    print("MOJO_TIMING corrosion::corrosion_rate_mpy", _ns_corrosion_rate_mpy, _acc_corrosion_rate_mpy)
    var _result_corrosion_rate_mpy = corrosion_rate_mpy(0.5, 0.5, 0.5, 0.5)
    var _summary_corrosion_rate_mpy = _summary_float64(_result_corrosion_rate_mpy)
    print("MOJO_RESULT corrosion::corrosion_rate_mpy", _summary_corrosion_rate_mpy)
    var _acc_corrosion_rate_mmpy: Float64 = 0.0
    var _t0_corrosion_rate_mmpy = perf_counter_ns()
    for _ in range(N):
        _acc_corrosion_rate_mmpy += corrosion_rate_mmpy(0.5, 0.5, 0.5, 0.5)
    var _t1_corrosion_rate_mmpy = perf_counter_ns()
    var _ns_corrosion_rate_mmpy = Float64(_t1_corrosion_rate_mmpy - _t0_corrosion_rate_mmpy) / Float64(N)
    print("MOJO_TIMING corrosion::corrosion_rate_mmpy", _ns_corrosion_rate_mmpy, _acc_corrosion_rate_mmpy)
    var _result_corrosion_rate_mmpy = corrosion_rate_mmpy(0.5, 0.5, 0.5, 0.5)
    var _summary_corrosion_rate_mmpy = _summary_float64(_result_corrosion_rate_mmpy)
    print("MOJO_RESULT corrosion::corrosion_rate_mmpy", _summary_corrosion_rate_mmpy)
    var _acc_pitting_rate: Float64 = 0.0
    var _t0_pitting_rate = perf_counter_ns()
    for _ in range(N):
        _acc_pitting_rate += pitting_rate(0.5, 0.5)
    var _t1_pitting_rate = perf_counter_ns()
    var _ns_pitting_rate = Float64(_t1_pitting_rate - _t0_pitting_rate) / Float64(N)
    print("MOJO_TIMING corrosion::pitting_rate", _ns_pitting_rate, _acc_pitting_rate)
    var _result_pitting_rate = pitting_rate(0.5, 0.5)
    var _summary_pitting_rate = _summary_float64(_result_pitting_rate)
    print("MOJO_RESULT corrosion::pitting_rate", _summary_pitting_rate)
    var _acc_pitting_factor: Float64 = 0.0
    var _t0_pitting_factor = perf_counter_ns()
    for _ in range(N):
        _acc_pitting_factor += pitting_factor(0.5, 0.5)
    var _t1_pitting_factor = perf_counter_ns()
    var _ns_pitting_factor = Float64(_t1_pitting_factor - _t0_pitting_factor) / Float64(N)
    print("MOJO_TIMING corrosion::pitting_factor", _ns_pitting_factor, _acc_pitting_factor)
    var _result_pitting_factor = pitting_factor(0.5, 0.5)
    var _summary_pitting_factor = _summary_float64(_result_pitting_factor)
    print("MOJO_RESULT corrosion::pitting_factor", _summary_pitting_factor)
    var _acc_galvanic_potential_difference: Float64 = 0.0
    var _t0_galvanic_potential_difference = perf_counter_ns()
    for _ in range(N):
        _acc_galvanic_potential_difference += galvanic_potential_difference(0.5, 0.5)
    var _t1_galvanic_potential_difference = perf_counter_ns()
    var _ns_galvanic_potential_difference = Float64(_t1_galvanic_potential_difference - _t0_galvanic_potential_difference) / Float64(N)
    print("MOJO_TIMING corrosion::galvanic_potential_difference", _ns_galvanic_potential_difference, _acc_galvanic_potential_difference)
    var _result_galvanic_potential_difference = galvanic_potential_difference(0.5, 0.5)
    var _summary_galvanic_potential_difference = _summary_float64(_result_galvanic_potential_difference)
    print("MOJO_RESULT corrosion::galvanic_potential_difference", _summary_galvanic_potential_difference)
    var _acc_nernst_potential: Float64 = 0.0
    var _t0_nernst_potential = perf_counter_ns()
    for _ in range(N):
        _acc_nernst_potential += nernst_potential(0.5, 0.5, 0.5, 0.5)
    var _t1_nernst_potential = perf_counter_ns()
    var _ns_nernst_potential = Float64(_t1_nernst_potential - _t0_nernst_potential) / Float64(N)
    print("MOJO_TIMING corrosion::nernst_potential", _ns_nernst_potential, _acc_nernst_potential)
    var _result_nernst_potential = nernst_potential(0.5, 0.5, 0.5, 0.5)
    var _summary_nernst_potential = _summary_float64(_result_nernst_potential)
    print("MOJO_RESULT corrosion::nernst_potential", _summary_nernst_potential)
    var _acc_passivation_current_density: Float64 = 0.0
    var _t0_passivation_current_density = perf_counter_ns()
    for _ in range(N):
        _acc_passivation_current_density += passivation_current_density(0.5, 0.5)
    var _t1_passivation_current_density = perf_counter_ns()
    var _ns_passivation_current_density = Float64(_t1_passivation_current_density - _t0_passivation_current_density) / Float64(N)
    print("MOJO_TIMING corrosion::passivation_current_density", _ns_passivation_current_density, _acc_passivation_current_density)
    var _result_passivation_current_density = passivation_current_density(0.5, 0.5)
    var _summary_passivation_current_density = _summary_float64(_result_passivation_current_density)
    print("MOJO_RESULT corrosion::passivation_current_density", _summary_passivation_current_density)
    var _acc_tafel_overpotential: Float64 = 0.0
    var _t0_tafel_overpotential = perf_counter_ns()
    for _ in range(N):
        _acc_tafel_overpotential += tafel_overpotential(0.5, 0.5, 0.5)
    var _t1_tafel_overpotential = perf_counter_ns()
    var _ns_tafel_overpotential = Float64(_t1_tafel_overpotential - _t0_tafel_overpotential) / Float64(N)
    print("MOJO_TIMING corrosion::tafel_overpotential", _ns_tafel_overpotential, _acc_tafel_overpotential)
    var _result_tafel_overpotential = tafel_overpotential(0.5, 0.5, 0.5)
    var _summary_tafel_overpotential = _summary_float64(_result_tafel_overpotential)
    print("MOJO_RESULT corrosion::tafel_overpotential", _summary_tafel_overpotential)
    var _acc_metal_loss_from_rate: Float64 = 0.0
    var _t0_metal_loss_from_rate = perf_counter_ns()
    for _ in range(N):
        _acc_metal_loss_from_rate += metal_loss_from_rate(0.5, 0.5)
    var _t1_metal_loss_from_rate = perf_counter_ns()
    var _ns_metal_loss_from_rate = Float64(_t1_metal_loss_from_rate - _t0_metal_loss_from_rate) / Float64(N)
    print("MOJO_TIMING corrosion::metal_loss_from_rate", _ns_metal_loss_from_rate, _acc_metal_loss_from_rate)
    var _result_metal_loss_from_rate = metal_loss_from_rate(0.5, 0.5)
    var _summary_metal_loss_from_rate = _summary_float64(_result_metal_loss_from_rate)
    print("MOJO_RESULT corrosion::metal_loss_from_rate", _summary_metal_loss_from_rate)
    var _acc_remaining_wall_thickness: Float64 = 0.0
    var _t0_remaining_wall_thickness = perf_counter_ns()
    for _ in range(N):
        _acc_remaining_wall_thickness += remaining_wall_thickness(0.5, 0.5)
    var _t1_remaining_wall_thickness = perf_counter_ns()
    var _ns_remaining_wall_thickness = Float64(_t1_remaining_wall_thickness - _t0_remaining_wall_thickness) / Float64(N)
    print("MOJO_TIMING corrosion::remaining_wall_thickness", _ns_remaining_wall_thickness, _acc_remaining_wall_thickness)
    var _result_remaining_wall_thickness = remaining_wall_thickness(0.5, 0.5)
    var _summary_remaining_wall_thickness = _summary_float64(_result_remaining_wall_thickness)
    print("MOJO_RESULT corrosion::remaining_wall_thickness", _summary_remaining_wall_thickness)
    var _acc_cathodic_protection_current: Float64 = 0.0
    var _t0_cathodic_protection_current = perf_counter_ns()
    for _ in range(N):
        _acc_cathodic_protection_current += cathodic_protection_current(0.5, 0.5)
    var _t1_cathodic_protection_current = perf_counter_ns()
    var _ns_cathodic_protection_current = Float64(_t1_cathodic_protection_current - _t0_cathodic_protection_current) / Float64(N)
    print("MOJO_TIMING corrosion::cathodic_protection_current", _ns_cathodic_protection_current, _acc_cathodic_protection_current)
    var _result_cathodic_protection_current = cathodic_protection_current(0.5, 0.5)
    var _summary_cathodic_protection_current = _summary_float64(_result_cathodic_protection_current)
    print("MOJO_RESULT corrosion::cathodic_protection_current", _summary_cathodic_protection_current)
    var _acc_service_life_estimate: Float64 = 0.0
    var _t0_service_life_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_service_life_estimate += service_life_estimate(0.5, 0.5)
    var _t1_service_life_estimate = perf_counter_ns()
    var _ns_service_life_estimate = Float64(_t1_service_life_estimate - _t0_service_life_estimate) / Float64(N)
    print("MOJO_TIMING corrosion::service_life_estimate", _ns_service_life_estimate, _acc_service_life_estimate)
    var _result_service_life_estimate = service_life_estimate(0.5, 0.5)
    var _summary_service_life_estimate = _summary_float64(_result_service_life_estimate)
    print("MOJO_RESULT corrosion::service_life_estimate", _summary_service_life_estimate)
