"""bench_color_science.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from color_science import delta_e_76, lab_to_lch_l, lab_to_lch_c, lab_to_lch_h, rgb_to_luminance, contrast_ratio, wcag_aa_pass, color_temperature_approx, metamerism_index, chromatic_adaptation_von_kries, cri_from_delta_e, whiteness_index_cie
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

    var _acc_delta_e_76: Float64 = 0.0
    var _t0_delta_e_76 = perf_counter_ns()
    for _ in range(N):
        _acc_delta_e_76 += delta_e_76(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_delta_e_76 = perf_counter_ns()
    var _ns_delta_e_76 = Float64(_t1_delta_e_76 - _t0_delta_e_76) / Float64(N)
    print("MOJO_TIMING color_science::delta_e_76", _ns_delta_e_76, _acc_delta_e_76)
    var _result_delta_e_76 = delta_e_76(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_delta_e_76 = _summary_float64(_result_delta_e_76)
    print("MOJO_RESULT color_science::delta_e_76", _summary_delta_e_76)
    var _acc_lab_to_lch_l: Float64 = 0.0
    var _t0_lab_to_lch_l = perf_counter_ns()
    for _ in range(N):
        _acc_lab_to_lch_l += lab_to_lch_l(0.5)
    var _t1_lab_to_lch_l = perf_counter_ns()
    var _ns_lab_to_lch_l = Float64(_t1_lab_to_lch_l - _t0_lab_to_lch_l) / Float64(N)
    print("MOJO_TIMING color_science::lab_to_lch_l", _ns_lab_to_lch_l, _acc_lab_to_lch_l)
    var _result_lab_to_lch_l = lab_to_lch_l(0.5)
    var _summary_lab_to_lch_l = _summary_float64(_result_lab_to_lch_l)
    print("MOJO_RESULT color_science::lab_to_lch_l", _summary_lab_to_lch_l)
    var _acc_lab_to_lch_c: Float64 = 0.0
    var _t0_lab_to_lch_c = perf_counter_ns()
    for _ in range(N):
        _acc_lab_to_lch_c += lab_to_lch_c(0.5, 0.5)
    var _t1_lab_to_lch_c = perf_counter_ns()
    var _ns_lab_to_lch_c = Float64(_t1_lab_to_lch_c - _t0_lab_to_lch_c) / Float64(N)
    print("MOJO_TIMING color_science::lab_to_lch_c", _ns_lab_to_lch_c, _acc_lab_to_lch_c)
    var _result_lab_to_lch_c = lab_to_lch_c(0.5, 0.5)
    var _summary_lab_to_lch_c = _summary_float64(_result_lab_to_lch_c)
    print("MOJO_RESULT color_science::lab_to_lch_c", _summary_lab_to_lch_c)
    var _acc_lab_to_lch_h: Float64 = 0.0
    var _t0_lab_to_lch_h = perf_counter_ns()
    for _ in range(N):
        _acc_lab_to_lch_h += lab_to_lch_h(0.5, 0.5)
    var _t1_lab_to_lch_h = perf_counter_ns()
    var _ns_lab_to_lch_h = Float64(_t1_lab_to_lch_h - _t0_lab_to_lch_h) / Float64(N)
    print("MOJO_TIMING color_science::lab_to_lch_h", _ns_lab_to_lch_h, _acc_lab_to_lch_h)
    var _result_lab_to_lch_h = lab_to_lch_h(0.5, 0.5)
    var _summary_lab_to_lch_h = _summary_float64(_result_lab_to_lch_h)
    print("MOJO_RESULT color_science::lab_to_lch_h", _summary_lab_to_lch_h)
    var _acc_rgb_to_luminance: Float64 = 0.0
    var _t0_rgb_to_luminance = perf_counter_ns()
    for _ in range(N):
        _acc_rgb_to_luminance += rgb_to_luminance(0.5, 0.5, 0.5)
    var _t1_rgb_to_luminance = perf_counter_ns()
    var _ns_rgb_to_luminance = Float64(_t1_rgb_to_luminance - _t0_rgb_to_luminance) / Float64(N)
    print("MOJO_TIMING color_science::rgb_to_luminance", _ns_rgb_to_luminance, _acc_rgb_to_luminance)
    var _result_rgb_to_luminance = rgb_to_luminance(0.5, 0.5, 0.5)
    var _summary_rgb_to_luminance = _summary_float64(_result_rgb_to_luminance)
    print("MOJO_RESULT color_science::rgb_to_luminance", _summary_rgb_to_luminance)
    var _acc_contrast_ratio: Float64 = 0.0
    var _t0_contrast_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_contrast_ratio += contrast_ratio(0.5, 0.5)
    var _t1_contrast_ratio = perf_counter_ns()
    var _ns_contrast_ratio = Float64(_t1_contrast_ratio - _t0_contrast_ratio) / Float64(N)
    print("MOJO_TIMING color_science::contrast_ratio", _ns_contrast_ratio, _acc_contrast_ratio)
    var _result_contrast_ratio = contrast_ratio(0.5, 0.5)
    var _summary_contrast_ratio = _summary_float64(_result_contrast_ratio)
    print("MOJO_RESULT color_science::contrast_ratio", _summary_contrast_ratio)
    var _acc_wcag_aa_pass: Float64 = 0.0
    var _t0_wcag_aa_pass = perf_counter_ns()
    for _ in range(N):
        _acc_wcag_aa_pass += wcag_aa_pass(0.5, 0.5)
    var _t1_wcag_aa_pass = perf_counter_ns()
    var _ns_wcag_aa_pass = Float64(_t1_wcag_aa_pass - _t0_wcag_aa_pass) / Float64(N)
    print("MOJO_TIMING color_science::wcag_aa_pass", _ns_wcag_aa_pass, _acc_wcag_aa_pass)
    var _result_wcag_aa_pass = wcag_aa_pass(0.5, 0.5)
    var _summary_wcag_aa_pass = _summary_float64(_result_wcag_aa_pass)
    print("MOJO_RESULT color_science::wcag_aa_pass", _summary_wcag_aa_pass)
    var _acc_color_temperature_approx: Float64 = 0.0
    var _t0_color_temperature_approx = perf_counter_ns()
    for _ in range(N):
        _acc_color_temperature_approx += color_temperature_approx(0.5, 0.5)
    var _t1_color_temperature_approx = perf_counter_ns()
    var _ns_color_temperature_approx = Float64(_t1_color_temperature_approx - _t0_color_temperature_approx) / Float64(N)
    print("MOJO_TIMING color_science::color_temperature_approx", _ns_color_temperature_approx, _acc_color_temperature_approx)
    var _result_color_temperature_approx = color_temperature_approx(0.5, 0.5)
    var _summary_color_temperature_approx = _summary_float64(_result_color_temperature_approx)
    print("MOJO_RESULT color_science::color_temperature_approx", _summary_color_temperature_approx)
    var _acc_metamerism_index: Float64 = 0.0
    var _t0_metamerism_index = perf_counter_ns()
    for _ in range(N):
        _acc_metamerism_index += metamerism_index(0.5, 0.5)
    var _t1_metamerism_index = perf_counter_ns()
    var _ns_metamerism_index = Float64(_t1_metamerism_index - _t0_metamerism_index) / Float64(N)
    print("MOJO_TIMING color_science::metamerism_index", _ns_metamerism_index, _acc_metamerism_index)
    var _result_metamerism_index = metamerism_index(0.5, 0.5)
    var _summary_metamerism_index = _summary_float64(_result_metamerism_index)
    print("MOJO_RESULT color_science::metamerism_index", _summary_metamerism_index)
    var _acc_chromatic_adaptation_von_kries: Float64 = 0.0
    var _t0_chromatic_adaptation_von_kries = perf_counter_ns()
    for _ in range(N):
        _acc_chromatic_adaptation_von_kries += chromatic_adaptation_von_kries(0.5, 0.5)
    var _t1_chromatic_adaptation_von_kries = perf_counter_ns()
    var _ns_chromatic_adaptation_von_kries = Float64(_t1_chromatic_adaptation_von_kries - _t0_chromatic_adaptation_von_kries) / Float64(N)
    print("MOJO_TIMING color_science::chromatic_adaptation_von_kries", _ns_chromatic_adaptation_von_kries, _acc_chromatic_adaptation_von_kries)
    var _result_chromatic_adaptation_von_kries = chromatic_adaptation_von_kries(0.5, 0.5)
    var _summary_chromatic_adaptation_von_kries = _summary_float64(_result_chromatic_adaptation_von_kries)
    print("MOJO_RESULT color_science::chromatic_adaptation_von_kries", _summary_chromatic_adaptation_von_kries)
    var _acc_cri_from_delta_e: Float64 = 0.0
    var _t0_cri_from_delta_e = perf_counter_ns()
    for _ in range(N):
        _acc_cri_from_delta_e += cri_from_delta_e(0.5)
    var _t1_cri_from_delta_e = perf_counter_ns()
    var _ns_cri_from_delta_e = Float64(_t1_cri_from_delta_e - _t0_cri_from_delta_e) / Float64(N)
    print("MOJO_TIMING color_science::cri_from_delta_e", _ns_cri_from_delta_e, _acc_cri_from_delta_e)
    var _result_cri_from_delta_e = cri_from_delta_e(0.5)
    var _summary_cri_from_delta_e = _summary_float64(_result_cri_from_delta_e)
    print("MOJO_RESULT color_science::cri_from_delta_e", _summary_cri_from_delta_e)
    var _acc_whiteness_index_cie: Float64 = 0.0
    var _t0_whiteness_index_cie = perf_counter_ns()
    for _ in range(N):
        _acc_whiteness_index_cie += whiteness_index_cie(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_whiteness_index_cie = perf_counter_ns()
    var _ns_whiteness_index_cie = Float64(_t1_whiteness_index_cie - _t0_whiteness_index_cie) / Float64(N)
    print("MOJO_TIMING color_science::whiteness_index_cie", _ns_whiteness_index_cie, _acc_whiteness_index_cie)
    var _result_whiteness_index_cie = whiteness_index_cie(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_whiteness_index_cie = _summary_float64(_result_whiteness_index_cie)
    print("MOJO_RESULT color_science::whiteness_index_cie", _summary_whiteness_index_cie)
