"""bench_sustainability.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from sustainability import carbon_footprint_transport, energy_intensity, water_intensity, waste_diversion_rate, renewable_energy_fraction, ghg_scope1, ghg_scope2, ghg_scope3_estimate, carbon_offset_cost, circular_economy_index, social_return_on_investment, esg_composite_score
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

    var _acc_carbon_footprint_transport: Float64 = 0.0
    var _t0_carbon_footprint_transport = perf_counter_ns()
    for _ in range(N):
        _acc_carbon_footprint_transport += carbon_footprint_transport(0.5, 0.5)
    var _t1_carbon_footprint_transport = perf_counter_ns()
    var _ns_carbon_footprint_transport = Float64(_t1_carbon_footprint_transport - _t0_carbon_footprint_transport) / Float64(N)
    print("MOJO_TIMING sustainability::carbon_footprint_transport", _ns_carbon_footprint_transport, _acc_carbon_footprint_transport)
    var _result_carbon_footprint_transport = carbon_footprint_transport(0.5, 0.5)
    var _summary_carbon_footprint_transport = _summary_float64(_result_carbon_footprint_transport)
    print("MOJO_RESULT sustainability::carbon_footprint_transport", _summary_carbon_footprint_transport)
    var _acc_energy_intensity: Float64 = 0.0
    var _t0_energy_intensity = perf_counter_ns()
    for _ in range(N):
        _acc_energy_intensity += energy_intensity(0.5, 0.5)
    var _t1_energy_intensity = perf_counter_ns()
    var _ns_energy_intensity = Float64(_t1_energy_intensity - _t0_energy_intensity) / Float64(N)
    print("MOJO_TIMING sustainability::energy_intensity", _ns_energy_intensity, _acc_energy_intensity)
    var _result_energy_intensity = energy_intensity(0.5, 0.5)
    var _summary_energy_intensity = _summary_float64(_result_energy_intensity)
    print("MOJO_RESULT sustainability::energy_intensity", _summary_energy_intensity)
    var _acc_water_intensity: Float64 = 0.0
    var _t0_water_intensity = perf_counter_ns()
    for _ in range(N):
        _acc_water_intensity += water_intensity(0.5, 0.5)
    var _t1_water_intensity = perf_counter_ns()
    var _ns_water_intensity = Float64(_t1_water_intensity - _t0_water_intensity) / Float64(N)
    print("MOJO_TIMING sustainability::water_intensity", _ns_water_intensity, _acc_water_intensity)
    var _result_water_intensity = water_intensity(0.5, 0.5)
    var _summary_water_intensity = _summary_float64(_result_water_intensity)
    print("MOJO_RESULT sustainability::water_intensity", _summary_water_intensity)
    var _acc_waste_diversion_rate: Float64 = 0.0
    var _t0_waste_diversion_rate = perf_counter_ns()
    for _ in range(N):
        _acc_waste_diversion_rate += waste_diversion_rate(0.5, 0.5)
    var _t1_waste_diversion_rate = perf_counter_ns()
    var _ns_waste_diversion_rate = Float64(_t1_waste_diversion_rate - _t0_waste_diversion_rate) / Float64(N)
    print("MOJO_TIMING sustainability::waste_diversion_rate", _ns_waste_diversion_rate, _acc_waste_diversion_rate)
    var _result_waste_diversion_rate = waste_diversion_rate(0.5, 0.5)
    var _summary_waste_diversion_rate = _summary_float64(_result_waste_diversion_rate)
    print("MOJO_RESULT sustainability::waste_diversion_rate", _summary_waste_diversion_rate)
    var _acc_renewable_energy_fraction: Float64 = 0.0
    var _t0_renewable_energy_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_renewable_energy_fraction += renewable_energy_fraction(0.5, 0.5)
    var _t1_renewable_energy_fraction = perf_counter_ns()
    var _ns_renewable_energy_fraction = Float64(_t1_renewable_energy_fraction - _t0_renewable_energy_fraction) / Float64(N)
    print("MOJO_TIMING sustainability::renewable_energy_fraction", _ns_renewable_energy_fraction, _acc_renewable_energy_fraction)
    var _result_renewable_energy_fraction = renewable_energy_fraction(0.5, 0.5)
    var _summary_renewable_energy_fraction = _summary_float64(_result_renewable_energy_fraction)
    print("MOJO_RESULT sustainability::renewable_energy_fraction", _summary_renewable_energy_fraction)
    var _acc_ghg_scope1: Float64 = 0.0
    var _t0_ghg_scope1 = perf_counter_ns()
    for _ in range(N):
        _acc_ghg_scope1 += ghg_scope1(0.5)
    var _t1_ghg_scope1 = perf_counter_ns()
    var _ns_ghg_scope1 = Float64(_t1_ghg_scope1 - _t0_ghg_scope1) / Float64(N)
    print("MOJO_TIMING sustainability::ghg_scope1", _ns_ghg_scope1, _acc_ghg_scope1)
    var _result_ghg_scope1 = ghg_scope1(0.5)
    var _summary_ghg_scope1 = _summary_float64(_result_ghg_scope1)
    print("MOJO_RESULT sustainability::ghg_scope1", _summary_ghg_scope1)
    var _acc_ghg_scope2: Float64 = 0.0
    var _t0_ghg_scope2 = perf_counter_ns()
    for _ in range(N):
        _acc_ghg_scope2 += ghg_scope2(0.5, 0.5)
    var _t1_ghg_scope2 = perf_counter_ns()
    var _ns_ghg_scope2 = Float64(_t1_ghg_scope2 - _t0_ghg_scope2) / Float64(N)
    print("MOJO_TIMING sustainability::ghg_scope2", _ns_ghg_scope2, _acc_ghg_scope2)
    var _result_ghg_scope2 = ghg_scope2(0.5, 0.5)
    var _summary_ghg_scope2 = _summary_float64(_result_ghg_scope2)
    print("MOJO_RESULT sustainability::ghg_scope2", _summary_ghg_scope2)
    var _acc_ghg_scope3_estimate: Float64 = 0.0
    var _t0_ghg_scope3_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_ghg_scope3_estimate += ghg_scope3_estimate(0.5, 0.5)
    var _t1_ghg_scope3_estimate = perf_counter_ns()
    var _ns_ghg_scope3_estimate = Float64(_t1_ghg_scope3_estimate - _t0_ghg_scope3_estimate) / Float64(N)
    print("MOJO_TIMING sustainability::ghg_scope3_estimate", _ns_ghg_scope3_estimate, _acc_ghg_scope3_estimate)
    var _result_ghg_scope3_estimate = ghg_scope3_estimate(0.5, 0.5)
    var _summary_ghg_scope3_estimate = _summary_float64(_result_ghg_scope3_estimate)
    print("MOJO_RESULT sustainability::ghg_scope3_estimate", _summary_ghg_scope3_estimate)
    var _acc_carbon_offset_cost: Float64 = 0.0
    var _t0_carbon_offset_cost = perf_counter_ns()
    for _ in range(N):
        _acc_carbon_offset_cost += carbon_offset_cost(0.5, 0.5)
    var _t1_carbon_offset_cost = perf_counter_ns()
    var _ns_carbon_offset_cost = Float64(_t1_carbon_offset_cost - _t0_carbon_offset_cost) / Float64(N)
    print("MOJO_TIMING sustainability::carbon_offset_cost", _ns_carbon_offset_cost, _acc_carbon_offset_cost)
    var _result_carbon_offset_cost = carbon_offset_cost(0.5, 0.5)
    var _summary_carbon_offset_cost = _summary_float64(_result_carbon_offset_cost)
    print("MOJO_RESULT sustainability::carbon_offset_cost", _summary_carbon_offset_cost)
    var _acc_circular_economy_index: Float64 = 0.0
    var _t0_circular_economy_index = perf_counter_ns()
    for _ in range(N):
        _acc_circular_economy_index += circular_economy_index(0.5, 0.5)
    var _t1_circular_economy_index = perf_counter_ns()
    var _ns_circular_economy_index = Float64(_t1_circular_economy_index - _t0_circular_economy_index) / Float64(N)
    print("MOJO_TIMING sustainability::circular_economy_index", _ns_circular_economy_index, _acc_circular_economy_index)
    var _result_circular_economy_index = circular_economy_index(0.5, 0.5)
    var _summary_circular_economy_index = _summary_float64(_result_circular_economy_index)
    print("MOJO_RESULT sustainability::circular_economy_index", _summary_circular_economy_index)
    var _acc_social_return_on_investment: Float64 = 0.0
    var _t0_social_return_on_investment = perf_counter_ns()
    for _ in range(N):
        _acc_social_return_on_investment += social_return_on_investment(0.5, 0.5)
    var _t1_social_return_on_investment = perf_counter_ns()
    var _ns_social_return_on_investment = Float64(_t1_social_return_on_investment - _t0_social_return_on_investment) / Float64(N)
    print("MOJO_TIMING sustainability::social_return_on_investment", _ns_social_return_on_investment, _acc_social_return_on_investment)
    var _result_social_return_on_investment = social_return_on_investment(0.5, 0.5)
    var _summary_social_return_on_investment = _summary_float64(_result_social_return_on_investment)
    print("MOJO_RESULT sustainability::social_return_on_investment", _summary_social_return_on_investment)
    var _acc_esg_composite_score: Float64 = 0.0
    var _t0_esg_composite_score = perf_counter_ns()
    for _ in range(N):
        _acc_esg_composite_score += esg_composite_score(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_esg_composite_score = perf_counter_ns()
    var _ns_esg_composite_score = Float64(_t1_esg_composite_score - _t0_esg_composite_score) / Float64(N)
    print("MOJO_TIMING sustainability::esg_composite_score", _ns_esg_composite_score, _acc_esg_composite_score)
    var _result_esg_composite_score = esg_composite_score(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_esg_composite_score = _summary_float64(_result_esg_composite_score)
    print("MOJO_RESULT sustainability::esg_composite_score", _summary_esg_composite_score)
