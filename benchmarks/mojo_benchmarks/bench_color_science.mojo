"""bench_color_science.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from color_science import delta_e_76, lab_to_lch_l, lab_to_lch_c, lab_to_lch_h, rgb_to_luminance, contrast_ratio, wcag_aa_pass, color_temperature_approx, metamerism_index, chromatic_adaptation_von_kries, cri_from_delta_e, whiteness_index_cie
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
