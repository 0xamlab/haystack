"""
heap.mojo — Heap data structures. Zero Python imports.

Replaces Python's heapq module with pure Mojo min-heap and max-heap
implementations, plus advanced operations like k-smallest, k-largest,
k-way merge, and running median.

Public API:
  heapify_min        — Build min-heap in place
  heapify_max        — Build max-heap in place
  heap_push_min      — Push value to min-heap
  heap_pop_min       — Pop minimum from min-heap
  heap_push_max      — Push value to max-heap
  heap_pop_max       — Pop maximum from max-heap
  heap_peek_min      — View minimum without removing
  heap_peek_max      — View maximum without removing
  k_smallest         — Find k smallest elements
  k_largest          — Find k largest elements
  merge_sorted_lists — K-way merge of sorted lists
  running_median     — Running median over data stream
  is_min_heap        — Verify min-heap property
"""


# ── Internal helpers ──────────────────────────────────────────────────────────


fn _swap(mut data: List[Float64], i: Int, j: Int):
    """Swap two elements in list."""
    var tmp = data[i]
    data[i] = data[j]
    data[j] = tmp


fn _sift_down_min(mut data: List[Float64], start: Int, end: Int):
    """Sift element at start down to maintain min-heap property."""
    var root = start
    while True:
        var child = 2 * root + 1
        if child > end:
            break
        var swap_idx = root
        if data[child] < data[swap_idx]:
            swap_idx = child
        if child + 1 <= end and data[child + 1] < data[swap_idx]:
            swap_idx = child + 1
        if swap_idx == root:
            break
        _swap(data, root, swap_idx)
        root = swap_idx


fn _sift_up_min(mut data: List[Float64], pos: Int):
    """Sift element at pos up to maintain min-heap property."""
    var child = pos
    while child > 0:
        var parent = (child - 1) // 2
        if data[child] < data[parent]:
            _swap(data, child, parent)
            child = parent
        else:
            break


fn _sift_down_max(mut data: List[Float64], start: Int, end: Int):
    """Sift element at start down to maintain max-heap property."""
    var root = start
    while True:
        var child = 2 * root + 1
        if child > end:
            break
        var swap_idx = root
        if data[child] > data[swap_idx]:
            swap_idx = child
        if child + 1 <= end and data[child + 1] > data[swap_idx]:
            swap_idx = child + 1
        if swap_idx == root:
            break
        _swap(data, root, swap_idx)
        root = swap_idx


fn _sift_up_max(mut data: List[Float64], pos: Int):
    """Sift element at pos up to maintain max-heap property."""
    var child = pos
    while child > 0:
        var parent = (child - 1) // 2
        if data[child] > data[parent]:
            _swap(data, child, parent)
            child = parent
        else:
            break


# ── heapify_min ───────────────────────────────────────────────────────────────


fn heapify_min(mut data: List[Float64]):
    """Build min-heap in place. O(n) time."""
    var n = len(data)
    var start = (n - 2) // 2
    while start >= 0:
        _sift_down_min(data, start, n - 1)
        start -= 1


# ── heapify_max ───────────────────────────────────────────────────────────────


fn heapify_max(mut data: List[Float64]):
    """Build max-heap in place. O(n) time."""
    var n = len(data)
    var start = (n - 2) // 2
    while start >= 0:
        _sift_down_max(data, start, n - 1)
        start -= 1


# ── heap_push_min ─────────────────────────────────────────────────────────────


fn heap_push_min(mut heap: List[Float64], value: Float64):
    """Push value onto min-heap, maintaining heap property."""
    heap.append(value)
    _sift_up_min(heap, len(heap) - 1)


# ── heap_pop_min ──────────────────────────────────────────────────────────────


fn heap_pop_min(mut heap: List[Float64]) -> Float64:
    """Pop and return minimum from min-heap."""
    var n = len(heap)
    if n == 0:
        return 0.0
    if n == 1:
        return heap.pop()
    var result = heap[0]
    heap[0] = heap[n - 1]
    _ = heap.pop()
    if len(heap) > 0:
        _sift_down_min(heap, 0, len(heap) - 1)
    return result


# ── heap_push_max ─────────────────────────────────────────────────────────────


fn heap_push_max(mut heap: List[Float64], value: Float64):
    """Push value onto max-heap, maintaining heap property."""
    heap.append(value)
    _sift_up_max(heap, len(heap) - 1)


# ── heap_pop_max ──────────────────────────────────────────────────────────────


fn heap_pop_max(mut heap: List[Float64]) -> Float64:
    """Pop and return maximum from max-heap."""
    var n = len(heap)
    if n == 0:
        return 0.0
    if n == 1:
        return heap.pop()
    var result = heap[0]
    heap[0] = heap[n - 1]
    _ = heap.pop()
    if len(heap) > 0:
        _sift_down_max(heap, 0, len(heap) - 1)
    return result


