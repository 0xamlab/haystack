"""Python equivalent of mojo/engine/image_morphology.mojo (auto-generated)."""
import math
import random as _rng

def random_float64(lo=0.0, hi=1.0): return _rng.uniform(lo, hi)
def random_si64(): return _rng.randint(-2**31, 2**31)
def random_ui64(): return _rng.randint(0, 2**32)

def json_get_string(raw, key, default=''):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return str(v) if v is not None else default
    except Exception: return default
def json_get_float(raw, key, default=0.0):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return float(v) if v is not None else default
    except Exception: return default
def json_get_int(raw, key, default=0):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return int(v) if v is not None else default
    except Exception: return default
def json_get_bool(raw, key, default=False):
    try:
        import json as _j; v = _j.loads(raw).get(key)
        return bool(v) if v is not None else default
    except Exception: return default
def json_get_object(raw, key, default='{}'):
    try:
        import json as _j; v = _j.loads(raw).get(key, {})
        return _j.dumps(v) if isinstance(v, dict) else default
    except Exception: return default
def json_get_array(raw, key, default='[]'):
    try:
        import json as _j; v = _j.loads(raw).get(key, [])
        return _j.dumps(v) if isinstance(v, list) else default
    except Exception: return default
def json_array_len(arr):
    try:
        import json as _j; return len(_j.loads(arr))
    except Exception: return 0
def json_array_get(arr, index):
    try:
        import json as _j; v = _j.loads(arr)
        return _j.dumps(v[index]) if index < len(v) else ''
    except Exception: return ''
def to_lower(s): return s.lower()
def contains_keyword(text, keyword): return keyword.lower() in text.lower()
def detect_polarity(field_name):
    n = field_name.lower()
    if any(k in n for k in ('cost','expense','loss','debit','charge','penalty','tax')): return -1
    if any(k in n for k in ('revenue','profit','income','gain','credit','sales')): return 1
    return 0
def detect_unit_hint(field_name):
    n = field_name.lower()
    if any(k in n for k in ('cost','price','revenue','profit','amount','value','dollar')): return 'currency'
    if any(k in n for k in ('pct','percent','ratio','rate','margin')): return 'percentage'
    if any(k in n for k in ('qty','quantity','count','units','volume')): return 'count'
    return ''
def infer_distribution_from_values(values): return ('normal', '{}')
def map_fields(raw): return []
def build_objective_function(mappings): return ''
def build_variables_json(mappings): return '[]'
class FieldMapping: pass
def dice_coefficient(a, b):
    if not a or not b: return 0.0
    def _bg(s): return set(s[i:i+2] for i in range(len(s)-1))
    ag, bg = _bg(a), _bg(b)
    if not ag or not bg: return 0.0
    return 2.0 * len(ag & bg) / (len(ag) + len(bg))
def edit_similarity(a, b):
    if not a and not b: return 1.0
    if not a or not b: return 0.0
    m, n = len(a), len(b); dp = list(range(n+1))
    for i in range(1, m+1):
        prev, dp[0] = dp[0], i
        for j in range(1, n+1):
            t = dp[j]; dp[j] = prev if a[i-1]==b[j-1] else 1+min(prev,dp[j],dp[j-1]); prev=t
    return 1.0 - dp[n] / max(m, n)
def jaccard_index(a, b):
    sa, sb = set(a), set(b)
    if not sa and not sb: return 1.0
    if not sa or not sb: return 0.0
    return len(sa & sb) / len(sa | sb)
def to_set(lst): return list(set(lst))
def parse_float64(s, default=0.0):
    try: return float(s)
    except Exception: return default
def parse_int(s, default=0):
    try: return int(float(s))
    except Exception: return default
DIM_UNKNOWN = 0; DIM_COUNT = 1; DIM_CURRENCY = 2; DIM_RATE = 3
DIM_RATIO = 4; DIM_IDENTIFIER = 5; DIM_INVALID = -1
def infer_from_samples(values): return DIM_UNKNOWN
def propagate(a, b, op): return DIM_UNKNOWN
def role_for_dimension(dim): return 'metric'
class Python:
    @staticmethod
    def import_module(name):
        import importlib; return importlib.import_module(name)

def _pixel_count(width, height):
    if width <= 0 or height <= 0:
        return 0
    return width * height



