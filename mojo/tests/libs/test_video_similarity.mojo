"""test_video_similarity.mojo — auto-generated tests for video_similarity."""
from std.math import isnan, isinf
from video_similarity import frame_duplicate_scores, average_frame_duplicate_score, frame_hash_hamming_series, average_frame_hash_hamming, temporal_signature_distance, clip_duplicate_score_flat, is_duplicate_clip_flat

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
    var _v_frame_duplicate_scores = frame_duplicate_scores(_lf48_video3x4x4, _lf48_video3x4x4_alt, 4, 4, 1)
    if len(_v_frame_duplicate_scores) >= 0: passed += 1; print("  ✅ video_similarity::frame_duplicate_scores")
    var _v_average_frame_duplicate_score = average_frame_duplicate_score(_lf48_video3x4x4, _lf48_video3x4x4_alt, 4, 4, 1)
    if is_finite(_v_average_frame_duplicate_score): passed += 1; print("  ✅ video_similarity::average_frame_duplicate_score =", _v_average_frame_duplicate_score)
    else: failed += 1; print("  ❌ video_similarity::average_frame_duplicate_score → non-finite:", _v_average_frame_duplicate_score)
    var _v_frame_hash_hamming_series = frame_hash_hamming_series(_lf48_video3x4x4, _lf48_video3x4x4_alt, 4, 4, 1)
    if len(_v_frame_hash_hamming_series) >= 0: passed += 1; print("  ✅ video_similarity::frame_hash_hamming_series")
    var _v_average_frame_hash_hamming = average_frame_hash_hamming(_lf48_video3x4x4, _lf48_video3x4x4_alt, 4, 4, 1)
    if is_finite(_v_average_frame_hash_hamming): passed += 1; print("  ✅ video_similarity::average_frame_hash_hamming =", _v_average_frame_hash_hamming)
    else: failed += 1; print("  ❌ video_similarity::average_frame_hash_hamming → non-finite:", _v_average_frame_hash_hamming)
    var _v_temporal_signature_distance = temporal_signature_distance(_lf48_video3x4x4, _lf48_video3x4x4_alt, 4, 4, 1)
    if is_finite(_v_temporal_signature_distance): passed += 1; print("  ✅ video_similarity::temporal_signature_distance =", _v_temporal_signature_distance)
    else: failed += 1; print("  ❌ video_similarity::temporal_signature_distance → non-finite:", _v_temporal_signature_distance)
    var _v_clip_duplicate_score_flat = clip_duplicate_score_flat(_lf48_video3x4x4, _lf48_video3x4x4_alt, 4, 4, 1)
    if is_finite(_v_clip_duplicate_score_flat): passed += 1; print("  ✅ video_similarity::clip_duplicate_score_flat =", _v_clip_duplicate_score_flat)
    else: failed += 1; print("  ❌ video_similarity::clip_duplicate_score_flat → non-finite:", _v_clip_duplicate_score_flat)
    _ = is_duplicate_clip_flat(_lf48_video3x4x4, _lf48_video3x4x4_alt, 4, 4, 1, 0.85)
    passed += 1; print("  ✅ video_similarity::is_duplicate_clip_flat")

    print("  [video_similarity] Passed:", passed, "Failed:", failed)
