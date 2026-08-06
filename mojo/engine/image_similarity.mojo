"""
image_similarity.mojo — Deterministic grayscale image similarity metrics on flat buffers. Zero Python imports.

All inputs are row-major grayscale flat buffers. Metrics operate over the
declared width × height region, treating missing trailing pixels as 0.

Public API:
  mean_squared_error_flat          — average squared pixel error
  mean_abs_error_flat              — average absolute pixel error
  psnr_flat                        — peak signal-to-noise ratio in dB (capped at 99 for identity)
  normalized_cross_correlation_flat — Pearson-style normalized cross-correlation in [-1, 1]
  ssim_global_flat                 — global SSIM approximation in [-1, 1]
  diff_fraction_flat               — fraction of pixels whose absolute diff exceeds a threshold
  crop_region_similarity_flat      — crop-local similarity in [0, 1] from inverse MAE
  duplicate_score_flat             — weighted duplicate score in [0, 1]
"""
from std.math import log as _log, sqrt


def _pixel_count(width: Int, height: Int) -> Int:
    if width <= 0 or height <= 0:
        return 0
    return width * height


def _pixel_value(flat: List[Float64], index: Int) -> Float64:
    if index < 0 or index >= len(flat):
        return 0.0
    return flat[index]


def _abs(v: Float64) -> Float64:
    return -v if v < 0.0 else v


def _clamp01(v: Float64) -> Float64:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def mean_squared_error_flat(
    flat_a: List[Float64], flat_b: List[Float64], width: Int, height: Int
) -> Float64:
    """Average squared pixel error."""
    var pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0
    var total: Float64 = 0.0
    for index in range(pixels):
        var diff = _pixel_value(flat_a, index) - _pixel_value(flat_b, index)
        total += diff * diff
    return total / Float64(pixels)


def mean_abs_error_flat(
    flat_a: List[Float64], flat_b: List[Float64], width: Int, height: Int
) -> Float64:
    """Average absolute pixel error."""
    var pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0
    var total: Float64 = 0.0
    for index in range(pixels):
        total += _abs(_pixel_value(flat_a, index) - _pixel_value(flat_b, index))
    return total / Float64(pixels)


def psnr_flat(
    flat_a: List[Float64], flat_b: List[Float64], width: Int, height: Int, max_value: Float64
) -> Float64:
    """Peak signal-to-noise ratio in dB. Identical images return 99.0."""
    if max_value <= 0.0:
        return 0.0
    var mse = mean_squared_error_flat(flat_a, flat_b, width, height)
    if mse <= 1e-12:
        return 99.0
    return 10.0 * (_log((max_value * max_value) / mse) / _log(10.0))
def normalized_cross_correlation_flat(
    flat_a: List[Float64], flat_b: List[Float64], width: Int, height: Int
) -> Float64:
    """Pearson-style normalized cross-correlation in [-1, 1]."""
    var pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0
    var mean_a: Float64 = 0.0
    var mean_b: Float64 = 0.0
    for index in range(pixels):
        mean_a += _pixel_value(flat_a, index)
        mean_b += _pixel_value(flat_b, index)
    mean_a /= Float64(pixels)
    mean_b /= Float64(pixels)

    var numerator: Float64 = 0.0
    var denom_a: Float64 = 0.0
    var denom_b: Float64 = 0.0
    for index in range(pixels):
        var da = _pixel_value(flat_a, index) - mean_a
        var db = _pixel_value(flat_b, index) - mean_b
        numerator += da * db
        denom_a += da * da
        denom_b += db * db
    var denom = sqrt(denom_a * denom_b)
    if denom <= 1e-12:
        return 1.0 if mean_abs_error_flat(flat_a, flat_b, width, height) <= 1e-12 else 0.0
    return numerator / denom
def ssim_global_flat(
    flat_a: List[Float64], flat_b: List[Float64], width: Int, height: Int
) -> Float64:
    """Global SSIM approximation using full-image statistics."""
    var pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0
    var mean_a: Float64 = 0.0
    var mean_b: Float64 = 0.0
    for index in range(pixels):
        mean_a += _pixel_value(flat_a, index)
        mean_b += _pixel_value(flat_b, index)
    mean_a /= Float64(pixels)
    mean_b /= Float64(pixels)

    var var_a: Float64 = 0.0
    var var_b: Float64 = 0.0
    var covariance: Float64 = 0.0
    for index in range(pixels):
        var da = _pixel_value(flat_a, index) - mean_a
        var db = _pixel_value(flat_b, index) - mean_b
        var_a += da * da
        var_b += db * db
        covariance += da * db
    var_a /= Float64(pixels)
    var_b /= Float64(pixels)
    covariance /= Float64(pixels)

    var c1: Float64 = 6.5025
    var c2: Float64 = 58.5225
    return (
        (2.0 * mean_a * mean_b + c1)
        * (2.0 * covariance + c2)
    ) / (
        (mean_a * mean_a + mean_b * mean_b + c1)
        * (var_a + var_b + c2)
    )
def diff_fraction_flat(
    flat_a: List[Float64], flat_b: List[Float64], width: Int, height: Int, diff_threshold: Float64
) -> Float64:
    """Fraction of pixels whose absolute difference exceeds diff_threshold."""
    var pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0
    var count = 0
    for index in range(pixels):
        if _abs(_pixel_value(flat_a, index) - _pixel_value(flat_b, index)) > diff_threshold:
            count += 1
    return Float64(count) / Float64(pixels)
def crop_region_similarity_flat(
    flat_a: List[Float64], flat_b: List[Float64],
    width: Int, height: Int, x0: Int, y0: Int, x1: Int, y1: Int,
) -> Float64:
    """Inverse-MAE crop similarity in [0, 1] for the inclusive box [x0, y0, x1, y1]."""
    if width <= 0 or height <= 0:
        return 0.0
    var left = x0
    var top = y0
    var right = x1
    var bottom = y1
    if left < 0:
        left = 0
    if top < 0:
        top = 0
    if right >= width:
        right = width - 1
    if bottom >= height:
        bottom = height - 1
    if right < left or bottom < top:
        return 0.0
    var total: Float64 = 0.0
    var count = 0
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            total += _abs(_pixel_value(flat_a, y * width + x) - _pixel_value(flat_b, y * width + x))
            count += 1
    if count <= 0:
        return 0.0
    return _clamp01(1.0 - (total / Float64(count)) / 255.0)
def duplicate_score_flat(
    flat_a: List[Float64], flat_b: List[Float64], width: Int, height: Int
) -> Float64:
    """Weighted duplicate score in [0, 1] from SSIM, NCC, and low-diff stability."""
    var ssim = _clamp01(ssim_global_flat(flat_a, flat_b, width, height))
    var ncc = _clamp01((normalized_cross_correlation_flat(flat_a, flat_b, width, height) + 1.0) / 2.0)
    var stable = 1.0 - diff_fraction_flat(flat_a, flat_b, width, height, 12.0)
    return _clamp01(0.55 * ssim + 0.25 * ncc + 0.20 * stable)
