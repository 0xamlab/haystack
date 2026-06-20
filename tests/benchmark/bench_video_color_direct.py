"""
bench_video_color_direct.py — compare direct Mojo and Python video color kernels.

This benchmark avoids the runtime socket/JSON boundary so the numbers reflect
kernel compute only. Use the runtime dispatch tests and kernel A-Z suite for
interface proof; use this script for raw video-color kernel speed.

Usage:
  ./.venv/bin/python tests/benchmark/bench_video_color_direct.py
"""

from __future__ import annotations

import importlib.util
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MOJO_ENV = PROJECT_ROOT / "mojo_env"
MOJO_BENCH = PROJECT_ROOT / "benchmarks" / "mojo_benchmarks" / "bench_video_color_direct.mojo"
MANUAL_LIB = PROJECT_ROOT / "benchmarks" / "python_manual_libs" / "video_color.py"

WIDTH = 96
HEIGHT = 64
FRAMES = 12
CHANNELS = 3
LEVELS = 8
SAMPLE_FRAMES = 6
WARM_MIN_SATURATION = 0.25
ITERATIONS = 24


def _load_manual_module():
    spec = importlib.util.spec_from_file_location("manual_video_color", MANUAL_LIB)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load manual video_color reference from {MANUAL_LIB}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


video_color_py = _load_manual_module()


def _scene(frame_index: int) -> int:
    if frame_index < 3:
        return 0
    if frame_index < 8:
        return 1
    return 2


