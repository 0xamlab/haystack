"""bench_soil_science.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from soil_science import soil_texture_sand_silt_clay, bulk_density, particle_density_typical, total_porosity, volumetric_water_content, gravimetric_water_content, field_capacity_estimate, wilting_point_estimate, available_water, cation_exchange_capacity_estimate, soil_organic_carbon, infiltration_rate_horton
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

    var _acc_soil_texture_sand_silt_clay: Float64 = 0.0
    var _t0_soil_texture_sand_silt_clay = perf_counter_ns()
    for _ in range(N):
        _acc_soil_texture_sand_silt_clay += Float64(soil_texture_sand_silt_clay(0.5, 0.5, 0.5))
    var _t1_soil_texture_sand_silt_clay = perf_counter_ns()
    var _ns_soil_texture_sand_silt_clay = Float64(_t1_soil_texture_sand_silt_clay - _t0_soil_texture_sand_silt_clay) / Float64(N)
    print("MOJO_TIMING soil_science::soil_texture_sand_silt_clay", _ns_soil_texture_sand_silt_clay, _acc_soil_texture_sand_silt_clay)
    var _acc_bulk_density: Float64 = 0.0
    var _t0_bulk_density = perf_counter_ns()
    for _ in range(N):
        _acc_bulk_density += bulk_density(0.5, 0.5)
    var _t1_bulk_density = perf_counter_ns()
    var _ns_bulk_density = Float64(_t1_bulk_density - _t0_bulk_density) / Float64(N)
    print("MOJO_TIMING soil_science::bulk_density", _ns_bulk_density, _acc_bulk_density)
    var _acc_particle_density_typical: Float64 = 0.0
    var _t0_particle_density_typical = perf_counter_ns()
    for _ in range(N):
        _acc_particle_density_typical += particle_density_typical()
    var _t1_particle_density_typical = perf_counter_ns()
    var _ns_particle_density_typical = Float64(_t1_particle_density_typical - _t0_particle_density_typical) / Float64(N)
    print("MOJO_TIMING soil_science::particle_density_typical", _ns_particle_density_typical, _acc_particle_density_typical)
    var _acc_total_porosity: Float64 = 0.0
    var _t0_total_porosity = perf_counter_ns()
    for _ in range(N):
        _acc_total_porosity += total_porosity(0.5, 0.5)
    var _t1_total_porosity = perf_counter_ns()
    var _ns_total_porosity = Float64(_t1_total_porosity - _t0_total_porosity) / Float64(N)
    print("MOJO_TIMING soil_science::total_porosity", _ns_total_porosity, _acc_total_porosity)
    var _acc_volumetric_water_content: Float64 = 0.0
    var _t0_volumetric_water_content = perf_counter_ns()
    for _ in range(N):
        _acc_volumetric_water_content += volumetric_water_content(0.5, 0.5)
    var _t1_volumetric_water_content = perf_counter_ns()
    var _ns_volumetric_water_content = Float64(_t1_volumetric_water_content - _t0_volumetric_water_content) / Float64(N)
    print("MOJO_TIMING soil_science::volumetric_water_content", _ns_volumetric_water_content, _acc_volumetric_water_content)
    var _acc_gravimetric_water_content: Float64 = 0.0
    var _t0_gravimetric_water_content = perf_counter_ns()
    for _ in range(N):
        _acc_gravimetric_water_content += gravimetric_water_content(0.5, 0.5)
    var _t1_gravimetric_water_content = perf_counter_ns()
    var _ns_gravimetric_water_content = Float64(_t1_gravimetric_water_content - _t0_gravimetric_water_content) / Float64(N)
    print("MOJO_TIMING soil_science::gravimetric_water_content", _ns_gravimetric_water_content, _acc_gravimetric_water_content)
    var _acc_field_capacity_estimate: Float64 = 0.0
    var _t0_field_capacity_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_field_capacity_estimate += field_capacity_estimate(0.5)
    var _t1_field_capacity_estimate = perf_counter_ns()
    var _ns_field_capacity_estimate = Float64(_t1_field_capacity_estimate - _t0_field_capacity_estimate) / Float64(N)
    print("MOJO_TIMING soil_science::field_capacity_estimate", _ns_field_capacity_estimate, _acc_field_capacity_estimate)
    var _acc_wilting_point_estimate: Float64 = 0.0
    var _t0_wilting_point_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_wilting_point_estimate += wilting_point_estimate(0.5)
    var _t1_wilting_point_estimate = perf_counter_ns()
    var _ns_wilting_point_estimate = Float64(_t1_wilting_point_estimate - _t0_wilting_point_estimate) / Float64(N)
    print("MOJO_TIMING soil_science::wilting_point_estimate", _ns_wilting_point_estimate, _acc_wilting_point_estimate)
    var _acc_available_water: Float64 = 0.0
    var _t0_available_water = perf_counter_ns()
    for _ in range(N):
        _acc_available_water += available_water(0.5, 0.5, 0.5)
    var _t1_available_water = perf_counter_ns()
    var _ns_available_water = Float64(_t1_available_water - _t0_available_water) / Float64(N)
    print("MOJO_TIMING soil_science::available_water", _ns_available_water, _acc_available_water)
    var _acc_cation_exchange_capacity_estimate: Float64 = 0.0
    var _t0_cation_exchange_capacity_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_cation_exchange_capacity_estimate += cation_exchange_capacity_estimate(0.5, 0.5)
    var _t1_cation_exchange_capacity_estimate = perf_counter_ns()
    var _ns_cation_exchange_capacity_estimate = Float64(_t1_cation_exchange_capacity_estimate - _t0_cation_exchange_capacity_estimate) / Float64(N)
    print("MOJO_TIMING soil_science::cation_exchange_capacity_estimate", _ns_cation_exchange_capacity_estimate, _acc_cation_exchange_capacity_estimate)
    var _acc_soil_organic_carbon: Float64 = 0.0
    var _t0_soil_organic_carbon = perf_counter_ns()
    for _ in range(N):
        _acc_soil_organic_carbon += soil_organic_carbon(0.5)
    var _t1_soil_organic_carbon = perf_counter_ns()
    var _ns_soil_organic_carbon = Float64(_t1_soil_organic_carbon - _t0_soil_organic_carbon) / Float64(N)
    print("MOJO_TIMING soil_science::soil_organic_carbon", _ns_soil_organic_carbon, _acc_soil_organic_carbon)
    var _acc_infiltration_rate_horton: Float64 = 0.0
    var _t0_infiltration_rate_horton = perf_counter_ns()
    for _ in range(N):
        _acc_infiltration_rate_horton += infiltration_rate_horton(0.5, 0.5, 0.5, 0.5)
    var _t1_infiltration_rate_horton = perf_counter_ns()
    var _ns_infiltration_rate_horton = Float64(_t1_infiltration_rate_horton - _t0_infiltration_rate_horton) / Float64(N)
    print("MOJO_TIMING soil_science::infiltration_rate_horton", _ns_infiltration_rate_horton, _acc_infiltration_rate_horton)
