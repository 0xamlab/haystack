"""
Test_video_storyboard.mojo — Tests for the pure-Mojo video_storyboard library.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_video_storyboard.mojo
"""
from video_storyboard import (
    scene_start_indices,
    scene_end_indices,
    scene_lengths_frames,
    scene_representative_frames,
    longest_scene_index,
    storyboard_frame_indices,
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


def _assert_eq_list_int(got: List[Int], expected: List[Int], label: String) raises:
    if len(got) != len(expected):
        print("❌ FAIL: " + label)
        print("   expected len: " + String(len(expected)))
        print("   got len:      " + String(len(got)))
        raise Error("assertion failed: " + label)
    for index in range(len(expected)):
        if got[index] != expected[index]:
            print("❌ FAIL: " + label)
            print("   mismatch at index " + String(index))
            print("   expected: " + String(expected[index]))
            print("   got:      " + String(got[index]))
            raise Error("assertion failed: " + label)


def _list_int1(a: Int) -> List[Int]:
    var out = List[Int]()
    out.append(a)
    return out^


def _list_int2(a: Int, b: Int) -> List[Int]:
    var out = List[Int]()
    out.append(a)
    out.append(b)
    return out^


def _list_int3(a: Int, b: Int, c: Int) -> List[Int]:
    var out = List[Int]()
    out.append(a)
    out.append(b)
    out.append(c)
    return out^


def _clip_three_scenes() -> List[Float64]:
    var flat = List[Float64]()
    for _ in range(16 * 2):
        flat.append(10.0)
    for _ in range(16 * 3):
        flat.append(120.0)
    for _ in range(16 * 2):
        flat.append(220.0)
    return flat^


def test_scene_spans() raises:
    var clip = _clip_three_scenes()
    _assert_eq_list_int(
        scene_start_indices(clip, 4, 4, 1, 0.2),
        _list_int3(0, 2, 5),
        "scene_start_indices",
    )
    _assert_eq_list_int(
        scene_end_indices(clip, 4, 4, 1, 0.2),
        _list_int3(1, 4, 6),
        "scene_end_indices",
    )
    _assert_eq_list_int(
        scene_lengths_frames(clip, 4, 4, 1, 0.2),
        _list_int3(2, 3, 2),
        "scene_lengths_frames",
    )
    _assert_eq_list_int(
        scene_representative_frames(clip, 4, 4, 1, 0.2),
        _list_int3(0, 3, 5),
        "scene_representative_frames",
    )
    print("✅ scene spans")


def test_storyboard_selection() raises:
    var clip = _clip_three_scenes()
    _assert_eq_int(longest_scene_index(clip, 4, 4, 1, 0.2), 1, "longest_scene_index")
    _assert_eq_list_int(
        storyboard_frame_indices(clip, 4, 4, 1, 0.2, 4),
        _list_int3(0, 3, 5),
        "storyboard_frame_indices full",
    )
    _assert_eq_list_int(
        storyboard_frame_indices(clip, 4, 4, 1, 0.2, 2),
        _list_int2(0, 5),
        "storyboard_frame_indices sampled",
    )
    _assert_eq_list_int(
        storyboard_frame_indices(clip, 4, 4, 1, 0.2, 1),
        _list_int1(3),
        "storyboard_frame_indices single",
    )
    print("✅ storyboard selection")


def main() raises:
    print("━━━ video_storyboard test suite ━━━")
    test_scene_spans()
    test_storyboard_selection()
    print("━━━ All video_storyboard tests passed ━━━")
