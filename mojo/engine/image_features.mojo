"""
image_features.mojo — Cheap visual features for routing & crop targeting. Zero Python imports.

Feeds the Vision Gate's "what is in it / where to crop" decisions: edge energy,
colour histograms + comparison metrics for deduplication, dominant colours, and a
coarse saliency grid that points at the most informative region of an image.

Grayscale operations take List[List[Float64]] (0-255); colour operations take a
row-major interleaved RGB list (flat_rgb[i*3+{0,1,2}], each 0-255) + width/height.

Public API:
  sobel_magnitude        — per-pixel Sobel gradient magnitude grid
  edge_density           — fraction of pixels with gradient magnitude > threshold
  color_histogram        — normalized bins³ RGB histogram from flat RGB
  histogram_intersection — Σ min(a_i, b_i)   (1 = identical normalized hists)
  histogram_chi_square   — ½ Σ (a-b)²/(a+b)  (0 = identical)
  histogram_correlation  — Pearson correlation of two histograms
  dominant_colors        — top-3 quantized colours as [r,g,b,weight]×3
  saliency_grid          — grid_rows×grid_cols mean-edge-energy map
  most_salient_cell      — flattened index (row*cols+col) of the peak cell
  edge_density_flat      — edge_density on flat grayscale pixels
  most_salient_cell_flat — most_salient_cell on flat grayscale pixels
"""
from std.math import sqrt, isnan, isinf
from image_ops import convolve_2d, sobel_x_kernel, sobel_y_kernel
from image_resize import reshape_to_grid


# Ceiling on wire-supplied bins per channel: the histogram allocates
# bins^3 entries, so the count must be bounded.
comptime MAX_COLOR_HISTOGRAM_BINS: Int = 64


# Ceiling on wire-supplied saliency grid dimensions: bounds the
# grid_rows*grid_cols allocation.
comptime MAX_SALIENCY_DIM: Int = 1024


# ── Sobel magnitude / edge density ──────────────────────────────────────────────


def sobel_magnitude(image: List[List[Float64]]) -> List[List[Float64]]:
    """Per-pixel sqrt(gx² + gy²) gradient magnitude (valid-mode, H-2 × W-2)."""
    var gx = convolve_2d(image, sobel_x_kernel())
    var gy = convolve_2d(image, sobel_y_kernel())
    var result = List[List[Float64]]()
    for r in range(len(gx)):
        var row = List[Float64]()
        for c in range(len(gx[r])):
            row.append(sqrt(gx[r][c] * gx[r][c] + gy[r][c] * gy[r][c]))
        result.append(row^)
    return result^


def edge_density(image: List[List[Float64]], mag_threshold: Float64) -> Float64:
    """Fraction of pixels whose Sobel magnitude exceeds mag_threshold."""
    var mag = sobel_magnitude(image)
    var n = 0
    var strong = 0
    for r in range(len(mag)):
        for c in range(len(mag[r])):
            n += 1
            if mag[r][c] > mag_threshold:
                strong += 1
    if n == 0:
        return 0.0
    return Float64(strong) / Float64(n)


# ── Colour histograms ───────────────────────────────────────────────────────────


def color_histogram(
    flat_rgb: List[Float64], width: Int, height: Int, bins_per_channel: Int
) -> List[Float64]:
    """Normalized bins³ RGB histogram. Index = (rb·bins + gb)·bins + bb."""
    var bins = bins_per_channel
    if bins <= 0:
        bins = 1
    if bins > MAX_COLOR_HISTOGRAM_BINS:
        bins = MAX_COLOR_HISTOGRAM_BINS
    var total_bins = bins * bins * bins
    var hist = List[Float64]()
    for _ in range(total_bins):
        hist.append(0.0)
    var npx = width * height
    var bin_w = 256.0 / Float64(bins)
    var count = 0
    for i in range(npx):
        var base = i * 3
        if base + 2 >= len(flat_rgb):
            break
        # Int() of a non-finite channel is an uncatchable abort; skip the pixel.
        if (
            isnan(flat_rgb[base]) or isinf(flat_rgb[base])
            or isnan(flat_rgb[base + 1]) or isinf(flat_rgb[base + 1])
            or isnan(flat_rgb[base + 2]) or isinf(flat_rgb[base + 2])
        ):
            continue
        var rb = Int(flat_rgb[base] / bin_w)
        var gb = Int(flat_rgb[base + 1] / bin_w)
        var bb = Int(flat_rgb[base + 2] / bin_w)
        if rb >= bins:
            rb = bins - 1
        if rb < 0:
            rb = 0
        if gb >= bins:
            gb = bins - 1
        if gb < 0:
            gb = 0
        if bb >= bins:
            bb = bins - 1
        if bb < 0:
            bb = 0
        hist[(rb * bins + gb) * bins + bb] += 1.0
        count += 1
    if count > 0:
        for k in range(total_bins):
            hist[k] = hist[k] / Float64(count)
    return hist^


def histogram_intersection(a: List[Float64], b: List[Float64]) -> Float64:
    """Σ min(a_i, b_i). For normalized histograms: 1 = identical, 0 = disjoint."""
    var n = len(a)
    if len(b) < n:
        n = len(b)
    var s: Float64 = 0.0
    for i in range(n):
        s += a[i] if a[i] < b[i] else b[i]
    return s


def histogram_chi_square(a: List[Float64], b: List[Float64]) -> Float64:
    """½ Σ (a_i-b_i)²/(a_i+b_i). 0 = identical; larger = more different."""
    var n = len(a)
    if len(b) < n:
        n = len(b)
    var s: Float64 = 0.0
    for i in range(n):
        var denom = a[i] + b[i]
        if denom > 0.0:
            var d = a[i] - b[i]
            s += (d * d) / denom
    return 0.5 * s


