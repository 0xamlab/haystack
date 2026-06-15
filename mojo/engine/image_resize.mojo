"""
image_resize.mojo — Grayscale downscaling and summed-area tables. Zero Python imports.

Foundation for the Codna Vision Gate: cheaply shrink a (PIL-decoded) grayscale
thumbnail to the tiny fixed sizes the perceptual hashers and quality scorers
need, and provide O(1) region sums via integral images.

Images are List[List[Float64]] (grayscale, values 0-255). Flat variants take a
row-major List[Float64] plus width/height so a caller can pass pixels over the
runtime socket without nesting the payload.

Public API:
  reshape_to_grid     — row-major flat List[Float64] + w,h → List[List[Float64]]
  flatten_grid        — List[List[Float64]] → row-major flat List[Float64]
  box_downscale       — area-average downscale to out_w × out_h
  bilinear_downscale  — bilinear-interpolated downscale to out_w × out_h
  resize_for_hash     — square size×size box-average (feeds aHash/pHash prep)
  resize_for_dhash    — (hash_w+1)×hash_h box-average (feeds dHash)
  integral_image      — (H+1)×(W+1) summed-area table
  box_sum             — O(1) inclusive region sum from an integral image
  downscale_flat      — flat→flat box downscale (socket-friendly entry point)
"""


# ── Helpers ───────────────────────────────────────────────────────────────────


fn _empty_grid() -> List[List[Float64]]:
    return List[List[Float64]]()


# ── reshape_to_grid / flatten_grid ──────────────────────────────────────────────


fn reshape_to_grid(
    flat: List[Float64], width: Int, height: Int
) -> List[List[Float64]]:
    """Row-major flat pixels → height×width grid. Missing cells become 0.0."""
    var result = List[List[Float64]]()
    if width <= 0 or height <= 0:
        return result^
    var n = len(flat)
    for r in range(height):
        var row = List[Float64]()
        for c in range(width):
            var idx = r * width + c
            if idx < n:
                row.append(flat[idx])
            else:
                row.append(0.0)
        result.append(row^)
    return result^


fn flatten_grid(image: List[List[Float64]]) -> List[Float64]:
    """Grid → row-major flat list."""
    var result = List[Float64]()
    var rows = len(image)
    for r in range(rows):
        var cols = len(image[r])
        for c in range(cols):
            result.append(image[r][c])
    return result^


# ── box_downscale ───────────────────────────────────────────────────────────────


fn box_downscale(
    image: List[List[Float64]], out_w: Int, out_h: Int
) -> List[List[Float64]]:
    """Area-average downscale. Each output cell averages its source block."""
    var ih = len(image)
    if ih == 0 or out_w <= 0 or out_h <= 0:
        return _empty_grid()
    var iw = len(image[0])
    if iw == 0:
        return _empty_grid()
    var result = List[List[Float64]]()
    for oy in range(out_h):
        var y0 = (oy * ih) // out_h
        var y1 = ((oy + 1) * ih) // out_h
        if y1 <= y0:
            y1 = y0 + 1
        if y1 > ih:
            y1 = ih
        var row = List[Float64]()
        for ox in range(out_w):
            var x0 = (ox * iw) // out_w
            var x1 = ((ox + 1) * iw) // out_w
            if x1 <= x0:
                x1 = x0 + 1
            if x1 > iw:
                x1 = iw
            var s: Float64 = 0.0
            var cnt = 0
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    s += image[yy][xx]
                    cnt += 1
            if cnt == 0:
                row.append(0.0)
            else:
                row.append(s / Float64(cnt))
        result.append(row^)
    return result^


# ── bilinear_downscale ──────────────────────────────────────────────────────────


