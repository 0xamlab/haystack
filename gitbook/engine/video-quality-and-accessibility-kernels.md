---
icon: closed-captioning
description: Per-pixel worst-case WCAG contrast for caption overlays, dominant/mean color analysis, a composite no-reference frame-quality score, and clip-to-clip duplicate detection, all over flat row-major video frame buffers.
---

# Video quality and accessibility kernels

Four modules that each take the same flat, row-major `[frame][row][col][channel]` buffer —
`width`, `height`, and `channels` describe one frame, and the buffer's total length divided by
that stride tells every function how many complete frames it holds — and answer a different
question about the clip. `video_quality` asks whether the clip is watchable at all: a composite
of per-frame sharpness/exposure/entropy and brightness-flicker stability, with no reference video
involved. `video_color` and `video_accessibility` both ask whether text drawn over the video would
be readable, but from two different, deliberately non-interchangeable angles: `video_color` looks
at the clip's dominant or mean color, `video_accessibility` looks at the worst single pixel.
`video_similarity` compares two clips frame-by-frame for dedup, cache-reuse, and regression
checks. None of the four declares a struct — every function returns a plain `Float64`, `Bool`,
`String`, `List[Float64]`, or `List[Int]`, and frame sampling (when a module doesn't need every
frame) always picks evenly-spaced indices that include the first and last frame.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# 3-frame, 2x2 RGB clip: frame 0 is uniformly dark (20,20,20), frame 1 mixes
# 3 dark pixels with 1 bright (220,220,220) pixel, frame 2 is uniformly bright.
clip = [20.0, 20.0, 20.0] * 4 + [20.0, 20.0, 20.0] * 3 + [220.0, 220.0, 220.0] + [220.0, 220.0, 220.0] * 4

runtime.execute("video_accessibility", "frame_min_preferred_text_contrast_for_video",
                [clip, 2, 2, 3, 1])["result"]
# 1.3713058806238527 -- frame 1's worst-case black/white contrast, held down by
# the single bright pixel even though 3 of its 4 pixels are dark

runtime.execute("video_accessibility", "sampled_video_wcag_safe_ratio",
                [clip, 2, 2, 3, 3, 16.0, False])["result"]
