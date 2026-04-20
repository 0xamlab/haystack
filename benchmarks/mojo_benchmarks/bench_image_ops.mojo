"""bench_image_ops.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from image_ops import convolve_2d, sobel_x_kernel, sobel_y_kernel, gaussian_kernel_3x3, sharpen_kernel, histogram, threshold, invert, brightness, contrast, mean_pixel
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

    var _acc_convolve_2d: Float64 = 0.0
    var _t0_convolve_2d = perf_counter_ns()
    for _ in range(N):
        var _r_convolve_2d = convolve_2d([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_convolve_2d += Float64(len(_r_convolve_2d))
    var _t1_convolve_2d = perf_counter_ns()
    var _ns_convolve_2d = Float64(_t1_convolve_2d - _t0_convolve_2d) / Float64(N)
    print("MOJO_TIMING image_ops::convolve_2d", _ns_convolve_2d, _acc_convolve_2d)
    var _acc_sobel_x_kernel: Float64 = 0.0
    var _t0_sobel_x_kernel = perf_counter_ns()
    for _ in range(N):
        var _r_sobel_x_kernel = sobel_x_kernel()
        _acc_sobel_x_kernel += Float64(len(_r_sobel_x_kernel))
    var _t1_sobel_x_kernel = perf_counter_ns()
    var _ns_sobel_x_kernel = Float64(_t1_sobel_x_kernel - _t0_sobel_x_kernel) / Float64(N)
    print("MOJO_TIMING image_ops::sobel_x_kernel", _ns_sobel_x_kernel, _acc_sobel_x_kernel)
    var _acc_sobel_y_kernel: Float64 = 0.0
    var _t0_sobel_y_kernel = perf_counter_ns()
    for _ in range(N):
        var _r_sobel_y_kernel = sobel_y_kernel()
        _acc_sobel_y_kernel += Float64(len(_r_sobel_y_kernel))
    var _t1_sobel_y_kernel = perf_counter_ns()
    var _ns_sobel_y_kernel = Float64(_t1_sobel_y_kernel - _t0_sobel_y_kernel) / Float64(N)
    print("MOJO_TIMING image_ops::sobel_y_kernel", _ns_sobel_y_kernel, _acc_sobel_y_kernel)
    var _acc_gaussian_kernel_3x3: Float64 = 0.0
    var _t0_gaussian_kernel_3x3 = perf_counter_ns()
    for _ in range(N):
        var _r_gaussian_kernel_3x3 = gaussian_kernel_3x3()
        _acc_gaussian_kernel_3x3 += Float64(len(_r_gaussian_kernel_3x3))
    var _t1_gaussian_kernel_3x3 = perf_counter_ns()
    var _ns_gaussian_kernel_3x3 = Float64(_t1_gaussian_kernel_3x3 - _t0_gaussian_kernel_3x3) / Float64(N)
    print("MOJO_TIMING image_ops::gaussian_kernel_3x3", _ns_gaussian_kernel_3x3, _acc_gaussian_kernel_3x3)
    var _acc_sharpen_kernel: Float64 = 0.0
    var _t0_sharpen_kernel = perf_counter_ns()
    for _ in range(N):
        var _r_sharpen_kernel = sharpen_kernel()
        _acc_sharpen_kernel += Float64(len(_r_sharpen_kernel))
    var _t1_sharpen_kernel = perf_counter_ns()
    var _ns_sharpen_kernel = Float64(_t1_sharpen_kernel - _t0_sharpen_kernel) / Float64(N)
    print("MOJO_TIMING image_ops::sharpen_kernel", _ns_sharpen_kernel, _acc_sharpen_kernel)
    var _acc_histogram: Float64 = 0.0
    var _t0_histogram = perf_counter_ns()
    for _ in range(N):
        var _r_histogram = histogram([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5)
        _acc_histogram += Float64(len(_r_histogram))
    var _t1_histogram = perf_counter_ns()
    var _ns_histogram = Float64(_t1_histogram - _t0_histogram) / Float64(N)
    print("MOJO_TIMING image_ops::histogram", _ns_histogram, _acc_histogram)
    var _acc_threshold: Float64 = 0.0
    var _t0_threshold = perf_counter_ns()
    for _ in range(N):
        var _r_threshold = threshold([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
        _acc_threshold += Float64(len(_r_threshold))
    var _t1_threshold = perf_counter_ns()
    var _ns_threshold = Float64(_t1_threshold - _t0_threshold) / Float64(N)
    print("MOJO_TIMING image_ops::threshold", _ns_threshold, _acc_threshold)
    var _acc_invert: Float64 = 0.0
    var _t0_invert = perf_counter_ns()
    for _ in range(N):
        var _r_invert = invert([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_invert += Float64(len(_r_invert))
    var _t1_invert = perf_counter_ns()
    var _ns_invert = Float64(_t1_invert - _t0_invert) / Float64(N)
    print("MOJO_TIMING image_ops::invert", _ns_invert, _acc_invert)
    var _acc_brightness: Float64 = 0.0
    var _t0_brightness = perf_counter_ns()
    for _ in range(N):
        var _r_brightness = brightness([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
        _acc_brightness += Float64(len(_r_brightness))
    var _t1_brightness = perf_counter_ns()
    var _ns_brightness = Float64(_t1_brightness - _t0_brightness) / Float64(N)
    print("MOJO_TIMING image_ops::brightness", _ns_brightness, _acc_brightness)
    var _acc_contrast: Float64 = 0.0
    var _t0_contrast = perf_counter_ns()
    for _ in range(N):
        var _r_contrast = contrast([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
        _acc_contrast += Float64(len(_r_contrast))
    var _t1_contrast = perf_counter_ns()
    var _ns_contrast = Float64(_t1_contrast - _t0_contrast) / Float64(N)
    print("MOJO_TIMING image_ops::contrast", _ns_contrast, _acc_contrast)
    var _acc_mean_pixel: Float64 = 0.0
    var _t0_mean_pixel = perf_counter_ns()
    for _ in range(N):
        _acc_mean_pixel += mean_pixel([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_mean_pixel = perf_counter_ns()
    var _ns_mean_pixel = Float64(_t1_mean_pixel - _t0_mean_pixel) / Float64(N)
    print("MOJO_TIMING image_ops::mean_pixel", _ns_mean_pixel, _acc_mean_pixel)
