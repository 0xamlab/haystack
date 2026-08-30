---
icon: image
description: Sobel edge/saliency features and color histograms, deterministic blur/exposure/entropy quality scores, pixel-level similarity metrics (MSE, PSNR, SSIM), and Otsu-based foreground region boxes over flat pixel buffers.
---

# Image feature and quality kernels

Four modules answer the questions a serving stack needs answered *before* it spends an expensive
vision-model call on an image: is this frame sharp enough and bright enough to bother with
(`image_quality`), what does it visually contain and where is the interesting part
(`image_features`), is it a near-duplicate of one already processed (`image_similarity`), and where
exactly is the foreground subject or block of ink (`image_regions`). All four are zero-Python-import
Mojo — `image_quality.mojo`'s docstring names this explicitly as feeding the "Vision Gate," the
cheap reject/route layer that decides whether to ask for a clearer image, skip it, or pay for a real
model call. Every function is a plain deterministic formula over pixel buffers: no model weights, no
randomness, and (`box_iou` aside, which takes `List[Int]`) no type but `Float64` in or out. Grayscale
functions take either a `List[List[Float64]]` grid (values 0-255) or a row-major flat buffer plus
`width`/`height` for the runtime's calling convention; `image_features`' color functions take a flat
*interleaved* RGB buffer (`flat_rgb[i*3 + {0,1,2}]`, each channel 0-255).

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# 4x4 grayscale frame, flattened row-major, 0-255 -- flat background with two
# isolated bright pixels
frame = [
    30, 30, 30, 30,
    30, 220, 30, 30,
    30, 30, 30, 30,
    30, 30, 30, 220,
]

runtime.execute("image_quality", "blur_score_flat", [frame, 4, 4])["result"]
# 153425.0 -- variance of the Laplacian response; isolated bright pixels against a
# flat field read as very sharp (high blur_score), not blurry

