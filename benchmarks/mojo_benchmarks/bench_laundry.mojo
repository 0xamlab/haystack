"""bench_laundry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from laundry import water_usage_liters, detergent_dose_ml, wash_temperature_energy, spin_g_force, moisture_retention, drying_time_estimate, energy_per_cycle, cost_per_wash, fabric_wear_cycles, stain_removal_efficiency, color_fastness_delta_e, water_hardness_compensation
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

    var _acc_water_usage_liters: Float64 = 0.0
    var _t0_water_usage_liters = perf_counter_ns()
    for _ in range(N):
        _acc_water_usage_liters += water_usage_liters(0.5, 0.5)
    var _t1_water_usage_liters = perf_counter_ns()
    var _ns_water_usage_liters = Float64(_t1_water_usage_liters - _t0_water_usage_liters) / Float64(N)
    print("MOJO_TIMING laundry::water_usage_liters", _ns_water_usage_liters, _acc_water_usage_liters)
    var _result_water_usage_liters = water_usage_liters(0.5, 0.5)
    var _summary_water_usage_liters = _summary_float64(_result_water_usage_liters)
    print("MOJO_RESULT laundry::water_usage_liters", _summary_water_usage_liters)
    var _acc_detergent_dose_ml: Float64 = 0.0
    var _t0_detergent_dose_ml = perf_counter_ns()
    for _ in range(N):
        _acc_detergent_dose_ml += detergent_dose_ml(0.5, 0.5, 0.5)
    var _t1_detergent_dose_ml = perf_counter_ns()
    var _ns_detergent_dose_ml = Float64(_t1_detergent_dose_ml - _t0_detergent_dose_ml) / Float64(N)
    print("MOJO_TIMING laundry::detergent_dose_ml", _ns_detergent_dose_ml, _acc_detergent_dose_ml)
    var _result_detergent_dose_ml = detergent_dose_ml(0.5, 0.5, 0.5)
    var _summary_detergent_dose_ml = _summary_float64(_result_detergent_dose_ml)
    print("MOJO_RESULT laundry::detergent_dose_ml", _summary_detergent_dose_ml)
    var _acc_wash_temperature_energy: Float64 = 0.0
    var _t0_wash_temperature_energy = perf_counter_ns()
    for _ in range(N):
        _acc_wash_temperature_energy += wash_temperature_energy(0.5, 0.5, 0.5)
    var _t1_wash_temperature_energy = perf_counter_ns()
    var _ns_wash_temperature_energy = Float64(_t1_wash_temperature_energy - _t0_wash_temperature_energy) / Float64(N)
    print("MOJO_TIMING laundry::wash_temperature_energy", _ns_wash_temperature_energy, _acc_wash_temperature_energy)
    var _result_wash_temperature_energy = wash_temperature_energy(0.5, 0.5, 0.5)
    var _summary_wash_temperature_energy = _summary_float64(_result_wash_temperature_energy)
    print("MOJO_RESULT laundry::wash_temperature_energy", _summary_wash_temperature_energy)
    var _acc_spin_g_force: Float64 = 0.0
    var _t0_spin_g_force = perf_counter_ns()
    for _ in range(N):
        _acc_spin_g_force += spin_g_force(0.5, 0.5)
    var _t1_spin_g_force = perf_counter_ns()
    var _ns_spin_g_force = Float64(_t1_spin_g_force - _t0_spin_g_force) / Float64(N)
    print("MOJO_TIMING laundry::spin_g_force", _ns_spin_g_force, _acc_spin_g_force)
    var _result_spin_g_force = spin_g_force(0.5, 0.5)
    var _summary_spin_g_force = _summary_float64(_result_spin_g_force)
    print("MOJO_RESULT laundry::spin_g_force", _summary_spin_g_force)
    var _acc_moisture_retention: Float64 = 0.0
    var _t0_moisture_retention = perf_counter_ns()
    for _ in range(N):
        _acc_moisture_retention += moisture_retention(0.5, 0.5)
    var _t1_moisture_retention = perf_counter_ns()
    var _ns_moisture_retention = Float64(_t1_moisture_retention - _t0_moisture_retention) / Float64(N)
    print("MOJO_TIMING laundry::moisture_retention", _ns_moisture_retention, _acc_moisture_retention)
    var _result_moisture_retention = moisture_retention(0.5, 0.5)
    var _summary_moisture_retention = _summary_float64(_result_moisture_retention)
    print("MOJO_RESULT laundry::moisture_retention", _summary_moisture_retention)
    var _acc_drying_time_estimate: Float64 = 0.0
    var _t0_drying_time_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_drying_time_estimate += drying_time_estimate(0.5, 0.5)
    var _t1_drying_time_estimate = perf_counter_ns()
    var _ns_drying_time_estimate = Float64(_t1_drying_time_estimate - _t0_drying_time_estimate) / Float64(N)
    print("MOJO_TIMING laundry::drying_time_estimate", _ns_drying_time_estimate, _acc_drying_time_estimate)
    var _result_drying_time_estimate = drying_time_estimate(0.5, 0.5)
    var _summary_drying_time_estimate = _summary_float64(_result_drying_time_estimate)
    print("MOJO_RESULT laundry::drying_time_estimate", _summary_drying_time_estimate)
    var _acc_energy_per_cycle: Float64 = 0.0
    var _t0_energy_per_cycle = perf_counter_ns()
    for _ in range(N):
        _acc_energy_per_cycle += energy_per_cycle(0.5, 0.5)
    var _t1_energy_per_cycle = perf_counter_ns()
    var _ns_energy_per_cycle = Float64(_t1_energy_per_cycle - _t0_energy_per_cycle) / Float64(N)
    print("MOJO_TIMING laundry::energy_per_cycle", _ns_energy_per_cycle, _acc_energy_per_cycle)
    var _result_energy_per_cycle = energy_per_cycle(0.5, 0.5)
    var _summary_energy_per_cycle = _summary_float64(_result_energy_per_cycle)
    print("MOJO_RESULT laundry::energy_per_cycle", _summary_energy_per_cycle)
    var _acc_cost_per_wash: Float64 = 0.0
    var _t0_cost_per_wash = perf_counter_ns()
    for _ in range(N):
        _acc_cost_per_wash += cost_per_wash(0.5, 0.5, 0.5, 0.5)
    var _t1_cost_per_wash = perf_counter_ns()
    var _ns_cost_per_wash = Float64(_t1_cost_per_wash - _t0_cost_per_wash) / Float64(N)
    print("MOJO_TIMING laundry::cost_per_wash", _ns_cost_per_wash, _acc_cost_per_wash)
    var _result_cost_per_wash = cost_per_wash(0.5, 0.5, 0.5, 0.5)
    var _summary_cost_per_wash = _summary_float64(_result_cost_per_wash)
    print("MOJO_RESULT laundry::cost_per_wash", _summary_cost_per_wash)
    var _acc_fabric_wear_cycles: Float64 = 0.0
    var _t0_fabric_wear_cycles = perf_counter_ns()
    for _ in range(N):
        _acc_fabric_wear_cycles += fabric_wear_cycles(0.5, 0.5, 0.5)
    var _t1_fabric_wear_cycles = perf_counter_ns()
    var _ns_fabric_wear_cycles = Float64(_t1_fabric_wear_cycles - _t0_fabric_wear_cycles) / Float64(N)
    print("MOJO_TIMING laundry::fabric_wear_cycles", _ns_fabric_wear_cycles, _acc_fabric_wear_cycles)
    var _result_fabric_wear_cycles = fabric_wear_cycles(0.5, 0.5, 0.5)
    var _summary_fabric_wear_cycles = _summary_float64(_result_fabric_wear_cycles)
    print("MOJO_RESULT laundry::fabric_wear_cycles", _summary_fabric_wear_cycles)
    var _acc_stain_removal_efficiency: Float64 = 0.0
    var _t0_stain_removal_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_stain_removal_efficiency += stain_removal_efficiency(0.5, 0.5)
    var _t1_stain_removal_efficiency = perf_counter_ns()
    var _ns_stain_removal_efficiency = Float64(_t1_stain_removal_efficiency - _t0_stain_removal_efficiency) / Float64(N)
    print("MOJO_TIMING laundry::stain_removal_efficiency", _ns_stain_removal_efficiency, _acc_stain_removal_efficiency)
    var _result_stain_removal_efficiency = stain_removal_efficiency(0.5, 0.5)
    var _summary_stain_removal_efficiency = _summary_float64(_result_stain_removal_efficiency)
    print("MOJO_RESULT laundry::stain_removal_efficiency", _summary_stain_removal_efficiency)
    var _acc_color_fastness_delta_e: Float64 = 0.0
    var _t0_color_fastness_delta_e = perf_counter_ns()
    for _ in range(N):
        _acc_color_fastness_delta_e += color_fastness_delta_e(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_color_fastness_delta_e = perf_counter_ns()
    var _ns_color_fastness_delta_e = Float64(_t1_color_fastness_delta_e - _t0_color_fastness_delta_e) / Float64(N)
    print("MOJO_TIMING laundry::color_fastness_delta_e", _ns_color_fastness_delta_e, _acc_color_fastness_delta_e)
    var _result_color_fastness_delta_e = color_fastness_delta_e(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_color_fastness_delta_e = _summary_float64(_result_color_fastness_delta_e)
    print("MOJO_RESULT laundry::color_fastness_delta_e", _summary_color_fastness_delta_e)
    var _acc_water_hardness_compensation: Float64 = 0.0
    var _t0_water_hardness_compensation = perf_counter_ns()
    for _ in range(N):
        _acc_water_hardness_compensation += water_hardness_compensation(0.5, 0.5, 0.5)
    var _t1_water_hardness_compensation = perf_counter_ns()
    var _ns_water_hardness_compensation = Float64(_t1_water_hardness_compensation - _t0_water_hardness_compensation) / Float64(N)
    print("MOJO_TIMING laundry::water_hardness_compensation", _ns_water_hardness_compensation, _acc_water_hardness_compensation)
    var _result_water_hardness_compensation = water_hardness_compensation(0.5, 0.5, 0.5)
    var _summary_water_hardness_compensation = _summary_float64(_result_water_hardness_compensation)
    print("MOJO_RESULT laundry::water_hardness_compensation", _summary_water_hardness_compensation)
