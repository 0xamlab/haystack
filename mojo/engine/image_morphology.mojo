"""
image_morphology.mojo — Binary morphology and connected-region helpers on flat buffers. Zero Python imports.

Pixels are interpreted as row-major grayscale or mask values. Any value greater
than or equal to `fg_threshold` is foreground. Binary outputs use 255.0 for
foreground and 0.0 for background.

Public API:
  binary_erode_flat            — square-kernel binary erosion
  binary_dilate_flat           — square-kernel binary dilation
  binary_open_flat             — erosion followed by dilation
  binary_close_flat            — dilation followed by erosion
  binary_fill_holes_flat       — fill background holes not connected to the border
  connected_components_4_flat  — 4-connected component labels as a flat Int list
  largest_component_bbox_flat  — [x0, y0, x1, y1, area] for the largest component
  distance_transform_cityblock_flat — city-block distance to background for foreground pixels
  foreground_area_ratio_flat   — foreground pixel fraction in [0, 1]
"""


fn _pixel_count(width: Int, height: Int) -> Int:
    if width <= 0 or height <= 0:
        return 0
    return width * height


fn _pixel_value(flat: List[Float64], index: Int) -> Float64:
    if index < 0 or index >= len(flat):
        return 0.0
    return flat[index]


fn _is_foreground(flat: List[Float64], index: Int, fg_threshold: Float64) -> Bool:
    return _pixel_value(flat, index) >= fg_threshold


fn _normalized_kernel_size(kernel_size: Int) -> Int:
    var size = kernel_size
    if size <= 0:
        size = 1
    if size % 2 == 0:
        size += 1
    return size


fn _binary_output_value(is_foreground: Bool) -> Float64:
    return 255.0 if is_foreground else 0.0


fn binary_erode_flat(
    flat: List[Float64], width: Int, height: Int, kernel_size: Int, fg_threshold: Float64
) -> List[Float64]:
    """Binary erosion with a square kernel. Even kernel sizes round up to the next odd size."""
    var out = List[Float64]()
    var pixels = _pixel_count(width, height)
    if pixels <= 0:
        return out^

    var size = _normalized_kernel_size(kernel_size)
    var radius = size // 2
    for y in range(height):
        for x in range(width):
            var keep = True
            for ky in range(size):
                var ny = y + ky - radius
                if ny < 0 or ny >= height:
                    keep = False
                    break
                for kx in range(size):
                    var nx = x + kx - radius
                    if nx < 0 or nx >= width:
                        keep = False
                        break
                    if not _is_foreground(flat, ny * width + nx, fg_threshold):
                        keep = False
                        break
                if not keep:
                    break
            out.append(_binary_output_value(keep))
    return out^


fn binary_dilate_flat(
    flat: List[Float64], width: Int, height: Int, kernel_size: Int, fg_threshold: Float64
) -> List[Float64]:
    """Binary dilation with a square kernel. Even kernel sizes round up to the next odd size."""
    var out = List[Float64]()
    var pixels = _pixel_count(width, height)
    if pixels <= 0:
        return out^

    var size = _normalized_kernel_size(kernel_size)
    var radius = size // 2
    for y in range(height):
        for x in range(width):
            var hit = False
            for ky in range(size):
                var ny = y + ky - radius
                if ny < 0 or ny >= height:
                    continue
                for kx in range(size):
                    var nx = x + kx - radius
                    if nx < 0 or nx >= width:
                        continue
                    if _is_foreground(flat, ny * width + nx, fg_threshold):
                        hit = True
                        break
                if hit:
                    break
            out.append(_binary_output_value(hit))
    return out^


fn binary_open_flat(
    flat: List[Float64], width: Int, height: Int, kernel_size: Int, fg_threshold: Float64
) -> List[Float64]:
    """Binary opening: erosion followed by dilation."""
    return binary_dilate_flat(
        binary_erode_flat(flat, width, height, kernel_size, fg_threshold),
        width,
        height,
        kernel_size,
        128.0,
    )


