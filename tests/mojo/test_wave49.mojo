"""Tests for Wave 49 — Sparse Vectors, Climate Calculations, PDEs."""

from sparse_vector import (
    sv_dot,
    sv_add,
    sv_scale,
    sv_norm,
    sv_cosine,
    sv_to_dense,
    dense_to_sparse,
    sv_nnz,
    sv_sparsity,
    sv_max,
)
from climate import (
    heat_index,
    wind_chill,
    dew_point,
    wet_bulb_approx,
    celsius_to_fahrenheit,
    fahrenheit_to_celsius,
    saturation_vapor_pressure,
    relative_humidity,
    apparent_temperature,
    cloud_base_height,
    pressure_altitude,
)
from pde import (
    heat_equation_1d,
    wave_equation_1d,
    laplace_2d,
    diffusion_cfl,
    wave_cfl,
    is_stable_heat,
    finite_difference_second,
    gaussian_initial,
    max_norm,
    energy,
)

from std.math import abs as fabs, exp, sqrt


# ── Helpers ──────────────────────────────────────────────────────────────────


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


fn _assert_eq(a: Int, b: Int, msg: String) raises:
    if a != b:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


fn _li2(a: Int, b: Int) -> List[Int]:
    var r = List[Int]()
    r.append(a); r.append(b)
    return r^


fn _li3(a: Int, b: Int, c: Int) -> List[Int]:
    var r = List[Int]()
    r.append(a); r.append(b); r.append(c)
    return r^


fn _lf2(a: Float64, b: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a); r.append(b)
    return r^


fn _lf3(a: Float64, b: Float64, c: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a); r.append(b); r.append(c)
    return r^


fn _lf5(a: Float64, b: Float64, c: Float64, d: Float64, e: Float64) -> List[Float64]:
    var r = List[Float64]()
    r.append(a); r.append(b); r.append(c); r.append(d); r.append(e)
    return r^


# ── Sparse vector tests ─────────────────────────────────────────────────────


