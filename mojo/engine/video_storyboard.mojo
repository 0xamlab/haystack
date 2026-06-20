"""
video_storyboard.mojo — Deterministic storyboard/timeline helpers for flat video frame buffers.

Built on the temporal video kernels to expose scene spans and representative
frame picks that callers can use for preview strips, moderation review, and
clip summarization without leaving the pure-Mojo lane.

Public API:
  scene_start_indices         — starting frame index of each detected scene
  scene_end_indices           — inclusive ending frame index of each detected scene
  scene_lengths_frames        — duration of each detected scene in frames
  scene_representative_frames — midpoint frame index of each detected scene
  longest_scene_index         — index of the longest detected scene, or -1 if empty
  storyboard_frame_indices    — capped representative-frame picks across the clip
"""
from video_features import scene_change_scores
from video_ops import frame_count_from_flat


def _scene_start_list(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, cut_threshold: Float64
) -> List[Int]:
    var out = List[Int]()
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames <= 0:
        return out^

    out.append(0)
    if frames == 1:
        return out^

    var scores = scene_change_scores(flat_frames, width, height, channels)
    for transition_index in range(len(scores)):
        if scores[transition_index] > cut_threshold:
            out.append(transition_index + 1)
    return out^


def _sample_dense_indices(total: Int, target: Int) -> List[Int]:
    var out = List[Int]()
    if total <= 0 or target <= 0:
        return out^
    if target >= total or target == 1:
        if target == 1:
            out.append(0)
            return out^
        for index in range(total):
            out.append(index)
        return out^

    var last = -1
    for pick in range(target):
        var index = (pick * (total - 1)) // (target - 1)
        if index <= last:
            index = last + 1
        if index >= total:
            index = total - 1
        out.append(index)
        last = index
    return out^


def scene_start_indices(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, cut_threshold: Float64
) -> List[Int]:
    """Starting frame index of each detected scene."""
    return _scene_start_list(flat_frames, width, height, channels, cut_threshold)


def scene_end_indices(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, cut_threshold: Float64
) -> List[Int]:
    """Inclusive ending frame index of each detected scene."""
    var out = List[Int]()
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames <= 0:
        return out^

    var starts = _scene_start_list(flat_frames, width, height, channels, cut_threshold)
    for scene_index in range(len(starts)):
        var next_start = frames
        if scene_index + 1 < len(starts):
            next_start = starts[scene_index + 1]
        out.append(next_start - 1)
    return out^


def scene_lengths_frames(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, cut_threshold: Float64
) -> List[Int]:
    """Scene durations in frames."""
    var out = List[Int]()
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames <= 0:
        return out^

    var starts = _scene_start_list(flat_frames, width, height, channels, cut_threshold)
    for scene_index in range(len(starts)):
        var next_start = frames
        if scene_index + 1 < len(starts):
            next_start = starts[scene_index + 1]
        out.append(next_start - starts[scene_index])
    return out^


def scene_representative_frames(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, cut_threshold: Float64
) -> List[Int]:
    """Midpoint frame index of each detected scene."""
    var out = List[Int]()
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames <= 0:
        return out^

    var starts = _scene_start_list(flat_frames, width, height, channels, cut_threshold)
    for scene_index in range(len(starts)):
        var next_start = frames
        if scene_index + 1 < len(starts):
            next_start = starts[scene_index + 1]
        var end_index = next_start - 1
        out.append((starts[scene_index] + end_index) // 2)
    return out^


def longest_scene_index(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, cut_threshold: Float64
) -> Int:
    """Index of the longest detected scene, or -1 when the clip is empty."""
    var lengths = scene_lengths_frames(flat_frames, width, height, channels, cut_threshold)
    if len(lengths) == 0:
        return -1

    var best_index = 0
    var best_length = lengths[0]
    for scene_index in range(1, len(lengths)):
        if lengths[scene_index] > best_length:
            best_length = lengths[scene_index]
            best_index = scene_index
    return best_index


def storyboard_frame_indices(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int,
    cut_threshold: Float64, max_frames: Int,
) -> List[Int]:
    """Representative storyboard frame picks capped at max_frames."""
    var out = List[Int]()
    if max_frames <= 0:
        return out^

    var reps = scene_representative_frames(flat_frames, width, height, channels, cut_threshold)
    if len(reps) == 0:
        return out^
    if max_frames >= len(reps):
        return reps^
    if max_frames == 1:
        var best_scene = longest_scene_index(flat_frames, width, height, channels, cut_threshold)
        if best_scene >= 0:
            out.append(reps[best_scene])
        return out^

    var sample_indices = _sample_dense_indices(len(reps), max_frames)
    for sample_index in sample_indices:
        out.append(reps[sample_index])
    return out^
