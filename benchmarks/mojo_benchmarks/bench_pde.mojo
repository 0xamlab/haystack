"""bench_pde.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pde import heat_equation_1d, wave_equation_1d, laplace_2d, diffusion_cfl, wave_cfl, is_stable_heat, finite_difference_second, gaussian_initial, max_norm, energy
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

    var _acc_heat_equation_1d: Float64 = 0.0
    var _t0_heat_equation_1d = perf_counter_ns()
    for _ in range(N):
        var _r_heat_equation_1d = heat_equation_1d(_lf5, 0.5, 0.5, 0.5, 5)
        _acc_heat_equation_1d += Float64(len(_r_heat_equation_1d))
    var _t1_heat_equation_1d = perf_counter_ns()
    var _ns_heat_equation_1d = Float64(_t1_heat_equation_1d - _t0_heat_equation_1d) / Float64(N)
    print("MOJO_TIMING pde::heat_equation_1d", _ns_heat_equation_1d, _acc_heat_equation_1d)
    var _acc_wave_equation_1d: Float64 = 0.0
    var _t0_wave_equation_1d = perf_counter_ns()
    for _ in range(N):
        var _r_wave_equation_1d = wave_equation_1d(_lf5, _lf5, 0.5, 0.5, 0.5, 5)
        _acc_wave_equation_1d += Float64(len(_r_wave_equation_1d))
    var _t1_wave_equation_1d = perf_counter_ns()
    var _ns_wave_equation_1d = Float64(_t1_wave_equation_1d - _t0_wave_equation_1d) / Float64(N)
    print("MOJO_TIMING pde::wave_equation_1d", _ns_wave_equation_1d, _acc_wave_equation_1d)
    var _acc_laplace_2d: Float64 = 0.0
    var _t0_laplace_2d = perf_counter_ns()
    for _ in range(N):
        var _r_laplace_2d = laplace_2d([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5)
        _acc_laplace_2d += Float64(len(_r_laplace_2d))
    var _t1_laplace_2d = perf_counter_ns()
    var _ns_laplace_2d = Float64(_t1_laplace_2d - _t0_laplace_2d) / Float64(N)
    print("MOJO_TIMING pde::laplace_2d", _ns_laplace_2d, _acc_laplace_2d)
    var _acc_diffusion_cfl: Float64 = 0.0
    var _t0_diffusion_cfl = perf_counter_ns()
    for _ in range(N):
        _acc_diffusion_cfl += diffusion_cfl(0.5, 0.5)
    var _t1_diffusion_cfl = perf_counter_ns()
    var _ns_diffusion_cfl = Float64(_t1_diffusion_cfl - _t0_diffusion_cfl) / Float64(N)
    print("MOJO_TIMING pde::diffusion_cfl", _ns_diffusion_cfl, _acc_diffusion_cfl)
    var _acc_wave_cfl: Float64 = 0.0
    var _t0_wave_cfl = perf_counter_ns()
    for _ in range(N):
        _acc_wave_cfl += wave_cfl(0.5, 0.5)
    var _t1_wave_cfl = perf_counter_ns()
    var _ns_wave_cfl = Float64(_t1_wave_cfl - _t0_wave_cfl) / Float64(N)
    print("MOJO_TIMING pde::wave_cfl", _ns_wave_cfl, _acc_wave_cfl)
    var _acc_is_stable_heat: Float64 = 0.0
    var _t0_is_stable_heat = perf_counter_ns()
    for _ in range(N):
        _acc_is_stable_heat += Float64(is_stable_heat(0.5, 0.5, 0.5))
    var _t1_is_stable_heat = perf_counter_ns()
    var _ns_is_stable_heat = Float64(_t1_is_stable_heat - _t0_is_stable_heat) / Float64(N)
    print("MOJO_TIMING pde::is_stable_heat", _ns_is_stable_heat, _acc_is_stable_heat)
    var _acc_finite_difference_second: Float64 = 0.0
    var _t0_finite_difference_second = perf_counter_ns()
    for _ in range(N):
        var _r_finite_difference_second = finite_difference_second(_lf5, 0.5)
        _acc_finite_difference_second += Float64(len(_r_finite_difference_second))
    var _t1_finite_difference_second = perf_counter_ns()
    var _ns_finite_difference_second = Float64(_t1_finite_difference_second - _t0_finite_difference_second) / Float64(N)
    print("MOJO_TIMING pde::finite_difference_second", _ns_finite_difference_second, _acc_finite_difference_second)
    var _acc_gaussian_initial: Float64 = 0.0
    var _t0_gaussian_initial = perf_counter_ns()
    for _ in range(N):
        var _r_gaussian_initial = gaussian_initial(5, 0.5, 0.5)
        _acc_gaussian_initial += Float64(len(_r_gaussian_initial))
    var _t1_gaussian_initial = perf_counter_ns()
    var _ns_gaussian_initial = Float64(_t1_gaussian_initial - _t0_gaussian_initial) / Float64(N)
    print("MOJO_TIMING pde::gaussian_initial", _ns_gaussian_initial, _acc_gaussian_initial)
    var _acc_max_norm: Float64 = 0.0
    var _t0_max_norm = perf_counter_ns()
    for _ in range(N):
        _acc_max_norm += max_norm(_lf5)
    var _t1_max_norm = perf_counter_ns()
    var _ns_max_norm = Float64(_t1_max_norm - _t0_max_norm) / Float64(N)
    print("MOJO_TIMING pde::max_norm", _ns_max_norm, _acc_max_norm)
    var _acc_energy: Float64 = 0.0
    var _t0_energy = perf_counter_ns()
    for _ in range(N):
        _acc_energy += energy(_lf5, 0.5)
    var _t1_energy = perf_counter_ns()
    var _ns_energy = Float64(_t1_energy - _t0_energy) / Float64(N)
    print("MOJO_TIMING pde::energy", _ns_energy, _acc_energy)
