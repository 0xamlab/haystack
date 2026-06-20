from __future__ import annotations

from importlib import util
from pathlib import Path


def _load_bench_module():
    module_path = (
        Path(__file__).resolve().parent / "benchmark" / "bench_video_temporal_direct.py"
    )
    spec = util.spec_from_file_location("bench_video_temporal_direct", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bench = _load_bench_module()


def test_parse_int_list_token_supports_empty_and_dense_lists() -> None:
    assert bench._parse_int_list_token("empty") == []
    assert bench._parse_int_list_token("3,11") == [3, 11]


def test_parse_mojo_output_extracts_storyboard_results_and_timings() -> None:
    parsed_results, parsed_timings = bench._parse_mojo_output(
        "\n".join(
            [
                "MOJO_RESULT temporal_mean_abs_diff 32.5",
                "MOJO_RESULT scene_cut_count 4",
                "MOJO_RESULT video_quality_score 0.85",
                "MOJO_RESULT longest_scene_index 0",
                "MOJO_RESULT storyboard_frame_indices 3,11",
                "MOJO_BENCH temporal_mean_abs_diff 271083.3 0",
                "MOJO_BENCH scene_cut_count 444666.6 0",
                "MOJO_BENCH video_quality_score 914000.0 0",
                "MOJO_BENCH longest_scene_index 453791.6 0",
                "MOJO_BENCH storyboard_frame_indices 451166.6 0",
            ]
        )
    )

    assert parsed_results == {
        "temporal_mean_abs_diff": 32.5,
        "scene_cut_count": 4,
        "video_quality_score": 0.85,
        "longest_scene_index": 0,
        "storyboard_frame_indices": [3, 11],
    }
    assert parsed_timings == {
        "temporal_mean_abs_diff": 271083.3,
        "scene_cut_count": 444666.6,
        "video_quality_score": 914000.0,
        "longest_scene_index": 453791.6,
        "storyboard_frame_indices": 451166.6,
    }
