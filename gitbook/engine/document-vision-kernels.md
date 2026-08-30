---
icon: scanner
description: Pixel-level document image processing -- Otsu and adaptive binarization, skew and scan-quality scoring, and projection-based segmentation into text lines, columns, density grids, and table-likeness scores.
---

# Document vision and layout kernels

Two modules for turning a scanned or photographed document page into structured geometry, before any
character gets recognized. `document_vision` is the lower layer: it takes a raw grayscale pixel buffer
and produces a clean binary ink mask (via global Otsu or local adaptive thresholding), row/column
foreground projections, a content bounding box, a skew angle, and a composite scan-quality score.
`document_layout` is built directly on top of it — it literally imports `horizontal_projection` and
`vertical_projection` from `document_vision` — and turns those projections into higher-level structure:
contiguous text-line bands, text columns, a foreground-density grid, and two scalar scores for whether a
page looks multi-column or table-like. Nothing in either module recognizes characters, words, or fonts;
this is the geometric preprocessing a real OCR or layout model would consume, not OCR itself, and there
is no separate "figure" or "image region" detector — the actual scope is text bands, columns, density
cells, and a table-likeness heuristic built from those same bands.

All functions take flat, row-major `List[Float64]` pixel buffers plus explicit `width`/`height`, and
every mask function agrees on one convention: a pixel is foreground ink if its value is `>= fg_threshold`
(binarized masks emit `255.0` for ink, `0.0` for paper). Boxes are always `[x0, y0, x1, y1, area]`,
inclusive corners, and — this is a real, load-bearing detail from the source, not a simplification —
`area` is the actual foreground-pixel count inside the box, never `(x1-x0+1)*(y1-y0+1)`; a ragged-edged
paragraph reports its true ink count, not the area of the rectangle that encloses it.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# an 8x8 mask with two horizontal ink bands: row 2 spans x=1..6, row 5 spans x=2..5
mask = [255.0 if (y == 2 and 1 <= x <= 6) or (y == 5 and 2 <= x <= 5) else 0.0
        for y in range(8) for x in range(8)]

runtime.execute("document_layout", "text_line_boxes_flat", [mask, 8, 8, 128.0, 1])["result"]
# [1, 2, 6, 2, 6, 2, 5, 5, 5, 4]
# two boxes, flattened: [x0=1,y0=2,x1=6,y1=2,area=6], [x0=2,y0=5,x1=5,y1=5,area=4]

runtime.execute("document_layout", "line_count_flat", [mask, 8, 8, 128.0, 1])["result"]
# 2
```

## The modules

| Module | What it does |
| --- | --- |
| `document_layout` | Projection-driven layout segmentation: contiguous text-line and text-column boxes and counts, a per-cell foreground density grid, and scalar multi-column and table-likeness scores. |
| `document_vision` | Document binarization and scan diagnostics: global Otsu and local-adaptive thresholding, row/column foreground projections, content bounding box, skew-angle estimate, and a composite scan-quality score. |

## `document_vision`: from grayscale pixels to a clean mask and a quality number

| Function | What it does |
| --- | --- |
| `otsu_threshold_flat(flat, width, height)` | Global Otsu threshold in 0-255 space: builds a 256-bin histogram and picks the threshold that maximizes between-class variance `weight_bg * weight_fg * (mean_bg - mean_fg)^2`. |
| `binarize_otsu_flat(flat, width, height)` | Runs `otsu_threshold_flat`, then emits `255.0` for any pixel `<= threshold` (dark ink), `0.0` otherwise. |
| `adaptive_mean_binarize_flat(flat, width, height, window_radius, bias)` | Local-mean thresholding via an integral image (`box_sum`/`integral_image` from `image_resize`): a pixel is ink if it is `<= local_window_mean - bias`, so uneven lighting across the page doesn't blow out one side. |
| `horizontal_projection(mask_flat, width, height, fg_threshold)` | Foreground pixel count per row. |
| `vertical_projection(mask_flat, width, height, fg_threshold)` | Foreground pixel count per column. |
| `mask_content_bbox_flat(mask_flat, width, height, fg_threshold)` | `[x0, y0, x1, y1, area]` bounding box of all foreground pixels; returns `[]` if the mask has none. |
| `skew_angle_estimate_flat(mask_flat, width, height, fg_threshold)` | Least-squares slope, in degrees, of each row's ink-centroid `x` against its `y` — a rotation estimate for deskewing. |
| `horizontal_text_score_flat(mask_flat, width, height, fg_threshold)` | Row-peakiness in `[0, 1]`: the row projection's coefficient of variation divided by the sum of the row and column projections' coefficients of variation. Higher means ink is concentrated into a few strong rows (horizontal text), not columns. |
| `document_scan_quality_flat(flat, width, height)` | Composite `[0, 1]` score: `0.45 * quality_score` (from `image_quality`, sharpness/exposure/entropy) `+ 0.20 * coverage_score + 0.20 * skew_score + 0.15 * horizontal_text_score_flat`. |

### Binarizing a two-line document and reading it back apart

The same `doc8` grid used in the pinned test suite — an 8×8 grayscale page, paper at `240.0`, ink at
`20.0` on row 2 (columns 1-6) and row 5 (columns 2-5) — walks cleanly through every function in this
module:

```python
doc = [20.0 if (y == 2 and 1 <= x <= 6) or (y == 5 and 2 <= x <= 5) else 240.0
       for y in range(8) for x in range(8)]

