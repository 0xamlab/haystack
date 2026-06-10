"""bench_image_resize.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from image_resize import reshape_to_grid, flatten_grid, box_downscale, bilinear_downscale, resize_for_hash, resize_for_dhash, integral_image, box_sum, downscale_flat
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_reshape_to_grid: Float64 = 0.0
    var _t0_reshape_to_grid = perf_counter_ns()
    for _ in range(N):
        var _r_reshape_to_grid = reshape_to_grid(_lf5, 5, 5)
        _acc_reshape_to_grid += Float64(len(_r_reshape_to_grid))
    var _t1_reshape_to_grid = perf_counter_ns()
    var _ns_reshape_to_grid = Float64(_t1_reshape_to_grid - _t0_reshape_to_grid) / Float64(N)
    print("MOJO_TIMING image_resize::reshape_to_grid", _ns_reshape_to_grid, _acc_reshape_to_grid)
    var _result_reshape_to_grid = reshape_to_grid(_lf5, 5, 5)
    var _summary_reshape_to_grid = _summary_list_list_float64(_result_reshape_to_grid)
    print("MOJO_RESULT image_resize::reshape_to_grid", _summary_reshape_to_grid)
    var _acc_flatten_grid: Float64 = 0.0
    var _t0_flatten_grid = perf_counter_ns()
    for _ in range(N):
        var _r_flatten_grid = flatten_grid([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_flatten_grid += Float64(len(_r_flatten_grid))
    var _t1_flatten_grid = perf_counter_ns()
    var _ns_flatten_grid = Float64(_t1_flatten_grid - _t0_flatten_grid) / Float64(N)
    print("MOJO_TIMING image_resize::flatten_grid", _ns_flatten_grid, _acc_flatten_grid)
    var _result_flatten_grid = flatten_grid([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_flatten_grid = _summary_list_float64(_result_flatten_grid)
    print("MOJO_RESULT image_resize::flatten_grid", _summary_flatten_grid)
    var _acc_box_downscale: Float64 = 0.0
    var _t0_box_downscale = perf_counter_ns()
    for _ in range(N):
        var _r_box_downscale = box_downscale([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 5)
        _acc_box_downscale += Float64(len(_r_box_downscale))
    var _t1_box_downscale = perf_counter_ns()
    var _ns_box_downscale = Float64(_t1_box_downscale - _t0_box_downscale) / Float64(N)
    print("MOJO_TIMING image_resize::box_downscale", _ns_box_downscale, _acc_box_downscale)
    var _result_box_downscale = box_downscale([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 5)
    var _summary_box_downscale = _summary_list_list_float64(_result_box_downscale)
    print("MOJO_RESULT image_resize::box_downscale", _summary_box_downscale)
    var _acc_bilinear_downscale: Float64 = 0.0
    var _t0_bilinear_downscale = perf_counter_ns()
    for _ in range(N):
        var _r_bilinear_downscale = bilinear_downscale([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 5)
        _acc_bilinear_downscale += Float64(len(_r_bilinear_downscale))
    var _t1_bilinear_downscale = perf_counter_ns()
    var _ns_bilinear_downscale = Float64(_t1_bilinear_downscale - _t0_bilinear_downscale) / Float64(N)
    print("MOJO_TIMING image_resize::bilinear_downscale", _ns_bilinear_downscale, _acc_bilinear_downscale)
    var _result_bilinear_downscale = bilinear_downscale([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 5)
    var _summary_bilinear_downscale = _summary_list_list_float64(_result_bilinear_downscale)
    print("MOJO_RESULT image_resize::bilinear_downscale", _summary_bilinear_downscale)
    var _acc_resize_for_hash: Float64 = 0.0
    var _t0_resize_for_hash = perf_counter_ns()
    for _ in range(N):
        var _r_resize_for_hash = resize_for_hash([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5)
        _acc_resize_for_hash += Float64(len(_r_resize_for_hash))
    var _t1_resize_for_hash = perf_counter_ns()
    var _ns_resize_for_hash = Float64(_t1_resize_for_hash - _t0_resize_for_hash) / Float64(N)
    print("MOJO_TIMING image_resize::resize_for_hash", _ns_resize_for_hash, _acc_resize_for_hash)
    var _result_resize_for_hash = resize_for_hash([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5)
    var _summary_resize_for_hash = _summary_list_list_float64(_result_resize_for_hash)
    print("MOJO_RESULT image_resize::resize_for_hash", _summary_resize_for_hash)
    var _acc_resize_for_dhash: Float64 = 0.0
    var _t0_resize_for_dhash = perf_counter_ns()
    for _ in range(N):
        var _r_resize_for_dhash = resize_for_dhash([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 5)
        _acc_resize_for_dhash += Float64(len(_r_resize_for_dhash))
    var _t1_resize_for_dhash = perf_counter_ns()
    var _ns_resize_for_dhash = Float64(_t1_resize_for_dhash - _t0_resize_for_dhash) / Float64(N)
    print("MOJO_TIMING image_resize::resize_for_dhash", _ns_resize_for_dhash, _acc_resize_for_dhash)
    var _result_resize_for_dhash = resize_for_dhash([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 5)
    var _summary_resize_for_dhash = _summary_list_list_float64(_result_resize_for_dhash)
    print("MOJO_RESULT image_resize::resize_for_dhash", _summary_resize_for_dhash)
    var _acc_integral_image: Float64 = 0.0
    var _t0_integral_image = perf_counter_ns()
    for _ in range(N):
        var _r_integral_image = integral_image([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_integral_image += Float64(len(_r_integral_image))
    var _t1_integral_image = perf_counter_ns()
    var _ns_integral_image = Float64(_t1_integral_image - _t0_integral_image) / Float64(N)
    print("MOJO_TIMING image_resize::integral_image", _ns_integral_image, _acc_integral_image)
    var _result_integral_image = integral_image([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_integral_image = _summary_list_list_float64(_result_integral_image)
    print("MOJO_RESULT image_resize::integral_image", _summary_integral_image)
    var _acc_box_sum: Float64 = 0.0
    var _t0_box_sum = perf_counter_ns()
    for _ in range(N):
        _acc_box_sum += box_sum([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 5, 5, 5)
    var _t1_box_sum = perf_counter_ns()
    var _ns_box_sum = Float64(_t1_box_sum - _t0_box_sum) / Float64(N)
    print("MOJO_TIMING image_resize::box_sum", _ns_box_sum, _acc_box_sum)
    var _result_box_sum = box_sum([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 5, 5, 5)
    var _summary_box_sum = _summary_float64(_result_box_sum)
    print("MOJO_RESULT image_resize::box_sum", _summary_box_sum)
    var _acc_downscale_flat: Float64 = 0.0
    var _t0_downscale_flat = perf_counter_ns()
    for _ in range(N):
        var _r_downscale_flat = downscale_flat(_lf5, 5, 5, 5, 5)
        _acc_downscale_flat += Float64(len(_r_downscale_flat))
    var _t1_downscale_flat = perf_counter_ns()
    var _ns_downscale_flat = Float64(_t1_downscale_flat - _t0_downscale_flat) / Float64(N)
    print("MOJO_TIMING image_resize::downscale_flat", _ns_downscale_flat, _acc_downscale_flat)
    var _result_downscale_flat = downscale_flat(_lf5, 5, 5, 5, 5)
    var _summary_downscale_flat = _summary_list_float64(_result_downscale_flat)
    print("MOJO_RESULT image_resize::downscale_flat", _summary_downscale_flat)