fn test_sparse_vector() raises:
    print("Testing sparse_vector...")

    # 1. sv_dot of orthogonal vectors == 0
    var ia = _li2(0, 2)
    var va = _lf2(1.0, 3.0)
    var ib = _li2(1, 3)
    var vb = _lf2(2.0, 4.0)
    _assert_close(sv_dot(ia, va, ib, vb), 0.0, 1e-12, "sv_dot orthogonal == 0")

    # 2. sv_dot of same vector == norm²
    var ic = _li3(0, 1, 2)
    var vc = _lf3(3.0, 4.0, 0.0)
    var dot_self = sv_dot(ic, vc, ic, vc)
    var norm_c = sv_norm(vc)
    _assert_close(dot_self, norm_c * norm_c, 1e-12, "sv_dot self == norm²")

    # 3. sv_dot with overlap
    var id1 = _li3(0, 1, 3)
    var vd1 = _lf3(1.0, 2.0, 3.0)
    var id2 = _li3(1, 2, 3)
    var vd2 = _lf3(4.0, 5.0, 6.0)
    _assert_close(sv_dot(id1, vd1, id2, vd2), 2.0 * 4.0 + 3.0 * 6.0, 1e-12, "sv_dot overlap")

    # 4. sv_to_dense basic
    var idx_e = _li2(1, 3)
    var val_e = _lf2(5.0, 7.0)
    var dense = sv_to_dense(idx_e, val_e, 5)
    _assert_close(dense[0], 0.0, 1e-15, "sv_to_dense[0]")
    _assert_close(dense[1], 5.0, 1e-15, "sv_to_dense[1]")
    _assert_close(dense[3], 7.0, 1e-15, "sv_to_dense[3]")

    # 5. sv_to_dense then dense_to_sparse roundtrip
    var sparse_rt = dense_to_sparse(dense)
    var rt_idx = sparse_rt[0].copy()
    var rt_val = sparse_rt[1].copy()
    _assert_eq(len(rt_idx), 2, "roundtrip nnz count")
    _assert_close(rt_idx[0], 1.0, 1e-15, "roundtrip idx[0]")
    _assert_close(rt_val[0], 5.0, 1e-15, "roundtrip val[0]")
    _assert_close(rt_idx[1], 3.0, 1e-15, "roundtrip idx[1]")
    _assert_close(rt_val[1], 7.0, 1e-15, "roundtrip val[1]")

    # 6. sv_cosine of identical vectors ≈ 1.0
    var if_ = _li3(0, 2, 4)
    var vf = _lf3(1.0, 2.0, 3.0)
    _assert_close(sv_cosine(if_, vf, if_, vf), 1.0, 1e-12, "sv_cosine identical == 1")

    # 7. sv_cosine of orthogonal == 0
    _assert_close(sv_cosine(ia, va, ib, vb), 0.0, 1e-12, "sv_cosine orthogonal == 0")

    # 8. sv_scale by 2 doubles all values
    var vals_g = _lf3(1.0, 2.0, 3.0)
    var scaled = sv_scale(vals_g, 2.0)
    _assert_close(scaled[0], 2.0, 1e-15, "sv_scale[0]")
    _assert_close(scaled[1], 4.0, 1e-15, "sv_scale[1]")
    _assert_close(scaled[2], 6.0, 1e-15, "sv_scale[2]")

    # 9. sv_scale by 0
    var scaled0 = sv_scale(vals_g, 0.0)
    _assert_close(scaled0[0], 0.0, 1e-15, "sv_scale by 0")

    # 10. sv_nnz correct count
    var vals_h = _lf3(1.0, 0.0, 3.0)
    _assert_eq(sv_nnz(vals_h), 2, "sv_nnz count")

    # 11. sv_nnz all non-zero
    _assert_eq(sv_nnz(vals_g), 3, "sv_nnz all nonzero")

    # 12. sv_sparsity of all-zero vector == 1.0
    _assert_close(sv_sparsity(0, 100), 1.0, 1e-15, "sv_sparsity all-zero == 1")

    # 13. sv_sparsity of full vector == 0.0
    _assert_close(sv_sparsity(10, 10), 0.0, 1e-15, "sv_sparsity full == 0")

    # 14. sv_sparsity partial
    _assert_close(sv_sparsity(2, 10), 0.8, 1e-15, "sv_sparsity partial")

    # 15. sv_norm
    var vals_n = _lf2(3.0, 4.0)
    _assert_close(sv_norm(vals_n), 5.0, 1e-12, "sv_norm 3-4-5")

    # 16. sv_max
    var vals_m = _lf3(-1.0, 5.0, 3.0)
    _assert_close(sv_max(vals_m), 5.0, 1e-15, "sv_max")

    # 17. sv_max negative
    var vals_neg = _lf2(-5.0, -2.0)
    _assert_close(sv_max(vals_neg), -2.0, 1e-15, "sv_max negative")

    # 18. sv_add basic merge
    var add_r = sv_add(_li2(0, 2), _lf2(1.0, 3.0), _li2(1, 3), _lf2(2.0, 4.0))
    _assert_eq(len(add_r[0]), 4, "sv_add merge len")

    # 19. sv_add overlap sums
    var add_o = sv_add(_li2(0, 1), _lf2(1.0, 2.0), _li2(0, 1), _lf2(3.0, 4.0))
    _assert_close(add_o[1][0], 4.0, 1e-15, "sv_add overlap val[0]")
    _assert_close(add_o[1][1], 6.0, 1e-15, "sv_add overlap val[1]")

    print("  sparse_vector: all passed ✓")


# ── Climate tests ────────────────────────────────────────────────────────────


