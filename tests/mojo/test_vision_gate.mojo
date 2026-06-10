"""
test_vision_gate.mojo — Tests for the pure-Mojo vision_gate router.

Validates the action-code policy:
  0 use_cache, 1 answer_from_features, 2 ask_for_clearer_image,
  3 ocr_text_regions, 4 vision_llm_low_res, 5 vision_llm_selected_crops
and the predicate helpers.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_vision_gate.mojo
"""
from vision_gate import (
    route_image_request,
    should_use_cache,
    needs_clearer_image,
    is_text_heavy,
    quality_gate_passed,
)


def _assert_eq_int(got: Int, expected: Int, label: String) raises:
    if got != expected:
        print("❌ FAIL: " + label)
        print("   expected: " + String(expected))
        print("   got:      " + String(got))
        raise Error("assertion failed: " + label)


def _assert_true(cond: Bool, label: String) raises:
    if not cond:
        print("❌ FAIL: " + label)
        raise Error("assertion failed: " + label)


def test_duplicate_wins() raises:
    # Duplicate short-circuits everything, even a blurry image.
    _assert_eq_int(
        route_image_request(5.0, 5.0, 0.1, 0.9, True, 0), 0, "duplicate → use_cache"
    )
    print("✅ duplicate → use_cache (0)")


def test_pixel_question() raises:
    # Intent 2 answered from features even if blurry/dark.
    _assert_eq_int(
        route_image_request(1.0, 2.0, 0.0, 0.0, False, 2), 1, "pixel question → answer_from_features"
    )
    print("✅ pixel question → answer_from_features (1)")


def test_clearer_image() raises:
    # Sharp-enough threshold is 100; 30 is blurry → ask for clearer.
    _assert_eq_int(
        route_image_request(30.0, 128.0, 5.0, 0.5, False, 0), 2, "blurry → ask_for_clearer_image"
    )
    # Over-exposed even if sharp.
    _assert_eq_int(
        route_image_request(5000.0, 250.0, 5.0, 0.5, False, 0), 2, "over-exposed → ask_for_clearer_image"
    )
    print("✅ unusable → ask_for_clearer_image (2)")


def test_text_ocr() raises:
    # Sharp, well-exposed, text intent, dense edges → OCR.
    _assert_eq_int(
        route_image_request(5000.0, 128.0, 4.5, 0.4, False, 1), 3, "text intent + edges → ocr"
    )
    # Text intent but almost no edges → low-res model fallback.
    _assert_eq_int(
        route_image_request(5000.0, 128.0, 4.5, 0.02, False, 1), 4, "text intent + flat → low_res"
    )
    print("✅ text intent → ocr / low_res (3/4)")


def test_general_routing() raises:
    # Sharp, salient region (high edge density) → selected crops.
    _assert_eq_int(
        route_image_request(5000.0, 128.0, 6.0, 0.5, False, 0), 5, "salient → selected_crops"
    )
    # Sharp but low edge density → whole low-res image.
    _assert_eq_int(
        route_image_request(5000.0, 128.0, 6.0, 0.05, False, 0), 4, "diffuse → low_res"
    )
    print("✅ general intent → crops / low_res (5/4)")


def test_near_blank() raises:
    # Sharp, exposed, but near-zero entropy → nothing to analyze.
    _assert_eq_int(
        route_image_request(5000.0, 128.0, 0.2, 0.5, False, 0), 1, "near-blank → answer_from_features"
    )
    print("✅ near-blank → answer_from_features (1)")


def test_predicates() raises:
    _assert_true(should_use_cache(True), "should_use_cache(True)")
    _assert_true(not should_use_cache(False), "not should_use_cache(False)")
    _assert_true(needs_clearer_image(50.0, 128.0), "needs_clearer for blur 50")
    _assert_true(not needs_clearer_image(5000.0, 128.0), "no clearer for sharp mid")
    _assert_true(is_text_heavy(0.3, 4.0), "text-heavy true")
    _assert_true(not is_text_heavy(0.05, 4.0), "text-heavy false (low edges)")
    _assert_true(quality_gate_passed(5000.0, 128.0, 5.0), "quality gate passes")
    _assert_true(not quality_gate_passed(10.0, 128.0, 5.0), "quality gate fails on blur")
    print("✅ predicate helpers")


def main() raises:
    print("━━━ vision_gate test suite ━━━")
    test_duplicate_wins()
    test_pixel_question()
    test_clearer_image()
    test_text_ocr()
    test_general_routing()
    test_near_blank()
    test_predicates()
    print("━━━ All vision_gate tests passed ━━━")
