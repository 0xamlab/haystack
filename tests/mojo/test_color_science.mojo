"""
test_color_science.mojo — Tests for the pure-Mojo color_science surface.

Validates:
  - CIE76 and Lab->LCH conversions
  - gamma-correct sRGB luminance and WCAG contrast
  - colour-temperature / metamerism / CRI helpers
  - CIE whiteness computation

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_color_science.mojo
"""
from color_science import (
    delta_e_76,
    lab_to_lch_l,
    lab_to_lch_c,
    lab_to_lch_h,
    rgb_to_luminance,
    contrast_ratio,
    wcag_aa_pass,
    color_temperature_approx,
    metamerism_index,
    chromatic_adaptation_von_kries,
    cri_from_delta_e,
    whiteness_index_cie,
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


def test_lab_space_helpers() raises:
    _assert_close(delta_e_76(50.0, 10.0, -5.0, 50.0, 10.0, -5.0), 0.0, 1e-12, "delta_e_76 identity")
    _assert_close(lab_to_lch_l(42.0), 42.0, 1e-12, "lab_to_lch_l passthrough")
    _assert_close(lab_to_lch_c(3.0, 4.0), 5.0, 1e-12, "lab_to_lch_c 3-4-5")
    _assert_close(lab_to_lch_h(0.0, 1.0), 90.0, 1e-12, "lab_to_lch_h quadrant I")
    _assert_close(lab_to_lch_h(-1.0, -1.0), 225.0, 1e-12, "lab_to_lch_h wraps negative hue")
    print("✅ Lab/LCH helpers")


def test_wcag_luminance_and_contrast() raises:
    _assert_close(rgb_to_luminance(0.0, 0.0, 0.0), 0.0, 1e-12, "black luminance")
    _assert_close(rgb_to_luminance(1.0, 1.0, 1.0), 1.0, 1e-12, "white luminance")
    _assert_close(
        rgb_to_luminance(0.5, 0.5, 0.5),
        0.21404114048223255,
        1e-8,
        "mid-gray luminance uses gamma correction",
    )
    _assert_close(contrast_ratio(0.0, 1.0), 21.0, 1e-12, "black vs white contrast")
    _assert_true(wcag_aa_pass(4.5, 12.0) == 1.0, "normal text passes at 4.5")
    _assert_true(wcag_aa_pass(3.0, 18.0) == 1.0, "large text passes at 3.0")
    _assert_true(wcag_aa_pass(3.0, 12.0) == 0.0, "normal text fails below 4.5")
    print("✅ WCAG luminance/contrast")


def test_color_quality_helpers() raises:
    _assert_close(color_temperature_approx(1.0, 1.0), 6500.0, 1e-12, "neutral CCT")
    _assert_close(metamerism_index(4.0, 1.5), 2.5, 1e-12, "metamerism delta")
    _assert_close(
        chromatic_adaptation_von_kries(0.4, 1.2),
        0.48,
        1e-12,
        "von Kries gain",
    )
    _assert_close(cri_from_delta_e(2.0), 90.8, 1e-12, "CRI from delta E")
    _assert_close(
        whiteness_index_cie(95.0, 0.310, 0.320, 0.313, 0.329),
        112.7,
        1e-9,
        "CIE whiteness index",
    )
    print("✅ colour quality helpers")


def main() raises:
    print("━━━ color_science test suite ━━━")
    test_lab_space_helpers()
    test_wcag_luminance_and_contrast()
    test_color_quality_helpers()
    print("━━━ All color_science tests passed ━━━")
