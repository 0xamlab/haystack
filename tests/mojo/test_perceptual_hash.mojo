"""
test_perceptual_hash.mojo — Tests for the pure-Mojo perceptual_hash library.

Validates:
  - hamming_distance: self-distance 0, counts bit 63, symmetric
  - ahash/dhash/phash are stable (identical images → distance 0)
  - pHash brightness invariance: a constant offset moves only the DC coefficient,
    so a brightened copy of a broadband image stays within a few bits
  - distinct content (different seeds) and inverted images → large distance
  - is_duplicate threshold behaviour
  - flat entry point matches the grid path

The test image is a deterministic broadband value-noise field: its spectrum is
spread across all 64 low-frequency DCT coefficients, so none sit at the AC
median where floating-point noise would flip bits (a smooth gradient would).

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_perceptual_hash.mojo
"""
from perceptual_hash import (
    ahash,
    dhash,
    phash,
    hamming_distance,
    is_duplicate,
    ahash_flat,
)


def _assert_true(cond: Bool, label: String) raises:
    if not cond:
        print("❌ FAIL: " + label)
        raise Error("assertion failed: " + label)


def _assert_eq_int(got: Int, expected: Int, label: String) raises:
    if got != expected:
        print("❌ FAIL: " + label)
        print("   expected: " + String(expected))
        print("   got:      " + String(got))
        raise Error("assertion failed: " + label)


def _noise(width: Int, height: Int, m1: UInt64, m2: UInt64) -> List[List[Float64]]:
    """Deterministic broadband value-noise in [20, 219] (so +15 stays unclamped)."""
    var g = List[List[Float64]]()
    for r in range(height):
        var row = List[Float64]()
        for c in range(width):
            var hh = (
                UInt64(r) * m1
                + UInt64(c) * m2
                + UInt64(r * c) * UInt64(2246822519)
            )
            hh = hh ^ (hh >> UInt64(15))
            hh = hh * UInt64(2654435761)
            hh = hh ^ (hh >> UInt64(13))
            row.append(Float64(Int(hh % UInt64(200))) + 20.0)
        g.append(row^)
    return g^


def _brighten(image: List[List[Float64]], delta: Float64) -> List[List[Float64]]:
    var g = List[List[Float64]]()
    for r in range(len(image)):
        var row = List[Float64]()
        for c in range(len(image[r])):
            row.append(image[r][c] + delta)
        g.append(row^)
    return g^


def _invert(image: List[List[Float64]]) -> List[List[Float64]]:
    var g = List[List[Float64]]()
    for r in range(len(image)):
        var row = List[Float64]()
        for c in range(len(image[r])):
            row.append(255.0 - image[r][c])
        g.append(row^)
    return g^


def test_hamming_basics() raises:
    _assert_eq_int(hamming_distance(UInt64(0), UInt64(0)), 0, "hamming(0,0)==0")
    var allset = ~UInt64(0)
    _assert_eq_int(hamming_distance(allset, UInt64(0)), 64, "hamming(all,0)==64")
    # bit 63 must be counted (regression guard vs Int popcount sign loss)
    var top = UInt64(1) << UInt64(63)
    _assert_eq_int(hamming_distance(top, UInt64(0)), 1, "hamming(bit63,0)==1")
    _assert_eq_int(
        hamming_distance(UInt64(12345), UInt64(98765)),
        hamming_distance(UInt64(98765), UInt64(12345)),
        "hamming symmetric",
    )
    print("✅ hamming_distance basics (incl. bit-63)")


def test_identical_images() raises:
    var img = _noise(40, 40, UInt64(73856093), UInt64(19349663))
    _assert_eq_int(hamming_distance(ahash(img), ahash(img)), 0, "ahash identical")
    _assert_eq_int(hamming_distance(dhash(img), dhash(img)), 0, "dhash identical")
    _assert_eq_int(hamming_distance(phash(img), phash(img)), 0, "phash identical")
    print("✅ identical images → distance 0")


def test_brightness_invariance() raises:
    var img = _noise(48, 48, UInt64(73856093), UInt64(19349663))
    var brighter = _brighten(img, 15.0)  # pure +15, no clamping → only DC moves
    var d = hamming_distance(phash(img), phash(brighter))
    _assert_true(d <= 6, "phash brightness-invariant within 6 bits (got " + String(d) + ")")
    _assert_true(is_duplicate(phash(img), phash(brighter), 6), "is_duplicate true for brighter copy")
    print("✅ pHash brightness invariance")


def test_distinct_images() raises:
    var a = _noise(64, 64, UInt64(73856093), UInt64(19349663))
    var b = _noise(64, 64, UInt64(2971215073), UInt64(433494437))  # different seeds
    var d = hamming_distance(phash(a), phash(b))
    _assert_true(d >= 18, "phash distinct content far apart (got " + String(d) + ")")
    _assert_true(not is_duplicate(phash(a), phash(b), 8), "is_duplicate false for distinct content")
    var inv = _invert(a)
    _assert_true(hamming_distance(ahash(a), ahash(inv)) >= 24, "ahash inverted far apart")
    print("✅ distinct images → large distance")


def test_flat_matches_grid() raises:
    var img = _noise(16, 16, UInt64(73856093), UInt64(19349663))
    var flat = List[Float64]()
    for r in range(16):
        for c in range(16):
            flat.append(img[r][c])
    _assert_eq_int(
        hamming_distance(ahash(img), ahash_flat(flat, 16, 16)),
        0,
        "ahash_flat matches ahash",
    )
    print("✅ flat entry point matches grid")


def main() raises:
    print("━━━ perceptual_hash test suite ━━━")
    test_hamming_basics()
    test_identical_images()
    test_brightness_invariance()
    test_distinct_images()
    test_flat_matches_grid()
    print("━━━ All perceptual_hash tests passed ━━━")
