---
icon: palette
description: RGB/HSL/HSV color-space conversion, CIE colorimetry (delta-E, Lab-to-LCH, CCT, CRI, whiteness), and WCAG text-contrast accessibility checking, layered as three modules of increasing specificity.
---

# Color science kernels

Three modules for color, in increasing order of how much they assume about what the color is *for*.
`color` is space conversion with no opinion about meaning — RGB, HSL, HSV, hex, interpolation,
plain Euclidean distance. `color_science` adds colorimetry: CIE76 delta-E, Lab-to-LCH, gamma-correct
sRGB relative luminance, WCAG contrast ratio, correlated color temperature, metamerism index, von
Kries chromatic adaptation, a CRI approximation, and CIE whiteness index. `color_check` sits on top
of both — it imports `RGB`/`hex_to_rgb`/`rgb_to_hex` from `color` and `contrast_ratio`/
`rgb_to_luminance` from `color_science` — and turns that arithmetic into a decision: does this
foreground/background pair pass WCAG AA for this font size, and if a background is a whole image
rather than one flat color, what text color and contrast does its dominant cluster imply.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# hex_to_rgb is exact for byte-aligned hex: 0x33/0xFF, 0x66/0xFF, 0x99/0xFF
rgb = runtime.execute("color", "hex_to_rgb", ["#336699"])["result"]
# RGB(r=0.2, g=0.4, b=0.6)

