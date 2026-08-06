"""bench_image_palette.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from image_palette import dominant_palette_rgb255, palette_size_estimate, palette_entropy, mean_saturation_rgb255, warm_color_ratio_rgb255, palette_contrast_score, accent_color_hex, is_monochrome_palette
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
    var N: Int = 10000

    var _acc_dominant_palette_rgb255: Float64 = 0.0
    var _t0_dominant_palette_rgb255 = perf_counter_ns()
    for _ in range(N):
        var _r_dominant_palette_rgb255 = dominant_palette_rgb255(_lf12_colorcheck2x2, 2, 2, 4, 2)
        _acc_dominant_palette_rgb255 += Float64(len(_r_dominant_palette_rgb255))
    var _t1_dominant_palette_rgb255 = perf_counter_ns()
    var _ns_dominant_palette_rgb255 = Float64(_t1_dominant_palette_rgb255 - _t0_dominant_palette_rgb255) / Float64(N)
    print("MOJO_TIMING image_palette::dominant_palette_rgb255", _ns_dominant_palette_rgb255, _acc_dominant_palette_rgb255)
    var _result_dominant_palette_rgb255 = dominant_palette_rgb255(_lf12_colorcheck2x2, 2, 2, 4, 2)
    var _summary_dominant_palette_rgb255 = _summary_list_float64(_result_dominant_palette_rgb255)
    print("MOJO_RESULT image_palette::dominant_palette_rgb255", _summary_dominant_palette_rgb255)
    var _acc_palette_size_estimate: Float64 = 0.0
    var _t0_palette_size_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_palette_size_estimate += Float64(palette_size_estimate(_lf12_colorcheck2x2, 2, 2, 4, 0.2))
    var _t1_palette_size_estimate = perf_counter_ns()
    var _ns_palette_size_estimate = Float64(_t1_palette_size_estimate - _t0_palette_size_estimate) / Float64(N)
    print("MOJO_TIMING image_palette::palette_size_estimate", _ns_palette_size_estimate, _acc_palette_size_estimate)
    var _result_palette_size_estimate = palette_size_estimate(_lf12_colorcheck2x2, 2, 2, 4, 0.2)
    var _summary_palette_size_estimate = _summary_int(_result_palette_size_estimate)
    print("MOJO_RESULT image_palette::palette_size_estimate", _summary_palette_size_estimate)
    var _acc_palette_entropy: Float64 = 0.0
    var _t0_palette_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_palette_entropy += palette_entropy(_lf12_colorcheck2x2, 2, 2, 4)
    var _t1_palette_entropy = perf_counter_ns()
    var _ns_palette_entropy = Float64(_t1_palette_entropy - _t0_palette_entropy) / Float64(N)
    print("MOJO_TIMING image_palette::palette_entropy", _ns_palette_entropy, _acc_palette_entropy)
    var _result_palette_entropy = palette_entropy(_lf12_colorcheck2x2, 2, 2, 4)
    var _summary_palette_entropy = _summary_float64(_result_palette_entropy)
    print("MOJO_RESULT image_palette::palette_entropy", _summary_palette_entropy)
    var _acc_mean_saturation_rgb255: Float64 = 0.0
    var _t0_mean_saturation_rgb255 = perf_counter_ns()
    for _ in range(N):
        _acc_mean_saturation_rgb255 += mean_saturation_rgb255(_lf12_colorcheck2x2, 2, 2)
    var _t1_mean_saturation_rgb255 = perf_counter_ns()
    var _ns_mean_saturation_rgb255 = Float64(_t1_mean_saturation_rgb255 - _t0_mean_saturation_rgb255) / Float64(N)
    print("MOJO_TIMING image_palette::mean_saturation_rgb255", _ns_mean_saturation_rgb255, _acc_mean_saturation_rgb255)
    var _result_mean_saturation_rgb255 = mean_saturation_rgb255(_lf12_colorcheck2x2, 2, 2)
    var _summary_mean_saturation_rgb255 = _summary_float64(_result_mean_saturation_rgb255)
    print("MOJO_RESULT image_palette::mean_saturation_rgb255", _summary_mean_saturation_rgb255)
    var _acc_warm_color_ratio_rgb255: Float64 = 0.0
    var _t0_warm_color_ratio_rgb255 = perf_counter_ns()
    for _ in range(N):
        _acc_warm_color_ratio_rgb255 += warm_color_ratio_rgb255(_lf12_colorcheck2x2, 2, 2, 0.25)
    var _t1_warm_color_ratio_rgb255 = perf_counter_ns()
    var _ns_warm_color_ratio_rgb255 = Float64(_t1_warm_color_ratio_rgb255 - _t0_warm_color_ratio_rgb255) / Float64(N)
    print("MOJO_TIMING image_palette::warm_color_ratio_rgb255", _ns_warm_color_ratio_rgb255, _acc_warm_color_ratio_rgb255)
    var _result_warm_color_ratio_rgb255 = warm_color_ratio_rgb255(_lf12_colorcheck2x2, 2, 2, 0.25)
    var _summary_warm_color_ratio_rgb255 = _summary_float64(_result_warm_color_ratio_rgb255)
    print("MOJO_RESULT image_palette::warm_color_ratio_rgb255", _summary_warm_color_ratio_rgb255)
    var _acc_palette_contrast_score: Float64 = 0.0
    var _t0_palette_contrast_score = perf_counter_ns()
    for _ in range(N):
        _acc_palette_contrast_score += palette_contrast_score(_lf12_colorcheck2x2, 2, 2, 4, 2)
    var _t1_palette_contrast_score = perf_counter_ns()
    var _ns_palette_contrast_score = Float64(_t1_palette_contrast_score - _t0_palette_contrast_score) / Float64(N)
    print("MOJO_TIMING image_palette::palette_contrast_score", _ns_palette_contrast_score, _acc_palette_contrast_score)
    var _result_palette_contrast_score = palette_contrast_score(_lf12_colorcheck2x2, 2, 2, 4, 2)
    var _summary_palette_contrast_score = _summary_float64(_result_palette_contrast_score)
    print("MOJO_RESULT image_palette::palette_contrast_score", _summary_palette_contrast_score)
    var _acc_accent_color_hex: Float64 = 0.0
    var _t0_accent_color_hex = perf_counter_ns()
    for _ in range(N):
        _ = accent_color_hex(_lf12_colorcheck2x2, 2, 2, 4)
    var _t1_accent_color_hex = perf_counter_ns()
    var _ns_accent_color_hex = Float64(_t1_accent_color_hex - _t0_accent_color_hex) / Float64(N)
    print("MOJO_TIMING image_palette::accent_color_hex", _ns_accent_color_hex, _acc_accent_color_hex)
    var _result_accent_color_hex = accent_color_hex(_lf12_colorcheck2x2, 2, 2, 4)
    var _summary_accent_color_hex = _summary_string(_result_accent_color_hex)
    print("MOJO_RESULT image_palette::accent_color_hex", _summary_accent_color_hex)
    var _acc_is_monochrome_palette: Float64 = 0.0
    var _t0_is_monochrome_palette = perf_counter_ns()
    for _ in range(N):
        _acc_is_monochrome_palette += Float64(is_monochrome_palette(_lf12_colorcheck2x2, 2, 2, 4, 0.2, 0.15))
    var _t1_is_monochrome_palette = perf_counter_ns()
    var _ns_is_monochrome_palette = Float64(_t1_is_monochrome_palette - _t0_is_monochrome_palette) / Float64(N)
    print("MOJO_TIMING image_palette::is_monochrome_palette", _ns_is_monochrome_palette, _acc_is_monochrome_palette)
    var _result_is_monochrome_palette = is_monochrome_palette(_lf12_colorcheck2x2, 2, 2, 4, 0.2, 0.15)
    var _summary_is_monochrome_palette = _summary_bool(_result_is_monochrome_palette)
    print("MOJO_RESULT image_palette::is_monochrome_palette", _summary_is_monochrome_palette)
