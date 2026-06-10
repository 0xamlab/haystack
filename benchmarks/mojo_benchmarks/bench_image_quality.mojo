"""bench_image_quality.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from image_quality import blur_score, is_blurry, brightness_mean, contrast_std, shannon_entropy, is_near_blank, uniformity, noise_estimate, is_over_or_under_exposed, quality_score, blur_score_flat, brightness_flat, entropy_flat, contrast_flat, quality_score_flat
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

    var _acc_blur_score: Float64 = 0.0
    var _t0_blur_score = perf_counter_ns()
    for _ in range(N):
        _acc_blur_score += blur_score([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_blur_score = perf_counter_ns()
    var _ns_blur_score = Float64(_t1_blur_score - _t0_blur_score) / Float64(N)
    print("MOJO_TIMING image_quality::blur_score", _ns_blur_score, _acc_blur_score)
    var _result_blur_score = blur_score([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_blur_score = _summary_float64(_result_blur_score)
    print("MOJO_RESULT image_quality::blur_score", _summary_blur_score)
    var _acc_is_blurry: Float64 = 0.0
    var _t0_is_blurry = perf_counter_ns()
    for _ in range(N):
        _acc_is_blurry += Float64(is_blurry([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5))
    var _t1_is_blurry = perf_counter_ns()
    var _ns_is_blurry = Float64(_t1_is_blurry - _t0_is_blurry) / Float64(N)
    print("MOJO_TIMING image_quality::is_blurry", _ns_is_blurry, _acc_is_blurry)
    var _result_is_blurry = is_blurry([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
    var _summary_is_blurry = _summary_bool(_result_is_blurry)
    print("MOJO_RESULT image_quality::is_blurry", _summary_is_blurry)
    var _acc_brightness_mean: Float64 = 0.0
    var _t0_brightness_mean = perf_counter_ns()
    for _ in range(N):
        _acc_brightness_mean += brightness_mean([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_brightness_mean = perf_counter_ns()
    var _ns_brightness_mean = Float64(_t1_brightness_mean - _t0_brightness_mean) / Float64(N)
    print("MOJO_TIMING image_quality::brightness_mean", _ns_brightness_mean, _acc_brightness_mean)
    var _result_brightness_mean = brightness_mean([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_brightness_mean = _summary_float64(_result_brightness_mean)
    print("MOJO_RESULT image_quality::brightness_mean", _summary_brightness_mean)
    var _acc_contrast_std: Float64 = 0.0
    var _t0_contrast_std = perf_counter_ns()
    for _ in range(N):
        _acc_contrast_std += contrast_std([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_contrast_std = perf_counter_ns()
    var _ns_contrast_std = Float64(_t1_contrast_std - _t0_contrast_std) / Float64(N)
    print("MOJO_TIMING image_quality::contrast_std", _ns_contrast_std, _acc_contrast_std)
    var _result_contrast_std = contrast_std([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_contrast_std = _summary_float64(_result_contrast_std)
    print("MOJO_RESULT image_quality::contrast_std", _summary_contrast_std)
    var _acc_shannon_entropy: Float64 = 0.0
    var _t0_shannon_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_shannon_entropy += shannon_entropy([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_shannon_entropy = perf_counter_ns()
    var _ns_shannon_entropy = Float64(_t1_shannon_entropy - _t0_shannon_entropy) / Float64(N)
    print("MOJO_TIMING image_quality::shannon_entropy", _ns_shannon_entropy, _acc_shannon_entropy)
    var _result_shannon_entropy = shannon_entropy([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_shannon_entropy = _summary_float64(_result_shannon_entropy)
    print("MOJO_RESULT image_quality::shannon_entropy", _summary_shannon_entropy)
    var _acc_is_near_blank: Float64 = 0.0
    var _t0_is_near_blank = perf_counter_ns()
    for _ in range(N):
        _acc_is_near_blank += Float64(is_near_blank([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5))
    var _t1_is_near_blank = perf_counter_ns()
    var _ns_is_near_blank = Float64(_t1_is_near_blank - _t0_is_near_blank) / Float64(N)
    print("MOJO_TIMING image_quality::is_near_blank", _ns_is_near_blank, _acc_is_near_blank)
    var _result_is_near_blank = is_near_blank([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5)
    var _summary_is_near_blank = _summary_bool(_result_is_near_blank)
    print("MOJO_RESULT image_quality::is_near_blank", _summary_is_near_blank)
    var _acc_uniformity: Float64 = 0.0
    var _t0_uniformity = perf_counter_ns()
    for _ in range(N):
        _acc_uniformity += uniformity([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_uniformity = perf_counter_ns()
    var _ns_uniformity = Float64(_t1_uniformity - _t0_uniformity) / Float64(N)
    print("MOJO_TIMING image_quality::uniformity", _ns_uniformity, _acc_uniformity)
    var _result_uniformity = uniformity([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_uniformity = _summary_float64(_result_uniformity)
    print("MOJO_RESULT image_quality::uniformity", _summary_uniformity)
    var _acc_noise_estimate: Float64 = 0.0
    var _t0_noise_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_noise_estimate += noise_estimate([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_noise_estimate = perf_counter_ns()
    var _ns_noise_estimate = Float64(_t1_noise_estimate - _t0_noise_estimate) / Float64(N)
    print("MOJO_TIMING image_quality::noise_estimate", _ns_noise_estimate, _acc_noise_estimate)
    var _result_noise_estimate = noise_estimate([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_noise_estimate = _summary_float64(_result_noise_estimate)
    print("MOJO_RESULT image_quality::noise_estimate", _summary_noise_estimate)
    var _acc_is_over_or_under_exposed: Float64 = 0.0
    var _t0_is_over_or_under_exposed = perf_counter_ns()
    for _ in range(N):
        _acc_is_over_or_under_exposed += Float64(is_over_or_under_exposed([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5, 0.5))
    var _t1_is_over_or_under_exposed = perf_counter_ns()
    var _ns_is_over_or_under_exposed = Float64(_t1_is_over_or_under_exposed - _t0_is_over_or_under_exposed) / Float64(N)
    print("MOJO_TIMING image_quality::is_over_or_under_exposed", _ns_is_over_or_under_exposed, _acc_is_over_or_under_exposed)
    var _result_is_over_or_under_exposed = is_over_or_under_exposed([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 0.5, 0.5)
    var _summary_is_over_or_under_exposed = _summary_bool(_result_is_over_or_under_exposed)
    print("MOJO_RESULT image_quality::is_over_or_under_exposed", _summary_is_over_or_under_exposed)
    var _acc_quality_score: Float64 = 0.0
    var _t0_quality_score = perf_counter_ns()
    for _ in range(N):
        _acc_quality_score += quality_score([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_quality_score = perf_counter_ns()
    var _ns_quality_score = Float64(_t1_quality_score - _t0_quality_score) / Float64(N)
    print("MOJO_TIMING image_quality::quality_score", _ns_quality_score, _acc_quality_score)
    var _result_quality_score = quality_score([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_quality_score = _summary_float64(_result_quality_score)
    print("MOJO_RESULT image_quality::quality_score", _summary_quality_score)
    var _acc_blur_score_flat: Float64 = 0.0
    var _t0_blur_score_flat = perf_counter_ns()
    for _ in range(N):
        _acc_blur_score_flat += blur_score_flat(_lf5, 5, 5)
    var _t1_blur_score_flat = perf_counter_ns()
    var _ns_blur_score_flat = Float64(_t1_blur_score_flat - _t0_blur_score_flat) / Float64(N)
    print("MOJO_TIMING image_quality::blur_score_flat", _ns_blur_score_flat, _acc_blur_score_flat)
    var _result_blur_score_flat = blur_score_flat(_lf5, 5, 5)
    var _summary_blur_score_flat = _summary_float64(_result_blur_score_flat)
    print("MOJO_RESULT image_quality::blur_score_flat", _summary_blur_score_flat)
    var _acc_brightness_flat: Float64 = 0.0
    var _t0_brightness_flat = perf_counter_ns()
    for _ in range(N):
        _acc_brightness_flat += brightness_flat(_lf5, 5, 5)
    var _t1_brightness_flat = perf_counter_ns()
    var _ns_brightness_flat = Float64(_t1_brightness_flat - _t0_brightness_flat) / Float64(N)
    print("MOJO_TIMING image_quality::brightness_flat", _ns_brightness_flat, _acc_brightness_flat)
    var _result_brightness_flat = brightness_flat(_lf5, 5, 5)
    var _summary_brightness_flat = _summary_float64(_result_brightness_flat)
    print("MOJO_RESULT image_quality::brightness_flat", _summary_brightness_flat)
    var _acc_entropy_flat: Float64 = 0.0
    var _t0_entropy_flat = perf_counter_ns()
    for _ in range(N):
        _acc_entropy_flat += entropy_flat(_lf5, 5, 5)
    var _t1_entropy_flat = perf_counter_ns()
    var _ns_entropy_flat = Float64(_t1_entropy_flat - _t0_entropy_flat) / Float64(N)
    print("MOJO_TIMING image_quality::entropy_flat", _ns_entropy_flat, _acc_entropy_flat)
    var _result_entropy_flat = entropy_flat(_lf5, 5, 5)
    var _summary_entropy_flat = _summary_float64(_result_entropy_flat)
    print("MOJO_RESULT image_quality::entropy_flat", _summary_entropy_flat)
    var _acc_contrast_flat: Float64 = 0.0
    var _t0_contrast_flat = perf_counter_ns()
    for _ in range(N):
        _acc_contrast_flat += contrast_flat(_lf5, 5, 5)
    var _t1_contrast_flat = perf_counter_ns()
    var _ns_contrast_flat = Float64(_t1_contrast_flat - _t0_contrast_flat) / Float64(N)
    print("MOJO_TIMING image_quality::contrast_flat", _ns_contrast_flat, _acc_contrast_flat)
    var _result_contrast_flat = contrast_flat(_lf5, 5, 5)
    var _summary_contrast_flat = _summary_float64(_result_contrast_flat)
    print("MOJO_RESULT image_quality::contrast_flat", _summary_contrast_flat)
    var _acc_quality_score_flat: Float64 = 0.0
    var _t0_quality_score_flat = perf_counter_ns()
    for _ in range(N):
        _acc_quality_score_flat += quality_score_flat(_lf5, 5, 5)
    var _t1_quality_score_flat = perf_counter_ns()
    var _ns_quality_score_flat = Float64(_t1_quality_score_flat - _t0_quality_score_flat) / Float64(N)
    print("MOJO_TIMING image_quality::quality_score_flat", _ns_quality_score_flat, _acc_quality_score_flat)
    var _result_quality_score_flat = quality_score_flat(_lf5, 5, 5)
    var _summary_quality_score_flat = _summary_float64(_result_quality_score_flat)
    print("MOJO_RESULT image_quality::quality_score_flat", _summary_quality_score_flat)