# 0.6666666666666666 -- frame 1 fails the 4.5:1 AA threshold for 16pt normal
# text; frames 0 and 2 (uniform) pass, so 2 of 3 sampled frames are safe
```

## The modules

| Module | What it does |
| --- | --- |
| `video_accessibility` | Per-pixel worst-case black/white WCAG contrast for a frame or a bottom subtitle band, sampled across a clip, plus the resulting pass ratio and backplate-needed verdict. |
| `video_color` | Frame and clip mean RGB, a quantized dominant color, mean HSV saturation, warm-frame ratio, consecutive-frame color drift, and a dominant-color-based preferred text contrast/color. |
| `video_quality` | Per-frame image-quality sampling, brightness-flicker and temporal-stability scoring, and the weighted composite `video_quality_score` / `is_usable_video` usability gate. |
| `video_similarity` | Frame-paired duplicate scoring (SSIM/NCC/stability), dHash Hamming distance, a temporal (intensity + motion + length) signature distance, and the combined `clip_duplicate_score_flat` / `is_duplicate_clip_flat` dedup verdict. |

## Shared frame convention

All four modules import `frame_count_from_flat` from `video_ops` rather than reimplementing frame
bookkeeping — buffer length ÷ `width*height*channels`, trailing partial values ignored. Three of
the four also import `sample_frame_indices` (`video_accessibility`, `video_color`, `video_quality`
— everywhere a `sample_frames`/`sample_frames_n` parameter appears): evenly spaced picks that
always include frame 0 and the last frame — asking for 1 sample returns just frame 0, asking for
at least as many samples as there are frames returns every frame. `video_quality` and
`video_similarity` additionally import `frame_mean_intensity` / `frame_mean_intensities`
(per-pixel channel average, then per-frame pixel average) for their brightness/intensity math.
`channels` fewer than 3 degrades gracefully everywhere: 1-channel buffers are read as grayscale
(`g = b = r`), 2-channel as grayscale plus a second channel treated as green (`b = g`). Every
function guards `frame_index` out of range or a non-positive `width`/`height`/`channels` by
returning zeros rather than raising.

## `video_color` vs. `video_accessibility`: two different definitions of "preferred text color"

Both modules expose a `preferred_text_..._for_video`-shaped function, and both return the same
kind of answer — a black/white choice and a WCAG contrast ratio — but they compute it from
opposite ends of the clip's color distribution, and the two are not interchangeable:

* **`video_color.preferred_text_contrast_for_video` / `preferred_text_color_for_video`** quantize
  every sampled pixel into a `levels^3`-bin RGB histogram (`dominant_clip_color_rgb255`), pick the
  single most-populous bin, and compute contrast against *that one dominant color*. This is a
  mean-ish, clip-level heuristic — cheap, and representative when the frame's background is fairly
  uniform.
* **`video_accessibility.frame_preferred_text_color_for_video` / `frame_min_preferred_text_contrast_for_video`**
  (and their `sampled_*` / `subtitle_band_*` variants) scan *every pixel* in the frame or band and
  track the worst-case (minimum) contrast a single black or white choice would achieve against any
  of them, then keep whichever of black/white has the higher worst-case floor. The module's own
  docstring calls this out explicitly: "Unlike mean-colour heuristics, it evaluates the minimum
  contrast achieved by a single global black/white text colour across all pixels."

The difference is exactly what the mixed clip above demonstrates: `video_color`'s dominant-color
view of frame 1 would see mostly-dark pixels and likely call it safe, while
`video_accessibility.frame_min_preferred_text_contrast_for_video(clip, 2, 2, 3, 1)` returns
`1.3713058806238527` — held down to failing by the single bright outlier pixel that a dominant-bin
histogram can wash out. `video_accessibility` is the module built for backplate/safety decisions;
`video_color`'s contrast helpers exist for lighter-weight preview and creative-review use, where a
representative color is good enough and a single stray pixel shouldn't force a backplate.

## `video_accessibility`: worst-case contrast, backplates, and subtitle bands

| Function | Signature | What it returns |
| --- | --- | --- |
| `frame_min_preferred_text_contrast_for_video` | `(flat_frames, width, height, channels, frame_index)` | Best worst-case black/white contrast for one frame. |
| `frame_preferred_text_color_for_video` | same | `"#000000"` or `"#FFFFFF"`, whichever wins that worst-case. |
| `sampled_video_min_text_contrast` | `(..., sample_frames_n)` | Minimum preferred contrast across evenly sampled frames. |
| `sampled_video_wcag_safe_ratio` | `(..., sample_frames_n, font_size_pt, is_bold)` | Fraction of sampled frames whose preferred contrast clears the WCAG AA threshold for that font size/weight. |
| `needs_text_backplate_for_video` | same | `True` when that ratio is below `1.0` — any sampled frame fails. |
| `subtitle_band_min_preferred_text_contrast_for_video` | `(..., sample_frames_n, band_rows)` | Same worst-case contrast, restricted to the bottom `band_rows` rows of each sampled frame. |
| `subtitle_band_preferred_text_color_for_video` | same | Black/white color for that bottom band. |
| `sampled_subtitle_band_wcag_safe_ratio` | `(..., sample_frames_n, band_rows, font_size_pt, is_bold)` | Pass ratio restricted to the subtitle band. |
| `subtitle_band_needs_backplate_for_video` | same | `True` when any sampled band fails AA. |

The WCAG threshold itself comes from `color_check.wcag_aa_required_contrast(font_size_pt,
is_bold)`: `3.0` for large text (`font_size_pt >= 18.0`, or bold text `>= 14.0`), `4.5` otherwise —
the standard WCAG 2 AA large/normal-text split. `frame_min_preferred_text_contrast_for_video` and
`contrast_ratio` both come straight from `color_science.mojo`'s sRGB-to-linear WCAG relative
luminance and `(lighter + 0.05) / (darker + 0.05)` contrast formula, so every number below is
reproducible from those two functions alone.

**Worked example**, using the same 3-frame mixed-caption clip as above (frame 0 uniformly
`(20,20,20)`, frame 1 three `(20,20,20)` pixels plus one `(220,220,220)`, frame 2 uniformly
`(220,220,220)`), independently re-derived from `color_science.rgb_to_luminance` /
`contrast_ratio`:

| Frame | Worst-case contrast | Preferred color |
| --- | --- | --- |
| 0 (uniform dark) | `18.422536070011546` | `#FFFFFF` |
| 1 (mixed) | `1.3713058806238527` | `#FFFFFF` |
| 2 (uniform bright) | (not pinned by the test; independently derived: `15.313870010129614`) | `#000000` |