runtime.execute("image_quality", "quality_score_flat", [frame, 4, 4])["result"]
# 0.5460996852346243 -- composite 40% sharpness + 30% exposure + 30% entropy usability score
```

## The modules

| Module | What it does |
| --- | --- |
| `image_features` | Cheap grayscale/RGB visual features for routing and crop targeting: Sobel edge magnitude and density, an RGB color histogram plus three histogram-comparison metrics, top-3 dominant-color extraction, and a coarse saliency grid pointing at an image's most edge-dense region. |
| `image_quality` | Deterministic reject/route signals for the Vision Gate: variance-of-Laplacian blur score, mean brightness, contrast (pixel std-dev), 256-bin Shannon entropy, a dominant-bucket uniformity fraction, MAD-based noise estimate, over/under-exposure and near-blank flags, and a composite 0-1 usability score. |
| `image_similarity` | Pixel-level comparison between two same-declared-size grayscale flat buffers: MSE, MAE, PSNR (dB, capped at 99 for identity), normalized cross-correlation, a global (whole-image, not windowed) SSIM approximation, a changed-pixel diff fraction, crop-local similarity, and a weighted duplicate-detection score. |
| `image_regions` | Otsu-based foreground segmentation and box geometry: dark-ink foreground masks, connected-component bounding boxes sorted by descending pixel count, the single largest foreground box, the most salient grid cell expressed as a box, inclusive crop extraction, and box IoU. |

## `image_features`: edges, color histograms, and saliency

| Function | What it does |
| --- | --- |
| `sobel_magnitude(image)` | Per-pixel `sqrt(gx² + gy²)` gradient magnitude; valid-mode convolution, output is `(H-2) x (W-2)`. |
| `edge_density(image, mag_threshold)` | Fraction of Sobel-magnitude pixels exceeding `mag_threshold`. |
| `edge_density_flat(flat, width, height, mag_threshold)` | `edge_density` from a flat buffer, via `reshape_to_grid`. |
| `color_histogram(flat_rgb, width, height, bins_per_channel)` | Normalized `bins³` RGB histogram; index = `(r_bin·bins + g_bin)·bins + b_bin`. `bins_per_channel` is clamped to `[1, 64]`. |
| `histogram_intersection(a, b)` | `Σ min(aᵢ, bᵢ)` — `1.0` for identical normalized histograms, `0.0` for disjoint ones. |
| `histogram_chi_square(a, b)` | `½ Σ (aᵢ-bᵢ)²/(aᵢ+bᵢ)` — `0.0` when identical, unbounded above. |
| `histogram_correlation(a, b)` | Pearson correlation of the two histograms, in `[-1, 1]`; `0.0` if either is flat. |
| `dominant_colors(flat_rgb, width, height, levels)` | Top-3 histogram bins by weight, decoded back to bin-center `[r, g, b, weight]`, `levels` bins per channel. |
| `saliency_grid(image, grid_rows, grid_cols)` | `grid_rows x grid_cols` map of mean Sobel edge energy per cell. |
| `most_salient_cell(saliency)` | Flattened `row*cols + col` index of the highest-energy cell; `-1` if the grid is empty. |
| `most_salient_cell_flat(flat, width, height, grid_rows, grid_cols)` | `saliency_grid` + `most_salient_cell` from a flat buffer; `grid_rows`/`grid_cols` are each clamped to `MAX_SALIENCY_DIM = 1024`. |

**A partial vertical edge, worked by hand.** A 5×5 frame with columns 0-1 at intensity `0` and
columns 2-4 at `255` — one hard edge, not a gradient — puts the step inside two of the three
3-wide Sobel windows and leaves the third window (columns 2-4, both sides at `255`) flat:

```python
edge = [
    0, 0, 255, 255, 255,
    0, 0, 255, 255, 255,
    0, 0, 255, 255, 255,
    0, 0, 255, 255, 255,
    0, 0, 255, 255, 255,
]
runtime.execute("image_features", "edge_density_flat", [edge, 5, 5, 500.0])["result"]
# 0.6666666666666666 -- 6 of the 9 valid-mode (3x3) output pixels exceed the threshold
```

`sobel_x`'s middle column carries weight `0`, so the gradient magnitude at each output cell depends
only on the *leftmost* and *rightmost* columns of its 3-wide window, not the one in between — window
columns `[0,1,2]` and `[1,2,3]` both straddle the edge (magnitude `1020.0`), window `[2,3,4]` sits
entirely inside the bright region (magnitude `0.0`). `saliency_grid(grid, 1, 3)` on the same frame
returns `[[1020.0, 1020.0, 0.0]]`, and `most_salient_cell` picks index `0` — the *first* cell tied
for the maximum, since the comparison is strict `>`, not `>=`.

**Color histogram indexing, worked by hand.** Two pixels — one reddish `(200, 10, 10)`, one greenish
`(10, 200, 10)` — through `color_histogram(flat_rgb, 2, 1, 2)` (2 bins per channel, `bin_width =
128.0`):

```python
flat_rgb = [200, 10, 10, 10, 200, 10]
runtime.execute("image_features", "color_histogram", [flat_rgb, 2, 1, 2])["result"]
# [0.0, 0.0, 0.5, 0.0, 0.5, 0.0, 0.0, 0.0] -- bin 2 (greenish) and bin 4 (reddish) each 0.5

