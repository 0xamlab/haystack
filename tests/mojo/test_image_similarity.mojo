"""
test_image_similarity.mojo — Tests for the pure-Mojo image_similarity library.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_image_similarity.mojo
"""
from image_similarity import (
    mean_squared_error_flat,
    mean_abs_error_flat,
    psnr_flat,
    normalized_cross_correlation_flat,
    ssim_global_flat,
    diff_fraction_flat,
    crop_region_similarity_flat,
    duplicate_score_flat,
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


fn _pattern8() -> List[Float64]:
    var flat = List[Float64]()
    for y in range(8):
        for x in range(8):
            flat.append(Float64((y * 37 + x * 19 + y * x * 3) % 200) + 20.0)
    return flat^


fn _patch_brighten(flat: List[Float64]) -> List[Float64]:
    var out = List[Float64]()
    for index in range(len(flat)):
        out.append(flat[index])
    for y in range(2, 4):
        for x in range(2, 4):
            var index = y * 8 + x
            var value = out[index] + 40.0
            if value > 255.0:
                value = 255.0
            out[index] = value
    return out^


fn _invert(flat: List[Float64]) -> List[Float64]:
    var out = List[Float64]()
    for index in range(len(flat)):
        out.append(255.0 - flat[index])
    return out^


def test_identity_metrics() raises:
    var base = _pattern8()
    _assert_close(mean_squared_error_flat(base, base, 8, 8), 0.0, 1e-12, "MSE identity")
    _assert_close(mean_abs_error_flat(base, base, 8, 8), 0.0, 1e-12, "MAE identity")
    _assert_close(psnr_flat(base, base, 8, 8, 255.0), 99.0, 1e-12, "PSNR identity sentinel")
    _assert_close(
        normalized_cross_correlation_flat(base, base, 8, 8),
        1.0,
        1e-9,
        "NCC identity",
    )
    _assert_close(ssim_global_flat(base, base, 8, 8), 1.0, 1e-9, "SSIM identity")
    _assert_close(diff_fraction_flat(base, base, 8, 8, 1.0), 0.0, 1e-12, "diff fraction identity")
    _assert_true(duplicate_score_flat(base, base, 8, 8) > 0.999, "duplicate score near 1 for identity")
    print("✅ identity metrics")


def test_localized_difference() raises:
    var base = _pattern8()
    var changed = _patch_brighten(base)
    _assert_true(mean_squared_error_flat(base, changed, 8, 8) > 0.0, "MSE detects patch change")
    _assert_true(mean_abs_error_flat(base, changed, 8, 8) > 0.0, "MAE detects patch change")
    _assert_true(diff_fraction_flat(base, changed, 8, 8, 5.0) > 0.0, "diff fraction detects patch change")
    _assert_close(
        crop_region_similarity_flat(base, changed, 8, 8, 0, 0, 1, 1),
        1.0,
        1e-9,
        "unchanged crop stays identical",
    )
    _assert_true(
        crop_region_similarity_flat(base, changed, 8, 8, 2, 2, 3, 3) < 1.0,
        "changed crop similarity drops below 1",
    )
    _assert_true(duplicate_score_flat(base, changed, 8, 8) < 1.0, "duplicate score drops after local change")
    print("✅ localized-difference metrics")


def test_inverted_difference() raises:
    var base = _pattern8()
    var inverted = _invert(base)
    _assert_true(
        normalized_cross_correlation_flat(base, inverted, 8, 8) < -0.99,
        "inversion yields strongly negative NCC",
    )
    _assert_true(ssim_global_flat(base, inverted, 8, 8) < 0.0, "inversion lowers SSIM below zero")
    _assert_true(duplicate_score_flat(base, inverted, 8, 8) < 0.2, "inversion is not a duplicate")
    print("✅ inverted-image metrics")


def main() raises:
    print("━━━ image_similarity test suite ━━━")
    test_identity_metrics()
    test_localized_difference()
    test_inverted_difference()
    print("━━━ All image_similarity tests passed ━━━")
