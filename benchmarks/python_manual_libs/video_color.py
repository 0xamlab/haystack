"""Manual Python reference for video_color.mojo."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


@dataclass(frozen=True)
class RGB:
    r: float
    g: float
    b: float


@dataclass(frozen=True)
class HSV:
    h: float
    s: float
    v: float


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _clamp_rgb255(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 255.0:
        return 255.0
    return value


def _srgb_channel_to_linear(channel: float) -> float:
    clamped = _clamp01(channel)
    if clamped <= 0.04045:
        return clamped / 12.92
    return ((clamped + 0.055) / 1.055) ** 2.4


def rgb_to_luminance(r: float, g: float, b: float) -> float:
    return (
        0.2126 * _srgb_channel_to_linear(r)
        + 0.7152 * _srgb_channel_to_linear(g)
        + 0.0722 * _srgb_channel_to_linear(b)
    )


def contrast_ratio(l1: float, l2: float) -> float:
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def rgb_to_hsv(color: RGB) -> HSV:
    r = color.r
    g = color.g
    b = color.b
    mx = max(r, g, b)
    mn = min(r, g, b)
    v = mx
    delta = mx - mn
    if mx == 0.0:
        return HSV(0.0, 0.0, v)
    s = delta / mx
    if delta == 0.0:
        return HSV(0.0, s, v)
    if mx == r:
        h = (g - b) / delta
        if g < b:
            h += 6.0
    elif mx == g:
        h = (b - r) / delta + 2.0
    else:
        h = (r - g) / delta + 4.0
    return HSV(h * 60.0, s, v)


def _frame_stride(width: int, height: int, channels: int) -> int:
    if width <= 0 or height <= 0 or channels <= 0:
        return 0
    return width * height * channels


def frame_count_from_flat(flat_frames: list[float], width: int, height: int, channels: int) -> int:
    stride = _frame_stride(width, height, channels)
    if stride <= 0:
        return 0
    return len(flat_frames) // stride


def sample_frame_indices(
    flat_frames: list[float], width: int, height: int, channels: int, target_frames: int
) -> list[int]:
    frames = frame_count_from_flat(flat_frames, width, height, channels)
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


def _pixel_rgb255(flat_frames: list[float], base: int, channels: int) -> tuple[float, float, float]:
    r = _clamp_rgb255(flat_frames[base])
    g = r
    b = r
    if channels >= 2:
        g = _clamp_rgb255(flat_frames[base + 1])
        b = g
    if channels >= 3:
        b = _clamp_rgb255(flat_frames[base + 2])
    return r, g, b


def frame_mean_rgb255(
    flat_frames: list[float], width: int, height: int, channels: int, frame_index: int
) -> list[float]:
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    stride = _frame_stride(width, height, channels)
    if frame_index < 0 or frame_index >= frames or stride <= 0:
        return [0.0, 0.0, 0.0]
    pixels = width * height
    if pixels <= 0:
        return [0.0, 0.0, 0.0]

    frame_base = frame_index * stride
    total_r = 0.0
    total_g = 0.0
    total_b = 0.0
    for pixel_index in range(pixels):
        r, g, b = _pixel_rgb255(flat_frames, frame_base + pixel_index * channels, channels)
        total_r += r
        total_g += g
        total_b += b
    return [
        total_r / float(pixels),
        total_g / float(pixels),
        total_b / float(pixels),
    ]


def frame_mean_rgb_series(
    flat_frames: list[float], width: int, height: int, channels: int
) -> list[float]:
    out: list[float] = []
    for frame_index in range(frame_count_from_flat(flat_frames, width, height, channels)):
        out.extend(frame_mean_rgb255(flat_frames, width, height, channels, frame_index))
    return out


def clip_mean_rgb255(
    flat_frames: list[float], width: int, height: int, channels: int
) -> list[float]:
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    stride = _frame_stride(width, height, channels)
    pixels = width * height
    if frames <= 0 or stride <= 0 or pixels <= 0:
        return [0.0, 0.0, 0.0]

    total_r = 0.0
    total_g = 0.0
    total_b = 0.0
    valid_pixels = 0
    for frame_index in range(frames):
        frame_base = frame_index * stride
        for pixel_index in range(pixels):
            r, g, b = _pixel_rgb255(flat_frames, frame_base + pixel_index * channels, channels)
            total_r += r
            total_g += g
            total_b += b
            valid_pixels += 1
    if valid_pixels <= 0:
        return [0.0, 0.0, 0.0]
    return [
        total_r / float(valid_pixels),
        total_g / float(valid_pixels),
        total_b / float(valid_pixels),
    ]


def _bin_index(r: float, g: float, b: float, bins: int, bin_width: float) -> int:
    rb = int(_clamp_rgb255(r) / bin_width)
    gb = int(_clamp_rgb255(g) / bin_width)
    bb = int(_clamp_rgb255(b) / bin_width)
    if rb < 0:
        rb = 0
    if gb < 0:
        gb = 0
    if bb < 0:
        bb = 0
    if rb >= bins:
        rb = bins - 1
    if gb >= bins:
        gb = bins - 1
    if bb >= bins:
        bb = bins - 1
    return (rb * bins + gb) * bins + bb


def dominant_clip_color_rgb255(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    levels: int,
    sample_frames_n: int,
) -> list[float]:
    bins = levels if levels > 0 else 1
    total_bins = bins * bins * bins
    stats = [0.0] * (total_bins * 4)

    frames = frame_count_from_flat(flat_frames, width, height, channels)
    stride = _frame_stride(width, height, channels)
    pixels = width * height
    if frames <= 0 or stride <= 0 or pixels <= 0:
        return [0.0, 0.0, 0.0, 0.0]

    target_frames = sample_frames_n
    if target_frames <= 0 or target_frames > frames:
        target_frames = frames
    picks = sample_frame_indices(flat_frames, width, height, channels, target_frames)
    bin_width = 256.0 / float(bins)
    valid_pixels = 0

    for frame_index in picks:
        frame_base = frame_index * stride
        for pixel_index in range(pixels):
            r, g, b = _pixel_rgb255(flat_frames, frame_base + pixel_index * channels, channels)
            offset = _bin_index(r, g, b, bins, bin_width) * 4
            stats[offset] += 1.0
            stats[offset + 1] += r
            stats[offset + 2] += g
            stats[offset + 3] += b
            valid_pixels += 1

    if valid_pixels <= 0:
        return [0.0, 0.0, 0.0, 0.0]

    best_index = -1
    best_count = 0.0
    for bin_index in range(total_bins):
        count = stats[bin_index * 4]
        if count > best_count:
            best_index = bin_index
            best_count = count
    if best_index < 0 or best_count <= 0.0:
        return [0.0, 0.0, 0.0, 0.0]

    offset = best_index * 4
    return [
        stats[offset + 1] / best_count,
        stats[offset + 2] / best_count,
        stats[offset + 3] / best_count,
        best_count / float(valid_pixels),
    ]


def clip_mean_saturation_rgb255(
    flat_frames: list[float], width: int, height: int, channels: int
) -> float:
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    stride = _frame_stride(width, height, channels)
    pixels = width * height
    if frames <= 0 or stride <= 0 or pixels <= 0:
        return 0.0

    total_s = 0.0
    valid_pixels = 0
    for frame_index in range(frames):
        frame_base = frame_index * stride
        for pixel_index in range(pixels):
            r, g, b = _pixel_rgb255(flat_frames, frame_base + pixel_index * channels, channels)
            total_s += rgb_to_hsv(RGB(r / 255.0, g / 255.0, b / 255.0)).s
            valid_pixels += 1
    if valid_pixels <= 0:
        return 0.0
    return total_s / float(valid_pixels)


def warm_frame_ratio_rgb255(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    min_saturation: float,
) -> float:
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames <= 0:
        return 0.0

    warm = 0
    for frame_index in range(frames):
        mean_rgb = frame_mean_rgb255(flat_frames, width, height, channels, frame_index)
        hsv = rgb_to_hsv(RGB(mean_rgb[0] / 255.0, mean_rgb[1] / 255.0, mean_rgb[2] / 255.0))
        if hsv.s >= min_saturation and (hsv.h <= 90.0 or hsv.h >= 330.0):
            warm += 1
    return float(warm) / float(frames)


def color_drift_score_rgb255(
    flat_frames: list[float], width: int, height: int, channels: int
) -> float:
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames < 2:
        return 0.0

    previous = frame_mean_rgb255(flat_frames, width, height, channels, 0)
    total = 0.0
    for frame_index in range(1, frames):
        current = frame_mean_rgb255(flat_frames, width, height, channels, frame_index)
        total += sqrt(
            (previous[0] - current[0]) ** 2
            + (previous[1] - current[1]) ** 2
            + (previous[2] - current[2]) ** 2
        )
        previous = current
    max_distance = 255.0 * sqrt(3.0)
    if max_distance <= 0.0:
        return 0.0
    return _clamp01((total / float(frames - 1)) / max_distance)


def preferred_text_contrast_for_video(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    levels: int,
    sample_frames_n: int,
) -> float:
    dominant = dominant_clip_color_rgb255(
        flat_frames, width, height, channels, levels, sample_frames_n
    )
    luminance = rgb_to_luminance(
        dominant[0] / 255.0,
        dominant[1] / 255.0,
        dominant[2] / 255.0,
    )
    black = contrast_ratio(0.0, luminance)
    white = contrast_ratio(1.0, luminance)
    return black if black >= white else white


def preferred_text_color_for_video(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    levels: int,
    sample_frames_n: int,
) -> str:
    dominant = dominant_clip_color_rgb255(
        flat_frames, width, height, channels, levels, sample_frames_n
    )
    luminance = rgb_to_luminance(
        dominant[0] / 255.0,
        dominant[1] / 255.0,
        dominant[2] / 255.0,
    )
    black = contrast_ratio(0.0, luminance)
    white = contrast_ratio(1.0, luminance)
    return "#000000" if black >= white else "#FFFFFF"
