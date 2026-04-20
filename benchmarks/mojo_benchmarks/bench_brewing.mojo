"""bench_brewing.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from brewing import original_gravity_to_plato, plato_to_gravity, abv_from_og_fg, apparent_attenuation, real_attenuation, ibu_tinseth, utilization_tinseth, mash_water_volume, strike_water_temp, color_srm_from_mcu, calories_per_12oz, priming_sugar_g
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

    var _acc_original_gravity_to_plato: Float64 = 0.0
    var _t0_original_gravity_to_plato = perf_counter_ns()
    for _ in range(N):
        _acc_original_gravity_to_plato += original_gravity_to_plato(0.5)
    var _t1_original_gravity_to_plato = perf_counter_ns()
    var _ns_original_gravity_to_plato = Float64(_t1_original_gravity_to_plato - _t0_original_gravity_to_plato) / Float64(N)
    print("MOJO_TIMING brewing::original_gravity_to_plato", _ns_original_gravity_to_plato, _acc_original_gravity_to_plato)
    var _acc_plato_to_gravity: Float64 = 0.0
    var _t0_plato_to_gravity = perf_counter_ns()
    for _ in range(N):
        _acc_plato_to_gravity += plato_to_gravity(0.5)
    var _t1_plato_to_gravity = perf_counter_ns()
    var _ns_plato_to_gravity = Float64(_t1_plato_to_gravity - _t0_plato_to_gravity) / Float64(N)
    print("MOJO_TIMING brewing::plato_to_gravity", _ns_plato_to_gravity, _acc_plato_to_gravity)
    var _acc_abv_from_og_fg: Float64 = 0.0
    var _t0_abv_from_og_fg = perf_counter_ns()
    for _ in range(N):
        _acc_abv_from_og_fg += abv_from_og_fg(0.5, 0.5)
    var _t1_abv_from_og_fg = perf_counter_ns()
    var _ns_abv_from_og_fg = Float64(_t1_abv_from_og_fg - _t0_abv_from_og_fg) / Float64(N)
    print("MOJO_TIMING brewing::abv_from_og_fg", _ns_abv_from_og_fg, _acc_abv_from_og_fg)
    var _acc_apparent_attenuation: Float64 = 0.0
    var _t0_apparent_attenuation = perf_counter_ns()
    for _ in range(N):
        _acc_apparent_attenuation += apparent_attenuation(0.5, 0.5)
    var _t1_apparent_attenuation = perf_counter_ns()
    var _ns_apparent_attenuation = Float64(_t1_apparent_attenuation - _t0_apparent_attenuation) / Float64(N)
    print("MOJO_TIMING brewing::apparent_attenuation", _ns_apparent_attenuation, _acc_apparent_attenuation)
    var _acc_real_attenuation: Float64 = 0.0
    var _t0_real_attenuation = perf_counter_ns()
    for _ in range(N):
        _acc_real_attenuation += real_attenuation(0.5)
    var _t1_real_attenuation = perf_counter_ns()
    var _ns_real_attenuation = Float64(_t1_real_attenuation - _t0_real_attenuation) / Float64(N)
    print("MOJO_TIMING brewing::real_attenuation", _ns_real_attenuation, _acc_real_attenuation)
    var _acc_ibu_tinseth: Float64 = 0.0
    var _t0_ibu_tinseth = perf_counter_ns()
    for _ in range(N):
        _acc_ibu_tinseth += ibu_tinseth(0.5, 0.5, 0.5, 0.5)
    var _t1_ibu_tinseth = perf_counter_ns()
    var _ns_ibu_tinseth = Float64(_t1_ibu_tinseth - _t0_ibu_tinseth) / Float64(N)
    print("MOJO_TIMING brewing::ibu_tinseth", _ns_ibu_tinseth, _acc_ibu_tinseth)
    var _acc_utilization_tinseth: Float64 = 0.0
    var _t0_utilization_tinseth = perf_counter_ns()
    for _ in range(N):
        _acc_utilization_tinseth += utilization_tinseth(0.5, 0.5)
    var _t1_utilization_tinseth = perf_counter_ns()
    var _ns_utilization_tinseth = Float64(_t1_utilization_tinseth - _t0_utilization_tinseth) / Float64(N)
    print("MOJO_TIMING brewing::utilization_tinseth", _ns_utilization_tinseth, _acc_utilization_tinseth)
    var _acc_mash_water_volume: Float64 = 0.0
    var _t0_mash_water_volume = perf_counter_ns()
    for _ in range(N):
        _acc_mash_water_volume += mash_water_volume(0.5, 0.5)
    var _t1_mash_water_volume = perf_counter_ns()
    var _ns_mash_water_volume = Float64(_t1_mash_water_volume - _t0_mash_water_volume) / Float64(N)
    print("MOJO_TIMING brewing::mash_water_volume", _ns_mash_water_volume, _acc_mash_water_volume)
    var _acc_strike_water_temp: Float64 = 0.0
    var _t0_strike_water_temp = perf_counter_ns()
    for _ in range(N):
        _acc_strike_water_temp += strike_water_temp(0.5, 0.5, 0.5)
    var _t1_strike_water_temp = perf_counter_ns()
    var _ns_strike_water_temp = Float64(_t1_strike_water_temp - _t0_strike_water_temp) / Float64(N)
    print("MOJO_TIMING brewing::strike_water_temp", _ns_strike_water_temp, _acc_strike_water_temp)
    var _acc_color_srm_from_mcu: Float64 = 0.0
    var _t0_color_srm_from_mcu = perf_counter_ns()
    for _ in range(N):
        _acc_color_srm_from_mcu += color_srm_from_mcu(0.5)
    var _t1_color_srm_from_mcu = perf_counter_ns()
    var _ns_color_srm_from_mcu = Float64(_t1_color_srm_from_mcu - _t0_color_srm_from_mcu) / Float64(N)
    print("MOJO_TIMING brewing::color_srm_from_mcu", _ns_color_srm_from_mcu, _acc_color_srm_from_mcu)
    var _acc_calories_per_12oz: Float64 = 0.0
    var _t0_calories_per_12oz = perf_counter_ns()
    for _ in range(N):
        _acc_calories_per_12oz += calories_per_12oz(0.5, 0.5)
    var _t1_calories_per_12oz = perf_counter_ns()
    var _ns_calories_per_12oz = Float64(_t1_calories_per_12oz - _t0_calories_per_12oz) / Float64(N)
    print("MOJO_TIMING brewing::calories_per_12oz", _ns_calories_per_12oz, _acc_calories_per_12oz)
    var _acc_priming_sugar_g: Float64 = 0.0
    var _t0_priming_sugar_g = perf_counter_ns()
    for _ in range(N):
        _acc_priming_sugar_g += priming_sugar_g(0.5, 0.5, 0.5)
    var _t1_priming_sugar_g = perf_counter_ns()
    var _ns_priming_sugar_g = Float64(_t1_priming_sugar_g - _t0_priming_sugar_g) / Float64(N)
    print("MOJO_TIMING brewing::priming_sugar_g", _ns_priming_sugar_g, _acc_priming_sugar_g)
