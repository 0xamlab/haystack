"""bench_image_ops.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from image_ops import convolve_2d, sobel_x_kernel, sobel_y_kernel, gaussian_kernel_3x3, sharpen_kernel, histogram, threshold, invert, brightness, contrast, mean_pixel
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

def _summary_list_float64_rounded6(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64_rounded6(value[i])
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
    var _lf12_colorcheck2x2 = List[Float64]()
    _lf12_colorcheck2x2.append(200.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0)
    _lf12_colorcheck2x2.append(200.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0)
    _lf12_colorcheck2x2.append(200.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0)
    _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(200.0)
    var _lf48_video3x4x4 = List[Float64]()
    for _ in range(16):
        _lf48_video3x4x4.append(10.0)
    for pixel in range(16):
        if pixel < 4:
            _lf48_video3x4x4.append(200.0)
        else:
            _lf48_video3x4x4.append(10.0)
    for _ in range(16):
        _lf48_video3x4x4.append(200.0)
    var _lf48_video3x4x4_alt = List[Float64]()
    for _ in range(16):
        _lf48_video3x4x4_alt.append(12.0)
    for pixel in range(16):
        if pixel < 4:
            _lf48_video3x4x4_alt.append(188.0)
        else:
            _lf48_video3x4x4_alt.append(12.0)
    for _ in range(16):
        _lf48_video3x4x4_alt.append(192.0)
    var _lf25_block5x5 = List[Float64]()
    for y in range(5):
        for x in range(5):
            if y >= 1 and y <= 3 and x >= 1 and x <= 3:
                _lf25_block5x5.append(255.0)
            else:
                _lf25_block5x5.append(0.0)
    var _lf25_ring5x5 = List[Float64]()
    for y in range(5):
        for x in range(5):
            if y >= 1 and y <= 3 and x >= 1 and x <= 3 and not (y == 2 and x == 2):
                _lf25_ring5x5.append(255.0)
            else:
                _lf25_ring5x5.append(0.0)
    var _lf36_components6x6 = List[Float64]()
    for y in range(6):
        for x in range(6):
            if (x == 0 and (y == 1 or y == 2)) or ((x == 3 and (y == 1 or y == 2 or y == 3)) or (x == 4 and y == 1)):
                _lf36_components6x6.append(255.0)
            else:
                _lf36_components6x6.append(0.0)
    var _lf64_doc8x8 = List[Float64]()
    var _lf64_doc8x8_alt = List[Float64]()
    var _lf64_docmask8x8 = List[Float64]()
    for y in range(8):
        for x in range(8):
            if (y == 2 and x >= 1 and x <= 6) or (y == 5 and x >= 2 and x <= 5):
                _lf64_doc8x8.append(20.0)
                _lf64_doc8x8_alt.append(60.0)
                _lf64_docmask8x8.append(255.0)
            else:
                _lf64_doc8x8.append(240.0)
                _lf64_doc8x8_alt.append(235.0)
                _lf64_docmask8x8.append(0.0)
    var _lf36_adaptive_doc6x6 = List[Float64]()
    for y in range(6):
        for x in range(6):
            if y == 2 and x >= 2 and x <= 3:
                _lf36_adaptive_doc6x6.append(40.0)
            elif x < 3:
                _lf36_adaptive_doc6x6.append(220.0)
            else:
                _lf36_adaptive_doc6x6.append(245.0)
    var _lf36_skewmask6x6 = List[Float64]()
    for y in range(6):
        for x in range(6):
            if y >= 1 and y <= 4 and x == y:
                _lf36_skewmask6x6.append(255.0)
            else:
                _lf36_skewmask6x6.append(0.0)
    var _lf64_blobdoc8x8 = List[Float64]()
    for y in range(8):
        for x in range(8):
            if (y >= 2 and y <= 4 and x >= 1 and x <= 3) or (x == 6 and (y == 1 or y == 2)):
                _lf64_blobdoc8x8.append(20.0)
            else:
                _lf64_blobdoc8x8.append(235.0)
    var _lf64_doccolumns8x8 = List[Float64]()
    for y in range(8):
        for x in range(8):
            if y >= 1 and y <= 6 and ((x >= 1 and x <= 2) or (x >= 5 and x <= 6)):
                _lf64_doccolumns8x8.append(255.0)
            else:
                _lf64_doccolumns8x8.append(0.0)
    var _lf81_doctable9x9 = List[Float64]()
    for y in range(9):
        for x in range(9):
            if ((y >= 1 and y <= 2) or (y >= 4 and y <= 5) or (y >= 7 and y <= 8)) and ((x >= 1 and x <= 2) or (x >= 4 and x <= 5) or (x >= 7 and x <= 8)):
                _lf81_doctable9x9.append(255.0)
            else:
                _lf81_doctable9x9.append(0.0)
    var _lf256_texture16x16 = List[Float64]()
    for y in range(16):
        for x in range(16):
            if y >= 8 and x >= 8:
                _lf256_texture16x16.append(255.0 if (x + y) % 2 == 0 else 0.0)
            else:
                _lf256_texture16x16.append(64.0)
    var _lf75_video_motion3x5x5 = List[Float64]()
    for _ in range(25):
        _lf75_video_motion3x5x5.append(10.0)
    for y in range(5):
        for x in range(5):
            if y >= 1 and y <= 2 and x >= 1 and x <= 2:
                _lf75_video_motion3x5x5.append(200.0)
            else:
                _lf75_video_motion3x5x5.append(10.0)
    for y in range(5):
        for x in range(5):
            if (y >= 1 and y <= 2 and x >= 1 and x <= 2) or (x == 4 and y == 4):
                _lf75_video_motion3x5x5.append(200.0)
            else:
                _lf75_video_motion3x5x5.append(10.0)
    var _lf16_grid4x4 = List[Float64]()
    for i in range(16):
        _lf16_grid4x4.append(Float64(i))
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _li4_box_a = List[Int]()
    _li4_box_a.append(0); _li4_box_a.append(0); _li4_box_a.append(2); _li4_box_a.append(2)
    var _li4_box_b = List[Int]()
    _li4_box_b.append(1); _li4_box_b.append(1); _li4_box_b.append(3); _li4_box_b.append(3)
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
    var _llf3_imageops = List[List[Float64]]()
    _llf3_imageops.append(List[Float64]()); _llf3_imageops.append(List[Float64]()); _llf3_imageops.append(List[Float64]())
    _llf3_imageops[0].append(0.5); _llf3_imageops[0].append(0.6); _llf3_imageops[0].append(0.7)
    _llf3_imageops[1].append(0.4); _llf3_imageops[1].append(0.3); _llf3_imageops[1].append(0.2)
    _llf3_imageops[2].append(0.1); _llf3_imageops[2].append(0.2); _llf3_imageops[2].append(0.3)
    var N: Int = 5000

    var _acc_convolve_2d: Float64 = 0.0
    var _t0_convolve_2d = perf_counter_ns()
    for _ in range(N):
        var _r_convolve_2d = convolve_2d(_llf3_imageops, _llf3_imageops)
        _acc_convolve_2d += Float64(len(_r_convolve_2d))
    var _t1_convolve_2d = perf_counter_ns()
    var _ns_convolve_2d = Float64(_t1_convolve_2d - _t0_convolve_2d) / Float64(N)
    print("MOJO_TIMING image_ops::convolve_2d", _ns_convolve_2d, _acc_convolve_2d)
    var _result_convolve_2d = convolve_2d(_llf3_imageops, _llf3_imageops)
    var _summary_convolve_2d = _summary_list_list_float64(_result_convolve_2d)
    print("MOJO_RESULT image_ops::convolve_2d", _summary_convolve_2d)
    var _acc_sobel_x_kernel: Float64 = 0.0
    var _t0_sobel_x_kernel = perf_counter_ns()
    for _ in range(N):
        var _r_sobel_x_kernel = sobel_x_kernel()
        _acc_sobel_x_kernel += Float64(len(_r_sobel_x_kernel))
    var _t1_sobel_x_kernel = perf_counter_ns()
    var _ns_sobel_x_kernel = Float64(_t1_sobel_x_kernel - _t0_sobel_x_kernel) / Float64(N)
    print("MOJO_TIMING image_ops::sobel_x_kernel", _ns_sobel_x_kernel, _acc_sobel_x_kernel)
    var _result_sobel_x_kernel = sobel_x_kernel()
    var _summary_sobel_x_kernel = _summary_list_list_float64(_result_sobel_x_kernel)
    print("MOJO_RESULT image_ops::sobel_x_kernel", _summary_sobel_x_kernel)
    var _acc_sobel_y_kernel: Float64 = 0.0
    var _t0_sobel_y_kernel = perf_counter_ns()
    for _ in range(N):
        var _r_sobel_y_kernel = sobel_y_kernel()
        _acc_sobel_y_kernel += Float64(len(_r_sobel_y_kernel))
    var _t1_sobel_y_kernel = perf_counter_ns()
    var _ns_sobel_y_kernel = Float64(_t1_sobel_y_kernel - _t0_sobel_y_kernel) / Float64(N)
    print("MOJO_TIMING image_ops::sobel_y_kernel", _ns_sobel_y_kernel, _acc_sobel_y_kernel)
    var _result_sobel_y_kernel = sobel_y_kernel()
    var _summary_sobel_y_kernel = _summary_list_list_float64(_result_sobel_y_kernel)
    print("MOJO_RESULT image_ops::sobel_y_kernel", _summary_sobel_y_kernel)
    var _acc_gaussian_kernel_3x3: Float64 = 0.0
    var _t0_gaussian_kernel_3x3 = perf_counter_ns()
    for _ in range(N):
        var _r_gaussian_kernel_3x3 = gaussian_kernel_3x3()
        _acc_gaussian_kernel_3x3 += Float64(len(_r_gaussian_kernel_3x3))
    var _t1_gaussian_kernel_3x3 = perf_counter_ns()
    var _ns_gaussian_kernel_3x3 = Float64(_t1_gaussian_kernel_3x3 - _t0_gaussian_kernel_3x3) / Float64(N)
    print("MOJO_TIMING image_ops::gaussian_kernel_3x3", _ns_gaussian_kernel_3x3, _acc_gaussian_kernel_3x3)
    var _result_gaussian_kernel_3x3 = gaussian_kernel_3x3()
    var _summary_gaussian_kernel_3x3 = _summary_list_list_float64(_result_gaussian_kernel_3x3)
    print("MOJO_RESULT image_ops::gaussian_kernel_3x3", _summary_gaussian_kernel_3x3)
    var _acc_sharpen_kernel: Float64 = 0.0
    var _t0_sharpen_kernel = perf_counter_ns()
    for _ in range(N):
        var _r_sharpen_kernel = sharpen_kernel()
        _acc_sharpen_kernel += Float64(len(_r_sharpen_kernel))
    var _t1_sharpen_kernel = perf_counter_ns()
    var _ns_sharpen_kernel = Float64(_t1_sharpen_kernel - _t0_sharpen_kernel) / Float64(N)
    print("MOJO_TIMING image_ops::sharpen_kernel", _ns_sharpen_kernel, _acc_sharpen_kernel)
    var _result_sharpen_kernel = sharpen_kernel()
    var _summary_sharpen_kernel = _summary_list_list_float64(_result_sharpen_kernel)
    print("MOJO_RESULT image_ops::sharpen_kernel", _summary_sharpen_kernel)
    var _acc_histogram: Float64 = 0.0
    var _t0_histogram = perf_counter_ns()
    for _ in range(N):
        var _r_histogram = histogram(_llf3_imageops, 5)
        _acc_histogram += Float64(len(_r_histogram))
    var _t1_histogram = perf_counter_ns()
    var _ns_histogram = Float64(_t1_histogram - _t0_histogram) / Float64(N)
    print("MOJO_TIMING image_ops::histogram", _ns_histogram, _acc_histogram)
    var _result_histogram = histogram(_llf3_imageops, 5)
    var _summary_histogram = _summary_list_int(_result_histogram)
    print("MOJO_RESULT image_ops::histogram", _summary_histogram)
    var _acc_threshold: Float64 = 0.0
    var _t0_threshold = perf_counter_ns()
    for _ in range(N):
        var _r_threshold = threshold(_llf3_imageops, 0.5)
        _acc_threshold += Float64(len(_r_threshold))
    var _t1_threshold = perf_counter_ns()
    var _ns_threshold = Float64(_t1_threshold - _t0_threshold) / Float64(N)
    print("MOJO_TIMING image_ops::threshold", _ns_threshold, _acc_threshold)
    var _result_threshold = threshold(_llf3_imageops, 0.5)
    var _summary_threshold = _summary_list_list_float64(_result_threshold)
    print("MOJO_RESULT image_ops::threshold", _summary_threshold)
    var _acc_invert: Float64 = 0.0
    var _t0_invert = perf_counter_ns()
    for _ in range(N):
        var _r_invert = invert(_llf3_imageops)
        _acc_invert += Float64(len(_r_invert))
    var _t1_invert = perf_counter_ns()
    var _ns_invert = Float64(_t1_invert - _t0_invert) / Float64(N)
    print("MOJO_TIMING image_ops::invert", _ns_invert, _acc_invert)
    var _result_invert = invert(_llf3_imageops)
    var _summary_invert = _summary_list_list_float64(_result_invert)
    print("MOJO_RESULT image_ops::invert", _summary_invert)
    var _acc_brightness: Float64 = 0.0
    var _t0_brightness = perf_counter_ns()
    for _ in range(N):
        var _r_brightness = brightness(_llf3_imageops, 0.5)
        _acc_brightness += Float64(len(_r_brightness))
    var _t1_brightness = perf_counter_ns()
    var _ns_brightness = Float64(_t1_brightness - _t0_brightness) / Float64(N)
    print("MOJO_TIMING image_ops::brightness", _ns_brightness, _acc_brightness)
    var _result_brightness = brightness(_llf3_imageops, 0.5)
    var _summary_brightness = _summary_list_list_float64(_result_brightness)
    print("MOJO_RESULT image_ops::brightness", _summary_brightness)
    var _acc_contrast: Float64 = 0.0
    var _t0_contrast = perf_counter_ns()
    for _ in range(N):
        var _r_contrast = contrast(_llf3_imageops, 0.5)
        _acc_contrast += Float64(len(_r_contrast))
    var _t1_contrast = perf_counter_ns()
    var _ns_contrast = Float64(_t1_contrast - _t0_contrast) / Float64(N)
    print("MOJO_TIMING image_ops::contrast", _ns_contrast, _acc_contrast)
    var _result_contrast = contrast(_llf3_imageops, 0.5)
    var _summary_contrast = _summary_list_list_float64(_result_contrast)
    print("MOJO_RESULT image_ops::contrast", _summary_contrast)
    var _acc_mean_pixel: Float64 = 0.0
    var _t0_mean_pixel = perf_counter_ns()
    for _ in range(N):
        _acc_mean_pixel += mean_pixel(_llf3_imageops)
    var _t1_mean_pixel = perf_counter_ns()
    var _ns_mean_pixel = Float64(_t1_mean_pixel - _t0_mean_pixel) / Float64(N)
    print("MOJO_TIMING image_ops::mean_pixel", _ns_mean_pixel, _acc_mean_pixel)
    var _result_mean_pixel = mean_pixel(_llf3_imageops)
    var _summary_mean_pixel = _summary_float64(_result_mean_pixel)
    print("MOJO_RESULT image_ops::mean_pixel", _summary_mean_pixel)