fn test_climate() raises:
    print("Testing climate...")

    # 20. celsius_to_fahrenheit(0) == 32
    _assert_close(celsius_to_fahrenheit(0.0), 32.0, 1e-12, "C2F(0)==32")

    # 21. celsius_to_fahrenheit(100) == 212
    _assert_close(celsius_to_fahrenheit(100.0), 212.0, 1e-12, "C2F(100)==212")

    # 22. fahrenheit_to_celsius(32) == 0
    _assert_close(fahrenheit_to_celsius(32.0), 0.0, 1e-12, "F2C(32)==0")

    # 23. fahrenheit_to_celsius(212) == 100
    _assert_close(fahrenheit_to_celsius(212.0), 100.0, 1e-12, "F2C(212)==100")

    # 24. roundtrip C→F→C
    _assert_close(fahrenheit_to_celsius(celsius_to_fahrenheit(37.5)), 37.5, 1e-10, "C-F-C roundtrip")

    # 25. heat_index(80, 40) ≈ 80 (low humidity → minimal change)
    var hi = heat_index(80.0, 40.0)
    _assert(fabs(hi - 80.0) < 5.0, "heat_index(80,40) near 80, got " + String(hi))

    # 26. heat_index high humidity > temp
    var hi_hot = heat_index(96.0, 80.0)
    _assert(hi_hot > 96.0, "heat_index high humidity > temp")

    # 27. wind_chill(0, 15) < 0
    var wc = wind_chill(0.0, 15.0)
    _assert(wc < 0.0, "wind_chill(0,15) < 0, got " + String(wc))

    # 28. wind_chill makes it feel colder
    _assert(wind_chill(20.0, 20.0) < 20.0, "wind_chill < air temp")

    # 29. dew_point(20, 50) < 20
    var dp = dew_point(20.0, 50.0)
    _assert(dp < 20.0, "dew_point(20,50) < 20, got " + String(dp))

    # 30. dew_point(20, 50) > -10 (reasonable)
    _assert(dp > -10.0, "dew_point(20,50) reasonable > -10")

    # 31. dew_point at 100% humidity == temp
    var dp100 = dew_point(20.0, 100.0)
    _assert_close(dp100, 20.0, 0.5, "dew_point at 100% ≈ temp")

    # 32. saturation_vapor_pressure(100) > saturation_vapor_pressure(0)
    _assert(
        saturation_vapor_pressure(100.0) > saturation_vapor_pressure(0.0),
        "SVP(100) > SVP(0)",
    )

    # 33. SVP(0) ≈ 6.1078 hPa (known value)
    _assert_close(saturation_vapor_pressure(0.0), 6.1078, 0.01, "SVP(0) ≈ 6.1078")

    # 34. relative_humidity(20, 20) ≈ 100%
    _assert_close(relative_humidity(20.0, 20.0), 100.0, 0.1, "RH(20,20) ≈ 100%")

    # 35. relative_humidity dew < temp → RH < 100
    var rh = relative_humidity(20.0, 10.0)
    _assert(rh < 100.0 and rh > 0.0, "RH(20,10) between 0 and 100")

    # 36. cloud_base_height positive
    var cbh = cloud_base_height(20.0, 10.0)
    _assert(cbh > 0.0, "cloud_base_height > 0")

    # 37. cloud_base_height(20, 20) == 0
    _assert_close(cloud_base_height(20.0, 20.0), 0.0, 1e-10, "cloud_base_height same temp/dew == 0")

    # 38. pressure_altitude(1013.25) ≈ 0 (sea level)
    _assert_close(pressure_altitude(1013.25), 0.0, 0.1, "pressure_altitude sea level ≈ 0")

    # 39. pressure_altitude lower pressure → higher altitude
    _assert(pressure_altitude(900.0) > pressure_altitude(1013.25), "lower pressure → higher alt")

    # 40. apparent_temperature basic
    var at = apparent_temperature(30.0, 70.0, 2.0)
    _assert(at > 20.0 and at < 50.0, "apparent_temperature reasonable range")

    # 41. wet_bulb_approx between dew_point and temp
    var wb = wet_bulb_approx(25.0, 50.0)
    _assert(wb > 0.0 and wb < 40.0, "wet_bulb reasonable range")

    print("  climate: all passed ✓")


# ── PDE tests ────────────────────────────────────────────────────────────────


