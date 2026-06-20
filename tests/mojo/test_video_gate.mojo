"""
test_video_gate.mojo — Tests for the pure-Mojo video_gate router.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_video_gate.mojo
"""
from video_gate import (
    should_use_cached_video,
    needs_clearer_video,
    quality_gate_passed_video,
    is_mostly_static_video,
    should_extract_keyframes,
    route_video_request,
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


def test_duplicate_and_simple_question() raises:
    _assert_eq_int(
        route_video_request(0.1, 100.0, 0.0, 100.0, 0.0, True, 0), 0, "duplicate → use_cache"
    )
    _assert_eq_int(
        route_video_request(0.1, 100.0, 0.0, 100.0, 0.0, False, 2), 1, "simple question → features"
    )
    print("✅ duplicate and simple temporal question")


def test_clearer_video_and_text() raises:
    _assert_eq_int(
        route_video_request(0.2, 20.0, 0.0, 10.0, 0.0, False, 0), 2, "low quality → clearer video"
    )
    _assert_eq_int(
        route_video_request(0.8, 20.0, 0.0, 90.0, 0.0, False, 0), 2, "high flicker → clearer video"
    )
    _assert_eq_int(
        route_video_request(0.8, 20.0, 0.0, 10.0, 0.1, False, 1), 3, "text intent → OCR keyframes"
    )
    print("✅ clearer video and text intent")


def test_keyframes_and_full_clip() raises:
    _assert_eq_int(
        route_video_request(0.8, 2.0, 0.95, 10.0, 0.05, False, 0), 4, "static clip → keyframes"
    )
    _assert_eq_int(
        route_video_request(0.8, 40.0, 0.1, 10.0, 0.3, False, 0), 4, "many cuts → keyframes"
    )
    _assert_eq_int(
        route_video_request(0.8, 40.0, 0.1, 10.0, 0.05, False, 0), 5, "dynamic clip → full clip"
    )
    print("✅ keyframe vs full-clip routing")


def test_predicates() raises:
    _assert_true(should_use_cached_video(True), "should_use_cached_video")
    _assert_true(needs_clearer_video(0.2, 10.0), "needs_clearer_video low quality")
    _assert_true(not needs_clearer_video(0.8, 10.0), "needs_clearer_video false")
    _assert_true(quality_gate_passed_video(0.8, 10.0), "quality gate pass")
    _assert_true(not quality_gate_passed_video(0.2, 90.0), "quality gate fail")
    _assert_true(is_mostly_static_video(2.0, 0.9), "mostly static")
    _assert_true(not is_mostly_static_video(20.0, 0.9), "not static on motion")
    _assert_true(should_extract_keyframes(0.3, 20.0, 0), "extract by scene rate")
    _assert_true(should_extract_keyframes(0.0, 2.0, 0), "extract by static motion")
    _assert_true(should_extract_keyframes(0.0, 20.0, 1), "extract by text intent")
    print("✅ predicate helpers")


def main() raises:
    print("━━━ video_gate test suite ━━━")
    test_duplicate_and_simple_question()
    test_clearer_video_and_text()
    test_keyframes_and_full_clip()
    test_predicates()
    print("━━━ All video_gate tests passed ━━━")
