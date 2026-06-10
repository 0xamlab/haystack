"""
perceptual_hash.mojo — Perceptual image hashing (aHash/dHash/pHash). Zero Python imports.

Compact 64-bit fingerprints for near-duplicate detection — the Vision Gate's
first cost saver: if an incoming image hashes within a few bits of one already
analyzed, reuse the cached result instead of calling a vision model.

Operates on grayscale grids (List[List[Float64]], values 0-255). The *_flat
variants accept row-major flat pixels + width/height for the runtime socket.
Callers pass a small pre-downscaled thumbnail; the hashers resize internally to
8×8 / 9×8 / 32×32 via image_resize.

Public API:
  ahash             — 8×8 average hash → UInt64
  dhash             — 9×8 horizontal-gradient hash → UInt64
  phash             — 32×32 DCT low-frequency hash → UInt64
  hamming_distance  — bit difference between two hashes
  is_duplicate      — hamming_distance <= max_distance
  ahash_flat        — ahash on flat pixels
  dhash_flat        — dhash on flat pixels
  phash_flat        — phash on flat pixels
"""
from std.math import cos
from image_resize import reshape_to_grid, resize_for_hash, resize_for_dhash


# ── popcount (64-bit, no sign-bit loss) ─────────────────────────────────────────


fn _popcount_u64(x: UInt64) -> Int:
    """Count set bits across all 64 bits (bitops.popcount drops bit 63)."""
    var n = x
    var count = 0
    for _ in range(64):
        count += Int(n & UInt64(1))
        n = n >> UInt64(1)
    return count


# ── median (insertion-sort copy) ────────────────────────────────────────────────


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


# ── DCT (top-left 8×8 of a 32×32 grid, unnormalized DCT-II) ──────────────────────


fn _dct8x8(image: List[List[Float64]]) -> List[Float64]:
    """Low-frequency 8×8 DCT-II coefficients of a 32×32 grid, row-major u*8+v.

    Unnormalized: only relative ordering vs the median matters for hashing, so
    the per-coefficient alpha(u) scale factors are omitted.
    """
    var n = 32
    var k = 8
    var pi: Float64 = 3.141592653589793
    var cos_t = List[List[Float64]]()
    for freq in range(k):
        var row = List[Float64]()
        for i in range(n):
            var angle = (2.0 * Float64(i) + 1.0) * Float64(freq) * pi / (
                2.0 * Float64(n)
            )
            row.append(cos(angle))
        cos_t.append(row^)
    # g[v][x] = Σ_y f[y][x] · cos_t[v][y]  (project columns onto vertical freqs)
    var g = List[List[Float64]]()
    for v in range(k):
        var row = List[Float64]()
        for x in range(n):
            var s: Float64 = 0.0
            for y in range(n):
                s += image[y][x] * cos_t[v][y]
            row.append(s)
        g.append(row^)
    # C[u][v] = Σ_x g[v][x] · cos_t[u][x]
    var out = List[Float64]()
    for u in range(k):
        for v in range(k):
            var s: Float64 = 0.0
            for x in range(n):
                s += g[v][x] * cos_t[u][x]
            out.append(s)
    return out^


# ── ahash ─────────────────────────────────────────────────────────────────────


fn ahash(image: List[List[Float64]]) -> UInt64:
    """8×8 average hash: bit set where the cell is >= the 8×8 mean."""
    var g = resize_for_hash(image, 8)
    if len(g) < 8 or len(g[0]) < 8:
        return UInt64(0)
    var s: Float64 = 0.0
    for r in range(8):
        for c in range(8):
            s += g[r][c]
    var mean = s / 64.0
    var h: UInt64 = 0
    for r in range(8):
        for c in range(8):
            h = h << UInt64(1)
            if g[r][c] >= mean:
                h = h | UInt64(1)
    return h


# ── dhash ─────────────────────────────────────────────────────────────────────


fn dhash(image: List[List[Float64]]) -> UInt64:
    """9×8 difference hash: bit set where a cell is brighter than its right neighbor."""
    var g = resize_for_dhash(image, 8, 8)
    if len(g) < 8 or len(g[0]) < 9:
        return UInt64(0)
    var h: UInt64 = 0
    for r in range(8):
        for c in range(8):
            h = h << UInt64(1)
            if g[r][c] < g[r][c + 1]:
                h = h | UInt64(1)
    return h


# ── phash ─────────────────────────────────────────────────────────────────────


fn phash(image: List[List[Float64]]) -> UInt64:
    """32×32 DCT perceptual hash: bit set where a low-freq coeff exceeds the AC median."""
    var g = resize_for_hash(image, 32)
    if len(g) < 32 or len(g[0]) < 32:
        return UInt64(0)
    var coeffs = _dct8x8(g)
    var ac = List[Float64]()
    for i in range(1, 64):
        ac.append(coeffs[i])
    var med = _median(ac)
    var h: UInt64 = 0
    for i in range(64):
        h = h << UInt64(1)
        if coeffs[i] > med:
            h = h | UInt64(1)
    return h


# ── distance / duplicate ────────────────────────────────────────────────────────


fn hamming_distance(a: UInt64, b: UInt64) -> Int:
    """Number of differing bits between two 64-bit hashes (0..64)."""
    return _popcount_u64(a ^ b)


fn is_duplicate(a: UInt64, b: UInt64, max_distance: Int) -> Bool:
    """True if the two hashes differ by at most max_distance bits."""
    return hamming_distance(a, b) <= max_distance


# ── flat-pixel entry points ─────────────────────────────────────────────────────


fn ahash_flat(flat: List[Float64], width: Int, height: Int) -> UInt64:
    """aHash from row-major flat grayscale pixels."""
    return ahash(reshape_to_grid(flat, width, height))


fn dhash_flat(flat: List[Float64], width: Int, height: Int) -> UInt64:
    """dHash from row-major flat grayscale pixels."""
    return dhash(reshape_to_grid(flat, width, height))


fn phash_flat(flat: List[Float64], width: Int, height: Int) -> UInt64:
    """pHash from row-major flat grayscale pixels."""
    return phash(reshape_to_grid(flat, width, height))
