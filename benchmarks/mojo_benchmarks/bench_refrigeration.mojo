"""bench_refrigeration.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from refrigeration import cop_refrigeration, cop_heat_pump, carnot_cop_refrigeration, carnot_cop_heat_pump, refrigeration_capacity_tons, superheat, subcooling, mass_flow_rate, compressor_work, energy_efficiency_ratio, seer_to_cop, refrigerant_charge_estimate
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

    var _acc_cop_refrigeration: Float64 = 0.0
    var _t0_cop_refrigeration = perf_counter_ns()
    for _ in range(N):
        _acc_cop_refrigeration += cop_refrigeration(0.5, 0.5)
    var _t1_cop_refrigeration = perf_counter_ns()
    var _ns_cop_refrigeration = Float64(_t1_cop_refrigeration - _t0_cop_refrigeration) / Float64(N)
    print("MOJO_TIMING refrigeration::cop_refrigeration", _ns_cop_refrigeration, _acc_cop_refrigeration)
    var _result_cop_refrigeration = cop_refrigeration(0.5, 0.5)
    var _summary_cop_refrigeration = _summary_float64(_result_cop_refrigeration)
    print("MOJO_RESULT refrigeration::cop_refrigeration", _summary_cop_refrigeration)
    var _acc_cop_heat_pump: Float64 = 0.0
    var _t0_cop_heat_pump = perf_counter_ns()
    for _ in range(N):
        _acc_cop_heat_pump += cop_heat_pump(0.5, 0.5)
    var _t1_cop_heat_pump = perf_counter_ns()
    var _ns_cop_heat_pump = Float64(_t1_cop_heat_pump - _t0_cop_heat_pump) / Float64(N)
    print("MOJO_TIMING refrigeration::cop_heat_pump", _ns_cop_heat_pump, _acc_cop_heat_pump)
    var _result_cop_heat_pump = cop_heat_pump(0.5, 0.5)
    var _summary_cop_heat_pump = _summary_float64(_result_cop_heat_pump)
    print("MOJO_RESULT refrigeration::cop_heat_pump", _summary_cop_heat_pump)
    var _acc_carnot_cop_refrigeration: Float64 = 0.0
    var _t0_carnot_cop_refrigeration = perf_counter_ns()
    for _ in range(N):
        _acc_carnot_cop_refrigeration += carnot_cop_refrigeration(0.5, 0.5)
    var _t1_carnot_cop_refrigeration = perf_counter_ns()
    var _ns_carnot_cop_refrigeration = Float64(_t1_carnot_cop_refrigeration - _t0_carnot_cop_refrigeration) / Float64(N)
    print("MOJO_TIMING refrigeration::carnot_cop_refrigeration", _ns_carnot_cop_refrigeration, _acc_carnot_cop_refrigeration)
    var _result_carnot_cop_refrigeration = carnot_cop_refrigeration(0.5, 0.5)
    var _summary_carnot_cop_refrigeration = _summary_float64(_result_carnot_cop_refrigeration)
    print("MOJO_RESULT refrigeration::carnot_cop_refrigeration", _summary_carnot_cop_refrigeration)
    var _acc_carnot_cop_heat_pump: Float64 = 0.0
    var _t0_carnot_cop_heat_pump = perf_counter_ns()
    for _ in range(N):
        _acc_carnot_cop_heat_pump += carnot_cop_heat_pump(0.5, 0.5)
    var _t1_carnot_cop_heat_pump = perf_counter_ns()
    var _ns_carnot_cop_heat_pump = Float64(_t1_carnot_cop_heat_pump - _t0_carnot_cop_heat_pump) / Float64(N)
    print("MOJO_TIMING refrigeration::carnot_cop_heat_pump", _ns_carnot_cop_heat_pump, _acc_carnot_cop_heat_pump)
    var _result_carnot_cop_heat_pump = carnot_cop_heat_pump(0.5, 0.5)
    var _summary_carnot_cop_heat_pump = _summary_float64(_result_carnot_cop_heat_pump)
    print("MOJO_RESULT refrigeration::carnot_cop_heat_pump", _summary_carnot_cop_heat_pump)
    var _acc_refrigeration_capacity_tons: Float64 = 0.0
    var _t0_refrigeration_capacity_tons = perf_counter_ns()
    for _ in range(N):
        _acc_refrigeration_capacity_tons += refrigeration_capacity_tons(0.5)
    var _t1_refrigeration_capacity_tons = perf_counter_ns()
    var _ns_refrigeration_capacity_tons = Float64(_t1_refrigeration_capacity_tons - _t0_refrigeration_capacity_tons) / Float64(N)
    print("MOJO_TIMING refrigeration::refrigeration_capacity_tons", _ns_refrigeration_capacity_tons, _acc_refrigeration_capacity_tons)
    var _result_refrigeration_capacity_tons = refrigeration_capacity_tons(0.5)
    var _summary_refrigeration_capacity_tons = _summary_float64(_result_refrigeration_capacity_tons)
    print("MOJO_RESULT refrigeration::refrigeration_capacity_tons", _summary_refrigeration_capacity_tons)
    var _acc_superheat: Float64 = 0.0
    var _t0_superheat = perf_counter_ns()
    for _ in range(N):
        _acc_superheat += superheat(0.5, 0.5)
    var _t1_superheat = perf_counter_ns()
    var _ns_superheat = Float64(_t1_superheat - _t0_superheat) / Float64(N)
    print("MOJO_TIMING refrigeration::superheat", _ns_superheat, _acc_superheat)
    var _result_superheat = superheat(0.5, 0.5)
    var _summary_superheat = _summary_float64(_result_superheat)
    print("MOJO_RESULT refrigeration::superheat", _summary_superheat)
    var _acc_subcooling: Float64 = 0.0
    var _t0_subcooling = perf_counter_ns()
    for _ in range(N):
        _acc_subcooling += subcooling(0.5, 0.5)
    var _t1_subcooling = perf_counter_ns()
    var _ns_subcooling = Float64(_t1_subcooling - _t0_subcooling) / Float64(N)
    print("MOJO_TIMING refrigeration::subcooling", _ns_subcooling, _acc_subcooling)
    var _result_subcooling = subcooling(0.5, 0.5)
    var _summary_subcooling = _summary_float64(_result_subcooling)
    print("MOJO_RESULT refrigeration::subcooling", _summary_subcooling)
    var _acc_mass_flow_rate: Float64 = 0.0
    var _t0_mass_flow_rate = perf_counter_ns()
    for _ in range(N):
        _acc_mass_flow_rate += mass_flow_rate(0.5, 0.5)
    var _t1_mass_flow_rate = perf_counter_ns()
    var _ns_mass_flow_rate = Float64(_t1_mass_flow_rate - _t0_mass_flow_rate) / Float64(N)
    print("MOJO_TIMING refrigeration::mass_flow_rate", _ns_mass_flow_rate, _acc_mass_flow_rate)
    var _result_mass_flow_rate = mass_flow_rate(0.5, 0.5)
    var _summary_mass_flow_rate = _summary_float64(_result_mass_flow_rate)
    print("MOJO_RESULT refrigeration::mass_flow_rate", _summary_mass_flow_rate)
    var _acc_compressor_work: Float64 = 0.0
    var _t0_compressor_work = perf_counter_ns()
    for _ in range(N):
        _acc_compressor_work += compressor_work(0.5, 0.5, 0.5)
    var _t1_compressor_work = perf_counter_ns()
    var _ns_compressor_work = Float64(_t1_compressor_work - _t0_compressor_work) / Float64(N)
    print("MOJO_TIMING refrigeration::compressor_work", _ns_compressor_work, _acc_compressor_work)
    var _result_compressor_work = compressor_work(0.5, 0.5, 0.5)
    var _summary_compressor_work = _summary_float64(_result_compressor_work)
    print("MOJO_RESULT refrigeration::compressor_work", _summary_compressor_work)
    var _acc_energy_efficiency_ratio: Float64 = 0.0
    var _t0_energy_efficiency_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_energy_efficiency_ratio += energy_efficiency_ratio(0.5, 0.5)
    var _t1_energy_efficiency_ratio = perf_counter_ns()
    var _ns_energy_efficiency_ratio = Float64(_t1_energy_efficiency_ratio - _t0_energy_efficiency_ratio) / Float64(N)
    print("MOJO_TIMING refrigeration::energy_efficiency_ratio", _ns_energy_efficiency_ratio, _acc_energy_efficiency_ratio)
    var _result_energy_efficiency_ratio = energy_efficiency_ratio(0.5, 0.5)
    var _summary_energy_efficiency_ratio = _summary_float64(_result_energy_efficiency_ratio)
    print("MOJO_RESULT refrigeration::energy_efficiency_ratio", _summary_energy_efficiency_ratio)
    var _acc_seer_to_cop: Float64 = 0.0
    var _t0_seer_to_cop = perf_counter_ns()
    for _ in range(N):
        _acc_seer_to_cop += seer_to_cop(0.5)
    var _t1_seer_to_cop = perf_counter_ns()
    var _ns_seer_to_cop = Float64(_t1_seer_to_cop - _t0_seer_to_cop) / Float64(N)
    print("MOJO_TIMING refrigeration::seer_to_cop", _ns_seer_to_cop, _acc_seer_to_cop)
    var _result_seer_to_cop = seer_to_cop(0.5)
    var _summary_seer_to_cop = _summary_float64(_result_seer_to_cop)
    print("MOJO_RESULT refrigeration::seer_to_cop", _summary_seer_to_cop)
    var _acc_refrigerant_charge_estimate: Float64 = 0.0
    var _t0_refrigerant_charge_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_refrigerant_charge_estimate += refrigerant_charge_estimate(0.5, 0.5)
    var _t1_refrigerant_charge_estimate = perf_counter_ns()
    var _ns_refrigerant_charge_estimate = Float64(_t1_refrigerant_charge_estimate - _t0_refrigerant_charge_estimate) / Float64(N)
    print("MOJO_TIMING refrigeration::refrigerant_charge_estimate", _ns_refrigerant_charge_estimate, _acc_refrigerant_charge_estimate)
    var _result_refrigerant_charge_estimate = refrigerant_charge_estimate(0.5, 0.5)
    var _summary_refrigerant_charge_estimate = _summary_float64(_result_refrigerant_charge_estimate)
    print("MOJO_RESULT refrigeration::refrigerant_charge_estimate", _summary_refrigerant_charge_estimate)
