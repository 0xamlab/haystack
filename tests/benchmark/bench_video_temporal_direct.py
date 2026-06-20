"""
bench_video_temporal_direct.py — compare direct Mojo and Python video temporal kernels.

This stays entirely off the runtime socket path so the timings reflect kernel
compute only. Use the runtime dispatch tests and kernel A-Z suite for interface
proof; use this script for raw video-kernel speed.

Usage:
  ./.venv/bin/python tests/benchmark/bench_video_temporal_direct.py
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
MOJO_BENCH = (
    PROJECT_ROOT / "benchmarks" / "mojo_benchmarks" / "bench_video_temporal_direct.mojo"
)

WIDTH = 96
HEIGHT = 64
FRAMES = 12
CHANNELS = 3
SAMPLE_FRAMES = 6
CUT_THRESHOLD = 0.18
STORYBOARD_MAX_FRAMES = 2
ITERATIONS = 24


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


def _frame_stride(width: int, height: int, channels: int) -> int:
    if width <= 0 or height <= 0 or channels <= 0:
        return 0
    return width * height * channels


def frame_count_from_flat_py(
    flat_frames: list[float], width: int, height: int, channels: int
) -> int:
    stride = _frame_stride(width, height, channels)
    if stride <= 0:
        return 0
    return len(flat_frames) // stride


def _pixel_mean(flat_frames: list[float], base: int, channels: int) -> float:
    return sum(flat_frames[base : base + channels]) / float(channels)


def frame_mean_abs_diff_py(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    frame_a_index: int,
    frame_b_index: int,
) -> float:
    frames = frame_count_from_flat_py(flat_frames, width, height, channels)
    stride = _frame_stride(width, height, channels)
    if (
        frame_a_index < 0
        or frame_b_index < 0
        or frame_a_index >= frames
        or frame_b_index >= frames
        or stride <= 0
    ):
        return 0.0
    pixels = width * height
    if pixels <= 0:
        return 0.0
    base_a = frame_a_index * stride
    base_b = frame_b_index * stride
    total = 0.0
    for pixel_index in range(pixels):
        mean_a = _pixel_mean(flat_frames, base_a + pixel_index * channels, channels)
        mean_b = _pixel_mean(flat_frames, base_b + pixel_index * channels, channels)
        total += abs(mean_a - mean_b)
    return total / float(pixels)


def temporal_mean_abs_diff_py(
    flat_frames: list[float], width: int, height: int, channels: int
) -> float:
    frames = frame_count_from_flat_py(flat_frames, width, height, channels)
    if frames < 2:
        return 0.0
    total = 0.0
    for frame_index in range(1, frames):
        total += frame_mean_abs_diff_py(
            flat_frames,
            width,
            height,
            channels,
            frame_index - 1,
            frame_index,
        )
    return total / float(frames - 1)


def scene_cut_count_py(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    cut_threshold: float,
) -> int:
    frames = frame_count_from_flat_py(flat_frames, width, height, channels)
    if frames < 2:
        return 0
    total = 0
    for frame_index in range(1, frames):
        score = (
            frame_mean_abs_diff_py(
                flat_frames,
                width,
                height,
                channels,
                frame_index - 1,
                frame_index,
            )
            / 255.0
        )
        if score > cut_threshold:
            total += 1
    return total


def scene_change_scores_py(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
) -> list[float]:
    frames = frame_count_from_flat_py(flat_frames, width, height, channels)
    if frames < 2:
        return []
    return [
        frame_mean_abs_diff_py(
            flat_frames,
            width,
            height,
            channels,
            frame_index - 1,
            frame_index,
        )
        / 255.0
        for frame_index in range(1, frames)
    ]


def scene_start_indices_py(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    cut_threshold: float,
) -> list[int]:
    frames = frame_count_from_flat_py(flat_frames, width, height, channels)
    if frames <= 0:
        return []
    starts = [0]
    if frames == 1:
        return starts
    for transition_index, score in enumerate(
        scene_change_scores_py(flat_frames, width, height, channels)
    ):
        if score > cut_threshold:
            starts.append(transition_index + 1)
    return starts


def scene_lengths_frames_py(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    cut_threshold: float,
) -> list[int]:
    frames = frame_count_from_flat_py(flat_frames, width, height, channels)
    if frames <= 0:
        return []
    starts = scene_start_indices_py(flat_frames, width, height, channels, cut_threshold)
    lengths: list[int] = []
    for scene_index, start in enumerate(starts):
        next_start = starts[scene_index + 1] if scene_index + 1 < len(starts) else frames
        lengths.append(next_start - start)
    return lengths


def scene_representative_frames_py(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    cut_threshold: float,
) -> list[int]:
    frames = frame_count_from_flat_py(flat_frames, width, height, channels)
    if frames <= 0:
        return []
    starts = scene_start_indices_py(flat_frames, width, height, channels, cut_threshold)
    reps: list[int] = []
    for scene_index, start in enumerate(starts):
        next_start = starts[scene_index + 1] if scene_index + 1 < len(starts) else frames
        reps.append((start + (next_start - 1)) // 2)
    return reps


def _sample_dense_indices(total: int, target: int) -> list[int]:
    if total <= 0 or target <= 0:
        return []
    if target >= total:
        return list(range(total))
    if target == 1:
        return [0]
    picks: list[int] = []
    last = -1
    for pick in range(target):
        index = (pick * (total - 1)) // (target - 1)
        if index <= last:
            index = last + 1
        if index >= total:
            index = total - 1
        picks.append(index)
        last = index
    return picks


def longest_scene_index_py(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    cut_threshold: float,
) -> int:
    lengths = scene_lengths_frames_py(flat_frames, width, height, channels, cut_threshold)
    if not lengths:
        return -1
    best_index = 0
    best_length = lengths[0]
    for scene_index, length in enumerate(lengths[1:], start=1):
        if length > best_length:
            best_index = scene_index
            best_length = length
    return best_index


def storyboard_frame_indices_py(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    cut_threshold: float,
    max_frames: int,
) -> list[int]:
    if max_frames <= 0:
        return []
    reps = scene_representative_frames_py(
        flat_frames, width, height, channels, cut_threshold
    )
    if not reps:
        return []
    if max_frames >= len(reps):
        return reps
    if max_frames == 1:
        best_scene = longest_scene_index_py(
            flat_frames, width, height, channels, cut_threshold
        )
        return [reps[best_scene]] if best_scene >= 0 else []
    return [reps[index] for index in _sample_dense_indices(len(reps), max_frames)]


def sample_frame_indices_py(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    target_frames: int,
) -> list[int]:
    frames = frame_count_from_flat_py(flat_frames, width, height, channels)
    if frames <= 0 or target_frames <= 0:
        return []
    if target_frames >= frames or target_frames == 1:
        if target_frames == 1:
            return [0]
        return list(range(frames))

    picks: list[int] = []
    last = -1
    for pick in range(target_frames):
        index = (pick * (frames - 1)) // (target_frames - 1)
        if index <= last:
            index = last + 1
        if index >= frames:
            index = frames - 1
        picks.append(index)
        last = index
    return picks


def _extract_frame_gray_flat(
    flat_frames: list[float], width: int, height: int, channels: int, frame_index: int
) -> list[float]:
    frames = frame_count_from_flat_py(flat_frames, width, height, channels)
    stride = _frame_stride(width, height, channels)
    if frame_index < 0 or frame_index >= frames or stride <= 0:
        return []
    base = frame_index * stride
    out: list[float] = []
    for pixel_index in range(width * height):
        pixel_base = base + pixel_index * channels
        out.append(_pixel_mean(flat_frames, pixel_base, channels))
    return out


def _reshape_to_grid(flat: list[float], width: int, height: int) -> list[list[float]]:
    if width <= 0 or height <= 0:
        return []
    result: list[list[float]] = []
    count = len(flat)
    for row_index in range(height):
        row: list[float] = []
        for col_index in range(width):
            index = row_index * width + col_index
            row.append(flat[index] if index < count else 0.0)
        result.append(row)
    return result


def _convolve_2d_valid(image: list[list[float]], kernel: list[list[float]]) -> list[list[float]]:
    image_height = len(image)
    image_width = len(image[0])
    kernel_height = len(kernel)
    kernel_width = len(kernel[0])
    output_height = image_height - kernel_height + 1
    output_width = image_width - kernel_width + 1
    result: list[list[float]] = []
    for row_index in range(output_height):
        row: list[float] = []
        for col_index in range(output_width):
            total = 0.0
            for kernel_row in range(kernel_height):
                for kernel_col in range(kernel_width):
                    total += (
                        image[row_index + kernel_row][col_index + kernel_col]
                        * kernel[kernel_row][kernel_col]
                    )
            row.append(total)
        result.append(row)
    return result


def _histogram(image: list[list[float]], bins: int) -> list[int]:
    histogram = [0] * bins
    bin_width = 256.0 / float(bins)
    for row in image:
        for value in row:
            index = int(value / bin_width)
            if index >= bins:
                index = bins - 1
            if index < 0:
                index = 0
            histogram[index] += 1
    return histogram


def _mean_pixel(image: list[list[float]]) -> float:
    total = 0.0
    count = 0
    for row in image:
        for value in row:
            total += value
            count += 1
    if count == 0:
        return 0.0
    return total / float(count)


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _laplacian_kernel() -> list[list[float]]:
    return [
        [0.0, 1.0, 0.0],
        [1.0, -4.0, 1.0],
        [0.0, 1.0, 0.0],
    ]


def _blur_score(image: list[list[float]]) -> float:
    laplacian = _convolve_2d_valid(image, _laplacian_kernel())
    total = 0.0
    count = 0
    for row in laplacian:
        for value in row:
            total += value
            count += 1
    if count == 0:
        return 0.0
    mean = total / float(count)
    variance_total = 0.0
    for row in laplacian:
        for value in row:
            diff = value - mean
            variance_total += diff * diff
    return variance_total / float(count)


def _shannon_entropy(image: list[list[float]]) -> float:
    bins = _histogram(image, 256)
    total = sum(bins)
    if total == 0:
        return 0.0
    ln2 = math.log(2.0)
    entropy = 0.0
    for count in bins:
        if count > 0:
            probability = float(count) / float(total)
            entropy -= probability * (math.log(probability) / ln2)
    return entropy


def _quality_score(image: list[list[float]]) -> float:
    brightness = _mean_pixel(image)
    exposure = 1.0 - abs(brightness - 128.0) / 128.0
    entropy = _shannon_entropy(image) / 8.0
    blur = _blur_score(image)
    sharpness = blur / (blur + 100.0)
    return _clamp01(0.4 * sharpness + 0.3 * exposure + 0.3 * entropy)


def frame_quality_series_py(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    sample_frames: int,
) -> list[float]:
    qualities: list[float] = []
    for frame_index in sample_frame_indices_py(
        flat_frames, width, height, channels, sample_frames
    ):
        qualities.append(
            _quality_score(
                _reshape_to_grid(
                    _extract_frame_gray_flat(
                        flat_frames, width, height, channels, frame_index
                    ),
                    width,
                    height,
                )
            )
        )
    return qualities


def average_frame_quality_py(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    sample_frames: int,
) -> float:
    qualities = frame_quality_series_py(
        flat_frames, width, height, channels, sample_frames
    )
    if not qualities:
        return 0.0
    return sum(qualities) / float(len(qualities))


def brightness_flicker_score_py(
    flat_frames: list[float], width: int, height: int, channels: int
) -> float:
    frames = frame_count_from_flat_py(flat_frames, width, height, channels)
    if frames < 2:
        return 0.0
    means: list[float] = []
    for frame_index in range(frames):
        frame_base = frame_index * _frame_stride(width, height, channels)
        total = 0.0
        for pixel_index in range(width * height):
            total += _pixel_mean(flat_frames, frame_base + pixel_index * channels, channels)
        means.append(total / float(width * height))
    return sum(
        abs(means[index] - means[index - 1]) for index in range(1, len(means))
    ) / float(len(means) - 1)


def temporal_stability_score_py(
    flat_frames: list[float], width: int, height: int, channels: int
) -> float:
    flicker = brightness_flicker_score_py(flat_frames, width, height, channels)
    return _clamp01(1.0 / (1.0 + flicker / 48.0))


def video_quality_score_py(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    sample_frames: int,
) -> float:
    frames = frame_count_from_flat_py(flat_frames, width, height, channels)
    if frames <= 0:
        return 0.0
    frame_quality = average_frame_quality_py(
        flat_frames, width, height, channels, sample_frames
    )
    stability = temporal_stability_score_py(flat_frames, width, height, channels)
    coverage = 1.0 if frames > 1 else 0.7
    return _clamp01(0.7 * frame_quality + 0.2 * stability + 0.1 * coverage)


def _result_checksum(result: Any) -> float:
    if isinstance(result, list):
        return sum(_result_checksum(item) for item in result)
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


def _parse_int_list_token(token: str) -> list[int]:
    if token == "empty":
        return []
    return [int(part) for part in token.split(",") if part]


def _parse_mojo_output(stdout: str) -> tuple[dict[str, Any], dict[str, float]]:
    results: dict[str, Any] = {}
    timings: dict[str, float] = {}
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if parts[:2] == ["MOJO_RESULT", "temporal_mean_abs_diff"] and len(parts) == 3:
            results["temporal_mean_abs_diff"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_RESULT", "scene_cut_count"] and len(parts) == 3:
            results["scene_cut_count"] = int(parts[2])
            continue
        if parts[:2] == ["MOJO_RESULT", "video_quality_score"] and len(parts) == 3:
            results["video_quality_score"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_RESULT", "longest_scene_index"] and len(parts) == 3:
            results["longest_scene_index"] = int(parts[2])
            continue
        if parts[:2] == ["MOJO_RESULT", "storyboard_frame_indices"] and len(parts) == 3:
            results["storyboard_frame_indices"] = _parse_int_list_token(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "temporal_mean_abs_diff"] and len(parts) >= 3:
            timings["temporal_mean_abs_diff"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "scene_cut_count"] and len(parts) >= 3:
            timings["scene_cut_count"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "video_quality_score"] and len(parts) >= 3:
            timings["video_quality_score"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "longest_scene_index"] and len(parts) >= 3:
            timings["longest_scene_index"] = float(parts[2])
            continue
        if parts[:2] == ["MOJO_BENCH", "storyboard_frame_indices"] and len(parts) >= 3:
            timings["storyboard_frame_indices"] = float(parts[2])
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
            "../benchmarks/mojo_benchmarks/bench_video_temporal_direct.mojo",
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


def main() -> None:
    clip = _build_clip()

    py_temporal, py_temporal_ns = _benchmark_python(
        "temporal_mean_abs_diff",
        temporal_mean_abs_diff_py,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
    )
    py_cuts, py_cuts_ns = _benchmark_python(
        "scene_cut_count",
        scene_cut_count_py,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        CUT_THRESHOLD,
    )
    py_quality, py_quality_ns = _benchmark_python(
        "video_quality_score",
        video_quality_score_py,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        SAMPLE_FRAMES,
    )
    py_longest, py_longest_ns = _benchmark_python(
        "longest_scene_index",
        longest_scene_index_py,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        CUT_THRESHOLD,
    )
    py_storyboard, py_storyboard_ns = _benchmark_python(
        "storyboard_frame_indices",
        storyboard_frame_indices_py,
        clip,
        WIDTH,
        HEIGHT,
        CHANNELS,
        CUT_THRESHOLD,
        STORYBOARD_MAX_FRAMES,
    )

    mojo_results, mojo_timings = _run_mojo_benchmark()

    _assert_close(mojo_results["temporal_mean_abs_diff"], py_temporal, "temporal_mean_abs_diff")
    if mojo_results["scene_cut_count"] != py_cuts:
        raise AssertionError(
            f"scene_cut_count mismatch: {mojo_results['scene_cut_count']} vs {py_cuts}"
        )
    _assert_close(mojo_results["video_quality_score"], py_quality, "video_quality_score")
    if mojo_results["longest_scene_index"] != py_longest:
        raise AssertionError(
            f"longest_scene_index mismatch: {mojo_results['longest_scene_index']} vs {py_longest}"
        )
    if mojo_results["storyboard_frame_indices"] != py_storyboard:
        raise AssertionError(
            "storyboard_frame_indices mismatch: "
            f"{mojo_results['storyboard_frame_indices']} vs {py_storyboard}"
        )

    speedups = {
        "temporal_mean_abs_diff": py_temporal_ns / mojo_timings["temporal_mean_abs_diff"],
        "scene_cut_count": py_cuts_ns / mojo_timings["scene_cut_count"],
        "video_quality_score": py_quality_ns / mojo_timings["video_quality_score"],
        "longest_scene_index": py_longest_ns / mojo_timings["longest_scene_index"],
        "storyboard_frame_indices": py_storyboard_ns
        / mojo_timings["storyboard_frame_indices"],
    }

    print(
        "RESULT temporal_mean_abs_diff",
        py_temporal,
        mojo_timings["temporal_mean_abs_diff"],
        py_temporal_ns,
        speedups["temporal_mean_abs_diff"],
    )
    print(
        "RESULT scene_cut_count",
        py_cuts,
        mojo_timings["scene_cut_count"],
        py_cuts_ns,
        speedups["scene_cut_count"],
    )
    print(
        "RESULT video_quality_score",
        py_quality,
        mojo_timings["video_quality_score"],
        py_quality_ns,
        speedups["video_quality_score"],
    )
    print(
        "RESULT longest_scene_index",
        py_longest,
        mojo_timings["longest_scene_index"],
        py_longest_ns,
        speedups["longest_scene_index"],
    )
    print(
        "RESULT storyboard_frame_indices",
        py_storyboard,
        mojo_timings["storyboard_frame_indices"],
        py_storyboard_ns,
        speedups["storyboard_frame_indices"],
    )


if __name__ == "__main__":
    main()
