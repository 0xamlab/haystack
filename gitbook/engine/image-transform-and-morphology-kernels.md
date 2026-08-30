---
icon: image
description: Binary morphology and connected components, grayscale convolution/filtering, box and bilinear downscaling with integral images, and deterministic RGB palette extraction, all on flat or nested Float64 image buffers.
---

# Image transform and morphology kernels

Four modules for turning pixels into either more pixels or a handful of numbers. `image_morphology`
works on a thresholded binary mask — erode, dilate, open, close, fill holes, label connected
components, measure a distance transform. `image_ops` works on a grayscale grid — convolution, the
standard Sobel/Gaussian/sharpen kernels, histograms, thresholding, and simple per-pixel adjustments.
`image_resize` shrinks a grayscale grid and provides the flat-buffer bridge the other two rely on,
plus integral images for O(1) region sums. `image_palette` runs on a flat RGB buffer and reduces a
whole image to a small set of dominant colors, an entropy score, a saturation/warmth read, and a
monochrome test. None of the four call into a real image-decoding library — every function takes
pixels already decoded into a `Float64` buffer and hands back numbers or another buffer of the same
kind.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# 5x5 canvas, a solid 3x3 foreground block in rows/cols 1-3 (255.0 = foreground)
block = [
    0,0,0,0,0,
    0,255,255,255,0,
    0,255,255,255,0,
    0,255,255,255,0,
    0,0,0,0,0,
]

eroded = runtime.execute("image_morphology", "binary_erode_flat", [block, 5, 5, 3, 128.0])["result"]
sum(1 for v in eroded if v >= 128.0)
# 1 -- a 3x3 erosion of a 3x3 block leaves only the center pixel

