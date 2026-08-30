---
icon: clapperboard
description: Frame-level video primitives -- scene-change scoring, motion-region extraction, storyboard/keyframe selection, and the routing gate that decides how much of a clip is worth a model call, mirroring the image-side vision_gate.
---

# Video content and scene kernels

Six modules for deciding what a clip is worth looking at before spending a model call on it. A
video arrives as one flat, row-major `Float64` buffer -- frame after frame, each frame
`width * height * channels` values in the 0-255 intensity range -- and everything here starts from
that buffer and works out: how much changed between consecutive frames, where on screen it changed,
which frames are representative enough to stand in for a whole scene, and whether the clip is worth
a vision-model call at all or can be answered from cheaper signals instead. None of the six decodes
video or touches a codec; `video_ops` is the base layer every frame-level function in this family
calls, `video_features`, `video_regions`, and `video_storyboard` build progressively higher-level
facts on top of it, and `video_gate` is the routing policy that turns those facts into a single
action code -- deliberately built to mirror `vision_gate`, the same kind of router for still images.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

# 3 frames, 4x4 grayscale: frame0 flat 10.0, frame1 has a 2x2-pixel patch of 200.0,
# frame2 flat 200.0 -- the exact fixture test_video_features.mojo pins its numbers against
flat_frames = [10.0] * 16 + ([200.0] * 4 + [10.0] * 12) + [200.0] * 16

runtime.execute("video_features", "scene_change_scores", [flat_frames, 4, 4, 1])["result"]
# [0.18627450980392157, 0.5588235294117647] -- mean-abs-diff per transition, normalized by 255

runtime.execute("video_gate", "route_video_request",
                [0.8, 40.0, 0.1, 10.0, 0.3, False, 0])["result"]
