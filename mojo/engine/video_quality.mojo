"""
video_quality.mojo — Deterministic quality scores for flat video frame buffers. Zero Python imports.

The image lane already scores single frames. This module lifts that into the
temporal domain by sampling frames, computing per-frame image quality, and mixing
that with brightness flicker into a clip-level usability score.

Public API:
  frame_quality_series   — sampled per-frame quality scores in [0, 1]
  average_frame_quality  — mean sampled frame quality
  brightness_flicker_score — mean absolute change of frame brightness
  temporal_stability_score — 1/(1+flicker/48), clamped to [0, 1]
  video_quality_score    — weighted clip usability score in [0, 1]
  is_usable_video        — quality threshold pass/fail
"""
from image_quality import quality_score
from image_resize import reshape_to_grid
from video_ops import (
    frame_count_from_flat,
    frame_mean_intensities,
    sample_frame_indices,
)


def _clamp01(x: Float64) -> Float64:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _frame_stride(width: Int, height: Int, channels: Int) -> Int:
    if width <= 0 or height <= 0 or channels <= 0:
        return 0
    return width * height * channels


def _extract_frame_gray_flat(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, frame_index: Int
) -> List[Float64]:
    var out = List[Float64]()
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    var stride = _frame_stride(width, height, channels)
    if frame_index < 0 or frame_index >= frames or stride <= 0:
        return out^
    var base = frame_index * stride
    var pixels = width * height
    for pixel_index in range(pixels):
        var pixel_base = base + pixel_index * channels
        var total: Float64 = 0.0
        for c in range(channels):
            total += flat_frames[pixel_base + c]
        out.append(total / Float64(channels))
    return out^


def frame_quality_series(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, sample_frames: Int
) -> List[Float64]:
    """Per-frame quality_score values for evenly sampled frames across the clip."""
    var picks = sample_frame_indices(flat_frames, width, height, channels, sample_frames)
    var out = List[Float64]()
    for pick in picks:
        out.append(
            quality_score(
                reshape_to_grid(
                    _extract_frame_gray_flat(flat_frames, width, height, channels, pick),
                    width,
                    height,
                )
            )
        )
    return out^


def average_frame_quality(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, sample_frames: Int
) -> Float64:
    """Mean sampled frame quality. Empty clips return 0."""
    var qualities = frame_quality_series(flat_frames, width, height, channels, sample_frames)
    if len(qualities) == 0:
        return 0.0
    var total: Float64 = 0.0
    for quality in qualities:
        total += quality
    return total / Float64(len(qualities))


def brightness_flicker_score(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int
) -> Float64:
    """Mean absolute brightness change between consecutive frames in 0-255 units."""
    var means = frame_mean_intensities(flat_frames, width, height, channels)
    if len(means) < 2:
        return 0.0
    var total: Float64 = 0.0
    for i in range(1, len(means)):
        var diff = means[i] - means[i - 1]
        if diff < 0.0:
            diff = -diff
        total += diff
    return total / Float64(len(means) - 1)


def temporal_stability_score(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int
) -> Float64:
    """Brightness-stability score in [0, 1]; 1 is stable, 0 is severe flicker."""
    var flicker = brightness_flicker_score(flat_frames, width, height, channels)
    return _clamp01(1.0 / (1.0 + flicker / 48.0))


def video_quality_score(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, sample_frames: Int
) -> Float64:
    """Weighted clip usability score in [0, 1]."""
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames <= 0:
        return 0.0
    var frame_quality = average_frame_quality(flat_frames, width, height, channels, sample_frames)
    var stability = temporal_stability_score(flat_frames, width, height, channels)
    var coverage = 1.0 if frames > 1 else 0.7
    return _clamp01(0.7 * frame_quality + 0.2 * stability + 0.1 * coverage)


def is_usable_video(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int,
    sample_frames: Int, min_quality: Float64,
) -> Bool:
    """True when video_quality_score meets or exceeds min_quality."""
    return (
        video_quality_score(flat_frames, width, height, channels, sample_frames)
        >= min_quality
    )
