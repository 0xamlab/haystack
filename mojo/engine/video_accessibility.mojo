"""
video_accessibility.mojo — Deterministic WCAG-style text safety for video frames and subtitle bands.

This module focuses on conservative overlay-readability checks for mixed video
backgrounds. Unlike mean-colour heuristics, it evaluates the minimum contrast
achieved by a single global black/white text colour across all pixels in a
frame or subtitle band. That lets the engine detect when a backplate is needed
because bright and dark regions coexist behind the same caption.

Public API:
  frame_min_preferred_text_contrast_for_video — best worst-case black/white contrast for one frame
  frame_preferred_text_color_for_video        — "#000000" or "#FFFFFF" for one frame
  sampled_video_min_text_contrast             — minimum preferred contrast across sampled frames
  sampled_video_wcag_safe_ratio               — sampled frame pass ratio for WCAG AA
  needs_text_backplate_for_video              — whether any sampled frame needs a backplate
  subtitle_band_min_preferred_text_contrast_for_video — best worst-case contrast for sampled subtitle bands
  subtitle_band_preferred_text_color_for_video        — recommended black/white subtitle colour
  sampled_subtitle_band_wcag_safe_ratio       — sampled subtitle-band pass ratio for WCAG AA
  subtitle_band_needs_backplate_for_video     — whether sampled subtitle bands need a backplate
"""
from color_check import wcag_aa_required_contrast
from color_science import contrast_ratio, rgb_to_luminance
from video_ops import frame_count_from_flat, sample_frame_indices


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


def _pixel_luminance(flat_frames: List[Float64], base: Int, channels: Int) -> Float64:
    var r = _clamp_rgb255(flat_frames[base]) / 255.0
    var g = r
    var b = r
    if channels >= 2:
        g = _clamp_rgb255(flat_frames[base + 1]) / 255.0
        b = g
    if channels >= 3:
        b = _clamp_rgb255(flat_frames[base + 2]) / 255.0
    return rgb_to_luminance(r, g, b)


def _best_contrast_from_minima(min_black: Float64, min_white: Float64) -> Float64:
    return min_black if min_black >= min_white else min_white


def _best_text_color_from_minima(min_black: Float64, min_white: Float64) -> String:
    return "#000000" if min_black >= min_white else "#FFFFFF"


def _region_text_contrast_minima(
    flat_frames: List[Float64],
    width: Int,
    height: Int,
    channels: Int,
    frame_index: Int,
    row_start: Int,
    row_end: Int,
) -> List[Float64]:
    var out = List[Float64]()
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    var stride = _frame_stride(width, height, channels)
    if frame_index < 0 or frame_index >= frames or stride <= 0:
        out.append(0.0)
        out.append(0.0)
        return out^

    var effective_row_start = row_start
    if effective_row_start < 0:
        effective_row_start = 0
    var effective_row_end = row_end
    if effective_row_end > height:
        effective_row_end = height
    if effective_row_start >= effective_row_end or width <= 0:
        out.append(0.0)
        out.append(0.0)
        return out^

    var frame_base = frame_index * stride
    var min_black = Float64(1e9)
    var min_white = Float64(1e9)
    var valid_pixels = 0
    for y in range(effective_row_start, effective_row_end):
        var row_base = frame_base + y * width * channels
        for x in range(width):
            var luminance = _pixel_luminance(flat_frames, row_base + x * channels, channels)
            var black_contrast = contrast_ratio(0.0, luminance)
            var white_contrast = contrast_ratio(1.0, luminance)
            if black_contrast < min_black:
                min_black = black_contrast
            if white_contrast < min_white:
                min_white = white_contrast
            valid_pixels += 1
    if valid_pixels == 0:
        out.append(0.0)
        out.append(0.0)
        return out^

    out.append(min_black)
    out.append(min_white)
    return out^


def _frame_preferred_contrast(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, frame_index: Int
) -> Float64:
    var minima = _region_text_contrast_minima(
        flat_frames,
        width,
        height,
        channels,
        frame_index,
        0,
        height,
    )
    return _best_contrast_from_minima(minima[0], minima[1])


def _frame_preferred_text_color(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, frame_index: Int
) -> String:
    var minima = _region_text_contrast_minima(
        flat_frames,
        width,
        height,
        channels,
        frame_index,
        0,
        height,
    )
    return _best_text_color_from_minima(minima[0], minima[1])


def _sampled_frame_indices(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, sample_frames_n: Int
) -> List[Int]:
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames <= 0:
        return List[Int]()
    var target = sample_frames_n
    if target <= 0 or target > frames:
        target = frames
    return sample_frame_indices(flat_frames, width, height, channels, target)


def _band_row_start(height: Int, band_rows: Int) -> Int:
    if height <= 0 or band_rows <= 0:
        return -1
    var rows = band_rows
    if rows > height:
        rows = height
    return height - rows


def frame_min_preferred_text_contrast_for_video(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, frame_index: Int,
) -> Float64:
    """Best worst-case black/white contrast for one frame."""
    return _frame_preferred_contrast(flat_frames, width, height, channels, frame_index)


def frame_preferred_text_color_for_video(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, frame_index: Int,
) -> String:
    """Single black/white text colour that maximizes the frame's minimum pixel contrast."""
    return _frame_preferred_text_color(flat_frames, width, height, channels, frame_index)


