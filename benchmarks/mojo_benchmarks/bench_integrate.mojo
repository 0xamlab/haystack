"""bench_integrate.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from integrate import trapezoid, simpson, romberg, cumulative_trapezoid, integrate_poly, quad_gauss_legendre
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_trapezoid = trapezoid(_lf5, 0.5)
    var _summary_trapezoid = _summary_float64(_result_trapezoid)
    print("MOJO_RESULT integrate::trapezoid", _summary_trapezoid)
    var _acc_simpson: Float64 = 0.0
    var _t0_simpson = perf_counter_ns()
    for _ in range(N):
        _acc_simpson += simpson(_lf5, 0.5)
    var _t1_simpson = perf_counter_ns()
    var _ns_simpson = Float64(_t1_simpson - _t0_simpson) / Float64(N)
    print("MOJO_TIMING integrate::simpson", _ns_simpson, _acc_simpson)
    var _result_simpson = simpson(_lf5, 0.5)
    var _summary_simpson = _summary_float64(_result_simpson)
    print("MOJO_RESULT integrate::simpson", _summary_simpson)
    var _acc_romberg: Float64 = 0.0
    var _t0_romberg = perf_counter_ns()
    for _ in range(N):
        _acc_romberg += romberg(_lf5, 0.5, 5)
    var _t1_romberg = perf_counter_ns()
    var _ns_romberg = Float64(_t1_romberg - _t0_romberg) / Float64(N)
    print("MOJO_TIMING integrate::romberg", _ns_romberg, _acc_romberg)
    var _result_romberg = romberg(_lf5, 0.5, 5)
    var _summary_romberg = _summary_float64(_result_romberg)
    print("MOJO_RESULT integrate::romberg", _summary_romberg)
    var _acc_cumulative_trapezoid: Float64 = 0.0
    var _t0_cumulative_trapezoid = perf_counter_ns()
    for _ in range(N):
        var _r_cumulative_trapezoid = cumulative_trapezoid(_lf5, 0.5)
        _acc_cumulative_trapezoid += Float64(len(_r_cumulative_trapezoid))
    var _t1_cumulative_trapezoid = perf_counter_ns()
    var _ns_cumulative_trapezoid = Float64(_t1_cumulative_trapezoid - _t0_cumulative_trapezoid) / Float64(N)
    print("MOJO_TIMING integrate::cumulative_trapezoid", _ns_cumulative_trapezoid, _acc_cumulative_trapezoid)
    var _result_cumulative_trapezoid = cumulative_trapezoid(_lf5, 0.5)
    var _summary_cumulative_trapezoid = _summary_list_float64(_result_cumulative_trapezoid)
    print("MOJO_RESULT integrate::cumulative_trapezoid", _summary_cumulative_trapezoid)
    var _acc_integrate_poly: Float64 = 0.0
    var _t0_integrate_poly = perf_counter_ns()
    for _ in range(N):
        _acc_integrate_poly += integrate_poly(_lf5, 0.5, 0.5)
    var _t1_integrate_poly = perf_counter_ns()
    var _ns_integrate_poly = Float64(_t1_integrate_poly - _t0_integrate_poly) / Float64(N)
    print("MOJO_TIMING integrate::integrate_poly", _ns_integrate_poly, _acc_integrate_poly)
    var _result_integrate_poly = integrate_poly(_lf5, 0.5, 0.5)
    var _summary_integrate_poly = _summary_float64(_result_integrate_poly)
    print("MOJO_RESULT integrate::integrate_poly", _summary_integrate_poly)
    var _acc_quad_gauss_legendre: Float64 = 0.0
    var _t0_quad_gauss_legendre = perf_counter_ns()
    for _ in range(N):
        _acc_quad_gauss_legendre += quad_gauss_legendre(_lf5, 0.5, 0.5)
    var _t1_quad_gauss_legendre = perf_counter_ns()
    var _ns_quad_gauss_legendre = Float64(_t1_quad_gauss_legendre - _t0_quad_gauss_legendre) / Float64(N)
    print("MOJO_TIMING integrate::quad_gauss_legendre", _ns_quad_gauss_legendre, _acc_quad_gauss_legendre)
    var _result_quad_gauss_legendre = quad_gauss_legendre(_lf5, 0.5, 0.5)
    var _summary_quad_gauss_legendre = _summary_float64(_result_quad_gauss_legendre)
    print("MOJO_RESULT integrate::quad_gauss_legendre", _summary_quad_gauss_legendre)
