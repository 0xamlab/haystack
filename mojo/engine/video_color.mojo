"""
video_color.mojo — Deterministic color-analysis helpers for flat video frame buffers.

Complements `color_science` and `image_palette` with clip-level color features
for video preview selection, overlay readability, and creative review while
staying fully inside the pure-Mojo lane.

Public API:
  frame_mean_rgb255               — mean RGB of one frame as [r, g, b]
  frame_mean_rgb_series           — mean RGB for every frame as [r, g, b] repeated
  clip_mean_rgb255                — mean RGB across the full clip
  dominant_clip_color_rgb255      — dominant quantized clip color as [r, g, b, weight]
  clip_mean_saturation_rgb255     — mean HSV saturation across all clip pixels
  warm_frame_ratio_rgb255         — fraction of frames whose mean color is warm
  color_drift_score_rgb255        — normalized consecutive-frame RGB drift in [0, 1]
  preferred_text_contrast_for_video — best black/white WCAG contrast for the clip
  preferred_text_color_for_video  — "#000000" or "#FFFFFF" for clip overlays
"""
from std.math import sqrt

from color import RGB, rgb_to_hsv
from color_science import contrast_ratio, rgb_to_luminance
from video_ops import frame_count_from_flat, sample_frame_indices


def _clamp01(v: Float64) -> Float64:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _clamp_rgb255(v: Float64) -> Float64:
    if v < 0.0:
        return 0.0
    if v > 255.0:
        return 255.0
    return v


def _frame_stride(width: Int, height: Int, channels: Int) -> Int:
    if width <= 0 or height <= 0 or channels <= 0:
        return 0
    return width * height * channels


def _append_rgb255(mut out: List[Float64], r: Float64, g: Float64, b: Float64):
    out.append(r)
    out.append(g)
    out.append(b)


def _frame_mean_rgb_internal(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, frame_index: Int,
) -> List[Float64]:
    var out = List[Float64]()
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    var stride = _frame_stride(width, height, channels)
    if frame_index < 0 or frame_index >= frames or stride <= 0:
        _append_rgb255(out, 0.0, 0.0, 0.0)
        return out^

    var pixels = width * height
    if pixels <= 0:
        _append_rgb255(out, 0.0, 0.0, 0.0)
        return out^

    var base = frame_index * stride
    var total_r: Float64 = 0.0
    var total_g: Float64 = 0.0
    var total_b: Float64 = 0.0
    for pixel_index in range(pixels):
        var pixel_base = base + pixel_index * channels
        var r = _clamp_rgb255(flat_frames[pixel_base])
        var g = r
        var b = r
        if channels >= 2:
            g = _clamp_rgb255(flat_frames[pixel_base + 1])
            b = g
        if channels >= 3:
            b = _clamp_rgb255(flat_frames[pixel_base + 2])
        total_r += r
        total_g += g
        total_b += b
    _append_rgb255(
        out,
        total_r / Float64(pixels),
        total_g / Float64(pixels),
        total_b / Float64(pixels),
    )
    return out^


def _bin_index(r: Float64, g: Float64, b: Float64, bins: Int, bin_width: Float64) -> Int:
    var rb = Int(_clamp_rgb255(r) / bin_width)
    var gb = Int(_clamp_rgb255(g) / bin_width)
    var bb = Int(_clamp_rgb255(b) / bin_width)
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