def sampled_video_min_text_contrast(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, sample_frames_n: Int,
) -> Float64:
    """Minimum preferred frame contrast across evenly sampled frames."""
    var picks = _sampled_frame_indices(flat_frames, width, height, channels, sample_frames_n)
    if len(picks) == 0:
        return 0.0
    var best_min = Float64(1e9)
    for pick_index in range(len(picks)):
        var frame_contrast = _frame_preferred_contrast(
            flat_frames,
            width,
            height,
            channels,
            picks[pick_index],
        )
        if frame_contrast < best_min:
            best_min = frame_contrast
    return best_min


def sampled_video_wcag_safe_ratio(
    flat_frames: List[Float64],
    width: Int,
    height: Int,
    channels: Int,
    sample_frames_n: Int,
    font_size_pt: Float64,
    is_bold: Bool,
) -> Float64:
    """Fraction of sampled frames whose preferred contrast meets WCAG AA."""
    var picks = _sampled_frame_indices(flat_frames, width, height, channels, sample_frames_n)
    if len(picks) == 0:
        return 0.0
    var threshold = wcag_aa_required_contrast(font_size_pt, is_bold)
    var safe = 0
    for pick_index in range(len(picks)):
        if (
            _frame_preferred_contrast(
                flat_frames,
                width,
                height,
                channels,
                picks[pick_index],
            )
            >= threshold
        ):
            safe += 1
    return Float64(safe) / Float64(len(picks))


def needs_text_backplate_for_video(
    flat_frames: List[Float64],
    width: Int,
    height: Int,
    channels: Int,
    sample_frames_n: Int,
    font_size_pt: Float64,
    is_bold: Bool,
) -> Bool:
    """True when any sampled frame falls below the WCAG AA threshold."""
    return sampled_video_wcag_safe_ratio(
        flat_frames,
        width,
        height,
        channels,
        sample_frames_n,
        font_size_pt,
        is_bold,
    ) < 1.0


def subtitle_band_min_preferred_text_contrast_for_video(
    flat_frames: List[Float64],
    width: Int,
    height: Int,
    channels: Int,
    sample_frames_n: Int,
    band_rows: Int,
) -> Float64:
    """Best worst-case black/white contrast across sampled bottom subtitle bands."""
    var row_start = _band_row_start(height, band_rows)
    if row_start < 0:
        return 0.0
    var picks = _sampled_frame_indices(flat_frames, width, height, channels, sample_frames_n)
    if len(picks) == 0:
        return 0.0
    var min_black = Float64(1e9)
    var min_white = Float64(1e9)
    for pick_index in range(len(picks)):
        var minima = _region_text_contrast_minima(
            flat_frames,
            width,
            height,
            channels,
            picks[pick_index],
            row_start,
            height,
        )
        if minima[0] < min_black:
            min_black = minima[0]
        if minima[1] < min_white:
            min_white = minima[1]
    return _best_contrast_from_minima(min_black, min_white)


def subtitle_band_preferred_text_color_for_video(
    flat_frames: List[Float64],
    width: Int,
    height: Int,
    channels: Int,
    sample_frames_n: Int,
    band_rows: Int,
) -> String:
    """Single black/white subtitle colour maximizing worst-case sampled band contrast."""
    var row_start = _band_row_start(height, band_rows)
    if row_start < 0:
        return "#000000"
    var picks = _sampled_frame_indices(flat_frames, width, height, channels, sample_frames_n)
    if len(picks) == 0:
        return "#000000"
    var min_black = Float64(1e9)
    var min_white = Float64(1e9)
    for pick_index in range(len(picks)):
        var minima = _region_text_contrast_minima(
            flat_frames,
            width,
            height,
            channels,
            picks[pick_index],
            row_start,
            height,
        )
        if minima[0] < min_black:
            min_black = minima[0]
        if minima[1] < min_white:
            min_white = minima[1]
    return _best_text_color_from_minima(min_black, min_white)


def sampled_subtitle_band_wcag_safe_ratio(
    flat_frames: List[Float64],
    width: Int,
    height: Int,
    channels: Int,
    sample_frames_n: Int,
    band_rows: Int,
    font_size_pt: Float64,
    is_bold: Bool,
) -> Float64:
    """Fraction of sampled subtitle bands whose preferred contrast meets WCAG AA."""
    var row_start = _band_row_start(height, band_rows)
    if row_start < 0:
        return 0.0
    var picks = _sampled_frame_indices(flat_frames, width, height, channels, sample_frames_n)
    if len(picks) == 0:
        return 0.0
    var threshold = wcag_aa_required_contrast(font_size_pt, is_bold)
    var safe = 0
    for pick_index in range(len(picks)):
        var minima = _region_text_contrast_minima(
            flat_frames,
            width,
            height,
            channels,
            picks[pick_index],
            row_start,
            height,
        )
        if _best_contrast_from_minima(minima[0], minima[1]) >= threshold:
            safe += 1
    return Float64(safe) / Float64(len(picks))


def subtitle_band_needs_backplate_for_video(
    flat_frames: List[Float64],
    width: Int,
    height: Int,
    channels: Int,
    sample_frames_n: Int,
    band_rows: Int,
    font_size_pt: Float64,
    is_bold: Bool,
) -> Bool:
    """True when any sampled subtitle band falls below the WCAG AA threshold."""
    return sampled_subtitle_band_wcag_safe_ratio(
        flat_frames,
        width,
        height,
        channels,
        sample_frames_n,
        band_rows,
        font_size_pt,
        is_bold,
    ) < 1.0