fn binary_close_flat(
    flat: List[Float64], width: Int, height: Int, kernel_size: Int, fg_threshold: Float64
) -> List[Float64]:
    """Binary closing: dilation followed by erosion."""
    return binary_erode_flat(
        binary_dilate_flat(flat, width, height, kernel_size, fg_threshold),
        width,
        height,
        kernel_size,
        128.0,
    )


fn binary_fill_holes_flat(
    flat: List[Float64], width: Int, height: Int, fg_threshold: Float64
) -> List[Float64]:
    """Fill interior background holes while preserving border-connected background."""
    var out = List[Float64]()
    var pixels = _pixel_count(width, height)
    if pixels <= 0:
        return out^

    var visited = List[Int]()
    for _ in range(pixels):
        visited.append(0)
    var stack = List[Int]()

    for x in range(width):
        var top = x
        if not _is_foreground(flat, top, fg_threshold) and visited[top] == 0:
            visited[top] = 1
            stack.append(top)
        var bottom = (height - 1) * width + x
        if not _is_foreground(flat, bottom, fg_threshold) and visited[bottom] == 0:
            visited[bottom] = 1
            stack.append(bottom)
    for y in range(height):
        var left = y * width
        if not _is_foreground(flat, left, fg_threshold) and visited[left] == 0:
            visited[left] = 1
            stack.append(left)
        var right = y * width + width - 1
        if not _is_foreground(flat, right, fg_threshold) and visited[right] == 0:
            visited[right] = 1
            stack.append(right)
    while len(stack) > 0:
        var current = stack[len(stack) - 1]
        stack.pop()
        var x = current % width
        var y = current // width
        if x > 0:
            var left = current - 1
            if not _is_foreground(flat, left, fg_threshold) and visited[left] == 0:
                visited[left] = 1
                stack.append(left)
        if x + 1 < width:
            var right = current + 1
            if not _is_foreground(flat, right, fg_threshold) and visited[right] == 0:
                visited[right] = 1
                stack.append(right)
        if y > 0:
            var up = current - width
            if not _is_foreground(flat, up, fg_threshold) and visited[up] == 0:
                visited[up] = 1
                stack.append(up)
        if y + 1 < height:
            var down = current + width
            if not _is_foreground(flat, down, fg_threshold) and visited[down] == 0:
                visited[down] = 1
                stack.append(down)
    for index in range(pixels):
        var filled = _is_foreground(flat, index, fg_threshold) or visited[index] == 0
        out.append(_binary_output_value(filled))
    return out^


fn connected_components_4_flat(
    flat: List[Float64], width: Int, height: Int, fg_threshold: Float64
) -> List[Int]:
    """4-connected component labels for foreground pixels. Background pixels remain 0."""
    var pixels = _pixel_count(width, height)
    var labels = List[Int]()
    for _ in range(pixels):
        labels.append(0)
    if pixels <= 0:
        return labels^

    var label = 0
    var stack = List[Int]()
    for index in range(pixels):
        if labels[index] != 0 or not _is_foreground(flat, index, fg_threshold):
            continue
        label += 1
        labels[index] = label
        stack.append(index)
        while len(stack) > 0:
            var current = stack[len(stack) - 1]
            stack.pop()
            var x = current % width
            var y = current // width
            if x > 0:
                var left = current - 1
                if labels[left] == 0 and _is_foreground(flat, left, fg_threshold):
                    labels[left] = label
                    stack.append(left)
            if x + 1 < width:
                var right = current + 1
                if labels[right] == 0 and _is_foreground(flat, right, fg_threshold):
                    labels[right] = label
                    stack.append(right)
            if y > 0:
                var up = current - width
                if labels[up] == 0 and _is_foreground(flat, up, fg_threshold):
                    labels[up] = label
                    stack.append(up)
            if y + 1 < height:
                var down = current + width
                if labels[down] == 0 and _is_foreground(flat, down, fg_threshold):
                    labels[down] = label
                    stack.append(down)
    return labels^


