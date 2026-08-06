"""
test_image_palette.mojo — Tests for the pure-Mojo image_palette library.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_image_palette.mojo
"""
from image_palette import (
    dominant_palette_rgb255,
    palette_size_estimate,
    palette_entropy,
    mean_saturation_rgb255,
    warm_color_ratio_rgb255,
    palette_contrast_score,
    accent_color_hex,
    is_monochrome_palette,
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


def _assert_eq_string(got: String, expected: String, label: String) raises:
    if got != expected:
        print("❌ FAIL: " + label)
        print("   expected: " + expected)
        print("   got:      " + got)
        raise Error("assertion failed: " + label)


def _red_blue_2x2() -> List[Float64]:
    var flat = List[Float64]()
    flat.append(200.0); flat.append(20.0); flat.append(20.0)
    flat.append(200.0); flat.append(20.0); flat.append(20.0)
    flat.append(200.0); flat.append(20.0); flat.append(20.0)
    flat.append(20.0); flat.append(20.0); flat.append(200.0)
    return flat^


def _gray_2x2() -> List[Float64]:
    var flat = List[Float64]()
    flat.append(40.0); flat.append(40.0); flat.append(40.0)
    flat.append(120.0); flat.append(120.0); flat.append(120.0)
    flat.append(200.0); flat.append(200.0); flat.append(200.0)
    flat.append(80.0); flat.append(80.0); flat.append(80.0)
    return flat^


def test_dominant_palette_and_entropy() raises:
    var palette = dominant_palette_rgb255(_red_blue_2x2(), 2, 2, 4, 2)
    _assert_eq_int(len(palette), 8, "two dominant palette colours")
    _assert_close(palette[0], 200.0, 1e-9, "dominant red r")
    _assert_close(palette[1], 20.0, 1e-9, "dominant red g")
    _assert_close(palette[2], 20.0, 1e-9, "dominant red b")
    _assert_close(palette[3], 0.75, 1e-9, "dominant red weight")
    _assert_close(palette[4], 20.0, 1e-9, "secondary blue r")
    _assert_close(palette[5], 20.0, 1e-9, "secondary blue g")
    _assert_close(palette[6], 200.0, 1e-9, "secondary blue b")
    _assert_close(palette[7], 0.25, 1e-9, "secondary blue weight")

    _assert_eq_int(
        palette_size_estimate(_red_blue_2x2(), 2, 2, 4, 0.2),
        2,
        "palette size at 20% weight",
    )
    _assert_eq_int(
        palette_size_estimate(_red_blue_2x2(), 2, 2, 4, 0.3),
        1,
        "palette size at 30% weight",
    )
    _assert_close(
        palette_entropy(_red_blue_2x2(), 2, 2, 4),
        0.8112781244591328,
        1e-9,
        "palette entropy",
    )
    print("✅ dominant palette / entropy")


def test_saturation_warmth_and_accent() raises:
    _assert_close(
        mean_saturation_rgb255(_red_blue_2x2(), 2, 2),
        0.9,
        1e-9,
        "mean saturation",
    )
    _assert_close(
        warm_color_ratio_rgb255(_red_blue_2x2(), 2, 2, 0.25),
        0.75,
        1e-9,
        "warm color ratio",
    )
    _assert_close(
        palette_contrast_score(_red_blue_2x2(), 2, 2, 4, 2),
        0.040792744995753236,
        1e-9,
        "palette contrast score",
    )
    _assert_eq_string(
        accent_color_hex(_red_blue_2x2(), 2, 2, 4),
        "#C81414",
        "accent color hex",
    )
    print("✅ saturation / warmth / accent")


def test_monochrome_detection() raises:
    _assert_true(
        is_monochrome_palette(_gray_2x2(), 2, 2, 4, 0.2, 0.15),
        "grayscale palette is monochrome",
    )
    _assert_true(
        not is_monochrome_palette(_red_blue_2x2(), 2, 2, 4, 0.2, 0.15),
        "red/blue palette is not monochrome",
    )
    print("✅ monochrome detection")


def main() raises:
    print("━━━ image_palette test suite ━━━")
    test_dominant_palette_and_entropy()
    test_saturation_warmth_and_accent()
    test_monochrome_detection()
    print("━━━ All image_palette tests passed ━━━")
