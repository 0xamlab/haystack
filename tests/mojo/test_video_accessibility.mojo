"""
Test_video_accessibility.mojo — Tests for the pure-Mojo video_accessibility library.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_video_accessibility.mojo
"""
from video_accessibility import (
    frame_min_preferred_text_contrast_for_video,
    frame_preferred_text_color_for_video,
    sampled_video_min_text_contrast,
    sampled_video_wcag_safe_ratio,
    needs_text_backplate_for_video,
    subtitle_band_min_preferred_text_contrast_for_video,
    subtitle_band_preferred_text_color_for_video,
    sampled_subtitle_band_wcag_safe_ratio,
    subtitle_band_needs_backplate_for_video,
)


def _assert_true(cond: Bool, label: String) raises:
    if not cond:
        print("❌ FAIL: " + label)
        raise Error("assertion failed: " + label)


def _assert_false(cond: Bool, label: String) raises:
    _assert_true(not cond, label)


def _assert_close(got: Float64, expected: Float64, tol: Float64, label: String) raises:
    var diff = got - expected
    if diff < 0.0:
        diff = -diff
    if diff > tol:
        print("❌ FAIL: " + label)
        print("   expected: " + String(expected) + " ± " + String(tol))
        print("   got:      " + String(got))
        raise Error("assertion failed: " + label)


def _assert_eq_string(got: String, expected: String, label: String) raises:
    if got != expected:
        print("❌ FAIL: " + label)
        print("   expected: " + expected)
        print("   got:      " + got)
        raise Error("assertion failed: " + label)


def _mixed_caption_clip() -> List[Float64]:
    var flat = List[Float64]()
    for _ in range(4):
        flat.append(20.0); flat.append(20.0); flat.append(20.0)
    flat.append(20.0); flat.append(20.0); flat.append(20.0)
    flat.append(20.0); flat.append(20.0); flat.append(20.0)
    flat.append(20.0); flat.append(20.0); flat.append(20.0)
    flat.append(220.0); flat.append(220.0); flat.append(220.0)
    for _ in range(4):
        flat.append(220.0); flat.append(220.0); flat.append(220.0)
    return flat^


def test_frame_level_accessibility() raises:
    var clip = _mixed_caption_clip()
    _assert_close(
        frame_min_preferred_text_contrast_for_video(clip, 2, 2, 3, 0),
        18.422536070011546,
        1e-9,
        "frame_min_preferred_text_contrast_for_video frame 0",
    )
    _assert_eq_string(
        frame_preferred_text_color_for_video(clip, 2, 2, 3, 0),
        "#FFFFFF",
        "frame_preferred_text_color_for_video frame 0",
    )
    _assert_close(
        frame_min_preferred_text_contrast_for_video(clip, 2, 2, 3, 1),
        1.3713058806238527,
        1e-9,
        "frame_min_preferred_text_contrast_for_video frame 1",
    )
    _assert_eq_string(
        frame_preferred_text_color_for_video(clip, 2, 2, 3, 1),
        "#FFFFFF",
        "frame_preferred_text_color_for_video frame 1",
    )
    _assert_eq_string(
        frame_preferred_text_color_for_video(clip, 2, 2, 3, 2),
        "#000000",
        "frame_preferred_text_color_for_video frame 2",
    )
    print("✅ frame-level accessibility")


def test_sampled_video_accessibility() raises:
    var clip = _mixed_caption_clip()
    _assert_close(
        sampled_video_min_text_contrast(clip, 2, 2, 3, 3),
        1.3713058806238527,
        1e-9,
        "sampled_video_min_text_contrast",
    )
    _assert_close(
        sampled_video_wcag_safe_ratio(clip, 2, 2, 3, 3, 16.0, False),
        2.0 / 3.0,
        1e-9,
        "sampled_video_wcag_safe_ratio",
    )
    _assert_true(
        needs_text_backplate_for_video(clip, 2, 2, 3, 3, 16.0, False),
        "needs_text_backplate_for_video",
    )
    print("✅ sampled frame safety")


def test_subtitle_band_accessibility() raises:
    var clip = _mixed_caption_clip()
    _assert_close(
        subtitle_band_min_preferred_text_contrast_for_video(clip, 2, 2, 3, 3, 1),
        1.3713058806238527,
        1e-9,
        "subtitle_band_min_preferred_text_contrast_for_video",
    )
    _assert_eq_string(
        subtitle_band_preferred_text_color_for_video(clip, 2, 2, 3, 3, 1),
        "#FFFFFF",
        "subtitle_band_preferred_text_color_for_video",
    )
    _assert_close(
        sampled_subtitle_band_wcag_safe_ratio(clip, 2, 2, 3, 3, 1, 16.0, False),
        2.0 / 3.0,
        1e-9,
        "sampled_subtitle_band_wcag_safe_ratio",
    )
    _assert_true(
        subtitle_band_needs_backplate_for_video(clip, 2, 2, 3, 3, 1, 16.0, False),
        "subtitle_band_needs_backplate_for_video",
    )
    _assert_false(
        subtitle_band_needs_backplate_for_video(clip, 2, 2, 3, 1, 1, 24.0, True),
        "subtitle_band_needs_backplate_for_video safe first frame",
    )
    print("✅ subtitle-band safety")


def main() raises:
    print("━━━ video_accessibility test suite ━━━")
    test_frame_level_accessibility()
    test_sampled_video_accessibility()
    test_subtitle_band_accessibility()
    print("━━━ All video_accessibility tests passed ━━━")
