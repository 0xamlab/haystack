"""bench_greenhouse.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from greenhouse import heat_loss_conduction, ventilation_rate, solar_gain, heating_requirement, co2_enrichment_rate, light_supplementation_hours, irrigation_volume, growing_area_utilization, energy_cost_heating, yield_per_sq_meter, temperature_setpoint_night, shade_factor
from std.time import perf_counter_ns

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
    var _acc_ventilation_rate: Float64 = 0.0
    var _t0_ventilation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_ventilation_rate += ventilation_rate(0.5, 0.5)
    var _t1_ventilation_rate = perf_counter_ns()
    var _ns_ventilation_rate = Float64(_t1_ventilation_rate - _t0_ventilation_rate) / Float64(N)
    print("MOJO_TIMING greenhouse::ventilation_rate", _ns_ventilation_rate, _acc_ventilation_rate)
    var _acc_solar_gain: Float64 = 0.0
    var _t0_solar_gain = perf_counter_ns()
    for _ in range(N):
        _acc_solar_gain += solar_gain(0.5, 0.5, 0.5)
    var _t1_solar_gain = perf_counter_ns()
    var _ns_solar_gain = Float64(_t1_solar_gain - _t0_solar_gain) / Float64(N)
    print("MOJO_TIMING greenhouse::solar_gain", _ns_solar_gain, _acc_solar_gain)
    var _acc_heating_requirement: Float64 = 0.0
    var _t0_heating_requirement = perf_counter_ns()
    for _ in range(N):
        _acc_heating_requirement += heating_requirement(0.5, 0.5)
    var _t1_heating_requirement = perf_counter_ns()
    var _ns_heating_requirement = Float64(_t1_heating_requirement - _t0_heating_requirement) / Float64(N)
    print("MOJO_TIMING greenhouse::heating_requirement", _ns_heating_requirement, _acc_heating_requirement)
    var _acc_co2_enrichment_rate: Float64 = 0.0
    var _t0_co2_enrichment_rate = perf_counter_ns()
    for _ in range(N):
        _acc_co2_enrichment_rate += co2_enrichment_rate(0.5, 0.5, 0.5, 0.5)
    var _t1_co2_enrichment_rate = perf_counter_ns()
    var _ns_co2_enrichment_rate = Float64(_t1_co2_enrichment_rate - _t0_co2_enrichment_rate) / Float64(N)
    print("MOJO_TIMING greenhouse::co2_enrichment_rate", _ns_co2_enrichment_rate, _acc_co2_enrichment_rate)
    var _acc_light_supplementation_hours: Float64 = 0.0
    var _t0_light_supplementation_hours = perf_counter_ns()
    for _ in range(N):
        _acc_light_supplementation_hours += light_supplementation_hours(0.5, 0.5, 0.5)
    var _t1_light_supplementation_hours = perf_counter_ns()
    var _ns_light_supplementation_hours = Float64(_t1_light_supplementation_hours - _t0_light_supplementation_hours) / Float64(N)
    print("MOJO_TIMING greenhouse::light_supplementation_hours", _ns_light_supplementation_hours, _acc_light_supplementation_hours)
    var _acc_irrigation_volume: Float64 = 0.0
    var _t0_irrigation_volume = perf_counter_ns()
    for _ in range(N):
        _acc_irrigation_volume += irrigation_volume(0.5, 0.5, 0.5)
    var _t1_irrigation_volume = perf_counter_ns()
    var _ns_irrigation_volume = Float64(_t1_irrigation_volume - _t0_irrigation_volume) / Float64(N)
    print("MOJO_TIMING greenhouse::irrigation_volume", _ns_irrigation_volume, _acc_irrigation_volume)
    var _acc_growing_area_utilization: Float64 = 0.0
    var _t0_growing_area_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_growing_area_utilization += growing_area_utilization(0.5, 0.5)
    var _t1_growing_area_utilization = perf_counter_ns()
    var _ns_growing_area_utilization = Float64(_t1_growing_area_utilization - _t0_growing_area_utilization) / Float64(N)
    print("MOJO_TIMING greenhouse::growing_area_utilization", _ns_growing_area_utilization, _acc_growing_area_utilization)
    var _acc_energy_cost_heating: Float64 = 0.0
    var _t0_energy_cost_heating = perf_counter_ns()
    for _ in range(N):
        _acc_energy_cost_heating += energy_cost_heating(0.5, 0.5)
    var _t1_energy_cost_heating = perf_counter_ns()
    var _ns_energy_cost_heating = Float64(_t1_energy_cost_heating - _t0_energy_cost_heating) / Float64(N)
    print("MOJO_TIMING greenhouse::energy_cost_heating", _ns_energy_cost_heating, _acc_energy_cost_heating)
    var _acc_yield_per_sq_meter: Float64 = 0.0
    var _t0_yield_per_sq_meter = perf_counter_ns()
    for _ in range(N):
        _acc_yield_per_sq_meter += yield_per_sq_meter(0.5, 0.5)
    var _t1_yield_per_sq_meter = perf_counter_ns()
    var _ns_yield_per_sq_meter = Float64(_t1_yield_per_sq_meter - _t0_yield_per_sq_meter) / Float64(N)
    print("MOJO_TIMING greenhouse::yield_per_sq_meter", _ns_yield_per_sq_meter, _acc_yield_per_sq_meter)
    var _acc_temperature_setpoint_night: Float64 = 0.0
    var _t0_temperature_setpoint_night = perf_counter_ns()
    for _ in range(N):
        _acc_temperature_setpoint_night += temperature_setpoint_night(0.5, 0.5)
    var _t1_temperature_setpoint_night = perf_counter_ns()
    var _ns_temperature_setpoint_night = Float64(_t1_temperature_setpoint_night - _t0_temperature_setpoint_night) / Float64(N)
    print("MOJO_TIMING greenhouse::temperature_setpoint_night", _ns_temperature_setpoint_night, _acc_temperature_setpoint_night)
    var _acc_shade_factor: Float64 = 0.0
    var _t0_shade_factor = perf_counter_ns()
    for _ in range(N):
        _acc_shade_factor += shade_factor(0.5)
    var _t1_shade_factor = perf_counter_ns()
    var _ns_shade_factor = Float64(_t1_shade_factor - _t0_shade_factor) / Float64(N)
    print("MOJO_TIMING greenhouse::shade_factor", _ns_shade_factor, _acc_shade_factor)
