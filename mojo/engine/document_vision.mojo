"""
document_vision.mojo — Deterministic document-thresholding and scan-quality helpers. Zero Python imports.

Assumes grayscale flat buffers with darker ink on lighter paper. Binary outputs
use 255.0 for foreground ink and 0.0 for background paper.

Public API:
  otsu_threshold_flat        — global Otsu threshold in 0-255 space
  binarize_otsu_flat         — dark-ink binary mask via Otsu
  adaptive_mean_binarize_flat — local-mean thresholding for uneven lighting
  horizontal_projection      — foreground counts by row
  vertical_projection        — foreground counts by column
  mask_content_bbox_flat     — [x0, y0, x1, y1, area] of the foreground mask
  skew_angle_estimate_flat   — left-to-right skew angle estimate in degrees
  horizontal_text_score_flat — row-peakiness score in [0, 1] for horizontal text layouts
  document_scan_quality_flat — composite scan quality score in [0, 1]
"""
from std.math import atan2, sqrt

from image_quality import quality_score
from image_resize import box_sum, integral_image, reshape_to_grid


fn _pixel_count(width: Int, height: Int) -> Int:
    if width <= 0 or height <= 0:
        return 0
    return width * height


fn _pixel_value(flat: List[Float64], index: Int) -> Float64:
    if index < 0 or index >= len(flat):
        return 0.0
    return flat[index]


fn _clamp255(v: Float64) -> Float64:
    if v < 0.0:
        return 0.0
    if v > 255.0:
        return 255.0
    return v


fn _clamp01(v: Float64) -> Float64:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


fn _abs(v: Float64) -> Float64:
    return -v if v < 0.0 else v


fn _foreground_mask_value(value: Float64, threshold: Float64) -> Float64:
    return 255.0 if value <= threshold else 0.0


fn _projection_coefficient_of_variation(values: List[Float64]) -> Float64:
    if len(values) == 0:
        return 0.0
    var mean: Float64 = 0.0
    for value in values:
        mean += value
    mean /= Float64(len(values))
    if mean <= 0.0:
        return 0.0
    var variance: Float64 = 0.0
    for value in values:
        var diff = value - mean
        variance += diff * diff
    variance /= Float64(len(values))
    return sqrt(variance) / mean


fn otsu_threshold_flat(flat: List[Float64], width: Int, height: Int) -> Float64:
    """Global Otsu threshold in 0-255 space. Missing pixels are treated as 0."""
    var pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0

    var hist = List[Int]()
    for _ in range(256):
        hist.append(0)
    for index in range(pixels):
        var bucket = Int(_clamp255(_pixel_value(flat, index)))
        hist[bucket] += 1

    var total_sum: Float64 = 0.0
    for bucket in range(256):
        total_sum += Float64(bucket * hist[bucket])

    var weight_background = 0
    var sum_background: Float64 = 0.0
    var best_threshold = 0
    var best_score: Float64 = -1.0
    for threshold in range(256):
        weight_background += hist[threshold]
        if weight_background == 0:
            continue
        var weight_foreground = pixels - weight_background
        if weight_foreground == 0:
            break
        sum_background += Float64(threshold * hist[threshold])
        var mean_background = sum_background / Float64(weight_background)
        var mean_foreground = (total_sum - sum_background) / Float64(weight_foreground)
        var diff = mean_background - mean_foreground
        var score = (
            Float64(weight_background)
            * Float64(weight_foreground)
            * diff
            * diff
        )
        if score > best_score:
            best_score = score
            best_threshold = threshold
    return Float64(best_threshold)


fn binarize_otsu_flat(flat: List[Float64], width: Int, height: Int) -> List[Float64]:
    """Binary dark-ink mask via Otsu thresholding."""
    var out = List[Float64]()
    var pixels = _pixel_count(width, height)
    if pixels <= 0:
        return out^
    var threshold = otsu_threshold_flat(flat, width, height)
    for index in range(pixels):
        out.append(_foreground_mask_value(_pixel_value(flat, index), threshold))
    return out^


fn adaptive_mean_binarize_flat(
    flat: List[Float64], width: Int, height: Int, window_radius: Int, bias: Float64
) -> List[Float64]:
    """Local-mean thresholding for uneven lighting. Ink is any pixel <= local_mean - bias."""
    var out = List[Float64]()
    var pixels = _pixel_count(width, height)
    if pixels <= 0:
        return out^
    var radius = window_radius
    if radius < 0:
        radius = 0
    var grid = reshape_to_grid(flat, width, height)
    var sat = integral_image(grid)
    for y in range(height):
        var y0 = y - radius
        if y0 < 0:
            y0 = 0
        var y1 = y + radius
        if y1 >= height:
            y1 = height - 1
        for x in range(width):
            var x0 = x - radius
            if x0 < 0:
                x0 = 0
            var x1 = x + radius
            if x1 >= width:
                x1 = width - 1
            var count = (y1 - y0 + 1) * (x1 - x0 + 1)
            var mean = box_sum(sat, y0, x0, y1, x1) / Float64(count)
            out.append(_foreground_mask_value(grid[y][x], mean - bias))
    return out^


