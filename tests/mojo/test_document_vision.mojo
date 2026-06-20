"""
test_document_vision.mojo — Tests for the pure-Mojo document_vision library.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_document_vision.mojo
"""
from document_vision import (
    otsu_threshold_flat,
    binarize_otsu_flat,
    adaptive_mean_binarize_flat,
    horizontal_projection,
    vertical_projection,
    mask_content_bbox_flat,
    skew_angle_estimate_flat,
    horizontal_text_score_flat,
    document_scan_quality_flat,
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
    for index in range(len(mask)):
        if mask[index] >= threshold:
            count += 1
    return count


fn _doc8() -> List[Float64]:
    var flat = List[Float64]()
    for y in range(8):
        for x in range(8):
            if y == 2 and x >= 1 and x <= 6:
                flat.append(20.0)
            elif y == 5 and x >= 2 and x <= 5:
                flat.append(20.0)
            else:
                flat.append(240.0)
    return flat^


fn _blank8() -> List[Float64]:
    var flat = List[Float64]()
    for _ in range(64):
        flat.append(240.0)
    return flat^


fn _adaptive_doc6() -> List[Float64]:
    var flat = List[Float64]()
    for y in range(6):
        for x in range(6):
            if y == 2 and x >= 2 and x <= 3:
                flat.append(40.0)
            else:
                flat.append(220.0 if x < 3 else 245.0)
    return flat^


fn _skew_mask6() -> List[Float64]:
    var flat = List[Float64]()
    for y in range(6):
        for x in range(6):
            if y >= 1 and y <= 4 and x == y:
                flat.append(255.0)
            else:
                flat.append(0.0)
    return flat^


def test_thresholds_and_masks() raises:
    var doc = _doc8()
    var threshold = otsu_threshold_flat(doc, 8, 8)
    _assert_true(threshold >= 20.0 and threshold < 240.0, "otsu threshold separates dark ink from paper")

    var mask = binarize_otsu_flat(doc, 8, 8)
    _assert_eq_int(_count_foreground(mask, 128.0), 10, "otsu mask captures ten ink pixels")
    _assert_true(mask[2 * 8 + 1] >= 128.0, "ink pixel becomes foreground")
    _assert_true(mask[0] < 128.0, "paper pixel stays background")

    var adaptive = adaptive_mean_binarize_flat(_adaptive_doc6(), 6, 6, 1, 20.0)
    _assert_true(adaptive[2 * 6 + 2] >= 128.0, "adaptive binarization keeps dark local ink")
    _assert_true(adaptive[0] < 128.0, "adaptive binarization rejects bright paper")
    print("✅ Otsu / adaptive binarization")


def test_projections_bbox_and_skew() raises:
    var mask = binarize_otsu_flat(_doc8(), 8, 8)
    var hp = horizontal_projection(mask, 8, 8, 128.0)
    var vp = vertical_projection(mask, 8, 8, 128.0)
    _assert_close(hp[2], 6.0, 1e-9, "row 2 projection")
    _assert_close(hp[5], 4.0, 1e-9, "row 5 projection")
    _assert_close(vp[1], 1.0, 1e-9, "column 1 projection")
    _assert_close(vp[2], 2.0, 1e-9, "column 2 projection")

    var bbox = mask_content_bbox_flat(mask, 8, 8, 128.0)
    _assert_eq_int(bbox[0], 1, "bbox x0")
    _assert_eq_int(bbox[1], 2, "bbox y0")
    _assert_eq_int(bbox[2], 6, "bbox x1")
    _assert_eq_int(bbox[3], 5, "bbox y1")
    _assert_eq_int(bbox[4], 10, "bbox area")

    var skew = skew_angle_estimate_flat(_skew_mask6(), 6, 6, 128.0)
    _assert_true(skew > 40.0 and skew < 50.0, "skew estimate tracks diagonal slope")
    print("✅ projections / bbox / skew")


def test_text_layout_and_quality() raises:
    var doc = _doc8()
    var mask = binarize_otsu_flat(doc, 8, 8)
    _assert_true(
        horizontal_text_score_flat(mask, 8, 8, 128.0) > 0.55,
        "horizontal text score prefers row-structured ink",
    )

    var doc_quality = document_scan_quality_flat(doc, 8, 8)
    var blank_quality = document_scan_quality_flat(_blank8(), 8, 8)
    _assert_true(doc_quality > 0.0, "document quality is positive for actual content")
    _assert_true(doc_quality > blank_quality, "document outranks blank scan")
    print("✅ text-layout score / scan quality")


def main() raises:
    print("━━━ document_vision test suite ━━━")
    test_thresholds_and_masks()
    test_projections_bbox_and_skew()
    test_text_layout_and_quality()
    print("━━━ All document_vision tests passed ━━━")
