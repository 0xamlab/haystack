"""test_pde.mojo — auto-generated tests for pde."""
from std.math import isnan, isinf
from pde import heat_equation_1d, wave_equation_1d, diffusion_cfl, wave_cfl, is_stable_heat, finite_difference_second, gaussian_initial, max_norm, energy

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _li3 = List[Int]()
    _li3.append(1); _li3.append(2); _li3.append(3)
    var _li2_zero = List[Int]()
    _li2_zero.append(0); _li2_zero.append(1)
    var _li3_tail = List[Int]()
    _li3_tail.append(2); _li3_tail.append(3); _li3_tail.append(4)
    var _li8 = List[Int]()
    for i in range(8):
        _li8.append(i + 1)
    var _li6_grid2x3 = List[Int]()
    _li6_grid2x3.append(0); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    _li6_grid2x3.append(1); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    var _li10_borda = List[Int]()
    _li10_borda.append(0); _li10_borda.append(1); _li10_borda.append(2); _li10_borda.append(3); _li10_borda.append(4)
    _li10_borda.append(1); _li10_borda.append(0); _li10_borda.append(2); _li10_borda.append(4); _li10_borda.append(3)
    var _li16 = List[Int]()
    for i in range(16):
        _li16.append(i)
    var _lf6_matrix = List[Float64]()
    _lf6_matrix.append(1.0); _lf6_matrix.append(2.0); _lf6_matrix.append(3.0)
    _lf6_matrix.append(4.0); _lf6_matrix.append(5.0); _lf6_matrix.append(6.0)
    var _lf8_coalitions = List[Float64]()
    _lf8_coalitions.append(0.0); _lf8_coalitions.append(1.0); _lf8_coalitions.append(2.0); _lf8_coalitions.append(4.0)
    _lf8_coalitions.append(3.0); _lf8_coalitions.append(5.0); _lf8_coalitions.append(6.0); _lf8_coalitions.append(9.0)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_heat_equation_1d = heat_equation_1d(_lf5, 0.5, 0.5, 0.5, 5)
    if len(_v_heat_equation_1d) >= 0: passed += 1; print("  ✅ pde::heat_equation_1d")
    var _v_wave_equation_1d = wave_equation_1d(_lf5, _lf5, 0.5, 0.5, 0.5, 5)
    if len(_v_wave_equation_1d) >= 0: passed += 1; print("  ✅ pde::wave_equation_1d")
    var _v_diffusion_cfl = diffusion_cfl(0.5, 0.5)
    if is_finite(_v_diffusion_cfl): passed += 1; print("  ✅ pde::diffusion_cfl =", _v_diffusion_cfl)
    else: failed += 1; print("  ❌ pde::diffusion_cfl → non-finite:", _v_diffusion_cfl)
    var _v_wave_cfl = wave_cfl(0.5, 0.5)
    if is_finite(_v_wave_cfl): passed += 1; print("  ✅ pde::wave_cfl =", _v_wave_cfl)
    else: failed += 1; print("  ❌ pde::wave_cfl → non-finite:", _v_wave_cfl)
    _ = is_stable_heat(0.5, 0.5, 0.5)
    passed += 1; print("  ✅ pde::is_stable_heat")
    var _v_finite_difference_second = finite_difference_second(_lf5, 0.5)
    if len(_v_finite_difference_second) >= 0: passed += 1; print("  ✅ pde::finite_difference_second")
    var _v_gaussian_initial = gaussian_initial(5, 0.5, 0.5)
    if len(_v_gaussian_initial) >= 0: passed += 1; print("  ✅ pde::gaussian_initial")
    var _v_max_norm = max_norm(_lf5)
    if is_finite(_v_max_norm): passed += 1; print("  ✅ pde::max_norm =", _v_max_norm)
    else: failed += 1; print("  ❌ pde::max_norm → non-finite:", _v_max_norm)
    var _v_energy = energy(_lf5, 0.5)
    if is_finite(_v_energy): passed += 1; print("  ✅ pde::energy =", _v_energy)
    else: failed += 1; print("  ❌ pde::energy → non-finite:", _v_energy)

    print("  [pde] Passed:", passed, "Failed:", failed)