runtime.execute("document_vision", "otsu_threshold_flat", [doc, 8, 8])["result"]
# 20.0 -- ten pixels at 20.0 vs. fifty-four at 240.0; every threshold from 20 through
# 239 scores identically, and the scan keeps the first (lowest) one it finds

mask = runtime.execute("document_vision", "binarize_otsu_flat", [doc, 8, 8])["result"]
runtime.execute("document_vision", "mask_content_bbox_flat", [mask, 8, 8, 128.0])["result"]
# [1, 2, 6, 5, 10] -- x0=1, y0=2, x1=6, y1=5, area=10 (6 + 4 ink pixels)

runtime.execute("document_vision", "horizontal_projection", [mask, 8, 8, 128.0])["result"]
# [0.0, 0.0, 6.0, 0.0, 0.0, 4.0, 0.0, 0.0]  -- rows 2 and 5 carry all the ink
```

`otsu_threshold_flat` deserves the note above because it is easy to assume Otsu always lands between
the two populations: reading the loop in `document_vision.mojo`, `weight_background` only changes when
`hist[threshold]` is non-zero, so `sum_background`/`mean_background` are frozen across every threshold
value that has zero pixels in it, and the between-class variance score is therefore identical across the
whole gap — the code keeps the *first* threshold to reach the maximum (`score > best_score`, strict),
which for a bimodal image is the value of the dark cluster itself, `20.0`, not a value in between.

`skew_angle_estimate_flat` fits a line through each row's ink centroid. On the diagonal mask from the
pinned test — a single foreground pixel at `(x, y) = (y, y)` for `y = 1..4` — every row's centroid
equals its own row index, giving `slope = 1.0` and `atan2(1.0, 1.0) * 180 / pi = 45.0` degrees exactly.
Run on the two horizontal bands above instead, both bands share the same centroid (`x = 3.5`), so the
fitted slope is `0.0` — a horizontal document reports zero skew, which is the input `document_scan_quality_flat`
rewards.

`horizontal_text_score_flat` on that same `mask` computes the row projection's coefficient of variation
(`std/mean` of `[0,0,6,0,0,4,0,0]`, `≈1.7776`) over the sum of the row and column CVs (column CV
`≈0.6633`), giving `1.7776 / (1.7776 + 0.6633) ≈ 0.7283` — comfortably above the pinned test's `> 0.55`
threshold, and correctly higher than the `0.5` tie-break the function falls back to only when both
projections are perfectly flat.

`document_scan_quality_flat` combines four signals: the `image_quality.quality_score` of the raw
grayscale grid (sharpness from Laplacian variance, exposure distance from mid-gray, Shannon entropy —
weight `0.45`), a coverage score built from `mask_content_bbox_flat`'s area ratio (`10/64 = 0.15625`,
scaled against a `0.18` target since it's under the `0.45` "too much ink" ceiling, giving
`0.15625/0.18 ≈ 0.868` — weight `0.20`), the skew score (`1.0` at zero skew — weight `0.20`), and
`horizontal_text_score_flat` itself (`≈0.728` — weight `0.15`). The pinned test only asserts the
qualitative shape of this composite (`doc_quality > 0` and `doc_quality` for real content beats a blank
page's), because `quality_score`'s own sharpness term depends on a Laplacian convolution's border
handling in `image_ops`, outside this page's two modules — but three of its four weighted terms are
exact numbers derivable straight from `document_vision.mojo` alone, as shown above.

## `document_layout`: projections turned into boxes, grids, and two page-type scores

| Function | What it does |
| --- | --- |
| `text_line_boxes_flat(mask_flat, width, height, fg_threshold, min_row_ink)` | Scans rows top to bottom; a row with `>= min_row_ink` foreground pixels extends the current band (or starts one), a row below that threshold closes it. Returns `[x0,y0,x1,y1,area]` per band. |
| `line_count_flat(mask_flat, width, height, fg_threshold, min_row_ink)` | `len(text_line_boxes_flat(...)) // 5` — a derived count, not a separately computed value. |
| `column_boxes_flat(mask_flat, width, height, fg_threshold, min_col_ink)` | The same band-scan as `text_line_boxes_flat`, transposed: scans columns left to right. |
| `column_count_flat(mask_flat, width, height, fg_threshold, min_col_ink)` | `len(column_boxes_flat(...)) // 5`, same derivation pattern as `line_count_flat`. |
| `text_density_grid_flat(mask_flat, width, height, fg_threshold, grid_rows, grid_cols)` | Splits the mask into a `grid_rows x grid_cols` grid and returns each cell's foreground fraction in `[0, 1]`, row-major. |
| `multi_column_score_flat(mask_flat, width, height, fg_threshold)` | Scores `[0, 1]` for a two-balanced-columns-with-a-gutter layout: tries every vertical split, and for each scores how balanced the two sides' ink densities are, how empty the split itself is (the gutter), and how strong the weaker side is, then keeps the best split. |
| `table_like_score_flat(mask_flat, width, height, fg_threshold)` | Scores `[0, 1]` for repeated row *and* column bands: `0.8 * (structure) + 0.2 * (active-cell ratio over a 4x4 density grid)`, where `structure` is halved unless the mask has at least 2 row bands *and* 2 column bands. |

