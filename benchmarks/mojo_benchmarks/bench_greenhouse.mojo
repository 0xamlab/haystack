"""bench_greenhouse.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from greenhouse import heat_loss_conduction, ventilation_rate, solar_gain, heating_requirement, co2_enrichment_rate, light_supplementation_hours, irrigation_volume, growing_area_utilization, energy_cost_heating, yield_per_sq_meter, temperature_setpoint_night, shade_factor
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

    var _acc_heat_loss_conduction: Float64 = 0.0
    var _t0_heat_loss_conduction = perf_counter_ns()
    for _ in range(N):
        _acc_heat_loss_conduction += heat_loss_conduction(0.5, 0.5, 0.5)
    var _t1_heat_loss_conduction = perf_counter_ns()
    var _ns_heat_loss_conduction = Float64(_t1_heat_loss_conduction - _t0_heat_loss_conduction) / Float64(N)
    print("MOJO_TIMING greenhouse::heat_loss_conduction", _ns_heat_loss_conduction, _acc_heat_loss_conduction)
    var _result_heat_loss_conduction = heat_loss_conduction(0.5, 0.5, 0.5)
    var _summary_heat_loss_conduction = _summary_float64(_result_heat_loss_conduction)
    print("MOJO_RESULT greenhouse::heat_loss_conduction", _summary_heat_loss_conduction)
    var _acc_ventilation_rate: Float64 = 0.0
    var _t0_ventilation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_ventilation_rate += ventilation_rate(0.5, 0.5)
    var _t1_ventilation_rate = perf_counter_ns()
    var _ns_ventilation_rate = Float64(_t1_ventilation_rate - _t0_ventilation_rate) / Float64(N)
    print("MOJO_TIMING greenhouse::ventilation_rate", _ns_ventilation_rate, _acc_ventilation_rate)
    var _result_ventilation_rate = ventilation_rate(0.5, 0.5)
    var _summary_ventilation_rate = _summary_float64(_result_ventilation_rate)
    print("MOJO_RESULT greenhouse::ventilation_rate", _summary_ventilation_rate)
    var _acc_solar_gain: Float64 = 0.0
    var _t0_solar_gain = perf_counter_ns()
    for _ in range(N):
        _acc_solar_gain += solar_gain(0.5, 0.5, 0.5)
    var _t1_solar_gain = perf_counter_ns()
    var _ns_solar_gain = Float64(_t1_solar_gain - _t0_solar_gain) / Float64(N)
    print("MOJO_TIMING greenhouse::solar_gain", _ns_solar_gain, _acc_solar_gain)
    var _result_solar_gain = solar_gain(0.5, 0.5, 0.5)
    var _summary_solar_gain = _summary_float64(_result_solar_gain)
    print("MOJO_RESULT greenhouse::solar_gain", _summary_solar_gain)
    var _acc_heating_requirement: Float64 = 0.0
    var _t0_heating_requirement = perf_counter_ns()
    for _ in range(N):
        _acc_heating_requirement += heating_requirement(0.5, 0.5)
    var _t1_heating_requirement = perf_counter_ns()
    var _ns_heating_requirement = Float64(_t1_heating_requirement - _t0_heating_requirement) / Float64(N)
    print("MOJO_TIMING greenhouse::heating_requirement", _ns_heating_requirement, _acc_heating_requirement)
    var _result_heating_requirement = heating_requirement(0.5, 0.5)
    var _summary_heating_requirement = _summary_float64(_result_heating_requirement)
    print("MOJO_RESULT greenhouse::heating_requirement", _summary_heating_requirement)
    var _acc_co2_enrichment_rate: Float64 = 0.0
    var _t0_co2_enrichment_rate = perf_counter_ns()
    for _ in range(N):
        _acc_co2_enrichment_rate += co2_enrichment_rate(0.5, 0.5, 0.5, 0.5)
    var _t1_co2_enrichment_rate = perf_counter_ns()
    var _ns_co2_enrichment_rate = Float64(_t1_co2_enrichment_rate - _t0_co2_enrichment_rate) / Float64(N)
    print("MOJO_TIMING greenhouse::co2_enrichment_rate", _ns_co2_enrichment_rate, _acc_co2_enrichment_rate)
    var _result_co2_enrichment_rate = co2_enrichment_rate(0.5, 0.5, 0.5, 0.5)
    var _summary_co2_enrichment_rate = _summary_float64(_result_co2_enrichment_rate)
    print("MOJO_RESULT greenhouse::co2_enrichment_rate", _summary_co2_enrichment_rate)
    var _acc_light_supplementation_hours: Float64 = 0.0
    var _t0_light_supplementation_hours = perf_counter_ns()
    for _ in range(N):
        _acc_light_supplementation_hours += light_supplementation_hours(0.5, 0.5, 0.5)
    var _t1_light_supplementation_hours = perf_counter_ns()
    var _ns_light_supplementation_hours = Float64(_t1_light_supplementation_hours - _t0_light_supplementation_hours) / Float64(N)
    print("MOJO_TIMING greenhouse::light_supplementation_hours", _ns_light_supplementation_hours, _acc_light_supplementation_hours)
    var _result_light_supplementation_hours = light_supplementation_hours(0.5, 0.5, 0.5)
    var _summary_light_supplementation_hours = _summary_float64(_result_light_supplementation_hours)
    print("MOJO_RESULT greenhouse::light_supplementation_hours", _summary_light_supplementation_hours)
    var _acc_irrigation_volume: Float64 = 0.0
    var _t0_irrigation_volume = perf_counter_ns()
    for _ in range(N):
        _acc_irrigation_volume += irrigation_volume(0.5, 0.5, 0.5)
    var _t1_irrigation_volume = perf_counter_ns()
    var _ns_irrigation_volume = Float64(_t1_irrigation_volume - _t0_irrigation_volume) / Float64(N)
    print("MOJO_TIMING greenhouse::irrigation_volume", _ns_irrigation_volume, _acc_irrigation_volume)
    var _result_irrigation_volume = irrigation_volume(0.5, 0.5, 0.5)
    var _summary_irrigation_volume = _summary_float64(_result_irrigation_volume)
    print("MOJO_RESULT greenhouse::irrigation_volume", _summary_irrigation_volume)
    var _acc_growing_area_utilization: Float64 = 0.0
    var _t0_growing_area_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_growing_area_utilization += growing_area_utilization(0.5, 0.5)
    var _t1_growing_area_utilization = perf_counter_ns()
    var _ns_growing_area_utilization = Float64(_t1_growing_area_utilization - _t0_growing_area_utilization) / Float64(N)
    print("MOJO_TIMING greenhouse::growing_area_utilization", _ns_growing_area_utilization, _acc_growing_area_utilization)
    var _result_growing_area_utilization = growing_area_utilization(0.5, 0.5)
    var _summary_growing_area_utilization = _summary_float64(_result_growing_area_utilization)
    print("MOJO_RESULT greenhouse::growing_area_utilization", _summary_growing_area_utilization)
    var _acc_energy_cost_heating: Float64 = 0.0
    var _t0_energy_cost_heating = perf_counter_ns()
    for _ in range(N):
        _acc_energy_cost_heating += energy_cost_heating(0.5, 0.5)
    var _t1_energy_cost_heating = perf_counter_ns()
    var _ns_energy_cost_heating = Float64(_t1_energy_cost_heating - _t0_energy_cost_heating) / Float64(N)
    print("MOJO_TIMING greenhouse::energy_cost_heating", _ns_energy_cost_heating, _acc_energy_cost_heating)
    var _result_energy_cost_heating = energy_cost_heating(0.5, 0.5)
    var _summary_energy_cost_heating = _summary_float64(_result_energy_cost_heating)
    print("MOJO_RESULT greenhouse::energy_cost_heating", _summary_energy_cost_heating)
    var _acc_yield_per_sq_meter: Float64 = 0.0
    var _t0_yield_per_sq_meter = perf_counter_ns()
    for _ in range(N):
        _acc_yield_per_sq_meter += yield_per_sq_meter(0.5, 0.5)
    var _t1_yield_per_sq_meter = perf_counter_ns()
    var _ns_yield_per_sq_meter = Float64(_t1_yield_per_sq_meter - _t0_yield_per_sq_meter) / Float64(N)
    print("MOJO_TIMING greenhouse::yield_per_sq_meter", _ns_yield_per_sq_meter, _acc_yield_per_sq_meter)
    var _result_yield_per_sq_meter = yield_per_sq_meter(0.5, 0.5)
    var _summary_yield_per_sq_meter = _summary_float64(_result_yield_per_sq_meter)
    print("MOJO_RESULT greenhouse::yield_per_sq_meter", _summary_yield_per_sq_meter)
    var _acc_temperature_setpoint_night: Float64 = 0.0
    var _t0_temperature_setpoint_night = perf_counter_ns()
    for _ in range(N):
        _acc_temperature_setpoint_night += temperature_setpoint_night(0.5, 0.5)
    var _t1_temperature_setpoint_night = perf_counter_ns()
    var _ns_temperature_setpoint_night = Float64(_t1_temperature_setpoint_night - _t0_temperature_setpoint_night) / Float64(N)
    print("MOJO_TIMING greenhouse::temperature_setpoint_night", _ns_temperature_setpoint_night, _acc_temperature_setpoint_night)
    var _result_temperature_setpoint_night = temperature_setpoint_night(0.5, 0.5)
    var _summary_temperature_setpoint_night = _summary_float64(_result_temperature_setpoint_night)
    print("MOJO_RESULT greenhouse::temperature_setpoint_night", _summary_temperature_setpoint_night)
    var _acc_shade_factor: Float64 = 0.0
    var _t0_shade_factor = perf_counter_ns()
    for _ in range(N):
        _acc_shade_factor += shade_factor(0.5)
    var _t1_shade_factor = perf_counter_ns()
    var _ns_shade_factor = Float64(_t1_shade_factor - _t0_shade_factor) / Float64(N)
    print("MOJO_TIMING greenhouse::shade_factor", _ns_shade_factor, _acc_shade_factor)
    var _result_shade_factor = shade_factor(0.5)
    var _summary_shade_factor = _summary_float64(_result_shade_factor)
    print("MOJO_RESULT greenhouse::shade_factor", _summary_shade_factor)
