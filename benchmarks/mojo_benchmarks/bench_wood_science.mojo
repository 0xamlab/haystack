"""bench_wood_science.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from wood_science import moisture_content, fiber_saturation_point, shrinkage_coefficient, modulus_of_rupture, modulus_of_elasticity, wood_density_at_mc, thermal_conductivity_wood, charring_rate, section_modulus, wood_hardness_janka
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

    var _acc_moisture_content: Float64 = 0.0
    var _t0_moisture_content = perf_counter_ns()
    for _ in range(N):
        _acc_moisture_content += moisture_content(0.5, 0.5)
    var _t1_moisture_content = perf_counter_ns()
    var _ns_moisture_content = Float64(_t1_moisture_content - _t0_moisture_content) / Float64(N)
    print("MOJO_TIMING wood_science::moisture_content", _ns_moisture_content, _acc_moisture_content)
    var _acc_fiber_saturation_point: Float64 = 0.0
    var _t0_fiber_saturation_point = perf_counter_ns()
    for _ in range(N):
        _acc_fiber_saturation_point += fiber_saturation_point(0.5)
    var _t1_fiber_saturation_point = perf_counter_ns()
    var _ns_fiber_saturation_point = Float64(_t1_fiber_saturation_point - _t0_fiber_saturation_point) / Float64(N)
    print("MOJO_TIMING wood_science::fiber_saturation_point", _ns_fiber_saturation_point, _acc_fiber_saturation_point)
    var _acc_shrinkage_coefficient: Float64 = 0.0
    var _t0_shrinkage_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_shrinkage_coefficient += shrinkage_coefficient(0.5, 0.5, 0.5)
    var _t1_shrinkage_coefficient = perf_counter_ns()
    var _ns_shrinkage_coefficient = Float64(_t1_shrinkage_coefficient - _t0_shrinkage_coefficient) / Float64(N)
    print("MOJO_TIMING wood_science::shrinkage_coefficient", _ns_shrinkage_coefficient, _acc_shrinkage_coefficient)
    var _acc_modulus_of_rupture: Float64 = 0.0
    var _t0_modulus_of_rupture = perf_counter_ns()
    for _ in range(N):
        _acc_modulus_of_rupture += modulus_of_rupture(0.5, 0.5, 0.5, 0.5)
    var _t1_modulus_of_rupture = perf_counter_ns()
    var _ns_modulus_of_rupture = Float64(_t1_modulus_of_rupture - _t0_modulus_of_rupture) / Float64(N)
    print("MOJO_TIMING wood_science::modulus_of_rupture", _ns_modulus_of_rupture, _acc_modulus_of_rupture)
    var _acc_modulus_of_elasticity: Float64 = 0.0
    var _t0_modulus_of_elasticity = perf_counter_ns()
    for _ in range(N):
        _acc_modulus_of_elasticity += modulus_of_elasticity(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_modulus_of_elasticity = perf_counter_ns()
    var _ns_modulus_of_elasticity = Float64(_t1_modulus_of_elasticity - _t0_modulus_of_elasticity) / Float64(N)
    print("MOJO_TIMING wood_science::modulus_of_elasticity", _ns_modulus_of_elasticity, _acc_modulus_of_elasticity)
    var _acc_wood_density_at_mc: Float64 = 0.0
    var _t0_wood_density_at_mc = perf_counter_ns()
    for _ in range(N):
        _acc_wood_density_at_mc += wood_density_at_mc(0.5, 0.5)
    var _t1_wood_density_at_mc = perf_counter_ns()
    var _ns_wood_density_at_mc = Float64(_t1_wood_density_at_mc - _t0_wood_density_at_mc) / Float64(N)
    print("MOJO_TIMING wood_science::wood_density_at_mc", _ns_wood_density_at_mc, _acc_wood_density_at_mc)
    var _acc_thermal_conductivity_wood: Float64 = 0.0
    var _t0_thermal_conductivity_wood = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_conductivity_wood += thermal_conductivity_wood(0.5, 0.5)
    var _t1_thermal_conductivity_wood = perf_counter_ns()
    var _ns_thermal_conductivity_wood = Float64(_t1_thermal_conductivity_wood - _t0_thermal_conductivity_wood) / Float64(N)
    print("MOJO_TIMING wood_science::thermal_conductivity_wood", _ns_thermal_conductivity_wood, _acc_thermal_conductivity_wood)
    var _acc_charring_rate: Float64 = 0.0
    var _t0_charring_rate = perf_counter_ns()
    for _ in range(N):
        _acc_charring_rate += charring_rate(0.5, 0.5)
    var _t1_charring_rate = perf_counter_ns()
    var _ns_charring_rate = Float64(_t1_charring_rate - _t0_charring_rate) / Float64(N)
    print("MOJO_TIMING wood_science::charring_rate", _ns_charring_rate, _acc_charring_rate)
    var _acc_section_modulus: Float64 = 0.0
    var _t0_section_modulus = perf_counter_ns()
    for _ in range(N):
        _acc_section_modulus += section_modulus(0.5, 0.5)
    var _t1_section_modulus = perf_counter_ns()
    var _ns_section_modulus = Float64(_t1_section_modulus - _t0_section_modulus) / Float64(N)
    print("MOJO_TIMING wood_science::section_modulus", _ns_section_modulus, _acc_section_modulus)
    var _acc_wood_hardness_janka: Float64 = 0.0
    var _t0_wood_hardness_janka = perf_counter_ns()
    for _ in range(N):
        _acc_wood_hardness_janka += wood_hardness_janka(0.5)
    var _t1_wood_hardness_janka = perf_counter_ns()
    var _ns_wood_hardness_janka = Float64(_t1_wood_hardness_janka - _t0_wood_hardness_janka) / Float64(N)
    print("MOJO_TIMING wood_science::wood_hardness_janka", _ns_wood_hardness_janka, _acc_wood_hardness_janka)
