"""
test_video_ops.mojo — Tests for the pure-Mojo video_ops library.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_video_ops.mojo
"""
from video_ops import (
    frame_count_from_flat,
    frame_mean_intensity,
    frame_mean_intensities,
    frame_mean_abs_diff,
    temporal_mean_abs_diff,
    temporal_max_abs_diff,
    freeze_frame_ratio,
    sample_frame_indices,
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


def _clip_three_frames() -> List[Float64]:
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


def test_frame_counts_and_means() raises:
    var clip = _clip_three_frames()
    _assert_eq_int(frame_count_from_flat(clip, 4, 4, 1), 3, "frame_count_from_flat")
    _assert_close(frame_mean_intensity(clip, 4, 4, 1, 0), 10.0, 1e-9, "frame0 mean")
    _assert_close(frame_mean_intensity(clip, 4, 4, 1, 1), 57.5, 1e-9, "frame1 mean")
    _assert_close(frame_mean_intensity(clip, 4, 4, 1, 2), 200.0, 1e-9, "frame2 mean")
    var means = frame_mean_intensities(clip, 4, 4, 1)
    _assert_true(len(means) == 3, "frame_mean_intensities length")
    _assert_close(means[1], 57.5, 1e-9, "frame_mean_intensities[1]")
    print("✅ frame counts and means")


def test_temporal_differences() raises:
    var clip = _clip_three_frames()
    _assert_close(frame_mean_abs_diff(clip, 4, 4, 1, 0, 1), 47.5, 1e-9, "diff 0→1")
    _assert_close(frame_mean_abs_diff(clip, 4, 4, 1, 1, 2), 142.5, 1e-9, "diff 1→2")
    _assert_close(temporal_mean_abs_diff(clip, 4, 4, 1), 95.0, 1e-9, "temporal mean diff")
    _assert_close(temporal_max_abs_diff(clip, 4, 4, 1), 142.5, 1e-9, "temporal max diff")
    _assert_close(freeze_frame_ratio(clip, 4, 4, 1, 50.0), 0.5, 1e-9, "freeze ratio")
    print("✅ temporal differences")


def test_sampling() raises:
    var clip = _clip_three_frames()
    var picks2 = sample_frame_indices(clip, 4, 4, 1, 2)
    _assert_true(len(picks2) == 2, "2 picks")
    _assert_eq_int(picks2[0], 0, "2 picks start")
    _assert_eq_int(picks2[1], 2, "2 picks end")
    var picks3 = sample_frame_indices(clip, 4, 4, 1, 3)
    _assert_true(len(picks3) == 3, "3 picks")
    _assert_eq_int(picks3[1], 1, "3 picks middle")
    print("✅ frame sampling")


def main() raises:
    print("━━━ video_ops test suite ━━━")
    test_frame_counts_and_means()
    test_temporal_differences()
    test_sampling()
    print("━━━ All video_ops tests passed ━━━")
