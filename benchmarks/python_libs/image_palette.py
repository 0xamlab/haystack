"""Manual Python reference for image_palette.mojo."""

from __future__ import annotations

from dataclasses import dataclass
from math import log


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


def _hex_char(value: int) -> str:
    return "0123456789ABCDEF"[value]


def rgb_to_hex(color: RGB) -> str:
    r = int(_clamp01(color.r) * 255.0 + 0.5)
    g = int(_clamp01(color.g) * 255.0 + 0.5)
    b = int(_clamp01(color.b) * 255.0 + 0.5)
    return (
        "#"
        + _hex_char((r >> 4) & 0x0F)
        + _hex_char(r & 0x0F)
        + _hex_char((g >> 4) & 0x0F)
        + _hex_char(g & 0x0F)
        + _hex_char((b >> 4) & 0x0F)
        + _hex_char(b & 0x0F)
    )


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


def _palette_stats(
    flat_rgb: list[float],
    width: int,
    height: int,
    levels: int,
) -> tuple[list[float], int]:
    bins = levels if levels > 0 else 1
    total_bins = bins * bins * bins
    stats = [0.0] * (total_bins * 4)
    bin_width = 256.0 / float(bins)
    target_pixels = max(width * height, 0)
    valid_pixels = 0

    for pixel_index in range(target_pixels):
        base = pixel_index * 3
        if base + 2 >= len(flat_rgb):
            break
        r = _clamp_rgb255(flat_rgb[base])
        g = _clamp_rgb255(flat_rgb[base + 1])
        b = _clamp_rgb255(flat_rgb[base + 2])
        offset = _bin_index(r, g, b, bins, bin_width) * 4
        stats[offset] += 1.0
        stats[offset + 1] += r
        stats[offset + 2] += g
        stats[offset + 3] += b
        valid_pixels += 1

    return stats, valid_pixels


def dominant_palette_rgb255(
    flat_rgb: list[float],
    width: int,
    height: int,
    levels: int,
    top_k: int,
) -> list[float]:
    out: list[float] = []
    if top_k <= 0:
        return out

    stats, valid_pixels = _palette_stats(flat_rgb, width, height, levels)
    if valid_pixels <= 0:
        return out

    total_bins = len(stats) // 4
    used = [False] * total_bins
    for _ in range(top_k):
        best_index = -1
        best_count = 0.0
        for bin_index in range(total_bins):
            count = stats[bin_index * 4]
            if not used[bin_index] and count > best_count:
                best_index = bin_index
                best_count = count
        if best_index < 0 or best_count <= 0.0:
            break
        offset = best_index * 4
        out.extend(
            [
                stats[offset + 1] / best_count,
                stats[offset + 2] / best_count,
                stats[offset + 3] / best_count,
                best_count / float(valid_pixels),
            ]
        )
        used[best_index] = True
    return out


def palette_size_estimate(
    flat_rgb: list[float],
    width: int,
    height: int,
    levels: int,
    min_weight: float,
) -> int:
    stats, valid_pixels = _palette_stats(flat_rgb, width, height, levels)
    if valid_pixels <= 0:
        return 0
    total_bins = len(stats) // 4
    count = 0
    for bin_index in range(total_bins):
        weight = stats[bin_index * 4] / float(valid_pixels)
        if stats[bin_index * 4] > 0.0 and weight >= min_weight:
            count += 1
    return count


def palette_entropy(flat_rgb: list[float], width: int, height: int, levels: int) -> float:
    stats, valid_pixels = _palette_stats(flat_rgb, width, height, levels)
    if valid_pixels <= 0:
        return 0.0
    total_bins = len(stats) // 4
    total = 0.0
    log2 = log(2.0)
    for bin_index in range(total_bins):
        count = stats[bin_index * 4]
        if count <= 0.0:
            continue
        p = count / float(valid_pixels)
        total -= p * (log(p) / log2)
    return total


