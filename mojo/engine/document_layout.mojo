"""
document_layout.mojo — Deterministic layout segmentation and scoring for document masks. Zero Python imports.

Inputs are flat row-major grayscale or binary masks. Any value greater than or
equal to `fg_threshold` is treated as foreground ink.

Boxes are inclusive and encoded as `[x0, y0, x1, y1, area]`, where `area` is
the actual foreground-pixel count inside the box, not the rectangle area.

Public API:
  text_line_boxes_flat   — contiguous horizontal text bands as flattened boxes
  line_count_flat        — count of horizontal text bands
  column_boxes_flat      — contiguous vertical text columns as flattened boxes
  column_count_flat      — count of vertical text columns
  text_density_grid_flat — per-cell foreground density in [0, 1]
  multi_column_score_flat — score in [0, 1] for multi-column layouts
  table_like_score_flat  — score in [0, 1] for grid / table-like layouts
"""
from document_vision import (
    horizontal_projection,
    vertical_projection,
)


fn _pixel_count(width: Int, height: Int) -> Int:
    if width <= 0 or height <= 0:
        return 0
    return width * height


fn _pixel_value(flat: List[Float64], index: Int) -> Float64:
    if index < 0 or index >= len(flat):
        return 0.0
    return flat[index]


fn _is_foreground(mask_flat: List[Float64], index: Int, fg_threshold: Float64) -> Bool:
    return _pixel_value(mask_flat, index) >= fg_threshold


fn _normalized_min_count(min_count: Int) -> Int:
    return 1 if min_count < 1 else min_count


fn _clamp01(value: Float64) -> Float64:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


fn _abs(value: Float64) -> Float64:
    return -value if value < 0.0 else value


fn _count_projection_bands(projection: List[Float64], min_count: Int) -> Int:
    if len(projection) == 0:
        return 0
    var threshold = Float64(_normalized_min_count(min_count))
    var bands = 0
    var active = False
    for value in projection:
        if value >= threshold:
            if not active:
                bands += 1
                active = True
        else:
            active = False
    return bands


fn text_line_boxes_flat(
    mask_flat: List[Float64], width: Int, height: Int, fg_threshold: Float64, min_row_ink: Int
) -> List[Int]:
    """Contiguous horizontal text bands as [x0, y0, x1, y1, area] × N."""
    var out = List[Int]()
    if _pixel_count(width, height) <= 0:
        return out^

    var threshold = _normalized_min_count(min_row_ink)
    var in_band = False
    var band_y0 = 0
    var band_y1 = 0
    var band_min_x = width
    var band_max_x = -1
    var band_area = 0

    for y in range(height):
        var row_area = 0
        var row_min_x = width
        var row_max_x = -1
        for x in range(width):
            if _is_foreground(mask_flat, y * width + x, fg_threshold):
                row_area += 1
                if x < row_min_x:
                    row_min_x = x
                if x > row_max_x:
                    row_max_x = x
        if row_area >= threshold:
            if not in_band:
                in_band = True
                band_y0 = y
                band_min_x = row_min_x
                band_max_x = row_max_x
                band_area = row_area
            else:
                if row_min_x < band_min_x:
                    band_min_x = row_min_x
                if row_max_x > band_max_x:
                    band_max_x = row_max_x
                band_area += row_area
            band_y1 = y
        elif in_band:
            out.append(band_min_x)
            out.append(band_y0)
            out.append(band_max_x)
            out.append(band_y1)
            out.append(band_area)
            in_band = False
    if in_band:
        out.append(band_min_x)
        out.append(band_y0)
        out.append(band_max_x)
        out.append(band_y1)
        out.append(band_area)
    return out^


fn line_count_flat(
    mask_flat: List[Float64], width: Int, height: Int, fg_threshold: Float64, min_row_ink: Int
) -> Int:
    """Count contiguous horizontal text bands."""
    return len(text_line_boxes_flat(mask_flat, width, height, fg_threshold, min_row_ink)) // 5


fn column_boxes_flat(
    mask_flat: List[Float64], width: Int, height: Int, fg_threshold: Float64, min_col_ink: Int
) -> List[Int]:
    """Contiguous vertical text columns as [x0, y0, x1, y1, area] × N."""
    var out = List[Int]()
    if _pixel_count(width, height) <= 0:
        return out^

    var threshold = _normalized_min_count(min_col_ink)
    var in_band = False
    var band_x0 = 0
    var band_x1 = 0
    var band_min_y = height
    var band_max_y = -1
    var band_area = 0

    for x in range(width):
        var col_area = 0
        var col_min_y = height
        var col_max_y = -1
        for y in range(height):
            if _is_foreground(mask_flat, y * width + x, fg_threshold):
                col_area += 1
                if y < col_min_y:
                    col_min_y = y
                if y > col_max_y:
                    col_max_y = y
        if col_area >= threshold:
            if not in_band:
                in_band = True
                band_x0 = x
                band_min_y = col_min_y
                band_max_y = col_max_y
                band_area = col_area
            else:
                if col_min_y < band_min_y:
                    band_min_y = col_min_y
                if col_max_y > band_max_y:
                    band_max_y = col_max_y
                band_area += col_area
            band_x1 = x
        elif in_band:
            out.append(band_x0)
            out.append(band_min_y)
            out.append(band_x1)
            out.append(band_max_y)
            out.append(band_area)
            in_band = False
    if in_band:
        out.append(band_x0)
        out.append(band_min_y)
        out.append(band_x1)
        out.append(band_max_y)
        out.append(band_area)
    return out^


