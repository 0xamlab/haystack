"""bench_ergonomics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ergonomics import niosh_rwl, lifting_index, metabolic_rate_walking, heat_stress_index, decibel_addition, noise_dose, cumulative_noise_dose_2, visual_angle_minutes, fitts_law_movement_time, hicks_law_reaction_time, comfort_temperature_pmv_simplified, body_mass_index
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

    var _acc_niosh_rwl: Float64 = 0.0
    var _t0_niosh_rwl = perf_counter_ns()
    for _ in range(N):
        _acc_niosh_rwl += niosh_rwl(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_niosh_rwl = perf_counter_ns()
    var _ns_niosh_rwl = Float64(_t1_niosh_rwl - _t0_niosh_rwl) / Float64(N)
    print("MOJO_TIMING ergonomics::niosh_rwl", _ns_niosh_rwl, _acc_niosh_rwl)
    var _acc_lifting_index: Float64 = 0.0
    var _t0_lifting_index = perf_counter_ns()
    for _ in range(N):
        _acc_lifting_index += lifting_index(0.5, 0.5)
    var _t1_lifting_index = perf_counter_ns()
    var _ns_lifting_index = Float64(_t1_lifting_index - _t0_lifting_index) / Float64(N)
    print("MOJO_TIMING ergonomics::lifting_index", _ns_lifting_index, _acc_lifting_index)
    var _acc_metabolic_rate_walking: Float64 = 0.0
    var _t0_metabolic_rate_walking = perf_counter_ns()
    for _ in range(N):
        _acc_metabolic_rate_walking += metabolic_rate_walking(0.5, 0.5, 0.5)
    var _t1_metabolic_rate_walking = perf_counter_ns()
    var _ns_metabolic_rate_walking = Float64(_t1_metabolic_rate_walking - _t0_metabolic_rate_walking) / Float64(N)
    print("MOJO_TIMING ergonomics::metabolic_rate_walking", _ns_metabolic_rate_walking, _acc_metabolic_rate_walking)
    var _acc_heat_stress_index: Float64 = 0.0
    var _t0_heat_stress_index = perf_counter_ns()
    for _ in range(N):
        _acc_heat_stress_index += heat_stress_index(0.5, 0.5)
    var _t1_heat_stress_index = perf_counter_ns()
    var _ns_heat_stress_index = Float64(_t1_heat_stress_index - _t0_heat_stress_index) / Float64(N)
    print("MOJO_TIMING ergonomics::heat_stress_index", _ns_heat_stress_index, _acc_heat_stress_index)
    var _acc_decibel_addition: Float64 = 0.0
    var _t0_decibel_addition = perf_counter_ns()
    for _ in range(N):
        _acc_decibel_addition += decibel_addition(0.5, 0.5)
    var _t1_decibel_addition = perf_counter_ns()
    var _ns_decibel_addition = Float64(_t1_decibel_addition - _t0_decibel_addition) / Float64(N)
    print("MOJO_TIMING ergonomics::decibel_addition", _ns_decibel_addition, _acc_decibel_addition)
    var _acc_noise_dose: Float64 = 0.0
    var _t0_noise_dose = perf_counter_ns()
    for _ in range(N):
        _acc_noise_dose += noise_dose(0.5, 0.5)
    var _t1_noise_dose = perf_counter_ns()
    var _ns_noise_dose = Float64(_t1_noise_dose - _t0_noise_dose) / Float64(N)
    print("MOJO_TIMING ergonomics::noise_dose", _ns_noise_dose, _acc_noise_dose)
    var _acc_cumulative_noise_dose_2: Float64 = 0.0
    var _t0_cumulative_noise_dose_2 = perf_counter_ns()
    for _ in range(N):
        _acc_cumulative_noise_dose_2 += cumulative_noise_dose_2(0.5, 0.5, 0.5, 0.5)
    var _t1_cumulative_noise_dose_2 = perf_counter_ns()
    var _ns_cumulative_noise_dose_2 = Float64(_t1_cumulative_noise_dose_2 - _t0_cumulative_noise_dose_2) / Float64(N)
    print("MOJO_TIMING ergonomics::cumulative_noise_dose_2", _ns_cumulative_noise_dose_2, _acc_cumulative_noise_dose_2)
    var _acc_visual_angle_minutes: Float64 = 0.0
    var _t0_visual_angle_minutes = perf_counter_ns()
    for _ in range(N):
        _acc_visual_angle_minutes += visual_angle_minutes(0.5, 0.5)
    var _t1_visual_angle_minutes = perf_counter_ns()
    var _ns_visual_angle_minutes = Float64(_t1_visual_angle_minutes - _t0_visual_angle_minutes) / Float64(N)
    print("MOJO_TIMING ergonomics::visual_angle_minutes", _ns_visual_angle_minutes, _acc_visual_angle_minutes)
    var _acc_fitts_law_movement_time: Float64 = 0.0
    var _t0_fitts_law_movement_time = perf_counter_ns()
    for _ in range(N):
        _acc_fitts_law_movement_time += fitts_law_movement_time(0.5, 0.5, 0.5, 0.5)
    var _t1_fitts_law_movement_time = perf_counter_ns()
    var _ns_fitts_law_movement_time = Float64(_t1_fitts_law_movement_time - _t0_fitts_law_movement_time) / Float64(N)
    print("MOJO_TIMING ergonomics::fitts_law_movement_time", _ns_fitts_law_movement_time, _acc_fitts_law_movement_time)
    var _acc_hicks_law_reaction_time: Float64 = 0.0
    var _t0_hicks_law_reaction_time = perf_counter_ns()
    for _ in range(N):
        _acc_hicks_law_reaction_time += hicks_law_reaction_time(0.5, 0.5, 0.5)
    var _t1_hicks_law_reaction_time = perf_counter_ns()
    var _ns_hicks_law_reaction_time = Float64(_t1_hicks_law_reaction_time - _t0_hicks_law_reaction_time) / Float64(N)
    print("MOJO_TIMING ergonomics::hicks_law_reaction_time", _ns_hicks_law_reaction_time, _acc_hicks_law_reaction_time)
    var _acc_comfort_temperature_pmv_simplified: Float64 = 0.0
    var _t0_comfort_temperature_pmv_simplified = perf_counter_ns()
    for _ in range(N):
        _acc_comfort_temperature_pmv_simplified += comfort_temperature_pmv_simplified(0.5, 0.5, 0.5)
    var _t1_comfort_temperature_pmv_simplified = perf_counter_ns()
    var _ns_comfort_temperature_pmv_simplified = Float64(_t1_comfort_temperature_pmv_simplified - _t0_comfort_temperature_pmv_simplified) / Float64(N)
    print("MOJO_TIMING ergonomics::comfort_temperature_pmv_simplified", _ns_comfort_temperature_pmv_simplified, _acc_comfort_temperature_pmv_simplified)
    var _acc_body_mass_index: Float64 = 0.0
    var _t0_body_mass_index = perf_counter_ns()
    for _ in range(N):
        _acc_body_mass_index += body_mass_index(0.5, 0.5)
    var _t1_body_mass_index = perf_counter_ns()
    var _ns_body_mass_index = Float64(_t1_body_mass_index - _t0_body_mass_index) / Float64(N)
    print("MOJO_TIMING ergonomics::body_mass_index", _ns_body_mass_index, _acc_body_mass_index)
