"""bench_soil_mechanics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from soil_mechanics import bearing_capacity_terzaghi, settlement_elastic, consolidation_degree, void_ratio, relative_density, liquid_limit_plasticity, shear_strength_mohr_coulomb, lateral_earth_pressure_ka, compression_index, hydraulic_conductivity_hazen
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

    var _acc_bearing_capacity_terzaghi: Float64 = 0.0
    var _t0_bearing_capacity_terzaghi = perf_counter_ns()
    for _ in range(N):
        _acc_bearing_capacity_terzaghi += bearing_capacity_terzaghi(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_bearing_capacity_terzaghi = perf_counter_ns()
    var _ns_bearing_capacity_terzaghi = Float64(_t1_bearing_capacity_terzaghi - _t0_bearing_capacity_terzaghi) / Float64(N)
    print("MOJO_TIMING soil_mechanics::bearing_capacity_terzaghi", _ns_bearing_capacity_terzaghi, _acc_bearing_capacity_terzaghi)
    var _acc_settlement_elastic: Float64 = 0.0
    var _t0_settlement_elastic = perf_counter_ns()
    for _ in range(N):
        _acc_settlement_elastic += settlement_elastic(0.5, 0.5, 0.5, 0.5)
    var _t1_settlement_elastic = perf_counter_ns()
    var _ns_settlement_elastic = Float64(_t1_settlement_elastic - _t0_settlement_elastic) / Float64(N)
    print("MOJO_TIMING soil_mechanics::settlement_elastic", _ns_settlement_elastic, _acc_settlement_elastic)
    var _acc_consolidation_degree: Float64 = 0.0
    var _t0_consolidation_degree = perf_counter_ns()
    for _ in range(N):
        _acc_consolidation_degree += consolidation_degree(0.5)
    var _t1_consolidation_degree = perf_counter_ns()
    var _ns_consolidation_degree = Float64(_t1_consolidation_degree - _t0_consolidation_degree) / Float64(N)
    print("MOJO_TIMING soil_mechanics::consolidation_degree", _ns_consolidation_degree, _acc_consolidation_degree)
    var _acc_void_ratio: Float64 = 0.0
    var _t0_void_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_void_ratio += void_ratio(0.5, 0.5, 0.5)
    var _t1_void_ratio = perf_counter_ns()
    var _ns_void_ratio = Float64(_t1_void_ratio - _t0_void_ratio) / Float64(N)
    print("MOJO_TIMING soil_mechanics::void_ratio", _ns_void_ratio, _acc_void_ratio)
    var _acc_relative_density: Float64 = 0.0
    var _t0_relative_density = perf_counter_ns()
    for _ in range(N):
        _acc_relative_density += relative_density(0.5, 0.5, 0.5)
    var _t1_relative_density = perf_counter_ns()
    var _ns_relative_density = Float64(_t1_relative_density - _t0_relative_density) / Float64(N)
    print("MOJO_TIMING soil_mechanics::relative_density", _ns_relative_density, _acc_relative_density)
    var _acc_liquid_limit_plasticity: Float64 = 0.0
    var _t0_liquid_limit_plasticity = perf_counter_ns()
    for _ in range(N):
        _acc_liquid_limit_plasticity += liquid_limit_plasticity(0.5, 0.5)
    var _t1_liquid_limit_plasticity = perf_counter_ns()
    var _ns_liquid_limit_plasticity = Float64(_t1_liquid_limit_plasticity - _t0_liquid_limit_plasticity) / Float64(N)
    print("MOJO_TIMING soil_mechanics::liquid_limit_plasticity", _ns_liquid_limit_plasticity, _acc_liquid_limit_plasticity)
    var _acc_shear_strength_mohr_coulomb: Float64 = 0.0
    var _t0_shear_strength_mohr_coulomb = perf_counter_ns()
    for _ in range(N):
        _acc_shear_strength_mohr_coulomb += shear_strength_mohr_coulomb(0.5, 0.5, 0.5)
    var _t1_shear_strength_mohr_coulomb = perf_counter_ns()
    var _ns_shear_strength_mohr_coulomb = Float64(_t1_shear_strength_mohr_coulomb - _t0_shear_strength_mohr_coulomb) / Float64(N)
    print("MOJO_TIMING soil_mechanics::shear_strength_mohr_coulomb", _ns_shear_strength_mohr_coulomb, _acc_shear_strength_mohr_coulomb)
    var _acc_lateral_earth_pressure_ka: Float64 = 0.0
    var _t0_lateral_earth_pressure_ka = perf_counter_ns()
    for _ in range(N):
        _acc_lateral_earth_pressure_ka += lateral_earth_pressure_ka(0.5)
    var _t1_lateral_earth_pressure_ka = perf_counter_ns()
    var _ns_lateral_earth_pressure_ka = Float64(_t1_lateral_earth_pressure_ka - _t0_lateral_earth_pressure_ka) / Float64(N)
    print("MOJO_TIMING soil_mechanics::lateral_earth_pressure_ka", _ns_lateral_earth_pressure_ka, _acc_lateral_earth_pressure_ka)
    var _acc_compression_index: Float64 = 0.0
    var _t0_compression_index = perf_counter_ns()
    for _ in range(N):
        _acc_compression_index += compression_index(0.5)
    var _t1_compression_index = perf_counter_ns()
    var _ns_compression_index = Float64(_t1_compression_index - _t0_compression_index) / Float64(N)
    print("MOJO_TIMING soil_mechanics::compression_index", _ns_compression_index, _acc_compression_index)
    var _acc_hydraulic_conductivity_hazen: Float64 = 0.0
    var _t0_hydraulic_conductivity_hazen = perf_counter_ns()
    for _ in range(N):
        _acc_hydraulic_conductivity_hazen += hydraulic_conductivity_hazen(0.5)
    var _t1_hydraulic_conductivity_hazen = perf_counter_ns()
    var _ns_hydraulic_conductivity_hazen = Float64(_t1_hydraulic_conductivity_hazen - _t0_hydraulic_conductivity_hazen) / Float64(N)
    print("MOJO_TIMING soil_mechanics::hydraulic_conductivity_hazen", _ns_hydraulic_conductivity_hazen, _acc_hydraulic_conductivity_hazen)