def _clip_palette_stats(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, levels: Int, sample_frames_n: Int,
) -> List[Float64]:
    var bins = levels
    if bins <= 0:
        bins = 1

    var total_bins = bins * bins * bins
    var stats = List[Float64]()
    for _ in range(total_bins * 4):
        stats.append(0.0)

    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    var stride = _frame_stride(width, height, channels)
    var pixels = width * height
    if frames <= 0 or stride <= 0 or pixels <= 0:
        stats.append(0.0)
        return stats^

    var target_frames = sample_frames_n
    if target_frames <= 0 or target_frames > frames:
        target_frames = frames
    var picks = sample_frame_indices(flat_frames, width, height, channels, target_frames)

    var bin_width = 256.0 / Float64(bins)
    var valid_pixels = 0
    for pick_index in range(len(picks)):
        var frame_base = picks[pick_index] * stride
        for pixel_index in range(pixels):
            var pixel_base = frame_base + pixel_index * channels
            var r = _clamp_rgb255(flat_frames[pixel_base])
            var g = r
            var b = r
            if channels >= 2:
                g = _clamp_rgb255(flat_frames[pixel_base + 1])
                b = g
            if channels >= 3:
                b = _clamp_rgb255(flat_frames[pixel_base + 2])
            var offset = _bin_index(r, g, b, bins, bin_width) * 4
            stats[offset] += 1.0
            stats[offset + 1] += r
            stats[offset + 2] += g
            stats[offset + 3] += b
            valid_pixels += 1
    stats.append(Float64(valid_pixels))
    return stats^


def _clip_mean_rgb_components(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int
) -> List[Float64]:
    var out = List[Float64]()
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    var stride = _frame_stride(width, height, channels)
    var pixels = width * height
    if frames <= 0 or stride <= 0 or pixels <= 0:
        _append_rgb255(out, 0.0, 0.0, 0.0)
        return out^

    var total_r: Float64 = 0.0
    var total_g: Float64 = 0.0
    var total_b: Float64 = 0.0
    var valid_pixels = 0
    for frame_index in range(frames):
        var frame_base = frame_index * stride
        for pixel_index in range(pixels):
            var pixel_base = frame_base + pixel_index * channels
            var r = _clamp_rgb255(flat_frames[pixel_base])
            var g = r
            var b = r
            if channels >= 2:
                g = _clamp_rgb255(flat_frames[pixel_base + 1])
                b = g
            if channels >= 3:
                b = _clamp_rgb255(flat_frames[pixel_base + 2])
            total_r += r
            total_g += g
            total_b += b
            valid_pixels += 1
    if valid_pixels <= 0:
        _append_rgb255(out, 0.0, 0.0, 0.0)
        return out^
    _append_rgb255(
        out,
        total_r / Float64(valid_pixels),
        total_g / Float64(valid_pixels),
        total_b / Float64(valid_pixels),
    )
    return out^


def frame_mean_rgb255(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, frame_index: Int,
) -> List[Float64]:
    """Mean RGB of one frame as [r, g, b]; out-of-range frames return zeros."""
    return _frame_mean_rgb_internal(flat_frames, width, height, channels, frame_index)


def frame_mean_rgb_series(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int
) -> List[Float64]:
    """Frame mean RGB values as [r, g, b] repeated once per frame."""
    var out = List[Float64]()
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    for frame_index in range(frames):
        var mean_rgb = _frame_mean_rgb_internal(flat_frames, width, height, channels, frame_index)
        _append_rgb255(out, mean_rgb[0], mean_rgb[1], mean_rgb[2])
    return out^


def clip_mean_rgb255(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int
) -> List[Float64]:
    """Mean RGB across the full clip."""
    return _clip_mean_rgb_components(flat_frames, width, height, channels)


def dominant_clip_color_rgb255(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, levels: Int, sample_frames_n: Int,
) -> List[Float64]:
    """Dominant quantized clip color as [r, g, b, weight] across sampled frames."""
    var out = List[Float64]()
    var stats = _clip_palette_stats(flat_frames, width, height, channels, levels, sample_frames_n)
    var valid_pixels = stats[len(stats) - 1] if len(stats) > 0 else 0.0
    if valid_pixels <= 0.0:
        out.append(0.0); out.append(0.0); out.append(0.0); out.append(0.0)
        return out^

    var total_bins = (len(stats) - 1) // 4
    var best_index = -1
    var best_count: Float64 = 0.0
    for bin_index in range(total_bins):
        var count = stats[bin_index * 4]
        if count > best_count:
            best_count = count
            best_index = bin_index
    if best_index < 0 or best_count <= 0.0:
        out.append(0.0); out.append(0.0); out.append(0.0); out.append(0.0)
        return out^

    var offset = best_index * 4
    out.append(stats[offset + 1] / best_count)
    out.append(stats[offset + 2] / best_count)
    out.append(stats[offset + 3] / best_count)
    out.append(best_count / valid_pixels)
    return out^


