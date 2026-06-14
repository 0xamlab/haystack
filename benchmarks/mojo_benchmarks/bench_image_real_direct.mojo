from std.math import isinf, isnan
from std.python import Python, PythonObject
from std.sys import argv as mojo_argv
from std.time import perf_counter_ns

from image_features import (
    color_histogram,
    dominant_colors,
    edge_density_flat,
    most_salient_cell_flat,
)
from image_quality import (
    blur_score_flat,
    brightness_flat,
    entropy_flat,
    quality_score_flat,
)
from image_resize import downscale_flat
from perceptual_hash import phash_flat
from python_bridge import fast_f64, fast_int
from vision_gate import route_image_request


def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h


def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value):
        return "float:nan"
    if isinf(value):
        return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)


def _summary_int(value: Int) -> String:
    return "int:" + String(value)


def _summary_u64(value: UInt64) -> String:
    return "int:" + String(value)


def _summary_list_float64_rounded6(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0:
            joined += "|"
        joined += _summary_float64_rounded6(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


def _iters_for_pixels(pixels: Int, scale: Int, min_iters: Int, max_iters: Int) -> Int:
    if pixels <= 0:
        return min_iters
    var iters = scale // pixels
    if iters < min_iters:
        return min_iters
    if iters > max_iters:
        return max_iters
    return iters


def _emit_meta(name: String, iters: Int) -> None:
    print("MOJO_ITERS", name, iters)


def _py_list_to_f64_list(values: PythonObject) raises -> List[Float64]:
    var builtins = Python.import_module("builtins")
    var count = fast_int(builtins.len(values))
    var out = List[Float64]()
    for i in range(count):
        out.append(fast_f64(values[i]))
    return out^


def main() raises:
    var args = mojo_argv()
    if len(args) < 2:
        print("usage: bench_image_real_direct <png-path>")
        return

    var image_path = String(args[1])
    var os = Python.import_module("os")
    var sys_m = Python.import_module("sys")
    sys_m.path.insert(0, os.getcwd())
    var loader = Python.import_module("benchmarks.png_loader")
    var loaded = loader.load_png_rgb(image_path)
    var width = fast_int(loaded["width"])
    var height = fast_int(loaded["height"])
    var flat_rgb = _py_list_to_f64_list(loaded["flat_rgb"])
    var flat_gray = _py_list_to_f64_list(loaded["flat_gray"])

    var pixels = width * height
    print("MOJO_IMAGE", image_path, width, height, pixels)

    var blur_for_route = blur_score_flat(flat_gray, width, height)
    var brightness_for_route = brightness_flat(flat_gray, width, height)
    var entropy_for_route = entropy_flat(flat_gray, width, height)
    var edge_for_route = edge_density_flat(flat_gray, width, height, 32.0)

    var scalar_iters = _iters_for_pixels(pixels, 400000, 1, 500)
    var list_iters = _iters_for_pixels(pixels, 120000, 1, 200)
    var hash_iters = _iters_for_pixels(pixels, 150000, 1, 200)
    var route_iters = 200000

    _emit_meta("blur_score_flat", scalar_iters)
    var _acc_blur_score_flat: Float64 = 0.0
    var _t0_blur_score_flat = perf_counter_ns()
    for _ in range(scalar_iters):
        _acc_blur_score_flat += blur_score_flat(flat_gray, width, height)
    var _t1_blur_score_flat = perf_counter_ns()
    print(
        "MOJO_TIMING blur_score_flat",
        Float64(_t1_blur_score_flat - _t0_blur_score_flat) / Float64(scalar_iters),
    )
    print(
        "MOJO_RESULT blur_score_flat",
        _summary_float64_rounded6(blur_score_flat(flat_gray, width, height)),
    )

    _emit_meta("quality_score_flat", scalar_iters)
    var _acc_quality_score_flat: Float64 = 0.0
    var _t0_quality_score_flat = perf_counter_ns()
    for _ in range(scalar_iters):
        _acc_quality_score_flat += quality_score_flat(flat_gray, width, height)
    var _t1_quality_score_flat = perf_counter_ns()
    print(
        "MOJO_TIMING quality_score_flat",
        Float64(_t1_quality_score_flat - _t0_quality_score_flat) / Float64(scalar_iters),
    )
    print(
        "MOJO_RESULT quality_score_flat",
        _summary_float64_rounded6(quality_score_flat(flat_gray, width, height)),
    )

    _emit_meta("edge_density_flat", scalar_iters)
    var _acc_edge_density_flat: Float64 = 0.0
    var _t0_edge_density_flat = perf_counter_ns()
    for _ in range(scalar_iters):
        _acc_edge_density_flat += edge_density_flat(flat_gray, width, height, 32.0)
    var _t1_edge_density_flat = perf_counter_ns()
    print(
        "MOJO_TIMING edge_density_flat",
        Float64(_t1_edge_density_flat - _t0_edge_density_flat) / Float64(scalar_iters),
    )
    print(
        "MOJO_RESULT edge_density_flat",
        _summary_float64_rounded6(edge_density_flat(flat_gray, width, height, 32.0)),
    )

    _emit_meta("most_salient_cell_flat", scalar_iters)
    var _acc_most_salient_cell_flat: Float64 = 0.0
    var _t0_most_salient_cell_flat = perf_counter_ns()
    for _ in range(scalar_iters):
        _acc_most_salient_cell_flat += Float64(
            most_salient_cell_flat(flat_gray, width, height, 4, 4)
        )
    var _t1_most_salient_cell_flat = perf_counter_ns()
    print(
        "MOJO_TIMING most_salient_cell_flat",
        Float64(_t1_most_salient_cell_flat - _t0_most_salient_cell_flat) / Float64(scalar_iters),
    )
    print(
        "MOJO_RESULT most_salient_cell_flat",
        _summary_int(most_salient_cell_flat(flat_gray, width, height, 4, 4)),
    )

    _emit_meta("downscale_flat", scalar_iters)
    var target_w = 64 if width >= 64 else width
    var target_h = 64 if height >= 64 else height
    var _acc_downscale_flat: Float64 = 0.0
    var _t0_downscale_flat = perf_counter_ns()
    for _ in range(scalar_iters):
        var result = downscale_flat(flat_gray, width, height, target_w, target_h)
        _acc_downscale_flat += Float64(len(result))
    var _t1_downscale_flat = perf_counter_ns()
    print(
        "MOJO_TIMING downscale_flat",
        Float64(_t1_downscale_flat - _t0_downscale_flat) / Float64(scalar_iters),
    )
    print(
        "MOJO_RESULT downscale_flat",
        _summary_list_float64_rounded6(
            downscale_flat(flat_gray, width, height, target_w, target_h)
        ),
    )

    _emit_meta("phash_flat", hash_iters)
    var _acc_phash_flat: Float64 = 0.0
    var _t0_phash_flat = perf_counter_ns()
    for _ in range(hash_iters):
        _acc_phash_flat += Float64(phash_flat(flat_gray, width, height))
    var _t1_phash_flat = perf_counter_ns()
    print(
        "MOJO_TIMING phash_flat",
        Float64(_t1_phash_flat - _t0_phash_flat) / Float64(hash_iters),
    )
    print("MOJO_RESULT phash_flat", _summary_u64(phash_flat(flat_gray, width, height)))

    _emit_meta("color_histogram", list_iters)
    var _acc_color_histogram: Float64 = 0.0
    var _t0_color_histogram = perf_counter_ns()
    for _ in range(list_iters):
        var result = color_histogram(flat_rgb, width, height, 8)
        _acc_color_histogram += Float64(len(result))
    var _t1_color_histogram = perf_counter_ns()
    print(
        "MOJO_TIMING color_histogram",
        Float64(_t1_color_histogram - _t0_color_histogram) / Float64(list_iters),
    )
    print(
        "MOJO_RESULT color_histogram",
        _summary_list_float64_rounded6(color_histogram(flat_rgb, width, height, 8)),
    )

    _emit_meta("dominant_colors", list_iters)
    var _acc_dominant_colors: Float64 = 0.0
    var _t0_dominant_colors = perf_counter_ns()
    for _ in range(list_iters):
        var result = dominant_colors(flat_rgb, width, height, 8)
        _acc_dominant_colors += Float64(len(result))
    var _t1_dominant_colors = perf_counter_ns()
    print(
        "MOJO_TIMING dominant_colors",
        Float64(_t1_dominant_colors - _t0_dominant_colors) / Float64(list_iters),
    )
    print(
        "MOJO_RESULT dominant_colors",
        _summary_list_float64_rounded6(dominant_colors(flat_rgb, width, height, 8)),
    )

    _emit_meta("route_image_request", route_iters)
    var _acc_route_image_request: Float64 = 0.0
    var _t0_route_image_request = perf_counter_ns()
    for _ in range(route_iters):
        _acc_route_image_request += Float64(
            route_image_request(
                blur_for_route,
                brightness_for_route,
                entropy_for_route,
                edge_for_route,
                False,
                0,
            )
        )
    var _t1_route_image_request = perf_counter_ns()
    print(
        "MOJO_TIMING route_image_request",
        Float64(_t1_route_image_request - _t0_route_image_request) / Float64(route_iters),
    )
    print(
        "MOJO_RESULT route_image_request",
        _summary_int(
            route_image_request(
                blur_for_route,
                brightness_for_route,
                entropy_for_route,
                edge_for_route,
                False,
                0,
            )
        ),
    )