# ── heap_peek_min ─────────────────────────────────────────────────────────────


fn heap_peek_min(heap: List[Float64]) -> Float64:
    """View minimum element without removing. Returns 0.0 if empty."""
    if len(heap) == 0:
        return 0.0
    return heap[0]


# ── heap_peek_max ─────────────────────────────────────────────────────────────


fn heap_peek_max(heap: List[Float64]) -> Float64:
    """View maximum element without removing. Returns 0.0 if empty."""
    if len(heap) == 0:
        return 0.0
    return heap[0]


# ── k_smallest ────────────────────────────────────────────────────────────────


fn k_smallest(data: List[Float64], k: Int) -> List[Float64]:
    """Find k smallest elements using a max-heap of size k.

    Returns unsorted list of k smallest values. O(n log k).
    """
    var n = len(data)
    var kk = min(k, n)
    if kk <= 0:
        return List[Float64]()

    # Build max-heap of first k elements
    var heap = List[Float64]()
    for i in range(kk):
        heap.append(data[i])
    heapify_max(heap)

    # Process remaining elements
    for i in range(kk, n):
        if data[i] < heap[0]:
            heap[0] = data[i]
            _sift_down_max(heap, 0, kk - 1)

    # Sort result for deterministic output
    _simple_sort(heap)
    return heap^


# ── k_largest ─────────────────────────────────────────────────────────────────


fn k_largest(data: List[Float64], k: Int) -> List[Float64]:
    """Find k largest elements using a min-heap of size k.

    Returns unsorted list of k largest values. O(n log k).
    """
    var n = len(data)
    var kk = min(k, n)
    if kk <= 0:
        return List[Float64]()

    # Build min-heap of first k elements
    var heap = List[Float64]()
    for i in range(kk):
        heap.append(data[i])
    heapify_min(heap)

    # Process remaining elements
    for i in range(kk, n):
        if data[i] > heap[0]:
            heap[0] = data[i]
            _sift_down_min(heap, 0, kk - 1)

    # Sort result for deterministic output
    _simple_sort(heap)
    return heap^


fn _simple_sort(mut data: List[Float64]):
    """Simple insertion sort for small lists."""
    var n = len(data)
    for i in range(1, n):
        var key = data[i]
        var j = i - 1
        while j >= 0 and data[j] > key:
            data[j + 1] = data[j]
            j -= 1
        data[j + 1] = key


# ── merge_sorted_lists ────────────────────────────────────────────────────────


fn merge_sorted_lists(lists: List[List[Float64]]) -> List[Float64]:
    """K-way merge of sorted lists using min-heap.

    Each input list must be sorted in ascending order.
    Returns single sorted list containing all elements.
    """
    var k = len(lists)
    if k == 0:
        return List[Float64]()

    # Use indices to track position in each list
    var indices = List[Int]()
    for i in range(k):
        indices.append(0)

    var result = List[Float64]()
    var total = 0
    for i in range(k):
        total += len(lists[i])

    for _ in range(total):
        var best_val: Float64 = 1e308
        var best_list = -1
        for j in range(k):
            if indices[j] < len(lists[j]):
                if lists[j][indices[j]] < best_val:
                    best_val = lists[j][indices[j]]
                    best_list = j
        if best_list == -1:
            break
        result.append(best_val)
        indices[best_list] = indices[best_list] + 1

    return result^


# ── running_median ────────────────────────────────────────────────────────────


fn running_median(data: List[Float64]) -> List[Float64]:
    """Compute running median for each prefix of data.

    For prefix of length n: if n is odd, median is middle element;
    if n is even, median is average of two middle elements.
    Uses sort-based approach for correctness.
    """
    var result = List[Float64]()
    var n = len(data)
    if n == 0:
        return result^

    for i in range(n):
        # Build sorted prefix
        var prefix = List[Float64]()
        for j in range(i + 1):
            prefix.append(data[j])
        _simple_sort(prefix)

        var plen = len(prefix)
        if plen % 2 == 1:
            result.append(prefix[plen // 2])
        else:
            result.append((prefix[plen // 2 - 1] + prefix[plen // 2]) / 2.0)

    return result^


# ── is_min_heap ───────────────────────────────────────────────────────────────


fn is_min_heap(data: List[Float64]) -> Bool:
    """Verify that data satisfies the min-heap property.

    For every node i, data[i] <= data[2*i+1] and data[i] <= data[2*i+2].
    """
    var n = len(data)
    for i in range(n):
        var left = 2 * i + 1
        var right = 2 * i + 2
        if left < n and data[i] > data[left]:
            return False
        if right < n and data[i] > data[right]:
            return False
    return True
