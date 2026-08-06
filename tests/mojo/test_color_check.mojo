"""
test_color_check.mojo — Tests for the pure-Mojo color_check accessibility surface.

Validates:
  - color_science uses gamma-correct WCAG luminance
  - color_check computes correct WCAG thresholds and pass/fail decisions
  - hex helpers validate input and choose the correct text colour
  - image helpers recover a dominant background and recommend accessible text

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_color_check.mojo
"""
from color_check import (
    wcag_relative_luminance_rgb255,
    wcag_relative_luminance_hex,
    wcag_aa_required_contrast,
    wcag_contrast_ratio_hex,
    wcag_text_pass_hex,
    preferred_text_color_hex,
    dominant_background_rgb255,
    dominant_background_hex,
    dominant_background_contrast_ratio_hex,
    dominant_background_wcag_pass_hex,
    preferred_text_color_for_image,
    preferred_text_contrast_for_image,
    preferred_text_pass_for_image,
)
from color_science import rgb_to_luminance


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


def _assert_eq_string(got: String, expected: String, label: String) raises:
    if got != expected:
        print("❌ FAIL: " + label)
        print("   expected: " + expected)
        print("   got:      " + got)
        raise Error("assertion failed: " + label)


def _red_dominant_image() -> List[Float64]:
    var flat = List[Float64]()
    # 3 red pixels, 1 blue pixel -> dominant weight 0.75.
    flat.append(200.0); flat.append(20.0); flat.append(20.0)
    flat.append(200.0); flat.append(20.0); flat.append(20.0)
    flat.append(200.0); flat.append(20.0); flat.append(20.0)
    flat.append(20.0); flat.append(20.0); flat.append(200.0)
    return flat^


def _yellow_image() -> List[Float64]:
    var flat = List[Float64]()
    for _ in range(4):
        flat.append(250.0)
        flat.append(250.0)
        flat.append(0.0)
    return flat^


def test_gamma_correct_luminance() raises:
    _assert_close(
        rgb_to_luminance(0.5, 0.5, 0.5),
        0.21404114048223255,
        1e-8,
        "rgb_to_luminance mid-gray uses sRGB gamma correction",
    )
    _assert_close(
        wcag_relative_luminance_rgb255(128.0, 128.0, 128.0),
        0.21586050011389923,
        1e-8,
        "wcag_relative_luminance_rgb255(128)",
    )
    _assert_close(
        wcag_relative_luminance_hex("#808080"),
        0.21586050011389923,
        1e-8,
        "wcag_relative_luminance_hex(#808080)",
    )
    print("✅ gamma-correct luminance")


def test_wcag_thresholds_and_hex_helpers() raises:
    _assert_close(wcag_aa_required_contrast(14.0, False), 4.5, 1e-8, "14pt normal -> 4.5")
    _assert_close(wcag_aa_required_contrast(14.0, True), 3.0, 1e-8, "14pt bold -> 3.0")
    _assert_close(wcag_aa_required_contrast(18.0, False), 3.0, 1e-8, "18pt regular -> 3.0")
    _assert_close(
        wcag_contrast_ratio_hex("#336699", "#FFFFFF"),
        5.997786839657083,
        1e-8,
        "#336699 vs white contrast",
    )
    _assert_true(
        not wcag_text_pass_hex("#808080", "#FFFFFF", 12.0, False),
        "gray on white fails normal text",
    )
    _assert_true(
        wcag_text_pass_hex("#808080", "#FFFFFF", 14.0, True),
        "gray on white passes 14pt bold",
    )
    _assert_eq_string(preferred_text_color_hex("#336699"), "#FFFFFF", "dark blue prefers white")
    _assert_eq_string(preferred_text_color_hex("#FAFA00"), "#000000", "light yellow prefers black")
    print("✅ WCAG thresholds + hex helpers")


def test_invalid_hex_rejected() raises:
    var threw = False
    try:
        _ = wcag_relative_luminance_hex("#12GG00")
    except e:
        _ = e
        threw = True
    _assert_true(threw, "invalid hex raises")
    print("✅ invalid hex rejected")


def test_image_background_helpers() raises:
    var image = _red_dominant_image()
    var bg = dominant_background_rgb255(image, 2, 2, 4)
    _assert_true(len(bg) == 4, "dominant_background_rgb255 returns [r,g,b,weight]")
    _assert_close(bg[0], 200.0, 1e-12, "dominant background r")
    _assert_close(bg[1], 20.0, 1e-12, "dominant background g")
    _assert_close(bg[2], 20.0, 1e-12, "dominant background b")
    _assert_close(bg[3], 0.75, 1e-12, "dominant background weight")
    _assert_eq_string(dominant_background_hex(image, 2, 2, 4), "#C81414", "dominant background hex")
    _assert_close(
        dominant_background_contrast_ratio_hex(image, 2, 2, 4, "#FFFFFF"),
        5.8888921644276735,
        1e-8,
        "dominant background contrast with white",
    )
    _assert_true(
        not dominant_background_wcag_pass_hex(image, 2, 2, 4, "#000000", 12.0, False),
        "black text fails red dominant background",
    )
    _assert_true(
        dominant_background_wcag_pass_hex(image, 2, 2, 4, "#FFFFFF", 12.0, False),
        "white text passes red dominant background",
    )
    _assert_eq_string(
        preferred_text_color_for_image(image, 2, 2, 4),
        "#FFFFFF",
        "red dominant image prefers white",
    )
    _assert_close(
        preferred_text_contrast_for_image(image, 2, 2, 4),
        5.8888921644276735,
        1e-8,
        "preferred text contrast for image",
    )
    _assert_true(
        preferred_text_pass_for_image(image, 2, 2, 4, 12.0, False),
        "preferred text passes red dominant image",
    )
    print("✅ dominant background image helpers")


def test_light_image_prefers_black() raises:
    var image = _yellow_image()
    _assert_eq_string(
        preferred_text_color_for_image(image, 2, 2, 4),
        "#000000",
        "light image prefers black",
    )
    _assert_true(
        preferred_text_pass_for_image(image, 2, 2, 4, 12.0, False),
        "preferred text passes light image",
    )
    print("✅ light image accessibility")


def main() raises:
    print("━━━ color_check test suite ━━━")
    test_gamma_correct_luminance()
    test_wcag_thresholds_and_hex_helpers()
    test_invalid_hex_rejected()
    test_image_background_helpers()
    test_light_image_prefers_black()
    print("━━━ All color_check tests passed ━━━")
