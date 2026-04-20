"""bench_limnology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from limnology import lake_volume_ellipsoid, hydraulic_retention_time, thermal_stratification_index, secchi_depth_estimate, trophic_state_index, phosphorus_loading, oxygen_saturation, attenuation_coefficient, lake_flushing_rate, nitrogen_fixation_rate
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

    var _acc_lake_volume_ellipsoid: Float64 = 0.0
    var _t0_lake_volume_ellipsoid = perf_counter_ns()
    for _ in range(N):
        _acc_lake_volume_ellipsoid += lake_volume_ellipsoid(0.5, 0.5, 0.5)
    var _t1_lake_volume_ellipsoid = perf_counter_ns()
    var _ns_lake_volume_ellipsoid = Float64(_t1_lake_volume_ellipsoid - _t0_lake_volume_ellipsoid) / Float64(N)
    print("MOJO_TIMING limnology::lake_volume_ellipsoid", _ns_lake_volume_ellipsoid, _acc_lake_volume_ellipsoid)
    var _acc_hydraulic_retention_time: Float64 = 0.0
    var _t0_hydraulic_retention_time = perf_counter_ns()
    for _ in range(N):
        _acc_hydraulic_retention_time += hydraulic_retention_time(0.5, 0.5)
    var _t1_hydraulic_retention_time = perf_counter_ns()
    var _ns_hydraulic_retention_time = Float64(_t1_hydraulic_retention_time - _t0_hydraulic_retention_time) / Float64(N)
    print("MOJO_TIMING limnology::hydraulic_retention_time", _ns_hydraulic_retention_time, _acc_hydraulic_retention_time)
    var _acc_thermal_stratification_index: Float64 = 0.0
    var _t0_thermal_stratification_index = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_stratification_index += thermal_stratification_index(0.5, 0.5, 0.5)
    var _t1_thermal_stratification_index = perf_counter_ns()
    var _ns_thermal_stratification_index = Float64(_t1_thermal_stratification_index - _t0_thermal_stratification_index) / Float64(N)
    print("MOJO_TIMING limnology::thermal_stratification_index", _ns_thermal_stratification_index, _acc_thermal_stratification_index)
    var _acc_secchi_depth_estimate: Float64 = 0.0
    var _t0_secchi_depth_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_secchi_depth_estimate += secchi_depth_estimate(0.5)
    var _t1_secchi_depth_estimate = perf_counter_ns()
    var _ns_secchi_depth_estimate = Float64(_t1_secchi_depth_estimate - _t0_secchi_depth_estimate) / Float64(N)
    print("MOJO_TIMING limnology::secchi_depth_estimate", _ns_secchi_depth_estimate, _acc_secchi_depth_estimate)
    var _acc_trophic_state_index: Float64 = 0.0
    var _t0_trophic_state_index = perf_counter_ns()
    for _ in range(N):
        _acc_trophic_state_index += trophic_state_index(0.5)
    var _t1_trophic_state_index = perf_counter_ns()
    var _ns_trophic_state_index = Float64(_t1_trophic_state_index - _t0_trophic_state_index) / Float64(N)
    print("MOJO_TIMING limnology::trophic_state_index", _ns_trophic_state_index, _acc_trophic_state_index)
    var _acc_phosphorus_loading: Float64 = 0.0
    var _t0_phosphorus_loading = perf_counter_ns()
    for _ in range(N):
        _acc_phosphorus_loading += phosphorus_loading(0.5, 0.5)
    var _t1_phosphorus_loading = perf_counter_ns()
    var _ns_phosphorus_loading = Float64(_t1_phosphorus_loading - _t0_phosphorus_loading) / Float64(N)
    print("MOJO_TIMING limnology::phosphorus_loading", _ns_phosphorus_loading, _acc_phosphorus_loading)
    var _acc_oxygen_saturation: Float64 = 0.0
    var _t0_oxygen_saturation = perf_counter_ns()
    for _ in range(N):
        _acc_oxygen_saturation += oxygen_saturation(0.5, 0.5)
    var _t1_oxygen_saturation = perf_counter_ns()
    var _ns_oxygen_saturation = Float64(_t1_oxygen_saturation - _t0_oxygen_saturation) / Float64(N)
    print("MOJO_TIMING limnology::oxygen_saturation", _ns_oxygen_saturation, _acc_oxygen_saturation)
    var _acc_attenuation_coefficient: Float64 = 0.0
    var _t0_attenuation_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_attenuation_coefficient += attenuation_coefficient(0.5)
    var _t1_attenuation_coefficient = perf_counter_ns()
    var _ns_attenuation_coefficient = Float64(_t1_attenuation_coefficient - _t0_attenuation_coefficient) / Float64(N)
    print("MOJO_TIMING limnology::attenuation_coefficient", _ns_attenuation_coefficient, _acc_attenuation_coefficient)
    var _acc_lake_flushing_rate: Float64 = 0.0
    var _t0_lake_flushing_rate = perf_counter_ns()
    for _ in range(N):
        _acc_lake_flushing_rate += lake_flushing_rate(0.5, 0.5)
    var _t1_lake_flushing_rate = perf_counter_ns()
    var _ns_lake_flushing_rate = Float64(_t1_lake_flushing_rate - _t0_lake_flushing_rate) / Float64(N)
    print("MOJO_TIMING limnology::lake_flushing_rate", _ns_lake_flushing_rate, _acc_lake_flushing_rate)
    var _acc_nitrogen_fixation_rate: Float64 = 0.0
    var _t0_nitrogen_fixation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_nitrogen_fixation_rate += nitrogen_fixation_rate(0.5, 0.5)
    var _t1_nitrogen_fixation_rate = perf_counter_ns()
    var _ns_nitrogen_fixation_rate = Float64(_t1_nitrogen_fixation_rate - _t0_nitrogen_fixation_rate) / Float64(N)
    print("MOJO_TIMING limnology::nitrogen_fixation_rate", _ns_nitrogen_fixation_rate, _acc_nitrogen_fixation_rate)
