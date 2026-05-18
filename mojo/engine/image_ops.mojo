"""
image_ops.mojo — Image operations on 2D grayscale grids. Zero Python imports.

Replaces Pillow / OpenCV basics with pure Mojo implementations for
convolution, edge detection, thresholding, histograms, and adjustments.

Images represented as List[List[Float64]] (grayscale, values 0-255).

Public API:
  convolve_2d        — 2D convolution (valid mode)
  sobel_x_kernel     — Sobel X edge detection kernel
  sobel_y_kernel     — Sobel Y edge detection kernel
  gaussian_kernel_3x3 — Normalized 3x3 Gaussian blur kernel
  sharpen_kernel     — Sharpening kernel
  histogram          — Intensity histogram
  threshold          — Binary threshold
  invert             — Invert: 255 - pixel
  brightness         — Adjust brightness, clamped
  contrast           — Adjust contrast, clamped
  mean_pixel         — Average pixel value
"""


# ── Helpers ───────────────────────────────────────────────────────────────────


fn _clamp(v: Float64, lo: Float64, hi: Float64) -> Float64:
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


# ── convolve_2d ───────────────────────────────────────────────────────────────


fn convolve_2d(
    image: List[List[Float64]], kernel: List[List[Float64]]
) -> List[List[Float64]]:
    """2D convolution (valid mode). Output is (H-kh+1) x (W-kw+1)."""
    var ih = len(image)
    var iw = len(image[0])
    var kh = len(kernel)
    var kw = len(kernel[0])
    var oh = ih - kh + 1
    var ow = iw - kw + 1
    var result = List[List[Float64]]()
    for r in range(oh):
        var row = List[Float64]()
        for c in range(ow):
            var s: Float64 = 0.0
            for kr in range(kh):
                for kc in range(kw):
                    s += image[r + kr][c + kc] * kernel[kr][kc]
            row.append(s)
        result.append(row^)
    return result^


# ── Kernel factories ──────────────────────────────────────────────────────────


fn sobel_x_kernel() -> List[List[Float64]]:
    """Sobel X edge detection kernel [[-1,0,1],[-2,0,2],[-1,0,1]]."""
    var k = List[List[Float64]]()
    var r0 = List[Float64]()
    r0.append(-1.0); r0.append(0.0); r0.append(1.0)
    var r1 = List[Float64]()
    r1.append(-2.0); r1.append(0.0); r1.append(2.0)
    var r2 = List[Float64]()
    r2.append(-1.0); r2.append(0.0); r2.append(1.0)
    k.append(r0^); k.append(r1^); k.append(r2^)
    return k^


fn sobel_y_kernel() -> List[List[Float64]]:
    """Sobel Y kernel [[-1,-2,-1],[0,0,0],[1,2,1]]."""
    var k = List[List[Float64]]()
    var r0 = List[Float64]()
    r0.append(-1.0); r0.append(-2.0); r0.append(-1.0)
    var r1 = List[Float64]()
    r1.append(0.0); r1.append(0.0); r1.append(0.0)
    var r2 = List[Float64]()
    r2.append(1.0); r2.append(2.0); r2.append(1.0)
    k.append(r0^); k.append(r1^); k.append(r2^)
    return k^


fn gaussian_kernel_3x3() -> List[List[Float64]]:
    """Normalized 3x3 Gaussian blur kernel."""
    var k = List[List[Float64]]()
    var r0 = List[Float64]()
    r0.append(1.0 / 16.0); r0.append(2.0 / 16.0); r0.append(1.0 / 16.0)
    var r1 = List[Float64]()
    r1.append(2.0 / 16.0); r1.append(4.0 / 16.0); r1.append(2.0 / 16.0)
    var r2 = List[Float64]()
    r2.append(1.0 / 16.0); r2.append(2.0 / 16.0); r2.append(1.0 / 16.0)
    k.append(r0^); k.append(r1^); k.append(r2^)
    return k^


fn sharpen_kernel() -> List[List[Float64]]:
    """Sharpening kernel [[0,-1,0],[-1,5,-1],[0,-1,0]]."""
    var k = List[List[Float64]]()
    var r0 = List[Float64]()
    r0.append(0.0); r0.append(-1.0); r0.append(0.0)
    var r1 = List[Float64]()
    r1.append(-1.0); r1.append(5.0); r1.append(-1.0)
    var r2 = List[Float64]()
    r2.append(0.0); r2.append(-1.0); r2.append(0.0)
    k.append(r0^); k.append(r1^); k.append(r2^)
    return k^


# ── histogram ─────────────────────────────────────────────────────────────────


fn histogram(image: List[List[Float64]], n_bins: Int) -> List[Int]:
    """Intensity histogram with n_bins bins spanning [0, 255]."""
    var bins = List[Int]()
    for _ in range(n_bins):
        bins.append(0)
    var bin_width = 256.0 / Float64(n_bins)
    var rows = len(image)
    for r in range(rows):
        var cols = len(image[r])
        for c in range(cols):
            var idx = Int(image[r][c] / bin_width)
            if idx >= n_bins:
                idx = n_bins - 1
            if idx < 0:
                idx = 0
            bins[idx] += 1
    return bins^


# ── threshold ─────────────────────────────────────────────────────────────────


fn threshold(
    image: List[List[Float64]], thresh: Float64
) -> List[List[Float64]]:
    """Binary threshold: 255 if pixel > thresh, else 0."""
    var result = List[List[Float64]]()
    var rows = len(image)
    for r in range(rows):
        var row = List[Float64]()
        var cols = len(image[r])
        for c in range(cols):
            if image[r][c] > thresh:
                row.append(255.0)
            else:
                row.append(0.0)
        result.append(row^)
    return result^


# ── invert ────────────────────────────────────────────────────────────────────


fn invert(image: List[List[Float64]]) -> List[List[Float64]]:
    """Invert: 255 - pixel."""
    var result = List[List[Float64]]()
    var rows = len(image)
    for r in range(rows):
        var row = List[Float64]()
        var cols = len(image[r])
        for c in range(cols):
            row.append(255.0 - image[r][c])
        result.append(row^)
    return result^


# ── brightness ────────────────────────────────────────────────────────────────


fn brightness(
    image: List[List[Float64]], delta: Float64
) -> List[List[Float64]]:
    """Adjust brightness, clamp to [0, 255]."""
    var result = List[List[Float64]]()
    var rows = len(image)
    for r in range(rows):
        var row = List[Float64]()
        var cols = len(image[r])
        for c in range(cols):
            row.append(_clamp(image[r][c] + delta, 0.0, 255.0))
        result.append(row^)
    return result^


# ── contrast ──────────────────────────────────────────────────────────────────


fn contrast(
    image: List[List[Float64]], factor: Float64
) -> List[List[Float64]]:
    """Adjust contrast: (pixel - 128) * factor + 128, clamp to [0, 255]."""
    var result = List[List[Float64]]()
    var rows = len(image)
    for r in range(rows):
        var row = List[Float64]()
        var cols = len(image[r])
        for c in range(cols):
            var v = (image[r][c] - 128.0) * factor + 128.0
            row.append(_clamp(v, 0.0, 255.0))
        result.append(row^)
    return result^


# ── mean_pixel ────────────────────────────────────────────────────────────────


fn mean_pixel(image: List[List[Float64]]) -> Float64:
    """Average pixel value."""
    var total: Float64 = 0.0
    var count = 0
    var rows = len(image)
    for r in range(rows):
        var cols = len(image[r])
        for c in range(cols):
            total += image[r][c]
            count += 1
    if count == 0:
        return 0.0
    return total / Float64(count)