At `font_size_pt=16.0, is_bold=False` the required contrast is `4.5`. Frames 0 and 2 clear it,
frame 1 (`1.37`) does not, so `sampled_video_wcag_safe_ratio(clip, 2, 2, 3, 3, 16.0, False) =
2/3 = 0.6666666666666666` and `needs_text_backplate_for_video` is `True`. Restricting to the
bottom subtitle band (`band_rows=1`, so only the last row of each `2x2` frame is scanned) produces
the identical `1.3713058806238527` / `2/3` numbers here, because that bottom row happens to
already contain both the dark and bright pixel of frame 1 — a smaller, differently-shaped clip
would not necessarily agree between the whole-frame and band-restricted variants.

## `video_color`: mean/dominant color, saturation, warmth, and drift

| Function | Signature | What it returns |
| --- | --- | --- |
| `frame_mean_rgb255` | `(flat_frames, width, height, channels, frame_index)` | Mean `[r, g, b]` of one frame. |
| `frame_mean_rgb_series` | `(flat_frames, width, height, channels)` | Mean `[r, g, b]` per frame, concatenated. |
| `clip_mean_rgb255` | same | Mean `[r, g, b]` across every pixel in every frame. |
| `dominant_clip_color_rgb255` | `(..., levels, sample_frames_n)` | `[r, g, b, weight]` of the most-populous bin in a `levels^3` RGB histogram over sampled frames. |
| `clip_mean_saturation_rgb255` | `(flat_frames, width, height, channels)` | Mean HSV saturation over every clip pixel. |
| `warm_frame_ratio_rgb255` | `(..., min_saturation)` | Fraction of frames whose mean-RGB hue is warm (`hue <= 90` or `>= 330`) and saturated enough. |
| `color_drift_score_rgb255` | `(flat_frames, width, height, channels)` | Mean consecutive-frame RGB Euclidean distance, normalized by `255*sqrt(3)` into `[0, 1]`. |
| `preferred_text_contrast_for_video` | `(..., levels, sample_frames_n)` | Best black/white WCAG contrast against the *dominant* clip color. |
| `preferred_text_color_for_video` | same | Black/white choice for that dominant color. |

**Worked example**, a 3-frame `2x2` RGB clip (frame 0 all `(200,20,20)`, frame 1 three
`(200,20,20)` pixels plus one `(20,20,200)`, frame 2 all `(20,20,200)`), from the pinned test:

* `frame_mean_rgb255(clip, 2, 2, 3, 1) = [155.0, 20.0, 65.0]` — the one outlier pixel pulls the
  frame mean a quarter of the way from red toward blue.
* `clip_mean_rgb255(clip, 2, 2, 3) = [125.0, 20.0, 95.0]`.
* `dominant_clip_color_rgb255(clip, 2, 2, 3, 4, 3) = [200.0, 20.0, 20.0, 0.5833333333333334]` — of
  the 12 sampled pixels, 7 land in the `(200,20,20)`-ish bin and 5 in `(20,20,200)`, so the red bin
  wins with weight `7/12`.
* `preferred_text_contrast_for_video(clip, 2, 2, 3, 4, 3) = 5.8888921644276735`, color `#FFFFFF`
  — computed only against that dominant `(200,20,20)` color, not against the outlier blue pixels.
* `clip_mean_saturation_rgb255(clip, 2, 2, 3) = 0.9` (every pixel is a fully-saturated primary-ish
  color at this scale).