runtime.execute("image_features", "dominant_colors", [flat_rgb, 2, 1, 2])["result"]
# [64.0, 192.0, 64.0, 0.5,    <- greenish bin center, weight 0.5 (found first, index 2)
#  192.0, 64.0, 64.0, 0.5,    <- reddish bin center, weight 0.5 (index 4)
#  64.0, 64.0, 64.0, 0.0]     <- no third color exists; weight 0.0 is a placeholder, not a real bin
```

The greenish pixel maps to `rb=0, gb=1, bb=0` → index `(0·2+1)·2+0 = 2`; the reddish pixel maps to
`rb=1, gb=0, bb=0` → index `4`. `dominant_colors` always emits exactly 3 entries regardless of how
many distinct colors the image actually has — with only two occupied bins here, the third pick finds
every remaining bin at `0.0`, decodes bin index `0` (the first one scanned) to its bin center
`(64.0, 64.0, 64.0)`, and reports weight `0.0`. A caller that doesn't check the weight would read
that third entry as "a third, low-weight color" rather than "no third color."

Comparing that mixed histogram against an all-reddish one (`[0,0,0,0,1.0,0,0,0]`, both pixels
`(200,10,10)`):

```python
mixed = [0.0, 0.0, 0.5, 0.0, 0.5, 0.0, 0.0, 0.0]
all_red = [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
runtime.execute("image_features", "histogram_intersection", [mixed, all_red])["result"]
# 0.5
runtime.execute("image_features", "histogram_chi_square", [mixed, all_red])["result"]
# 0.3333333333333333
runtime.execute("image_features", "histogram_correlation", [mixed, all_red])["result"]
# 0.6546536707079772
```

## `image_quality`: blur, brightness, entropy, and a composite score

| Function | What it does |
| --- | --- |
| `blur_score(image)` / `blur_score_flat` | Variance of the 4-neighbour Laplacian response (`[[0,1,0],[1,-4,1],[0,1,0]]`); higher is sharper. |
| `is_blurry(image, threshold)` | `blur_score(image) < threshold` (the docstring suggests `~100` as a starting threshold for 0-255 images). |
| `brightness_mean(image)` / `brightness_flat` | Mean pixel value, 0-255. |
| `contrast_std(image)` / `contrast_flat` | Population standard deviation of pixel values. |
| `shannon_entropy(image)` / `entropy_flat` | 256-bin intensity entropy in bits, `0` (flat) to `8` (maximally spread). |
| `is_near_blank(image, std_threshold)` | `contrast_std(image) < std_threshold`. |
| `uniformity(image)` | Fraction of pixels in the single most-populated 16-bin bucket. |
| `noise_estimate(image)` | `1.4826 x` the median absolute deviation of the Laplacian response — a robust (outlier-resistant) sigma estimate. |
| `is_over_or_under_exposed(image, low, high)` | `True` if `brightness_mean` falls outside `[low, high]`. |
| `quality_score(image)` / `quality_score_flat` | Composite `0.4 * sharp + 0.3 * exposure + 0.3 * entropy`, clamped to `[0, 1]` (see below). |

**The composite score, worked by hand.** For the sharp 4×4 frame from the opening example (a flat
`30`-intensity field with two isolated `220`-intensity pixels), the 2×2 valid-mode Laplacian response
is `[[-760.0, 190.0], [190.0, 0.0]]` (mean `-95.0`), giving `blur_score = 153425.0`. `brightness_mean
= 53.75`, so `exposure = 1 - |53.75 - 128| / 128 = 0.419921875`. The 256-bin histogram has only two
occupied bins (fourteen pixels at `30`, two at `220`), so `shannon_entropy = -(0.875·log₂0.875 +
0.125·log₂0.125) ≈ 0.5435644` bits, and `entropy/8 ≈ 0.0679455`. `sharp = blur/(blur+100) ≈
0.9993487`. Combining: `0.4·0.9993487 + 0.3·0.419921875 + 0.3·0.0679455 ≈ 0.5460997`, matching the
`quality_score_flat` call above. The `100.0` constant inside `sharp`'s denominator sets the scale at
which `blur_score` starts to matter: at `blur_score = 100` sharpness contributes exactly half its
maximum weight (`sharp = 0.5`), and the term saturates toward `1.0` only for scores well above that,
so `is_blurry`'s suggested `~100` threshold and `quality_score`'s own midpoint are the same number by
design, not coincidence.

{% hint style="info" %}
**`noise_estimate` and `blur_score` both start from the same Laplacian response but summarize it
differently.** `blur_score` is the response's *variance* — sensitive to a handful of large,
real edges, which is exactly what you want when asking "is this image sharp." `noise_estimate` is
`1.4826 x` the response's *median absolute deviation* — a robust statistic that a few strong edges
barely move, which is what you want when asking "how noisy is the flat background," independent of
whether the image also happens to contain sharp edges elsewhere.
{% endhint %}

## `image_similarity`: pixel-level comparison metrics

Unlike `image_features` and `image_quality`, none of these eight functions take a
`List[List[Float64]]` grid variant or call `reshape_to_grid` — every one operates directly on two
flat buffers over the declared `width x height` region, and a pixel past either buffer's end reads as
`0.0` rather than being refused. That is a real, load-bearing difference in how out-of-range input is
handled versus the other three modules in this family, not just an implementation detail: a caller
that declares a `width`/`height` larger than one of its two buffers gets a silent comparison against
zero-padding on the short side, not an error or an all-zero sentinel result.

| Function | What it does |
| --- | --- |
| `mean_squared_error_flat(a, b, width, height)` | Average squared pixel error. |
| `mean_abs_error_flat(a, b, width, height)` | Average absolute pixel error. |
| `psnr_flat(a, b, width, height, max_value)` | `10 * log10(max_value² / mse)` in dB; returns `99.0` (not `+inf`) when `mse <= 1e-12`. |
| `normalized_cross_correlation_flat(a, b, width, height)` | Pearson-style normalized cross-correlation, `[-1, 1]`. |
| `ssim_global_flat(a, b, width, height)` | Global SSIM approximation from whole-image mean/variance/covariance — not the windowed, multi-scale SSIM some libraries compute. |
| `diff_fraction_flat(a, b, width, height, diff_threshold)` | Fraction of pixels whose absolute difference exceeds `diff_threshold`. |
| `crop_region_similarity_flat(a, b, width, height, x0, y0, x1, y1)` | `1 - (MAE over the inclusive box) / 255`, clamped to `[0, 1]`. |
| `duplicate_score_flat(a, b, width, height)` | `0.55 * ssim + 0.25 * ncc_rescaled + 0.20 * (1 - diff_fraction@12.0)`, clamped to `[0, 1]`. |

**A near-duplicate pair, worked by hand.** Two 2×2 frames, `a = [10, 20, 30, 40]` and `b = [12, 18,
33, 42]` (every pixel off by 2-3 intensity levels):

```python
a = [10.0, 20.0, 30.0, 40.0]
b = [12.0, 18.0, 33.0, 42.0]

runtime.execute("image_similarity", "mean_squared_error_flat", [a, b, 2, 2])["result"]
# 5.25
runtime.execute("image_similarity", "psnr_flat", [a, b, 2, 2, 255.0])["result"]
# 40.92921057461954
runtime.execute("image_similarity", "ssim_global_flat", [a, b, 2, 2])["result"]
# 0.9874739440015203
runtime.execute("image_similarity", "duplicate_score_flat", [a, b, 2, 2])["result"]
# 0.9916076085309442
```

`duplicate_score_flat` composes the other functions: `ssim = 0.98747...`, `ncc = 0.98798...`
rescaled from `[-1,1]` to `[0,1]` as `0.99399`, and `diff_fraction_flat(a, b, 2, 2, 12.0) = 0.0`
(every pixel differs by less than `12.0`) so `stable = 1.0`. `0.55*0.98747 + 0.25*0.99399 +
0.20*1.0 = 0.99161`, comfortably in "these are the same image, lightly re-encoded" territory.
`psnr_flat`'s `99.0` cap only fires when `mse <= 1e-12`, essentially bit-identical buffers — this
pair, at `mse = 5.25`, is nowhere near it and gets the real logarithmic value instead.

## `image_regions`: composing Otsu, connected components, and box geometry

`image_regions` is the one module of the four that imports from outside this family:
`foreground_mask_otsu_flat` delegates straight to `document_vision.binarize_otsu_flat`, and
`connected_component_boxes_flat` delegates to `image_morphology.connected_components_4_flat` — both
documented on their own pages, not here. `saliency_box_flat` closes the loop with `image_features`,
calling that module's `saliency_grid`/`most_salient_cell` directly rather than re-implementing
saliency scoring.

| Function | What it does |
| --- | --- |
| `foreground_mask_otsu_flat(flat, width, height)` | Otsu-threshold dark-ink mask: `255.0` where a pixel is `<=` the computed threshold, `0.0` otherwise. |
| `connected_component_boxes_flat(mask_flat, width, height, fg_threshold, max_regions)` | 4-connected components (foreground = `value >= fg_threshold`) as flattened `[x0,y0,x1,y1,area]` boxes, sorted by descending `area`, capped at `max_regions`. |
| `largest_foreground_box_flat(flat, width, height)` | `foreground_mask_otsu_flat` piped into `connected_component_boxes_flat` with `fg_threshold=128.0`, `max_regions=1`. |
| `saliency_box_flat(flat, width, height, grid_rows, grid_cols)` | The most salient `image_features` grid cell, converted to a `[x0,y0,x1,y1,area]` box. |
| `extract_box_flat(flat, width, height, x0, y0, x1, y1)` | Inclusive crop as a flat list; out-of-range coordinates are clamped into bounds, a reversed box returns `[]`. |
| `box_iou(box_a, box_b)` | Intersection-over-union for two `[x0,y0,x1,y1,...]` boxes (`List[Int]`); extra trailing values (e.g. an `area` field) are ignored. |

**`largest_foreground_box_flat`'s two thresholds line up on purpose.** `foreground_mask_otsu_flat`
only ever emits `0.0` or `255.0` (`_foreground_mask_value` picks one of exactly two constants), and
`largest_foreground_box_flat` hardcodes `fg_threshold=128.0` when handing that mask to
`connected_component_boxes_flat` — a value that sits exactly between the mask's two possible outputs,
so it cleanly separates "dark, marked foreground" (`255.0 >= 128.0`) from "light, marked background"
(`0.0 < 128.0`) regardless of what the original grayscale intensities were. `connected_component_boxes_flat`
itself is generic — it works on any float mask against any threshold — but this particular composition
is tuned for the specific two-level output `foreground_mask_otsu_flat` always produces.

**Connected components, worked from a real test fixture.** `mojo/tests/libs/test_image_regions.mojo`
builds a 6×6 mask with two disconnected ink shapes: a 2-pixel vertical stroke and a 4-pixel L-shape.
Flood-filling that mask by hand (4-connectivity, `fg_threshold=128.0`) gives exactly two components —
the L-shape (pixels at `(3,1)`, `(4,1)`, `(3,2)`, `(3,3)`) and the stroke (`(0,1)`, `(0,2)`):

```python
mask = [
    0,   0, 0, 0,   0, 0,
    255, 0, 0, 255, 255, 0,
    255, 0, 0, 255, 0,   0,
    0,   0, 0, 255, 0,   0,
    0,   0, 0, 0,   0,   0,
    0,   0, 0, 0,   0,   0,
]
runtime.execute("image_regions", "connected_component_boxes_flat", [mask, 6, 6, 128.0, 4])["result"]
# [3, 1, 4, 3, 4,   0, 1, 0, 2, 2]
```

The first box is the L-shape: bounding box `(3,1)-(4,3)`, but `area=4` — the actual foreground pixel
*count*, not the bounding-box area (`(4-3+1)*(3-1+1) = 6`). The two only agree when a component
happens to fill its whole bounding box, which an L-shape by definition does not; reading `area` as a
box-fill fraction rather than a raw pixel count would silently misjudge every non-rectangular region.
The second box, the 2-pixel stroke, sorts second because `2 < 4`, even though `max_regions=4` would
have room for both plus two more if they existed.

**`box_iou` normalizes box order that the other box functions don't.** From the same test file,
`box_iou([0,0,2,2], [1,1,3,3])` computes intersection `2x2 = 4` over union `9 + 9 - 4 = 14`:

```python
runtime.execute("image_regions", "box_iou", [[0, 0, 2, 2], [1, 1, 3, 3]])["result"]
# 0.2857142857142857
```

`box_iou` swaps `x0/x1` and `y0/y1` internally if either box is stored reversed, so a genuinely
backwards box (`x1 < x0`) still produces the right IoU. `extract_box_flat` and
`crop_region_similarity_flat` do not do this — they clamp each coordinate into `[0, width)` /
`[0, height)` independently and then check `right < left or bottom < top`, so a box passed in with
`x1 < x0` returns an *empty* crop (`[]` or `0.0`) rather than the auto-corrected region `box_iou`
would compute for the same four numbers. The three functions accept the same `[x0,y0,x1,y1]` shape
but disagree on what a reversed one means.

## Guarantees and edge cases

* **Flat-buffer dimension guards are not uniform across the family.** `image_features` and
  `image_quality`'s `*_flat` functions all check `width <= 0 or height <= 0 or width > len(flat) //
  height` before reshaping, and return a degenerate `0.0`/`-1`/`False` rather than ever letting
  `reshape_to_grid` zero-pad a declared grid larger than the supplied pixels. `image_similarity`
  has no such guard — its `_pixel_value` helper returns `0.0` for any out-of-range index, so a
  mismatched `width`/`height` silently compares against zero-padding instead of being refused. See
  the `image_similarity` section above.
* **Two size ceilings bound wire-supplied allocations, and they don't cover every caller.**
  `image_features.color_histogram`/`dominant_colors` clamp `bins_per_channel`/`levels` to
  `MAX_COLOR_HISTOGRAM_BINS = 64` (bounding the `bins³` histogram array), and
  `most_salient_cell_flat` clamps `grid_rows`/`grid_cols` to `MAX_SALIENCY_DIM = 1024`. Neither
  `image_features.saliency_grid` (the non-flat variant) nor `image_regions.saliency_box_flat` applies
  that second ceiling — both pass `grid_rows`/`grid_cols` straight through to the grid allocation, so
  a caller reaching saliency scoring through `image_regions` rather than
  `image_features.most_salient_cell_flat` does not get the same allocation bound for free.
* **Non-finite RGB input is skipped, not rejected.** `color_histogram` checks each channel with
  `isnan`/`isinf` before calling `Int()` on it (an uncatchable abort otherwise) and simply skips that
  pixel — a buffer with a handful of `NaN` pixels produces a histogram normalized over the *remaining*
  finite pixels, not an error and not a zero-filled bin for the bad ones.
* **Degenerate-input sentinels are specific values, not `0.0` across the board.**
  `psnr_flat` returns `99.0` (not `+inf`) when `mse <= 1e-12`; `normalized_cross_correlation_flat`
  returns `1.0` if both images are flat *and* identical (`mae <= 1e-12`), else `0.0` if they're flat
  but different (e.g. solid black vs. solid white — genuinely uncorrelated by this metric, not
  undefined); `histogram_correlation` returns `0.0` for either flat histogram; `expert`-style ties in
  `dominant_colors`/`most_salient_cell` resolve to the *first* index scanned, since every comparison
  is strict `>`.

## Verification

All four `mojo/tests/libs/test_image_*.mojo` files are auto-generated coverage smoke tests: they call
every function once on small fixed fixtures (mostly a generic 5-element list, though
`test_image_similarity.mojo` and `test_image_regions.mojo` build purpose-shaped 6×6/8×8 mask and
"document" fixtures) and assert only that the result is finite or non-negative-length — none of the
four pin a specific expected number. `tests/mojo/test_wave*.mojo` has no hand-verified suites for
these four modules either. Every numeric example above was independently hand-traced against the
real formulas in `mojo/engine/image_features.mojo`, `image_quality.mojo`, `image_similarity.mojo`,
and `image_regions.mojo` (plus, for the connected-components and box-order examples, the real fixture
data inside `mojo/tests/libs/test_image_regions.mojo`), then cross-checked with an independent
line-by-line Python re-implementation of each formula — every number given can be reproduced by
re-running that arithmetic.

**Next:** see [Runtime library catalog](runtime-library-catalog.md) for every module and function, or
[Data quality](data-quality.md) for the equivalent reject/route scoring pattern applied to tabular
rather than image data.
