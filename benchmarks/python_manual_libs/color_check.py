"""Manual Python reference for color_check.mojo."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RGB:
    r: float
    g: float
    b: float


def _clamp_rgb255(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 255.0:
        return 255.0
    return value


def _rgb255_to_rgb01(r: float, g: float, b: float) -> RGB:
    return RGB(_clamp_rgb255(r) / 255.0, _clamp_rgb255(g) / 255.0, _clamp_rgb255(b) / 255.0)


def _srgb_channel_to_linear(channel: float) -> float:
    clamped = min(1.0, max(0.0, channel))
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


def _hex_char(value: int) -> str:
    return "0123456789ABCDEF"[value]


def rgb_to_hex(color: RGB) -> str:
    r = int(round(min(1.0, max(0.0, color.r)) * 255.0))
    g = int(round(min(1.0, max(0.0, color.g)) * 255.0))
    b = int(round(min(1.0, max(0.0, color.b)) * 255.0))
    return (
        "#"
        + _hex_char((r >> 4) & 0x0F)
        + _hex_char(r & 0x0F)
        + _hex_char((g >> 4) & 0x0F)
        + _hex_char(g & 0x0F)
        + _hex_char((b >> 4) & 0x0F)
        + _hex_char(b & 0x0F)
    )


def _validated_hex_to_rgb(raw: str) -> RGB:
    text = raw[1:] if raw.startswith("#") else raw
    if len(text) != 6:
        raise ValueError(f"Expected a 6-digit RGB hex string, received length {len(text)}.")
    try:
        return RGB(
            int(text[0:2], 16) / 255.0,
            int(text[2:4], 16) / 255.0,
            int(text[4:6], 16) / 255.0,
        )
    except ValueError as exc:
        raise ValueError("Hex string contains a non-hexadecimal character.") from exc


def hex_to_rgb(raw: str) -> RGB:
    return _validated_hex_to_rgb(raw)


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


def dominant_background_rgb255(
    flat_rgb: list[float], width: int, height: int, levels: int
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
        hist[
            _dominant_bin_index(
                flat_rgb[base],
                flat_rgb[base + 1],
                flat_rgb[base + 2],
                bins,
                bin_width,
            )
        ] += 1
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


def wcag_relative_luminance_rgb255(r: float, g: float, b: float) -> float:
    color = _rgb255_to_rgb01(r, g, b)
    return rgb_to_luminance(color.r, color.g, color.b)


def wcag_relative_luminance_hex(raw: str) -> float:
    color = _validated_hex_to_rgb(raw)
    return rgb_to_luminance(color.r, color.g, color.b)


def wcag_aa_required_contrast(font_size_pt: float, is_bold: bool) -> float:
    if font_size_pt >= 18.0 or (is_bold and font_size_pt >= 14.0):
        return 3.0
    return 4.5


def wcag_contrast_ratio_rgb255(
    fg_r: float,
    fg_g: float,
    fg_b: float,
    bg_r: float,
    bg_g: float,
    bg_b: float,
) -> float:
    return contrast_ratio(
        wcag_relative_luminance_rgb255(fg_r, fg_g, fg_b),
        wcag_relative_luminance_rgb255(bg_r, bg_g, bg_b),
    )


def wcag_contrast_ratio_hex(fg_hex: str, bg_hex: str) -> float:
    return contrast_ratio(
        wcag_relative_luminance_hex(fg_hex),
        wcag_relative_luminance_hex(bg_hex),
    )


def wcag_text_pass_rgb255(
    fg_r: float,
    fg_g: float,
    fg_b: float,
    bg_r: float,
    bg_g: float,
    bg_b: float,
    font_size_pt: float,
    is_bold: bool,
) -> bool:
    return (
        wcag_contrast_ratio_rgb255(fg_r, fg_g, fg_b, bg_r, bg_g, bg_b)
        >= wcag_aa_required_contrast(font_size_pt, is_bold)
    )


def wcag_text_pass_hex(
    fg_hex: str,
    bg_hex: str,
    font_size_pt: float,
    is_bold: bool,
) -> bool:
    return (
        wcag_contrast_ratio_hex(fg_hex, bg_hex)
        >= wcag_aa_required_contrast(font_size_pt, is_bold)
    )


def preferred_text_color_rgb255(bg_r: float, bg_g: float, bg_b: float) -> str:
    black = wcag_contrast_ratio_rgb255(0.0, 0.0, 0.0, bg_r, bg_g, bg_b)
    white = wcag_contrast_ratio_rgb255(255.0, 255.0, 255.0, bg_r, bg_g, bg_b)
    return "#000000" if black >= white else "#FFFFFF"


def preferred_text_color_hex(bg_hex: str) -> str:
    color = _validated_hex_to_rgb(bg_hex)
    return preferred_text_color_rgb255(color.r * 255.0, color.g * 255.0, color.b * 255.0)


def dominant_background_hex(flat_rgb: list[float], width: int, height: int, levels: int) -> str:
    bg = dominant_background_rgb255(flat_rgb, width, height, levels)
    return rgb_to_hex(_rgb255_to_rgb01(bg[0], bg[1], bg[2]))


def dominant_background_contrast_ratio_hex(
    flat_rgb: list[float],
    width: int,
    height: int,
    levels: int,
    text_hex: str,
) -> float:
    bg = dominant_background_rgb255(flat_rgb, width, height, levels)
    text = _validated_hex_to_rgb(text_hex)
    return wcag_contrast_ratio_rgb255(
        text.r * 255.0,
        text.g * 255.0,
        text.b * 255.0,
        bg[0],
        bg[1],
        bg[2],
    )


def dominant_background_wcag_pass_hex(
    flat_rgb: list[float],
    width: int,
    height: int,
    levels: int,
    text_hex: str,
    font_size_pt: float,
    is_bold: bool,
) -> bool:
    return (
        dominant_background_contrast_ratio_hex(flat_rgb, width, height, levels, text_hex)
        >= wcag_aa_required_contrast(font_size_pt, is_bold)
    )


def preferred_text_color_for_image(
    flat_rgb: list[float],
    width: int,
    height: int,
    levels: int,
) -> str:
    bg = dominant_background_rgb255(flat_rgb, width, height, levels)
    return preferred_text_color_rgb255(bg[0], bg[1], bg[2])


def preferred_text_contrast_for_image(
    flat_rgb: list[float],
    width: int,
    height: int,
    levels: int,
) -> float:
    bg = dominant_background_rgb255(flat_rgb, width, height, levels)
    black = wcag_contrast_ratio_rgb255(0.0, 0.0, 0.0, bg[0], bg[1], bg[2])
    white = wcag_contrast_ratio_rgb255(255.0, 255.0, 255.0, bg[0], bg[1], bg[2])
    return black if black >= white else white


def preferred_text_pass_for_image(
    flat_rgb: list[float],
    width: int,
    height: int,
    levels: int,
    font_size_pt: float,
    is_bold: bool,
) -> bool:
    return (
        preferred_text_contrast_for_image(flat_rgb, width, height, levels)
        >= wcag_aa_required_contrast(font_size_pt, is_bold)
    )
