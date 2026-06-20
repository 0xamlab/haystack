"""
video_features.mojo — Deterministic temporal features for flat video frame buffers. Zero Python imports.

Built on `video_ops`: scene-change scoring, keyframe selection, and clip-level
motion summaries that the caller can use to decide whether a static screenshot-like
clip is enough or whether the full motion sequence matters.

Public API:
  scene_change_scores  — normalized consecutive-frame change scores in [0, 1]
  scene_cut_count      — count of change scores above a threshold
  scene_cut_rate       — cut_count / transitions
  peak_motion_frame    — later frame index of the strongest consecutive transition
  keyframe_indices     — first frame plus cut frames, capped at max_frames
"""
from video_ops import (
    frame_count_from_flat,
    frame_mean_abs_diff,
)


fn scene_change_scores(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int
) -> List[Float64]:
    """Consecutive-frame change scores normalized to [0, 1] by 255."""
    var out = List[Float64]()
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames < 2:
        return out^
    for frame_index in range(1, frames):
        out.append(
            frame_mean_abs_diff(
                flat_frames,
                width,
                height,
                channels,
                frame_index - 1,
                frame_index,
            ) / 255.0
        )
    return out^


fn scene_cut_count(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, cut_threshold: Float64
) -> Int:
    """Count scene changes whose normalized score exceeds cut_threshold."""
    var scores = scene_change_scores(flat_frames, width, height, channels)
    var total = 0
    for score in scores:
        if score > cut_threshold:
            total += 1
    return total


fn scene_cut_rate(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, cut_threshold: Float64
) -> Float64:
    """Scene cuts divided by the number of consecutive transitions."""
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames < 2:
        return 0.0
    return (
        Float64(scene_cut_count(flat_frames, width, height, channels, cut_threshold))
        / Float64(frames - 1)
    )


fn peak_motion_frame(flat_frames: List[Float64], width: Int, height: Int, channels: Int) -> Int:
    """Later frame index of the strongest consecutive transition."""
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames <= 0:
        return -1
    if frames == 1:
        return 0
    var best_index = 1
    var best_score: Float64 = -1.0
    for frame_index in range(1, frames):
        var score = frame_mean_abs_diff(
            flat_frames,
            width,
            height,
            channels,
            frame_index - 1,
            frame_index,
        )
        if score > best_score:
            best_score = score
            best_index = frame_index
    return best_index


fn keyframe_indices(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int,
    cut_threshold: Float64, max_frames: Int,
) -> List[Int]:
    """First frame plus frames that follow cut_threshold transitions, capped at max_frames."""
    var out = List[Int]()
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames <= 0 or max_frames <= 0:
        return out^

    out.append(0)
    if frames == 1:
        return out^

    for frame_index in range(1, frames):
        if len(out) >= max_frames:
            break
        var score = frame_mean_abs_diff(
            flat_frames,
            width,
            height,
            channels,
            frame_index - 1,
            frame_index,
        ) / 255.0
        if score > cut_threshold:
            out.append(frame_index)
    if len(out) < max_frames and out[len(out) - 1] != frames - 1:
        out.append(frames - 1)
    return out^