ratio = runtime.execute("image_morphology", "foreground_area_ratio_flat", [block, 5, 5, 128.0])["result"]
# 0.36 -- 9 of the 25 pixels are foreground before erosion
```

## The modules

| Module | What it does |
| --- | --- |
| `image_morphology` | Binary erosion, dilation, opening, closing, hole filling, 4-connected component labeling, largest-component bounding box, city-block distance transform, and foreground-area ratio — all on flat row-major buffers thresholded at a caller-supplied `fg_threshold`. |
| `image_ops` | 2D convolution, the Sobel-X/Sobel-Y/Gaussian-3x3/sharpen kernel factories, an intensity histogram, binary thresholding, inversion, brightness/contrast adjustment, and mean pixel value — on nested `List[List[Float64]]` grayscale grids. |
| `image_resize` | Area-average (box) and bilinear downscaling to an arbitrary `out_w`\*`out_h`, the fixed-size resizes a perceptual-hash pipeline needs, integral images with O(1) rectangular-sum queries, and the `reshape_to_grid`/`flatten_grid` pair that bridges flat and nested layouts. |
| `image_palette` | Dominant-color extraction by RGB-cube quantization, palette size and Shannon entropy, mean HSV saturation, warm-color ratio, a WCAG-luminance-based palette contrast score, accent-color hex, and monochrome detection — on flat interleaved RGB buffers. |

## Two layouts, and the module that bridges them

`image_morphology` takes a flat `List[Float64]` plus `width`/`height` — a row-major mask with no
nesting, so pixels can cross the runtime socket without a jagged payload. `image_ops` takes a nested
`List[List[Float64]]` grid instead, because convolution and the kernel factories are naturally
row/column operations and none of `image_ops`'s functions need to travel the socket as a flat buffer
in this corpus's test suite. `image_palette` takes a third shape again: a flat buffer, but
interleaved RGB triples (`[r0,g0,b0,r1,g1,b1,...]`) rather than one channel per element.
`image_resize` is the one module that speaks both of the grayscale layouts on purpose —
`reshape_to_grid` and `flatten_grid` convert between them, `downscale_flat` composes
`reshape_to_grid` → `box_downscale` → `flatten_grid` into one flat-in/flat-out call, and every other
resize function in the module takes and returns the nested grid form directly.

## `image_morphology`: binary shape operations on a thresholded mask

| Function | What it does |
| --- | --- |
| `binary_erode_flat(flat, width, height, kernel_size, fg_threshold)` | A pixel survives only if every pixel in its `kernel_size`×`kernel_size` neighborhood is foreground; any neighborhood that runs off the canvas edge fails automatically. |
| `binary_dilate_flat(flat, width, height, kernel_size, fg_threshold)` | A pixel becomes foreground if any in-bounds pixel in its neighborhood is foreground; out-of-bounds neighbors are skipped, not counted as failing. |
| `binary_open_flat(flat, width, height, kernel_size, fg_threshold)` | Erosion (at `fg_threshold`) then dilation (at a fixed `128.0`) — removes small foreground noise without growing what survives. |
| `binary_close_flat(flat, width, height, kernel_size, fg_threshold)` | Dilation (at `fg_threshold`) then erosion (at a fixed `128.0`) — fills small background gaps without shrinking what remains. |
| `binary_fill_holes_flat(flat, width, height, fg_threshold)` | Flood-fills background from every border pixel inward; any background left unreached is an interior hole and becomes foreground. |
| `connected_components_4_flat(flat, width, height, fg_threshold)` | Labels each 4-connected foreground blob with a distinct positive integer, scanning in row-major order; background stays `0`. |
| `largest_component_bbox_flat(flat, width, height, fg_threshold)` | `[x0, y0, x1, y1, area]` for the largest 4-connected component, or an empty list if there is no foreground. |
| `distance_transform_cityblock_flat(flat, width, height, fg_threshold)` | City-block (L1) distance from each foreground pixel to the nearest background pixel, via a two-pass forward/backward sweep; background pixels are `0`. |
| `foreground_area_ratio_flat(flat, width, height, fg_threshold)` | Foreground pixel count divided by total pixel count, in `[0, 1]`. |

Every function in this module treats a pixel as foreground when its value is `>= fg_threshold`, and
every binary output uses `255.0`/`0.0` rather than `1.0`/`0.0` — so the output of one binary op is a
valid mask input to the next without rescaling.

**Erosion and dilation treat the canvas edge asymmetrically.** `binary_erode_flat` requires the
*entire* `kernel_size`×`kernel_size` window to be in bounds and foreground; the moment any offset
falls outside `[0, width)`×`[0, height)`, that pixel is marked `keep = False` and erosion discards
it — which means erosion always strips a border band `kernel_size // 2` pixels wide, regardless of
what the mask looks like there. `binary_dilate_flat` does the opposite: an out-of-bounds neighbor is
`continue`d past, not treated as a failed vote, so a foreground pixel one step from the edge with any
in-bounds foreground neighbor survives and can even grow new foreground right up to the canvas
boundary. `binary_open_flat` and `binary_close_flat` inherit whichever behavior their first pass
uses.

**`binary_open_flat`/`binary_close_flat`'s second-pass threshold of `128.0` is hardcoded, not a
bug.** The first pass (`binary_erode_flat` or `binary_dilate_flat`) always emits exactly `0.0` or
`255.0`, by construction; the second pass only needs to tell those two values apart, and any
threshold strictly between them works identically, so the caller's own `fg_threshold` — which might
be `50.0` or `200.0` for the *original* grayscale mask — is deliberately not reused for the
intermediate binary buffer.

Worked from `tests/mojo/test_image_morphology.mojo`'s real assertions, on the 5x5 block above
(`kernel_size=3`, `fg_threshold=128.0`): erosion leaves exactly 1 foreground pixel (the center);
dilation of the same block fills the whole 5x5 canvas (25 foreground pixels), because the block
already reaches one step from every edge. Opening a single isolated foreground pixel on an otherwise
empty 5x5 canvas removes it entirely (0 foreground pixels survive) — erosion has nothing
`kernel_size`-wide to preserve, so dilating an empty buffer stays empty. Closing a 3x3 ring (a 3x3
block with its center pixel missing) fills the center hole back in, leaving all 9 pixels of the
solid block; `binary_fill_holes_flat` on that same ring reaches the identical result by a different
route — flooding background in from the canvas border never reaches the ring's interior, so that one
interior pixel is reclassified foreground.

