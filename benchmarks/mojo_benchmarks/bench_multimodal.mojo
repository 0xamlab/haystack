"""bench_multimodal.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from multimodal import image_patch_embed, image_patch_count, spectrogram_mel_freq, spectrogram_stft_magnitude, audio_feature_norm, vision_attention_scale, cross_modal_similarity, image_token_count, ocr_confidence_score, multimodal_fusion_weight
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

    var _acc_image_patch_embed: Float64 = 0.0
    var _t0_image_patch_embed = perf_counter_ns()
    for _ in range(N):
        _acc_image_patch_embed += image_patch_embed(0.5, 0.5, 0.5)
    var _t1_image_patch_embed = perf_counter_ns()
    var _ns_image_patch_embed = Float64(_t1_image_patch_embed - _t0_image_patch_embed) / Float64(N)
    print("MOJO_TIMING multimodal::image_patch_embed", _ns_image_patch_embed, _acc_image_patch_embed)
    var _result_image_patch_embed = image_patch_embed(0.5, 0.5, 0.5)
    var _summary_image_patch_embed = _summary_float64(_result_image_patch_embed)
    print("MOJO_RESULT multimodal::image_patch_embed", _summary_image_patch_embed)
    var _acc_image_patch_count: Float64 = 0.0
    var _t0_image_patch_count = perf_counter_ns()
    for _ in range(N):
        _acc_image_patch_count += image_patch_count(0.5, 0.5)
    var _t1_image_patch_count = perf_counter_ns()
    var _ns_image_patch_count = Float64(_t1_image_patch_count - _t0_image_patch_count) / Float64(N)
    print("MOJO_TIMING multimodal::image_patch_count", _ns_image_patch_count, _acc_image_patch_count)
    var _result_image_patch_count = image_patch_count(0.5, 0.5)
    var _summary_image_patch_count = _summary_float64(_result_image_patch_count)
    print("MOJO_RESULT multimodal::image_patch_count", _summary_image_patch_count)
    var _acc_spectrogram_mel_freq: Float64 = 0.0
    var _t0_spectrogram_mel_freq = perf_counter_ns()
    for _ in range(N):
        _acc_spectrogram_mel_freq += spectrogram_mel_freq(0.5)
    var _t1_spectrogram_mel_freq = perf_counter_ns()
    var _ns_spectrogram_mel_freq = Float64(_t1_spectrogram_mel_freq - _t0_spectrogram_mel_freq) / Float64(N)
    print("MOJO_TIMING multimodal::spectrogram_mel_freq", _ns_spectrogram_mel_freq, _acc_spectrogram_mel_freq)
    var _result_spectrogram_mel_freq = spectrogram_mel_freq(0.5)
    var _summary_spectrogram_mel_freq = _summary_float64(_result_spectrogram_mel_freq)
    print("MOJO_RESULT multimodal::spectrogram_mel_freq", _summary_spectrogram_mel_freq)
    var _acc_spectrogram_stft_magnitude: Float64 = 0.0
    var _t0_spectrogram_stft_magnitude = perf_counter_ns()
    for _ in range(N):
        _acc_spectrogram_stft_magnitude += spectrogram_stft_magnitude(0.5, 0.5)
    var _t1_spectrogram_stft_magnitude = perf_counter_ns()
    var _ns_spectrogram_stft_magnitude = Float64(_t1_spectrogram_stft_magnitude - _t0_spectrogram_stft_magnitude) / Float64(N)
    print("MOJO_TIMING multimodal::spectrogram_stft_magnitude", _ns_spectrogram_stft_magnitude, _acc_spectrogram_stft_magnitude)
    var _result_spectrogram_stft_magnitude = spectrogram_stft_magnitude(0.5, 0.5)
    var _summary_spectrogram_stft_magnitude = _summary_float64(_result_spectrogram_stft_magnitude)
    print("MOJO_RESULT multimodal::spectrogram_stft_magnitude", _summary_spectrogram_stft_magnitude)
    var _acc_audio_feature_norm: Float64 = 0.0
    var _t0_audio_feature_norm = perf_counter_ns()
    for _ in range(N):
        _acc_audio_feature_norm += audio_feature_norm(0.5, 0.5, 0.5)
    var _t1_audio_feature_norm = perf_counter_ns()
    var _ns_audio_feature_norm = Float64(_t1_audio_feature_norm - _t0_audio_feature_norm) / Float64(N)
    print("MOJO_TIMING multimodal::audio_feature_norm", _ns_audio_feature_norm, _acc_audio_feature_norm)
    var _result_audio_feature_norm = audio_feature_norm(0.5, 0.5, 0.5)
    var _summary_audio_feature_norm = _summary_float64(_result_audio_feature_norm)
    print("MOJO_RESULT multimodal::audio_feature_norm", _summary_audio_feature_norm)
    var _acc_vision_attention_scale: Float64 = 0.0
    var _t0_vision_attention_scale = perf_counter_ns()
    for _ in range(N):
        _acc_vision_attention_scale += vision_attention_scale(0.5)
    var _t1_vision_attention_scale = perf_counter_ns()
    var _ns_vision_attention_scale = Float64(_t1_vision_attention_scale - _t0_vision_attention_scale) / Float64(N)
    print("MOJO_TIMING multimodal::vision_attention_scale", _ns_vision_attention_scale, _acc_vision_attention_scale)
    var _result_vision_attention_scale = vision_attention_scale(0.5)
    var _summary_vision_attention_scale = _summary_float64(_result_vision_attention_scale)
    print("MOJO_RESULT multimodal::vision_attention_scale", _summary_vision_attention_scale)
    var _acc_cross_modal_similarity: Float64 = 0.0
    var _t0_cross_modal_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_cross_modal_similarity += cross_modal_similarity(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_cross_modal_similarity = perf_counter_ns()
    var _ns_cross_modal_similarity = Float64(_t1_cross_modal_similarity - _t0_cross_modal_similarity) / Float64(N)
    print("MOJO_TIMING multimodal::cross_modal_similarity", _ns_cross_modal_similarity, _acc_cross_modal_similarity)
    var _result_cross_modal_similarity = cross_modal_similarity(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_cross_modal_similarity = _summary_float64(_result_cross_modal_similarity)
    print("MOJO_RESULT multimodal::cross_modal_similarity", _summary_cross_modal_similarity)
    var _acc_image_token_count: Float64 = 0.0
    var _t0_image_token_count = perf_counter_ns()
    for _ in range(N):
        _acc_image_token_count += image_token_count(0.5, 0.5, 0.5)
    var _t1_image_token_count = perf_counter_ns()
    var _ns_image_token_count = Float64(_t1_image_token_count - _t0_image_token_count) / Float64(N)
    print("MOJO_TIMING multimodal::image_token_count", _ns_image_token_count, _acc_image_token_count)
    var _result_image_token_count = image_token_count(0.5, 0.5, 0.5)
    var _summary_image_token_count = _summary_float64(_result_image_token_count)
    print("MOJO_RESULT multimodal::image_token_count", _summary_image_token_count)
    var _acc_ocr_confidence_score: Float64 = 0.0
    var _t0_ocr_confidence_score = perf_counter_ns()
    for _ in range(N):
        _acc_ocr_confidence_score += ocr_confidence_score(0.5, 0.5)
    var _t1_ocr_confidence_score = perf_counter_ns()
    var _ns_ocr_confidence_score = Float64(_t1_ocr_confidence_score - _t0_ocr_confidence_score) / Float64(N)
    print("MOJO_TIMING multimodal::ocr_confidence_score", _ns_ocr_confidence_score, _acc_ocr_confidence_score)
    var _result_ocr_confidence_score = ocr_confidence_score(0.5, 0.5)
    var _summary_ocr_confidence_score = _summary_float64(_result_ocr_confidence_score)
    print("MOJO_RESULT multimodal::ocr_confidence_score", _summary_ocr_confidence_score)
    var _acc_multimodal_fusion_weight: Float64 = 0.0
    var _t0_multimodal_fusion_weight = perf_counter_ns()
    for _ in range(N):
        _acc_multimodal_fusion_weight += multimodal_fusion_weight(0.5, 0.5, 0.5)
    var _t1_multimodal_fusion_weight = perf_counter_ns()
    var _ns_multimodal_fusion_weight = Float64(_t1_multimodal_fusion_weight - _t0_multimodal_fusion_weight) / Float64(N)
    print("MOJO_TIMING multimodal::multimodal_fusion_weight", _ns_multimodal_fusion_weight, _acc_multimodal_fusion_weight)
    var _result_multimodal_fusion_weight = multimodal_fusion_weight(0.5, 0.5, 0.5)
    var _summary_multimodal_fusion_weight = _summary_float64(_result_multimodal_fusion_weight)
    print("MOJO_RESULT multimodal::multimodal_fusion_weight", _summary_multimodal_fusion_weight)