def _pixel_value(flat, index):
    if index < 0 or index >= len(flat):
        return 0.0
    return flat[index]



def _is_foreground(flat, index, fg_threshold):
    return _pixel_value(flat, index) >= fg_threshold



def _normalized_kernel_size(kernel_size):
    size = kernel_size
    if size <= 0:
        size = 1
    if size % 2 == 0:
        size += 1
    return size



def _binary_output_value(is_foreground):
    return 255.0 if is_foreground else 0.0



def binary_erode_flat(flat, width, height, kernel_size, fg_threshold):
    out = []
    pixels = _pixel_count(width, height)
    if pixels <= 0:
        return out

    size = _normalized_kernel_size(kernel_size)
    radius = size // 2
    for y in range(height):
        for x in range(width):
            keep = True
            for ky in range(size):
                ny = y + ky - radius
                if ny < 0 or ny >= height:
                    keep = False
                    break
                for kx in range(size):
                    nx = x + kx - radius
                    if nx < 0 or nx >= width:
                        keep = False
                        break
                    if not _is_foreground(flat, ny * width + nx, fg_threshold):
                        keep = False
                        break
                if not keep:
                    break
            out.append(_binary_output_value(keep))
    return out



def binary_dilate_flat(flat, width, height, kernel_size, fg_threshold):
    out = []
    pixels = _pixel_count(width, height)
    if pixels <= 0:
        return out

    size = _normalized_kernel_size(kernel_size)
    radius = size // 2
    for y in range(height):
        for x in range(width):
            hit = False
            for ky in range(size):
                ny = y + ky - radius
                if ny < 0 or ny >= height:
                    continue
                for kx in range(size):
                    nx = x + kx - radius
                    if nx < 0 or nx >= width:
                        continue
                    if _is_foreground(flat, ny * width + nx, fg_threshold):
                        hit = True
                        break
                if hit:
                    break
            out.append(_binary_output_value(hit))
    return out



def binary_open_flat(flat, width, height, kernel_size, fg_threshold):
    return binary_dilate_flat(
        binary_erode_flat(flat, width, height, kernel_size, fg_threshold),
        width,
        height,
        kernel_size,
        128.0,
    )



def binary_close_flat(flat, width, height, kernel_size, fg_threshold):
    return binary_erode_flat(
        binary_dilate_flat(flat, width, height, kernel_size, fg_threshold),
        width,
        height,
        kernel_size,
        128.0,
    )



def binary_fill_holes_flat(flat, width, height, fg_threshold):
    out = []
    pixels = _pixel_count(width, height)
    if pixels <= 0:
        return out

    visited = []
    for _ in range(pixels):
        visited.append(0)
    stack = []

    for x in range(width):
        top = x
        if not _is_foreground(flat, top, fg_threshold) and visited[top] == 0:
            visited[top] = 1
            stack.append(top)
        bottom = (height - 1) * width + x
        if not _is_foreground(flat, bottom, fg_threshold) and visited[bottom] == 0:
            visited[bottom] = 1
            stack.append(bottom)
    for y in range(height):
        left = y * width
        if not _is_foreground(flat, left, fg_threshold) and visited[left] == 0:
            visited[left] = 1
            stack.append(left)
        right = y * width + width - 1
        if not _is_foreground(flat, right, fg_threshold) and visited[right] == 0:
            visited[right] = 1
            stack.append(right)
    while len(stack) > 0:
        current = stack[len(stack) - 1]
        stack.pop()
        x = current % width
        y = current // width
        if x > 0:
            left = current - 1
            if not _is_foreground(flat, left, fg_threshold) and visited[left] == 0:
                visited[left] = 1
                stack.append(left)
        if x + 1 < width:
            right = current + 1
            if not _is_foreground(flat, right, fg_threshold) and visited[right] == 0:
                visited[right] = 1
                stack.append(right)
        if y > 0:
            up = current - width
            if not _is_foreground(flat, up, fg_threshold) and visited[up] == 0:
                visited[up] = 1
                stack.append(up)
        if y + 1 < height:
            down = current + width
            if not _is_foreground(flat, down, fg_threshold) and visited[down] == 0:
                visited[down] = 1
                stack.append(down)
    for index in range(pixels):
        filled = _is_foreground(flat, index, fg_threshold) or visited[index] == 0
        out.append(_binary_output_value(filled))
    return out