fn horizontal_projection(
    mask_flat: List[Float64], width: Int, height: Int, fg_threshold: Float64
) -> List[Float64]:
    """Foreground counts by row from a binary or thresholded mask."""
    var out = List[Float64]()
    var pixels = _pixel_count(width, height)
    if pixels <= 0:
        return out^
    for y in range(height):
        var total: Float64 = 0.0
        for x in range(width):
            if _pixel_value(mask_flat, y * width + x) >= fg_threshold:
                total += 1.0
        out.append(total)
    return out^


fn vertical_projection(
    mask_flat: List[Float64], width: Int, height: Int, fg_threshold: Float64
) -> List[Float64]:
    """Foreground counts by column from a binary or thresholded mask."""
    var out = List[Float64]()
    var pixels = _pixel_count(width, height)
    if pixels <= 0:
        return out^
    for x in range(width):
        var total: Float64 = 0.0
        for y in range(height):
            if _pixel_value(mask_flat, y * width + x) >= fg_threshold:
                total += 1.0
        out.append(total)
    return out^


fn mask_content_bbox_flat(
    mask_flat: List[Float64], width: Int, height: Int, fg_threshold: Float64
) -> List[Int]:
    """Foreground bounding box as [x0, y0, x1, y1, area]. Empty masks return []."""
    var out = List[Int]()
    var pixels = _pixel_count(width, height)
    if pixels <= 0:
        return out^
    var min_x = width
    var min_y = height
    var max_x = -1
    var max_y = -1
    var area = 0
    for y in range(height):
        for x in range(width):
            if _pixel_value(mask_flat, y * width + x) >= fg_threshold:
                area += 1
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y
    if area == 0:
        return out^
    out.append(min_x)
    out.append(min_y)
    out.append(max_x)
    out.append(max_y)
    out.append(area)
    return out^


fn skew_angle_estimate_flat(
    mask_flat: List[Float64], width: Int, height: Int, fg_threshold: Float64
) -> Float64:
    """Least-squares slope angle in degrees from row-wise ink centroids."""
    var pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0
    var sum_y: Float64 = 0.0
    var sum_center: Float64 = 0.0
    var sum_yy: Float64 = 0.0
    var sum_y_center: Float64 = 0.0
    var row_count = 0
    for y in range(height):
        var left = width
        var right = -1
        var count = 0
        for x in range(width):
            if _pixel_value(mask_flat, y * width + x) >= fg_threshold:
                count += 1
                if x < left:
                    left = x
                if x > right:
                    right = x
        if count == 0:
            continue
        var center = (Float64(left) + Float64(right)) / 2.0
        var yf = Float64(y)
        sum_y += yf
        sum_center += center
        sum_yy += yf * yf
        sum_y_center += yf * center
        row_count += 1
    if row_count < 2:
        return 0.0
    var n = Float64(row_count)
    var denom = n * sum_yy - sum_y * sum_y
    if denom == 0.0:
        return 0.0
    var slope = (n * sum_y_center - sum_y * sum_center) / denom
    return atan2(slope, 1.0) * 180.0 / 3.141592653589793


fn horizontal_text_score_flat(
    mask_flat: List[Float64], width: Int, height: Int, fg_threshold: Float64
) -> Float64:
    """Row-peakiness score in [0, 1]. Higher values suggest horizontal text layout."""
    var pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0
    var hp = horizontal_projection(mask_flat, width, height, fg_threshold)
    var vp = vertical_projection(mask_flat, width, height, fg_threshold)
    var total_ink: Float64 = 0.0
    for value in hp:
        total_ink += value
    if total_ink <= 0.0:
        return 0.0
    var row_cv = _projection_coefficient_of_variation(hp)
    var col_cv = _projection_coefficient_of_variation(vp)
    if row_cv <= 0.0 and col_cv <= 0.0:
        return 0.5
    return _clamp01(row_cv / (row_cv + col_cv))
fn document_scan_quality_flat(flat: List[Float64], width: Int, height: Int) -> Float64:
    """Composite document scan quality score in [0, 1]."""
    var pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0
    var grid = reshape_to_grid(flat, width, height)
    var base_quality = quality_score(grid)
    var mask = binarize_otsu_flat(flat, width, height)
    var bbox = mask_content_bbox_flat(mask, width, height, 128.0)
    if len(bbox) < 5:
        return 0.0
    var area_ratio = Float64(bbox[4]) / Float64(pixels)
    var coverage_score = _clamp01(area_ratio / 0.18)
    if area_ratio > 0.45:
        coverage_score = _clamp01((0.95 - area_ratio) / 0.50)
    var skew_score = 1.0 - _clamp01(_abs(skew_angle_estimate_flat(mask, width, height, 128.0)) / 15.0)
    var text_score = horizontal_text_score_flat(mask, width, height, 128.0)
    return _clamp01(
        0.45 * base_quality
        + 0.20 * coverage_score
        + 0.20 * skew_score
        + 0.15 * text_score
    )
