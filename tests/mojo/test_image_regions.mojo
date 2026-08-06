"""
test_image_regions.mojo — Tests for the pure-Mojo image_regions library.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_image_regions.mojo
"""
from image_regions import (
    foreground_mask_otsu_flat,
    connected_component_boxes_flat,
    largest_foreground_box_flat,
    saliency_box_flat,
    extract_box_flat,
    box_iou,
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


def _count_foreground(mask: List[Float64], threshold: Float64) -> Int:
    var count = 0
    for index in range(len(mask)):
        if mask[index] >= threshold:
            count += 1
    return count


def _two_components_mask6() -> List[Float64]:
    var flat = List[Float64]()
    for y in range(6):
        for x in range(6):
            var on_left = x == 0 and (y == 1 or y == 2)
            var on_right = (x == 3 and (y == 1 or y == 2 or y == 3)) or (x == 4 and y == 1)
            flat.append(255.0 if on_left or on_right else 0.0)
    return flat^


def _blob_doc8() -> List[Float64]:
    var flat = List[Float64]()
    for y in range(8):
        for x in range(8):
            var big = y >= 2 and y <= 4 and x >= 1 and x <= 3
            var small = x == 6 and (y == 1 or y == 2)
            flat.append(20.0 if big or small else 235.0)
    return flat^


def _bottom_right_texture16() -> List[Float64]:
    var flat = List[Float64]()
    for y in range(16):
        for x in range(16):
            if y >= 8 and x >= 8:
                flat.append(255.0 if (x + y) % 2 == 0 else 0.0)
            else:
                flat.append(64.0)
    return flat^


def _grid4() -> List[Float64]:
    var flat = List[Float64]()
    for index in range(16):
        flat.append(Float64(index))
    return flat^


def test_masks_and_component_boxes() raises:
    var mask = foreground_mask_otsu_flat(_blob_doc8(), 8, 8)
    _assert_eq_int(_count_foreground(mask, 128.0), 11, "Otsu mask captures both blobs")

    var boxes = connected_component_boxes_flat(_two_components_mask6(), 6, 6, 128.0, 4)
    _assert_eq_int(len(boxes), 10, "two boxes × five integers")
    _assert_eq_int(boxes[0], 3, "largest box x0")
    _assert_eq_int(boxes[1], 1, "largest box y0")
    _assert_eq_int(boxes[2], 4, "largest box x1")
    _assert_eq_int(boxes[3], 3, "largest box y1")
    _assert_eq_int(boxes[4], 4, "largest box area")
    _assert_eq_int(boxes[5], 0, "second box x0")
    _assert_eq_int(boxes[9], 2, "second box area")
    print("✅ foreground mask / component boxes")


def test_largest_box_and_saliency() raises:
    var largest = largest_foreground_box_flat(_blob_doc8(), 8, 8)
    _assert_eq_int(largest[0], 1, "largest foreground x0")
    _assert_eq_int(largest[1], 2, "largest foreground y0")
    _assert_eq_int(largest[2], 3, "largest foreground x1")
    _assert_eq_int(largest[3], 4, "largest foreground y1")
    _assert_eq_int(largest[4], 9, "largest foreground area")

    var saliency = saliency_box_flat(_bottom_right_texture16(), 16, 16, 2, 2)
    _assert_eq_int(saliency[0], 8, "saliency box x0")
    _assert_eq_int(saliency[1], 8, "saliency box y0")
    _assert_eq_int(saliency[2], 15, "saliency box x1")
    _assert_eq_int(saliency[3], 15, "saliency box y1")
    _assert_eq_int(saliency[4], 64, "saliency box area")
    print("✅ largest foreground box / saliency box")


def test_extract_and_iou() raises:
    var crop = extract_box_flat(_grid4(), 4, 4, 1, 1, 2, 2)
    _assert_eq_int(len(crop), 4, "2x2 crop length")
    _assert_close(crop[0], 5.0, 1e-9, "crop first value")
    _assert_close(crop[1], 6.0, 1e-9, "crop second value")
    _assert_close(crop[2], 9.0, 1e-9, "crop third value")
    _assert_close(crop[3], 10.0, 1e-9, "crop fourth value")

    var box_a = List[Int]()
    box_a.append(0); box_a.append(0); box_a.append(2); box_a.append(2)
    var box_b = List[Int]()
    box_b.append(1); box_b.append(1); box_b.append(3); box_b.append(3)
    _assert_close(box_iou(box_a, box_b), 4.0 / 14.0, 1e-9, "box IoU")
    print("✅ crop extraction / box IoU")


def main() raises:
    print("━━━ image_regions test suite ━━━")
    test_masks_and_component_boxes()
    test_largest_box_and_saliency()
    test_extract_and_iou()
    print("━━━ All image_regions tests passed ━━━")