# same color, read as WCAG contrast against white text
runtime.execute("color_check", "wcag_contrast_ratio_hex", ["#336699", "#FFFFFF"])["result"]
# 5.997786839657083 -- comfortably above the 4.5 AA threshold for normal-size text
```

## The modules

| Module | What it does |
| --- | --- |
| `color` | RGB/HSL/HSV structs and lossless-round-trip conversions between them, hex encode/decode, linear interpolation, Euclidean color distance, luminance-weighted grayscale, and RGB complement. |
| `color_check` | WCAG 2.x text-contrast accessibility: gamma-correct relative luminance, contrast ratio, the AA pass/fail threshold table, hex-string validation, black-vs-white text recommendation, and dominant-background extraction from a flat RGB image buffer for image-overlay text decisions. |
| `color_science` | CIE colorimetry primitives: CIE76 delta-E, Lab-to-LCH decomposition, gamma-correct sRGB luminance, WCAG contrast ratio, a simplified AA pass/fail, approximate correlated color temperature, metamerism index, von Kries chromatic adaptation, a CRI approximation, and CIE whiteness index. |

## `color_check` is accessibility contrast checking, not reference-chart verification

The name invites a reading of "check a captured color against a reference chart" — the kind of
consistency check a color-calibration workflow runs against an X-Rite ColorChecker or similar target.
The real module, read function by function in `mojo/engine/color_check.mojo`, is nothing like that:
every one of its sixteen functions is WCAG 2.x text-on-background accessibility contrast, either
against an explicit background color or against the dominant cluster of a flat image buffer. There is
no reference-swatch input, no calibration target, and no notion of a "correct" color to check
against — `color_check` answers "is this text readable on this background," not "does this captured
color match this known standard." The actual colorimetric machinery for comparing two colors against
each other — CIE76 delta-E, metamerism index — lives one module over, in `color_science`.

## `color`: space conversion with no opinion about meaning

All eleven functions and three structs (`RGB`, `HSL`, `HSV`) work in a self-contained, dependency-free
file (`mojo/engine/color.mojo`) with no imports from the other two modules. `rgb_to_hsl`/`hsl_to_rgb`
and `rgb_to_hsv`/`hsv_to_rgb` are round-trip pairs — `tests/mojo/test_wave23.mojo`'s hand-written
`test_color` confirms `hsl_to_rgb(rgb_to_hsl(RGB(0.3, 0.6, 0.9)))` and the HSV equivalent both recover
the original channels to within `0.01`, and pins several exact values along the way:

| Call | Result |
| --- | --- |
| `rgb_to_hex(RGB(1.0, 0.0, 0.0))` | `"#FF0000"` |
| `color_distance(RGB(0,0,0), RGB(1,1,1))` | `sqrt(3) ≈ 1.7320508` |
| `grayscale(RGB(1.0, 0.0, 0.0)).r` | `0.299` (the R weight in `0.299R + 0.587G + 0.114B`) |
| `complement(RGB(1.0, 0.0, 0.0))` | `RGB(0.0, 1.0, 1.0)` — cyan |
| `clamp01(-0.5)`, `clamp01(1.5)` | `0.0`, `1.0` |

`hex_to_rgb` fails closed rather than raising: a hex string that is too short, or that contains a
non-hex-digit anywhere in its six-character body, returns `RGB(0.0, 0.0, 0.0)` (black) instead of an
error. `color_check`'s own `_validated_hex_to_rgb` wraps `hex_to_rgb` with an explicit length and
digit check that `raises` instead, precisely because bare `color.hex_to_rgb` cannot distinguish "input
was black" from "input was malformed" — a caller that needs to know which happened must validate
before calling `color.hex_to_rgb`, or call through `color_check`, not trust its return value alone.

## `color_science`: colorimetry primitives, hand-verified

`tests/mojo/test_wave93.mojo` (`test_color_science`) and `tests/mojo/test_color_science.mojo`
both hand-verify this module's twelve functions against the textbook formulas — not the auto-generated
single-call smoke test that exists alongside them in `mojo/tests/libs/test_color_science.mojo` (which
only checks each return value is finite). Reproducing a few by hand against the real source in
`mojo/engine/color_science.mojo` confirms the pinned values:

- **`delta_e_76(50, 25, 10, 60, 30, 15)`** — CIE76 Euclidean distance in Lab space, `sqrt(10² + 5² +
  5²) = sqrt(150) ≈ 12.247449`.
- **`lab_to_lch_c(3.0, 4.0) = 5.0`** — chroma is `sqrt(a² + b²)`, the familiar 3-4-5 triangle.
- **`lab_to_lch_h(0.0, -1.0) = 270.0`** — `atan2(-1, 0) = -90°`, wrapped into `[0, 360)` by adding 360.
- **`rgb_to_luminance(0.5, 0.5, 0.5) ≈ 0.21404114048223255`** — gamma-corrected, not `0.5`: sRGB's
  `((c + 0.055) / 1.055) ^ 2.4` linearization for `c > 0.04045` pulls mid-gray's *linear* luminance
  well below its *encoded* value.
- **`contrast_ratio(0.0, 1.0) = 21.0`** — `(lighter + 0.05) / (darker + 0.05)`, the maximum possible
  WCAG contrast ratio (pure black against pure white), independent of argument order.
- **`whiteness_index_cie(95.0, 0.310, 0.320, 0.313, 0.329) = 112.7`** — CIE whiteness
  `Y + 800(xₙ-x) + 1700(yₙ-y) = 95 + 800(0.003) + 1700(0.009) = 95 + 2.4 + 15.3`.

Several formulas here are explicitly simplified approximations, not full CIE-standard implementations,
and the docstrings say so plainly: `color_temperature_approx` is "simplified CCT ≈ 6500 * (B/R)", not
the McCamy or Robertson polynomial a color-science library would use, and `cri_from_delta_e` is
"CRI ≈ 100 - 4.6*ΔE (simplified)" rather than the full 14-sample-color TCS methodology behind the real
CIE Ra metric. Treat both as fast, order-of-magnitude estimates for routing/ranking decisions, not as
values to report against a lighting-industry CRI or CCT spec.

## Two `wcag_aa_pass`-shaped functions that are not interchangeable

`color_science.wcag_aa_pass(contrast_ratio_val, font_size_pt)` and `color_check`'s pass/fail family
both implement WCAG AA thresholding, but they are different functions with different contracts, not
one shared implementation called from two places:

| | `color_science.wcag_aa_pass` | `color_check.wcag_text_pass_*` |
| --- | --- | --- |
| Return type | `Float64` (`1.0` / `0.0`) | `Bool` |
| Bold text | not modeled — only `font_size_pt >= 18.0` lowers the bar to `3.0` | `wcag_aa_required_contrast(font_size_pt, is_bold)` also lowers the bar at `>= 14.0` when `is_bold` |
| Inputs | a precomputed contrast ratio | raw colors (hex or 0-255 RGB) — computes the ratio itself |

`color_science.wcag_aa_pass(3.0, 14.0)` returns `0.0` (fails — 14pt regular text needs `4.5`), while
`color_check.wcag_text_pass_hex` on colors yielding that same `3.0` ratio at `14.0pt, is_bold=True`
returns `True`, because bold text drops the required contrast to `3.0` starting at 14pt rather than
18pt. Calling `color_science.wcag_aa_pass` for a bold-text decision silently applies the *regular*-text
threshold — it has no `is_bold` parameter to get right or wrong.

## `color_check`'s dominant-background path, worked from its own test fixture

`tests/mojo/test_color_check.mojo`'s `_red_dominant_image()` builds a 2×2 flat RGB buffer — three
red pixels `(200, 20, 20)` and one blue pixel `(20, 20, 200)` — and quantizes it into `levels=4` bins
per channel (`bin_w = 256/4 = 64`). All three red pixels land in the same bin and the blue pixel lands
in a different one, so the histogram's best bin has count 3 out of 4 valid pixels:

```python
img = [200,20,20, 200,20,20, 200,20,20, 20,20,200]  # width=2, height=2, RGB triples
bg = runtime.execute("color_check", "dominant_background_rgb255", [img, 2, 2, 4])["result"]
# [r, g, b, weight] -> [200.0, 20.0, 20.0, 0.75]
```

`weight = 0.75` is the dominant bin's pixel count (`3`) divided by total valid pixels (`4`) — not a
color-similarity score. `dominant_background_hex` on the same buffer returns `"#C81414"` (`200, 20,
20` in hex), and `dominant_background_contrast_ratio_hex(img, 2, 2, 4, "#FFFFFF")` reports
`5.8888921644276735` — white text against that dominant red passes the default `4.5` AA threshold,
while `"#000000"` against the same background does not (`dominant_background_wcag_pass_hex(...,
"#000000", 12.0, False)` is `False`), matching `preferred_text_color_for_image` choosing `"#FFFFFF"`.
The image helpers never look at every pixel individually when computing the mean — only pixels whose
own bin matches the single winning bin are averaged, so a background with two nearly-tied clusters can
have its reported color pulled toward whichever bin's running sum happens to win ties (the scan keeps
the first bin index it sees at the highest count; later bins need to be strictly greater to replace it).

## Edge cases

- **`hex_to_rgb` (in `color`) never raises** — malformed input silently becomes black, as described
  above. `color_check`'s `_validated_hex_to_rgb` is the module's own answer to that gap, and every
  `color_check` function that accepts a hex string routes through it, so malformed hex reaches the
  caller as a raised `Error`, not a silently-wrong black.
- **`levels <= 0`** passed to any `color_check` image function is clamped to `1` bin internally
  (`_dominant_background_stats`), which collapses the whole image into a single histogram bucket — the
  "dominant" color becomes the mean of every pixel, not a mode.
- **`color_temperature_approx(r, b)`** divides by `r` with no zero guard; a pure-blue or black pixel
  (`r = 0.0`) is not handled specially by the function itself.
- **`wcag_aa_required_contrast`**'s bold/size interaction is an OR, not independent thresholds:
  `font_size_pt >= 18.0` *or* (`is_bold` *and* `font_size_pt >= 14.0`) drops the bar to `3.0`; anything
  else — including 17pt bold — stays at `4.5`.

## Verification notes

`mojo/tests/libs/test_color.mojo`, `test_color_check.mojo`, and `test_color_science.mojo` are the
auto-generated coverage smoke tests for this family: each calls every function once with fixed
placeholder arguments and checks only that numeric results are finite, or that string/list results
don't crash the call — they do not pin expected values. The real, hand-written correctness tests live
in `tests/mojo/test_wave23.mojo` (`test_color`, 30 assertions against exact and near-exact
expected values), `tests/mojo/test_wave93.mojo` (`test_color_science`), and the dedicated
`tests/mojo/test_color_check.mojo` / `test_color_science.mojo` files. `color_check.mojo`'s own source
(`from color_science import contrast_ratio, rgb_to_luminance`) confirms `wcag_relative_luminance_rgb255`
and `wcag_contrast_ratio_rgb255` are thin wrappers that normalize 0-255 input to 0-1 and then call
`color_science`'s functions directly — a real composition, not a duplicated reimplementation, and
`test_color_check.mojo`'s pinned mid-gray value (`0.21404114048223255` for `rgb_to_luminance(0.5, 0.5,
0.5)`) matches `test_color_science.mojo`'s pinned value for the identical call. Every pinned number
quoted on this page traces to one of those files or was independently recomputed from the formulas in
the three `.mojo` source files.

**Next:** see [Runtime library catalog](runtime-library-catalog.md) for the full function-count index,
or [Engine catalog](catalog.md) for how `color`, `color_check`, and `color_science` are exposed as
part of the broader engine surface.
