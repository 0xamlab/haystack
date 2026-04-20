"""test_crystallography.mojo — auto-generated tests for crystallography library."""
from std.math import isnan, isinf
from crystallography import bragg_angle, d_spacing_cubic, lattice_parameter_from_d, unit_cell_volume_cubic, unit_cell_volume_tetragonal, unit_cell_volume_orthorhombic, atomic_packing_factor_fcc, atomic_packing_factor_bcc, scherrer_crystallite_size, interplanar_angle_cubic, density_from_crystal, structure_factor_magnitude

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

    var _v_bragg_angle = bragg_angle(0.5, 0.5, 0.5)
    if is_finite(_v_bragg_angle): passed += 1; print("  ✅ crystallography::bragg_angle =", _v_bragg_angle)
    else: failed += 1; print("  ❌ crystallography::bragg_angle → non-finite:", _v_bragg_angle)
    var _v_d_spacing_cubic = d_spacing_cubic(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_d_spacing_cubic): passed += 1; print("  ✅ crystallography::d_spacing_cubic =", _v_d_spacing_cubic)
    else: failed += 1; print("  ❌ crystallography::d_spacing_cubic → non-finite:", _v_d_spacing_cubic)
    var _v_lattice_parameter_from_d = lattice_parameter_from_d(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_lattice_parameter_from_d): passed += 1; print("  ✅ crystallography::lattice_parameter_from_d =", _v_lattice_parameter_from_d)
    else: failed += 1; print("  ❌ crystallography::lattice_parameter_from_d → non-finite:", _v_lattice_parameter_from_d)
    var _v_unit_cell_volume_cubic = unit_cell_volume_cubic(0.5)
    if is_finite(_v_unit_cell_volume_cubic): passed += 1; print("  ✅ crystallography::unit_cell_volume_cubic =", _v_unit_cell_volume_cubic)
    else: failed += 1; print("  ❌ crystallography::unit_cell_volume_cubic → non-finite:", _v_unit_cell_volume_cubic)
    var _v_unit_cell_volume_tetragonal = unit_cell_volume_tetragonal(0.5, 0.5)
    if is_finite(_v_unit_cell_volume_tetragonal): passed += 1; print("  ✅ crystallography::unit_cell_volume_tetragonal =", _v_unit_cell_volume_tetragonal)
    else: failed += 1; print("  ❌ crystallography::unit_cell_volume_tetragonal → non-finite:", _v_unit_cell_volume_tetragonal)
    var _v_unit_cell_volume_orthorhombic = unit_cell_volume_orthorhombic(0.5, 0.5, 0.5)
    if is_finite(_v_unit_cell_volume_orthorhombic): passed += 1; print("  ✅ crystallography::unit_cell_volume_orthorhombic =", _v_unit_cell_volume_orthorhombic)
    else: failed += 1; print("  ❌ crystallography::unit_cell_volume_orthorhombic → non-finite:", _v_unit_cell_volume_orthorhombic)
    var _v_atomic_packing_factor_fcc = atomic_packing_factor_fcc()
    if is_finite(_v_atomic_packing_factor_fcc): passed += 1; print("  ✅ crystallography::atomic_packing_factor_fcc =", _v_atomic_packing_factor_fcc)
    else: failed += 1; print("  ❌ crystallography::atomic_packing_factor_fcc → non-finite:", _v_atomic_packing_factor_fcc)
    var _v_atomic_packing_factor_bcc = atomic_packing_factor_bcc()
    if is_finite(_v_atomic_packing_factor_bcc): passed += 1; print("  ✅ crystallography::atomic_packing_factor_bcc =", _v_atomic_packing_factor_bcc)
    else: failed += 1; print("  ❌ crystallography::atomic_packing_factor_bcc → non-finite:", _v_atomic_packing_factor_bcc)
    var _v_scherrer_crystallite_size = scherrer_crystallite_size(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_scherrer_crystallite_size): passed += 1; print("  ✅ crystallography::scherrer_crystallite_size =", _v_scherrer_crystallite_size)
    else: failed += 1; print("  ❌ crystallography::scherrer_crystallite_size → non-finite:", _v_scherrer_crystallite_size)
    var _v_interplanar_angle_cubic = interplanar_angle_cubic(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_interplanar_angle_cubic): passed += 1; print("  ✅ crystallography::interplanar_angle_cubic =", _v_interplanar_angle_cubic)
    else: failed += 1; print("  ❌ crystallography::interplanar_angle_cubic → non-finite:", _v_interplanar_angle_cubic)
    var _v_density_from_crystal = density_from_crystal(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_density_from_crystal): passed += 1; print("  ✅ crystallography::density_from_crystal =", _v_density_from_crystal)
    else: failed += 1; print("  ❌ crystallography::density_from_crystal → non-finite:", _v_density_from_crystal)
    var _v_structure_factor_magnitude = structure_factor_magnitude(0.5, 0.5)
    if is_finite(_v_structure_factor_magnitude): passed += 1; print("  ✅ crystallography::structure_factor_magnitude =", _v_structure_factor_magnitude)
    else: failed += 1; print("  ❌ crystallography::structure_factor_magnitude → non-finite:", _v_structure_factor_magnitude)

    print("  [crystallography] Passed:", passed, "Failed:", failed)
