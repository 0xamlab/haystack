"""bench_multimodal.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from multimodal import image_patch_embed, image_patch_count, spectrogram_mel_freq, spectrogram_stft_magnitude, audio_feature_norm, vision_attention_scale, cross_modal_similarity, image_token_count, ocr_confidence_score, multimodal_fusion_weight
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

    var _acc_image_patch_embed: Float64 = 0.0
    var _t0_image_patch_embed = perf_counter_ns()
    for _ in range(N):
        _acc_image_patch_embed += image_patch_embed(0.5, 0.5, 0.5)
    var _t1_image_patch_embed = perf_counter_ns()
    var _ns_image_patch_embed = Float64(_t1_image_patch_embed - _t0_image_patch_embed) / Float64(N)
    print("MOJO_TIMING multimodal::image_patch_embed", _ns_image_patch_embed, _acc_image_patch_embed)
    var _acc_image_patch_count: Float64 = 0.0
    var _t0_image_patch_count = perf_counter_ns()
    for _ in range(N):
        _acc_image_patch_count += image_patch_count(0.5, 0.5)
    var _t1_image_patch_count = perf_counter_ns()
    var _ns_image_patch_count = Float64(_t1_image_patch_count - _t0_image_patch_count) / Float64(N)
    print("MOJO_TIMING multimodal::image_patch_count", _ns_image_patch_count, _acc_image_patch_count)
    var _acc_spectrogram_mel_freq: Float64 = 0.0
    var _t0_spectrogram_mel_freq = perf_counter_ns()
    for _ in range(N):
        _acc_spectrogram_mel_freq += spectrogram_mel_freq(0.5)
    var _t1_spectrogram_mel_freq = perf_counter_ns()
    var _ns_spectrogram_mel_freq = Float64(_t1_spectrogram_mel_freq - _t0_spectrogram_mel_freq) / Float64(N)
    print("MOJO_TIMING multimodal::spectrogram_mel_freq", _ns_spectrogram_mel_freq, _acc_spectrogram_mel_freq)
    var _acc_spectrogram_stft_magnitude: Float64 = 0.0
    var _t0_spectrogram_stft_magnitude = perf_counter_ns()
    for _ in range(N):
        _acc_spectrogram_stft_magnitude += spectrogram_stft_magnitude(0.5, 0.5)
    var _t1_spectrogram_stft_magnitude = perf_counter_ns()
    var _ns_spectrogram_stft_magnitude = Float64(_t1_spectrogram_stft_magnitude - _t0_spectrogram_stft_magnitude) / Float64(N)
    print("MOJO_TIMING multimodal::spectrogram_stft_magnitude", _ns_spectrogram_stft_magnitude, _acc_spectrogram_stft_magnitude)
    var _acc_audio_feature_norm: Float64 = 0.0
    var _t0_audio_feature_norm = perf_counter_ns()
    for _ in range(N):
        _acc_audio_feature_norm += audio_feature_norm(0.5, 0.5, 0.5)
    var _t1_audio_feature_norm = perf_counter_ns()
    var _ns_audio_feature_norm = Float64(_t1_audio_feature_norm - _t0_audio_feature_norm) / Float64(N)
    print("MOJO_TIMING multimodal::audio_feature_norm", _ns_audio_feature_norm, _acc_audio_feature_norm)
    var _acc_vision_attention_scale: Float64 = 0.0
    var _t0_vision_attention_scale = perf_counter_ns()
    for _ in range(N):
        _acc_vision_attention_scale += vision_attention_scale(0.5)
    var _t1_vision_attention_scale = perf_counter_ns()
    var _ns_vision_attention_scale = Float64(_t1_vision_attention_scale - _t0_vision_attention_scale) / Float64(N)
    print("MOJO_TIMING multimodal::vision_attention_scale", _ns_vision_attention_scale, _acc_vision_attention_scale)
    var _acc_cross_modal_similarity: Float64 = 0.0
    var _t0_cross_modal_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_cross_modal_similarity += cross_modal_similarity(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_cross_modal_similarity = perf_counter_ns()
    var _ns_cross_modal_similarity = Float64(_t1_cross_modal_similarity - _t0_cross_modal_similarity) / Float64(N)
    print("MOJO_TIMING multimodal::cross_modal_similarity", _ns_cross_modal_similarity, _acc_cross_modal_similarity)
    var _acc_image_token_count: Float64 = 0.0
    var _t0_image_token_count = perf_counter_ns()
    for _ in range(N):
        _acc_image_token_count += image_token_count(0.5, 0.5, 0.5)
    var _t1_image_token_count = perf_counter_ns()
    var _ns_image_token_count = Float64(_t1_image_token_count - _t0_image_token_count) / Float64(N)
    print("MOJO_TIMING multimodal::image_token_count", _ns_image_token_count, _acc_image_token_count)
    var _acc_ocr_confidence_score: Float64 = 0.0
    var _t0_ocr_confidence_score = perf_counter_ns()
    for _ in range(N):
        _acc_ocr_confidence_score += ocr_confidence_score(0.5, 0.5)
    var _t1_ocr_confidence_score = perf_counter_ns()
    var _ns_ocr_confidence_score = Float64(_t1_ocr_confidence_score - _t0_ocr_confidence_score) / Float64(N)
    print("MOJO_TIMING multimodal::ocr_confidence_score", _ns_ocr_confidence_score, _acc_ocr_confidence_score)
    var _acc_multimodal_fusion_weight: Float64 = 0.0
    var _t0_multimodal_fusion_weight = perf_counter_ns()
    for _ in range(N):
        _acc_multimodal_fusion_weight += multimodal_fusion_weight(0.5, 0.5, 0.5)
    var _t1_multimodal_fusion_weight = perf_counter_ns()
    var _ns_multimodal_fusion_weight = Float64(_t1_multimodal_fusion_weight - _t0_multimodal_fusion_weight) / Float64(N)
    print("MOJO_TIMING multimodal::multimodal_fusion_weight", _ns_multimodal_fusion_weight, _acc_multimodal_fusion_weight)
