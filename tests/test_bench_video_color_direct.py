from __future__ import annotations

from importlib import util
from pathlib import Path


def _load_bench_module():
    module_path = Path(__file__).resolve().parent / "benchmark" / "bench_video_color_direct.py"
    spec = util.spec_from_file_location("bench_video_color_direct", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bench = _load_bench_module()


def test_parse_mojo_output_extracts_video_color_results_and_timings() -> None:
    parsed_results, parsed_timings = bench._parse_mojo_output(
        "\n".join(
            [
                "MOJO_RESULT clip_mean_rgb255 120.0 20.0 95.0",
                "MOJO_RESULT dominant_clip_color_rgb255 200.0 20.0 20.0 0.58",
                "MOJO_RESULT clip_mean_saturation_rgb255 0.9",
                "MOJO_RESULT warm_frame_ratio_rgb255 0.66",
                "MOJO_RESULT color_drift_score_rgb255 0.28",
                "MOJO_RESULT preferred_text_contrast_for_video 5.88",
                "MOJO_RESULT preferred_text_color_for_video #FFFFFF",
                "MOJO_BENCH clip_mean_rgb255 12345.0 0",
                "MOJO_BENCH dominant_clip_color_rgb255 22345.0 0",
                "MOJO_BENCH clip_mean_saturation_rgb255 32345.0 0",
                "MOJO_BENCH warm_frame_ratio_rgb255 42345.0 0",
                "MOJO_BENCH color_drift_score_rgb255 52345.0 0",
                "MOJO_BENCH preferred_text_contrast_for_video 62345.0 0",
                "MOJO_BENCH preferred_text_color_for_video 72345.0 0",
            ]
        )
    )

    assert parsed_results == {
        "clip_mean_rgb255": [120.0, 20.0, 95.0],
        "dominant_clip_color_rgb255": [200.0, 20.0, 20.0, 0.58],
        "clip_mean_saturation_rgb255": 0.9,
        "warm_frame_ratio_rgb255": 0.66,
        "color_drift_score_rgb255": 0.28,
        "preferred_text_contrast_for_video": 5.88,
        "preferred_text_color_for_video": "#FFFFFF",
    }
    assert parsed_timings == {
        "clip_mean_rgb255": 12345.0,
        "dominant_clip_color_rgb255": 22345.0,
        "clip_mean_saturation_rgb255": 32345.0,
        "warm_frame_ratio_rgb255": 42345.0,
        "color_drift_score_rgb255": 52345.0,
        "preferred_text_contrast_for_video": 62345.0,
        "preferred_text_color_for_video": 72345.0,
    }
