"""
Test_video_color.mojo — Tests for the pure-Mojo video_color library.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_video_color.mojo
"""
from video_color import (
    frame_mean_rgb255,
    frame_mean_rgb_series,
    clip_mean_rgb255,
    dominant_clip_color_rgb255,
    clip_mean_saturation_rgb255,
    warm_frame_ratio_rgb255,
    color_drift_score_rgb255,
    preferred_text_contrast_for_video,
    preferred_text_color_for_video,
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


def _assert_eq_string(got: String, expected: String, label: String) raises:
    if got != expected:
        print("❌ FAIL: " + label)
        print("   expected: " + expected)
        print("   got:      " + got)
        raise Error("assertion failed: " + label)


def _assert_close_list(got: List[Float64], expected: List[Float64], tol: Float64, label: String) raises:
    if len(got) != len(expected):
        print("❌ FAIL: " + label)
        print("   expected len: " + String(len(expected)))
        print("   got len:      " + String(len(got)))
        raise Error("assertion failed: " + label)
    for index in range(len(expected)):
        var diff = got[index] - expected[index]
        if diff < 0.0:
            diff = -diff
        if diff > tol:
            print("❌ FAIL: " + label)
            print("   mismatch at index " + String(index))
            print("   expected: " + String(expected[index]))
            print("   got:      " + String(got[index]))
            raise Error("assertion failed: " + label)


def _list_float3(a: Float64, b: Float64, c: Float64) -> List[Float64]:
    var out = List[Float64]()
    out.append(a)
    out.append(b)
    out.append(c)
    return out^


def _list_float4(a: Float64, b: Float64, c: Float64, d: Float64) -> List[Float64]:
    var out = List[Float64]()
    out.append(a)
    out.append(b)
    out.append(c)
    out.append(d)
    return out^


def _list_float9(
    a: Float64, b: Float64, c: Float64,
    d: Float64, e: Float64, f: Float64,
    g: Float64, h: Float64, i: Float64,
) -> List[Float64]:
    var out = List[Float64]()
    out.append(a); out.append(b); out.append(c)
    out.append(d); out.append(e); out.append(f)
    out.append(g); out.append(h); out.append(i)
    return out^


def _clip_rgb_three_frames() -> List[Float64]:
    var flat = List[Float64]()
    for _ in range(4):
        flat.append(200.0); flat.append(20.0); flat.append(20.0)
    for pixel in range(4):
        if pixel < 3:
            flat.append(200.0); flat.append(20.0); flat.append(20.0)
        else:
            flat.append(20.0); flat.append(20.0); flat.append(200.0)
    for _ in range(4):
        flat.append(20.0); flat.append(20.0); flat.append(200.0)
    return flat^


def test_frame_and_clip_means() raises:
    var clip = _clip_rgb_three_frames()
    _assert_close_list(
        frame_mean_rgb255(clip, 2, 2, 3, 0),
        _list_float3(200.0, 20.0, 20.0),
        1e-9,
        "frame_mean_rgb255 frame 0",
    )
    _assert_close_list(
        frame_mean_rgb255(clip, 2, 2, 3, 1),
        _list_float3(155.0, 20.0, 65.0),
        1e-9,
        "frame_mean_rgb255 frame 1",
    )
    _assert_close_list(
        frame_mean_rgb_series(clip, 2, 2, 3),
        _list_float9(200.0, 20.0, 20.0, 155.0, 20.0, 65.0, 20.0, 20.0, 200.0),
        1e-9,
        "frame_mean_rgb_series",
    )
    _assert_close_list(
        clip_mean_rgb255(clip, 2, 2, 3),
        _list_float3(125.0, 20.0, 95.0),
        1e-9,
        "clip_mean_rgb255",
    )
    print("✅ frame / clip means")


def test_palette_and_readability() raises:
    var clip = _clip_rgb_three_frames()
    _assert_close_list(
        dominant_clip_color_rgb255(clip, 2, 2, 3, 4, 3),
        _list_float4(200.0, 20.0, 20.0, 0.5833333333333334),
        1e-9,
        "dominant_clip_color_rgb255",
    )
    _assert_close(
        preferred_text_contrast_for_video(clip, 2, 2, 3, 4, 3),
        5.8888921644276735,
        1e-8,
        "preferred_text_contrast_for_video",
    )
    _assert_eq_string(
        preferred_text_color_for_video(clip, 2, 2, 3, 4, 3),
        "#FFFFFF",
        "preferred_text_color_for_video",
    )
    print("✅ palette / readability")


def test_saturation_warmth_and_drift() raises:
    var clip = _clip_rgb_three_frames()
    _assert_close(
        clip_mean_saturation_rgb255(clip, 2, 2, 3),
        0.9,
        1e-9,
        "clip_mean_saturation_rgb255",
    )
    _assert_close(
        warm_frame_ratio_rgb255(clip, 2, 2, 3, 0.25),
        2.0 / 3.0,
        1e-9,
        "warm_frame_ratio_rgb255",
    )
    _assert_close(
        color_drift_score_rgb255(clip, 2, 2, 3),
        0.2881752638568445,
        1e-9,
        "color_drift_score_rgb255",
    )
    print("✅ saturation / warmth / drift")


def main() raises:
    print("━━━ video_color test suite ━━━")
    test_frame_and_clip_means()
    test_palette_and_readability()
    test_saturation_warmth_and_drift()
    print("━━━ All video_color tests passed ━━━")