For `connected_components_4_flat`, an L-shaped test fixture with two separate blobs (a 2-pixel
vertical segment at column 0, and a 4-pixel blob spanning columns 3-4) labels the first-scanned blob
`1` and the second `2`; `largest_component_bbox_flat` on the same fixture returns
`[3, 1, 4, 3, 4]` — the 4-pixel blob's bounding box and area, correctly picking it over the 2-pixel
one. For `distance_transform_cityblock_flat` on the solid 3x3 block, the outermost ring of the block
is distance `1` from background and the true center pixel is distance `2`; background pixels stay
`0`.

## `image_ops`: convolution, kernel factories, and per-pixel adjustments

| Function | What it does |
| --- | --- |
| `convolve_2d(image, kernel)` | Valid-mode 2D convolution; output is `(H-kh+1)`×`(W-kw+1)`. Returns an empty grid rather than reading past a ragged or empty row. |
| `sobel_x_kernel()` / `sobel_y_kernel()` | The fixed 3x3 Sobel edge-detection kernels. |
| `gaussian_kernel_3x3()` | The normalized 3x3 Gaussian blur kernel (weights sum to `1.0`). |
| `sharpen_kernel()` | The fixed 3x3 unsharp-mask-style sharpening kernel (center `5`, four-neighbor `-1`). |
| `histogram(image, n_bins)` | Intensity histogram over `[0, 255]` with `n_bins` bins, clamped to `HISTOGRAM_MAX_BINS` (`65536`); non-finite pixels are skipped rather than binned. |
| `threshold(image, thresh)` | `255.0` where `pixel > thresh`, else `0.0`. |
| `invert(image)` | `255.0 - pixel`. |
| `brightness(image, delta)` | `pixel + delta`, clamped to `[0, 255]`. |
| `contrast(image, factor)` | `(pixel - 128) * factor + 128`, clamped to `[0, 255]`. |
| `mean_pixel(image)` | Average value over every pixel in the grid; `0.0` for an empty image. |

`convolve_2d`'s empty-on-ragged-input behavior is a deliberate guard, not an omission: the source's
own comment notes that indexing a jagged row past its declared width would be an uncatchable Mojo
abort, so the function checks every row's length against the first row's before doing any
arithmetic and returns an empty grid for a degenerate shape instead. `histogram` carries the same
kind of guard for a different failure — `Int()` of a NaN or infinite pixel is itself an uncatchable
abort, so `histogram` checks `isnan`/`isinf` per pixel and skips that pixel rather than crashing the
whole call, and `HISTOGRAM_MAX_BINS` caps a wire-supplied `n_bins` so a malicious or malformed
request can't force an unbounded bin-array allocation.

Worked against the real fixture in `tests/mojo/test_wave51.mojo` (a hand-built 4x4 grayscale image
with rows `[100,150,200,50]`, `[80,120,180,30]`, `[60,90,160,20]`, `[40,70,140,10]`):
`mean_pixel` returns `93.75` (the 16 values sum to `1500`). Convolving that image with the identity
kernel `[[0,0,0],[0,1,0],[0,0,0]]` gives a 2x2 output (`4-3+1`) whose four values are the image's
four center-ish pixels unchanged — `out[0][0] == 120.0`, `out[0][1] == 180.0` — because a 3x3
identity kernel is a convolution that does nothing but crop. `histogram(image, 8)` (bin width `32`)
sorts the 16 pixels into bins `[3, 3, 3, 2, 2, 2, 1, 0]` — three pixels each fall in bins 0-2 (values
10-90), tapering off toward the single pixel at `200` in bin 6, and no pixel reaches bin 7. Doubling
the same image's brightness by `+300` clamps every pixel to `255.0`; darkening by `-300` clamps every
pixel to `0.0`, since even the brightest source pixel (`200`) can't survive a `-300` shift before the
clamp.

## `image_resize`: box/bilinear downscaling and the flat/grid bridge

