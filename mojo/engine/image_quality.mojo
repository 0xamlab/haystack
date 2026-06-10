"""
image_quality.mojo — Deterministic image quality scores. Zero Python imports.

Cheap reject/route signals for the Vision Gate: decide whether an image is sharp
enough, bright enough, and information-rich enough to be worth an expensive
vision-model call — or whether to ask for a clearer image or skip it entirely.

Operates on grayscale grids (List[List[Float64]], values 0-255). The *_flat
variants accept row-major flat pixels + width/height for the runtime socket.

Public API:
  blur_score               — variance of the Laplacian (higher = sharper)
  is_blurry                — blur_score < threshold
  brightness_mean          — mean pixel value (0-255)
  contrast_std             — standard deviation of pixel values
  shannon_entropy          — 256-bin intensity entropy in bits (0-8)
  is_near_blank            — contrast_std < threshold
  uniformity               — fraction of pixels in the dominant 16-bin bucket
  noise_estimate           — robust noise sigma via MAD of the Laplacian
  is_over_or_under_exposed — brightness outside [low, high]
  quality_score            — composite usability score in [0, 1]
  blur_score_flat          — blur_score on flat pixels
  brightness_flat          — brightness_mean on flat pixels
  entropy_flat             — shannon_entropy on flat pixels
  contrast_flat            — contrast_std on flat pixels
  quality_score_flat       — quality_score on flat pixels
"""
from std.math import log as _log, sqrt
from image_ops import convolve_2d, histogram, mean_pixel
from image_resize import reshape_to_grid


# ── Helpers ───────────────────────────────────────────────────────────────────


fn _abs(x: Float64) -> Float64:
    return -x if x < 0.0 else x


fn _clamp01(x: Float64) -> Float64:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


fn _laplacian_kernel() -> List[List[Float64]]:
    """4-neighbour Laplacian [[0,1,0],[1,-4,1],[0,1,0]]."""
    var k = List[List[Float64]]()
    var r0 = List[Float64]()
    r0.append(0.0); r0.append(1.0); r0.append(0.0)
    var r1 = List[Float64]()
    r1.append(1.0); r1.append(-4.0); r1.append(1.0)
    var r2 = List[Float64]()
    r2.append(0.0); r2.append(1.0); r2.append(0.0)
    k.append(r0^); k.append(r1^); k.append(r2^)
    return k^


