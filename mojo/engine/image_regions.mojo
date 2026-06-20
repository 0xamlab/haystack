"""
image_regions.mojo — Foreground regions, saliency boxes, and crop helpers on flat buffers. Zero Python imports.

Boxes are inclusive and encoded as `[x0, y0, x1, y1, area]` unless otherwise
noted. The box utilities accept either 4-value or 5-value boxes and ignore any
extra trailing values.

Public API:
  foreground_mask_otsu_flat      — Otsu-based foreground mask
  connected_component_boxes_flat — flattened [x0,y0,x1,y1,area] boxes sorted by area
  largest_foreground_box_flat    — largest Otsu-thresholded component box
  saliency_box_flat              — most salient grid cell as [x0,y0,x1,y1,area]
  extract_box_flat               — inclusive crop extraction as a flat list
  box_iou                        — intersection-over-union for two boxes
"""
from document_vision import binarize_otsu_flat
from image_features import most_salient_cell, saliency_grid
from image_morphology import connected_components_4_flat
from image_resize import reshape_to_grid


fn _pixel_count(width: Int, height: Int) -> Int:
    if width <= 0 or height <= 0:
        return 0
    return width * height


fn _pixel_value(flat: List[Float64], index: Int) -> Float64:
    if index < 0 or index >= len(flat):
        return 0.0
    return flat[index]


fn foreground_mask_otsu_flat(flat: List[Float64], width: Int, height: Int) -> List[Float64]:
    """Otsu-based dark-foreground mask."""
    return binarize_otsu_flat(flat, width, height)


fn connected_component_boxes_flat(
    mask_flat: List[Float64], width: Int, height: Int, fg_threshold: Float64, max_regions: Int
) -> List[Int]:
    """Flattened boxes sorted by descending area: [x0,y0,x1,y1,area] × N."""
    var out = List[Int]()
    var pixels = _pixel_count(width, height)
    if pixels <= 0 or max_regions <= 0:
        return out^

    var labels = connected_components_4_flat(mask_flat, width, height, fg_threshold)
    var max_label = 0
    for label in labels:
        if label > max_label:
            max_label = label
    if max_label <= 0:
        return out^

    var min_x = List[Int]()
    var min_y = List[Int]()
    var max_x = List[Int]()
    var max_y = List[Int]()
    var area = List[Int]()
    for _ in range(max_label + 1):
        min_x.append(width)
        min_y.append(height)
        max_x.append(-1)
        max_y.append(-1)
        area.append(0)
    for index in range(len(labels)):
        var label = labels[index]
        if label <= 0:
            continue
        var x = index % width
        var y = index // width
        area[label] += 1
        if x < min_x[label]:
            min_x[label] = x
        if y < min_y[label]:
            min_y[label] = y
        if x > max_x[label]:
            max_x[label] = x
        if y > max_y[label]:
            max_y[label] = y
    var order = List[Int]()
    for label in range(1, max_label + 1):
        if area[label] > 0:
            order.append(label)
    for i in range(1, len(order)):
        var key = order[i]
        var j = i - 1
        while j >= 0 and area[order[j]] < area[key]:
            order[j + 1] = order[j]
            j -= 1
        order[j + 1] = key
    var limit = max_regions
    if limit > len(order):
        limit = len(order)
    for i in range(limit):
        var label = order[i]
        out.append(min_x[label])
        out.append(min_y[label])
        out.append(max_x[label])
        out.append(max_y[label])
        out.append(area[label])
    return out^
fn largest_foreground_box_flat(flat: List[Float64], width: Int, height: Int) -> List[Int]:
    """Largest Otsu-thresholded component box as [x0, y0, x1, y1, area]."""
    var mask = foreground_mask_otsu_flat(flat, width, height)
    var boxes = connected_component_boxes_flat(mask, width, height, 128.0, 1)
    var out = List[Int]()
    for i in range(len(boxes)):
        out.append(boxes[i])
    return out^
fn saliency_box_flat(
    flat: List[Float64], width: Int, height: Int, grid_rows: Int, grid_cols: Int
) -> List[Int]:
    """Most salient grid cell as [x0, y0, x1, y1, area]."""
    var out = List[Int]()
    if width <= 0 or height <= 0 or grid_rows <= 0 or grid_cols <= 0:
        return out^
    var sal = saliency_grid(reshape_to_grid(flat, width, height), grid_rows, grid_cols)
    var index = most_salient_cell(sal)
    if index < 0:
        return out^
    var row = index // grid_cols
    var col = index % grid_cols
    var x0 = (col * width) // grid_cols
    var y0 = (row * height) // grid_rows
    var x1 = ((col + 1) * width) // grid_cols - 1
    var y1 = ((row + 1) * height) // grid_rows - 1
    if x1 < x0:
        x1 = x0
    if y1 < y0:
        y1 = y0
    out.append(x0)
    out.append(y0)
    out.append(x1)
    out.append(y1)
    out.append((x1 - x0 + 1) * (y1 - y0 + 1))
    return out^
fn extract_box_flat(
    flat: List[Float64], width: Int, height: Int, x0: Int, y0: Int, x1: Int, y1: Int
) -> List[Float64]:
    """Inclusive crop extraction as a flat list. Invalid boxes return []."""
    var out = List[Float64]()
    if width <= 0 or height <= 0:
        return out^
    var left = x0
    var top = y0
    var right = x1
    var bottom = y1
    if left < 0:
        left = 0
    if top < 0:
        top = 0
    if right >= width:
        right = width - 1
    if bottom >= height:
        bottom = height - 1
    if right < left or bottom < top:
        return out^
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            out.append(_pixel_value(flat, y * width + x))
    return out^
fn box_iou(box_a: List[Int], box_b: List[Int]) -> Float64:
    """Intersection-over-union for two inclusive boxes."""
    if len(box_a) < 4 or len(box_b) < 4:
        return 0.0
    var ax0 = box_a[0]
    var ay0 = box_a[1]
    var ax1 = box_a[2]
    var ay1 = box_a[3]
    if ax1 < ax0:
        var tmp = ax0
        ax0 = ax1
        ax1 = tmp
    if ay1 < ay0:
        var tmp = ay0
        ay0 = ay1
        ay1 = tmp
    var bx0 = box_b[0]
    var by0 = box_b[1]
    var bx1 = box_b[2]
    var by1 = box_b[3]
    if bx1 < bx0:
        var tmp = bx0
        bx0 = bx1
        bx1 = tmp
    if by1 < by0:
        var tmp = by0
        by0 = by1
        by1 = tmp
    var ix0 = ax0 if ax0 > bx0 else bx0
    var iy0 = ay0 if ay0 > by0 else by0
    var ix1 = ax1 if ax1 < bx1 else bx1
    var iy1 = ay1 if ay1 < by1 else by1
    if ix1 < ix0 or iy1 < iy0:
        return 0.0
    var intersection = Float64((ix1 - ix0 + 1) * (iy1 - iy0 + 1))
    var area_a = Float64((ax1 - ax0 + 1) * (ay1 - ay0 + 1))
    var area_b = Float64((bx1 - bx0 + 1) * (by1 - by0 + 1))
    var union_area = area_a + area_b - intersection
    if union_area <= 0.0:
        return 0.0
    return intersection / union_area
