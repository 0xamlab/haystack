"""bench_image_features.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from image_features import sobel_magnitude, edge_density, color_histogram, histogram_intersection, histogram_chi_square, histogram_correlation, dominant_colors, saliency_grid, most_salient_cell, edge_density_flat, most_salient_cell_flat
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

    var _acc_sobel_magnitude: Float64 = 0.0
    var _t0_sobel_magnitude = perf_counter_ns()
    for _ in range(N):
        var _r_sobel_magnitude = sobel_magnitude([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_sobel_magnitude += Float64(len(_r_sobel_magnitude))
    var _t1_sobel_magnitude = perf_counter_ns()
    var _ns_sobel_magnitude = Float64(_t1_sobel_magnitude - _t0_sobel_magnitude) / Float64(N)
    print("MOJO_TIMING image_features::sobel_magnitude", _ns_sobel_magnitude, _acc_sobel_magnitude)
    var _result_sobel_magnitude = sobel_magnitude([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_sobel_magnitude = _summary_list_list_float64(_result_sobel_magnitude)
    print("MOJO_RESULT image_features::sobel_magnitude", _summary_sobel_magnitude)
    var _acc_edge_density: Float64 = 0.0
    var _t0_edge_density = perf_counter_ns()
    for _ in range(N):
        _acc_edge_density += edge_density([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
    var _t1_edge_density = perf_counter_ns()
    var _ns_edge_density = Float64(_t1_edge_density - _t0_edge_density) / Float64(N)
    print("MOJO_TIMING image_features::edge_density", _ns_edge_density, _acc_edge_density)
    var _result_edge_density = edge_density([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
    var _summary_edge_density = _summary_float64(_result_edge_density)
    print("MOJO_RESULT image_features::edge_density", _summary_edge_density)
    var _acc_color_histogram: Float64 = 0.0
    var _t0_color_histogram = perf_counter_ns()
    for _ in range(N):
        var _r_color_histogram = color_histogram(_lf5, 5, 5, 5)
        _acc_color_histogram += Float64(len(_r_color_histogram))
    var _t1_color_histogram = perf_counter_ns()
    var _ns_color_histogram = Float64(_t1_color_histogram - _t0_color_histogram) / Float64(N)
    print("MOJO_TIMING image_features::color_histogram", _ns_color_histogram, _acc_color_histogram)
    var _result_color_histogram = color_histogram(_lf5, 5, 5, 5)
    var _summary_color_histogram = _summary_list_float64(_result_color_histogram)
    print("MOJO_RESULT image_features::color_histogram", _summary_color_histogram)
    var _acc_histogram_intersection: Float64 = 0.0
    var _t0_histogram_intersection = perf_counter_ns()
    for _ in range(N):
        _acc_histogram_intersection += histogram_intersection(_lf5, _lf5)
    var _t1_histogram_intersection = perf_counter_ns()
    var _ns_histogram_intersection = Float64(_t1_histogram_intersection - _t0_histogram_intersection) / Float64(N)
    print("MOJO_TIMING image_features::histogram_intersection", _ns_histogram_intersection, _acc_histogram_intersection)
    var _result_histogram_intersection = histogram_intersection(_lf5, _lf5)
    var _summary_histogram_intersection = _summary_float64(_result_histogram_intersection)
    print("MOJO_RESULT image_features::histogram_intersection", _summary_histogram_intersection)
    var _acc_histogram_chi_square: Float64 = 0.0
    var _t0_histogram_chi_square = perf_counter_ns()
    for _ in range(N):
        _acc_histogram_chi_square += histogram_chi_square(_lf5, _lf5)
    var _t1_histogram_chi_square = perf_counter_ns()
    var _ns_histogram_chi_square = Float64(_t1_histogram_chi_square - _t0_histogram_chi_square) / Float64(N)
    print("MOJO_TIMING image_features::histogram_chi_square", _ns_histogram_chi_square, _acc_histogram_chi_square)
    var _result_histogram_chi_square = histogram_chi_square(_lf5, _lf5)
    var _summary_histogram_chi_square = _summary_float64(_result_histogram_chi_square)
    print("MOJO_RESULT image_features::histogram_chi_square", _summary_histogram_chi_square)
    var _acc_histogram_correlation: Float64 = 0.0
    var _t0_histogram_correlation = perf_counter_ns()
    for _ in range(N):
        _acc_histogram_correlation += histogram_correlation(_lf5, _lf5)
    var _t1_histogram_correlation = perf_counter_ns()
    var _ns_histogram_correlation = Float64(_t1_histogram_correlation - _t0_histogram_correlation) / Float64(N)
    print("MOJO_TIMING image_features::histogram_correlation", _ns_histogram_correlation, _acc_histogram_correlation)
    var _result_histogram_correlation = histogram_correlation(_lf5, _lf5)
    var _summary_histogram_correlation = _summary_float64(_result_histogram_correlation)
    print("MOJO_RESULT image_features::histogram_correlation", _summary_histogram_correlation)
    var _acc_dominant_colors: Float64 = 0.0
    var _t0_dominant_colors = perf_counter_ns()
    for _ in range(N):
        var _r_dominant_colors = dominant_colors(_lf5, 5, 5, 5)
        _acc_dominant_colors += Float64(len(_r_dominant_colors))
    var _t1_dominant_colors = perf_counter_ns()
    var _ns_dominant_colors = Float64(_t1_dominant_colors - _t0_dominant_colors) / Float64(N)
    print("MOJO_TIMING image_features::dominant_colors", _ns_dominant_colors, _acc_dominant_colors)
    var _result_dominant_colors = dominant_colors(_lf5, 5, 5, 5)
    var _summary_dominant_colors = _summary_list_float64(_result_dominant_colors)
    print("MOJO_RESULT image_features::dominant_colors", _summary_dominant_colors)
    var _acc_saliency_grid: Float64 = 0.0
    var _t0_saliency_grid = perf_counter_ns()
    for _ in range(N):
        var _r_saliency_grid = saliency_grid([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 5)
        _acc_saliency_grid += Float64(len(_r_saliency_grid))
    var _t1_saliency_grid = perf_counter_ns()
    var _ns_saliency_grid = Float64(_t1_saliency_grid - _t0_saliency_grid) / Float64(N)
    print("MOJO_TIMING image_features::saliency_grid", _ns_saliency_grid, _acc_saliency_grid)
    var _result_saliency_grid = saliency_grid([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5, 5)
    var _summary_saliency_grid = _summary_list_list_float64(_result_saliency_grid)
    print("MOJO_RESULT image_features::saliency_grid", _summary_saliency_grid)
    var _acc_most_salient_cell: Float64 = 0.0
    var _t0_most_salient_cell = perf_counter_ns()
    for _ in range(N):
        _acc_most_salient_cell += Float64(most_salient_cell([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]))
    var _t1_most_salient_cell = perf_counter_ns()
    var _ns_most_salient_cell = Float64(_t1_most_salient_cell - _t0_most_salient_cell) / Float64(N)
    print("MOJO_TIMING image_features::most_salient_cell", _ns_most_salient_cell, _acc_most_salient_cell)
    var _result_most_salient_cell = most_salient_cell([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_most_salient_cell = _summary_int(_result_most_salient_cell)
    print("MOJO_RESULT image_features::most_salient_cell", _summary_most_salient_cell)
    var _acc_edge_density_flat: Float64 = 0.0
    var _t0_edge_density_flat = perf_counter_ns()
    for _ in range(N):
        _acc_edge_density_flat += edge_density_flat(_lf5, 5, 5, 0.5)
    var _t1_edge_density_flat = perf_counter_ns()
    var _ns_edge_density_flat = Float64(_t1_edge_density_flat - _t0_edge_density_flat) / Float64(N)
    print("MOJO_TIMING image_features::edge_density_flat", _ns_edge_density_flat, _acc_edge_density_flat)
    var _result_edge_density_flat = edge_density_flat(_lf5, 5, 5, 0.5)
    var _summary_edge_density_flat = _summary_float64(_result_edge_density_flat)
    print("MOJO_RESULT image_features::edge_density_flat", _summary_edge_density_flat)
    var _acc_most_salient_cell_flat: Float64 = 0.0
    var _t0_most_salient_cell_flat = perf_counter_ns()
    for _ in range(N):
        _acc_most_salient_cell_flat += Float64(most_salient_cell_flat(_lf5, 5, 5, 5, 5))
    var _t1_most_salient_cell_flat = perf_counter_ns()
    var _ns_most_salient_cell_flat = Float64(_t1_most_salient_cell_flat - _t0_most_salient_cell_flat) / Float64(N)
    print("MOJO_TIMING image_features::most_salient_cell_flat", _ns_most_salient_cell_flat, _acc_most_salient_cell_flat)
    var _result_most_salient_cell_flat = most_salient_cell_flat(_lf5, 5, 5, 5, 5)
    var _summary_most_salient_cell_flat = _summary_int(_result_most_salient_cell_flat)
    print("MOJO_RESULT image_features::most_salient_cell_flat", _summary_most_salient_cell_flat)
