"""bench_hydrogeology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from hydrogeology import darcy_velocity, transmissivity, storativity, theis_drawdown, dupuit_discharge, hydraulic_gradient, specific_yield, capillary_rise_height, leakance_factor, groundwater_age_mixing
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

    var _acc_darcy_velocity: Float64 = 0.0
    var _t0_darcy_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_darcy_velocity += darcy_velocity(0.5, 0.5)
    var _t1_darcy_velocity = perf_counter_ns()
    var _ns_darcy_velocity = Float64(_t1_darcy_velocity - _t0_darcy_velocity) / Float64(N)
    print("MOJO_TIMING hydrogeology::darcy_velocity", _ns_darcy_velocity, _acc_darcy_velocity)
    var _result_darcy_velocity = darcy_velocity(0.5, 0.5)
    var _summary_darcy_velocity = _summary_float64(_result_darcy_velocity)
    print("MOJO_RESULT hydrogeology::darcy_velocity", _summary_darcy_velocity)
    var _acc_transmissivity: Float64 = 0.0
    var _t0_transmissivity = perf_counter_ns()
    for _ in range(N):
        _acc_transmissivity += transmissivity(0.5, 0.5)
    var _t1_transmissivity = perf_counter_ns()
    var _ns_transmissivity = Float64(_t1_transmissivity - _t0_transmissivity) / Float64(N)
    print("MOJO_TIMING hydrogeology::transmissivity", _ns_transmissivity, _acc_transmissivity)
    var _result_transmissivity = transmissivity(0.5, 0.5)
    var _summary_transmissivity = _summary_float64(_result_transmissivity)
    print("MOJO_RESULT hydrogeology::transmissivity", _summary_transmissivity)
    var _acc_storativity: Float64 = 0.0
    var _t0_storativity = perf_counter_ns()
    for _ in range(N):
        _acc_storativity += storativity(0.5, 0.5)
    var _t1_storativity = perf_counter_ns()
    var _ns_storativity = Float64(_t1_storativity - _t0_storativity) / Float64(N)
    print("MOJO_TIMING hydrogeology::storativity", _ns_storativity, _acc_storativity)
    var _result_storativity = storativity(0.5, 0.5)
    var _summary_storativity = _summary_float64(_result_storativity)
    print("MOJO_RESULT hydrogeology::storativity", _summary_storativity)
    var _acc_theis_drawdown: Float64 = 0.0
    var _t0_theis_drawdown = perf_counter_ns()
    for _ in range(N):
        _acc_theis_drawdown += theis_drawdown(0.5, 0.5, 0.5)
    var _t1_theis_drawdown = perf_counter_ns()
    var _ns_theis_drawdown = Float64(_t1_theis_drawdown - _t0_theis_drawdown) / Float64(N)
    print("MOJO_TIMING hydrogeology::theis_drawdown", _ns_theis_drawdown, _acc_theis_drawdown)
    var _result_theis_drawdown = theis_drawdown(0.5, 0.5, 0.5)
    var _summary_theis_drawdown = _summary_float64(_result_theis_drawdown)
    print("MOJO_RESULT hydrogeology::theis_drawdown", _summary_theis_drawdown)
    var _acc_dupuit_discharge: Float64 = 0.0
    var _t0_dupuit_discharge = perf_counter_ns()
    for _ in range(N):
        _acc_dupuit_discharge += dupuit_discharge(0.5, 0.5, 0.5, 0.5)
    var _t1_dupuit_discharge = perf_counter_ns()
    var _ns_dupuit_discharge = Float64(_t1_dupuit_discharge - _t0_dupuit_discharge) / Float64(N)
    print("MOJO_TIMING hydrogeology::dupuit_discharge", _ns_dupuit_discharge, _acc_dupuit_discharge)
    var _result_dupuit_discharge = dupuit_discharge(0.5, 0.5, 0.5, 0.5)
    var _summary_dupuit_discharge = _summary_float64(_result_dupuit_discharge)
    print("MOJO_RESULT hydrogeology::dupuit_discharge", _summary_dupuit_discharge)
    var _acc_hydraulic_gradient: Float64 = 0.0
    var _t0_hydraulic_gradient = perf_counter_ns()
    for _ in range(N):
        _acc_hydraulic_gradient += hydraulic_gradient(0.5, 0.5)
    var _t1_hydraulic_gradient = perf_counter_ns()
    var _ns_hydraulic_gradient = Float64(_t1_hydraulic_gradient - _t0_hydraulic_gradient) / Float64(N)
    print("MOJO_TIMING hydrogeology::hydraulic_gradient", _ns_hydraulic_gradient, _acc_hydraulic_gradient)
    var _result_hydraulic_gradient = hydraulic_gradient(0.5, 0.5)
    var _summary_hydraulic_gradient = _summary_float64(_result_hydraulic_gradient)
    print("MOJO_RESULT hydrogeology::hydraulic_gradient", _summary_hydraulic_gradient)
    var _acc_specific_yield: Float64 = 0.0
    var _t0_specific_yield = perf_counter_ns()
    for _ in range(N):
        _acc_specific_yield += specific_yield(0.5, 0.5)
    var _t1_specific_yield = perf_counter_ns()
    var _ns_specific_yield = Float64(_t1_specific_yield - _t0_specific_yield) / Float64(N)
    print("MOJO_TIMING hydrogeology::specific_yield", _ns_specific_yield, _acc_specific_yield)
    var _result_specific_yield = specific_yield(0.5, 0.5)
    var _summary_specific_yield = _summary_float64(_result_specific_yield)
    print("MOJO_RESULT hydrogeology::specific_yield", _summary_specific_yield)
    var _acc_capillary_rise_height: Float64 = 0.0
    var _t0_capillary_rise_height = perf_counter_ns()
    for _ in range(N):
        _acc_capillary_rise_height += capillary_rise_height(0.5, 0.5, 0.5, 0.5)
    var _t1_capillary_rise_height = perf_counter_ns()
    var _ns_capillary_rise_height = Float64(_t1_capillary_rise_height - _t0_capillary_rise_height) / Float64(N)
    print("MOJO_TIMING hydrogeology::capillary_rise_height", _ns_capillary_rise_height, _acc_capillary_rise_height)
    var _result_capillary_rise_height = capillary_rise_height(0.5, 0.5, 0.5, 0.5)
    var _summary_capillary_rise_height = _summary_float64(_result_capillary_rise_height)
    print("MOJO_RESULT hydrogeology::capillary_rise_height", _summary_capillary_rise_height)
    var _acc_leakance_factor: Float64 = 0.0
    var _t0_leakance_factor = perf_counter_ns()
    for _ in range(N):
        _acc_leakance_factor += leakance_factor(0.5, 0.5, 0.5)
    var _t1_leakance_factor = perf_counter_ns()
    var _ns_leakance_factor = Float64(_t1_leakance_factor - _t0_leakance_factor) / Float64(N)
    print("MOJO_TIMING hydrogeology::leakance_factor", _ns_leakance_factor, _acc_leakance_factor)
    var _result_leakance_factor = leakance_factor(0.5, 0.5, 0.5)
    var _summary_leakance_factor = _summary_float64(_result_leakance_factor)
    print("MOJO_RESULT hydrogeology::leakance_factor", _summary_leakance_factor)
    var _acc_groundwater_age_mixing: Float64 = 0.0
    var _t0_groundwater_age_mixing = perf_counter_ns()
    for _ in range(N):
        _acc_groundwater_age_mixing += groundwater_age_mixing(0.5, 0.5, 0.5)
    var _t1_groundwater_age_mixing = perf_counter_ns()
    var _ns_groundwater_age_mixing = Float64(_t1_groundwater_age_mixing - _t0_groundwater_age_mixing) / Float64(N)
    print("MOJO_TIMING hydrogeology::groundwater_age_mixing", _ns_groundwater_age_mixing, _acc_groundwater_age_mixing)
    var _result_groundwater_age_mixing = groundwater_age_mixing(0.5, 0.5, 0.5)
    var _summary_groundwater_age_mixing = _summary_float64(_result_groundwater_age_mixing)
    print("MOJO_RESULT hydrogeology::groundwater_age_mixing", _summary_groundwater_age_mixing)
