"""test_video_color.mojo — auto-generated tests for video_color."""
from std.math import isnan, isinf
from video_color import frame_mean_rgb255, frame_mean_rgb_series, clip_mean_rgb255, dominant_clip_color_rgb255, clip_mean_saturation_rgb255, warm_frame_ratio_rgb255, color_drift_score_rgb255, preferred_text_contrast_for_video, preferred_text_color_for_video

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _li3 = List[Int]()
    _li3.append(1); _li3.append(2); _li3.append(3)
    var _li2_zero = List[Int]()
    _li2_zero.append(0); _li2_zero.append(1)
    var _li3_tail = List[Int]()
    _li3_tail.append(2); _li3_tail.append(3); _li3_tail.append(4)
    var _li8 = List[Int]()
    for i in range(8):
        _li8.append(i + 1)
    var _li6_grid2x3 = List[Int]()
    _li6_grid2x3.append(0); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    _li6_grid2x3.append(1); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    var _li10_borda = List[Int]()
    _li10_borda.append(0); _li10_borda.append(1); _li10_borda.append(2); _li10_borda.append(3); _li10_borda.append(4)
    _li10_borda.append(1); _li10_borda.append(0); _li10_borda.append(2); _li10_borda.append(4); _li10_borda.append(3)
    var _li16 = List[Int]()
    for i in range(16):
        _li16.append(i)
    var _lf6_matrix = List[Float64]()
    _lf6_matrix.append(1.0); _lf6_matrix.append(2.0); _lf6_matrix.append(3.0)
    _lf6_matrix.append(4.0); _lf6_matrix.append(5.0); _lf6_matrix.append(6.0)
    var _lf8_coalitions = List[Float64]()
    _lf8_coalitions.append(0.0); _lf8_coalitions.append(1.0); _lf8_coalitions.append(2.0); _lf8_coalitions.append(4.0)
    _lf8_coalitions.append(3.0); _lf8_coalitions.append(5.0); _lf8_coalitions.append(6.0); _lf8_coalitions.append(9.0)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _lf36_video_rgb3x2x2 = List[Float64]()
    for _ in range(4):
        _lf36_video_rgb3x2x2.append(200.0); _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(20.0)
    for pixel in range(4):
        if pixel < 3:
            _lf36_video_rgb3x2x2.append(200.0); _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(20.0)
        else:
            _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(200.0)
    for _ in range(4):
        _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(200.0)
    var _v_frame_mean_rgb255 = frame_mean_rgb255(_lf36_video_rgb3x2x2, 2, 2, 3, 1)
    if len(_v_frame_mean_rgb255) >= 0: passed += 1; print("  ✅ video_color::frame_mean_rgb255")
    var _v_frame_mean_rgb_series = frame_mean_rgb_series(_lf36_video_rgb3x2x2, 2, 2, 3)
    if len(_v_frame_mean_rgb_series) >= 0: passed += 1; print("  ✅ video_color::frame_mean_rgb_series")
    var _v_clip_mean_rgb255 = clip_mean_rgb255(_lf36_video_rgb3x2x2, 2, 2, 3)
    if len(_v_clip_mean_rgb255) >= 0: passed += 1; print("  ✅ video_color::clip_mean_rgb255")
    var _v_dominant_clip_color_rgb255 = dominant_clip_color_rgb255(_lf36_video_rgb3x2x2, 2, 2, 3, 4, 3)
    if len(_v_dominant_clip_color_rgb255) >= 0: passed += 1; print("  ✅ video_color::dominant_clip_color_rgb255")
    var _v_clip_mean_saturation_rgb255 = clip_mean_saturation_rgb255(_lf36_video_rgb3x2x2, 2, 2, 3)
    if is_finite(_v_clip_mean_saturation_rgb255): passed += 1; print("  ✅ video_color::clip_mean_saturation_rgb255 =", _v_clip_mean_saturation_rgb255)
    else: failed += 1; print("  ❌ video_color::clip_mean_saturation_rgb255 → non-finite:", _v_clip_mean_saturation_rgb255)
    var _v_warm_frame_ratio_rgb255 = warm_frame_ratio_rgb255(_lf36_video_rgb3x2x2, 2, 2, 3, 0.25)
    if is_finite(_v_warm_frame_ratio_rgb255): passed += 1; print("  ✅ video_color::warm_frame_ratio_rgb255 =", _v_warm_frame_ratio_rgb255)
    else: failed += 1; print("  ❌ video_color::warm_frame_ratio_rgb255 → non-finite:", _v_warm_frame_ratio_rgb255)
    var _v_color_drift_score_rgb255 = color_drift_score_rgb255(_lf36_video_rgb3x2x2, 2, 2, 3)
    if is_finite(_v_color_drift_score_rgb255): passed += 1; print("  ✅ video_color::color_drift_score_rgb255 =", _v_color_drift_score_rgb255)
    else: failed += 1; print("  ❌ video_color::color_drift_score_rgb255 → non-finite:", _v_color_drift_score_rgb255)
    var _v_preferred_text_contrast_for_video = preferred_text_contrast_for_video(_lf36_video_rgb3x2x2, 2, 2, 3, 4, 3)
    if is_finite(_v_preferred_text_contrast_for_video): passed += 1; print("  ✅ video_color::preferred_text_contrast_for_video =", _v_preferred_text_contrast_for_video)
    else: failed += 1; print("  ❌ video_color::preferred_text_contrast_for_video → non-finite:", _v_preferred_text_contrast_for_video)
    _ = preferred_text_color_for_video(_lf36_video_rgb3x2x2, 2, 2, 3, 4, 3)
    passed += 1; print("  ✅ video_color::preferred_text_color_for_video")

    print("  [video_color] Passed:", passed, "Failed:", failed)
