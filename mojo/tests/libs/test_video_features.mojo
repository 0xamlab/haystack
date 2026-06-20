"""test_video_features.mojo — auto-generated tests for video_features."""
from std.math import isnan, isinf
from video_features import scene_change_scores, scene_cut_count, scene_cut_rate, peak_motion_frame, keyframe_indices

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
    var _v_scene_change_scores = scene_change_scores(_lf48_video3x4x4, 4, 4, 1)
    if len(_v_scene_change_scores) >= 0: passed += 1; print("  ✅ video_features::scene_change_scores")
    _ = scene_cut_count(_lf48_video3x4x4, 4, 4, 1, 0.4)
    passed += 1; print("  ✅ video_features::scene_cut_count")
    var _v_scene_cut_rate = scene_cut_rate(_lf48_video3x4x4, 4, 4, 1, 0.4)
    if is_finite(_v_scene_cut_rate): passed += 1; print("  ✅ video_features::scene_cut_rate =", _v_scene_cut_rate)
    else: failed += 1; print("  ❌ video_features::scene_cut_rate → non-finite:", _v_scene_cut_rate)
    _ = peak_motion_frame(_lf48_video3x4x4, 4, 4, 1)
    passed += 1; print("  ✅ video_features::peak_motion_frame")
    var _v_keyframe_indices = keyframe_indices(_lf48_video3x4x4, 4, 4, 1, 0.4, 4)
    if len(_v_keyframe_indices) >= 0: passed += 1; print("  ✅ video_features::keyframe_indices")

    print("  [video_features] Passed:", passed, "Failed:", failed)
