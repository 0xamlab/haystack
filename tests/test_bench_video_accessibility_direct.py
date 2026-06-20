from __future__ import annotations

from importlib import util
from pathlib import Path


def _load_bench_module():
    module_path = Path(__file__).resolve().parent / "benchmark" / "bench_video_accessibility_direct.py"
    spec = util.spec_from_file_location("bench_video_accessibility_direct", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bench = _load_bench_module()


def test_parse_mojo_output_extracts_video_accessibility_results_and_timings() -> None:
    parsed_results, parsed_timings = bench._parse_mojo_output(
        "\n".join(
            [
                "MOJO_RESULT frame_min_preferred_text_contrast_for_video 1.37",
                "MOJO_RESULT frame_preferred_text_color_for_video #FFFFFF",
                "MOJO_RESULT sampled_video_min_text_contrast 1.25",
                "MOJO_RESULT sampled_video_wcag_safe_ratio 0.5",
                "MOJO_RESULT needs_text_backplate_for_video True",
                "MOJO_RESULT subtitle_band_min_preferred_text_contrast_for_video 1.11",
                "MOJO_RESULT subtitle_band_preferred_text_color_for_video #000000",
                "MOJO_RESULT sampled_subtitle_band_wcag_safe_ratio 0.25",
                "MOJO_RESULT subtitle_band_needs_backplate_for_video True",
                "MOJO_BENCH frame_min_preferred_text_contrast_for_video 12345.0 0",
                "MOJO_BENCH frame_preferred_text_color_for_video 22345.0 0",
                "MOJO_BENCH sampled_video_min_text_contrast 32345.0 0",
                "MOJO_BENCH sampled_video_wcag_safe_ratio 42345.0 0",
                "MOJO_BENCH needs_text_backplate_for_video 52345.0 0",
                "MOJO_BENCH subtitle_band_min_preferred_text_contrast_for_video 62345.0 0",
                "MOJO_BENCH subtitle_band_preferred_text_color_for_video 72345.0 0",
                "MOJO_BENCH sampled_subtitle_band_wcag_safe_ratio 82345.0 0",
                "MOJO_BENCH subtitle_band_needs_backplate_for_video 92345.0 0",
            ]
        )
    )

    assert parsed_results == {
        "frame_min_preferred_text_contrast_for_video": 1.37,
        "frame_preferred_text_color_for_video": "#FFFFFF",
        "sampled_video_min_text_contrast": 1.25,
        "sampled_video_wcag_safe_ratio": 0.5,
        "needs_text_backplate_for_video": True,
        "subtitle_band_min_preferred_text_contrast_for_video": 1.11,
        "subtitle_band_preferred_text_color_for_video": "#000000",
        "sampled_subtitle_band_wcag_safe_ratio": 0.25,
        "subtitle_band_needs_backplate_for_video": True,
    }
    assert parsed_timings == {
        "frame_min_preferred_text_contrast_for_video": 12345.0,
        "frame_preferred_text_color_for_video": 22345.0,
        "sampled_video_min_text_contrast": 32345.0,
        "sampled_video_wcag_safe_ratio": 42345.0,
        "needs_text_backplate_for_video": 52345.0,
        "subtitle_band_min_preferred_text_contrast_for_video": 62345.0,
        "subtitle_band_preferred_text_color_for_video": 72345.0,
        "sampled_subtitle_band_wcag_safe_ratio": 82345.0,
        "subtitle_band_needs_backplate_for_video": 92345.0,
    }
