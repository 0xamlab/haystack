"""
test_image_quality.mojo — Tests for the pure-Mojo image_quality library.

Validates:
  - blur_score: a sharp checkerboard scores far higher than a smooth gradient
  - brightness_mean / contrast_std on a constant field
  - is_near_blank / uniformity on a constant field
  - shannon_entropy: 0 for constant, ~1 bit for a two-value image
  - is_over_or_under_exposed bounds
  - quality_score stays in [0, 1]
  - flat entry points match the grid path

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_image_quality.mojo
"""
from image_quality import (
    blur_score,
    is_blurry,
    brightness_mean,
    contrast_std,
    shannon_entropy,
    is_near_blank,
    uniformity,
    noise_estimate,
    is_over_or_under_exposed,
    quality_score,
    blur_score_flat,
    brightness_flat,
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


fn _constant(n: Int, value: Float64) -> List[List[Float64]]:
    var g = List[List[Float64]]()
    for _ in range(n):
        var row = List[Float64]()
        for _ in range(n):
            row.append(value)
        g.append(row^)
    return g^


fn _checker(n: Int) -> List[List[Float64]]:
    """Alternating 0/255 cells → maximal high-frequency content."""
    var g = List[List[Float64]]()
    for r in range(n):
        var row = List[Float64]()
        for c in range(n):
            if (r + c) % 2 == 0:
                row.append(0.0)
            else:
                row.append(255.0)
        g.append(row^)
    return g^


fn _gradient(n: Int) -> List[List[Float64]]:
    """Linear ramp → Laplacian ≈ 0 in the interior (a 'smooth/blurry' image)."""
    var g = List[List[Float64]]()
    for r in range(n):
        var row = List[Float64]()
        for c in range(n):
            row.append(Float64(r + c) * 2.0)
        g.append(row^)
    return g^


fn _two_value(n: Int) -> List[List[Float64]]:
    """Top half 0, bottom half 255 → two equiprobable intensities → entropy 1 bit."""
    var g = List[List[Float64]]()
    for r in range(n):
        var row = List[Float64]()
        for _ in range(n):
            if r < n // 2:
                row.append(0.0)
            else:
                row.append(255.0)
        g.append(row^)
    return g^


def test_blur_score() raises:
    var sharp = _checker(16)
    var smooth = _gradient(16)
    var bs_sharp = blur_score(sharp)
    var bs_smooth = blur_score(smooth)
    _assert_true(bs_sharp > bs_smooth, "checker sharper than gradient")
    _assert_true(bs_sharp > 1000.0, "checker blur_score large")
    _assert_true(is_blurry(smooth, 100.0), "gradient is blurry under threshold 100")
    _assert_true(not is_blurry(sharp, 100.0), "checker is not blurry")
    print("✅ blur_score sharp vs smooth")


def test_brightness_contrast() raises:
    var flat = _constant(10, 100.0)
    _assert_close(brightness_mean(flat), 100.0, 1e-9, "brightness of constant 100")
    _assert_close(contrast_std(flat), 0.0, 1e-9, "contrast_std of constant == 0")
    _assert_true(is_near_blank(flat, 1.0), "constant is near-blank")
    _assert_close(uniformity(flat), 1.0, 1e-9, "uniformity of constant == 1")
    print("✅ brightness / contrast / blank / uniformity")


def test_entropy() raises:
    var flat = _constant(16, 50.0)
    _assert_close(shannon_entropy(flat), 0.0, 1e-9, "entropy of constant == 0")
    var tv = _two_value(16)
    _assert_close(shannon_entropy(tv), 1.0, 1e-6, "entropy of two-value == 1 bit")
    print("✅ shannon_entropy")


def test_exposure_and_noise() raises:
    _assert_true(is_over_or_under_exposed(_constant(8, 10.0), 30.0, 220.0), "dark is under-exposed")
    _assert_true(is_over_or_under_exposed(_constant(8, 250.0), 30.0, 220.0), "bright is over-exposed")
    _assert_true(not is_over_or_under_exposed(_constant(8, 128.0), 30.0, 220.0), "mid is fine")
    _assert_close(noise_estimate(_constant(8, 128.0)), 0.0, 1e-9, "noise of constant == 0")
    print("✅ exposure bounds / noise_estimate")


def test_quality_score_range() raises:
    var q_checker = quality_score(_checker(16))
    var q_flat = quality_score(_constant(16, 0.0))
    _assert_true(q_checker >= 0.0 and q_checker <= 1.0, "quality in [0,1] (checker)")
    _assert_true(q_flat >= 0.0 and q_flat <= 1.0, "quality in [0,1] (blank)")
    _assert_true(q_checker > q_flat, "textured mid-tone image scores above a black blank")
    print("✅ quality_score range + ordering")


def test_flat_matches_grid() raises:
    var img = _checker(12)
    var flat = List[Float64]()
    for r in range(12):
        for c in range(12):
            flat.append(img[r][c])
    _assert_close(blur_score_flat(flat, 12, 12), blur_score(img), 1e-6, "blur_score_flat matches")
    _assert_close(brightness_flat(flat, 12, 12), brightness_mean(img), 1e-9, "brightness_flat matches")
    print("✅ flat entry points match grid")


def main() raises:
    print("━━━ image_quality test suite ━━━")
    test_blur_score()
    test_brightness_contrast()
    test_entropy()
    test_exposure_and_noise()
    test_quality_score_range()
    test_flat_matches_grid()
    print("━━━ All image_quality tests passed ━━━")
