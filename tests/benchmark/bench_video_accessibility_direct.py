"""
bench_video_accessibility_direct.py — compare direct Mojo and Python video accessibility kernels.

This benchmark bypasses the runtime socket/JSON path so the timings isolate
kernel compute only. Use the runtime dispatch tests for interface proof.

Usage:
  ./.venv/bin/python tests/benchmark/bench_video_accessibility_direct.py
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
MOJO_BENCH = PROJECT_ROOT / "benchmarks" / "mojo_benchmarks" / "bench_video_accessibility_direct.mojo"
MANUAL_LIB = PROJECT_ROOT / "benchmarks" / "python_manual_libs" / "video_accessibility.py"

WIDTH = 96
HEIGHT = 64
FRAMES = 12
CHANNELS = 3
SAMPLE_FRAMES = 6
BAND_ROWS = 12
FONT_SIZE_PT = 16.0
IS_BOLD = False
ITERATIONS = 24


def _load_manual_module():
    spec = importlib.util.spec_from_file_location("manual_video_accessibility", MANUAL_LIB)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load manual video_accessibility reference from {MANUAL_LIB}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


video_accessibility_py = _load_manual_module()


def _scene(frame_index: int) -> int:
    if frame_index < 4:
        return 0
    if frame_index < 8:
        return 1
    return 2


def _build_clip() -> list[float]:
    clip: list[float] = []
    for frame_index in range(FRAMES):
        scene = _scene(frame_index)
        x_offset = (frame_index * 5) % WIDTH
        y_offset = (frame_index * 3) % HEIGHT
        for y in range(HEIGHT):
            for x in range(WIDTH):
                px = (x + x_offset) % WIDTH
                py = (y + y_offset) % HEIGHT
                if scene == 0:
                    base = 220.0 if ((px // 6 + py // 6 + frame_index) % 2) == 0 else 20.0
                    clip.extend((base, base, base))
                elif scene == 1:
                    base = 25.0 if px < WIDTH // 2 else 230.0
                    accent = 240.0 if (py + frame_index) % 12 < 6 else 15.0
                    clip.extend((base, accent, float((40 + px * 2 + frame_index * 7) % 256)))
                else:
                    if py >= HEIGHT - BAND_ROWS:
                        band = 235.0 if ((px // 8 + frame_index) % 2) == 0 else 20.0
                        clip.extend((band, band, band))
                    else:
                        clip.extend(
                            (
                                float((60 + px + frame_index * 3) % 256),
                                float((20 + py * 2 + frame_index * 5) % 256),
                                float((180 + px // 2 - py + frame_index * 4 + 512) % 256),
                            )
                        )
    return clip


def _result_checksum(result: Any) -> float:
    if isinstance(result, str):
        return 1.0 if result == "#FFFFFF" else 0.0
    if isinstance(result, bool):
        return 1.0 if result else 0.0
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
        if parts[:2] == ["MOJO_RESULT", "frame_min_preferred_text_contrast_for_video"] and len(parts) == 3:
            results["frame_min_preferred_text_contrast_for_video"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_RESULT", "frame_preferred_text_color_for_video"] and len(parts) == 3:
            results["frame_preferred_text_color_for_video"] = parts[2]
            continue
        if parts[:2] == ["MOJO_RESULT", "sampled_video_min_text_contrast"] and len(parts) == 3:
            results["sampled_video_min_text_contrast"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_RESULT", "sampled_video_wcag_safe_ratio"] and len(parts) == 3:
            results["sampled_video_wcag_safe_ratio"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_RESULT", "needs_text_backplate_for_video"] and len(parts) == 3:
            results["needs_text_backplate_for_video"] = parts[2] == "True"
            continue
        if parts[:2] == ["MOJO_RESULT", "subtitle_band_min_preferred_text_contrast_for_video"] and len(parts) == 3:
            results["subtitle_band_min_preferred_text_contrast_for_video"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_RESULT", "subtitle_band_preferred_text_color_for_video"] and len(parts) == 3:
            results["subtitle_band_preferred_text_color_for_video"] = parts[2]
            continue
        if parts[:2] == ["MOJO_RESULT", "sampled_subtitle_band_wcag_safe_ratio"] and len(parts) == 3:
            results["sampled_subtitle_band_wcag_safe_ratio"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_RESULT", "subtitle_band_needs_backplate_for_video"] and len(parts) == 3:
            results["subtitle_band_needs_backplate_for_video"] = parts[2] == "True"
            continue
        if parts[:2] == ["MOJO_BENCH", "frame_min_preferred_text_contrast_for_video"] and len(parts) >= 3:
            timings["frame_min_preferred_text_contrast_for_video"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "frame_preferred_text_color_for_video"] and len(parts) >= 3:
            timings["frame_preferred_text_color_for_video"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "sampled_video_min_text_contrast"] and len(parts) >= 3:
            timings["sampled_video_min_text_contrast"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "sampled_video_wcag_safe_ratio"] and len(parts) >= 3:
            timings["sampled_video_wcag_safe_ratio"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "needs_text_backplate_for_video"] and len(parts) >= 3:
            timings["needs_text_backplate_for_video"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "subtitle_band_min_preferred_text_contrast_for_video"] and len(parts) >= 3:
            timings["subtitle_band_min_preferred_text_contrast_for_video"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "subtitle_band_preferred_text_color_for_video"] and len(parts) >= 3:
            timings["subtitle_band_preferred_text_color_for_video"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "sampled_subtitle_band_wcag_safe_ratio"] and len(parts) >= 3:
            timings["sampled_subtitle_band_wcag_safe_ratio"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "subtitle_band_needs_backplate_for_video"] and len(parts) >= 3:
            timings["subtitle_band_needs_backplate_for_video"] = float(parts[2])
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
            "../benchmarks/mojo_benchmarks/bench_video_accessibility_direct.mojo",
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


def _assert_eq(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label} mismatch: {actual!r} vs {expected!r}")


def main() -> None:
    clip = _build_clip()

    py_frame_contrast, py_frame_contrast_ns = _benchmark_python(
        "frame_min_preferred_text_contrast_for_video",
        video_accessibility_py.frame_min_preferred_text_contrast_for_video,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        5,
    )
    py_frame_color, py_frame_color_ns = _benchmark_python(
        "frame_preferred_text_color_for_video",
        video_accessibility_py.frame_preferred_text_color_for_video,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        5,
    )
    py_sampled_contrast, py_sampled_contrast_ns = _benchmark_python(
        "sampled_video_min_text_contrast",
        video_accessibility_py.sampled_video_min_text_contrast,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        SAMPLE_FRAMES,
    )
    py_sampled_ratio, py_sampled_ratio_ns = _benchmark_python(
        "sampled_video_wcag_safe_ratio",
        video_accessibility_py.sampled_video_wcag_safe_ratio,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        SAMPLE_FRAMES,
        FONT_SIZE_PT,
        IS_BOLD,
    )
    py_sampled_backplate, py_sampled_backplate_ns = _benchmark_python(
        "needs_text_backplate_for_video",
        video_accessibility_py.needs_text_backplate_for_video,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        SAMPLE_FRAMES,
        FONT_SIZE_PT,
        IS_BOLD,
    )
    py_band_contrast, py_band_contrast_ns = _benchmark_python(
        "subtitle_band_min_preferred_text_contrast_for_video",
        video_accessibility_py.subtitle_band_min_preferred_text_contrast_for_video,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        SAMPLE_FRAMES,
        BAND_ROWS,
    )
    py_band_color, py_band_color_ns = _benchmark_python(
        "subtitle_band_preferred_text_color_for_video",
        video_accessibility_py.subtitle_band_preferred_text_color_for_video,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        SAMPLE_FRAMES,
        BAND_ROWS,
    )
    py_band_ratio, py_band_ratio_ns = _benchmark_python(
        "sampled_subtitle_band_wcag_safe_ratio",
        video_accessibility_py.sampled_subtitle_band_wcag_safe_ratio,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        SAMPLE_FRAMES,
        BAND_ROWS,
        FONT_SIZE_PT,
        IS_BOLD,
    )
    py_band_backplate, py_band_backplate_ns = _benchmark_python(
        "subtitle_band_needs_backplate_for_video",
        video_accessibility_py.subtitle_band_needs_backplate_for_video,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        SAMPLE_FRAMES,
        BAND_ROWS,
        FONT_SIZE_PT,
        IS_BOLD,
    )

    mojo_results, mojo_timings = _run_mojo_benchmark()

    _assert_close(
        mojo_results["frame_min_preferred_text_contrast_for_video"],
        py_frame_contrast,
        "frame_min_preferred_text_contrast_for_video",
    )
    _assert_eq(
        mojo_results["frame_preferred_text_color_for_video"],
        py_frame_color,
        "frame_preferred_text_color_for_video",
    )
    _assert_close(
        mojo_results["sampled_video_min_text_contrast"],
        py_sampled_contrast,
        "sampled_video_min_text_contrast",
    )
    _assert_close(
        mojo_results["sampled_video_wcag_safe_ratio"],
        py_sampled_ratio,
        "sampled_video_wcag_safe_ratio",
    )
    _assert_eq(
        mojo_results["needs_text_backplate_for_video"],
        py_sampled_backplate,
        "needs_text_backplate_for_video",
    )
    _assert_close(
        mojo_results["subtitle_band_min_preferred_text_contrast_for_video"],
        py_band_contrast,
        "subtitle_band_min_preferred_text_contrast_for_video",
    )
    _assert_eq(
        mojo_results["subtitle_band_preferred_text_color_for_video"],
        py_band_color,
        "subtitle_band_preferred_text_color_for_video",
    )
    _assert_close(
        mojo_results["sampled_subtitle_band_wcag_safe_ratio"],
        py_band_ratio,
        "sampled_subtitle_band_wcag_safe_ratio",
    )
    _assert_eq(
        mojo_results["subtitle_band_needs_backplate_for_video"],
        py_band_backplate,
        "subtitle_band_needs_backplate_for_video",
    )

    speedups = {
        "frame_min_preferred_text_contrast_for_video": py_frame_contrast_ns
        / mojo_timings["frame_min_preferred_text_contrast_for_video"],
        "frame_preferred_text_color_for_video": py_frame_color_ns
        / mojo_timings["frame_preferred_text_color_for_video"],
        "sampled_video_min_text_contrast": py_sampled_contrast_ns
        / mojo_timings["sampled_video_min_text_contrast"],
        "sampled_video_wcag_safe_ratio": py_sampled_ratio_ns
        / mojo_timings["sampled_video_wcag_safe_ratio"],
        "needs_text_backplate_for_video": py_sampled_backplate_ns
        / mojo_timings["needs_text_backplate_for_video"],
        "subtitle_band_min_preferred_text_contrast_for_video": py_band_contrast_ns
        / mojo_timings["subtitle_band_min_preferred_text_contrast_for_video"],
        "subtitle_band_preferred_text_color_for_video": py_band_color_ns
        / mojo_timings["subtitle_band_preferred_text_color_for_video"],
        "sampled_subtitle_band_wcag_safe_ratio": py_band_ratio_ns
        / mojo_timings["sampled_subtitle_band_wcag_safe_ratio"],
        "subtitle_band_needs_backplate_for_video": py_band_backplate_ns
        / mojo_timings["subtitle_band_needs_backplate_for_video"],
    }

    print(
        "RESULT frame_min_preferred_text_contrast_for_video",
        py_frame_contrast,
        mojo_timings["frame_min_preferred_text_contrast_for_video"],
        py_frame_contrast_ns,
        speedups["frame_min_preferred_text_contrast_for_video"],
    )
    print(
        "RESULT frame_preferred_text_color_for_video",
        py_frame_color,
        mojo_timings["frame_preferred_text_color_for_video"],
        py_frame_color_ns,
        speedups["frame_preferred_text_color_for_video"],
    )
    print(
        "RESULT sampled_video_min_text_contrast",
        py_sampled_contrast,
        mojo_timings["sampled_video_min_text_contrast"],
        py_sampled_contrast_ns,
        speedups["sampled_video_min_text_contrast"],
    )
    print(
        "RESULT sampled_video_wcag_safe_ratio",
        py_sampled_ratio,
        mojo_timings["sampled_video_wcag_safe_ratio"],
        py_sampled_ratio_ns,
        speedups["sampled_video_wcag_safe_ratio"],
    )
    print(
        "RESULT needs_text_backplate_for_video",
        py_sampled_backplate,
        mojo_timings["needs_text_backplate_for_video"],
        py_sampled_backplate_ns,
        speedups["needs_text_backplate_for_video"],
    )
    print(
        "RESULT subtitle_band_min_preferred_text_contrast_for_video",
        py_band_contrast,
        mojo_timings["subtitle_band_min_preferred_text_contrast_for_video"],
        py_band_contrast_ns,
        speedups["subtitle_band_min_preferred_text_contrast_for_video"],
    )
    print(
        "RESULT subtitle_band_preferred_text_color_for_video",
        py_band_color,
        mojo_timings["subtitle_band_preferred_text_color_for_video"],
        py_band_color_ns,
        speedups["subtitle_band_preferred_text_color_for_video"],
    )
    print(
        "RESULT sampled_subtitle_band_wcag_safe_ratio",
        py_band_ratio,
        mojo_timings["sampled_subtitle_band_wcag_safe_ratio"],
        py_band_ratio_ns,
        speedups["sampled_subtitle_band_wcag_safe_ratio"],
    )
    print(
        "RESULT subtitle_band_needs_backplate_for_video",
        py_band_backplate,
        mojo_timings["subtitle_band_needs_backplate_for_video"],
        py_band_backplate_ns,
        speedups["subtitle_band_needs_backplate_for_video"],
    )


if __name__ == "__main__":
    main()