def mean_saturation_rgb255(flat_rgb: list[float], width: int, height: int) -> float:
    target_pixels = max(width * height, 0)
    valid = 0
    total = 0.0
    for pixel_index in range(target_pixels):
        base = pixel_index * 3
        if base + 2 >= len(flat_rgb):
            break
        hsv = rgb_to_hsv(
            RGB(
                _clamp_rgb255(flat_rgb[base]) / 255.0,
                _clamp_rgb255(flat_rgb[base + 1]) / 255.0,
                _clamp_rgb255(flat_rgb[base + 2]) / 255.0,
            )
        )
        total += hsv.s
        valid += 1
    if valid <= 0:
        return 0.0
    return total / float(valid)


def warm_color_ratio_rgb255(
    flat_rgb: list[float],
    width: int,
    height: int,
    min_saturation: float,
) -> float:
    target_pixels = max(width * height, 0)
    valid = 0
    warm = 0
    for pixel_index in range(target_pixels):
        base = pixel_index * 3
        if base + 2 >= len(flat_rgb):
            break
        hsv = rgb_to_hsv(
            RGB(
                _clamp_rgb255(flat_rgb[base]) / 255.0,
                _clamp_rgb255(flat_rgb[base + 1]) / 255.0,
                _clamp_rgb255(flat_rgb[base + 2]) / 255.0,
            )
        )
        if hsv.s >= min_saturation and (hsv.h <= 90.0 or hsv.h >= 330.0):
            warm += 1
        valid += 1
    if valid <= 0:
        return 0.0
    return float(warm) / float(valid)


def palette_contrast_score(
    flat_rgb: list[float],
    width: int,
    height: int,
    levels: int,
    top_k: int,
) -> float:
    palette = dominant_palette_rgb255(flat_rgb, width, height, levels, top_k)
    colors = len(palette) // 4
    if colors < 2:
        return 0.0

    total_weight = 0.0
    total_score = 0.0
    for i in range(colors):
        ri = palette[i * 4] / 255.0
        gi = palette[i * 4 + 1] / 255.0
        bi = palette[i * 4 + 2] / 255.0
        li = rgb_to_luminance(ri, gi, bi)
        wi = palette[i * 4 + 3]
        for j in range(i + 1, colors):
            rj = palette[j * 4] / 255.0
            gj = palette[j * 4 + 1] / 255.0
            bj = palette[j * 4 + 2] / 255.0
            pair_weight = wi * palette[j * 4 + 3]
            total_weight += pair_weight
            total_score += pair_weight * (
                (contrast_ratio(li, rgb_to_luminance(rj, gj, bj)) - 1.0) / 20.0
            )
    if total_weight <= 0.0:
        return 0.0
    ratio = total_score / total_weight
    if ratio < 0.0:
        return 0.0
    if ratio > 1.0:
        return 1.0
    return ratio


def accent_color_hex(flat_rgb: list[float], width: int, height: int, levels: int) -> str:
    palette = dominant_palette_rgb255(flat_rgb, width, height, levels, 5)
    colors = len(palette) // 4
    if colors <= 0:
        return "#000000"

    best_index = 0
    best_score = -1.0
    for index in range(colors):
        r = palette[index * 4]
        g = palette[index * 4 + 1]
        b = palette[index * 4 + 2]
        weight = palette[index * 4 + 3]
        hsv = rgb_to_hsv(RGB(r / 255.0, g / 255.0, b / 255.0))
        score = hsv.s * (0.25 + 0.75 * weight)
        if score > best_score:
            best_score = score
            best_index = index

    return rgb_to_hex(
        RGB(
            palette[best_index * 4] / 255.0,
            palette[best_index * 4 + 1] / 255.0,
            palette[best_index * 4 + 2] / 255.0,
        )
    )


def is_monochrome_palette(
    flat_rgb: list[float],
    width: int,
    height: int,
    levels: int,
    min_weight: float,
    max_mean_saturation: float,
) -> bool:
    if mean_saturation_rgb255(flat_rgb, width, height) <= max_mean_saturation:
        return True
    return palette_size_estimate(flat_rgb, width, height, levels, min_weight) <= 1
