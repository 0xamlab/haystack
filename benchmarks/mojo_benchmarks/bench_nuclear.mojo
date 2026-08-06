"""bench_nuclear.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from nuclear import radioactive_decay, half_life_from_lambda, lambda_from_half_life, activity, decay_constant_from_activity, binding_energy_per_nucleon, mass_defect, q_value, neutron_multiplication, dose_rate_inverse_square, shielding_attenuation, critical_mass_estimate
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

    var _acc_radioactive_decay: Float64 = 0.0
    var _t0_radioactive_decay = perf_counter_ns()
    for _ in range(N):
        _acc_radioactive_decay += radioactive_decay(0.5, 0.5, 0.5)
    var _t1_radioactive_decay = perf_counter_ns()
    var _ns_radioactive_decay = Float64(_t1_radioactive_decay - _t0_radioactive_decay) / Float64(N)
    print("MOJO_TIMING nuclear::radioactive_decay", _ns_radioactive_decay, _acc_radioactive_decay)
    var _result_radioactive_decay = radioactive_decay(0.5, 0.5, 0.5)
    var _summary_radioactive_decay = _summary_float64(_result_radioactive_decay)
    print("MOJO_RESULT nuclear::radioactive_decay", _summary_radioactive_decay)
    var _acc_half_life_from_lambda: Float64 = 0.0
    var _t0_half_life_from_lambda = perf_counter_ns()
    for _ in range(N):
        _acc_half_life_from_lambda += half_life_from_lambda(0.5)
    var _t1_half_life_from_lambda = perf_counter_ns()
    var _ns_half_life_from_lambda = Float64(_t1_half_life_from_lambda - _t0_half_life_from_lambda) / Float64(N)
    print("MOJO_TIMING nuclear::half_life_from_lambda", _ns_half_life_from_lambda, _acc_half_life_from_lambda)
    var _result_half_life_from_lambda = half_life_from_lambda(0.5)
    var _summary_half_life_from_lambda = _summary_float64(_result_half_life_from_lambda)
    print("MOJO_RESULT nuclear::half_life_from_lambda", _summary_half_life_from_lambda)
    var _acc_lambda_from_half_life: Float64 = 0.0
    var _t0_lambda_from_half_life = perf_counter_ns()
    for _ in range(N):
        _acc_lambda_from_half_life += lambda_from_half_life(0.5)
    var _t1_lambda_from_half_life = perf_counter_ns()
    var _ns_lambda_from_half_life = Float64(_t1_lambda_from_half_life - _t0_lambda_from_half_life) / Float64(N)
    print("MOJO_TIMING nuclear::lambda_from_half_life", _ns_lambda_from_half_life, _acc_lambda_from_half_life)
    var _result_lambda_from_half_life = lambda_from_half_life(0.5)
    var _summary_lambda_from_half_life = _summary_float64(_result_lambda_from_half_life)
    print("MOJO_RESULT nuclear::lambda_from_half_life", _summary_lambda_from_half_life)
    var _acc_activity: Float64 = 0.0
    var _t0_activity = perf_counter_ns()
    for _ in range(N):
        _acc_activity += activity(0.5, 0.5)
    var _t1_activity = perf_counter_ns()
    var _ns_activity = Float64(_t1_activity - _t0_activity) / Float64(N)
    print("MOJO_TIMING nuclear::activity", _ns_activity, _acc_activity)
    var _result_activity = activity(0.5, 0.5)
    var _summary_activity = _summary_float64(_result_activity)
    print("MOJO_RESULT nuclear::activity", _summary_activity)
    var _acc_decay_constant_from_activity: Float64 = 0.0
    var _t0_decay_constant_from_activity = perf_counter_ns()
    for _ in range(N):
        _acc_decay_constant_from_activity += decay_constant_from_activity(0.5, 0.5)
    var _t1_decay_constant_from_activity = perf_counter_ns()
    var _ns_decay_constant_from_activity = Float64(_t1_decay_constant_from_activity - _t0_decay_constant_from_activity) / Float64(N)
    print("MOJO_TIMING nuclear::decay_constant_from_activity", _ns_decay_constant_from_activity, _acc_decay_constant_from_activity)
    var _result_decay_constant_from_activity = decay_constant_from_activity(0.5, 0.5)
    var _summary_decay_constant_from_activity = _summary_float64(_result_decay_constant_from_activity)
    print("MOJO_RESULT nuclear::decay_constant_from_activity", _summary_decay_constant_from_activity)
    var _acc_binding_energy_per_nucleon: Float64 = 0.0
    var _t0_binding_energy_per_nucleon = perf_counter_ns()
    for _ in range(N):
        _acc_binding_energy_per_nucleon += binding_energy_per_nucleon(0.5, 0.5)
    var _t1_binding_energy_per_nucleon = perf_counter_ns()
    var _ns_binding_energy_per_nucleon = Float64(_t1_binding_energy_per_nucleon - _t0_binding_energy_per_nucleon) / Float64(N)
    print("MOJO_TIMING nuclear::binding_energy_per_nucleon", _ns_binding_energy_per_nucleon, _acc_binding_energy_per_nucleon)
    var _result_binding_energy_per_nucleon = binding_energy_per_nucleon(0.5, 0.5)
    var _summary_binding_energy_per_nucleon = _summary_float64(_result_binding_energy_per_nucleon)
    print("MOJO_RESULT nuclear::binding_energy_per_nucleon", _summary_binding_energy_per_nucleon)
    var _acc_mass_defect: Float64 = 0.0
    var _t0_mass_defect = perf_counter_ns()
    for _ in range(N):
        _acc_mass_defect += mass_defect(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_mass_defect = perf_counter_ns()
    var _ns_mass_defect = Float64(_t1_mass_defect - _t0_mass_defect) / Float64(N)
    print("MOJO_TIMING nuclear::mass_defect", _ns_mass_defect, _acc_mass_defect)
    var _result_mass_defect = mass_defect(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_mass_defect = _summary_float64(_result_mass_defect)
    print("MOJO_RESULT nuclear::mass_defect", _summary_mass_defect)
    var _acc_q_value: Float64 = 0.0
    var _t0_q_value = perf_counter_ns()
    for _ in range(N):
        _acc_q_value += q_value(0.5, 0.5, 0.5)
    var _t1_q_value = perf_counter_ns()
    var _ns_q_value = Float64(_t1_q_value - _t0_q_value) / Float64(N)
    print("MOJO_TIMING nuclear::q_value", _ns_q_value, _acc_q_value)
    var _result_q_value = q_value(0.5, 0.5, 0.5)
    var _summary_q_value = _summary_float64(_result_q_value)
    print("MOJO_RESULT nuclear::q_value", _summary_q_value)
    var _acc_neutron_multiplication: Float64 = 0.0
    var _t0_neutron_multiplication = perf_counter_ns()
    for _ in range(N):
        _acc_neutron_multiplication += neutron_multiplication(0.5, 0.5)
    var _t1_neutron_multiplication = perf_counter_ns()
    var _ns_neutron_multiplication = Float64(_t1_neutron_multiplication - _t0_neutron_multiplication) / Float64(N)
    print("MOJO_TIMING nuclear::neutron_multiplication", _ns_neutron_multiplication, _acc_neutron_multiplication)
    var _result_neutron_multiplication = neutron_multiplication(0.5, 0.5)
    var _summary_neutron_multiplication = _summary_float64(_result_neutron_multiplication)
    print("MOJO_RESULT nuclear::neutron_multiplication", _summary_neutron_multiplication)
    var _acc_dose_rate_inverse_square: Float64 = 0.0
    var _t0_dose_rate_inverse_square = perf_counter_ns()
    for _ in range(N):
        _acc_dose_rate_inverse_square += dose_rate_inverse_square(0.5, 0.5, 0.5)
    var _t1_dose_rate_inverse_square = perf_counter_ns()
    var _ns_dose_rate_inverse_square = Float64(_t1_dose_rate_inverse_square - _t0_dose_rate_inverse_square) / Float64(N)
    print("MOJO_TIMING nuclear::dose_rate_inverse_square", _ns_dose_rate_inverse_square, _acc_dose_rate_inverse_square)
    var _result_dose_rate_inverse_square = dose_rate_inverse_square(0.5, 0.5, 0.5)
    var _summary_dose_rate_inverse_square = _summary_float64(_result_dose_rate_inverse_square)
    print("MOJO_RESULT nuclear::dose_rate_inverse_square", _summary_dose_rate_inverse_square)
    var _acc_shielding_attenuation: Float64 = 0.0
    var _t0_shielding_attenuation = perf_counter_ns()
    for _ in range(N):
        _acc_shielding_attenuation += shielding_attenuation(0.5, 0.5, 0.5)
    var _t1_shielding_attenuation = perf_counter_ns()
    var _ns_shielding_attenuation = Float64(_t1_shielding_attenuation - _t0_shielding_attenuation) / Float64(N)
    print("MOJO_TIMING nuclear::shielding_attenuation", _ns_shielding_attenuation, _acc_shielding_attenuation)
    var _result_shielding_attenuation = shielding_attenuation(0.5, 0.5, 0.5)
    var _summary_shielding_attenuation = _summary_float64(_result_shielding_attenuation)
    print("MOJO_RESULT nuclear::shielding_attenuation", _summary_shielding_attenuation)
    var _acc_critical_mass_estimate: Float64 = 0.0
    var _t0_critical_mass_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_critical_mass_estimate += critical_mass_estimate(0.5, 0.5, 0.5)
    var _t1_critical_mass_estimate = perf_counter_ns()
    var _ns_critical_mass_estimate = Float64(_t1_critical_mass_estimate - _t0_critical_mass_estimate) / Float64(N)
    print("MOJO_TIMING nuclear::critical_mass_estimate", _ns_critical_mass_estimate, _acc_critical_mass_estimate)
    var _result_critical_mass_estimate = critical_mass_estimate(0.5, 0.5, 0.5)
    var _summary_critical_mass_estimate = _summary_float64(_result_critical_mass_estimate)
    print("MOJO_RESULT nuclear::critical_mass_estimate", _summary_critical_mass_estimate)
