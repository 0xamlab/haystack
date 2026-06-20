"""
image_palette.mojo — Deterministic palette-level image analysis on flat RGB buffers. Zero Python imports.

Complements low-level colour math with image-level palette features for routing,
branding checks, and creative review. All inputs are flat row-major RGB buffers
with channels in 0-255.

Public API:
  dominant_palette_rgb255  — top-k quantized palette colours as [r,g,b,weight]×k
  palette_size_estimate    — number of palette bins whose normalized weight >= min_weight
  palette_entropy          — Shannon entropy in bits over quantized palette bins
  mean_saturation_rgb255   — mean HSV saturation in [0, 1]
  warm_color_ratio_rgb255  — fraction of warm pixels with saturation >= min_saturation
  palette_contrast_score   — weighted pairwise dominant-palette contrast score in [0, 1]
  accent_color_hex         — saturated dominant accent as "#RRGGBB"
  is_monochrome_palette    — true when the image is effectively monochrome
"""
from std.math import log as _log
from color import RGB, rgb_to_hsv, rgb_to_hex
from color_science import contrast_ratio, rgb_to_luminance


fn _clamp01(v: Float64) -> Float64:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


fn _clamp_rgb255(v: Float64) -> Float64:
    if v < 0.0:
        return 0.0
    if v > 255.0:
        return 255.0
    return v


fn _bin_index(r: Float64, g: Float64, b: Float64, bins: Int, bin_w: Float64) -> Int:
    var rb = Int(_clamp_rgb255(r) / bin_w)
    var gb = Int(_clamp_rgb255(g) / bin_w)
    var bb = Int(_clamp_rgb255(b) / bin_w)
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


fn _palette_stats(flat_rgb: List[Float64], width: Int, height: Int, levels: Int) -> List[Float64]:
    """Return packed [count,sum_r,sum_g,sum_b]×bins plus trailing valid-pixel count."""
    var bins = levels
    if bins <= 0:
        bins = 1
    var total_bins = bins * bins * bins
    var stats = List[Float64]()
    for _ in range(total_bins * 4):
        stats.append(0.0)

    var bin_w = 256.0 / Float64(bins)
    var target_pixels = width * height
    if target_pixels < 0:
        target_pixels = 0

    var valid_pixels = 0
    for pixel_index in range(target_pixels):
        var base = pixel_index * 3
        if base + 2 >= len(flat_rgb):
            break
        var r = _clamp_rgb255(flat_rgb[base])
        var g = _clamp_rgb255(flat_rgb[base + 1])
        var b = _clamp_rgb255(flat_rgb[base + 2])
        var offset = _bin_index(r, g, b, bins, bin_w) * 4
        stats[offset] += 1.0
        stats[offset + 1] += r
        stats[offset + 2] += g
        stats[offset + 3] += b
        valid_pixels += 1
    stats.append(Float64(valid_pixels))
    return stats^


fn _valid_pixels(stats: List[Float64]) -> Float64:
    if len(stats) == 0:
        return 0.0
    return stats[len(stats) - 1]


fn dominant_palette_rgb255(
    flat_rgb: List[Float64], width: Int, height: Int, levels: Int, top_k: Int
) -> List[Float64]:
    """Top-k palette colours as [r,g,b,weight] repeated in descending weight order."""
    var out = List[Float64]()
    if top_k <= 0:
        return out^

    var stats = _palette_stats(flat_rgb, width, height, levels)
    var valid = _valid_pixels(stats)
    if valid <= 0.0:
        return out^

    var total_bins = (len(stats) - 1) // 4
    var used = List[Bool]()
    for _ in range(total_bins):
        used.append(False)

    for _pick in range(top_k):
        var best = -1
        var best_count: Float64 = 0.0
        for bin_index in range(total_bins):
            var count = stats[bin_index * 4]
            if not used[bin_index] and count > best_count:
                best = bin_index
                best_count = count
        if best < 0 or best_count <= 0.0:
            break
        var offset = best * 4
        out.append(stats[offset + 1] / best_count)
        out.append(stats[offset + 2] / best_count)
        out.append(stats[offset + 3] / best_count)
        out.append(best_count / valid)
        used[best] = True
    return out^


fn palette_size_estimate(
    flat_rgb: List[Float64], width: Int, height: Int, levels: Int, min_weight: Float64
) -> Int:
    """Count palette bins whose normalized weight is at least min_weight."""
    var stats = _palette_stats(flat_rgb, width, height, levels)
    var valid = _valid_pixels(stats)
    if valid <= 0.0:
        return 0
    var total_bins = (len(stats) - 1) // 4
    var count = 0
    for bin_index in range(total_bins):
        var weight = stats[bin_index * 4] / valid
        if stats[bin_index * 4] > 0.0 and weight >= min_weight:
            count += 1
    return count


