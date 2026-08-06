"""
test_image_resize.mojo — Tests for the pure-Mojo image_resize library.

Validates:
  - reshape_to_grid / flatten_grid round-trip
  - box_downscale area averaging and dimensions
  - bilinear_downscale dimensions and exactness on a constant image
  - integral_image + box_sum region sums
  - downscale_flat end-to-end flat→flat

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_image_resize.mojo
"""
from image_resize import (
    reshape_to_grid,
    flatten_grid,
    box_downscale,
    bilinear_downscale,
    resize_for_hash,
    resize_for_dhash,
    integral_image,
    box_sum,
    downscale_flat,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _assert_true(cond: Bool, label: String) raises:
    if not cond:
        print("❌ FAIL: " + label)
        raise Error("assertion failed: " + label)


def _assert_close(got: Float64, expected: Float64, label: String) raises:
    var d = got - expected
    if d < 0.0:
        d = -d
    if d > 1e-9:
        print("❌ FAIL: " + label)
        print("   expected: " + String(expected))
        print("   got:      " + String(got))
        raise Error("assertion failed: " + label)


def _ramp(width: Int, height: Int) -> List[List[Float64]]:
    """Grid where pixel(r,c) = r*width + c."""
    var g = List[List[Float64]]()
    for r in range(height):
        var row = List[Float64]()
        for c in range(width):
            row.append(Float64(r * width + c))
        g.append(row^)
    return g^


def _constant(width: Int, height: Int, value: Float64) -> List[List[Float64]]:
    var g = List[List[Float64]]()
    for _ in range(height):
        var row = List[Float64]()
        for _ in range(width):
            row.append(value)
        g.append(row^)
    return g^


# ── Tests ───────────────────────────────────────────────────────────────────

def test_reshape_roundtrip() raises:
    var flat = List[Float64]()
    for i in range(6):
        flat.append(Float64(i))
    var g = reshape_to_grid(flat, 3, 2)
    _assert_true(len(g) == 2, "reshape rows == 2")
    _assert_true(len(g[0]) == 3, "reshape cols == 3")
    _assert_close(g[1][2], 5.0, "reshape g[1][2] == 5")
    var back = flatten_grid(g)
    _assert_true(len(back) == 6, "flatten len == 6")
    _assert_close(back[4], 4.0, "flatten back[4] == 4")
    print("✅ reshape/flatten round-trip")


def test_box_downscale() raises:
    # 4x4 → 2x2: each output cell averages a 2x2 block of the ramp.
    var g = _ramp(4, 4)
    var small = box_downscale(g, 2, 2)
    _assert_true(len(small) == 2 and len(small[0]) == 2, "box dims 2x2")
    # Top-left block = mean(0,1,4,5) = 2.5
    _assert_close(small[0][0], 2.5, "box top-left mean == 2.5")
    # Bottom-right block = mean(10,11,14,15) = 12.5
    _assert_close(small[1][1], 12.5, "box bottom-right mean == 12.5")
    print("✅ box_downscale averaging")


def test_bilinear_constant() raises:
    # Downscaling a constant image must preserve the constant exactly.
    var g = _constant(8, 8, 137.0)
    var small = bilinear_downscale(g, 3, 3)
    _assert_true(len(small) == 3 and len(small[0]) == 3, "bilinear dims 3x3")
    _assert_close(small[1][1], 137.0, "bilinear preserves constant")
    print("✅ bilinear_downscale on constant")


def test_resize_helpers() raises:
    var g = _ramp(16, 16)
    var h = resize_for_hash(g, 8)
    _assert_true(len(h) == 8 and len(h[0]) == 8, "resize_for_hash 8x8")
    var d = resize_for_dhash(g, 8, 8)
    _assert_true(len(d) == 8 and len(d[0]) == 9, "resize_for_dhash 9 cols x 8 rows")
    print("✅ resize_for_hash / resize_for_dhash dims")


def test_integral_and_box_sum() raises:
    var g = _ramp(3, 3)  # values 0..8
    var ii = integral_image(g)
    _assert_true(len(ii) == 4 and len(ii[0]) == 4, "integral dims (H+1)x(W+1)")
    # Sum of whole 3x3 = 0+1+...+8 = 36
    _assert_close(box_sum(ii, 0, 0, 2, 2), 36.0, "box_sum full == 36")
    # Single cell (1,1) = 4
    _assert_close(box_sum(ii, 1, 1, 1, 1), 4.0, "box_sum single == 4")
    # Bottom-right 2x2 block: 4+5+7+8 = 24
    _assert_close(box_sum(ii, 1, 1, 2, 2), 24.0, "box_sum 2x2 == 24")
    print("✅ integral_image / box_sum")


def test_downscale_flat() raises:
    var flat = List[Float64]()
    for i in range(16):
        flat.append(Float64(i))  # 4x4 ramp, row-major
    var out = downscale_flat(flat, 4, 4, 2, 2)
    _assert_true(len(out) == 4, "downscale_flat len == 4")
    _assert_close(out[0], 2.5, "downscale_flat[0] == 2.5")
    _assert_close(out[3], 12.5, "downscale_flat[3] == 12.5")
    print("✅ downscale_flat end-to-end")


def main() raises:
    print("━━━ image_resize test suite ━━━")
    test_reshape_roundtrip()
    test_box_downscale()
    test_bilinear_constant()
    test_resize_helpers()
    test_integral_and_box_sum()
    test_downscale_flat()
    print("━━━ All image_resize tests passed ━━━")
