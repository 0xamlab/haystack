"""
bench_vision_color_check.py — compare direct Mojo and Python image color-check kernels.

This benchmark intentionally avoids the Unix-socket/JSON runtime boundary so the
numbers reflect kernel compute only. Use the runtime-server tests and kernel A-Z
suite for dispatcher proof; use this script for raw image-kernel speed.

Usage:
  ./.venv/bin/python tests/benchmark/bench_vision_color_check.py
"""

from __future__ import annotations

import math
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MOJO_ENV = PROJECT_ROOT / "mojo_env"
MOJO_BENCH = PROJECT_ROOT / "benchmarks" / "mojo_benchmarks" / "bench_color_check_image.mojo"

WIDTH = 256
HEIGHT = 256
LEVELS = 8
ITERATIONS = 120


def _build_image() -> list[float]:
    image: list[float] = []
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if (x + y) % 16 == 0:
                image.extend((20.0, 20.0, 200.0))
            else:
                image.extend((200.0, 20.0, 20.0))
    return image


def _clamp_rgb255(value: float) -> float:
    return min(255.0, max(0.0, value))


def _srgb_channel_to_linear(channel: float) -> float:
    clamped = min(1.0, max(0.0, channel))
    if clamped <= 0.04045:
        return clamped / 12.92
    return ((clamped + 0.055) / 1.055) ** 2.4


def _rgb_to_luminance_rgb255(r: float, g: float, b: float) -> float:
    return (
        0.2126 * _srgb_channel_to_linear(_clamp_rgb255(r) / 255.0)
        + 0.7152 * _srgb_channel_to_linear(_clamp_rgb255(g) / 255.0)
        + 0.0722 * _srgb_channel_to_linear(_clamp_rgb255(b) / 255.0)
    )


def _contrast_ratio(l1: float, l2: float) -> float:
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _wcag_contrast_ratio_rgb255(
    fg_r: float,
    fg_g: float,
    fg_b: float,
    bg_r: float,
    bg_g: float,
    bg_b: float,
) -> float:
    return _contrast_ratio(
        _rgb_to_luminance_rgb255(fg_r, fg_g, fg_b),
        _rgb_to_luminance_rgb255(bg_r, bg_g, bg_b),
    )


def _channel_bin(value: float, bins: int, bin_width: float) -> int:
    bucket = int(_clamp_rgb255(value) / bin_width)
    if bucket < 0:
        return 0
    if bucket >= bins:
        return bins - 1
    return bucket


def _dominant_bin_index(r: float, g: float, b: float, bins: int, bin_width: float) -> int:
    rb = _channel_bin(r, bins, bin_width)
    gb = _channel_bin(g, bins, bin_width)
    bb = _channel_bin(b, bins, bin_width)
    return (rb * bins + gb) * bins + bb


def dominant_background_rgb255_py(
    flat_rgb: list[float],
    width: int,
    height: int,
    levels: int,
) -> list[float]:
    bins = max(levels, 1)
    hist = [0] * (bins * bins * bins)
    bin_width = 256.0 / float(bins)
    target_pixels = max(width * height, 0)

    valid_pixels = 0
    for pixel_index in range(target_pixels):
        base = pixel_index * 3
        if base + 2 >= len(flat_rgb):
            break
        hist[_dominant_bin_index(flat_rgb[base], flat_rgb[base + 1], flat_rgb[base + 2], bins, bin_width)] += 1
        valid_pixels += 1

    if valid_pixels == 0:
        return [0.0, 0.0, 0.0, 0.0]

    best_bin = 0
    best_count = hist[0]
    for index, count in enumerate(hist[1:], start=1):
        if count > best_count:
            best_bin = index
            best_count = count

    sum_r = 0.0
    sum_g = 0.0
    sum_b = 0.0
    for pixel_index in range(target_pixels):
        base = pixel_index * 3
        if base + 2 >= len(flat_rgb):
            break
        r = _clamp_rgb255(flat_rgb[base])
        g = _clamp_rgb255(flat_rgb[base + 1])
        b = _clamp_rgb255(flat_rgb[base + 2])
        if _dominant_bin_index(r, g, b, bins, bin_width) == best_bin:
            sum_r += r
            sum_g += g
            sum_b += b

    return [
        sum_r / float(best_count),
        sum_g / float(best_count),
        sum_b / float(best_count),
        float(best_count) / float(valid_pixels),
    ]


def preferred_text_contrast_for_image_py(
    flat_rgb: list[float],
    width: int,
    height: int,
    levels: int,
) -> float:
    bg_r, bg_g, bg_b, _ = dominant_background_rgb255_py(flat_rgb, width, height, levels)
    black = _wcag_contrast_ratio_rgb255(0.0, 0.0, 0.0, bg_r, bg_g, bg_b)
    white = _wcag_contrast_ratio_rgb255(255.0, 255.0, 255.0, bg_r, bg_g, bg_b)
    return black if black >= white else white


