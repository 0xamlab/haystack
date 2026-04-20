"""bench_laundry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from laundry import water_usage_liters, detergent_dose_ml, wash_temperature_energy, spin_g_force, moisture_retention, drying_time_estimate, energy_per_cycle, cost_per_wash, fabric_wear_cycles, stain_removal_efficiency, color_fastness_delta_e, water_hardness_compensation
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

    var _acc_water_usage_liters: Float64 = 0.0
    var _t0_water_usage_liters = perf_counter_ns()
    for _ in range(N):
        _acc_water_usage_liters += water_usage_liters(0.5, 0.5)
    var _t1_water_usage_liters = perf_counter_ns()
    var _ns_water_usage_liters = Float64(_t1_water_usage_liters - _t0_water_usage_liters) / Float64(N)
    print("MOJO_TIMING laundry::water_usage_liters", _ns_water_usage_liters, _acc_water_usage_liters)
    var _acc_detergent_dose_ml: Float64 = 0.0
    var _t0_detergent_dose_ml = perf_counter_ns()
    for _ in range(N):
        _acc_detergent_dose_ml += detergent_dose_ml(0.5, 0.5, 0.5)
    var _t1_detergent_dose_ml = perf_counter_ns()
    var _ns_detergent_dose_ml = Float64(_t1_detergent_dose_ml - _t0_detergent_dose_ml) / Float64(N)
    print("MOJO_TIMING laundry::detergent_dose_ml", _ns_detergent_dose_ml, _acc_detergent_dose_ml)
    var _acc_wash_temperature_energy: Float64 = 0.0
    var _t0_wash_temperature_energy = perf_counter_ns()
    for _ in range(N):
        _acc_wash_temperature_energy += wash_temperature_energy(0.5, 0.5, 0.5)
    var _t1_wash_temperature_energy = perf_counter_ns()
    var _ns_wash_temperature_energy = Float64(_t1_wash_temperature_energy - _t0_wash_temperature_energy) / Float64(N)
    print("MOJO_TIMING laundry::wash_temperature_energy", _ns_wash_temperature_energy, _acc_wash_temperature_energy)
    var _acc_spin_g_force: Float64 = 0.0
    var _t0_spin_g_force = perf_counter_ns()
    for _ in range(N):
        _acc_spin_g_force += spin_g_force(0.5, 0.5)
    var _t1_spin_g_force = perf_counter_ns()
    var _ns_spin_g_force = Float64(_t1_spin_g_force - _t0_spin_g_force) / Float64(N)
    print("MOJO_TIMING laundry::spin_g_force", _ns_spin_g_force, _acc_spin_g_force)
    var _acc_moisture_retention: Float64 = 0.0
    var _t0_moisture_retention = perf_counter_ns()
    for _ in range(N):
        _acc_moisture_retention += moisture_retention(0.5, 0.5)
    var _t1_moisture_retention = perf_counter_ns()
    var _ns_moisture_retention = Float64(_t1_moisture_retention - _t0_moisture_retention) / Float64(N)
    print("MOJO_TIMING laundry::moisture_retention", _ns_moisture_retention, _acc_moisture_retention)
    var _acc_drying_time_estimate: Float64 = 0.0
    var _t0_drying_time_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_drying_time_estimate += drying_time_estimate(0.5, 0.5)
    var _t1_drying_time_estimate = perf_counter_ns()
    var _ns_drying_time_estimate = Float64(_t1_drying_time_estimate - _t0_drying_time_estimate) / Float64(N)
    print("MOJO_TIMING laundry::drying_time_estimate", _ns_drying_time_estimate, _acc_drying_time_estimate)
    var _acc_energy_per_cycle: Float64 = 0.0
    var _t0_energy_per_cycle = perf_counter_ns()
    for _ in range(N):
        _acc_energy_per_cycle += energy_per_cycle(0.5, 0.5)
    var _t1_energy_per_cycle = perf_counter_ns()
    var _ns_energy_per_cycle = Float64(_t1_energy_per_cycle - _t0_energy_per_cycle) / Float64(N)
    print("MOJO_TIMING laundry::energy_per_cycle", _ns_energy_per_cycle, _acc_energy_per_cycle)
    var _acc_cost_per_wash: Float64 = 0.0
    var _t0_cost_per_wash = perf_counter_ns()
    for _ in range(N):
        _acc_cost_per_wash += cost_per_wash(0.5, 0.5, 0.5, 0.5)
    var _t1_cost_per_wash = perf_counter_ns()
    var _ns_cost_per_wash = Float64(_t1_cost_per_wash - _t0_cost_per_wash) / Float64(N)
    print("MOJO_TIMING laundry::cost_per_wash", _ns_cost_per_wash, _acc_cost_per_wash)
    var _acc_fabric_wear_cycles: Float64 = 0.0
    var _t0_fabric_wear_cycles = perf_counter_ns()
    for _ in range(N):
        _acc_fabric_wear_cycles += fabric_wear_cycles(0.5, 0.5, 0.5)
    var _t1_fabric_wear_cycles = perf_counter_ns()
    var _ns_fabric_wear_cycles = Float64(_t1_fabric_wear_cycles - _t0_fabric_wear_cycles) / Float64(N)
    print("MOJO_TIMING laundry::fabric_wear_cycles", _ns_fabric_wear_cycles, _acc_fabric_wear_cycles)
    var _acc_stain_removal_efficiency: Float64 = 0.0
    var _t0_stain_removal_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_stain_removal_efficiency += stain_removal_efficiency(0.5, 0.5)
    var _t1_stain_removal_efficiency = perf_counter_ns()
    var _ns_stain_removal_efficiency = Float64(_t1_stain_removal_efficiency - _t0_stain_removal_efficiency) / Float64(N)
    print("MOJO_TIMING laundry::stain_removal_efficiency", _ns_stain_removal_efficiency, _acc_stain_removal_efficiency)
    var _acc_color_fastness_delta_e: Float64 = 0.0
    var _t0_color_fastness_delta_e = perf_counter_ns()
    for _ in range(N):
        _acc_color_fastness_delta_e += color_fastness_delta_e(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_color_fastness_delta_e = perf_counter_ns()
    var _ns_color_fastness_delta_e = Float64(_t1_color_fastness_delta_e - _t0_color_fastness_delta_e) / Float64(N)
    print("MOJO_TIMING laundry::color_fastness_delta_e", _ns_color_fastness_delta_e, _acc_color_fastness_delta_e)
    var _acc_water_hardness_compensation: Float64 = 0.0
    var _t0_water_hardness_compensation = perf_counter_ns()
    for _ in range(N):
        _acc_water_hardness_compensation += water_hardness_compensation(0.5, 0.5, 0.5)
    var _t1_water_hardness_compensation = perf_counter_ns()
    var _ns_water_hardness_compensation = Float64(_t1_water_hardness_compensation - _t0_water_hardness_compensation) / Float64(N)
    print("MOJO_TIMING laundry::water_hardness_compensation", _ns_water_hardness_compensation, _acc_water_hardness_compensation)
