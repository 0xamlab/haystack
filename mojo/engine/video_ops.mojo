"""
video_ops.mojo — Deterministic temporal operations for flat video frame buffers. Zero Python imports.

Videos are represented as a flat row-major sequence of contiguous frames:
  frame0(pixel0 channels..., pixel1 channels..., ...), frame1(...), ...

Each pixel stores `channels` values (1 for grayscale, 3 for RGB, 4 for RGBA).
Temporal comparisons operate on per-pixel channel means in the 0-255 range.

Public API:
  frame_count_from_flat   — infer the number of complete frames from a flat buffer
  frame_mean_intensity    — average pixel intensity of one frame
  frame_mean_intensities  — average intensity for every frame
  frame_mean_abs_diff     — mean absolute per-pixel difference between two frames
  temporal_mean_abs_diff  — mean consecutive-frame absolute difference
  temporal_max_abs_diff   — peak consecutive-frame absolute difference
  freeze_frame_ratio      — fraction of consecutive transitions under a diff threshold
  sample_frame_indices    — evenly-spaced frame picks for keyframes / sampling
"""


def _frame_stride(width: Int, height: Int, channels: Int) -> Int:
    if width <= 0 or height <= 0 or channels <= 0:
        return 0
    return width * height * channels


def _frame_count_internal(flat_frames: List[Float64], width: Int, height: Int, channels: Int) -> Int:
    var stride = _frame_stride(width, height, channels)
    if stride <= 0:
        return 0
    return len(flat_frames) // stride


def _pixel_mean(flat_frames: List[Float64], base: Int, channels: Int) -> Float64:
    if channels <= 0:
        return 0.0
    var total: Float64 = 0.0
    for c in range(channels):
        total += flat_frames[base + c]
    return total / Float64(channels)


def frame_count_from_flat(flat_frames: List[Float64], width: Int, height: Int, channels: Int) -> Int:
    """Infer the number of complete frames. Partial trailing values are ignored."""
    return _frame_count_internal(flat_frames, width, height, channels)


def frame_mean_intensity(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, frame_index: Int,
) -> Float64:
    """Average 0-255 pixel intensity for one frame; 0 if the frame is out of range."""
    var frames = _frame_count_internal(flat_frames, width, height, channels)
    var stride = _frame_stride(width, height, channels)
    if frame_index < 0 or frame_index >= frames or stride <= 0:
        return 0.0
    var pixels = width * height
    if pixels <= 0:
        return 0.0
    var frame_base = frame_index * stride
    var total: Float64 = 0.0
    for pixel_index in range(pixels):
        total += _pixel_mean(flat_frames, frame_base + pixel_index * channels, channels)
    return total / Float64(pixels)


def frame_mean_intensities(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int
) -> List[Float64]:
    """Average intensity for each complete frame."""
    var out = List[Float64]()
    var frames = _frame_count_internal(flat_frames, width, height, channels)
    for frame_index in range(frames):
        out.append(frame_mean_intensity(flat_frames, width, height, channels, frame_index))
    return out^


def frame_mean_abs_diff(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int,
    frame_a_index: Int, frame_b_index: Int,
) -> Float64:
    """Mean absolute per-pixel difference between two frames after channel averaging."""
    var frames = _frame_count_internal(flat_frames, width, height, channels)
    var stride = _frame_stride(width, height, channels)
    if (
        frame_a_index < 0
        or frame_b_index < 0
        or frame_a_index >= frames
        or frame_b_index >= frames
        or stride <= 0
    ):
        return 0.0
    var pixels = width * height
    if pixels <= 0:
        return 0.0
    var base_a = frame_a_index * stride
    var base_b = frame_b_index * stride
    var total: Float64 = 0.0
    for pixel_index in range(pixels):
        var mean_a = _pixel_mean(flat_frames, base_a + pixel_index * channels, channels)
        var mean_b = _pixel_mean(flat_frames, base_b + pixel_index * channels, channels)
        var diff = mean_a - mean_b
        if diff < 0.0:
            diff = -diff
        total += diff
    return total / Float64(pixels)


def temporal_mean_abs_diff(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int
) -> Float64:
    """Mean consecutive-frame absolute difference in 0-255 intensity units."""
    var frames = _frame_count_internal(flat_frames, width, height, channels)
    if frames < 2:
        return 0.0
    var total: Float64 = 0.0
    for frame_index in range(1, frames):
        total += frame_mean_abs_diff(
            flat_frames,
            width,
            height,
            channels,
            frame_index - 1,
            frame_index,
        )
    return total / Float64(frames - 1)


def temporal_max_abs_diff(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int
) -> Float64:
    """Maximum consecutive-frame absolute difference in 0-255 intensity units."""
    var frames = _frame_count_internal(flat_frames, width, height, channels)
    if frames < 2:
        return 0.0
    var best: Float64 = 0.0
    for frame_index in range(1, frames):
        var diff = frame_mean_abs_diff(
            flat_frames,
            width,
            height,
            channels,
            frame_index - 1,
            frame_index,
        )
        if diff > best:
            best = diff
    return best


def freeze_frame_ratio(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, diff_threshold: Float64
) -> Float64:
    """Fraction of consecutive transitions with mean absolute difference <= diff_threshold.

    Single-frame clips are treated as fully static and return 1.0.
    """
    var frames = _frame_count_internal(flat_frames, width, height, channels)
    if frames < 2:
        return 1.0
    var frozen = 0
    for frame_index in range(1, frames):
        if (
            frame_mean_abs_diff(
                flat_frames,
                width,
                height,
                channels,
                frame_index - 1,
                frame_index,
            )
            <= diff_threshold
        ):
            frozen += 1
    return Float64(frozen) / Float64(frames - 1)


def sample_frame_indices(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, target_frames: Int
) -> List[Int]:
    """Evenly spaced frame indices covering the start and end of the clip."""
    var out = List[Int]()
    var frames = _frame_count_internal(flat_frames, width, height, channels)
    if frames <= 0 or target_frames <= 0:
        return out^
    if target_frames >= frames or target_frames == 1:
        if target_frames == 1:
            out.append(0)
            return out^
        for frame_index in range(frames):
            out.append(frame_index)
        return out^

    var last = -1
    for pick in range(target_frames):
        var idx = (pick * (frames - 1)) // (target_frames - 1)
        if idx <= last:
            idx = last + 1
        if idx >= frames:
            idx = frames - 1
        out.append(idx)
        last = idx
    return out^
