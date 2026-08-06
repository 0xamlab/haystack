"""
color_check.mojo — WCAG-ready color accessibility helpers for vision/image flows. Zero Python imports.

This module bridges low-level color math and image-level routing by exposing
deterministic helpers for:
  - gamma-corrected luminance and WCAG contrast
  - large/bold text AA thresholds
  - black-vs-white text recommendation
  - dominant background extraction from flat RGB images

Image helpers operate on the dominant quantized background cluster and return
the cluster mean as [r, g, b, weight], where channels stay in 0-255.

Public API:
  wcag_relative_luminance_rgb255      — gamma-corrected relative luminance from 0-255 RGB
  wcag_relative_luminance_hex         — same for "#RRGGBB"
  wcag_aa_required_contrast           — 4.5 normal text, 3.0 large/bold-large
  wcag_contrast_ratio_rgb255          — contrast ratio between two 0-255 RGB colours
  wcag_contrast_ratio_hex             — contrast ratio between two hex colours
  wcag_text_pass_rgb255               — WCAG AA pass/fail for 0-255 RGB colours
  wcag_text_pass_hex                  — WCAG AA pass/fail for hex colours
  preferred_text_color_rgb255         — choose "#000000" or "#FFFFFF" for max contrast
  preferred_text_color_hex            — same for a hex background
  dominant_background_rgb255          — dominant background colour as [r, g, b, weight]
  dominant_background_hex             — dominant background colour as "#RRGGBB"
  dominant_background_contrast_ratio_hex — contrast of text hex vs dominant background
  dominant_background_wcag_pass_hex   — WCAG AA pass/fail vs dominant background
  preferred_text_color_for_image      — choose "#000000" or "#FFFFFF" for dominant background
  preferred_text_contrast_for_image   — contrast ratio of the preferred text colour
  preferred_text_pass_for_image       — WCAG AA pass/fail for the preferred text colour
"""
from color import RGB, hex_to_rgb, rgb_to_hex
from color_science import contrast_ratio, rgb_to_luminance


def _clamp_rgb255(v: Float64) -> Float64:
    if v < 0.0:
        return 0.0
    if v > 255.0:
        return 255.0
    return v


def _rgb255_to_rgb01(r: Float64, g: Float64, b: Float64) -> RGB:
    return RGB(_clamp_rgb255(r) / 255.0, _clamp_rgb255(g) / 255.0, _clamp_rgb255(b) / 255.0)


def _is_hex_digit(b: UInt8) -> Bool:
    var code = Int(b)
    return (
        (code >= 48 and code <= 57)
        or (code >= 65 and code <= 70)
        or (code >= 97 and code <= 102)
    )


def _validated_hex_to_rgb(hex: String) raises -> RGB:
    var bytes = hex.as_bytes()
    var offset = 0
    if len(hex) > 0 and Int(bytes[0]) == 35:
        offset = 1
    if len(hex) - offset != 6:
        raise Error(
            "Expected a 6-digit RGB hex string, received length "
            + String(len(hex) - offset)
            + "."
        )
    for i in range(offset, offset + 6):
        if not _is_hex_digit(bytes[i]):
            raise Error("Hex string contains a non-hexadecimal character.")
    return hex_to_rgb(hex)


def _channel_bin(v: Float64, bins: Int, bin_w: Float64) -> Int:
    var bucket = Int(_clamp_rgb255(v) / bin_w)
    if bucket < 0:
        return 0
    if bucket >= bins:
        return bins - 1
    return bucket


def _dominant_bin_index(r: Float64, g: Float64, b: Float64, bins: Int, bin_w: Float64) -> Int:
    var rb = _channel_bin(r, bins, bin_w)
    var gb = _channel_bin(g, bins, bin_w)
    var bb = _channel_bin(b, bins, bin_w)
    return (rb * bins + gb) * bins + bb


def _dominant_background_stats(
    flat_rgb: List[Float64], width: Int, height: Int, levels: Int
) -> List[Float64]:
    var bins = levels
    if bins <= 0:
        bins = 1
    var total_bins = bins * bins * bins
    var hist = List[Int]()
    for _ in range(total_bins):
        hist.append(0)

    var bin_w = 256.0 / Float64(bins)
    var target_pixels = width * height
    if target_pixels < 0:
        target_pixels = 0

    var valid_pixels = 0
    for i in range(target_pixels):
        var base = i * 3
        if base + 2 >= len(flat_rgb):
            break
        hist[
            _dominant_bin_index(
                flat_rgb[base],
                flat_rgb[base + 1],
                flat_rgb[base + 2],
                bins,
                bin_w,
            )
        ] += 1
        valid_pixels += 1

    var out = List[Float64]()
    if valid_pixels == 0:
        out.append(0.0)
        out.append(0.0)
        out.append(0.0)
        out.append(0.0)
        return out^

    var best_bin = 0
    var best_count = hist[0]
    for i in range(1, len(hist)):
        if hist[i] > best_count:
            best_bin = i
            best_count = hist[i]

    var sum_r: Float64 = 0.0
    var sum_g: Float64 = 0.0
    var sum_b: Float64 = 0.0
    for i in range(target_pixels):
        var base = i * 3
        if base + 2 >= len(flat_rgb):
            break
        var r = _clamp_rgb255(flat_rgb[base])
        var g = _clamp_rgb255(flat_rgb[base + 1])
        var b = _clamp_rgb255(flat_rgb[base + 2])
        if _dominant_bin_index(r, g, b, bins, bin_w) == best_bin:
            sum_r += r
            sum_g += g
            sum_b += b

    out.append(sum_r / Float64(best_count))
    out.append(sum_g / Float64(best_count))
    out.append(sum_b / Float64(best_count))
    out.append(Float64(best_count) / Float64(valid_pixels))
    return out^