def _build_clip() -> list[float]:
    clip: list[float] = []
    for frame_index in range(FRAMES):
        scene = _scene(frame_index)
        x_offset = (frame_index * 3) % WIDTH
        y_offset = (frame_index * 2) % HEIGHT
        for y in range(HEIGHT):
            for x in range(WIDTH):
                px = (x + x_offset) % WIDTH
                py = (y + y_offset) % HEIGHT
                if scene == 0:
                    clip.extend(
                        (
                            float((px * 2 + py + frame_index * 7) % 256),
                            float((px + 40 + frame_index * 5) % 256),
                            float((180 - py + frame_index * 3 + 256) % 256),
                        )
                    )
                elif scene == 1:
                    clip.extend(
                        (
                            220.0 if px < WIDTH // 2 else 25.0,
                            float((py * 3 + frame_index * 13) % 256),
                            float((255 - px + frame_index * 11 + 256) % 256),
                        )
                    )
                else:
                    stripe = 255.0 if ((px // 8 + py // 8 + frame_index) % 2) == 0 else 20.0
                    clip.extend(
                        (
                            stripe,
                            float((60 + py * 2 + frame_index * 9) % 256),
                            float((30 + px * 3 + frame_index * 4) % 256),
                        )
                    )
    return clip


def _result_checksum(result: Any) -> float:
    if isinstance(result, list):
        return sum(_result_checksum(item) for item in result)
    if isinstance(result, str):
        return 1.0 if result == "#FFFFFF" else 0.0
    return float(result)


def _benchmark_python(label: str, fn: Any, *args: Any) -> tuple[Any, float]:
    result = None
    for _ in range(3):
        result = fn(*args)

    start_ns = time.perf_counter_ns()
    checksum = 0.0
    for _ in range(ITERATIONS):
        result = fn(*args)
        checksum += _result_checksum(result)
    elapsed_ns = time.perf_counter_ns() - start_ns
    ns_per_call = elapsed_ns / ITERATIONS
    print(f"PY_BENCH {label} {ns_per_call} {checksum}")
    return result, ns_per_call


def _resolve_pixi() -> str:
    pixi = shutil.which("pixi")
    if pixi is None:
        raise RuntimeError("pixi is not available on PATH.")
    return pixi


def _parse_mojo_output(stdout: str) -> tuple[dict[str, Any], dict[str, float]]:
    results: dict[str, Any] = {}
    timings: dict[str, float] = {}
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if parts[:2] == ["MOJO_RESULT", "clip_mean_rgb255"] and len(parts) == 5:
            results["clip_mean_rgb255"] = [float(parts[2]), float(parts[3]), float(parts[4])]
            continue
        if parts[:2] == ["MOJO_RESULT", "dominant_clip_color_rgb255"] and len(parts) == 6:
            results["dominant_clip_color_rgb255"] = [
                float(parts[2]),
                float(parts[3]),
                float(parts[4]),
                float(parts[5]),
            ]
            continue
        if parts[:2] == ["MOJO_RESULT", "clip_mean_saturation_rgb255"] and len(parts) == 3:
            results["clip_mean_saturation_rgb255"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_RESULT", "warm_frame_ratio_rgb255"] and len(parts) == 3:
            results["warm_frame_ratio_rgb255"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_RESULT", "color_drift_score_rgb255"] and len(parts) == 3:
            results["color_drift_score_rgb255"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_RESULT", "preferred_text_contrast_for_video"] and len(parts) == 3:
            results["preferred_text_contrast_for_video"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_RESULT", "preferred_text_color_for_video"] and len(parts) == 3:
            results["preferred_text_color_for_video"] = parts[2]
            continue
        if parts[:2] == ["MOJO_BENCH", "clip_mean_rgb255"] and len(parts) >= 3:
            timings["clip_mean_rgb255"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "dominant_clip_color_rgb255"] and len(parts) >= 3:
            timings["dominant_clip_color_rgb255"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "clip_mean_saturation_rgb255"] and len(parts) >= 3:
            timings["clip_mean_saturation_rgb255"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "warm_frame_ratio_rgb255"] and len(parts) >= 3:
            timings["warm_frame_ratio_rgb255"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "color_drift_score_rgb255"] and len(parts) >= 3:
            timings["color_drift_score_rgb255"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "preferred_text_contrast_for_video"] and len(parts) >= 3:
            timings["preferred_text_contrast_for_video"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "preferred_text_color_for_video"] and len(parts) >= 3:
            timings["preferred_text_color_for_video"] = float(parts[2])
            continue
    return results, timings


def _run_mojo_benchmark() -> tuple[dict[str, Any], dict[str, float]]:
    proc = subprocess.run(
        [
            _resolve_pixi(),
            "run",
            "mojo",
            "run",
            "-I",
            "../mojo/engine",
            "../benchmarks/mojo_benchmarks/bench_video_color_direct.mojo",
        ],
        cwd=MOJO_ENV,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Mojo benchmark failed:\nstdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}")
    return _parse_mojo_output(proc.stdout)


def _assert_close(actual: float, expected: float, label: str) -> None:
    if not math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9):
        raise AssertionError(f"{label} mismatch: {actual} vs {expected}")


def _assert_close_list(actual: list[float], expected: list[float], label: str) -> None:
    if len(actual) != len(expected):
        raise AssertionError(f"{label} length mismatch: {actual!r} vs {expected!r}")
    for index, (actual_value, expected_value) in enumerate(zip(actual, expected, strict=True)):
        if not math.isclose(actual_value, expected_value, rel_tol=1e-9, abs_tol=1e-9):
            raise AssertionError(
                f"{label}[{index}] mismatch: {actual_value} vs {expected_value}"
            )


def main() -> None:
    clip = _build_clip()

    py_clip_mean, py_clip_mean_ns = _benchmark_python(
        "clip_mean_rgb255",
        video_color_py.clip_mean_rgb255,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
    )
    py_dominant, py_dominant_ns = _benchmark_python(
        "dominant_clip_color_rgb255",
        video_color_py.dominant_clip_color_rgb255,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        LEVELS,
        SAMPLE_FRAMES,
    )
    py_saturation, py_saturation_ns = _benchmark_python(
        "clip_mean_saturation_rgb255",
        video_color_py.clip_mean_saturation_rgb255,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
    )
    py_warm_ratio, py_warm_ratio_ns = _benchmark_python(
        "warm_frame_ratio_rgb255",
        video_color_py.warm_frame_ratio_rgb255,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        WARM_MIN_SATURATION,
    )
    py_drift, py_drift_ns = _benchmark_python(
        "color_drift_score_rgb255",
        video_color_py.color_drift_score_rgb255,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
    )
    py_text_contrast, py_text_contrast_ns = _benchmark_python(
        "preferred_text_contrast_for_video",
        video_color_py.preferred_text_contrast_for_video,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        LEVELS,
        SAMPLE_FRAMES,
    )
    py_text_color, py_text_color_ns = _benchmark_python(
        "preferred_text_color_for_video",
        video_color_py.preferred_text_color_for_video,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        LEVELS,
        SAMPLE_FRAMES,
    )

    mojo_results, mojo_timings = _run_mojo_benchmark()

    _assert_close_list(mojo_results["clip_mean_rgb255"], py_clip_mean, "clip_mean_rgb255")
    _assert_close_list(
        mojo_results["dominant_clip_color_rgb255"],
        py_dominant,
        "dominant_clip_color_rgb255",
    )
    _assert_close(
        mojo_results["clip_mean_saturation_rgb255"],
        py_saturation,
        "clip_mean_saturation_rgb255",
    )
    _assert_close(
        mojo_results["warm_frame_ratio_rgb255"],
        py_warm_ratio,
        "warm_frame_ratio_rgb255",
    )
    _assert_close(
        mojo_results["color_drift_score_rgb255"],
        py_drift,
        "color_drift_score_rgb255",
    )
    _assert_close(
        mojo_results["preferred_text_contrast_for_video"],
        py_text_contrast,
        "preferred_text_contrast_for_video",
    )
    if mojo_results["preferred_text_color_for_video"] != py_text_color:
        raise AssertionError(
            "preferred_text_color_for_video mismatch: "
            f"{mojo_results['preferred_text_color_for_video']} vs {py_text_color}"
        )

    speedups = {
        "clip_mean_rgb255": py_clip_mean_ns / mojo_timings["clip_mean_rgb255"],
        "dominant_clip_color_rgb255": py_dominant_ns / mojo_timings["dominant_clip_color_rgb255"],
        "clip_mean_saturation_rgb255": py_saturation_ns
        / mojo_timings["clip_mean_saturation_rgb255"],
        "warm_frame_ratio_rgb255": py_warm_ratio_ns / mojo_timings["warm_frame_ratio_rgb255"],
        "color_drift_score_rgb255": py_drift_ns / mojo_timings["color_drift_score_rgb255"],
        "preferred_text_contrast_for_video": py_text_contrast_ns
        / mojo_timings["preferred_text_contrast_for_video"],
        "preferred_text_color_for_video": py_text_color_ns
        / mojo_timings["preferred_text_color_for_video"],
    }

    print(
        "RESULT clip_mean_rgb255",
        py_clip_mean,
        mojo_timings["clip_mean_rgb255"],
        py_clip_mean_ns,
        speedups["clip_mean_rgb255"],
    )
    print(
        "RESULT dominant_clip_color_rgb255",
        py_dominant,
        mojo_timings["dominant_clip_color_rgb255"],
        py_dominant_ns,
        speedups["dominant_clip_color_rgb255"],
    )
    print(
        "RESULT clip_mean_saturation_rgb255",
        py_saturation,
        mojo_timings["clip_mean_saturation_rgb255"],
        py_saturation_ns,
        speedups["clip_mean_saturation_rgb255"],
    )
    print(
        "RESULT warm_frame_ratio_rgb255",
        py_warm_ratio,
        mojo_timings["warm_frame_ratio_rgb255"],
        py_warm_ratio_ns,
        speedups["warm_frame_ratio_rgb255"],
    )
    print(
        "RESULT color_drift_score_rgb255",
        py_drift,
        mojo_timings["color_drift_score_rgb255"],
        py_drift_ns,
        speedups["color_drift_score_rgb255"],
    )
    print(
        "RESULT preferred_text_contrast_for_video",
        py_text_contrast,
        mojo_timings["preferred_text_contrast_for_video"],
        py_text_contrast_ns,
        speedups["preferred_text_contrast_for_video"],
    )
    print(
        "RESULT preferred_text_color_for_video",
        py_text_color,
        mojo_timings["preferred_text_color_for_video"],
        py_text_color_ns,
        speedups["preferred_text_color_for_video"],
    )


if __name__ == "__main__":
    main()