fn test_pde() raises:
    print("Testing pde...")

    # 42. gaussian_initial — peak at center
    var gi = gaussian_initial(101, 0.5, 0.1)
    _assert_eq(len(gi), 101, "gaussian_initial length")
    var peak_idx = 50  # center at 0.5 on [0,1] with 101 points
    _assert(gi[peak_idx] > gi[0], "gaussian peak > boundary")
    _assert(gi[peak_idx] > gi[100], "gaussian peak > right boundary")

    # 43. gaussian peak ≈ 1.0 (exp(0) = 1)
    _assert_close(gi[peak_idx], 1.0, 1e-10, "gaussian peak ≈ 1.0")

    # 44. heat_equation_1d — energy decreases (diffusion dissipates)
    var u0_heat = gaussian_initial(51, 0.5, 0.1)
    # Set boundary to 0
    u0_heat[0] = 0.0
    u0_heat[50] = 0.0
    var dx_h: Float64 = 1.0 / 50.0
    var alpha_h: Float64 = 0.01
    var dt_h: Float64 = 0.0001  # within CFL
    var e0 = energy(u0_heat, dx_h)
    var u_final_heat = heat_equation_1d(u0_heat, alpha_h, dx_h, dt_h, 100)
    var e1 = energy(u_final_heat, dx_h)
    _assert(e1 < e0, "heat eq: energy decreases, e0=" + String(e0) + " e1=" + String(e1))

    # 45. heat_equation_1d with uniform zero IC → stays zero
    var u0_zero = List[Float64]()
    for _i in range(21):
        u0_zero.append(0.0)
    var u_zero = heat_equation_1d(u0_zero, 0.01, 0.05, 0.0001, 50)
    _assert_close(max_norm(u_zero), 0.0, 1e-15, "heat eq: zero IC stays zero")

    # 46. is_stable_heat — True for small dt
    _assert(is_stable_heat(0.01, 0.1, 0.001), "is_stable_heat small dt")

    # 47. is_stable_heat — False for large dt
    _assert(not is_stable_heat(0.01, 0.01, 1.0), "is_stable_heat large dt → False")

    # 48. diffusion_cfl positive
    var cfl_d = diffusion_cfl(0.01, 0.1)
    _assert(cfl_d > 0.0, "diffusion_cfl > 0")
    _assert_close(cfl_d, 0.5, 1e-12, "diffusion_cfl(0.01,0.1) == 0.5")

    # 49. wave_cfl positive
    var cfl_w = wave_cfl(1.0, 0.1)
    _assert(cfl_w > 0.0, "wave_cfl > 0")
    _assert_close(cfl_w, 0.1, 1e-12, "wave_cfl(1.0,0.1) == 0.1")

    # 50. finite_difference_second of parabola x² → constant 2
    var parab = List[Float64]()
    var dx_p: Float64 = 0.1
    for i in range(11):
        var x = Float64(i) * dx_p
        parab.append(x * x)
    var d2 = finite_difference_second(parab, dx_p)
    # Interior points should be ≈ 2.0
    for i in range(1, 10):
        _assert_close(d2[i], 2.0, 1e-8, "fd2 parabola[" + String(i) + "] ≈ 2")

    # 51. finite_difference_second boundaries are 0
    _assert_close(d2[0], 0.0, 1e-15, "fd2 boundary[0] == 0")
    _assert_close(d2[10], 0.0, 1e-15, "fd2 boundary[-1] == 0")

    # 52. max_norm correct
    var u_test = _lf5(-3.0, 1.0, 4.0, -5.0, 2.0)
    _assert_close(max_norm(u_test), 5.0, 1e-15, "max_norm == 5")

    # 53. max_norm of zeros
    var zeros3 = _lf3(0.0, 0.0, 0.0)
    _assert_close(max_norm(zeros3), 0.0, 1e-15, "max_norm zeros == 0")

    # 54. energy positive
    var u_en = _lf3(1.0, 2.0, 3.0)
    _assert(energy(u_en, 0.1) > 0.0, "energy > 0")

    # 55. energy value check: (1+4+9)*0.1 = 1.4
    _assert_close(energy(u_en, 0.1), 1.4, 1e-12, "energy == 1.4")

    # 56. wave_equation_1d — energy approximately preserved
    var n_w = 51
    var dx_w: Float64 = 1.0 / 50.0
    var c_w: Float64 = 1.0
    var dt_w: Float64 = 0.005  # within CFL for c=1, dx=0.02: dt_max=0.02
    var u0_wave = gaussian_initial(n_w, 0.5, 0.1)
    u0_wave[0] = 0.0
    u0_wave[n_w - 1] = 0.0
    var v0_wave = List[Float64]()
    for _i in range(n_w):
        v0_wave.append(0.0)
    var e_wave_0 = energy(u0_wave, dx_w)
    var u_wave_f = wave_equation_1d(u0_wave, v0_wave, c_w, dx_w, dt_w, 20)
    var e_wave_1 = energy(u_wave_f, dx_w)
    # Energy should be approximately preserved (within 50% for small steps)
    _assert(e_wave_1 > 0.0, "wave energy > 0 after steps")
    var ratio = e_wave_1 / e_wave_0
    _assert(ratio > 0.5 and ratio < 2.0, "wave energy roughly preserved, ratio=" + String(ratio))

    # 57. laplace_2d — interior converges toward boundary average
    var rows = 5
    var cols = 5
    var grid = List[List[Float64]]()
    for i in range(rows):
        var row = List[Float64]()
        for j in range(cols):
            if i == 0:
                row.append(100.0)  # top boundary = 100
            else:
                row.append(0.0)
        grid.append(row^)
    var solved = laplace_2d(grid, 500)
    # Interior should be between 0 and 100
    _assert(solved[2][2] > 0.0, "laplace interior > 0")
    _assert(solved[2][2] < 100.0, "laplace interior < 100")

    # 58. laplace boundary unchanged
    _assert_close(solved[0][2], 100.0, 1e-10, "laplace top boundary preserved")
    _assert_close(solved[4][2], 0.0, 1e-10, "laplace bottom boundary preserved")

    # 59. laplace symmetry (center column values symmetric)
    _assert_close(solved[2][1], solved[2][3], 1e-6, "laplace symmetry")

    # 60. wave_cfl smaller dx → smaller dt_max
    _assert(wave_cfl(1.0, 0.01) < wave_cfl(1.0, 0.1), "smaller dx → smaller cfl")

    print("  pde: all passed ✓")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("=== Wave 49 Tests ===")
    test_sparse_vector()
    test_climate()
    test_pde()
    print("=== All Wave 49 tests passed ===")