def _preferred_contrast_against_rgb255(bg_r: Float64, bg_g: Float64, bg_b: Float64) -> Float64:
    var black = wcag_contrast_ratio_rgb255(0.0, 0.0, 0.0, bg_r, bg_g, bg_b)
    var white = wcag_contrast_ratio_rgb255(255.0, 255.0, 255.0, bg_r, bg_g, bg_b)
    return black if black >= white else white


def wcag_relative_luminance_rgb255(r: Float64, g: Float64, b: Float64) -> Float64:
    var c = _rgb255_to_rgb01(r, g, b)
    return rgb_to_luminance(c.r, c.g, c.b)


def wcag_relative_luminance_hex(hex: String) raises -> Float64:
    var c = _validated_hex_to_rgb(hex)
    return rgb_to_luminance(c.r, c.g, c.b)


def wcag_aa_required_contrast(font_size_pt: Float64, is_bold: Bool) -> Float64:
    if font_size_pt >= 18.0 or (is_bold and font_size_pt >= 14.0):
        return 3.0
    return 4.5


def wcag_contrast_ratio_rgb255(
    fg_r: Float64, fg_g: Float64, fg_b: Float64,
    bg_r: Float64, bg_g: Float64, bg_b: Float64,
) -> Float64:
    return contrast_ratio(
        wcag_relative_luminance_rgb255(fg_r, fg_g, fg_b),
        wcag_relative_luminance_rgb255(bg_r, bg_g, bg_b),
    )


def wcag_contrast_ratio_hex(fg_hex: String, bg_hex: String) raises -> Float64:
    return contrast_ratio(
        wcag_relative_luminance_hex(fg_hex),
        wcag_relative_luminance_hex(bg_hex),
    )


def wcag_text_pass_rgb255(
    fg_r: Float64, fg_g: Float64, fg_b: Float64,
    bg_r: Float64, bg_g: Float64, bg_b: Float64,
    font_size_pt: Float64, is_bold: Bool,
) -> Bool:
    return (
        wcag_contrast_ratio_rgb255(fg_r, fg_g, fg_b, bg_r, bg_g, bg_b)
        >= wcag_aa_required_contrast(font_size_pt, is_bold)
    )


def wcag_text_pass_hex(
    fg_hex: String, bg_hex: String, font_size_pt: Float64, is_bold: Bool,
) raises -> Bool:
    return (
        wcag_contrast_ratio_hex(fg_hex, bg_hex)
        >= wcag_aa_required_contrast(font_size_pt, is_bold)
    )


def preferred_text_color_rgb255(bg_r: Float64, bg_g: Float64, bg_b: Float64) -> String:
    var black = wcag_contrast_ratio_rgb255(0.0, 0.0, 0.0, bg_r, bg_g, bg_b)
    var white = wcag_contrast_ratio_rgb255(255.0, 255.0, 255.0, bg_r, bg_g, bg_b)
    return "#000000" if black >= white else "#FFFFFF"


def preferred_text_color_hex(bg_hex: String) raises -> String:
    var c = _validated_hex_to_rgb(bg_hex)
    return preferred_text_color_rgb255(c.r * 255.0, c.g * 255.0, c.b * 255.0)


def dominant_background_rgb255(
    flat_rgb: List[Float64], width: Int, height: Int, levels: Int
) -> List[Float64]:
    return _dominant_background_stats(flat_rgb, width, height, levels)


def dominant_background_hex(flat_rgb: List[Float64], width: Int, height: Int, levels: Int) -> String:
    var bg = dominant_background_rgb255(flat_rgb, width, height, levels)
    return rgb_to_hex(_rgb255_to_rgb01(bg[0], bg[1], bg[2]))


def dominant_background_contrast_ratio_hex(
    flat_rgb: List[Float64], width: Int, height: Int, levels: Int, text_hex: String,
) raises -> Float64:
    var bg = dominant_background_rgb255(flat_rgb, width, height, levels)
    var text = _validated_hex_to_rgb(text_hex)
    return wcag_contrast_ratio_rgb255(
        text.r * 255.0,
        text.g * 255.0,
        text.b * 255.0,
        bg[0],
        bg[1],
        bg[2],
    )


def dominant_background_wcag_pass_hex(
    flat_rgb: List[Float64], width: Int, height: Int, levels: Int,
    text_hex: String, font_size_pt: Float64, is_bold: Bool,
) raises -> Bool:
    return (
        dominant_background_contrast_ratio_hex(flat_rgb, width, height, levels, text_hex)
        >= wcag_aa_required_contrast(font_size_pt, is_bold)
    )


def preferred_text_color_for_image(
    flat_rgb: List[Float64], width: Int, height: Int, levels: Int,
) -> String:
    var bg = dominant_background_rgb255(flat_rgb, width, height, levels)
    return preferred_text_color_rgb255(bg[0], bg[1], bg[2])


def preferred_text_contrast_for_image(
    flat_rgb: List[Float64], width: Int, height: Int, levels: Int,
) -> Float64:
    var bg = dominant_background_rgb255(flat_rgb, width, height, levels)
    return _preferred_contrast_against_rgb255(bg[0], bg[1], bg[2])


def preferred_text_pass_for_image(
    flat_rgb: List[Float64], width: Int, height: Int, levels: Int,
    font_size_pt: Float64, is_bold: Bool,
) -> Bool:
    return (
        preferred_text_contrast_for_image(flat_rgb, width, height, levels)
        >= wcag_aa_required_contrast(font_size_pt, is_bold)
    )
