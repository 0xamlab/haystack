"""
pipeline.mojo — Data Pipeline / Workflow utilities. Zero Python imports.

Replaces luigi/prefect core data-pipeline patterns with pure Mojo
map, filter, reduce, batch, window, flatten, and zip primitives.

Public API:
  map_list          — Apply operation to each element (square/sqrt/negate/abs/double)
  filter_list       — Filter elements by comparison to threshold
  reduce_sum        — Sum all elements
  reduce_product    — Product of all elements
  reduce_min        — Minimum element
  reduce_max        — Maximum element
  chain_map_filter  — Chain: first map, then filter
  batch             — Split data into fixed-size batches
  flatten           — Flatten list of lists into single list
  zip_lists         — Zip two lists into pairs
  window            — Sliding window of given size
  unique_values     — Unique values preserving order
"""
from std.math import sqrt, abs as fabs


# ── map_list ─────────────────────────────────────────────────────────────────


fn map_list(data: List[Float64], op: Int) -> List[Float64]:
    """Apply operation to each element.

    Args:
        data: Input list.
        op:   0=square, 1=sqrt, 2=negate, 3=abs, 4=double.

    Returns:
        New list with transformed values.
    """
    var result = List[Float64]()
    for i in range(len(data)):
        var v = data[i]
        if op == 0:
            result.append(v * v)
        elif op == 1:
            result.append(sqrt(v))
        elif op == 2:
            result.append(-v)
        elif op == 3:
            result.append(fabs(v))
        elif op == 4:
            result.append(v * 2.0)
        else:
            result.append(v)
    return result^


# ── filter_list ──────────────────────────────────────────────────────────────


fn filter_list(
    data: List[Float64], op: Int, threshold: Float64
) -> List[Float64]:
    """Filter elements by comparison to threshold.

    Args:
        data:      Input list.
        op:        0=keep > threshold, 1=keep < threshold,
                   2=keep == threshold (within 1e-9), 3=keep >= threshold.
        threshold: Comparison value.

    Returns:
        Filtered list.
    """
    var result = List[Float64]()
    for i in range(len(data)):
        var v = data[i]
        if op == 0 and v > threshold:
            result.append(v)
        elif op == 1 and v < threshold:
            result.append(v)
        elif op == 2 and fabs(v - threshold) < 1e-9:
            result.append(v)
        elif op == 3 and v >= threshold:
            result.append(v)
    return result^


# ── reduce_sum ───────────────────────────────────────────────────────────────


fn reduce_sum(data: List[Float64]) -> Float64:
    """Sum all elements. Returns 0.0 for empty list."""
    var s: Float64 = 0.0
    for i in range(len(data)):
        s += data[i]
    return s


# ── reduce_product ───────────────────────────────────────────────────────────


fn reduce_product(data: List[Float64]) -> Float64:
    """Product of all elements. Returns 1.0 for empty list."""
    var p: Float64 = 1.0
    for i in range(len(data)):
        p *= data[i]
    return p


# ── reduce_min ───────────────────────────────────────────────────────────────


fn reduce_min(data: List[Float64]) -> Float64:
    """Minimum element. Returns 1e308 for empty list."""
    if len(data) == 0:
        return 1e308
    var m = data[0]
    for i in range(1, len(data)):
        if data[i] < m:
            m = data[i]
    return m


# ── reduce_max ───────────────────────────────────────────────────────────────


fn reduce_max(data: List[Float64]) -> Float64:
    """Maximum element. Returns -1e308 for empty list."""
    if len(data) == 0:
        return -1e308
    var m = data[0]
    for i in range(1, len(data)):
        if data[i] > m:
            m = data[i]
    return m


# ── chain_map_filter ─────────────────────────────────────────────────────────


fn chain_map_filter(
    data: List[Float64], map_op: Int, filter_op: Int, threshold: Float64
) -> List[Float64]:
    """Chain: first map, then filter.

    Args:
        data:      Input list.
        map_op:    Operation code for map_list.
        filter_op: Operation code for filter_list.
        threshold: Threshold for filter_list.

    Returns:
        Result of map then filter.
    """
    var mapped = map_list(data, map_op)
    return filter_list(mapped, filter_op, threshold)


# ── batch ────────────────────────────────────────────────────────────────────


fn batch(data: List[Float64], batch_size: Int) -> List[List[Float64]]:
    """Split data into batches of given size (last batch may be smaller).

    Args:
        data:       Input list.
        batch_size: Size of each batch (must be >= 1).

    Returns:
        List of batches.
    """
    var result = List[List[Float64]]()
    var n = len(data)
    var i = 0
    while i < n:
        var b = List[Float64]()
        var end = i + batch_size
        if end > n:
            end = n
        for j in range(i, end):
            b.append(data[j])
        result.append(b^)
        i += batch_size
    return result^


# ── flatten ──────────────────────────────────────────────────────────────────


fn flatten(batches: List[List[Float64]]) -> List[Float64]:
    """Flatten list of lists into single list."""
    var result = List[Float64]()
    for i in range(len(batches)):
        for j in range(len(batches[i])):
            result.append(batches[i][j])
    return result^


# ── zip_lists ────────────────────────────────────────────────────────────────


fn zip_lists(a: List[Float64], b: List[Float64]) -> List[List[Float64]]:
    """Zip two lists into pairs [a_i, b_i]. Length = min(len(a), len(b))."""
    var n = len(a)
    if len(b) < n:
        n = len(b)
    var result = List[List[Float64]]()
    for i in range(n):
        var pair = List[Float64]()
        pair.append(a[i])
        pair.append(b[i])
        result.append(pair^)
    return result^


# ── window ───────────────────────────────────────────────────────────────────


fn window(data: List[Float64], size: Int) -> List[List[Float64]]:
    """Sliding window of given size.

    Args:
        data: Input list.
        size: Window size (must be >= 1).

    Returns:
        List of windows. Each window is a List[Float64] of length `size`.
    """
    var result = List[List[Float64]]()
    var n = len(data)
    if size <= 0 or size > n:
        return result^
    for i in range(n - size + 1):
        var w = List[Float64]()
        for j in range(i, i + size):
            w.append(data[j])
        result.append(w^)
    return result^


# ── unique_values ────────────────────────────────────────────────────────────


fn unique_values(data: List[Float64]) -> List[Float64]:
    """Unique values preserving first-occurrence order (tolerance 1e-12)."""
    var result = List[Float64]()
    for i in range(len(data)):
        var found = False
        for j in range(len(result)):
            if fabs(data[i] - result[j]) < 1e-12:
                found = True
                break
        if not found:
            result.append(data[i])
    return result^
