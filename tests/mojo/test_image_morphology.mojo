"""
test_image_morphology.mojo — Tests for the pure-Mojo image_morphology library.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_image_morphology.mojo
"""
from image_morphology import (
    binary_erode_flat,
    binary_dilate_flat,
    binary_open_flat,
    binary_close_flat,
    binary_fill_holes_flat,
    connected_components_4_flat,
    largest_component_bbox_flat,
    distance_transform_cityblock_flat,
    foreground_area_ratio_flat,
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


fn _flatten(grid: List[List[Float64]]) -> List[Float64]:
    var out = List[Float64]()
    for y in range(len(grid)):
        for x in range(len(grid[y])):
            out.append(grid[y][x])
    return out^


fn _count_foreground(flat: List[Float64], threshold: Float64) -> Int:
    var count = 0
    for index in range(len(flat)):
        if flat[index] >= threshold:
            count += 1
    return count


fn _block5() -> List[Float64]:
    var grid = List[List[Float64]]()
    for y in range(5):
        var row = List[Float64]()
        for x in range(5):
            if y >= 1 and y <= 3 and x >= 1 and x <= 3:
                row.append(255.0)
            else:
                row.append(0.0)
        grid.append(row^)
    return _flatten(grid)


fn _single_pixel5() -> List[Float64]:
    var grid = List[List[Float64]]()
    for y in range(5):
        var row = List[Float64]()
        for x in range(5):
            row.append(255.0 if y == 2 and x == 2 else 0.0)
        grid.append(row^)
    return _flatten(grid)


fn _ring5() -> List[Float64]:
    var grid = List[List[Float64]]()
    for y in range(5):
        var row = List[Float64]()
        for x in range(5):
            if y >= 1 and y <= 3 and x >= 1 and x <= 3 and not (y == 2 and x == 2):
                row.append(255.0)
            else:
                row.append(0.0)
        grid.append(row^)
    return _flatten(grid)


fn _two_components6() -> List[Float64]:
    var grid = List[List[Float64]]()
    for y in range(6):
        var row = List[Float64]()
        for x in range(6):
            var on_left = x == 0 and (y == 1 or y == 2)
            var on_right = (x == 3 and (y == 1 or y == 2 or y == 3)) or (x == 4 and y == 1)
            row.append(255.0 if on_left or on_right else 0.0)
        grid.append(row^)
    return _flatten(grid)


def test_binary_morphology() raises:
    var block = _block5()
    var eroded = binary_erode_flat(block, 5, 5, 3, 128.0)
    var dilated = binary_dilate_flat(block, 5, 5, 3, 128.0)
    _assert_eq_int(_count_foreground(eroded, 128.0), 1, "3x3 block erodes to center pixel")
    _assert_true(eroded[2 * 5 + 2] >= 128.0, "center pixel survives erosion")
    _assert_eq_int(_count_foreground(dilated, 128.0), 25, "3x3 block dilates to full 5x5")

    var opened = binary_open_flat(_single_pixel5(), 5, 5, 3, 128.0)
    _assert_eq_int(_count_foreground(opened, 128.0), 0, "opening removes isolated noise")

    var closed = binary_close_flat(_ring5(), 5, 5, 3, 128.0)
    _assert_eq_int(_count_foreground(closed, 128.0), 9, "closing fills the 3x3 ring hole")
    _assert_true(closed[2 * 5 + 2] >= 128.0, "closing fills center hole")
    print("✅ erosion / dilation / open / close")


def test_fill_holes_components_and_bbox() raises:
    var filled = binary_fill_holes_flat(_ring5(), 5, 5, 128.0)
    _assert_eq_int(_count_foreground(filled, 128.0), 9, "fill_holes fills center hole")
    _assert_true(filled[2 * 5 + 2] >= 128.0, "fill_holes sets center foreground")

    var comps = _two_components6()
    var labels = connected_components_4_flat(comps, 6, 6, 128.0)
    _assert_eq_int(labels[1 * 6 + 0], 1, "left component gets label 1")
    _assert_eq_int(labels[1 * 6 + 3], 2, "right component gets label 2")
    _assert_eq_int(labels[3 * 6 + 3], 2, "right tail keeps label 2")

    var bbox = largest_component_bbox_flat(comps, 6, 6, 128.0)
    _assert_eq_int(len(bbox), 5, "largest bbox returns five values")
    _assert_eq_int(bbox[0], 3, "largest bbox x0")
    _assert_eq_int(bbox[1], 1, "largest bbox y0")
    _assert_eq_int(bbox[2], 4, "largest bbox x1")
    _assert_eq_int(bbox[3], 3, "largest bbox y1")
    _assert_eq_int(bbox[4], 4, "largest bbox area")
    print("✅ fill_holes / connected components / bbox")


def test_distance_transform_and_ratio() raises:
    var block = _block5()
    var dist = distance_transform_cityblock_flat(block, 5, 5, 128.0)
    _assert_eq_int(dist[0], 0, "background distance is 0")
    _assert_eq_int(dist[1 * 5 + 1], 1, "edge foreground distance is 1")
    _assert_eq_int(dist[2 * 5 + 2], 2, "center foreground distance is 2")
    _assert_close(
        foreground_area_ratio_flat(block, 5, 5, 128.0),
        9.0 / 25.0,
        1e-9,
        "foreground area ratio",
    )
    print("✅ distance transform / foreground ratio")


def main() raises:
    print("━━━ image_morphology test suite ━━━")
    test_binary_morphology()
    test_fill_holes_components_and_bbox()
    test_distance_transform_and_ratio()
    print("━━━ All image_morphology tests passed ━━━")