def clip_mean_saturation_rgb255(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int
) -> Float64:
    """Mean HSV saturation across every valid clip pixel."""
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    var stride = _frame_stride(width, height, channels)
    var pixels = width * height
    if frames <= 0 or stride <= 0 or pixels <= 0:
        return 0.0

    var total_s: Float64 = 0.0
    var valid_pixels = 0
    for frame_index in range(frames):
        var frame_base = frame_index * stride
        for pixel_index in range(pixels):
            var pixel_base = frame_base + pixel_index * channels
            var r = _clamp_rgb255(flat_frames[pixel_base])
            var g = r
            var b = r
            if channels >= 2:
                g = _clamp_rgb255(flat_frames[pixel_base + 1])
                b = g
            if channels >= 3:
                b = _clamp_rgb255(flat_frames[pixel_base + 2])
            total_s += rgb_to_hsv(RGB(r / 255.0, g / 255.0, b / 255.0)).s
            valid_pixels += 1
    if valid_pixels <= 0:
        return 0.0
    return total_s / Float64(valid_pixels)


def warm_frame_ratio_rgb255(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, min_saturation: Float64,
) -> Float64:
    """Fraction of frames whose mean RGB hue is warm and whose saturation >= min_saturation."""
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames <= 0:
        return 0.0

    var warm = 0
    for frame_index in range(frames):
        var mean_rgb = _frame_mean_rgb_internal(flat_frames, width, height, channels, frame_index)
        var hsv = rgb_to_hsv(
            RGB(mean_rgb[0] / 255.0, mean_rgb[1] / 255.0, mean_rgb[2] / 255.0)
        )
        if hsv.s >= min_saturation and (hsv.h <= 90.0 or hsv.h >= 330.0):
            warm += 1
    return Float64(warm) / Float64(frames)


def color_drift_score_rgb255(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int
) -> Float64:
    """Mean consecutive-frame RGB drift normalized to [0, 1]."""
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames < 2:
        return 0.0

    var prev = _frame_mean_rgb_internal(flat_frames, width, height, channels, 0)
    var total: Float64 = 0.0
    for frame_index in range(1, frames):
        var current = _frame_mean_rgb_internal(flat_frames, width, height, channels, frame_index)
        var dr = prev[0] - current[0]
        var dg = prev[1] - current[1]
        var db = prev[2] - current[2]
        total += sqrt(dr * dr + dg * dg + db * db)
        prev = current^
    var max_distance = 255.0 * sqrt(3.0)
    if max_distance <= 0.0:
        return 0.0
    return _clamp01((total / Float64(frames - 1)) / max_distance)


def preferred_text_contrast_for_video(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, levels: Int, sample_frames_n: Int,
) -> Float64:
    """Best WCAG contrast ratio from black/white against the dominant clip color."""
    var dominant = dominant_clip_color_rgb255(
        flat_frames, width, height, channels, levels, sample_frames_n
    )
    var luminance = rgb_to_luminance(
        dominant[0] / 255.0,
        dominant[1] / 255.0,
        dominant[2] / 255.0,
    )
    var black = contrast_ratio(0.0, luminance)
    var white = contrast_ratio(1.0, luminance)
    return black if black >= white else white


def preferred_text_color_for_video(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, levels: Int, sample_frames_n: Int,
) -> String:
    """Recommended black/white overlay text color for the dominant clip color."""
    var dominant = dominant_clip_color_rgb255(
        flat_frames, width, height, channels, levels, sample_frames_n
    )
    var luminance = rgb_to_luminance(
        dominant[0] / 255.0,
        dominant[1] / 255.0,
        dominant[2] / 255.0,
    )
    var black = contrast_ratio(0.0, luminance)
    var white = contrast_ratio(1.0, luminance)
    return "#000000" if black >= white else "#FFFFFF"
