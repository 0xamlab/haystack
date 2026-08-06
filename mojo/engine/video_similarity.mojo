"""
video_similarity.mojo — Deterministic clip-to-clip similarity metrics. Zero Python imports.

Complements the existing per-clip video modules by adding direct video-vs-video
comparison primitives for dedupe, cache reuse, and regression checks.

Videos are flat row-major frame buffers with `channels` values per pixel.
Similarity operates on grayscale frame means derived from those channels.

Public API:
  frame_duplicate_scores        — per-frame duplicate scores in [0, 1]
  average_frame_duplicate_score — mean of the per-frame duplicate scores
  frame_hash_hamming_series     — per-frame dHash Hamming distances in [0, 64]
  average_frame_hash_hamming    — mean per-frame Hamming distance
  temporal_signature_distance   — clip-level temporal distance in [0, 1]
  clip_duplicate_score_flat     — weighted duplicate score in [0, 1]
  is_duplicate_clip_flat        — duplicate_score >= min_score
"""
from image_similarity import duplicate_score_flat
from perceptual_hash import dhash_flat, hamming_distance
from video_features import scene_change_scores
from video_ops import frame_count_from_flat, frame_mean_intensity


def _abs(v: Float64) -> Float64:
    return -v if v < 0.0 else v


def _clamp01(v: Float64) -> Float64:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _frame_stride(width: Int, height: Int, channels: Int) -> Int:
    if width <= 0 or height <= 0 or channels <= 0:
        return 0
    return width * height * channels


def _pixel_mean(flat_frames: List[Float64], base: Int, channels: Int) -> Float64:
    if channels <= 0:
        return 0.0
    var total: Float64 = 0.0
    for c in range(channels):
        total += flat_frames[base + c]
    return total / Float64(channels)


def _extract_frame_gray_flat(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, frame_index: Int,
) -> List[Float64]:
    var out = List[Float64]()
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    var stride = _frame_stride(width, height, channels)
    if frame_index < 0 or frame_index >= frames or stride <= 0:
        return out^
    var pixels = width * height
    var frame_base = frame_index * stride
    for pixel_index in range(pixels):
        out.append(_pixel_mean(flat_frames, frame_base + pixel_index * channels, channels))
    return out^


def _paired_frame_count(
    flat_a: List[Float64], flat_b: List[Float64], width: Int, height: Int, channels: Int,
) -> Int:
    var frames_a = frame_count_from_flat(flat_a, width, height, channels)
    var frames_b = frame_count_from_flat(flat_b, width, height, channels)
    return frames_a if frames_a <= frames_b else frames_b


def _frame_count_gap_ratio(frames_a: Int, frames_b: Int) -> Float64:
    if frames_a <= 0 and frames_b <= 0:
        return 0.0
    var max_frames = frames_a if frames_a >= frames_b else frames_b
    var gap = frames_a - frames_b
    if gap < 0:
        gap = -gap
    return Float64(gap) / Float64(max_frames)


def frame_duplicate_scores(
    flat_a: List[Float64], flat_b: List[Float64], width: Int, height: Int, channels: Int
) -> List[Float64]:
    """Per-frame duplicate scores for aligned frames up to min(frame_count_a, frame_count_b)."""
    var out = List[Float64]()
    var frames = _paired_frame_count(flat_a, flat_b, width, height, channels)
    if frames <= 0:
        return out^
    for frame_index in range(frames):
        var frame_a = _extract_frame_gray_flat(flat_a, width, height, channels, frame_index)
        var frame_b = _extract_frame_gray_flat(flat_b, width, height, channels, frame_index)
        out.append(duplicate_score_flat(frame_a, frame_b, width, height))
    return out^


def average_frame_duplicate_score(
    flat_a: List[Float64], flat_b: List[Float64], width: Int, height: Int, channels: Int
) -> Float64:
    """Mean frame duplicate score in [0, 1]. Empty vs empty returns 1.0."""
    var frames_a = frame_count_from_flat(flat_a, width, height, channels)
    var frames_b = frame_count_from_flat(flat_b, width, height, channels)
    if frames_a <= 0 and frames_b <= 0:
        return 1.0
    if frames_a <= 0 or frames_b <= 0:
        return 0.0
    var scores = frame_duplicate_scores(flat_a, flat_b, width, height, channels)
    if len(scores) == 0:
        return 0.0
    var total: Float64 = 0.0
    for score in scores:
        total += score
    return total / Float64(len(scores))


