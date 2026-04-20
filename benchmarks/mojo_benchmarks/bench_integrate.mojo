"""bench_integrate.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from integrate import trapezoid, simpson, romberg, cumulative_trapezoid, integrate_poly, quad_gauss_legendre
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

    var _acc_trapezoid: Float64 = 0.0
    var _t0_trapezoid = perf_counter_ns()
    for _ in range(N):
        _acc_trapezoid += trapezoid(_lf5, 0.5)
    var _t1_trapezoid = perf_counter_ns()
    var _ns_trapezoid = Float64(_t1_trapezoid - _t0_trapezoid) / Float64(N)
    print("MOJO_TIMING integrate::trapezoid", _ns_trapezoid, _acc_trapezoid)
    var _acc_simpson: Float64 = 0.0
    var _t0_simpson = perf_counter_ns()
    for _ in range(N):
        _acc_simpson += simpson(_lf5, 0.5)
    var _t1_simpson = perf_counter_ns()
    var _ns_simpson = Float64(_t1_simpson - _t0_simpson) / Float64(N)
    print("MOJO_TIMING integrate::simpson", _ns_simpson, _acc_simpson)
    var _acc_romberg: Float64 = 0.0
    var _t0_romberg = perf_counter_ns()
    for _ in range(N):
        _acc_romberg += romberg(_lf5, 0.5, 5)
    var _t1_romberg = perf_counter_ns()
    var _ns_romberg = Float64(_t1_romberg - _t0_romberg) / Float64(N)
    print("MOJO_TIMING integrate::romberg", _ns_romberg, _acc_romberg)
    var _acc_cumulative_trapezoid: Float64 = 0.0
    var _t0_cumulative_trapezoid = perf_counter_ns()
    for _ in range(N):
        var _r_cumulative_trapezoid = cumulative_trapezoid(_lf5, 0.5)
        _acc_cumulative_trapezoid += Float64(len(_r_cumulative_trapezoid))
    var _t1_cumulative_trapezoid = perf_counter_ns()
    var _ns_cumulative_trapezoid = Float64(_t1_cumulative_trapezoid - _t0_cumulative_trapezoid) / Float64(N)
    print("MOJO_TIMING integrate::cumulative_trapezoid", _ns_cumulative_trapezoid, _acc_cumulative_trapezoid)
    var _acc_integrate_poly: Float64 = 0.0
    var _t0_integrate_poly = perf_counter_ns()
    for _ in range(N):
        _acc_integrate_poly += integrate_poly(_lf5, 0.5, 0.5)
    var _t1_integrate_poly = perf_counter_ns()
    var _ns_integrate_poly = Float64(_t1_integrate_poly - _t0_integrate_poly) / Float64(N)
    print("MOJO_TIMING integrate::integrate_poly", _ns_integrate_poly, _acc_integrate_poly)
    var _acc_quad_gauss_legendre: Float64 = 0.0
    var _t0_quad_gauss_legendre = perf_counter_ns()
    for _ in range(N):
        _acc_quad_gauss_legendre += quad_gauss_legendre(_lf5, 0.5, 0.5)
    var _t1_quad_gauss_legendre = perf_counter_ns()
    var _ns_quad_gauss_legendre = Float64(_t1_quad_gauss_legendre - _t0_quad_gauss_legendre) / Float64(N)
    print("MOJO_TIMING integrate::quad_gauss_legendre", _ns_quad_gauss_legendre, _acc_quad_gauss_legendre)
