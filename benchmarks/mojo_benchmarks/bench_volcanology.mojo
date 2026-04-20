"""bench_volcanology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from volcanology import vei_energy_estimate, lava_flow_velocity, eruption_column_height, tephra_fallout_thickness, magma_viscosity_estimate, effusion_rate, lahar_velocity, volcanic_gas_emission_rate, recurrence_interval, alert_level, pyroclastic_flow_runout, caldera_collapse_volume
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

    var _acc_vei_energy_estimate: Float64 = 0.0
    var _t0_vei_energy_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_vei_energy_estimate += vei_energy_estimate(0.5)
    var _t1_vei_energy_estimate = perf_counter_ns()
    var _ns_vei_energy_estimate = Float64(_t1_vei_energy_estimate - _t0_vei_energy_estimate) / Float64(N)
    print("MOJO_TIMING volcanology::vei_energy_estimate", _ns_vei_energy_estimate, _acc_vei_energy_estimate)
    var _acc_lava_flow_velocity: Float64 = 0.0
    var _t0_lava_flow_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_lava_flow_velocity += lava_flow_velocity(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_lava_flow_velocity = perf_counter_ns()
    var _ns_lava_flow_velocity = Float64(_t1_lava_flow_velocity - _t0_lava_flow_velocity) / Float64(N)
    print("MOJO_TIMING volcanology::lava_flow_velocity", _ns_lava_flow_velocity, _acc_lava_flow_velocity)
    var _acc_eruption_column_height: Float64 = 0.0
    var _t0_eruption_column_height = perf_counter_ns()
    for _ in range(N):
        _acc_eruption_column_height += eruption_column_height(0.5, 0.5)
    var _t1_eruption_column_height = perf_counter_ns()
    var _ns_eruption_column_height = Float64(_t1_eruption_column_height - _t0_eruption_column_height) / Float64(N)
    print("MOJO_TIMING volcanology::eruption_column_height", _ns_eruption_column_height, _acc_eruption_column_height)
    var _acc_tephra_fallout_thickness: Float64 = 0.0
    var _t0_tephra_fallout_thickness = perf_counter_ns()
    for _ in range(N):
        _acc_tephra_fallout_thickness += tephra_fallout_thickness(0.5, 0.5)
    var _t1_tephra_fallout_thickness = perf_counter_ns()
    var _ns_tephra_fallout_thickness = Float64(_t1_tephra_fallout_thickness - _t0_tephra_fallout_thickness) / Float64(N)
    print("MOJO_TIMING volcanology::tephra_fallout_thickness", _ns_tephra_fallout_thickness, _acc_tephra_fallout_thickness)
    var _acc_magma_viscosity_estimate: Float64 = 0.0
    var _t0_magma_viscosity_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_magma_viscosity_estimate += magma_viscosity_estimate(0.5)
    var _t1_magma_viscosity_estimate = perf_counter_ns()
    var _ns_magma_viscosity_estimate = Float64(_t1_magma_viscosity_estimate - _t0_magma_viscosity_estimate) / Float64(N)
    print("MOJO_TIMING volcanology::magma_viscosity_estimate", _ns_magma_viscosity_estimate, _acc_magma_viscosity_estimate)
    var _acc_effusion_rate: Float64 = 0.0
    var _t0_effusion_rate = perf_counter_ns()
    for _ in range(N):
        _acc_effusion_rate += effusion_rate(0.5, 0.5)
    var _t1_effusion_rate = perf_counter_ns()
    var _ns_effusion_rate = Float64(_t1_effusion_rate - _t0_effusion_rate) / Float64(N)
    print("MOJO_TIMING volcanology::effusion_rate", _ns_effusion_rate, _acc_effusion_rate)
    var _acc_lahar_velocity: Float64 = 0.0
    var _t0_lahar_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_lahar_velocity += lahar_velocity(0.5, 0.5)
    var _t1_lahar_velocity = perf_counter_ns()
    var _ns_lahar_velocity = Float64(_t1_lahar_velocity - _t0_lahar_velocity) / Float64(N)
    print("MOJO_TIMING volcanology::lahar_velocity", _ns_lahar_velocity, _acc_lahar_velocity)
    var _acc_volcanic_gas_emission_rate: Float64 = 0.0
    var _t0_volcanic_gas_emission_rate = perf_counter_ns()
    for _ in range(N):
        _acc_volcanic_gas_emission_rate += volcanic_gas_emission_rate(0.5, 0.5)
    var _t1_volcanic_gas_emission_rate = perf_counter_ns()
    var _ns_volcanic_gas_emission_rate = Float64(_t1_volcanic_gas_emission_rate - _t0_volcanic_gas_emission_rate) / Float64(N)
    print("MOJO_TIMING volcanology::volcanic_gas_emission_rate", _ns_volcanic_gas_emission_rate, _acc_volcanic_gas_emission_rate)
    var _acc_recurrence_interval: Float64 = 0.0
    var _t0_recurrence_interval = perf_counter_ns()
    for _ in range(N):
        _acc_recurrence_interval += recurrence_interval(0.5, 0.5)
    var _t1_recurrence_interval = perf_counter_ns()
    var _ns_recurrence_interval = Float64(_t1_recurrence_interval - _t0_recurrence_interval) / Float64(N)
    print("MOJO_TIMING volcanology::recurrence_interval", _ns_recurrence_interval, _acc_recurrence_interval)
    var _acc_alert_level: Float64 = 0.0
    var _t0_alert_level = perf_counter_ns()
    for _ in range(N):
        _acc_alert_level += alert_level(0.5, 0.5, 0.5)
    var _t1_alert_level = perf_counter_ns()
    var _ns_alert_level = Float64(_t1_alert_level - _t0_alert_level) / Float64(N)
    print("MOJO_TIMING volcanology::alert_level", _ns_alert_level, _acc_alert_level)
    var _acc_pyroclastic_flow_runout: Float64 = 0.0
    var _t0_pyroclastic_flow_runout = perf_counter_ns()
    for _ in range(N):
        _acc_pyroclastic_flow_runout += pyroclastic_flow_runout(0.5, 0.5)
    var _t1_pyroclastic_flow_runout = perf_counter_ns()
    var _ns_pyroclastic_flow_runout = Float64(_t1_pyroclastic_flow_runout - _t0_pyroclastic_flow_runout) / Float64(N)
    print("MOJO_TIMING volcanology::pyroclastic_flow_runout", _ns_pyroclastic_flow_runout, _acc_pyroclastic_flow_runout)
    var _acc_caldera_collapse_volume: Float64 = 0.0
    var _t0_caldera_collapse_volume = perf_counter_ns()
    for _ in range(N):
        _acc_caldera_collapse_volume += caldera_collapse_volume(0.5, 0.5)
    var _t1_caldera_collapse_volume = perf_counter_ns()
    var _ns_caldera_collapse_volume = Float64(_t1_caldera_collapse_volume - _t0_caldera_collapse_volume) / Float64(N)
    print("MOJO_TIMING volcanology::caldera_collapse_volume", _ns_caldera_collapse_volume, _acc_caldera_collapse_volume)
