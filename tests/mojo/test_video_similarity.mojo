"""
test_video_similarity.mojo — Tests for the pure-Mojo video_similarity library.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_video_similarity.mojo
"""
from video_similarity import (
    frame_duplicate_scores,
    average_frame_duplicate_score,
    frame_hash_hamming_series,
    average_frame_hash_hamming,
    temporal_signature_distance,
    clip_duplicate_score_flat,
    is_duplicate_clip_flat,
)


def _assert_true(cond: Bool, label: String) raises:
    if not cond:
        print("❌ FAIL: " + label)
        raise Error("assertion failed: " + label)


def _assert_close(got: Float64, expected: Float64, tol: Float64, label: String) raises:
    var diff = got - expected
    if diff < 0.0:
        diff = -diff
    if diff > tol:
        print("❌ FAIL: " + label)
        print("   expected: " + String(expected) + " ± " + String(tol))
        print("   got:      " + String(got))
        raise Error("assertion failed: " + label)


def _assert_eq_int(got: Int, expected: Int, label: String) raises:
    if got != expected:
        print("❌ FAIL: " + label)
        print("   expected: " + String(expected))
        print("   got:      " + String(got))
        raise Error("assertion failed: " + label)


fn _base_clip3x4x4() -> List[Float64]:
    var flat = List[Float64]()
    for _ in range(16):
        flat.append(10.0)
    for pixel in range(16):
        if pixel < 4:
            flat.append(200.0)
        else:
            flat.append(10.0)
    for _ in range(16):
        flat.append(200.0)
    return flat^


fn _near_clip3x4x4() -> List[Float64]:
    var flat = List[Float64]()
    for _ in range(16):
        flat.append(12.0)
    for pixel in range(16):
        if pixel < 4:
            flat.append(188.0)
        else:
            flat.append(12.0)
    for _ in range(16):
        flat.append(192.0)
    return flat^


fn _far_clip3x4x4() -> List[Float64]:
    var flat = List[Float64]()
    for _ in range(16):
        flat.append(200.0)
    for _ in range(16):
        flat.append(10.0)
    for pixel in range(16):
        if (pixel % 4) < 2:
            flat.append(200.0)
        else:
            flat.append(10.0)
    return flat^


def test_identical_clip_similarity() raises:
    var base = _base_clip3x4x4()
    var scores = frame_duplicate_scores(base, base, 4, 4, 1)
    _assert_eq_int(len(scores), 3, "three aligned frame scores")
    _assert_close(scores[0], 1.0, 1e-9, "frame 0 duplicate")
    _assert_close(scores[1], 1.0, 1e-9, "frame 1 duplicate")
    _assert_close(scores[2], 1.0, 1e-9, "frame 2 duplicate")
    _assert_close(
        average_frame_duplicate_score(base, base, 4, 4, 1),
        1.0,
        1e-9,
        "average duplicate score",
    )

    var distances = frame_hash_hamming_series(base, base, 4, 4, 1)
    _assert_eq_int(len(distances), 3, "three frame hash distances")
    _assert_eq_int(distances[0], 0, "frame 0 hash distance")
    _assert_eq_int(distances[1], 0, "frame 1 hash distance")
    _assert_eq_int(distances[2], 0, "frame 2 hash distance")
    _assert_close(
        average_frame_hash_hamming(base, base, 4, 4, 1),
        0.0,
        1e-9,
        "average frame hash hamming",
    )
    _assert_close(
        temporal_signature_distance(base, base, 4, 4, 1),
        0.0,
        1e-9,
        "temporal distance identical",
    )
    _assert_close(
        clip_duplicate_score_flat(base, base, 4, 4, 1),
        1.0,
        1e-9,
        "clip duplicate score identical",
    )
    _assert_true(
        is_duplicate_clip_flat(base, base, 4, 4, 1, 0.98),
        "identical clips pass duplicate threshold",
    )
    print("✅ identical clip similarity")


def test_near_vs_far_clip_similarity() raises:
    var base = _base_clip3x4x4()
    var near = _near_clip3x4x4()
    var far = _far_clip3x4x4()

    var near_score = clip_duplicate_score_flat(base, near, 4, 4, 1)
    var far_score = clip_duplicate_score_flat(base, far, 4, 4, 1)
    _assert_true(near_score > 0.9, "near clip keeps a strong duplicate score")
    _assert_true(far_score < 0.7, "far clip reduces duplicate score")
    _assert_true(near_score > far_score, "near clip outranks far clip")

    var near_hash = average_frame_hash_hamming(base, near, 4, 4, 1)
    var far_hash = average_frame_hash_hamming(base, far, 4, 4, 1)
    _assert_true(near_hash <= far_hash, "near clip hash distance stays below far clip")

    var near_temporal = temporal_signature_distance(base, near, 4, 4, 1)
    var far_temporal = temporal_signature_distance(base, far, 4, 4, 1)
    _assert_true(near_temporal < far_temporal, "near clip temporal distance is smaller")
    _assert_true(
        not is_duplicate_clip_flat(base, far, 4, 4, 1, 0.9),
        "far clip fails a strict duplicate threshold",
    )
    print("✅ near-vs-far clip similarity")


def main() raises:
    print("━━━ video_similarity test suite ━━━")
    test_identical_clip_similarity()
    test_near_vs_far_clip_similarity()
    print("━━━ All video_similarity tests passed ━━━")
