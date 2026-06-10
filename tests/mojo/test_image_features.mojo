"""
test_image_features.mojo — Tests for the pure-Mojo image_features library.

Validates:
  - edge_density: high for a checkerboard, zero for a constant field
  - color_histogram normalizes to ~1 and lands in the expected bin
  - histogram_intersection / chi_square / correlation on identical vs disjoint
  - dominant_colors surfaces the solid colour with weight ≈ 1
  - saliency_grid + most_salient_cell point at the textured quadrant
  - flat entry points match the grid path

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_image_features.mojo
"""
from image_features import (
    sobel_magnitude,
    edge_density,
    color_histogram,
    histogram_intersection,
    histogram_chi_square,
    histogram_correlation,
    dominant_colors,
    saliency_grid,
    most_salient_cell,
    edge_density_flat,
    most_salient_cell_flat,
)


def _assert_true(cond: Bool, label: String) raises:
    if not cond:
        print("❌ FAIL: " + label)
        raise Error("assertion failed: " + label)


def _assert_close(got: Float64, expected: Float64, tol: Float64, label: String) raises:
    var d = got - expected
    if d < 0.0:
        d = -d
    if d > tol:
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


fn _stripes(n: Int) -> List[List[Float64]]:
    """Width-2 vertical stripes (0/255). Unlike a 1-px checker (which the
    symmetric Sobel kernel nulls out), every interior column borders a
    transition → strong, dense gradient response."""
    var g = List[List[Float64]]()
    for r in range(n):
        var row = List[Float64]()
        for c in range(n):
            row.append(255.0 if (c // 2) % 2 == 1 else 0.0)
        g.append(row^)
    return g^


fn _constant(n: Int, v: Float64) -> List[List[Float64]]:
    var g = List[List[Float64]]()
    for _ in range(n):
        var row = List[Float64]()
        for _ in range(n):
            row.append(v)
        g.append(row^)
    return g^


fn _bottom_right_texture(n: Int) -> List[List[Float64]]:
    """Flat (64) everywhere except a checker in the bottom-right quadrant."""
    var g = List[List[Float64]]()
    var half = n // 2
    for r in range(n):
        var row = List[Float64]()
        for c in range(n):
            if r >= half and c >= half:
                row.append(255.0 if (c // 2) % 2 == 1 else 0.0)
            else:
                row.append(64.0)
        g.append(row^)
    return g^


fn _solid_rgb(npx: Int, r: Float64, g: Float64, b: Float64) -> List[Float64]:
    var f = List[Float64]()
    for _ in range(npx):
        f.append(r)
        f.append(g)
        f.append(b)
    return f^


def test_edge_density() raises:
    _assert_true(edge_density(_stripes(16), 100.0) > 0.5, "stripe edge density high")
    _assert_close(edge_density(_constant(16, 100.0), 100.0), 0.0, 1e-9, "constant edge density 0")
    var mag = sobel_magnitude(_stripes(16))
    _assert_true(len(mag) == 14 and len(mag[0]) == 14, "sobel_magnitude valid dims 14x14")
    print("✅ edge_density / sobel_magnitude")


def test_color_histograms() raises:
    var red = color_histogram(_solid_rgb(64, 255.0, 0.0, 0.0), 8, 8, 2)
    var blue = color_histogram(_solid_rgb(64, 0.0, 0.0, 255.0), 8, 8, 2)
    _assert_true(len(red) == 8, "2³ = 8 bins")
    var ssum: Float64 = 0.0
    for i in range(len(red)):
        ssum += red[i]
    _assert_close(ssum, 1.0, 1e-9, "histogram normalized to 1")
    _assert_close(histogram_intersection(red, red), 1.0, 1e-9, "self-intersection == 1")
    _assert_close(histogram_intersection(red, blue), 0.0, 1e-9, "red∩blue == 0")
    _assert_close(histogram_chi_square(red, red), 0.0, 1e-9, "self chi-square == 0")
    _assert_true(histogram_chi_square(red, blue) > 0.0, "red vs blue chi-square > 0")
    _assert_close(histogram_correlation(red, red), 1.0, 1e-9, "self-correlation == 1")
    print("✅ color_histogram + comparison metrics")


def test_dominant_colors() raises:
    var dom = dominant_colors(_solid_rgb(64, 240.0, 20.0, 20.0), 8, 8, 2)
    _assert_true(len(dom) == 12, "3 colours × [r,g,b,weight]")
    # Top colour weight ≈ 1 and is reddish (r > g and r > b).
    _assert_close(dom[3], 1.0, 1e-9, "dominant weight ≈ 1")
    _assert_true(dom[0] > dom[1] and dom[0] > dom[2], "dominant colour is reddish")
    print("✅ dominant_colors")


def test_saliency() raises:
    var img = _bottom_right_texture(16)
    var sal = saliency_grid(img, 2, 2)
    _assert_true(len(sal) == 2 and len(sal[0]) == 2, "saliency grid 2x2")
    # Bottom-right cell (row 1, col 1) → flattened index 1*2+1 = 3.
    _assert_eq_int(most_salient_cell(sal), 3, "peak saliency in bottom-right cell")
    print("✅ saliency_grid / most_salient_cell")


def test_flat_matches_grid() raises:
    var img = _stripes(16)
    var flat = List[Float64]()
    for r in range(16):
        for c in range(16):
            flat.append(img[r][c])
    _assert_close(
        edge_density_flat(flat, 16, 16, 100.0),
        edge_density(img, 100.0),
        1e-9,
        "edge_density_flat matches",
    )
    var br = _bottom_right_texture(16)
    var brflat = List[Float64]()
    for r in range(16):
        for c in range(16):
            brflat.append(br[r][c])
    _assert_eq_int(
        most_salient_cell_flat(brflat, 16, 16, 2, 2),
        most_salient_cell(saliency_grid(br, 2, 2)),
        "most_salient_cell_flat matches",
    )
    print("✅ flat entry points match grid")


def main() raises:
    print("━━━ image_features test suite ━━━")
    test_edge_density()
    test_color_histograms()
    test_dominant_colors()
    test_saliency()
    test_flat_matches_grid()
    print("━━━ All image_features tests passed ━━━")
