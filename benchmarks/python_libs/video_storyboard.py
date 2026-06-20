"""Manual Python reference for video_storyboard.mojo."""

from __future__ import annotations


def _frame_stride(width: int, height: int, channels: int) -> int:
    if width <= 0 or height <= 0 or channels <= 0:
        return 0
    return width * height * channels


def frame_count_from_flat(flat_frames: list[float], width: int, height: int, channels: int) -> int:
    stride = _frame_stride(width, height, channels)
    if stride <= 0:
        return 0
    return len(flat_frames) // stride


def _pixel_mean(flat_frames: list[float], base: int, channels: int) -> float:
    if channels <= 0:
        return 0.0
    return sum(flat_frames[base : base + channels]) / float(channels)


def frame_mean_abs_diff(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    frame_a_index: int,
    frame_b_index: int,
) -> float:
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    stride = _frame_stride(width, height, channels)
    if (
        frame_a_index < 0
        or frame_b_index < 0
        or frame_a_index >= frames
        or frame_b_index >= frames
        or stride <= 0
    ):
        return 0.0
    pixels = width * height
    if pixels <= 0:
        return 0.0
    base_a = frame_a_index * stride
    base_b = frame_b_index * stride
    total = 0.0
    for pixel_index in range(pixels):
        mean_a = _pixel_mean(flat_frames, base_a + pixel_index * channels, channels)
        mean_b = _pixel_mean(flat_frames, base_b + pixel_index * channels, channels)
        total += abs(mean_a - mean_b)
    return total / float(pixels)


def scene_change_scores(
    flat_frames: list[float], width: int, height: int, channels: int
) -> list[float]:
    out: list[float] = []
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames < 2:
        return out
    for frame_index in range(1, frames):
        out.append(
            frame_mean_abs_diff(
                flat_frames,
                width,
                height,
                channels,
                frame_index - 1,
                frame_index,
            )
            / 255.0
        )
    return out


def _scene_start_list(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    cut_threshold: float,
) -> list[int]:
    out: list[int] = []
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames <= 0:
        return out

    out.append(0)
    if frames == 1:
        return out

    for transition_index, score in enumerate(
        scene_change_scores(flat_frames, width, height, channels)
    ):
        if score > cut_threshold:
            out.append(transition_index + 1)
    return out


def _sample_dense_indices(total: int, target: int) -> list[int]:
    out: list[int] = []
    if total <= 0 or target <= 0:
        return out
    if target >= total or target == 1:
        if target == 1:
            return [0]
        return list(range(total))

    last = -1
    for pick in range(target):
        index = (pick * (total - 1)) // (target - 1)
        if index <= last:
            index = last + 1
        if index >= total:
            index = total - 1
        out.append(index)
        last = index
    return out


def scene_start_indices(
    flat_frames: list[float], width: int, height: int, channels: int, cut_threshold: float
) -> list[int]:
    return _scene_start_list(flat_frames, width, height, channels, cut_threshold)


def scene_end_indices(
    flat_frames: list[float], width: int, height: int, channels: int, cut_threshold: float
) -> list[int]:
    out: list[int] = []
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames <= 0:
        return out

    starts = _scene_start_list(flat_frames, width, height, channels, cut_threshold)
    for scene_index, start in enumerate(starts):
        next_start = starts[scene_index + 1] if scene_index + 1 < len(starts) else frames
        out.append(next_start - 1)
    return out


def scene_lengths_frames(
    flat_frames: list[float], width: int, height: int, channels: int, cut_threshold: float
) -> list[int]:
    out: list[int] = []
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames <= 0:
        return out

    starts = _scene_start_list(flat_frames, width, height, channels, cut_threshold)
    for scene_index, start in enumerate(starts):
        next_start = starts[scene_index + 1] if scene_index + 1 < len(starts) else frames
        out.append(next_start - start)
    return out


def scene_representative_frames(
    flat_frames: list[float], width: int, height: int, channels: int, cut_threshold: float
) -> list[int]:
    out: list[int] = []
    frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames <= 0:
        return out

    starts = _scene_start_list(flat_frames, width, height, channels, cut_threshold)
    for scene_index, start in enumerate(starts):
        next_start = starts[scene_index + 1] if scene_index + 1 < len(starts) else frames
        out.append((start + (next_start - 1)) // 2)
    return out


def longest_scene_index(
    flat_frames: list[float], width: int, height: int, channels: int, cut_threshold: float
) -> int:
    lengths = scene_lengths_frames(flat_frames, width, height, channels, cut_threshold)
    if not lengths:
        return -1
    best_index = 0
    best_length = lengths[0]
    for scene_index, length in enumerate(lengths[1:], start=1):
        if length > best_length:
            best_length = length
            best_index = scene_index
    return best_index


def storyboard_frame_indices(
    flat_frames: list[float],
    width: int,
    height: int,
    channels: int,
    cut_threshold: float,
    max_frames: int,
) -> list[int]:
    out: list[int] = []
    if max_frames <= 0:
        return out

    reps = scene_representative_frames(flat_frames, width, height, channels, cut_threshold)
    if not reps:
        return out
    if max_frames >= len(reps):
        return reps
    if max_frames == 1:
        best_scene = longest_scene_index(flat_frames, width, height, channels, cut_threshold)
        return [reps[best_scene]] if best_scene >= 0 else []

    return [reps[index] for index in _sample_dense_indices(len(reps), max_frames)]