# 4 -- vision_llm_keyframes: scene_cut_rate 0.3 clears the 0.20 keyframe threshold, so the
# router extracts keyframes instead of sending the full clip
```

## The modules

| Module | What it does |
| --- | --- |
| `video_features` | Temporal feature extraction on top of `video_ops`: normalized scene-change scores, scene-cut count/rate, the frame index with peak motion, and keyframe index selection capped at a frame budget. |
| `video_gate` | Deterministic routing policy for a whole video clip -- picks the cheapest valid action (cache reuse, feature answer, clearer-video request, keyframe OCR, keyframe vision call, or full-clip vision call) from cheap scalar signals. Its own docstring says it mirrors `vision_gate` for temporal media. |
| `video_ops` | The base layer: frame count from a flat buffer, per-frame mean intensity, frame-to-frame mean absolute difference, temporal mean/max diff and freeze-frame ratio across a clip, and evenly-spaced frame sampling. |
| `video_regions` | Motion-region extraction: binary diff masks between two frames, connected motion boxes (via `image_regions`'s connected-component labeling), per-transition motion-area ratios, the peak-motion box, and a temporal union motion box/coverage ratio across the whole clip. |
| `video_storyboard` | Scene segmentation built on `video_features`'s change scores: scene start/end frame indices, per-scene lengths and midpoint ("representative") frames, the longest scene, and a storyboard frame list capped at a target count. |
| `vision_gate` | The image-side counterpart `video_gate` mirrors -- the same action-code/intent-code routing shape, applied to a single still image's blur/brightness/entropy/edge-density signals instead of a clip's quality/motion/flicker/scene-cut signals. |

## `video_ops` is the dependency every other data module in this family shares

`video_features.scene_change_scores` calls `video_ops.frame_count_from_flat` and
`frame_mean_abs_diff` directly; `video_regions` imports `frame_count_from_flat` from `video_ops`
(and `connected_component_boxes_flat` from the separate `image_regions` module for the actual
connected-component labeling); `video_storyboard` imports `scene_change_scores` from
`video_features` and `frame_count_from_flat` from `video_ops`. So the real dependency chain is
`video_ops` → `video_features` → `video_storyboard`, with `video_regions` a sibling of
`video_features` that shares only the `video_ops` frame-counting base and reaches outside this
family into `image_regions` for box connectivity. `video_gate` and `vision_gate` sit apart from all
four: both take already-computed scalars (`motion_score`, `blur_score`, and so on) as arguments and
never call into `video_ops`, `video_features`, `video_regions`, or `video_storyboard` themselves --
the caller is expected to have already run those kernels and handed the router their outputs.

## A worked scene-change and keyframe example

The 4x4, 3-frame clip above is `tests/mojo/test_video_features.mojo`'s own
fixture: frame 0 is flat at intensity 10.0, frame 1 turns 4 of its 16 pixels to 200.0, and frame 2
is flat at 200.0. `frame_mean_abs_diff` compares the two frames' per-pixel means directly (grayscale,
so each pixel's "channel mean" is just its own value):

* Frame 0 → 1: 4 pixels flip by `|10 - 200| = 190`, the other 12 stay unchanged. Mean over all 16
  pixels: `4 * 190 / 16 = 47.5`.
* Frame 1 → 2: the 12 still-dark pixels flip by `190`, the 4 already-bright ones stay unchanged.
  Mean: `12 * 190 / 16 = 142.5`.

`scene_change_scores` normalizes both by 255: `[47.5/255, 142.5/255] = [0.18627..., 0.55882...]`.
Against `cut_threshold = 0.4`, only the second transition clears it, so `scene_cut_count = 1` and
`scene_cut_rate = 1/2 = 0.5`. `peak_motion_frame` reports `2` -- the later frame of the strongest
transition -- and `keyframe_indices(..., 0.4, 4)` returns `[0, 2]`: frame 0 always leads, frame 1
never crosses the cut threshold so it's skipped, and frame 2 is appended both because it crosses the
threshold and because it's the clip's last frame. Every one of these numbers is pinned exactly in
`tests/mojo/test_video_features.mojo` and reproduces the formulas in `mojo/engine/video_ops.mojo`
and `mojo/engine/video_features.mojo` by hand.

## A worked motion-region example

`tests/mojo/test_video_regions.mojo` builds a 5x5, 3-frame grayscale clip: frame 0 flat at 10.0;
frame 1 turns the 2x2 block `x∈[1,2], y∈[1,2]` to 200.0; frame 2 keeps that same block and also
flips the single corner pixel `(4, 4)`. With `diff_threshold = 50.0`:

* `frame_diff_mask_flat(..., 0, 1, 50.0)` marks exactly those 4 block pixels foreground (`255.0`);
  `motion_boxes_between_frames(..., 0, 1, 50.0, 4)` returns one box, `[1, 1, 2, 2, 4]` -- inclusive
  corners `(1,1)`-`(2,2)`, area `4`.
* `largest_motion_box_between_frames(..., 1, 2, 50.0)` -- comparing frame 1 to frame 2, where only
  the corner pixel changed -- returns `[4, 4, 4, 4, 1]`: a single-pixel box.
* `temporal_motion_area_series` reports the two transitions' motion coverage as `[4/25, 1/25]`.
* `peak_motion_box_flat` picks the transition with the most moving pixels (0→1, 4 pixels) and
  returns its box, `[1, 1, 2, 2, 4]`.
* `temporal_union_motion_box_flat` takes the OR of every transition's mask across the whole clip:
  the 2x2 block (4 pixels) plus the corner pixel (1 pixel) union to a bounding box of
  `[1, 1, 4, 4, 5]` -- note the *box* spans corners `(1,1)`-`(4,4)` even though only 5 of its 16
  contained pixels ever moved; `area` in this box is the true foreground pixel count (`5`), not the
  box's rectangular area (`16`).
* `motion_coverage_ratio_flat` reports `5/25 = 0.2` -- the fraction of all 25 pixels that moved at
  least once, which is exactly the union box's `area` field over `width * height`.

## A worked storyboard example

`tests/mojo/test_video_storyboard.mojo` uses a 4x4, 7-frame clip with three flat intensity plateaus:
frames 0-1 at 10.0, frames 2-4 at 120.0, frames 5-6 at 220.0. At `cut_threshold = 0.2`,
`scene_start_indices` returns `[0, 2, 5]`, `scene_end_indices` returns `[1, 4, 6]`, and
`scene_lengths_frames` returns `[2, 3, 2]` -- three scenes, the middle one longest.
`scene_representative_frames` returns `[0, 3, 5]`, the integer-divided midpoint of each `[start,
end]` span. `longest_scene_index` returns `1` (the 3-frame middle scene). `storyboard_frame_indices`
with `max_frames = 4` returns all three representative frames unchanged (`4 >= 3`); at
`max_frames = 2` it evenly samples two of the three representatives, `[0, 5]`; at `max_frames = 1`
it collapses to the single representative frame of the *longest* scene specifically, `[3]`, not
just the first or last representative -- `storyboard_frame_indices` calls `longest_scene_index`
for exactly this one-frame case rather than reusing its own even-sampling helper.

## `video_gate` mirrors `vision_gate`'s shape, not its logic

`video_gate.mojo`'s own docstring states the relationship directly: "This mirrors `vision_gate` for
temporal media." Both modules are pure branching logic with no pixel math (`video_gate` never calls
into `video_ops`, `video_features`, or `video_regions`; `vision_gate` never calls into any image
kernel), both return an `Int` action code in the same `0`-`5` range with the same first two slots
(`0 use_cache`, `1 answer_from_features`), and both accept the same shape of caller-supplied `Int`
`intent_code` (`0` general, `1` read-text, `2` simple pixel/temporal question, `3` compare/dedupe).
Reading both routers side by side against their real bodies, the mirror holds for the *shape* of the
decision tree but the two diverge in real ways past the shared opening:

| Step | `vision_gate.route_image_request` | `video_gate.route_video_request` |
| --- | --- | --- |
| 1 | duplicate → `0` | duplicate → `0` |
| 2 | `intent_code == 2` → `1` | `intent_code == 2` → `1` |
| 3 | `needs_clearer_image(blur_score, brightness)` → `2` | `needs_clearer_video(video_quality, flicker_score)` → `2` |
| 4 | `entropy < _ENTROPY_MIN` (near-blank) → `1` | *(no equivalent branch)* |
| 5 | `intent_code == 1`: OCR (`3`) if `edge_density > _TEXT_EDGE_MIN`, else low-res (`4`) | `intent_code == 1` → `3`, unconditionally |
| 6 | `edge_density > _CROP_EDGE_MIN` → `5` (crops), else `4` (low-res) | `should_extract_keyframes(...)` → `4`, else `is_mostly_static_video(...)` → `4`, else `5` |

Two concrete differences worth calling out: `vision_gate` has a dedicated near-blank branch
(low-entropy images are answered from features even when otherwise sharp and well-exposed) that
`video_gate` has no analogue for; and `vision_gate`'s text-intent branch re-checks `edge_density`
to decide between OCR and a plain low-res model call, while `video_gate`'s text-intent branch routes
straight to keyframe OCR (action `3`) with no equivalent secondary check. The two modules also take
different *kinds* of quality signal: `vision_gate.needs_clearer_image` works from two raw
per-image measurements (`blur_score`, `brightness`) computed elsewhere; `video_gate.needs_clearer_video`
takes a single already-aggregated `video_quality` scalar plus `flicker_score` -- video quality
scoring is assumed to happen upstream (in a module such as `video_quality`, outside this page's
scope) rather than being recomputed from raw signals inside the gate itself. So "mirrors" is accurate
as a design statement -- same action-code numbering convention, same duplicate/pixel-question/quality
short-circuit order, same pure-branching-logic shape -- but the two are independent implementations
with real behavioral differences past step 3, not one wrapping the other.

## `freeze_ratio` reaches `route_video_request` but never changes its answer

`route_video_request` takes `freeze_ratio` as its third parameter and passes it to exactly one call
in its own body: `is_mostly_static_video(motion_score, freeze_ratio)` on the second-to-last line.
Tracing what has to be true for that line to ever run and matter shows it can't. `should_extract_keyframes`
runs first and already returns `True` (routing to `4`) whenever `is_mostly_static_video(motion_score,
1.0)` is `True` -- and since `is_mostly_static_video`'s own body is
`motion_score <= 4.0 and freeze_ratio >= 0.85`, passing a hardcoded `1.0` for `freeze_ratio` there
means that check reduces to just `motion_score <= 4.0`, always satisfied when the real freeze ratio
would also satisfy `is_mostly_static_video(motion_score, freeze_ratio)` (which needs that same
`motion_score <= 4.0`, plus a `freeze_ratio` of at least `0.85`). So any input for which
`route_video_request`'s own `is_mostly_static_video(motion_score, freeze_ratio)` line would return
`True` has already been caught by `should_extract_keyframes` two lines earlier -- the line is
unreachable, and `freeze_ratio` -- despite being a named, documented parameter of the router --
has no effect on `route_video_request`'s return value. The standalone `is_mostly_static_video`
function itself is unaffected by this and works exactly as documented when called directly (as
`should_extract_keyframes` does, and as the worked test cases below confirm); the dead branch is
specific to how the two are composed inside `route_video_request`.

This does not show up as a test failure because nothing in `tests/mojo/test_video_gate.mojo` needs
`freeze_ratio` to matter to pass -- e.g. `route_video_request(0.8, 2.0, 0.95, 10.0, 0.05, False, 0)`
returns `4` ("static clip → keyframes") via the `should_extract_keyframes` branch regardless of what
`freeze_ratio` is set to; substituting any other `freeze_ratio` value into that same call still
returns `4`, for the reason traced above.

## Verification

`mojo/tests/libs/test_video_features.mojo`, `test_video_gate.mojo`, `test_video_ops.mojo`,
`test_video_regions.mojo`, `test_video_storyboard.mojo`, and `test_vision_gate.mojo` are
auto-generated coverage smoke tests -- each calls every function once with placeholder arguments and
checks only that the result is finite or type-correct, no specific numeric output pinned. The real,
hand-written suites live in `tests/mojo/` under the same six filenames and pin exact values: every
number in the worked examples above (`47.5`, `142.5`, `0.18627...`, the motion boxes, the scene spans,
the routing action codes) is asserted to an exact match or a `1e-9` tolerance in those files, and this
page's worked-by-hand arithmetic reproduces every one of them independently from the formulas in
`mojo/engine/video_features.mojo`, `video_gate.mojo`, `video_ops.mojo`, `video_regions.mojo`,
`video_storyboard.mojo`, and `vision_gate.mojo`.

**Next:** see [Multimodal and inference operations kernels](multimodal-and-inference-operations-kernels.md)
for the scalar vision/audio front-end primitives this family's outputs eventually feed, or browse the
[Runtime library catalog](runtime-library-catalog.md) for every module and function.