| Function | What it does |
| --- | --- |
| `reshape_to_grid(flat, width, height)` | Row-major flat buffer → `height`×`width` grid; missing cells (buffer shorter than `width*height`) become `0.0`. |
| `flatten_grid(image)` | Grid → row-major flat buffer, in the ragged length each row actually has. |
| `box_downscale(image, out_w, out_h)` | Area-average downscale: each output cell is the mean of the source block it maps to. |
| `bilinear_downscale(image, out_w, out_h)` | Bilinear-interpolated downscale using half-pixel-center sampling. |
| `resize_for_hash(image, size)` | `box_downscale(image, size, size)` — a square average, e.g. `8` for aHash or `32` for pHash's pre-DCT stage. |
| `resize_for_dhash(image, hash_w, hash_h)` | `box_downscale(image, hash_w + 1, hash_h)` — one extra column so `hash_w*hash_h` adjacent-column comparisons are possible. |
| `integral_image(image)` | `(H+1)`×`(W+1)` summed-area table; `I[y+1][x+1]` is the sum of `image[0..y][0..x]`. |
| `box_sum(integral, r0, c0, r1, c1)` | Inclusive rectangular-region sum from an integral image in O(1), clamped to the source grid's bounds. |
| `downscale_flat(flat, in_w, in_h, out_w, out_h)` | `reshape_to_grid` → `box_downscale` → `flatten_grid` in one call — the flat-buffer entry point for callers who never want the nested form. |

Worked against `tests/mojo/test_image_resize.mojo`'s real assertions: a 4x4 "ramp" grid where
`pixel(r,c) = r*4 + c` (values `0..15`) box-downscaled to 2x2 gives a top-left cell of `2.5`
(mean of `0,1,4,5`) and a bottom-right cell of `12.5` (mean of `10,11,14,15`) — `downscale_flat` on
the flattened version of the same ramp reproduces `2.5` and `12.5` at the matching flat indices,
confirming the flat entry point and the grid path agree. `bilinear_downscale` on a constant 8x8 image
of `137.0` returns a constant 3x3 image still exactly `137.0` — interpolating between equal samples
can't move the value. On a 3x3 ramp (`0..8`), `integral_image`'s full-grid `box_sum` is `36.0`
(`0+1+...+8`), a single-cell query at `(1,1)` is `4.0` (the ramp's own center value), and the
bottom-right 2x2 region (`4,5,7,8`) sums to `24.0`. `resize_for_dhash` on a 16x16 image with
`hash_w=hash_h=8` returns an 8-row, **9**-column grid — the extra column is the point: dHash compares
each pixel to its right-hand neighbor, so `hash_w` columns of comparisons need `hash_w + 1` columns
of pixels.

## `image_palette`: dominant colors, entropy, saturation, and monochrome detection

| Function | What it does |
| --- | --- |
| `dominant_palette_rgb255(flat_rgb, width, height, levels, top_k)` | Quantizes RGB into a `levels`×`levels`×`levels` bin cube, then returns the top `top_k` bins by pixel count as `[r,g,b,weight]` groups (mean channel values, weight = share of valid pixels), most-populous first. |
| `palette_size_estimate(flat_rgb, width, height, levels, min_weight)` | Count of quantization bins whose normalized weight is `>= min_weight`. |
| `palette_entropy(flat_rgb, width, height, levels)` | Shannon entropy in bits over the quantized-bin histogram. |
| `mean_saturation_rgb255(flat_rgb, width, height)` | Mean HSV saturation across all valid pixels, in `[0, 1]`. |
| `warm_color_ratio_rgb255(flat_rgb, width, height, min_saturation)` | Fraction of pixels whose hue is warm (`h <= 90°` or `h >= 330°`) and whose saturation clears `min_saturation`. |
| `palette_contrast_score(flat_rgb, width, height, levels, top_k)` | Pixel-weighted pairwise WCAG contrast ratio across the top-`top_k` dominant colors, normalized from the `[1, 21]` WCAG scale to `[0, 1]`. |
| `accent_color_hex(flat_rgb, width, height, levels)` | The single dominant color (from the top 5) that scores highest on `saturation * (0.25 + 0.75 * weight)`, as `"#RRGGBB"`. |
| `is_monochrome_palette(flat_rgb, width, height, levels, min_weight, max_mean_saturation)` | `True` if mean saturation is at or below `max_mean_saturation`, **or** if `palette_size_estimate` at `min_weight` finds at most one significant bin. |

Quantization bins on `levels`: each channel is divided into `levels` equal-width buckets of
`256 / levels`, and the three per-channel bucket indices combine into one of `levels³` bins — so
`levels=4` (as in every worked example below) means a `64`-value-wide bucket per channel and `64`
total bins.

Worked against `tests/mojo/test_image_palette.mojo`'s real assertions, on a 2x2 image with three red
pixels (`200,20,20`) and one blue pixel (`20,20,200`), `levels=4`: `dominant_palette_rgb255(...,
top_k=2)` returns the red bin first — `[200.0, 20.0, 20.0, 0.75]` — then blue —
`[20.0, 20.0, 200.0, 0.25]`. At `min_weight=0.2` both bins qualify, so `palette_size_estimate`
returns `2`; raise the bar to `min_weight=0.3` and only red's `0.75` clears it, so the count drops to
`1`. `palette_entropy` on the same two-bin split (`p = 0.75, 0.25`) is `0.8112781244591328` bits —
`-(0.75·log2 0.75 + 0.25·log2 0.25)`, below the `1.0`-bit ceiling a 50/50 split would hit. Both red
and blue happen to share the same `(max-min)/max = 0.9` saturation here, so `mean_saturation_rgb255`
is exactly `0.9` regardless of the 3:1 mix. `warm_color_ratio_rgb255(..., min_saturation=0.25)` is
`0.75`: the three red pixels clear both the hue and saturation gates, the one blue pixel (hue near
240°) does not.

**`palette_contrast_score` measures luminance separation, not how different two colors look.** Red
and blue are about as far apart in hue as two colors can be, but `palette_contrast_score(...,
levels=4, top_k=2)` on this fixture is only `0.040792744995753236` — barely above `0`. The reason is
in the formula: it feeds each color's WCAG relative luminance (`rgb_to_luminance`, the standard
`0.2126R + 0.7152G + 0.0722B` weighting over linearized sRGB) into `contrast_ratio`, and this
particular red and blue are both fairly dark, non-extreme colors — their luminances work out to
about `0.128` and `0.048`, giving a WCAG contrast ratio near `1.8:1` against a scale that runs to
`21:1` for true black-on-white. A palette can be visually vivid and still score low here if none of
its dominant colors are far apart in *lightness*.