def connected_components_4_flat(flat, width, height, fg_threshold):
    pixels = _pixel_count(width, height)
    labels = []
    for _ in range(pixels):
        labels.append(0)
    if pixels <= 0:
        return labels

    label = 0
    stack = []
    for index in range(pixels):
        if labels[index] != 0 or not _is_foreground(flat, index, fg_threshold):
            continue
        label += 1
        labels[index] = label
        stack.append(index)
        while len(stack) > 0:
            current = stack[len(stack) - 1]
            stack.pop()
            x = current % width
            y = current // width
            if x > 0:
                left = current - 1
                if labels[left] == 0 and _is_foreground(flat, left, fg_threshold):
                    labels[left] = label
                    stack.append(left)
            if x + 1 < width:
                right = current + 1
                if labels[right] == 0 and _is_foreground(flat, right, fg_threshold):
                    labels[right] = label
                    stack.append(right)
            if y > 0:
                up = current - width
                if labels[up] == 0 and _is_foreground(flat, up, fg_threshold):
                    labels[up] = label
                    stack.append(up)
            if y + 1 < height:
                down = current + width
                if labels[down] == 0 and _is_foreground(flat, down, fg_threshold):
                    labels[down] = label
                    stack.append(down)
    return labels



def largest_component_bbox_flat(flat, width, height, fg_threshold):
    out = []
    pixels = _pixel_count(width, height)
    if pixels <= 0:
        return out

    visited = []
    for _ in range(pixels):
        visited.append(0)
    stack = []
    best_area = 0
    best_x0 = 0
    best_y0 = 0
    best_x1 = -1
    best_y1 = -1

    for index in range(pixels):
        if visited[index] != 0 or not _is_foreground(flat, index, fg_threshold):
            continue
        stack.append(index)
        visited[index] = 1
        area = 0
        min_x = width
        min_y = height
        max_x = -1
        max_y = -1
        while len(stack) > 0:
            current = stack[len(stack) - 1]
            stack.pop()
            x = current % width
            y = current // width
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
                left = current - 1
                if visited[left] == 0 and _is_foreground(flat, left, fg_threshold):
                    visited[left] = 1
                    stack.append(left)
            if x + 1 < width:
                right = current + 1
                if visited[right] == 0 and _is_foreground(flat, right, fg_threshold):
                    visited[right] = 1
                    stack.append(right)
            if y > 0:
                up = current - width
                if visited[up] == 0 and _is_foreground(flat, up, fg_threshold):
                    visited[up] = 1
                    stack.append(up)
            if y + 1 < height:
                down = current + width
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
        return out
    out.append(best_x0)
    out.append(best_y0)
    out.append(best_x1)
    out.append(best_y1)
    out.append(best_area)
    return out



def distance_transform_cityblock_flat(flat, width, height, fg_threshold):
    pixels = _pixel_count(width, height)
    out = []
    if pixels <= 0:
        return out

    max_distance = width + height + 1
    for index in range(pixels):
        if _is_foreground(flat, index, fg_threshold):
            out.append(max_distance)
        else:
            out.append(0)
    for y in range(height):
        for x in range(width):
            index = y * width + x
            if out[index] == 0:
                continue
            best = out[index]
            if x > 0 and out[index - 1] + 1 < best:
                best = out[index - 1] + 1
            if y > 0 and out[index - width] + 1 < best:
                best = out[index - width] + 1
            out[index] = best
    for y_rev in range(height):
        y = height - 1 - y_rev
        for x_rev in range(width):
            x = width - 1 - x_rev
            index = y * width + x
            if out[index] == 0:
                continue
            best = out[index]
            if x + 1 < width and out[index + 1] + 1 < best:
                best = out[index + 1] + 1
            if y + 1 < height and out[index + width] + 1 < best:
                best = out[index + width] + 1
            out[index] = best
    return out



def foreground_area_ratio_flat(flat, width, height, fg_threshold):
    pixels = _pixel_count(width, height)
    if pixels <= 0:
        return 0.0
    count = 0
    for index in range(pixels):
        if _is_foreground(flat, index, fg_threshold):
            count += 1
    return float(count) / float(pixels)
