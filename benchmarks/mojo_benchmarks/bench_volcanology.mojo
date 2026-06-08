"""bench_volcanology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from volcanology import vei_energy_estimate, lava_flow_velocity, eruption_column_height, tephra_fallout_thickness, magma_viscosity_estimate, effusion_rate, lahar_velocity, volcanic_gas_emission_rate, recurrence_interval, alert_level, pyroclastic_flow_runout, caldera_collapse_volume
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

    var _acc_vei_energy_estimate: Float64 = 0.0
    var _t0_vei_energy_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_vei_energy_estimate += vei_energy_estimate(0.5)
    var _t1_vei_energy_estimate = perf_counter_ns()
    var _ns_vei_energy_estimate = Float64(_t1_vei_energy_estimate - _t0_vei_energy_estimate) / Float64(N)
    print("MOJO_TIMING volcanology::vei_energy_estimate", _ns_vei_energy_estimate, _acc_vei_energy_estimate)
    var _result_vei_energy_estimate = vei_energy_estimate(0.5)
    var _summary_vei_energy_estimate = _summary_float64(_result_vei_energy_estimate)
    print("MOJO_RESULT volcanology::vei_energy_estimate", _summary_vei_energy_estimate)
    var _acc_lava_flow_velocity: Float64 = 0.0
    var _t0_lava_flow_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_lava_flow_velocity += lava_flow_velocity(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_lava_flow_velocity = perf_counter_ns()
    var _ns_lava_flow_velocity = Float64(_t1_lava_flow_velocity - _t0_lava_flow_velocity) / Float64(N)
    print("MOJO_TIMING volcanology::lava_flow_velocity", _ns_lava_flow_velocity, _acc_lava_flow_velocity)
    var _result_lava_flow_velocity = lava_flow_velocity(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_lava_flow_velocity = _summary_float64(_result_lava_flow_velocity)
    print("MOJO_RESULT volcanology::lava_flow_velocity", _summary_lava_flow_velocity)
    var _acc_eruption_column_height: Float64 = 0.0
    var _t0_eruption_column_height = perf_counter_ns()
    for _ in range(N):
        _acc_eruption_column_height += eruption_column_height(0.5, 0.5)
    var _t1_eruption_column_height = perf_counter_ns()
    var _ns_eruption_column_height = Float64(_t1_eruption_column_height - _t0_eruption_column_height) / Float64(N)
    print("MOJO_TIMING volcanology::eruption_column_height", _ns_eruption_column_height, _acc_eruption_column_height)
    var _result_eruption_column_height = eruption_column_height(0.5, 0.5)
    var _summary_eruption_column_height = _summary_float64(_result_eruption_column_height)
    print("MOJO_RESULT volcanology::eruption_column_height", _summary_eruption_column_height)
    var _acc_tephra_fallout_thickness: Float64 = 0.0
    var _t0_tephra_fallout_thickness = perf_counter_ns()
    for _ in range(N):
        _acc_tephra_fallout_thickness += tephra_fallout_thickness(0.5, 0.5)
    var _t1_tephra_fallout_thickness = perf_counter_ns()
    var _ns_tephra_fallout_thickness = Float64(_t1_tephra_fallout_thickness - _t0_tephra_fallout_thickness) / Float64(N)
    print("MOJO_TIMING volcanology::tephra_fallout_thickness", _ns_tephra_fallout_thickness, _acc_tephra_fallout_thickness)
    var _result_tephra_fallout_thickness = tephra_fallout_thickness(0.5, 0.5)
    var _summary_tephra_fallout_thickness = _summary_float64(_result_tephra_fallout_thickness)
    print("MOJO_RESULT volcanology::tephra_fallout_thickness", _summary_tephra_fallout_thickness)
    var _acc_magma_viscosity_estimate: Float64 = 0.0
    var _t0_magma_viscosity_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_magma_viscosity_estimate += magma_viscosity_estimate(0.5)
    var _t1_magma_viscosity_estimate = perf_counter_ns()
    var _ns_magma_viscosity_estimate = Float64(_t1_magma_viscosity_estimate - _t0_magma_viscosity_estimate) / Float64(N)
    print("MOJO_TIMING volcanology::magma_viscosity_estimate", _ns_magma_viscosity_estimate, _acc_magma_viscosity_estimate)
    var _result_magma_viscosity_estimate = magma_viscosity_estimate(0.5)
    var _summary_magma_viscosity_estimate = _summary_float64(_result_magma_viscosity_estimate)
    print("MOJO_RESULT volcanology::magma_viscosity_estimate", _summary_magma_viscosity_estimate)
    var _acc_effusion_rate: Float64 = 0.0
    var _t0_effusion_rate = perf_counter_ns()
    for _ in range(N):
        _acc_effusion_rate += effusion_rate(0.5, 0.5)
    var _t1_effusion_rate = perf_counter_ns()
    var _ns_effusion_rate = Float64(_t1_effusion_rate - _t0_effusion_rate) / Float64(N)
    print("MOJO_TIMING volcanology::effusion_rate", _ns_effusion_rate, _acc_effusion_rate)
    var _result_effusion_rate = effusion_rate(0.5, 0.5)
    var _summary_effusion_rate = _summary_float64(_result_effusion_rate)
    print("MOJO_RESULT volcanology::effusion_rate", _summary_effusion_rate)
    var _acc_lahar_velocity: Float64 = 0.0
    var _t0_lahar_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_lahar_velocity += lahar_velocity(0.5, 0.5)
    var _t1_lahar_velocity = perf_counter_ns()
    var _ns_lahar_velocity = Float64(_t1_lahar_velocity - _t0_lahar_velocity) / Float64(N)
    print("MOJO_TIMING volcanology::lahar_velocity", _ns_lahar_velocity, _acc_lahar_velocity)
    var _result_lahar_velocity = lahar_velocity(0.5, 0.5)
    var _summary_lahar_velocity = _summary_float64(_result_lahar_velocity)
    print("MOJO_RESULT volcanology::lahar_velocity", _summary_lahar_velocity)
    var _acc_volcanic_gas_emission_rate: Float64 = 0.0
    var _t0_volcanic_gas_emission_rate = perf_counter_ns()
    for _ in range(N):
        _acc_volcanic_gas_emission_rate += volcanic_gas_emission_rate(0.5, 0.5)
    var _t1_volcanic_gas_emission_rate = perf_counter_ns()
    var _ns_volcanic_gas_emission_rate = Float64(_t1_volcanic_gas_emission_rate - _t0_volcanic_gas_emission_rate) / Float64(N)
    print("MOJO_TIMING volcanology::volcanic_gas_emission_rate", _ns_volcanic_gas_emission_rate, _acc_volcanic_gas_emission_rate)
    var _result_volcanic_gas_emission_rate = volcanic_gas_emission_rate(0.5, 0.5)
    var _summary_volcanic_gas_emission_rate = _summary_float64(_result_volcanic_gas_emission_rate)
    print("MOJO_RESULT volcanology::volcanic_gas_emission_rate", _summary_volcanic_gas_emission_rate)
    var _acc_recurrence_interval: Float64 = 0.0
    var _t0_recurrence_interval = perf_counter_ns()
    for _ in range(N):
        _acc_recurrence_interval += recurrence_interval(0.5, 0.5)
    var _t1_recurrence_interval = perf_counter_ns()
    var _ns_recurrence_interval = Float64(_t1_recurrence_interval - _t0_recurrence_interval) / Float64(N)
    print("MOJO_TIMING volcanology::recurrence_interval", _ns_recurrence_interval, _acc_recurrence_interval)
    var _result_recurrence_interval = recurrence_interval(0.5, 0.5)
    var _summary_recurrence_interval = _summary_float64(_result_recurrence_interval)
    print("MOJO_RESULT volcanology::recurrence_interval", _summary_recurrence_interval)
    var _acc_alert_level: Float64 = 0.0
    var _t0_alert_level = perf_counter_ns()
    for _ in range(N):
        _acc_alert_level += alert_level(0.5, 0.5, 0.5)
    var _t1_alert_level = perf_counter_ns()
    var _ns_alert_level = Float64(_t1_alert_level - _t0_alert_level) / Float64(N)
    print("MOJO_TIMING volcanology::alert_level", _ns_alert_level, _acc_alert_level)
    var _result_alert_level = alert_level(0.5, 0.5, 0.5)
    var _summary_alert_level = _summary_float64(_result_alert_level)
    print("MOJO_RESULT volcanology::alert_level", _summary_alert_level)
    var _acc_pyroclastic_flow_runout: Float64 = 0.0
    var _t0_pyroclastic_flow_runout = perf_counter_ns()
    for _ in range(N):
        _acc_pyroclastic_flow_runout += pyroclastic_flow_runout(0.5, 0.5)
    var _t1_pyroclastic_flow_runout = perf_counter_ns()
    var _ns_pyroclastic_flow_runout = Float64(_t1_pyroclastic_flow_runout - _t0_pyroclastic_flow_runout) / Float64(N)
    print("MOJO_TIMING volcanology::pyroclastic_flow_runout", _ns_pyroclastic_flow_runout, _acc_pyroclastic_flow_runout)
    var _result_pyroclastic_flow_runout = pyroclastic_flow_runout(0.5, 0.5)
    var _summary_pyroclastic_flow_runout = _summary_float64(_result_pyroclastic_flow_runout)
    print("MOJO_RESULT volcanology::pyroclastic_flow_runout", _summary_pyroclastic_flow_runout)
    var _acc_caldera_collapse_volume: Float64 = 0.0
    var _t0_caldera_collapse_volume = perf_counter_ns()
    for _ in range(N):
        _acc_caldera_collapse_volume += caldera_collapse_volume(0.5, 0.5)
    var _t1_caldera_collapse_volume = perf_counter_ns()
    var _ns_caldera_collapse_volume = Float64(_t1_caldera_collapse_volume - _t0_caldera_collapse_volume) / Float64(N)
    print("MOJO_TIMING volcanology::caldera_collapse_volume", _ns_caldera_collapse_volume, _acc_caldera_collapse_volume)
    var _result_caldera_collapse_volume = caldera_collapse_volume(0.5, 0.5)
    var _summary_caldera_collapse_volume = _summary_float64(_result_caldera_collapse_volume)
    print("MOJO_RESULT volcanology::caldera_collapse_volume", _summary_caldera_collapse_volume)