fn _median(values: List[Float64]) -> Float64:
    var n = len(values)
    if n == 0:
        return 0.0
    var a = List[Float64]()
    for i in range(n):
        a.append(values[i])
    for i in range(1, n):
        var key = a[i]
        var j = i - 1
        while j >= 0 and a[j] > key:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = key
    if n % 2 == 1:
        return a[n // 2]
    return (a[n // 2 - 1] + a[n // 2]) / 2.0


# ── blur / sharpness ────────────────────────────────────────────────────────────


fn blur_score(image: List[List[Float64]]) -> Float64:
    """Variance of the Laplacian response. Higher = sharper, lower = blurrier."""
    var lap = convolve_2d(image, _laplacian_kernel())
    var n = 0
    var s: Float64 = 0.0
    for r in range(len(lap)):
        for c in range(len(lap[r])):
            s += lap[r][c]
            n += 1
    if n == 0:
        return 0.0
    var mean = s / Float64(n)
    var acc: Float64 = 0.0
    for r in range(len(lap)):
        for c in range(len(lap[r])):
            var d = lap[r][c] - mean
            acc += d * d
    return acc / Float64(n)


fn is_blurry(image: List[List[Float64]], threshold: Float64) -> Bool:
    """True if the Laplacian variance is below threshold (e.g. ~100 for 0-255)."""
    return blur_score(image) < threshold


# ── brightness / contrast ───────────────────────────────────────────────────────


fn brightness_mean(image: List[List[Float64]]) -> Float64:
    """Average pixel value (0-255)."""
    return mean_pixel(image)


fn contrast_std(image: List[List[Float64]]) -> Float64:
    """Population standard deviation of pixel values."""
    var n = 0
    var s: Float64 = 0.0
    for r in range(len(image)):
        for c in range(len(image[r])):
            s += image[r][c]
            n += 1
    if n == 0:
        return 0.0
    var mean = s / Float64(n)
    var acc: Float64 = 0.0
    for r in range(len(image)):
        for c in range(len(image[r])):
            var d = image[r][c] - mean
            acc += d * d
    return sqrt(acc / Float64(n))


# ── entropy / uniformity / blankness ────────────────────────────────────────────


fn shannon_entropy(image: List[List[Float64]]) -> Float64:
    """256-bin intensity entropy in bits (0 = flat, up to 8 = uniform spread)."""
    var bins = histogram(image, 256)
    var total = 0
    for i in range(len(bins)):
        total += bins[i]
    if total == 0:
        return 0.0
    var ln2 = _log(2.0)
    var ent: Float64 = 0.0
    for i in range(len(bins)):
        if bins[i] > 0:
            var p = Float64(bins[i]) / Float64(total)
            ent -= p * (_log(p) / ln2)
    return ent


fn is_near_blank(image: List[List[Float64]], std_threshold: Float64) -> Bool:
    """True if pixel variation is below threshold (mostly uniform / empty)."""
    return contrast_std(image) < std_threshold


fn uniformity(image: List[List[Float64]]) -> Float64:
    """Fraction of pixels falling in the single most-populated 16-bin bucket."""
    var bins = histogram(image, 16)
    var total = 0
    var mx = 0
    for i in range(len(bins)):
        total += bins[i]
        if bins[i] > mx:
            mx = bins[i]
    if total == 0:
        return 0.0
    return Float64(mx) / Float64(total)


# ── noise ───────────────────────────────────────────────────────────────────────


fn noise_estimate(image: List[List[Float64]]) -> Float64:
    """Robust noise sigma: 1.4826 × MAD of the Laplacian response."""
    var lap = convolve_2d(image, _laplacian_kernel())
    var vals = List[Float64]()
    for r in range(len(lap)):
        for c in range(len(lap[r])):
            vals.append(lap[r][c])
    if len(vals) == 0:
        return 0.0
    var med = _median(vals)
    var devs = List[Float64]()
    for i in range(len(vals)):
        devs.append(_abs(vals[i] - med))
    return 1.4826 * _median(devs)


# ── exposure / composite ──────────────────────────────────────────────────────


fn is_over_or_under_exposed(
    image: List[List[Float64]], low: Float64, high: Float64
) -> Bool:
    """True if mean brightness falls outside [low, high]."""
    var m = mean_pixel(image)
    return m < low or m > high


fn quality_score(image: List[List[Float64]]) -> Float64:
    """Composite usability score in [0,1]: 40% sharpness, 30% exposure, 30% entropy."""
    var b = mean_pixel(image)
    var exposure = 1.0 - _abs(b - 128.0) / 128.0
    var ent = shannon_entropy(image) / 8.0
    var blur = blur_score(image)
    var sharp = blur / (blur + 100.0)
    return _clamp01(0.4 * sharp + 0.3 * exposure + 0.3 * ent)


# ── flat-pixel entry points ─────────────────────────────────────────────────────


fn blur_score_flat(flat: List[Float64], width: Int, height: Int) -> Float64:
    return blur_score(reshape_to_grid(flat, width, height))


fn brightness_flat(flat: List[Float64], width: Int, height: Int) -> Float64:
    return brightness_mean(reshape_to_grid(flat, width, height))


fn entropy_flat(flat: List[Float64], width: Int, height: Int) -> Float64:
    return shannon_entropy(reshape_to_grid(flat, width, height))


fn contrast_flat(flat: List[Float64], width: Int, height: Int) -> Float64:
    return contrast_std(reshape_to_grid(flat, width, height))


fn quality_score_flat(flat: List[Float64], width: Int, height: Int) -> Float64:
    return quality_score(reshape_to_grid(flat, width, height))