* `warm_frame_ratio_rgb255(clip, 2, 2, 3, 0.25) = 2/3` — frames 0 and 1 have warm (reddish) mean
  hues above the saturation floor; frame 2's mean is blue, which is not warm by the `<=90 or
  >=330` degree test.
* `color_drift_score_rgb255(clip, 2, 2, 3) = 0.2881752638568445` — the mean of the two
  frame-to-frame RGB distances (`45*sqrt(2)` then `135*sqrt(2)`) divided by the maximum possible
  distance `255*sqrt(3)`.

## `video_quality`: a composite no-reference usability score, not a reference-based metric

Despite sitting in a "video quality" family, none of these functions compare against a reference
or ground-truth video — there is no second clip anywhere in the signatures. `video_quality_score`
is a **no-reference** composite built from three pieces, each already grounded in another module:

1. **`average_frame_quality`** samples frames (`sample_frame_indices`), reshapes each to a 2D grid,
   and calls `image_quality.quality_score` on it — itself `0.4*sharpness + 0.3*exposure +
   0.3*entropy`, all in `[0, 1]`.
2. **`temporal_stability_score`** is `1 / (1 + brightness_flicker_score/48)`, where
   `brightness_flicker_score` is the mean absolute frame-to-frame change in mean brightness
   (0-255 units, no sampling — every frame is used).
3. **`coverage`** is a coarse binary term: `1.0` if the clip has more than one frame, `0.7` for a
   single-frame clip.

`video_quality_score = clamp01(0.7*frame_quality + 0.2*stability + 0.1*coverage)`, and
`is_usable_video` is just that score compared against a caller-supplied `min_quality` floor.

| Function | Signature | What it returns |
| --- | --- | --- |
| `frame_quality_series` | `(flat_frames, width, height, channels, sample_frames)` | Per-sampled-frame `image_quality.quality_score` values. |
| `average_frame_quality` | same | Mean of that series; `0.0` for an empty clip. |
| `brightness_flicker_score` | `(flat_frames, width, height, channels)` | Mean absolute brightness change between every pair of consecutive frames, in 0-255 units. |
| `temporal_stability_score` | same | `1/(1 + flicker/48)`, clamped to `[0, 1]`. |
| `video_quality_score` | `(..., sample_frames)` | The `0.7/0.2/0.1` weighted composite above, in `[0, 1]`. |
| `is_usable_video` | `(..., sample_frames, min_quality)` | `video_quality_score >= min_quality`. |

**Worked example**, from the pinned test's "bad" clip (`4x4`, 1 channel: frame 0 uniformly `10.0`,
frame 1 twelve pixels `10.0` plus four `200.0`, frame 2 uniformly `200.0`): frame mean intensities
are `10.0, 57.5, 200.0`, so `brightness_flicker_score = mean(|57.5-10|, |200-57.5|) =
mean(47.5, 142.5) = 95.0` exactly, and `temporal_stability_score = 1/(1+95/48) =
0.3356643356643356` — severe flicker, so stability is pulled down near a third. Against a "good"
clip built from a smooth 3-frame gradient, the test asserts (without pinning exact values) that
`video_quality_score(good) > video_quality_score(bad)`, the good clip's score is `>= 0.35`, the bad
clip's is `< 0.35`, and `average_frame_quality(good) > average_frame_quality(bad)` — i.e. the
ordering, not just the pass/fail gate, holds all the way down to the per-frame quality term.

A single-frame clip has no frame pairs, so `brightness_flicker_score = 0.0` and
`temporal_stability_score = 1.0` unconditionally, while `coverage` drops to `0.7` — a fixed
`0.1 * 0.3 = 0.03` quality-score penalty for having only one frame to judge stability from,
regardless of how that one frame actually looks.

## `video_similarity`: clip-to-clip duplicate detection, paired by frame index

Every function here takes two clips (`flat_a`, `flat_b`) sharing `width`/`height`/`channels`, and
pairs them by **position**, not by content search — frame `i` of `a` is always compared against
frame `i` of `b`, up to `min(frame_count_a, frame_count_b)`. There is no alignment search, no
dynamic time warping, and no attempt to find the best-matching offset between two clips that start
at different points.

| Function | Signature | What it returns |
| --- | --- | --- |
| `frame_duplicate_scores` | `(flat_a, flat_b, width, height, channels)` | Per-paired-frame `image_similarity.duplicate_score_flat` (0.55·SSIM + 0.25·NCC + 0.20·low-diff-stability), one entry per aligned frame. |
| `average_frame_duplicate_score` | same | Mean of that series; `1.0` if both clips are empty, `0.0` if only one is. |
| `frame_hash_hamming_series` | same | Per-paired-frame `perceptual_hash.dhash_flat` Hamming distance, `0..64`. |
| `average_frame_hash_hamming` | same | Mean of that series; `64.0` (maximally different) if only one clip is empty, `0.0` if both are. |
| `temporal_signature_distance` | same | `0.55·intensity_gap + 0.30·motion_gap + 0.15·frame_count_gap_ratio`, in `[0, 1]`; motion comes from `video_features.scene_change_scores` on each clip. |
| `clip_duplicate_score_flat` | same | `0.55·avg_frame_score + 0.25·(1 - avg_hash/64) + 0.20·(1 - temporal_distance)`, in `[0, 1]`. |
| `is_duplicate_clip_flat` | `(..., min_score)` | `clip_duplicate_score_flat >= min_score`. |

**Worked example**, from the pinned test: comparing a base `4x4` grayscale 3-frame clip against
*itself* gives `frame_duplicate_scores = [1.0, 1.0, 1.0]`, `average_frame_hash_hamming = 0.0`,
`temporal_signature_distance = 0.0`, and `clip_duplicate_score_flat = 1.0`. Comparing that same
base clip against a "near" clip (every pixel shifted by 2-12 intensity units) keeps
`clip_duplicate_score_flat > 0.9`, while comparing it against a "far" clip (inverted brightness and
a different pixel pattern per frame) drops the score below `0.7` — the test asserts the ordering
(`near_score > far_score`, `near_hash <= far_hash`, `near_temporal < far_temporal`) rather than
pinning exact values for the near/far cases, and `is_duplicate_clip_flat(base, far, 4, 4, 1, 0.9)`
is `False` at a strict `0.9` threshold.

## Edge-case behavior

* **Out-of-range `frame_index` or non-positive dimensions** — every function across all four
  modules returns zeros (`0.0`, `[0,0,0]`, or `"#000000"` as applicable) rather than raising.
* **Empty-vs-empty in `video_similarity`** reads as "identical": `average_frame_duplicate_score`
  and `clip_duplicate_score_flat` both return `1.0`, `average_frame_hash_hamming` and
  `temporal_signature_distance` return `0.0`. **Empty-vs-non-empty** reads as "maximally
  different": duplicate score `0.0`, hash distance `64.0` (the maximum possible for a 64-bit
  hash), temporal distance `1.0`.
* **`sample_frame_indices` at the boundary**: requesting exactly 1 sample always returns just
  frame 0; requesting at least as many samples as the clip has frames returns every frame in
  order; requesting more frames than fit is not an error, it silently saturates to "all frames."
* **`channels` below 3** degrade gracefully everywhere in this family: 1-channel is read as
  grayscale (`g = b = r`), 2-channel treats the second channel as green with blue copied from it —
  there is no dedicated grayscale code path, the RGB math just collapses.

## Verification

`video_accessibility`, `video_color`, `video_quality`, and `video_similarity` each have two test
files. `mojo/tests/libs/test_video_*.mojo` are auto-generated coverage smoke tests — one call per
function against a fixed synthetic clip, checking only that the result is finite (or, for
bool/string returns, that the call doesn't raise); they pin no specific numeric output. The real,
hand-written suites are `tests/mojo/test_video_accessibility.mojo`,
`test_video_color.mojo`, `test_video_quality.mojo`, and `test_video_similarity.mojo` — these pin
exact expected values (contrast ratios to 9+ significant figures, RGB triples, saturation, drift
scores) and are what every worked number in this page comes from. Every pinned value quoted above
was independently re-derived from the real formulas in `color_science.mojo` (sRGB linearization,
WCAG contrast), `color_check.mojo` (`wcag_aa_required_contrast`), and the four modules' own source,
not copied from the test file without checking — the frame-0/frame-1 contrast values, the
dominant-color weight, and the color-drift score all reproduced to the same precision the tests
assert.

**Next:** see the [Runtime library catalog](runtime-library-catalog.md) for every module and
function this instance ships, including the `image_quality`, `image_similarity`, `color_science`,
`color_check`, and `perceptual_hash` modules these four build on.