def preferred_text_color_for_image_py(
    flat_rgb: list[float],
    width: int,
    height: int,
    levels: int,
) -> str:
    bg_r, bg_g, bg_b, _ = dominant_background_rgb255_py(flat_rgb, width, height, levels)
    black = _wcag_contrast_ratio_rgb255(0.0, 0.0, 0.0, bg_r, bg_g, bg_b)
    white = _wcag_contrast_ratio_rgb255(255.0, 255.0, 255.0, bg_r, bg_g, bg_b)
    return "#000000" if black >= white else "#FFFFFF"


def _benchmark_python(
    label: str,
    fn: Any,
    *args: Any,
) -> tuple[Any, float]:
    result = None
    for _ in range(3):
        result = fn(*args)

    start_ns = time.perf_counter_ns()
    checksum = 0.0
    for _ in range(ITERATIONS):
        result = fn(*args)
        if isinstance(result, list):
            checksum += sum(result)
        elif isinstance(result, str):
            checksum += 1.0 if result == "#FFFFFF" else 0.0
        else:
            checksum += float(result)
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
        if parts[:2] == ["MOJO_RESULT", "dominant_background_rgb255"] and len(parts) == 6:
            results["dominant_background_rgb255"] = [float(parts[2]), float(parts[3]), float(parts[4]), float(parts[5])]
            continue
        if parts[:2] == ["MOJO_RESULT", "preferred_text_contrast_for_image"] and len(parts) == 3:
            results["preferred_text_contrast_for_image"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_RESULT", "preferred_text_color_for_image"] and len(parts) == 3:
            results["preferred_text_color_for_image"] = parts[2]
            continue
        if parts[:2] == ["MOJO_BENCH", "dominant_background_rgb255"] and len(parts) >= 3:
            timings["dominant_background_rgb255"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "preferred_text_contrast_for_image"] and len(parts) >= 3:
            timings["preferred_text_contrast_for_image"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "preferred_text_color_for_image"] and len(parts) >= 3:
            timings["preferred_text_color_for_image"] = float(parts[2])
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
            "../benchmarks/mojo_benchmarks/bench_color_check_image.mojo",
        ],
        cwd=MOJO_ENV,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Mojo benchmark failed:\nstdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}")
    return _parse_mojo_output(proc.stdout)


def _assert_close_list(actual: list[float], expected: list[float], label: str) -> None:
    if len(actual) != len(expected):
        raise AssertionError(f"{label} length mismatch: {actual!r} vs {expected!r}")
    for index, (actual_value, expected_value) in enumerate(zip(actual, expected, strict=True)):
        if not math.isclose(actual_value, expected_value, rel_tol=1e-9, abs_tol=1e-9):
            raise AssertionError(
                f"{label}[{index}] mismatch: actual={actual_value} expected={expected_value}"
            )


def main() -> int:
    image = _build_image()

    py_bg, py_bg_ns = _benchmark_python(
        "dominant_background_rgb255",
        dominant_background_rgb255_py,
        image,
        WIDTH,
        HEIGHT,
        LEVELS,
    )
    py_contrast, py_contrast_ns = _benchmark_python(
        "preferred_text_contrast_for_image",
        preferred_text_contrast_for_image_py,
        image,
        WIDTH,
        HEIGHT,
        LEVELS,
    )
    py_text, py_text_ns = _benchmark_python(
        "preferred_text_color_for_image",
        preferred_text_color_for_image_py,
        image,
        WIDTH,
        HEIGHT,
        LEVELS,
    )

    mojo_results, mojo_timings = _run_mojo_benchmark()

    _assert_close_list(mojo_results["dominant_background_rgb255"], py_bg, "dominant_background_rgb255")
    if not math.isclose(
        float(mojo_results["preferred_text_contrast_for_image"]),
        float(py_contrast),
        rel_tol=1e-9,
        abs_tol=1e-9,
    ):
        raise AssertionError("preferred_text_contrast_for_image mismatch")
    if mojo_results["preferred_text_color_for_image"] != py_text:
        raise AssertionError("preferred_text_color_for_image mismatch")

    rows = [
        ("dominant_background_rgb255", py_bg_ns, mojo_timings["dominant_background_rgb255"]),
        (
            "preferred_text_contrast_for_image",
            py_contrast_ns,
            mojo_timings["preferred_text_contrast_for_image"],
        ),
        ("preferred_text_color_for_image", py_text_ns, mojo_timings["preferred_text_color_for_image"]),
    ]

    print("Vision color_check direct-compute benchmark")
    print(f"Image: {WIDTH}x{HEIGHT} RGB, levels={LEVELS}, iterations={ITERATIONS}")
    print("")
    print(f"{'Function':36} {'Python ns/call':>16} {'Mojo ns/call':>16} {'Speedup':>10}")
    for name, py_ns, mojo_ns in rows:
        speedup = py_ns / mojo_ns if mojo_ns > 0 else float("inf")
        print(f"{name:36} {py_ns:16.0f} {mojo_ns:16.0f} {speedup:10.2f}x")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
