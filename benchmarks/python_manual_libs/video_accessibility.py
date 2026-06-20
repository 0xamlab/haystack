"""Manual Python reference for mojo/engine/video_accessibility.mojo."""

from __future__ import annotations


def _clamp_rgb255(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 255.0:
        return 255.0
    return value


def _srgb_channel_to_linear(channel_255: float) -> float:
    channel = _clamp_rgb255(channel_255) / 255.0
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _rgb_to_luminance(r_255: float, g_255: float, b_255: float) -> float:
    r = _srgb_channel_to_linear(r_255)
    g = _srgb_channel_to_linear(g_255)
    b = _srgb_channel_to_linear(b_255)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(l1: float, l2: float) -> float:
    lighter = l1 if l1 >= l2 else l2
    darker = l2 if l1 >= l2 else l1
    return (lighter + 0.05) / (darker + 0.05)


def _frame_count_from_flat(flat_frames: list[float], width: int, height: int, channels: int) -> int:
    if width <= 0 or height <= 0 or channels <= 0:
        return 0
    return len(flat_frames) // (width * height * channels)


def _pixel_luminance(flat_frames: list[float], base: int, channels: int) -> float:
    r = _clamp_rgb255(flat_frames[base])
    g = r
    b = r
    if channels >= 2:
        g = _clamp_rgb255(flat_frames[base + 1])
        b = g
    if channels >= 3:
        b = _clamp_rgb255(flat_frames[base + 2])
    return _rgb_to_luminance(r, g, b)


def _best_contrast_from_minima(min_black: float, min_white: float) -> float:
    return min_black if min_black >= min_white else min_white


def _best_text_color_from_minima(min_black: float, min_white: float) -> str:
    return "#000000" if min_black >= min_white else "#FFFFFF"


def _region_text_contrast_minima(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    frame_index: int,
    row_start: int,
    row_end: int,
) -> tuple[float, float]:
    frames = _frame_count_from_flat(flat_frames, width, height, channels)
    stride = width * height * channels
    if frame_index < 0 or frame_index >= frames or stride <= 0:
        return 0.0, 0.0

    effective_row_start = max(row_start, 0)
    effective_row_end = min(row_end, height)
    if effective_row_start >= effective_row_end or width <= 0:
        return 0.0, 0.0

    frame_base = frame_index * stride
    min_black = float("inf")
    min_white = float("inf")
    valid_pixels = 0
    for y in range(effective_row_start, effective_row_end):
        row_base = frame_base + y * width * channels
        for x in range(width):
            luminance = _pixel_luminance(flat_frames, row_base + x * channels, channels)
            black_contrast = _contrast_ratio(0.0, luminance)
            white_contrast = _contrast_ratio(1.0, luminance)
            if black_contrast < min_black:
                min_black = black_contrast
            if white_contrast < min_white:
                min_white = white_contrast
            valid_pixels += 1
    if valid_pixels == 0:
        return 0.0, 0.0
    return min_black, min_white


def _sample_frame_indices(
    flat_frames: list[float], width: int, height: int, channels: int, sample_frames_n: int
) -> list[int]:
    frames = _frame_count_from_flat(flat_frames, width, height, channels)
    if frames <= 0:
        return []
    if sample_frames_n <= 0 or sample_frames_n > frames:
        sample_frames_n = frames
    if sample_frames_n == 1:
        return [0]
    if sample_frames_n >= frames:
        return list(range(frames))
    picks: list[int] = []
    last = -1
    for pick in range(sample_frames_n):
        idx = (pick * (frames - 1)) // (sample_frames_n - 1)
        if idx <= last:
            idx = last + 1
        if idx >= frames:
            idx = frames - 1
        picks.append(idx)
        last = idx
    return picks


def _band_row_start(height: int, band_rows: int) -> int:
    if height <= 0 or band_rows <= 0:
        return -1
    return height - min(height, band_rows)


def _wcag_aa_required_contrast(font_size_pt: float, is_bold: bool) -> float:
    if font_size_pt >= 18.0 or (is_bold and font_size_pt >= 14.0):
        return 3.0
    return 4.5


def frame_min_preferred_text_contrast_for_video(
    flat_frames: list[float], width: int, height: int, channels: int, frame_index: int
) -> float:
    minima = _region_text_contrast_minima(flat_frames, width, height, channels, frame_index, 0, height)
    return _best_contrast_from_minima(minima[0], minima[1])


def frame_preferred_text_color_for_video(
    flat_frames: list[float], width: int, height: int, channels: int, frame_index: int
) -> str:
    minima = _region_text_contrast_minima(flat_frames, width, height, channels, frame_index, 0, height)
    return _best_text_color_from_minima(minima[0], minima[1])


def sampled_video_min_text_contrast(
    flat_frames: list[float], width: int, height: int, channels: int, sample_frames_n: int
) -> float:
    picks = _sample_frame_indices(flat_frames, width, height, channels, sample_frames_n)
    if not picks:
        return 0.0
    return min(
        frame_min_preferred_text_contrast_for_video(flat_frames, width, height, channels, frame_index)
        for frame_index in picks
    )


def sampled_video_wcag_safe_ratio(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    sample_frames_n: int,
    font_size_pt: float,
    is_bold: bool,
) -> float:
    picks = _sample_frame_indices(flat_frames, width, height, channels, sample_frames_n)
    if not picks:
        return 0.0
    threshold = _wcag_aa_required_contrast(font_size_pt, is_bold)
    safe = sum(
        1
        for frame_index in picks
        if frame_min_preferred_text_contrast_for_video(
            flat_frames, width, height, channels, frame_index
        )
        >= threshold
    )
    return safe / len(picks)


def needs_text_backplate_for_video(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    sample_frames_n: int,
    font_size_pt: float,
    is_bold: bool,
) -> bool:
    return (
        sampled_video_wcag_safe_ratio(
            flat_frames,
            width,
            height,
            channels,
            sample_frames_n,
            font_size_pt,
            is_bold,
        )
        < 1.0
    )


def subtitle_band_min_preferred_text_contrast_for_video(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    sample_frames_n: int,
    band_rows: int,
) -> float:
    row_start = _band_row_start(height, band_rows)
    if row_start < 0:
        return 0.0
    picks = _sample_frame_indices(flat_frames, width, height, channels, sample_frames_n)
    if not picks:
        return 0.0
    min_black = float("inf")
    min_white = float("inf")
    for frame_index in picks:
        frame_min_black, frame_min_white = _region_text_contrast_minima(
            flat_frames, width, height, channels, frame_index, row_start, height
        )
        min_black = min(min_black, frame_min_black)
        min_white = min(min_white, frame_min_white)
    return _best_contrast_from_minima(min_black, min_white)


def subtitle_band_preferred_text_color_for_video(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    sample_frames_n: int,
    band_rows: int,
) -> str:
    row_start = _band_row_start(height, band_rows)
    if row_start < 0:
        return "#000000"
    picks = _sample_frame_indices(flat_frames, width, height, channels, sample_frames_n)
    if not picks:
        return "#000000"
    min_black = float("inf")
    min_white = float("inf")
    for frame_index in picks:
        frame_min_black, frame_min_white = _region_text_contrast_minima(
            flat_frames, width, height, channels, frame_index, row_start, height
        )
        min_black = min(min_black, frame_min_black)
        min_white = min(min_white, frame_min_white)
    return _best_text_color_from_minima(min_black, min_white)


def sampled_subtitle_band_wcag_safe_ratio(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    sample_frames_n: int,
    band_rows: int,
    font_size_pt: float,
    is_bold: bool,
) -> float:
    row_start = _band_row_start(height, band_rows)
    if row_start < 0:
        return 0.0
    picks = _sample_frame_indices(flat_frames, width, height, channels, sample_frames_n)
    if not picks:
        return 0.0
    threshold = _wcag_aa_required_contrast(font_size_pt, is_bold)
    safe = 0
    for frame_index in picks:
        minima = _region_text_contrast_minima(
            flat_frames, width, height, channels, frame_index, row_start, height
        )
        if _best_contrast_from_minima(minima[0], minima[1]) >= threshold:
            safe += 1
    return safe / len(picks)


def subtitle_band_needs_backplate_for_video(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    sample_frames_n: int,
    band_rows: int,
    font_size_pt: float,
    is_bold: bool,
) -> bool:
    return (
        sampled_subtitle_band_wcag_safe_ratio(
            flat_frames,
            width,
            height,
            channels,
            sample_frames_n,
            band_rows,
            font_size_pt,
            is_bold,
        )
        < 1.0
    )