`min_row_ink`/`min_col_ink` are both floored at `1` internally (`_normalized_min_count`) — passing `0`
or a negative value is silently treated as `1`, not as "any row counts" or an error.

### A worked two-column page: exact split, not just a threshold check

The pinned test only asserts `multi_column_score_flat(...) > 0.65` for a mask with two 2-pixel-wide ink
columns (`x=1..2` and `x=5..6`, both spanning `y=1..6`) on an 8×8 grid, separated by a 2-column gutter.
Tracing `multi_column_score_flat`'s own loop against that mask's vertical projection
(`[0, 6, 6, 0, 0, 6, 6, 0]`) by hand: the split at `x=3` puts `12` ink pixels on each side, and the code
divides each side by a different span — `left_density = left_mass / (split * height) = 12/24 = 0.5`,
`right_density = right_mass / ((width-split-1) * height) = 12/32 = 0.375` — because the left region is
narrower (3 columns) than the right (4 columns) at this particular split. The gutter itself is empty
(`valley_density = 0`), so `balance = 1 - |0.5-0.375|/0.5 = 0.75`, `valley_separation = 1.0`, and
`strength = min(0.375, 0.5)/0.35`, clamped to `1.0`. The split at `x=4` is the mirror image and scores
identically. Both beat every other split (the ones landing inside an ink band score `0` because the
"gutter" they'd cut through is itself full of ink), so the function returns exactly **`0.75`** — a
concrete number, not just "above 0.65."

```python
twocol = [255.0 if 1 <= y <= 6 and (1 <= x <= 2 or 5 <= x <= 6) else 0.0
          for y in range(8) for x in range(8)]

runtime.execute("document_layout", "column_boxes_flat", [twocol, 8, 8, 128.0, 2])["result"]
# [1, 1, 2, 6, 12, 5, 1, 6, 6, 12]  -- two columns, each [x0,y0,x1,y1,area], area 12 = 2x6

runtime.execute("document_layout", "multi_column_score_flat", [twocol, 8, 8, 128.0])["result"]
# 0.75
```

### The density grid, cell by cell

`text_density_grid_flat` on the two-line `docmask8` from the earlier example, split into a 2×2 grid,
gives four exact fractions the pinned test checks to `1e-9`:

```python
runtime.execute("document_layout", "text_density_grid_flat", [mask, 8, 8, 128.0, 2, 2])["result"]
# [0.1875, 0.1875, 0.125, 0.125]
```

The top-left and top-right cells (rows 0-3) each catch 3 of row 2's 6 ink pixels (`3/16 = 0.1875`); the
bottom-left and bottom-right cells (rows 4-7) each catch 2 of row 5's 4 ink pixels (`2/16 = 0.125`) —
the row 5 band starts at `x=2`, so it straddles the grid's vertical midline (`x=4`) evenly too.

### Table-likeness needs bands in both directions, not just density

`table_like_score_flat`'s pinned test builds a 9×9 grid of 3×3 ink blocks arranged in a 3×3 checkerboard
(rows and columns 1-2, 4-5, 7-8 all lit) and asserts it scores `> 0.8`, strictly higher than the same
two-line `docmask8` used above. Reading the formula explains why the gap is so large rather than just
confirming it is positive: `docmask8` has 2 horizontal bands (`row_bands = 2`, clearing the minimum) but
only **1** vertical band, not 2 — its vertical projection `[0,1,2,2,2,2,1,0]` never drops back to zero
between columns 1 and 6, so the whole span counts as one continuous column band, not two separate ones.
That single shortfall (`col_bands = 1 < 2`) triggers the `structure *= 0.35` penalty and caps
`docmask8`'s own score around `0.145` (`structure = 0.5*0.5 + 0.5*0.0 = 0.25`, penalized to `0.0875`,
plus `0.2 *` a `6/16` active-cell ratio). The checkerboard mask clears both band-count minimums
(`row_bands = col_bands = 3`), skips the penalty entirely (`structure = 1.0`), and adds a high
active-cell ratio from its own 4×4 density grid on top — the two conditions compound rather than trading
off, which is why the gap between the two scores is so wide.

## Verification

`mojo/tests/libs/test_document_layout.mojo` and `mojo/tests/libs/test_document_vision.mojo` are the
auto-generated coverage smoke tests — each calls every function once and checks only that the result is
finite or non-negative-length, printing the value but asserting nothing about it. The real, hand-written
numeric suites live in `tests/mojo/test_document_layout.mojo` and `tests/mojo/test_document_vision.mojo`;
every exact number in this page — the two text-line boxes, the two column boxes, all four density-grid
cells, `multi_column_score_flat`'s `0.75`, the `45.0`-degree skew estimate, the `otsu_threshold_flat`
result of `20.0`, the row/column projection values, and the content bounding box — is asserted there
to `1e-9` (or exactly, for integer box coordinates), not merely printed. `document_scan_quality_flat`
and `table_like_score_flat`'s tests assert relative orderings (`doc_quality > blank_quality`,
`table_score > doc_score`) rather than exact values, which this page follows by presenting their
component terms precisely instead of inventing a composite number the test suite itself doesn't pin.

**Next:** see the [Runtime library catalog](runtime-library-catalog.md) for every module and function,
or [Declared capabilities](capabilities.md) for what these two modules report about determinism and cost.
