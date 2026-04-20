"""bench_hydroponics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from hydroponics import ec_from_tds, tds_from_ec, nutrient_concentration, ph_adjustment_acid, light_daily_integral, vpd, water_consumption_rate, nutrient_uptake_rate, grow_light_efficiency, reservoir_dilution, yield_per_area, crop_cycle_roi
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

    var _acc_ec_from_tds: Float64 = 0.0
    var _t0_ec_from_tds = perf_counter_ns()
    for _ in range(N):
        _acc_ec_from_tds += ec_from_tds(0.5, 0.5)
    var _t1_ec_from_tds = perf_counter_ns()
    var _ns_ec_from_tds = Float64(_t1_ec_from_tds - _t0_ec_from_tds) / Float64(N)
    print("MOJO_TIMING hydroponics::ec_from_tds", _ns_ec_from_tds, _acc_ec_from_tds)
    var _acc_tds_from_ec: Float64 = 0.0
    var _t0_tds_from_ec = perf_counter_ns()
    for _ in range(N):
        _acc_tds_from_ec += tds_from_ec(0.5, 0.5)
    var _t1_tds_from_ec = perf_counter_ns()
    var _ns_tds_from_ec = Float64(_t1_tds_from_ec - _t0_tds_from_ec) / Float64(N)
    print("MOJO_TIMING hydroponics::tds_from_ec", _ns_tds_from_ec, _acc_tds_from_ec)
    var _acc_nutrient_concentration: Float64 = 0.0
    var _t0_nutrient_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_nutrient_concentration += nutrient_concentration(0.5, 0.5)
    var _t1_nutrient_concentration = perf_counter_ns()
    var _ns_nutrient_concentration = Float64(_t1_nutrient_concentration - _t0_nutrient_concentration) / Float64(N)
    print("MOJO_TIMING hydroponics::nutrient_concentration", _ns_nutrient_concentration, _acc_nutrient_concentration)
    var _acc_ph_adjustment_acid: Float64 = 0.0
    var _t0_ph_adjustment_acid = perf_counter_ns()
    for _ in range(N):
        _acc_ph_adjustment_acid += ph_adjustment_acid(0.5, 0.5, 0.5)
    var _t1_ph_adjustment_acid = perf_counter_ns()
    var _ns_ph_adjustment_acid = Float64(_t1_ph_adjustment_acid - _t0_ph_adjustment_acid) / Float64(N)
    print("MOJO_TIMING hydroponics::ph_adjustment_acid", _ns_ph_adjustment_acid, _acc_ph_adjustment_acid)
    var _acc_light_daily_integral: Float64 = 0.0
    var _t0_light_daily_integral = perf_counter_ns()
    for _ in range(N):
        _acc_light_daily_integral += light_daily_integral(0.5, 0.5)
    var _t1_light_daily_integral = perf_counter_ns()
    var _ns_light_daily_integral = Float64(_t1_light_daily_integral - _t0_light_daily_integral) / Float64(N)
    print("MOJO_TIMING hydroponics::light_daily_integral", _ns_light_daily_integral, _acc_light_daily_integral)
    var _acc_vpd: Float64 = 0.0
    var _t0_vpd = perf_counter_ns()
    for _ in range(N):
        _acc_vpd += vpd(0.5, 0.5)
    var _t1_vpd = perf_counter_ns()
    var _ns_vpd = Float64(_t1_vpd - _t0_vpd) / Float64(N)
    print("MOJO_TIMING hydroponics::vpd", _ns_vpd, _acc_vpd)
    var _acc_water_consumption_rate: Float64 = 0.0
    var _t0_water_consumption_rate = perf_counter_ns()
    for _ in range(N):
        _acc_water_consumption_rate += water_consumption_rate(0.5, 0.5)
    var _t1_water_consumption_rate = perf_counter_ns()
    var _ns_water_consumption_rate = Float64(_t1_water_consumption_rate - _t0_water_consumption_rate) / Float64(N)
    print("MOJO_TIMING hydroponics::water_consumption_rate", _ns_water_consumption_rate, _acc_water_consumption_rate)
    var _acc_nutrient_uptake_rate: Float64 = 0.0
    var _t0_nutrient_uptake_rate = perf_counter_ns()
    for _ in range(N):
        _acc_nutrient_uptake_rate += nutrient_uptake_rate(0.5, 0.5, 0.5, 0.5)
    var _t1_nutrient_uptake_rate = perf_counter_ns()
    var _ns_nutrient_uptake_rate = Float64(_t1_nutrient_uptake_rate - _t0_nutrient_uptake_rate) / Float64(N)
    print("MOJO_TIMING hydroponics::nutrient_uptake_rate", _ns_nutrient_uptake_rate, _acc_nutrient_uptake_rate)
    var _acc_grow_light_efficiency: Float64 = 0.0
    var _t0_grow_light_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_grow_light_efficiency += grow_light_efficiency(0.5, 0.5)
    var _t1_grow_light_efficiency = perf_counter_ns()
    var _ns_grow_light_efficiency = Float64(_t1_grow_light_efficiency - _t0_grow_light_efficiency) / Float64(N)
    print("MOJO_TIMING hydroponics::grow_light_efficiency", _ns_grow_light_efficiency, _acc_grow_light_efficiency)
    var _acc_reservoir_dilution: Float64 = 0.0
    var _t0_reservoir_dilution = perf_counter_ns()
    for _ in range(N):
        _acc_reservoir_dilution += reservoir_dilution(0.5, 0.5, 0.5)
    var _t1_reservoir_dilution = perf_counter_ns()
    var _ns_reservoir_dilution = Float64(_t1_reservoir_dilution - _t0_reservoir_dilution) / Float64(N)
    print("MOJO_TIMING hydroponics::reservoir_dilution", _ns_reservoir_dilution, _acc_reservoir_dilution)
    var _acc_yield_per_area: Float64 = 0.0
    var _t0_yield_per_area = perf_counter_ns()
    for _ in range(N):
        _acc_yield_per_area += yield_per_area(0.5, 0.5)
    var _t1_yield_per_area = perf_counter_ns()
    var _ns_yield_per_area = Float64(_t1_yield_per_area - _t0_yield_per_area) / Float64(N)
    print("MOJO_TIMING hydroponics::yield_per_area", _ns_yield_per_area, _acc_yield_per_area)
    var _acc_crop_cycle_roi: Float64 = 0.0
    var _t0_crop_cycle_roi = perf_counter_ns()
    for _ in range(N):
        _acc_crop_cycle_roi += crop_cycle_roi(0.5, 0.5)
    var _t1_crop_cycle_roi = perf_counter_ns()
    var _ns_crop_cycle_roi = Float64(_t1_crop_cycle_roi - _t0_crop_cycle_roi) / Float64(N)
    print("MOJO_TIMING hydroponics::crop_cycle_roi", _ns_crop_cycle_roi, _acc_crop_cycle_roi)