def frame_hash_hamming_series(
    flat_a: List[Float64], flat_b: List[Float64], width: Int, height: Int, channels: Int
) -> List[Int]:
    """Per-frame dHash Hamming distances for aligned frames."""
    var out = List[Int]()
    var frames = _paired_frame_count(flat_a, flat_b, width, height, channels)
    if frames <= 0:
        return out^
    for frame_index in range(frames):
        var frame_a = _extract_frame_gray_flat(flat_a, width, height, channels, frame_index)
        var frame_b = _extract_frame_gray_flat(flat_b, width, height, channels, frame_index)
        out.append(hamming_distance(dhash_flat(frame_a, width, height), dhash_flat(frame_b, width, height)))
    return out^


def average_frame_hash_hamming(
    flat_a: List[Float64], flat_b: List[Float64], width: Int, height: Int, channels: Int
) -> Float64:
    """Mean frame dHash Hamming distance. Empty vs non-empty returns 64.0."""
    var frames_a = frame_count_from_flat(flat_a, width, height, channels)
    var frames_b = frame_count_from_flat(flat_b, width, height, channels)
    if frames_a <= 0 and frames_b <= 0:
        return 0.0
    if frames_a <= 0 or frames_b <= 0:
        return 64.0
    var distances = frame_hash_hamming_series(flat_a, flat_b, width, height, channels)
    if len(distances) == 0:
        return 64.0
    var total: Float64 = 0.0
    for value in distances:
        total += Float64(value)
    return total / Float64(len(distances))


def temporal_signature_distance(
    flat_a: List[Float64], flat_b: List[Float64], width: Int, height: Int, channels: Int
) -> Float64:
    """Clip-level temporal distance in [0, 1] from intensity, motion, and length mismatch."""
    var frames_a = frame_count_from_flat(flat_a, width, height, channels)
    var frames_b = frame_count_from_flat(flat_b, width, height, channels)
    if frames_a <= 0 and frames_b <= 0:
        return 0.0
    if frames_a <= 0 or frames_b <= 0:
        return 1.0

    var paired_frames = frames_a if frames_a <= frames_b else frames_b
    var intensity_gap: Float64 = 0.0
    for frame_index in range(paired_frames):
        intensity_gap += _abs(
            frame_mean_intensity(flat_a, width, height, channels, frame_index)
            - frame_mean_intensity(flat_b, width, height, channels, frame_index)
        ) / 255.0
    intensity_gap /= Float64(paired_frames)

    var motion_a = scene_change_scores(flat_a, width, height, channels)
    var motion_b = scene_change_scores(flat_b, width, height, channels)
    var paired_transitions = len(motion_a)
    if len(motion_b) < paired_transitions:
        paired_transitions = len(motion_b)

    var motion_gap: Float64 = 0.0
    if paired_transitions > 0:
        for index in range(paired_transitions):
            motion_gap += _abs(motion_a[index] - motion_b[index])
        motion_gap /= Float64(paired_transitions)

    var count_gap = _frame_count_gap_ratio(frames_a, frames_b)
    return _clamp01(0.55 * intensity_gap + 0.30 * motion_gap + 0.15 * count_gap)


def clip_duplicate_score_flat(
    flat_a: List[Float64], flat_b: List[Float64], width: Int, height: Int, channels: Int
) -> Float64:
    """Weighted clip duplicate score in [0, 1] from frame, hash, and temporal agreement."""
    var frames_a = frame_count_from_flat(flat_a, width, height, channels)
    var frames_b = frame_count_from_flat(flat_b, width, height, channels)
    if frames_a <= 0 and frames_b <= 0:
        return 1.0
    if frames_a <= 0 or frames_b <= 0:
        return 0.0

    var frame_score = average_frame_duplicate_score(flat_a, flat_b, width, height, channels)
    var hash_similarity = _clamp01(
        1.0 - average_frame_hash_hamming(flat_a, flat_b, width, height, channels) / 64.0
    )
    var temporal_similarity = 1.0 - temporal_signature_distance(flat_a, flat_b, width, height, channels)
    return _clamp01(0.55 * frame_score + 0.25 * hash_similarity + 0.20 * temporal_similarity)


def is_duplicate_clip_flat(
    flat_a: List[Float64], flat_b: List[Float64],
    width: Int, height: Int, channels: Int, min_score: Float64,
) -> Bool:
    """True when clip_duplicate_score_flat meets or exceeds min_score."""
    return clip_duplicate_score_flat(flat_a, flat_b, width, height, channels) >= min_score
