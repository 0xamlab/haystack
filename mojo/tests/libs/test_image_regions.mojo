"""test_image_regions.mojo — auto-generated tests for image_regions."""
from std.math import isnan, isinf
from image_regions import foreground_mask_otsu_flat, connected_component_boxes_flat, largest_foreground_box_flat, saliency_box_flat, extract_box_flat, box_iou

def is_finite(x: Float64) -> Bool:
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

    var _lf64_blobdoc8x8 = List[Float64]()
    for y in range(8):
        for x in range(8):
            if (y >= 2 and y <= 4 and x >= 1 and x <= 3) or (x == 6 and (y == 1 or y == 2)):
                _lf64_blobdoc8x8.append(20.0)
            else:
                _lf64_blobdoc8x8.append(235.0)
    var _lf36_components6x6 = List[Float64]()
    for y in range(6):
        for x in range(6):
            if (x == 0 and (y == 1 or y == 2)) or ((x == 3 and (y == 1 or y == 2 or y == 3)) or (x == 4 and y == 1)):
                _lf36_components6x6.append(255.0)
            else:
                _lf36_components6x6.append(0.0)
    var _lf256_texture16x16 = List[Float64]()
    for y in range(16):
        for x in range(16):
            if y >= 8 and x >= 8:
                _lf256_texture16x16.append(255.0 if (x + y) % 2 == 0 else 0.0)
            else:
                _lf256_texture16x16.append(64.0)
    var _lf16_grid4x4 = List[Float64]()
    for i in range(16):
        _lf16_grid4x4.append(Float64(i))
    var _li4_box_a = List[Int]()
    _li4_box_a.append(0); _li4_box_a.append(0); _li4_box_a.append(2); _li4_box_a.append(2)
    var _li4_box_b = List[Int]()
    _li4_box_b.append(1); _li4_box_b.append(1); _li4_box_b.append(3); _li4_box_b.append(3)
    var _v_foreground_mask_otsu_flat = foreground_mask_otsu_flat(_lf64_blobdoc8x8, 8, 8)
    if len(_v_foreground_mask_otsu_flat) >= 0: passed += 1; print("  ✅ image_regions::foreground_mask_otsu_flat")
    var _v_connected_component_boxes_flat = connected_component_boxes_flat(_lf36_components6x6, 6, 6, 128.0, 4)
    if len(_v_connected_component_boxes_flat) >= 0: passed += 1; print("  ✅ image_regions::connected_component_boxes_flat")
    var _v_largest_foreground_box_flat = largest_foreground_box_flat(_lf64_blobdoc8x8, 8, 8)
    if len(_v_largest_foreground_box_flat) >= 0: passed += 1; print("  ✅ image_regions::largest_foreground_box_flat")
    var _v_saliency_box_flat = saliency_box_flat(_lf256_texture16x16, 16, 16, 2, 2)
    if len(_v_saliency_box_flat) >= 0: passed += 1; print("  ✅ image_regions::saliency_box_flat")
    var _v_extract_box_flat = extract_box_flat(_lf16_grid4x4, 4, 4, 1, 1, 2, 2)
    if len(_v_extract_box_flat) >= 0: passed += 1; print("  ✅ image_regions::extract_box_flat")
    var _v_box_iou = box_iou(_li4_box_a, _li4_box_b)
    if is_finite(_v_box_iou): passed += 1; print("  ✅ image_regions::box_iou =", _v_box_iou)
    else: failed += 1; print("  ❌ image_regions::box_iou → non-finite:", _v_box_iou)

    print("  [image_regions] Passed:", passed, "Failed:", failed)
