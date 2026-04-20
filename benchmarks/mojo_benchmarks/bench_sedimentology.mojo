"""bench_sedimentology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from sedimentology import settling_velocity_stokes, shields_parameter, critical_shear_stress, bedload_transport, suspended_load_rouse, grain_size_phi, phi_to_mm, sorting_coefficient, skewness_folk_ward, sediment_budget
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

    var _acc_settling_velocity_stokes: Float64 = 0.0
    var _t0_settling_velocity_stokes = perf_counter_ns()
    for _ in range(N):
        _acc_settling_velocity_stokes += settling_velocity_stokes(0.5, 0.5, 0.5, 0.5)
    var _t1_settling_velocity_stokes = perf_counter_ns()
    var _ns_settling_velocity_stokes = Float64(_t1_settling_velocity_stokes - _t0_settling_velocity_stokes) / Float64(N)
    print("MOJO_TIMING sedimentology::settling_velocity_stokes", _ns_settling_velocity_stokes, _acc_settling_velocity_stokes)
    var _acc_shields_parameter: Float64 = 0.0
    var _t0_shields_parameter = perf_counter_ns()
    for _ in range(N):
        _acc_shields_parameter += shields_parameter(0.5, 0.5, 0.5, 0.5)
    var _t1_shields_parameter = perf_counter_ns()
    var _ns_shields_parameter = Float64(_t1_shields_parameter - _t0_shields_parameter) / Float64(N)
    print("MOJO_TIMING sedimentology::shields_parameter", _ns_shields_parameter, _acc_shields_parameter)
    var _acc_critical_shear_stress: Float64 = 0.0
    var _t0_critical_shear_stress = perf_counter_ns()
    for _ in range(N):
        _acc_critical_shear_stress += critical_shear_stress(0.5, 0.5, 0.5)
    var _t1_critical_shear_stress = perf_counter_ns()
    var _ns_critical_shear_stress = Float64(_t1_critical_shear_stress - _t0_critical_shear_stress) / Float64(N)
    print("MOJO_TIMING sedimentology::critical_shear_stress", _ns_critical_shear_stress, _acc_critical_shear_stress)
    var _acc_bedload_transport: Float64 = 0.0
    var _t0_bedload_transport = perf_counter_ns()
    for _ in range(N):
        _acc_bedload_transport += bedload_transport(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_bedload_transport = perf_counter_ns()
    var _ns_bedload_transport = Float64(_t1_bedload_transport - _t0_bedload_transport) / Float64(N)
    print("MOJO_TIMING sedimentology::bedload_transport", _ns_bedload_transport, _acc_bedload_transport)
    var _acc_suspended_load_rouse: Float64 = 0.0
    var _t0_suspended_load_rouse = perf_counter_ns()
    for _ in range(N):
        _acc_suspended_load_rouse += suspended_load_rouse(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_suspended_load_rouse = perf_counter_ns()
    var _ns_suspended_load_rouse = Float64(_t1_suspended_load_rouse - _t0_suspended_load_rouse) / Float64(N)
    print("MOJO_TIMING sedimentology::suspended_load_rouse", _ns_suspended_load_rouse, _acc_suspended_load_rouse)
    var _acc_grain_size_phi: Float64 = 0.0
    var _t0_grain_size_phi = perf_counter_ns()
    for _ in range(N):
        _acc_grain_size_phi += grain_size_phi(0.5)
    var _t1_grain_size_phi = perf_counter_ns()
    var _ns_grain_size_phi = Float64(_t1_grain_size_phi - _t0_grain_size_phi) / Float64(N)
    print("MOJO_TIMING sedimentology::grain_size_phi", _ns_grain_size_phi, _acc_grain_size_phi)
    var _acc_phi_to_mm: Float64 = 0.0
    var _t0_phi_to_mm = perf_counter_ns()
    for _ in range(N):
        _acc_phi_to_mm += phi_to_mm(0.5)
    var _t1_phi_to_mm = perf_counter_ns()
    var _ns_phi_to_mm = Float64(_t1_phi_to_mm - _t0_phi_to_mm) / Float64(N)
    print("MOJO_TIMING sedimentology::phi_to_mm", _ns_phi_to_mm, _acc_phi_to_mm)
    var _acc_sorting_coefficient: Float64 = 0.0
    var _t0_sorting_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_sorting_coefficient += sorting_coefficient(0.5, 0.5, 0.5, 0.5)
    var _t1_sorting_coefficient = perf_counter_ns()
    var _ns_sorting_coefficient = Float64(_t1_sorting_coefficient - _t0_sorting_coefficient) / Float64(N)
    print("MOJO_TIMING sedimentology::sorting_coefficient", _ns_sorting_coefficient, _acc_sorting_coefficient)
    var _acc_skewness_folk_ward: Float64 = 0.0
    var _t0_skewness_folk_ward = perf_counter_ns()
    for _ in range(N):
        _acc_skewness_folk_ward += skewness_folk_ward(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_skewness_folk_ward = perf_counter_ns()
    var _ns_skewness_folk_ward = Float64(_t1_skewness_folk_ward - _t0_skewness_folk_ward) / Float64(N)
    print("MOJO_TIMING sedimentology::skewness_folk_ward", _ns_skewness_folk_ward, _acc_skewness_folk_ward)
    var _acc_sediment_budget: Float64 = 0.0
    var _t0_sediment_budget = perf_counter_ns()
    for _ in range(N):
        _acc_sediment_budget += sediment_budget(0.5, 0.5, 0.5)
    var _t1_sediment_budget = perf_counter_ns()
    var _ns_sediment_budget = Float64(_t1_sediment_budget - _t0_sediment_budget) / Float64(N)
    print("MOJO_TIMING sedimentology::sediment_budget", _ns_sediment_budget, _acc_sediment_budget)