fn column_count_flat(
    mask_flat: List[Float64], width: Int, height: Int, fg_threshold: Float64, min_col_ink: Int
) -> Int:
    """Count contiguous vertical text columns."""
    return len(column_boxes_flat(mask_flat, width, height, fg_threshold, min_col_ink)) // 5


fn text_density_grid_flat(
    mask_flat: List[Float64],
    width: Int,
    height: Int,
    fg_threshold: Float64,
    grid_rows: Int,
    grid_cols: Int,
) -> List[Float64]:
    """Per-cell foreground density in [0, 1]."""
    var out = List[Float64]()
    if _pixel_count(width, height) <= 0 or grid_rows <= 0 or grid_cols <= 0:
        return out^

    for row in range(grid_rows):
        var y0 = (row * height) // grid_rows
        var y1 = ((row + 1) * height) // grid_rows - 1
        if y1 < y0:
            y1 = y0
        for col in range(grid_cols):
            var x0 = (col * width) // grid_cols
            var x1 = ((col + 1) * width) // grid_cols - 1
            if x1 < x0:
                x1 = x0
            var count = 0
            var cell_area = (y1 - y0 + 1) * (x1 - x0 + 1)
            if cell_area <= 0:
                out.append(0.0)
                continue
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    if _is_foreground(mask_flat, y * width + x, fg_threshold):
                        count += 1
            out.append(Float64(count) / Float64(cell_area))
    return out^


fn multi_column_score_flat(
    mask_flat: List[Float64], width: Int, height: Int, fg_threshold: Float64
) -> Float64:
    """Score in [0, 1] for layouts that look like two balanced columns with a gutter."""
    if width < 3 or height <= 0:
        return 0.0

    var projection = vertical_projection(mask_flat, width, height, fg_threshold)
    var prefix = List[Float64]()
    var running: Float64 = 0.0
    for value in projection:
        running += value
        prefix.append(running)
    if running <= 0.0:
        return 0.0

    var best: Float64 = 0.0
    for split in range(1, width - 1):
        var left_mass = prefix[split - 1]
        var right_mass = running - prefix[split]
        if left_mass <= 0.0 or right_mass <= 0.0:
            continue
        var left_density = left_mass / Float64(split * height)
        var right_density = right_mass / Float64((width - split - 1) * height)
        var max_side = left_density if left_density > right_density else right_density
        if max_side <= 0.0:
            continue
        var valley_density = projection[split] / Float64(height)
        var balance = 1.0 - (_abs(left_density - right_density) / max_side)
        var valley_separation = 1.0 - (valley_density / max_side)
        var side_strength = left_density if left_density < right_density else right_density
        var strength = side_strength / 0.35
        var score = (
            _clamp01(balance)
            * _clamp01(valley_separation)
            * _clamp01(strength)
        )
        if score > best:
            best = score
    return _clamp01(best)


fn table_like_score_flat(
    mask_flat: List[Float64], width: Int, height: Int, fg_threshold: Float64
) -> Float64:
    """Score in [0, 1] for layouts with repeated row and column bands."""
    if _pixel_count(width, height) <= 0:
        return 0.0

    var min_row_ink = width // 5
    if min_row_ink < 1:
        min_row_ink = 1
    var min_col_ink = height // 5
    if min_col_ink < 1:
        min_col_ink = 1

    var row_bands = _count_projection_bands(
        horizontal_projection(mask_flat, width, height, fg_threshold),
        min_row_ink,
    )
    var col_bands = _count_projection_bands(
        vertical_projection(mask_flat, width, height, fg_threshold),
        min_col_ink,
    )

    var densities = text_density_grid_flat(mask_flat, width, height, fg_threshold, 4, 4)
    var active_cells = 0
    for density in densities:
        if density >= 0.12:
            active_cells += 1
    var active_ratio: Float64 = 0.0
    if len(densities) > 0:
        active_ratio = Float64(active_cells) / Float64(len(densities))

    var row_strength = _clamp01(Float64(row_bands - 1) / 2.0)
    var col_strength = _clamp01(Float64(col_bands - 1) / 2.0)
    var structure = 0.5 * row_strength + 0.5 * col_strength
    if row_bands < 2 or col_bands < 2:
        structure *= 0.35
    return _clamp01(0.8 * structure + 0.2 * active_ratio)

