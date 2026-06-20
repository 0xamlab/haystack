"""
test_video_quality.mojo — Tests for the pure-Mojo video_quality library.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_video_quality.mojo
"""
from video_quality import (
    frame_quality_series,
    average_frame_quality,
    brightness_flicker_score,
    temporal_stability_score,
    video_quality_score,
    is_usable_video,
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


fn _bad_clip() -> List[Float64]:
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


fn _good_clip() -> List[Float64]:
    var flat = List[Float64]()
    for frame_index in range(3):
        for y in range(4):
            for x in range(4):
                flat.append(40.0 + Float64(x * 20 + y * 15 + frame_index * 10))
    return flat^


def test_quality_series_and_flicker() raises:
    var clip = _bad_clip()
    var qualities = frame_quality_series(clip, 4, 4, 1, 3)
    _assert_true(len(qualities) == 3, "three quality samples")
    _assert_true(qualities[1] > qualities[2] and qualities[2] > qualities[0], "quality ordering")
    _assert_close(brightness_flicker_score(clip, 4, 4, 1), 95.0, 1e-9, "brightness_flicker_score")
    _assert_close(
        temporal_stability_score(clip, 4, 4, 1),
        1.0 / (1.0 + 95.0 / 48.0),
        1e-9,
        "temporal_stability_score",
    )
    print("✅ quality series and flicker")


def test_video_quality_score() raises:
    var bad = _bad_clip()
    var good = _good_clip()
    var bad_score = video_quality_score(bad, 4, 4, 1, 3)
    var good_score = video_quality_score(good, 4, 4, 1, 3)
    _assert_true(good_score > bad_score, "good clip scores higher")
    _assert_true(good_score >= 0.35, "good clip usable")
    _assert_true(bad_score < 0.35, "bad clip not usable")
    _assert_true(is_usable_video(good, 4, 4, 1, 3, 0.35), "good clip usable")
    _assert_true(not is_usable_video(bad, 4, 4, 1, 3, 0.35), "bad clip not usable")
    _assert_true(
        average_frame_quality(good, 4, 4, 1, 3) > average_frame_quality(bad, 4, 4, 1, 3),
        "average_frame_quality ordering",
    )
    print("✅ video quality score")


def main() raises:
    print("━━━ video_quality test suite ━━━")
    test_quality_series_and_flicker()
    test_video_quality_score()
    print("━━━ All video_quality tests passed ━━━")
