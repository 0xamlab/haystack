"""
test_video_features.mojo — Tests for the pure-Mojo video_features library.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_video_features.mojo
"""
from video_features import (
    scene_change_scores,
    scene_cut_count,
    scene_cut_rate,
    peak_motion_frame,
    keyframe_indices,
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


fn _clip_three_frames() -> List[Float64]:
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


def test_scene_scores_and_cuts() raises:
    var clip = _clip_three_frames()
    var scores = scene_change_scores(clip, 4, 4, 1)
    _assert_true(len(scores) == 2, "two transition scores")
    _assert_close(scores[0], 47.5 / 255.0, 1e-9, "score 0→1")
    _assert_close(scores[1], 142.5 / 255.0, 1e-9, "score 1→2")
    _assert_eq_int(scene_cut_count(clip, 4, 4, 1, 0.4), 1, "scene_cut_count")
    _assert_close(scene_cut_rate(clip, 4, 4, 1, 0.4), 0.5, 1e-9, "scene_cut_rate")
    print("✅ scene scores and cuts")


def test_keyframes_and_peak_motion() raises:
    var clip = _clip_three_frames()
    _assert_eq_int(peak_motion_frame(clip, 4, 4, 1), 2, "peak_motion_frame")
    var keys = keyframe_indices(clip, 4, 4, 1, 0.4, 4)
    _assert_true(len(keys) == 2, "keyframe count")
    _assert_eq_int(keys[0], 0, "first keyframe")
    _assert_eq_int(keys[1], 2, "cut keyframe")
    print("✅ keyframes and peak motion")


def main() raises:
    print("━━━ video_features test suite ━━━")
    test_scene_scores_and_cuts()
    test_keyframes_and_peak_motion()
    print("━━━ All video_features tests passed ━━━")
