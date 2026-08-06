"""test_video_accessibility.mojo — auto-generated tests for video_accessibility."""
from std.math import isnan, isinf
from video_accessibility import frame_min_preferred_text_contrast_for_video, frame_preferred_text_color_for_video, sampled_video_min_text_contrast, sampled_video_wcag_safe_ratio, needs_text_backplate_for_video, subtitle_band_min_preferred_text_contrast_for_video, subtitle_band_preferred_text_color_for_video, sampled_subtitle_band_wcag_safe_ratio, subtitle_band_needs_backplate_for_video

def is_finite(x: Float64) -> Bool:
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
    var _v_frame_min_preferred_text_contrast_for_video = frame_min_preferred_text_contrast_for_video(_lf36_video_rgb3x2x2, 2, 2, 3, 1)
    if is_finite(_v_frame_min_preferred_text_contrast_for_video): passed += 1; print("  ✅ video_accessibility::frame_min_preferred_text_contrast_for_video =", _v_frame_min_preferred_text_contrast_for_video)
    else: failed += 1; print("  ❌ video_accessibility::frame_min_preferred_text_contrast_for_video → non-finite:", _v_frame_min_preferred_text_contrast_for_video)
    _ = frame_preferred_text_color_for_video(_lf36_video_rgb3x2x2, 2, 2, 3, 1)
    passed += 1; print("  ✅ video_accessibility::frame_preferred_text_color_for_video")
    var _v_sampled_video_min_text_contrast = sampled_video_min_text_contrast(_lf36_video_rgb3x2x2, 2, 2, 3, 3)
    if is_finite(_v_sampled_video_min_text_contrast): passed += 1; print("  ✅ video_accessibility::sampled_video_min_text_contrast =", _v_sampled_video_min_text_contrast)
    else: failed += 1; print("  ❌ video_accessibility::sampled_video_min_text_contrast → non-finite:", _v_sampled_video_min_text_contrast)
    var _v_sampled_video_wcag_safe_ratio = sampled_video_wcag_safe_ratio(_lf36_video_rgb3x2x2, 2, 2, 3, 3, 16.0, False)
    if is_finite(_v_sampled_video_wcag_safe_ratio): passed += 1; print("  ✅ video_accessibility::sampled_video_wcag_safe_ratio =", _v_sampled_video_wcag_safe_ratio)
    else: failed += 1; print("  ❌ video_accessibility::sampled_video_wcag_safe_ratio → non-finite:", _v_sampled_video_wcag_safe_ratio)
    _ = needs_text_backplate_for_video(_lf36_video_rgb3x2x2, 2, 2, 3, 3, 16.0, False)
    passed += 1; print("  ✅ video_accessibility::needs_text_backplate_for_video")
    var _v_subtitle_band_min_preferred_text_contrast_for_video = subtitle_band_min_preferred_text_contrast_for_video(_lf36_video_rgb3x2x2, 2, 2, 3, 3, 1)
    if is_finite(_v_subtitle_band_min_preferred_text_contrast_for_video): passed += 1; print("  ✅ video_accessibility::subtitle_band_min_preferred_text_contrast_for_video =", _v_subtitle_band_min_preferred_text_contrast_for_video)
    else: failed += 1; print("  ❌ video_accessibility::subtitle_band_min_preferred_text_contrast_for_video → non-finite:", _v_subtitle_band_min_preferred_text_contrast_for_video)
    _ = subtitle_band_preferred_text_color_for_video(_lf36_video_rgb3x2x2, 2, 2, 3, 3, 1)
    passed += 1; print("  ✅ video_accessibility::subtitle_band_preferred_text_color_for_video")
    var _v_sampled_subtitle_band_wcag_safe_ratio = sampled_subtitle_band_wcag_safe_ratio(_lf36_video_rgb3x2x2, 2, 2, 3, 3, 1, 16.0, False)
    if is_finite(_v_sampled_subtitle_band_wcag_safe_ratio): passed += 1; print("  ✅ video_accessibility::sampled_subtitle_band_wcag_safe_ratio =", _v_sampled_subtitle_band_wcag_safe_ratio)
    else: failed += 1; print("  ❌ video_accessibility::sampled_subtitle_band_wcag_safe_ratio → non-finite:", _v_sampled_subtitle_band_wcag_safe_ratio)
    _ = subtitle_band_needs_backplate_for_video(_lf36_video_rgb3x2x2, 2, 2, 3, 3, 1, 16.0, False)
    passed += 1; print("  ✅ video_accessibility::subtitle_band_needs_backplate_for_video")

    print("  [video_accessibility] Passed:", passed, "Failed:", failed)
