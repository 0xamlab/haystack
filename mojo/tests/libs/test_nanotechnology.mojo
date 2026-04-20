"""test_nanotechnology.mojo — auto-generated tests for nanotechnology library."""
from std.math import isnan, isinf
from nanotechnology import surface_to_volume_sphere, nanoparticle_surface_area, nanoparticle_volume, specific_surface_area, quantum_confinement_energy, mean_free_path, knudsen_number, van_der_waals_force, diffusion_coefficient_stokes_einstein, zeta_potential_mobility, aspect_ratio, packing_fraction_fcc

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_surface_to_volume_sphere = surface_to_volume_sphere(0.5)
    if is_finite(_v_surface_to_volume_sphere): passed += 1; print("  ✅ nanotechnology::surface_to_volume_sphere =", _v_surface_to_volume_sphere)
    else: failed += 1; print("  ❌ nanotechnology::surface_to_volume_sphere → non-finite:", _v_surface_to_volume_sphere)
    var _v_nanoparticle_surface_area = nanoparticle_surface_area(0.5)
    if is_finite(_v_nanoparticle_surface_area): passed += 1; print("  ✅ nanotechnology::nanoparticle_surface_area =", _v_nanoparticle_surface_area)
    else: failed += 1; print("  ❌ nanotechnology::nanoparticle_surface_area → non-finite:", _v_nanoparticle_surface_area)
    var _v_nanoparticle_volume = nanoparticle_volume(0.5)
    if is_finite(_v_nanoparticle_volume): passed += 1; print("  ✅ nanotechnology::nanoparticle_volume =", _v_nanoparticle_volume)
    else: failed += 1; print("  ❌ nanotechnology::nanoparticle_volume → non-finite:", _v_nanoparticle_volume)
    var _v_specific_surface_area = specific_surface_area(0.5, 0.5)
    if is_finite(_v_specific_surface_area): passed += 1; print("  ✅ nanotechnology::specific_surface_area =", _v_specific_surface_area)
    else: failed += 1; print("  ❌ nanotechnology::specific_surface_area → non-finite:", _v_specific_surface_area)
    var _v_quantum_confinement_energy = quantum_confinement_energy(0.5, 0.5, 0.5)
    if is_finite(_v_quantum_confinement_energy): passed += 1; print("  ✅ nanotechnology::quantum_confinement_energy =", _v_quantum_confinement_energy)
    else: failed += 1; print("  ❌ nanotechnology::quantum_confinement_energy → non-finite:", _v_quantum_confinement_energy)
    var _v_mean_free_path = mean_free_path(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_mean_free_path): passed += 1; print("  ✅ nanotechnology::mean_free_path =", _v_mean_free_path)
    else: failed += 1; print("  ❌ nanotechnology::mean_free_path → non-finite:", _v_mean_free_path)
    var _v_knudsen_number = knudsen_number(0.5, 0.5)
    if is_finite(_v_knudsen_number): passed += 1; print("  ✅ nanotechnology::knudsen_number =", _v_knudsen_number)
    else: failed += 1; print("  ❌ nanotechnology::knudsen_number → non-finite:", _v_knudsen_number)
    var _v_van_der_waals_force = van_der_waals_force(0.5, 0.5, 0.5)
    if is_finite(_v_van_der_waals_force): passed += 1; print("  ✅ nanotechnology::van_der_waals_force =", _v_van_der_waals_force)
    else: failed += 1; print("  ❌ nanotechnology::van_der_waals_force → non-finite:", _v_van_der_waals_force)
    var _v_diffusion_coefficient_stokes_einstein = diffusion_coefficient_stokes_einstein(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_diffusion_coefficient_stokes_einstein): passed += 1; print("  ✅ nanotechnology::diffusion_coefficient_stokes_einstein =", _v_diffusion_coefficient_stokes_einstein)
    else: failed += 1; print("  ❌ nanotechnology::diffusion_coefficient_stokes_einstein → non-finite:", _v_diffusion_coefficient_stokes_einstein)
    var _v_zeta_potential_mobility = zeta_potential_mobility(0.5, 0.5, 0.5)
    if is_finite(_v_zeta_potential_mobility): passed += 1; print("  ✅ nanotechnology::zeta_potential_mobility =", _v_zeta_potential_mobility)
    else: failed += 1; print("  ❌ nanotechnology::zeta_potential_mobility → non-finite:", _v_zeta_potential_mobility)
    var _v_aspect_ratio = aspect_ratio(0.5, 0.5)
    if is_finite(_v_aspect_ratio): passed += 1; print("  ✅ nanotechnology::aspect_ratio =", _v_aspect_ratio)
    else: failed += 1; print("  ❌ nanotechnology::aspect_ratio → non-finite:", _v_aspect_ratio)
    var _v_packing_fraction_fcc = packing_fraction_fcc()
    if is_finite(_v_packing_fraction_fcc): passed += 1; print("  ✅ nanotechnology::packing_fraction_fcc =", _v_packing_fraction_fcc)
    else: failed += 1; print("  ❌ nanotechnology::packing_fraction_fcc → non-finite:", _v_packing_fraction_fcc)

    print("  [nanotechnology] Passed:", passed, "Failed:", failed)