fn bilinear_downscale(
    image: List[List[Float64]], out_w: Int, out_h: Int
) -> List[List[Float64]]:
    """Bilinear-interpolated resize to out_w × out_h (half-pixel centers)."""
    var ih = len(image)
    if ih == 0 or out_w <= 0 or out_h <= 0:
        return _empty_grid()
    var iw = len(image[0])
    if iw == 0:
        return _empty_grid()
    var result = List[List[Float64]]()
    for oy in range(out_h):
        var sy = (Float64(oy) + 0.5) * Float64(ih) / Float64(out_h) - 0.5
        if sy < 0.0:
            sy = 0.0
        var y0 = Int(sy)
        var y1 = y0 + 1
        if y1 > ih - 1:
            y1 = ih - 1
        var fy = sy - Float64(y0)
        var row = List[Float64]()
        for ox in range(out_w):
            var sx = (Float64(ox) + 0.5) * Float64(iw) / Float64(out_w) - 0.5
            if sx < 0.0:
                sx = 0.0
            var x0 = Int(sx)
            var x1 = x0 + 1
            if x1 > iw - 1:
                x1 = iw - 1
            var fx = sx - Float64(x0)
            var top = image[y0][x0] * (1.0 - fx) + image[y0][x1] * fx
            var bot = image[y1][x0] * (1.0 - fx) + image[y1][x1] * fx
            row.append(top * (1.0 - fy) + bot * fy)
        result.append(row^)
    return result^


# ── resize_for_hash / resize_for_dhash ──────────────────────────────────────────


fn resize_for_hash(image: List[List[Float64]], size: Int) -> List[List[Float64]]:
    """Square size×size area-average (e.g. 8 for aHash, 32 for pHash prep)."""
    return box_downscale(image, size, size)


fn resize_for_dhash(
    image: List[List[Float64]], hash_w: Int, hash_h: Int
) -> List[List[Float64]]:
    """(hash_w+1)×hash_h grid so adjacent-column compares yield hash_w×hash_h bits."""
    return box_downscale(image, hash_w + 1, hash_h)


# ── integral_image / box_sum ────────────────────────────────────────────────────


fn integral_image(image: List[List[Float64]]) -> List[List[Float64]]:
    """(H+1)×(W+1) summed-area table; I[y+1][x+1] = sum of image[0..y][0..x]."""
    var ih = len(image)
    if ih == 0:
        return _empty_grid()
    var iw = len(image[0])
    var result = List[List[Float64]]()
    var zero_row = List[Float64]()
    for _ in range(iw + 1):
        zero_row.append(0.0)
    result.append(zero_row^)
    for y in range(ih):
        var row = List[Float64]()
        row.append(0.0)
        for x in range(iw):
            var v = image[y][x] + result[y][x + 1] + row[x] - result[y][x]
            row.append(v)
        result.append(row^)
    return result^


fn box_sum(
    integral: List[List[Float64]], r0: Int, c0: Int, r1: Int, c1: Int
) -> Float64:
    """Inclusive sum over rows r0..r1 and cols c0..c1 of the source grid."""
    var h = len(integral)
    if h == 0:
        return 0.0
    var w = len(integral[0])
    var a0 = r0
    var b0 = c0
    var a1 = r1
    var b1 = c1
    if a0 < 0:
        a0 = 0
    if b0 < 0:
        b0 = 0
    if a1 > h - 2:
        a1 = h - 2
    if b1 > w - 2:
        b1 = w - 2
    if a1 < a0 or b1 < b0:
        return 0.0
    return (
        integral[a1 + 1][b1 + 1]
        - integral[a0][b1 + 1]
        - integral[a1 + 1][b0]
        + integral[a0][b0]
    )


# ── downscale_flat ──────────────────────────────────────────────────────────────


fn downscale_flat(
    flat: List[Float64], in_w: Int, in_h: Int, out_w: Int, out_h: Int
) -> List[Float64]:
    """Socket-friendly: flat row-major pixels → box-downscaled flat pixels."""
    var grid = reshape_to_grid(flat, in_w, in_h)
    var small = box_downscale(grid, out_w, out_h)
    return flatten_grid(small)
