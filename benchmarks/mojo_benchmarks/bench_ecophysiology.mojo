"""bench_ecophysiology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ecophysiology import metabolic_rate_kleiber, thermal_conductance, q10_temperature_coefficient, evaporative_water_loss, aerobic_scope, hypoxia_tolerance, osmoregulation_cost, heart_rate_fick, oxygen_consumption_rate, field_metabolic_rate
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

    var _acc_metabolic_rate_kleiber: Float64 = 0.0
    var _t0_metabolic_rate_kleiber = perf_counter_ns()
    for _ in range(N):
        _acc_metabolic_rate_kleiber += metabolic_rate_kleiber(0.5)
    var _t1_metabolic_rate_kleiber = perf_counter_ns()
    var _ns_metabolic_rate_kleiber = Float64(_t1_metabolic_rate_kleiber - _t0_metabolic_rate_kleiber) / Float64(N)
    print("MOJO_TIMING ecophysiology::metabolic_rate_kleiber", _ns_metabolic_rate_kleiber, _acc_metabolic_rate_kleiber)
    var _result_metabolic_rate_kleiber = metabolic_rate_kleiber(0.5)
    var _summary_metabolic_rate_kleiber = _summary_float64(_result_metabolic_rate_kleiber)
    print("MOJO_RESULT ecophysiology::metabolic_rate_kleiber", _summary_metabolic_rate_kleiber)
    var _acc_thermal_conductance: Float64 = 0.0
    var _t0_thermal_conductance = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_conductance += thermal_conductance(0.5, 0.5, 0.5)
    var _t1_thermal_conductance = perf_counter_ns()
    var _ns_thermal_conductance = Float64(_t1_thermal_conductance - _t0_thermal_conductance) / Float64(N)
    print("MOJO_TIMING ecophysiology::thermal_conductance", _ns_thermal_conductance, _acc_thermal_conductance)
    var _result_thermal_conductance = thermal_conductance(0.5, 0.5, 0.5)
    var _summary_thermal_conductance = _summary_float64(_result_thermal_conductance)
    print("MOJO_RESULT ecophysiology::thermal_conductance", _summary_thermal_conductance)
    var _acc_q10_temperature_coefficient: Float64 = 0.0
    var _t0_q10_temperature_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_q10_temperature_coefficient += q10_temperature_coefficient(0.5, 0.5, 0.5, 0.5)
    var _t1_q10_temperature_coefficient = perf_counter_ns()
    var _ns_q10_temperature_coefficient = Float64(_t1_q10_temperature_coefficient - _t0_q10_temperature_coefficient) / Float64(N)
    print("MOJO_TIMING ecophysiology::q10_temperature_coefficient", _ns_q10_temperature_coefficient, _acc_q10_temperature_coefficient)
    var _result_q10_temperature_coefficient = q10_temperature_coefficient(0.5, 0.5, 0.5, 0.5)
    var _summary_q10_temperature_coefficient = _summary_float64(_result_q10_temperature_coefficient)
    print("MOJO_RESULT ecophysiology::q10_temperature_coefficient", _summary_q10_temperature_coefficient)
    var _acc_evaporative_water_loss: Float64 = 0.0
    var _t0_evaporative_water_loss = perf_counter_ns()
    for _ in range(N):
        _acc_evaporative_water_loss += evaporative_water_loss(0.5, 0.5, 0.5)
    var _t1_evaporative_water_loss = perf_counter_ns()
    var _ns_evaporative_water_loss = Float64(_t1_evaporative_water_loss - _t0_evaporative_water_loss) / Float64(N)
    print("MOJO_TIMING ecophysiology::evaporative_water_loss", _ns_evaporative_water_loss, _acc_evaporative_water_loss)
    var _result_evaporative_water_loss = evaporative_water_loss(0.5, 0.5, 0.5)
    var _summary_evaporative_water_loss = _summary_float64(_result_evaporative_water_loss)
    print("MOJO_RESULT ecophysiology::evaporative_water_loss", _summary_evaporative_water_loss)
    var _acc_aerobic_scope: Float64 = 0.0
    var _t0_aerobic_scope = perf_counter_ns()
    for _ in range(N):
        _acc_aerobic_scope += aerobic_scope(0.5, 0.5)
    var _t1_aerobic_scope = perf_counter_ns()
    var _ns_aerobic_scope = Float64(_t1_aerobic_scope - _t0_aerobic_scope) / Float64(N)
    print("MOJO_TIMING ecophysiology::aerobic_scope", _ns_aerobic_scope, _acc_aerobic_scope)
    var _result_aerobic_scope = aerobic_scope(0.5, 0.5)
    var _summary_aerobic_scope = _summary_float64(_result_aerobic_scope)
    print("MOJO_RESULT ecophysiology::aerobic_scope", _summary_aerobic_scope)
    var _acc_hypoxia_tolerance: Float64 = 0.0
    var _t0_hypoxia_tolerance = perf_counter_ns()
    for _ in range(N):
        _acc_hypoxia_tolerance += hypoxia_tolerance(0.5, 0.5)
    var _t1_hypoxia_tolerance = perf_counter_ns()
    var _ns_hypoxia_tolerance = Float64(_t1_hypoxia_tolerance - _t0_hypoxia_tolerance) / Float64(N)
    print("MOJO_TIMING ecophysiology::hypoxia_tolerance", _ns_hypoxia_tolerance, _acc_hypoxia_tolerance)
    var _result_hypoxia_tolerance = hypoxia_tolerance(0.5, 0.5)
    var _summary_hypoxia_tolerance = _summary_float64(_result_hypoxia_tolerance)
    print("MOJO_RESULT ecophysiology::hypoxia_tolerance", _summary_hypoxia_tolerance)
    var _acc_osmoregulation_cost: Float64 = 0.0
    var _t0_osmoregulation_cost = perf_counter_ns()
    for _ in range(N):
        _acc_osmoregulation_cost += osmoregulation_cost(0.5, 0.5, 0.5)
    var _t1_osmoregulation_cost = perf_counter_ns()
    var _ns_osmoregulation_cost = Float64(_t1_osmoregulation_cost - _t0_osmoregulation_cost) / Float64(N)
    print("MOJO_TIMING ecophysiology::osmoregulation_cost", _ns_osmoregulation_cost, _acc_osmoregulation_cost)
    var _result_osmoregulation_cost = osmoregulation_cost(0.5, 0.5, 0.5)
    var _summary_osmoregulation_cost = _summary_float64(_result_osmoregulation_cost)
    print("MOJO_RESULT ecophysiology::osmoregulation_cost", _summary_osmoregulation_cost)
    var _acc_heart_rate_fick: Float64 = 0.0
    var _t0_heart_rate_fick = perf_counter_ns()
    for _ in range(N):
        _acc_heart_rate_fick += heart_rate_fick(0.5, 0.5, 0.5)
    var _t1_heart_rate_fick = perf_counter_ns()
    var _ns_heart_rate_fick = Float64(_t1_heart_rate_fick - _t0_heart_rate_fick) / Float64(N)
    print("MOJO_TIMING ecophysiology::heart_rate_fick", _ns_heart_rate_fick, _acc_heart_rate_fick)
    var _result_heart_rate_fick = heart_rate_fick(0.5, 0.5, 0.5)
    var _summary_heart_rate_fick = _summary_float64(_result_heart_rate_fick)
    print("MOJO_RESULT ecophysiology::heart_rate_fick", _summary_heart_rate_fick)
    var _acc_oxygen_consumption_rate: Float64 = 0.0
    var _t0_oxygen_consumption_rate = perf_counter_ns()
    for _ in range(N):
        _acc_oxygen_consumption_rate += oxygen_consumption_rate(0.5, 0.5, 0.5)
    var _t1_oxygen_consumption_rate = perf_counter_ns()
    var _ns_oxygen_consumption_rate = Float64(_t1_oxygen_consumption_rate - _t0_oxygen_consumption_rate) / Float64(N)
    print("MOJO_TIMING ecophysiology::oxygen_consumption_rate", _ns_oxygen_consumption_rate, _acc_oxygen_consumption_rate)
    var _result_oxygen_consumption_rate = oxygen_consumption_rate(0.5, 0.5, 0.5)
    var _summary_oxygen_consumption_rate = _summary_float64(_result_oxygen_consumption_rate)
    print("MOJO_RESULT ecophysiology::oxygen_consumption_rate", _summary_oxygen_consumption_rate)
    var _acc_field_metabolic_rate: Float64 = 0.0
    var _t0_field_metabolic_rate = perf_counter_ns()
    for _ in range(N):
        _acc_field_metabolic_rate += field_metabolic_rate(0.5, 0.5, 0.5)
    var _t1_field_metabolic_rate = perf_counter_ns()
    var _ns_field_metabolic_rate = Float64(_t1_field_metabolic_rate - _t0_field_metabolic_rate) / Float64(N)
    print("MOJO_TIMING ecophysiology::field_metabolic_rate", _ns_field_metabolic_rate, _acc_field_metabolic_rate)
    var _result_field_metabolic_rate = field_metabolic_rate(0.5, 0.5, 0.5)
    var _summary_field_metabolic_rate = _summary_float64(_result_field_metabolic_rate)
    print("MOJO_RESULT ecophysiology::field_metabolic_rate", _summary_field_metabolic_rate)
