from __future__ import annotations

from pathlib import Path

from benchmarks.image_real_direct_benchmark import (
    _build_mojo_build_command,
    build_python_cases,
    load_png_image,
    parse_mojo_benchmark_output,
    summarize_value,
)
from benchmarks.png_loader import load_png_rgb


def test_summarize_value_matches_mojo_rounding_and_hashes() -> None:
    assert summarize_value(1.23456789) == "float:1.234568"
    assert summarize_value(-1.23456789) == "float:-1.234568"
    assert summarize_value(7) == "int:7"
    assert summarize_value([1.0, 2.25, 3.5]) == "list:3:79212981"


def test_parse_mojo_benchmark_output_extracts_timings_and_results() -> None:
    parsed = parse_mojo_benchmark_output(
        "\n".join(
            [
                "MOJO_IMAGE /tmp/test.png 64 64 4096",
                "MOJO_ITERS blur_score_flat 97",
                "MOJO_TIMING blur_score_flat 1234.5",
                "MOJO_RESULT blur_score_flat float:42.0",
            ]
        )
    )

    assert parsed["image_meta"] == {
        "path": "/tmp/test.png",
        "width": 64,
        "height": 64,
        "pixels": 4096,
    }
    assert parsed["iters"] == {"blur_score_flat": 97}
    assert parsed["timings"] == {"blur_score_flat": 1234.5}
    assert parsed["results"] == {"blur_score_flat": "float:42.0"}


def test_load_png_rgb_reads_repo_fixture() -> None:
    fixture = Path(
        "/Users/angel/Developer/decision-engine/"
        "mojo_env/.pixi/envs/default/share/jupyter/kernels/mojo/logo-64x64.png"
    )
    payload = load_png_rgb(fixture)

    assert payload["width"] == 64
    assert payload["height"] == 64
    assert len(payload["flat_rgb"]) == 64 * 64 * 3
    assert len(payload["flat_gray"]) == 64 * 64


def test_build_mojo_build_command_uses_repo_pixi_layout() -> None:
    binary_path = Path("/tmp/bench_image_real_direct")
    command = _build_mojo_build_command("/usr/local/bin/pixi", binary_path)

    assert command == [
        "/usr/local/bin/pixi",
        "run",
        "mojo",
        "build",
        "-I",
        "../mojo/engine",
        "../benchmarks/mojo_benchmarks/bench_image_real_direct.mojo",
        "-o",
        "/tmp/bench_image_real_direct",
    ]


def test_build_python_cases_includes_palette_analysis_cases() -> None:
    fixture = load_png_image(
        "mojo_logo_64",
        Path(
            "/Users/angel/Developer/decision-engine/"
            "mojo_env/.pixi/envs/default/share/jupyter/kernels/mojo/logo-64x64.png"
        ),
    )
    case_names = {case.name for case in build_python_cases(fixture)}

    assert {
        "dominant_palette_rgb255",
        "palette_size_estimate",
        "palette_entropy",
        "mean_saturation_rgb255",
        "warm_color_ratio_rgb255",
        "palette_contrast_score",
    } <= case_names
