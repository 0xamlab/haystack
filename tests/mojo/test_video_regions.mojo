"""
test_video_regions.mojo — Tests for the pure-Mojo video_regions library.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_video_regions.mojo
"""
from video_regions import (
    frame_diff_mask_flat,
    motion_boxes_between_frames,
    largest_motion_box_between_frames,
    temporal_motion_area_series,
    peak_motion_box_flat,
    temporal_union_motion_box_flat,
    motion_coverage_ratio_flat,
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


fn _count_foreground(mask: List[Float64], threshold: Float64) -> Int:
    var count = 0
    for value in mask:
        if value >= threshold:
            count += 1
    return count


fn _motion_clip3x5x5() -> List[Float64]:
    var flat = List[Float64]()
    for _ in range(25):
        flat.append(10.0)
    for y in range(5):
        for x in range(5):
            if y >= 1 and y <= 2 and x >= 1 and x <= 2:
                flat.append(200.0)
            else:
                flat.append(10.0)
    for y in range(5):
        for x in range(5):
            if (y >= 1 and y <= 2 and x >= 1 and x <= 2) or (x == 4 and y == 4):
                flat.append(200.0)
            else:
                flat.append(10.0)
    return flat^


def test_frame_diff_masks_and_boxes() raises:
    var clip = _motion_clip3x5x5()
    var mask01 = frame_diff_mask_flat(clip, 5, 5, 1, 0, 1, 50.0)
    _assert_eq_int(_count_foreground(mask01, 128.0), 4, "0→1 motion mask area")
    _assert_true(mask01[1 * 5 + 1] >= 128.0, "block motion pixel is foreground")
    _assert_true(mask01[0] < 128.0, "static pixel stays background")

    var boxes01 = motion_boxes_between_frames(clip, 5, 5, 1, 0, 1, 50.0, 4)
    _assert_eq_int(len(boxes01), 5, "one 0→1 motion box")
    _assert_eq_int(boxes01[0], 1, "0→1 x0")
    _assert_eq_int(boxes01[1], 1, "0→1 y0")
    _assert_eq_int(boxes01[2], 2, "0→1 x1")
    _assert_eq_int(boxes01[3], 2, "0→1 y1")
    _assert_eq_int(boxes01[4], 4, "0→1 area")

    var box12 = largest_motion_box_between_frames(clip, 5, 5, 1, 1, 2, 50.0)
    _assert_eq_int(box12[0], 4, "1→2 x0")
    _assert_eq_int(box12[1], 4, "1→2 y0")
    _assert_eq_int(box12[2], 4, "1→2 x1")
    _assert_eq_int(box12[3], 4, "1→2 y1")
    _assert_eq_int(box12[4], 1, "1→2 area")
    print("✅ frame diff masks / motion boxes")


def test_temporal_motion_summaries() raises:
    var clip = _motion_clip3x5x5()
    var series = temporal_motion_area_series(clip, 5, 5, 1, 50.0)
    _assert_eq_int(len(series), 2, "two transition ratios")
    _assert_close(series[0], 4.0 / 25.0, 1e-9, "0→1 motion ratio")
    _assert_close(series[1], 1.0 / 25.0, 1e-9, "1→2 motion ratio")

    var peak = peak_motion_box_flat(clip, 5, 5, 1, 50.0)
    _assert_eq_int(peak[0], 1, "peak x0")
    _assert_eq_int(peak[1], 1, "peak y0")
    _assert_eq_int(peak[2], 2, "peak x1")
    _assert_eq_int(peak[3], 2, "peak y1")
    _assert_eq_int(peak[4], 4, "peak area")

    var union_box = temporal_union_motion_box_flat(clip, 5, 5, 1, 50.0)
    _assert_eq_int(union_box[0], 1, "union x0")
    _assert_eq_int(union_box[1], 1, "union y0")
    _assert_eq_int(union_box[2], 4, "union x1")
    _assert_eq_int(union_box[3], 4, "union y1")
    _assert_eq_int(union_box[4], 5, "union area")

    _assert_close(
        motion_coverage_ratio_flat(clip, 5, 5, 1, 50.0),
        5.0 / 25.0,
        1e-9,
        "motion coverage ratio",
    )
    print("✅ temporal motion summaries")


def main() raises:
    print("━━━ video_regions test suite ━━━")
    test_frame_diff_masks_and_boxes()
    test_temporal_motion_summaries()
    print("━━━ All video_regions tests passed ━━━")
