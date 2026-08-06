"""
video_regions.mojo — Deterministic motion-region extraction for flat video frame buffers. Zero Python imports.

Videos are flat row-major sequences of complete frames. Per-pixel comparisons
operate on the mean of each pixel's `channels` values.

Boxes are inclusive and encoded as `[x0, y0, x1, y1, area]`, where `area` is
the actual count of motion pixels inside the box.

Public API:
  frame_diff_mask_flat            — binary motion mask between two frames
  motion_boxes_between_frames     — connected motion boxes between two frames
  largest_motion_box_between_frames — largest connected motion box between two frames
  temporal_motion_area_series     — per-transition motion-area ratios in [0, 1]
  peak_motion_box_flat            — largest-motion box from the strongest transition
  temporal_union_motion_box_flat  — union motion bounding box across all transitions
  motion_coverage_ratio_flat      — fraction of pixels that move at least once
"""
from image_regions import connected_component_boxes_flat
from video_ops import frame_count_from_flat


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


def _abs(value: Float64) -> Float64:
    return -value if value < 0.0 else value


def _foreground_count(mask_flat: List[Float64], fg_threshold: Float64) -> Int:
    var count = 0
    for value in mask_flat:
        if value >= fg_threshold:
            count += 1
    return count


def _mask_bbox(mask_flat: List[Float64], width: Int, height: Int, fg_threshold: Float64) -> List[Int]:
    var out = List[Int]()
    if width <= 0 or height <= 0:
        return out^
    var min_x = width
    var min_y = height
    var max_x = -1
    var max_y = -1
    var area = 0
    for index in range(len(mask_flat)):
        if mask_flat[index] < fg_threshold:
            continue
        area += 1
        var x = index % width
        var y = index // width
        if x < min_x:
            min_x = x
        if y < min_y:
            min_y = y
        if x > max_x:
            max_x = x
        if y > max_y:
            max_y = y
    if area <= 0:
        return out^
    out.append(min_x)
    out.append(min_y)
    out.append(max_x)
    out.append(max_y)
    out.append(area)
    return out^


def _diff_mask_between_frames(
    flat_frames: List[Float64],
    width: Int,
    height: Int,
    channels: Int,
    frame_a_index: Int,
    frame_b_index: Int,
    diff_threshold: Float64,
) -> List[Float64]:
    var out = List[Float64]()
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    var stride = _frame_stride(width, height, channels)
    if (
        stride <= 0
        or frame_a_index < 0
        or frame_b_index < 0
        or frame_a_index >= frames
        or frame_b_index >= frames
    ):
        return out^

    var pixels = width * height
    var base_a = frame_a_index * stride
    var base_b = frame_b_index * stride
    for pixel_index in range(pixels):
        var mean_a = _pixel_mean(flat_frames, base_a + pixel_index * channels, channels)
        var mean_b = _pixel_mean(flat_frames, base_b + pixel_index * channels, channels)
        out.append(255.0 if _abs(mean_a - mean_b) >= diff_threshold else 0.0)
    return out^


def frame_diff_mask_flat(
    flat_frames: List[Float64],
    width: Int,
    height: Int,
    channels: Int,
    frame_a_index: Int,
    frame_b_index: Int,
    diff_threshold: Float64,
) -> List[Float64]:
    """Binary motion mask between two frames."""
    return _diff_mask_between_frames(
        flat_frames,
        width,
        height,
        channels,
        frame_a_index,
        frame_b_index,
        diff_threshold,
    )


def motion_boxes_between_frames(
    flat_frames: List[Float64],
    width: Int,
    height: Int,
    channels: Int,
    frame_a_index: Int,
    frame_b_index: Int,
    diff_threshold: Float64,
    max_regions: Int,
) -> List[Int]:
    """Connected motion boxes between two frames as [x0, y0, x1, y1, area] × N."""
    if max_regions <= 0:
        var empty = List[Int]()
        return empty^
    return connected_component_boxes_flat(
        _diff_mask_between_frames(
            flat_frames,
            width,
            height,
            channels,
            frame_a_index,
            frame_b_index,
            diff_threshold,
        ),
        width,
        height,
        128.0,
        max_regions,
    )


def largest_motion_box_between_frames(
    flat_frames: List[Float64],
    width: Int,
    height: Int,
    channels: Int,
    frame_a_index: Int,
    frame_b_index: Int,
    diff_threshold: Float64,
) -> List[Int]:
    """Largest connected motion box between two frames."""
    var boxes = motion_boxes_between_frames(
        flat_frames,
        width,
        height,
        channels,
        frame_a_index,
        frame_b_index,
        diff_threshold,
        1,
    )
    var out = List[Int]()
    for value in boxes:
        out.append(value)
    return out^


def temporal_motion_area_series(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, diff_threshold: Float64
) -> List[Float64]:
    """Per-transition motion-area ratios in [0, 1]."""
    var out = List[Float64]()
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    var pixels = width * height
    if frames < 2 or pixels <= 0:
        return out^
    for frame_index in range(1, frames):
        var mask = _diff_mask_between_frames(
            flat_frames,
            width,
            height,
            channels,
            frame_index - 1,
            frame_index,
            diff_threshold,
        )
        out.append(Float64(_foreground_count(mask, 128.0)) / Float64(pixels))
    return out^


def peak_motion_box_flat(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, diff_threshold: Float64
) -> List[Int]:
    """Largest motion box from the transition with the most moving pixels."""
    var out = List[Int]()
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    if frames < 2:
        return out^

    var best_count = -1
    for frame_index in range(1, frames):
        var mask = _diff_mask_between_frames(
            flat_frames,
            width,
            height,
            channels,
            frame_index - 1,
            frame_index,
            diff_threshold,
        )
        var count = _foreground_count(mask, 128.0)
        if count > best_count:
            best_count = count
            var boxes = connected_component_boxes_flat(mask, width, height, 128.0, 1)
            out = List[Int]()
            for value in boxes:
                out.append(value)
    return out^


def temporal_union_motion_box_flat(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, diff_threshold: Float64
) -> List[Int]:
    """Bounding box and area of all pixels that move at least once across the clip."""
    var out = List[Int]()
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    var pixels = width * height
    if frames < 2 or pixels <= 0:
        return out^

    var union_mask = List[Float64]()
    for _ in range(pixels):
        union_mask.append(0.0)
    for frame_index in range(1, frames):
        var mask = _diff_mask_between_frames(
            flat_frames,
            width,
            height,
            channels,
            frame_index - 1,
            frame_index,
            diff_threshold,
        )
        for index in range(pixels):
            if mask[index] >= 128.0:
                union_mask[index] = 255.0
    return _mask_bbox(union_mask, width, height, 128.0)


def motion_coverage_ratio_flat(
    flat_frames: List[Float64], width: Int, height: Int, channels: Int, diff_threshold: Float64
) -> Float64:
    """Fraction of pixels that move at least once across the clip."""
    var frames = frame_count_from_flat(flat_frames, width, height, channels)
    var pixels = width * height
    if frames < 2 or pixels <= 0:
        return 0.0

    var union_mask = List[Float64]()
    for _ in range(pixels):
        union_mask.append(0.0)
    for frame_index in range(1, frames):
        var mask = _diff_mask_between_frames(
            flat_frames,
            width,
            height,
            channels,
            frame_index - 1,
            frame_index,
            diff_threshold,
        )
        for index in range(pixels):
            if mask[index] >= 128.0:
                union_mask[index] = 255.0
    return Float64(_foreground_count(union_mask, 128.0)) / Float64(pixels)

