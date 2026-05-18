"""
sorting.mojo — Sorting algorithms. Zero Python imports.

Replaces Python sort internals with named, pure Mojo implementations
of classic sorting algorithms plus utility functions.

Public API:
  quicksort        — Quicksort with Lomuto partition
  mergesort        — Top-down recursive merge sort
  heapsort         — Heap sort via max-heap
  insertion_sort   — Insertion sort
  selection_sort   — Selection sort
  bubble_sort      — Bubble sort with early termination
  counting_sort_int — Counting sort for non-negative integers
  is_sorted        — Check if list is sorted ascending
  reverse_list     — Reverse a list
  nth_smallest     — Find nth smallest element (0-indexed)
"""


# ── _swap ────────────────────────────────────────────────────────────────────


fn _swap(mut data: List[Float64], i: Int, j: Int):
    """Swap elements at indices i and j."""
    var tmp = data[i]
    data[i] = data[j]
    data[j] = tmp


# ── quicksort ────────────────────────────────────────────────────────────────


fn _lomuto_partition(mut data: List[Float64], lo: Int, hi: Int) -> Int:
    """Lomuto partition scheme. Returns pivot index."""
    var pivot = data[hi]
    var i = lo
    for j in range(lo, hi):
        if data[j] <= pivot:
            _swap(data, i, j)
            i += 1
    _swap(data, i, hi)
    return i


fn _quicksort_impl(mut data: List[Float64], lo: Int, hi: Int):
    """Recursive quicksort helper."""
    if lo < hi:
        var p = _lomuto_partition(data, lo, hi)
        _quicksort_impl(data, lo, p - 1)
        _quicksort_impl(data, p + 1, hi)


fn quicksort(data: List[Float64]) -> List[Float64]:
    """Quicksort with Lomuto partition. Returns sorted copy."""
    var result = List[Float64]()
    for i in range(len(data)):
        result.append(data[i])
    if len(result) > 1:
        _quicksort_impl(result, 0, len(result) - 1)
    return result^


# ── mergesort ────────────────────────────────────────────────────────────────


fn _merge(a: List[Float64], b: List[Float64]) -> List[Float64]:
    """Merge two sorted lists into one sorted list."""
    var result = List[Float64]()
    var i = 0
    var j = 0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            result.append(a[i])
            i += 1
        else:
            result.append(b[j])
            j += 1
    while i < len(a):
        result.append(a[i])
        i += 1
    while j < len(b):
        result.append(b[j])
        j += 1
    return result^


fn _mergesort_impl(data: List[Float64]) -> List[Float64]:
    """Recursive merge sort."""
    if len(data) <= 1:
        var copy = List[Float64]()
        for i in range(len(data)):
            copy.append(data[i])
        return copy^
    var mid = len(data) // 2
    var left = List[Float64]()
    var right = List[Float64]()
    for i in range(mid):
        left.append(data[i])
    for i in range(mid, len(data)):
        right.append(data[i])
    var sorted_left = _mergesort_impl(left^)
    var sorted_right = _mergesort_impl(right^)
    return _merge(sorted_left^, sorted_right^)


fn mergesort(data: List[Float64]) -> List[Float64]:
    """Top-down recursive merge sort. Returns sorted copy."""
    return _mergesort_impl(data)


# ── heapsort ─────────────────────────────────────────────────────────────────


fn _sift_down(mut data: List[Float64], start: Int, end: Int):
    """Sift down element at start to maintain max-heap property."""
    var root = start
    while root * 2 + 1 <= end:
        var child = root * 2 + 1
        var swap_idx = root
        if data[swap_idx] < data[child]:
            swap_idx = child
        if child + 1 <= end and data[swap_idx] < data[child + 1]:
            swap_idx = child + 1
        if swap_idx == root:
            return
        _swap(data, root, swap_idx)
        root = swap_idx


fn heapsort(data: List[Float64]) -> List[Float64]:
    """Heap sort via max-heap. Returns sorted copy."""
    var result = List[Float64]()
    for i in range(len(data)):
        result.append(data[i])
    var n = len(result)
    if n <= 1:
        return result^
    # Build max-heap
    var start = (n - 2) // 2
    while start >= 0:
        _sift_down(result, start, n - 1)
        start -= 1
    # Extract elements
    var end = n - 1
    while end > 0:
        _swap(result, 0, end)
        end -= 1
        _sift_down(result, 0, end)
    return result^


# ── insertion_sort ───────────────────────────────────────────────────────────


fn insertion_sort(data: List[Float64]) -> List[Float64]:
    """Insertion sort. Returns sorted copy."""
    var result = List[Float64]()
    for i in range(len(data)):
        result.append(data[i])
    for i in range(1, len(result)):
        var key = result[i]
        var j = i - 1
        while j >= 0 and result[j] > key:
            result[j + 1] = result[j]
            j -= 1
        result[j + 1] = key
    return result^


# ── selection_sort ───────────────────────────────────────────────────────────


fn selection_sort(data: List[Float64]) -> List[Float64]:
    """Selection sort. Returns sorted copy."""
    var result = List[Float64]()
    for i in range(len(data)):
        result.append(data[i])
    var n = len(result)
    for i in range(n):
        var min_idx = i
        for j in range(i + 1, n):
            if result[j] < result[min_idx]:
                min_idx = j
        if min_idx != i:
            _swap(result, i, min_idx)
    return result^


# ── bubble_sort ──────────────────────────────────────────────────────────────


fn bubble_sort(data: List[Float64]) -> List[Float64]:
    """Bubble sort with early termination. Returns sorted copy."""
    var result = List[Float64]()
    for i in range(len(data)):
        result.append(data[i])
    var n = len(result)
    for i in range(n):
        var swapped = False
        for j in range(0, n - i - 1):
            if result[j] > result[j + 1]:
                _swap(result, j, j + 1)
                swapped = True
        if not swapped:
            break
    return result^


# ── counting_sort_int ────────────────────────────────────────────────────────


fn counting_sort_int(data: List[Int]) -> List[Int]:
    """Counting sort for non-negative integers. Returns sorted copy."""
    if len(data) == 0:
        return List[Int]()
    # Find max
    var max_val = data[0]
    for i in range(1, len(data)):
        if data[i] > max_val:
            max_val = data[i]
    # Count occurrences
    var counts = List[Int]()
    for i in range(max_val + 1):
        counts.append(0)
    for i in range(len(data)):
        counts[data[i]] += 1
    # Build sorted output
    var result = List[Int]()
    for i in range(len(counts)):
        for _ in range(counts[i]):
            result.append(i)
    return result^


# ── is_sorted ────────────────────────────────────────────────────────────────


fn is_sorted(data: List[Float64]) -> Bool:
    """Check if list is sorted in ascending order."""
    for i in range(1, len(data)):
        if data[i] < data[i - 1]:
            return False
    return True


# ── reverse_list ─────────────────────────────────────────────────────────────


fn reverse_list(data: List[Float64]) -> List[Float64]:
    """Reverse a list. Returns new reversed list."""
    var result = List[Float64]()
    var i = len(data) - 1
    while i >= 0:
        result.append(data[i])
        i -= 1
    return result^


# ── nth_smallest ─────────────────────────────────────────────────────────────


fn nth_smallest(data: List[Float64], n: Int) -> Float64:
    """Find the nth smallest element (0-indexed) via sorting."""
    var sorted_data = quicksort(data)
    return sorted_data[n]
