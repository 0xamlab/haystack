"""bench_nanotechnology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from nanotechnology import surface_to_volume_sphere, nanoparticle_surface_area, nanoparticle_volume, specific_surface_area, quantum_confinement_energy, mean_free_path, knudsen_number, van_der_waals_force, diffusion_coefficient_stokes_einstein, zeta_potential_mobility, aspect_ratio, packing_fraction_fcc
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

    var _acc_surface_to_volume_sphere: Float64 = 0.0
    var _t0_surface_to_volume_sphere = perf_counter_ns()
    for _ in range(N):
        _acc_surface_to_volume_sphere += surface_to_volume_sphere(0.5)
    var _t1_surface_to_volume_sphere = perf_counter_ns()
    var _ns_surface_to_volume_sphere = Float64(_t1_surface_to_volume_sphere - _t0_surface_to_volume_sphere) / Float64(N)
    print("MOJO_TIMING nanotechnology::surface_to_volume_sphere", _ns_surface_to_volume_sphere, _acc_surface_to_volume_sphere)
    var _acc_nanoparticle_surface_area: Float64 = 0.0
    var _t0_nanoparticle_surface_area = perf_counter_ns()
    for _ in range(N):
        _acc_nanoparticle_surface_area += nanoparticle_surface_area(0.5)
    var _t1_nanoparticle_surface_area = perf_counter_ns()
    var _ns_nanoparticle_surface_area = Float64(_t1_nanoparticle_surface_area - _t0_nanoparticle_surface_area) / Float64(N)
    print("MOJO_TIMING nanotechnology::nanoparticle_surface_area", _ns_nanoparticle_surface_area, _acc_nanoparticle_surface_area)
    var _acc_nanoparticle_volume: Float64 = 0.0
    var _t0_nanoparticle_volume = perf_counter_ns()
    for _ in range(N):
        _acc_nanoparticle_volume += nanoparticle_volume(0.5)
    var _t1_nanoparticle_volume = perf_counter_ns()
    var _ns_nanoparticle_volume = Float64(_t1_nanoparticle_volume - _t0_nanoparticle_volume) / Float64(N)
    print("MOJO_TIMING nanotechnology::nanoparticle_volume", _ns_nanoparticle_volume, _acc_nanoparticle_volume)
    var _acc_specific_surface_area: Float64 = 0.0
    var _t0_specific_surface_area = perf_counter_ns()
    for _ in range(N):
        _acc_specific_surface_area += specific_surface_area(0.5, 0.5)
    var _t1_specific_surface_area = perf_counter_ns()
    var _ns_specific_surface_area = Float64(_t1_specific_surface_area - _t0_specific_surface_area) / Float64(N)
    print("MOJO_TIMING nanotechnology::specific_surface_area", _ns_specific_surface_area, _acc_specific_surface_area)
    var _acc_quantum_confinement_energy: Float64 = 0.0
    var _t0_quantum_confinement_energy = perf_counter_ns()
    for _ in range(N):
        _acc_quantum_confinement_energy += quantum_confinement_energy(0.5, 0.5, 0.5)
    var _t1_quantum_confinement_energy = perf_counter_ns()
    var _ns_quantum_confinement_energy = Float64(_t1_quantum_confinement_energy - _t0_quantum_confinement_energy) / Float64(N)
    print("MOJO_TIMING nanotechnology::quantum_confinement_energy", _ns_quantum_confinement_energy, _acc_quantum_confinement_energy)
    var _acc_mean_free_path: Float64 = 0.0
    var _t0_mean_free_path = perf_counter_ns()
    for _ in range(N):
        _acc_mean_free_path += mean_free_path(0.5, 0.5, 0.5, 0.5)
    var _t1_mean_free_path = perf_counter_ns()
    var _ns_mean_free_path = Float64(_t1_mean_free_path - _t0_mean_free_path) / Float64(N)
    print("MOJO_TIMING nanotechnology::mean_free_path", _ns_mean_free_path, _acc_mean_free_path)
    var _acc_knudsen_number: Float64 = 0.0
    var _t0_knudsen_number = perf_counter_ns()
    for _ in range(N):
        _acc_knudsen_number += knudsen_number(0.5, 0.5)
    var _t1_knudsen_number = perf_counter_ns()
    var _ns_knudsen_number = Float64(_t1_knudsen_number - _t0_knudsen_number) / Float64(N)
    print("MOJO_TIMING nanotechnology::knudsen_number", _ns_knudsen_number, _acc_knudsen_number)
    var _acc_van_der_waals_force: Float64 = 0.0
    var _t0_van_der_waals_force = perf_counter_ns()
    for _ in range(N):
        _acc_van_der_waals_force += van_der_waals_force(0.5, 0.5, 0.5)
    var _t1_van_der_waals_force = perf_counter_ns()
    var _ns_van_der_waals_force = Float64(_t1_van_der_waals_force - _t0_van_der_waals_force) / Float64(N)
    print("MOJO_TIMING nanotechnology::van_der_waals_force", _ns_van_der_waals_force, _acc_van_der_waals_force)
    var _acc_diffusion_coefficient_stokes_einstein: Float64 = 0.0
    var _t0_diffusion_coefficient_stokes_einstein = perf_counter_ns()
    for _ in range(N):
        _acc_diffusion_coefficient_stokes_einstein += diffusion_coefficient_stokes_einstein(0.5, 0.5, 0.5, 0.5)
    var _t1_diffusion_coefficient_stokes_einstein = perf_counter_ns()
    var _ns_diffusion_coefficient_stokes_einstein = Float64(_t1_diffusion_coefficient_stokes_einstein - _t0_diffusion_coefficient_stokes_einstein) / Float64(N)
    print("MOJO_TIMING nanotechnology::diffusion_coefficient_stokes_einstein", _ns_diffusion_coefficient_stokes_einstein, _acc_diffusion_coefficient_stokes_einstein)
    var _acc_zeta_potential_mobility: Float64 = 0.0
    var _t0_zeta_potential_mobility = perf_counter_ns()
    for _ in range(N):
        _acc_zeta_potential_mobility += zeta_potential_mobility(0.5, 0.5, 0.5)
    var _t1_zeta_potential_mobility = perf_counter_ns()
    var _ns_zeta_potential_mobility = Float64(_t1_zeta_potential_mobility - _t0_zeta_potential_mobility) / Float64(N)
    print("MOJO_TIMING nanotechnology::zeta_potential_mobility", _ns_zeta_potential_mobility, _acc_zeta_potential_mobility)
    var _acc_aspect_ratio: Float64 = 0.0
    var _t0_aspect_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_aspect_ratio += aspect_ratio(0.5, 0.5)
    var _t1_aspect_ratio = perf_counter_ns()
    var _ns_aspect_ratio = Float64(_t1_aspect_ratio - _t0_aspect_ratio) / Float64(N)
    print("MOJO_TIMING nanotechnology::aspect_ratio", _ns_aspect_ratio, _acc_aspect_ratio)
    var _acc_packing_fraction_fcc: Float64 = 0.0
    var _t0_packing_fraction_fcc = perf_counter_ns()
    for _ in range(N):
        _acc_packing_fraction_fcc += packing_fraction_fcc()
    var _t1_packing_fraction_fcc = perf_counter_ns()
    var _ns_packing_fraction_fcc = Float64(_t1_packing_fraction_fcc - _t0_packing_fraction_fcc) / Float64(N)
    print("MOJO_TIMING nanotechnology::packing_fraction_fcc", _ns_packing_fraction_fcc, _acc_packing_fraction_fcc)