fn largest_component_bbox_flat(
    flat: List[Float64], width: Int, height: Int, fg_threshold: Float64
) -> List[Int]:
    """Largest 4-connected foreground component as [x0, y0, x1, y1, area]."""
    var out = List[Int]()
    var pixels = _pixel_count(width, height)
    if pixels <= 0:
        return out^

    var visited = List[Int]()
    for _ in range(pixels):
        visited.append(0)
    var stack = List[Int]()
    var best_area = 0
    var best_x0 = 0
    var best_y0 = 0
    var best_x1 = -1
    var best_y1 = -1

    for index in range(pixels):
        if visited[index] != 0 or not _is_foreground(flat, index, fg_threshold):
            continue
        stack.append(index)
        visited[index] = 1
        var area = 0
        var min_x = width
        var min_y = height
        var max_x = -1
        var max_y = -1
        while len(stack) > 0:
            var current = stack[len(stack) - 1]
            stack.pop()
            var x = current % width
            var y = current // width
            area += 1
            if x < min_x:
                min_x = x
            if y < min_y:
                min_y = y
            if x > max_x:
                max_x = x
            if y > max_y:
                max_y = y
            if x > 0:
                var left = current - 1
                if visited[left] == 0 and _is_foreground(flat, left, fg_threshold):
                    visited[left] = 1
                    stack.append(left)
            if x + 1 < width:
                var right = current + 1
                if visited[right] == 0 and _is_foreground(flat, right, fg_threshold):
                    visited[right] = 1
                    stack.append(right)
            if y > 0:
                var up = current - width
                if visited[up] == 0 and _is_foreground(flat, up, fg_threshold):
                    visited[up] = 1
                    stack.append(up)
            if y + 1 < height:
                var down = current + width
                if visited[down] == 0 and _is_foreground(flat, down, fg_threshold):
                    visited[down] = 1
                    stack.append(down)
        if area > best_area:
            best_area = area
            best_x0 = min_x
            best_y0 = min_y
            best_x1 = max_x
            best_y1 = max_y

    if best_area <= 0:
        return out^
    out.append(best_x0)
    out.append(best_y0)
    out.append(best_x1)
    out.append(best_y1)
    out.append(best_area)
    return out^


fn distance_transform_cityblock_flat(
    flat: List[Float64], width: Int, height: Int, fg_threshold: Float64
) -> List[Int]:
    """Foreground city-block distance to the nearest background pixel; background pixels stay 0."""
    var pixels = _pixel_count(width, height)
    var out = List[Int]()
    if pixels <= 0:
        return out^

    var max_distance = width + height + 1
    for index in range(pixels):
        if _is_foreground(flat, index, fg_threshold):
            out.append(max_distance)
        else:
            out.append(0)
    for y in range(height):
        for x in range(width):
            var index = y * width + x
            if out[index] == 0:
                continue
            var best = out[index]
            if x > 0 and out[index - 1] + 1 < best:
                best = out[index - 1] + 1
            if y > 0 and out[index - width] + 1 < best:
                best = out[index - width] + 1
            out[index] = best
    for y_rev in range(height):
        var y = height - 1 - y_rev
        for x_rev in range(width):
            var x = width - 1 - x_rev
            var index = y * width + x
            if out[index] == 0:
                continue
            var best = out[index]
            if x + 1 < width and out[index + 1] + 1 < best:
                best = out[index + 1] + 1
            if y + 1 < height and out[index + width] + 1 < best:
                best = out[index + width] + 1
            out[index] = best
    return out^


fn foreground_area_ratio_flat(
    flat: List[Float64], width: Int, height: Int, fg_threshold: Float64
) -> Float64:
    """Foreground pixel fraction in [0, 1]."""
    var pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0
    var count = 0
    for index in range(pixels):
        if _is_foreground(flat, index, fg_threshold):
            count += 1
    return Float64(count) / Float64(pixels)
