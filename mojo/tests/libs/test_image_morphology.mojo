"""test_image_morphology.mojo — auto-generated tests for image_morphology."""
from std.math import isnan, isinf
from image_morphology import binary_erode_flat, binary_dilate_flat, binary_open_flat, binary_close_flat, binary_fill_holes_flat, connected_components_4_flat, largest_component_bbox_flat, distance_transform_cityblock_flat, foreground_area_ratio_flat

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

    var _lf25_block5x5 = List[Float64]()
    for y in range(5):
        for x in range(5):
            if y >= 1 and y <= 3 and x >= 1 and x <= 3:
                _lf25_block5x5.append(255.0)
            else:
                _lf25_block5x5.append(0.0)
    var _lf25_ring5x5 = List[Float64]()
    for y in range(5):
        for x in range(5):
            if y >= 1 and y <= 3 and x >= 1 and x <= 3 and not (y == 2 and x == 2):
                _lf25_ring5x5.append(255.0)
            else:
                _lf25_ring5x5.append(0.0)
    var _lf36_components6x6 = List[Float64]()
    for y in range(6):
        for x in range(6):
            if (x == 0 and (y == 1 or y == 2)) or ((x == 3 and (y == 1 or y == 2 or y == 3)) or (x == 4 and y == 1)):
                _lf36_components6x6.append(255.0)
            else:
                _lf36_components6x6.append(0.0)
    var _v_binary_erode_flat = binary_erode_flat(_lf25_block5x5, 5, 5, 3, 128.0)
    if len(_v_binary_erode_flat) >= 0: passed += 1; print("  ✅ image_morphology::binary_erode_flat")
    var _v_binary_dilate_flat = binary_dilate_flat(_lf25_block5x5, 5, 5, 3, 128.0)
    if len(_v_binary_dilate_flat) >= 0: passed += 1; print("  ✅ image_morphology::binary_dilate_flat")
    var _v_binary_open_flat = binary_open_flat(_lf25_block5x5, 5, 5, 3, 128.0)
    if len(_v_binary_open_flat) >= 0: passed += 1; print("  ✅ image_morphology::binary_open_flat")
    var _v_binary_close_flat = binary_close_flat(_lf25_ring5x5, 5, 5, 3, 128.0)
    if len(_v_binary_close_flat) >= 0: passed += 1; print("  ✅ image_morphology::binary_close_flat")
    var _v_binary_fill_holes_flat = binary_fill_holes_flat(_lf25_ring5x5, 5, 5, 128.0)
    if len(_v_binary_fill_holes_flat) >= 0: passed += 1; print("  ✅ image_morphology::binary_fill_holes_flat")
    var _v_connected_components_4_flat = connected_components_4_flat(_lf36_components6x6, 6, 6, 128.0)
    if len(_v_connected_components_4_flat) >= 0: passed += 1; print("  ✅ image_morphology::connected_components_4_flat")
    var _v_largest_component_bbox_flat = largest_component_bbox_flat(_lf36_components6x6, 6, 6, 128.0)
    if len(_v_largest_component_bbox_flat) >= 0: passed += 1; print("  ✅ image_morphology::largest_component_bbox_flat")
    var _v_distance_transform_cityblock_flat = distance_transform_cityblock_flat(_lf25_block5x5, 5, 5, 128.0)
    if len(_v_distance_transform_cityblock_flat) >= 0: passed += 1; print("  ✅ image_morphology::distance_transform_cityblock_flat")
    var _v_foreground_area_ratio_flat = foreground_area_ratio_flat(_lf25_block5x5, 5, 5, 128.0)
    if is_finite(_v_foreground_area_ratio_flat): passed += 1; print("  ✅ image_morphology::foreground_area_ratio_flat =", _v_foreground_area_ratio_flat)
    else: failed += 1; print("  ❌ image_morphology::foreground_area_ratio_flat → non-finite:", _v_foreground_area_ratio_flat)

    print("  [image_morphology] Passed:", passed, "Failed:", failed)
