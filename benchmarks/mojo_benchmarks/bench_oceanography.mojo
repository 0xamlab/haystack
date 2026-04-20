"""bench_oceanography.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from oceanography import seawater_density, buoyancy_frequency, tidal_force, geostrophic_velocity, ekman_depth, mixed_layer_heat_flux, salinity_from_chlorinity, wave_celerity_shallow, wave_celerity_deep, freshwater_flux
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

    var _acc_seawater_density: Float64 = 0.0
    var _t0_seawater_density = perf_counter_ns()
    for _ in range(N):
        _acc_seawater_density += seawater_density(0.5, 0.5)
    var _t1_seawater_density = perf_counter_ns()
    var _ns_seawater_density = Float64(_t1_seawater_density - _t0_seawater_density) / Float64(N)
    print("MOJO_TIMING oceanography::seawater_density", _ns_seawater_density, _acc_seawater_density)
    var _acc_buoyancy_frequency: Float64 = 0.0
    var _t0_buoyancy_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_buoyancy_frequency += buoyancy_frequency(0.5, 0.5, 0.5)
    var _t1_buoyancy_frequency = perf_counter_ns()
    var _ns_buoyancy_frequency = Float64(_t1_buoyancy_frequency - _t0_buoyancy_frequency) / Float64(N)
    print("MOJO_TIMING oceanography::buoyancy_frequency", _ns_buoyancy_frequency, _acc_buoyancy_frequency)
    var _acc_tidal_force: Float64 = 0.0
    var _t0_tidal_force = perf_counter_ns()
    for _ in range(N):
        _acc_tidal_force += tidal_force(0.5, 0.5, 0.5)
    var _t1_tidal_force = perf_counter_ns()
    var _ns_tidal_force = Float64(_t1_tidal_force - _t0_tidal_force) / Float64(N)
    print("MOJO_TIMING oceanography::tidal_force", _ns_tidal_force, _acc_tidal_force)
    var _acc_geostrophic_velocity: Float64 = 0.0
    var _t0_geostrophic_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_geostrophic_velocity += geostrophic_velocity(0.5, 0.5, 0.5)
    var _t1_geostrophic_velocity = perf_counter_ns()
    var _ns_geostrophic_velocity = Float64(_t1_geostrophic_velocity - _t0_geostrophic_velocity) / Float64(N)
    print("MOJO_TIMING oceanography::geostrophic_velocity", _ns_geostrophic_velocity, _acc_geostrophic_velocity)
    var _acc_ekman_depth: Float64 = 0.0
    var _t0_ekman_depth = perf_counter_ns()
    for _ in range(N):
        _acc_ekman_depth += ekman_depth(0.5, 0.5)
    var _t1_ekman_depth = perf_counter_ns()
    var _ns_ekman_depth = Float64(_t1_ekman_depth - _t0_ekman_depth) / Float64(N)
    print("MOJO_TIMING oceanography::ekman_depth", _ns_ekman_depth, _acc_ekman_depth)
    var _acc_mixed_layer_heat_flux: Float64 = 0.0
    var _t0_mixed_layer_heat_flux = perf_counter_ns()
    for _ in range(N):
        _acc_mixed_layer_heat_flux += mixed_layer_heat_flux(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_mixed_layer_heat_flux = perf_counter_ns()
    var _ns_mixed_layer_heat_flux = Float64(_t1_mixed_layer_heat_flux - _t0_mixed_layer_heat_flux) / Float64(N)
    print("MOJO_TIMING oceanography::mixed_layer_heat_flux", _ns_mixed_layer_heat_flux, _acc_mixed_layer_heat_flux)
    var _acc_salinity_from_chlorinity: Float64 = 0.0
    var _t0_salinity_from_chlorinity = perf_counter_ns()
    for _ in range(N):
        _acc_salinity_from_chlorinity += salinity_from_chlorinity(0.5)
    var _t1_salinity_from_chlorinity = perf_counter_ns()
    var _ns_salinity_from_chlorinity = Float64(_t1_salinity_from_chlorinity - _t0_salinity_from_chlorinity) / Float64(N)
    print("MOJO_TIMING oceanography::salinity_from_chlorinity", _ns_salinity_from_chlorinity, _acc_salinity_from_chlorinity)
    var _acc_wave_celerity_shallow: Float64 = 0.0
    var _t0_wave_celerity_shallow = perf_counter_ns()
    for _ in range(N):
        _acc_wave_celerity_shallow += wave_celerity_shallow(0.5)
    var _t1_wave_celerity_shallow = perf_counter_ns()
    var _ns_wave_celerity_shallow = Float64(_t1_wave_celerity_shallow - _t0_wave_celerity_shallow) / Float64(N)
    print("MOJO_TIMING oceanography::wave_celerity_shallow", _ns_wave_celerity_shallow, _acc_wave_celerity_shallow)
    var _acc_wave_celerity_deep: Float64 = 0.0
    var _t0_wave_celerity_deep = perf_counter_ns()
    for _ in range(N):
        _acc_wave_celerity_deep += wave_celerity_deep(0.5)
    var _t1_wave_celerity_deep = perf_counter_ns()
    var _ns_wave_celerity_deep = Float64(_t1_wave_celerity_deep - _t0_wave_celerity_deep) / Float64(N)
    print("MOJO_TIMING oceanography::wave_celerity_deep", _ns_wave_celerity_deep, _acc_wave_celerity_deep)
    var _acc_freshwater_flux: Float64 = 0.0
    var _t0_freshwater_flux = perf_counter_ns()
    for _ in range(N):
        _acc_freshwater_flux += freshwater_flux(0.5, 0.5, 0.5)
    var _t1_freshwater_flux = perf_counter_ns()
    var _ns_freshwater_flux = Float64(_t1_freshwater_flux - _t0_freshwater_flux) / Float64(N)
    print("MOJO_TIMING oceanography::freshwater_flux", _ns_freshwater_flux, _acc_freshwater_flux)
