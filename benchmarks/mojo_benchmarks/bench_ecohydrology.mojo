"""bench_ecohydrology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from ecohydrology import interception_loss, transpiration_priestley_taylor, root_water_uptake, streamflow_baseflow_index, wetland_retention_time, riparian_buffer_efficiency, ecohydrological_stress, flood_pulse_benefit, water_table_depth_et, catchment_runoff_ratio
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

    var _acc_interception_loss: Float64 = 0.0
    var _t0_interception_loss = perf_counter_ns()
    for _ in range(N):
        _acc_interception_loss += interception_loss(0.5, 0.5, 0.5)
    var _t1_interception_loss = perf_counter_ns()
    var _ns_interception_loss = Float64(_t1_interception_loss - _t0_interception_loss) / Float64(N)
    print("MOJO_TIMING ecohydrology::interception_loss", _ns_interception_loss, _acc_interception_loss)
    var _acc_transpiration_priestley_taylor: Float64 = 0.0
    var _t0_transpiration_priestley_taylor = perf_counter_ns()
    for _ in range(N):
        _acc_transpiration_priestley_taylor += transpiration_priestley_taylor(0.5, 0.5, 0.5, 0.5)
    var _t1_transpiration_priestley_taylor = perf_counter_ns()
    var _ns_transpiration_priestley_taylor = Float64(_t1_transpiration_priestley_taylor - _t0_transpiration_priestley_taylor) / Float64(N)
    print("MOJO_TIMING ecohydrology::transpiration_priestley_taylor", _ns_transpiration_priestley_taylor, _acc_transpiration_priestley_taylor)
    var _acc_root_water_uptake: Float64 = 0.0
    var _t0_root_water_uptake = perf_counter_ns()
    for _ in range(N):
        _acc_root_water_uptake += root_water_uptake(0.5, 0.5, 0.5, 0.5)
    var _t1_root_water_uptake = perf_counter_ns()
    var _ns_root_water_uptake = Float64(_t1_root_water_uptake - _t0_root_water_uptake) / Float64(N)
    print("MOJO_TIMING ecohydrology::root_water_uptake", _ns_root_water_uptake, _acc_root_water_uptake)
    var _acc_streamflow_baseflow_index: Float64 = 0.0
    var _t0_streamflow_baseflow_index = perf_counter_ns()
    for _ in range(N):
        _acc_streamflow_baseflow_index += streamflow_baseflow_index(0.5, 0.5)
    var _t1_streamflow_baseflow_index = perf_counter_ns()
    var _ns_streamflow_baseflow_index = Float64(_t1_streamflow_baseflow_index - _t0_streamflow_baseflow_index) / Float64(N)
    print("MOJO_TIMING ecohydrology::streamflow_baseflow_index", _ns_streamflow_baseflow_index, _acc_streamflow_baseflow_index)
    var _acc_wetland_retention_time: Float64 = 0.0
    var _t0_wetland_retention_time = perf_counter_ns()
    for _ in range(N):
        _acc_wetland_retention_time += wetland_retention_time(0.5, 0.5)
    var _t1_wetland_retention_time = perf_counter_ns()
    var _ns_wetland_retention_time = Float64(_t1_wetland_retention_time - _t0_wetland_retention_time) / Float64(N)
    print("MOJO_TIMING ecohydrology::wetland_retention_time", _ns_wetland_retention_time, _acc_wetland_retention_time)
    var _acc_riparian_buffer_efficiency: Float64 = 0.0
    var _t0_riparian_buffer_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_riparian_buffer_efficiency += riparian_buffer_efficiency(0.5, 0.5, 0.5)
    var _t1_riparian_buffer_efficiency = perf_counter_ns()
    var _ns_riparian_buffer_efficiency = Float64(_t1_riparian_buffer_efficiency - _t0_riparian_buffer_efficiency) / Float64(N)
    print("MOJO_TIMING ecohydrology::riparian_buffer_efficiency", _ns_riparian_buffer_efficiency, _acc_riparian_buffer_efficiency)
    var _acc_ecohydrological_stress: Float64 = 0.0
    var _t0_ecohydrological_stress = perf_counter_ns()
    for _ in range(N):
        _acc_ecohydrological_stress += ecohydrological_stress(0.5, 0.5, 0.5)
    var _t1_ecohydrological_stress = perf_counter_ns()
    var _ns_ecohydrological_stress = Float64(_t1_ecohydrological_stress - _t0_ecohydrological_stress) / Float64(N)
    print("MOJO_TIMING ecohydrology::ecohydrological_stress", _ns_ecohydrological_stress, _acc_ecohydrological_stress)
    var _acc_flood_pulse_benefit: Float64 = 0.0
    var _t0_flood_pulse_benefit = perf_counter_ns()
    for _ in range(N):
        _acc_flood_pulse_benefit += flood_pulse_benefit(0.5, 0.5, 0.5)
    var _t1_flood_pulse_benefit = perf_counter_ns()
    var _ns_flood_pulse_benefit = Float64(_t1_flood_pulse_benefit - _t0_flood_pulse_benefit) / Float64(N)
    print("MOJO_TIMING ecohydrology::flood_pulse_benefit", _ns_flood_pulse_benefit, _acc_flood_pulse_benefit)
    var _acc_water_table_depth_et: Float64 = 0.0
    var _t0_water_table_depth_et = perf_counter_ns()
    for _ in range(N):
        _acc_water_table_depth_et += water_table_depth_et(0.5, 0.5, 0.5)
    var _t1_water_table_depth_et = perf_counter_ns()
    var _ns_water_table_depth_et = Float64(_t1_water_table_depth_et - _t0_water_table_depth_et) / Float64(N)
    print("MOJO_TIMING ecohydrology::water_table_depth_et", _ns_water_table_depth_et, _acc_water_table_depth_et)
    var _acc_catchment_runoff_ratio: Float64 = 0.0
    var _t0_catchment_runoff_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_catchment_runoff_ratio += catchment_runoff_ratio(0.5, 0.5)
    var _t1_catchment_runoff_ratio = perf_counter_ns()
    var _ns_catchment_runoff_ratio = Float64(_t1_catchment_runoff_ratio - _t0_catchment_runoff_ratio) / Float64(N)
    print("MOJO_TIMING ecohydrology::catchment_runoff_ratio", _ns_catchment_runoff_ratio, _acc_catchment_runoff_ratio)