fn palette_entropy(flat_rgb: List[Float64], width: Int, height: Int, levels: Int) -> Float64:
    """Shannon entropy in bits over the quantized RGB palette histogram."""
    var stats = _palette_stats(flat_rgb, width, height, levels)
    var valid = _valid_pixels(stats)
    if valid <= 0.0:
        return 0.0
    var total_bins = (len(stats) - 1) // 4
    var total: Float64 = 0.0
    var log2 = _log(2.0)
    for bin_index in range(total_bins):
        var count = stats[bin_index * 4]
        if count <= 0.0:
            continue
        var p = count / valid
        total -= p * (_log(p) / log2)
    return total


fn mean_saturation_rgb255(flat_rgb: List[Float64], width: Int, height: Int) -> Float64:
    """Mean HSV saturation across valid RGB pixels in [0, 1]."""
    var target_pixels = width * height
    if target_pixels < 0:
        target_pixels = 0
    var valid = 0
    var total: Float64 = 0.0
    for pixel_index in range(target_pixels):
        var base = pixel_index * 3
        if base + 2 >= len(flat_rgb):
            break
        var hsv = rgb_to_hsv(
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
    return total / Float64(valid)


fn warm_color_ratio_rgb255(
    flat_rgb: List[Float64], width: Int, height: Int, min_saturation: Float64
) -> Float64:
    """Fraction of pixels whose HSV hue is warm and whose saturation >= min_saturation."""
    var target_pixels = width * height
    if target_pixels < 0:
        target_pixels = 0
    var valid = 0
    var warm = 0
    for pixel_index in range(target_pixels):
        var base = pixel_index * 3
        if base + 2 >= len(flat_rgb):
            break
        var hsv = rgb_to_hsv(
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
    return Float64(warm) / Float64(valid)


fn palette_contrast_score(
    flat_rgb: List[Float64], width: Int, height: Int, levels: Int, top_k: Int
) -> Float64:
    """Weighted pairwise dominant-palette contrast score normalized to [0, 1]."""
    var palette = dominant_palette_rgb255(flat_rgb, width, height, levels, top_k)
    var colors = len(palette) // 4
    if colors < 2:
        return 0.0

    var total_weight: Float64 = 0.0
    var total_score: Float64 = 0.0
    for i in range(colors):
        var ri = palette[i * 4] / 255.0
        var gi = palette[i * 4 + 1] / 255.0
        var bi = palette[i * 4 + 2] / 255.0
        var li = rgb_to_luminance(ri, gi, bi)
        var wi = palette[i * 4 + 3]
        for j in range(i + 1, colors):
            var rj = palette[j * 4] / 255.0
            var gj = palette[j * 4 + 1] / 255.0
            var bj = palette[j * 4 + 2] / 255.0
            var pair_weight = wi * palette[j * 4 + 3]
            total_weight += pair_weight
            total_score += pair_weight * ((contrast_ratio(li, rgb_to_luminance(rj, gj, bj)) - 1.0) / 20.0)
    if total_weight <= 0.0:
        return 0.0
    return _clamp01(total_score / total_weight)


fn accent_color_hex(flat_rgb: List[Float64], width: Int, height: Int, levels: Int) -> String:
    """Return the strongest saturated dominant accent as a hex colour."""
    var palette = dominant_palette_rgb255(flat_rgb, width, height, levels, 5)
    var colors = len(palette) // 4
    if colors <= 0:
        return "#000000"

    var best_index = 0
    var best_score: Float64 = -1.0
    for index in range(colors):
        var r = palette[index * 4]
        var g = palette[index * 4 + 1]
        var b = palette[index * 4 + 2]
        var weight = palette[index * 4 + 3]
        var hsv = rgb_to_hsv(RGB(r / 255.0, g / 255.0, b / 255.0))
        var score = hsv.s * (0.25 + 0.75 * weight)
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


fn is_monochrome_palette(
    flat_rgb: List[Float64], width: Int, height: Int,
    levels: Int, min_weight: Float64, max_mean_saturation: Float64,
) -> Bool:
    """True when the image is effectively monochrome by saturation or palette size."""
    if mean_saturation_rgb255(flat_rgb, width, height) <= max_mean_saturation:
        return True
    return palette_size_estimate(flat_rgb, width, height, levels, min_weight) <= 1