def histogram_correlation(a: List[Float64], b: List[Float64]) -> Float64:
    """Pearson correlation of two histograms in [-1, 1]; 0 if either is flat."""
    var n = len(a)
    if len(b) < n:
        n = len(b)
    if n == 0:
        return 0.0
    var ma: Float64 = 0.0
    var mb: Float64 = 0.0
    for i in range(n):
        ma += a[i]
        mb += b[i]
    ma = ma / Float64(n)
    mb = mb / Float64(n)
    var cov: Float64 = 0.0
    var va: Float64 = 0.0
    var vb: Float64 = 0.0
    for i in range(n):
        var da = a[i] - ma
        var db = b[i] - mb
        cov += da * db
        va += da * da
        vb += db * db
    var denom = sqrt(va * vb)
    if denom <= 0.0:
        return 0.0
    return cov / denom


# ── Dominant colours ────────────────────────────────────────────────────────────


def dominant_colors(
    flat_rgb: List[Float64], width: Int, height: Int, levels: Int
) -> List[Float64]:
    """Top-3 quantized colours as a flat [r,g,b,weight] × 3 list (bin centers)."""
    var bins = levels
    if bins <= 0:
        bins = 1
    # Must match color_histogram's clamp, or the index decode below would
    # disagree with the histogram layout.
    if bins > MAX_COLOR_HISTOGRAM_BINS:
        bins = MAX_COLOR_HISTOGRAM_BINS
    var hist = color_histogram(flat_rgb, width, height, bins)
    var bin_w = 256.0 / Float64(bins)
    var out = List[Float64]()
    for _pick in range(3):
        var best = 0
        var best_w: Float64 = -1.0
        for k in range(len(hist)):
            if hist[k] > best_w:
                best_w = hist[k]
                best = k
        var bb = best % bins
        var gb = (best // bins) % bins
        var rb = (best // (bins * bins)) % bins
        out.append((Float64(rb) + 0.5) * bin_w)
        out.append((Float64(gb) + 0.5) * bin_w)
        out.append((Float64(bb) + 0.5) * bin_w)
        out.append(best_w if best_w > 0.0 else 0.0)
        if len(hist) > 0:
            hist[best] = -1.0
    return out^


# ── Saliency ──────────────────────────────────────────────────────────────────


def saliency_grid(
    image: List[List[Float64]], grid_rows: Int, grid_cols: Int
) -> List[List[Float64]]:
    """grid_rows×grid_cols map of mean Sobel edge energy per cell."""
    var result = List[List[Float64]]()
    if grid_rows <= 0 or grid_cols <= 0:
        return result^
    var mag = sobel_magnitude(image)
    var hh = len(mag)
    if hh == 0:
        return result^
    var ww = len(mag[0])
    for gr in range(grid_rows):
        var y0 = (gr * hh) // grid_rows
        var y1 = ((gr + 1) * hh) // grid_rows
        if y1 <= y0:
            y1 = y0 + 1
        if y1 > hh:
            y1 = hh
        var row = List[Float64]()
        for gc in range(grid_cols):
            var x0 = (gc * ww) // grid_cols
            var x1 = ((gc + 1) * ww) // grid_cols
            if x1 <= x0:
                x1 = x0 + 1
            if x1 > ww:
                x1 = ww
            var s: Float64 = 0.0
            var cnt = 0
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    s += mag[yy][xx]
                    cnt += 1
            if cnt == 0:
                row.append(0.0)
            else:
                row.append(s / Float64(cnt))
        result.append(row^)
    return result^


def most_salient_cell(saliency: List[List[Float64]]) -> Int:
    """Flattened index (row*cols + col) of the highest-energy cell; -1 if empty."""
    var rows = len(saliency)
    if rows == 0:
        return -1
    var cols = len(saliency[0])
    if cols == 0:
        return -1
    var best = -1
    var best_v: Float64 = -1.0
    for r in range(rows):
        for c in range(len(saliency[r])):
            if saliency[r][c] > best_v:
                best_v = saliency[r][c]
                best = r * cols + c
    return best


# ── flat-pixel entry points ─────────────────────────────────────────────────────


def edge_density_flat(
    flat: List[Float64], width: Int, height: Int, mag_threshold: Float64
) -> Float64:
    # The declared width*height must fit the pixels actually supplied; a
    # larger grid (or non-positive dims) would fabricate an unbounded grid.
    var npix = len(flat)
    if width <= 0 or height <= 0 or width > npix // height:
        return 0.0
    return edge_density(reshape_to_grid(flat, width, height), mag_threshold)


def most_salient_cell_flat(
    flat: List[Float64], width: Int, height: Int, grid_rows: Int, grid_cols: Int
) -> Int:
    # The declared width*height must fit the pixels actually supplied, and
    # the saliency grid dims are clamped so neither grid is unbounded.
    var npix = len(flat)
    if width <= 0 or height <= 0 or width > npix // height:
        return -1
    if grid_rows <= 0 or grid_cols <= 0:
        return -1
    var gr = grid_rows
    var gc = grid_cols
    if gr > MAX_SALIENCY_DIM:
        gr = MAX_SALIENCY_DIM
    if gc > MAX_SALIENCY_DIM:
        gc = MAX_SALIENCY_DIM
    var grid = reshape_to_grid(flat, width, height)
    return most_salient_cell(saliency_grid(grid, gr, gc))