`accent_color_hex` on the same fixture picks red: its score is
`0.9 * (0.25 + 0.75*0.75) = 0.73125` against blue's `0.9 * (0.25 + 0.75*0.25) = 0.39375`, so it
returns `"#C81414"` (`200, 20, 20` in hex). For `is_monochrome_palette`, a genuinely gray 2x2 fixture
(each pixel has `r == g == b`, so saturation is `0.0` everywhere) is monochrome purely on the first
check — `mean_saturation_rgb255 <= max_mean_saturation` short-circuits before `palette_size_estimate`
is even called. The red/blue fixture fails that first check (`0.9 > 0.15`) and then fails the second
too, since `palette_size_estimate` at `min_weight=0.2` still finds `2` significant bins — so it
correctly reports `False`.

`image_palette` builds on RGB→HSV conversion, hex formatting, and the WCAG luminance/contrast
formulas from the separate `color` and `color_science` modules (`from color import RGB, rgb_to_hsv,
rgb_to_hex` / `from color_science import contrast_ratio, rgb_to_luminance`) rather than
reimplementing that math — this page documents `image_palette`'s own eight functions only.

## Verification

`image_morphology`, `image_resize`, and `image_palette` each have a real, hand-written pinned test
suite at `tests/mojo/test_image_morphology.mojo`, `tests/mojo/test_image_resize.mojo`, and
`tests/mojo/test_image_palette.mojo` — every numeric value in the worked examples above is a literal
assertion from one of those three files, not an independently derived estimate. `image_ops`'s pinned
suite lives in `tests/mojo/test_wave51.mojo` alongside that wave's recommender-system and
epidemiology tests. Separately, each module also has an auto-generated smoke test under
`mojo/tests/libs/test_image_*.mojo` that calls every function once with fixed fixture data and checks
only that the result is finite or non-negative-length — those files provide coverage, not the pinned
values used here.

**Next:** see [Runtime library catalog](runtime-library-catalog.md) for the full function/module
index across the engine, including this family's four sibling computer-vision modules
(`image_features`, `image_similarity`, `image_quality`, `image_regions`), or
[Engine catalog](catalog.md) for how these modules map to callable engines.
