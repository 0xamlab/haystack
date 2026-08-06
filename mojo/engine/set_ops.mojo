"""
set_ops.mojo — Set operations on sorted List[Int]. Zero Python imports.

Replaces Python set operations with pure Mojo implementations operating
on sorted integer lists. All functions assume inputs are sorted and
deduplicated unless noted otherwise (use to_set to prepare raw data).

Public API:
  set_union                — merge two sorted lists without duplicates
  set_intersection         — elements in both sorted lists
  set_difference           — elements in a but not b
  set_symmetric_difference — elements in either but not both
  is_subset                — check if a ⊆ b
  is_superset              — check if a ⊇ b
  set_equals               — check if a == b
  power_set_size           — 2^n (size of power set)
  jaccard_index            — |A∩B| / |A∪B|
  to_set                   — sort and deduplicate a list
  set_contains             — binary search membership test
  set_cardinality          — number of elements
"""


# ── set_union ────────────────────────────────────────────────────────────────


def set_union(a: List[Int], b: List[Int]) -> List[Int]:
    """Union of two sorted lists (merge without duplicates)."""
    var result = List[Int]()
    var i = 0
    var j = 0
    var na = len(a)
    var nb = len(b)
    while i < na and j < nb:
        if a[i] < b[j]:
            result.append(a[i])
            i += 1
        elif a[i] > b[j]:
            result.append(b[j])
            j += 1
        else:
            result.append(a[i])
            i += 1
            j += 1
    while i < na:
        result.append(a[i])
        i += 1
    while j < nb:
        result.append(b[j])
        j += 1
    return result^


# ── set_intersection ─────────────────────────────────────────────────────────


def set_intersection(a: List[Int], b: List[Int]) -> List[Int]:
    """Intersection of two sorted lists."""
    var result = List[Int]()
    var i = 0
    var j = 0
    var na = len(a)
    var nb = len(b)
    while i < na and j < nb:
        if a[i] < b[j]:
            i += 1
        elif a[i] > b[j]:
            j += 1
        else:
            result.append(a[i])
            i += 1
            j += 1
    return result^


# ── set_difference ───────────────────────────────────────────────────────────


def set_difference(a: List[Int], b: List[Int]) -> List[Int]:
    """Elements in a but not in b (both sorted)."""
    var result = List[Int]()
    var i = 0
    var j = 0
    var na = len(a)
    var nb = len(b)
    while i < na and j < nb:
        if a[i] < b[j]:
            result.append(a[i])
            i += 1
        elif a[i] > b[j]:
            j += 1
        else:
            i += 1
            j += 1
    while i < na:
        result.append(a[i])
        i += 1
    return result^


# ── set_symmetric_difference ─────────────────────────────────────────────────


def set_symmetric_difference(a: List[Int], b: List[Int]) -> List[Int]:
    """Elements in either a or b but not both (both sorted)."""
    var result = List[Int]()
    var i = 0
    var j = 0
    var na = len(a)
    var nb = len(b)
    while i < na and j < nb:
        if a[i] < b[j]:
            result.append(a[i])
            i += 1
        elif a[i] > b[j]:
            result.append(b[j])
            j += 1
        else:
            i += 1
            j += 1
    while i < na:
        result.append(a[i])
        i += 1
    while j < nb:
        result.append(b[j])
        j += 1
    return result^


# ── is_subset ────────────────────────────────────────────────────────────────


def is_subset(a: List[Int], b: List[Int]) -> Bool:
    """Check if a ⊆ b (every element in a is in b). Both sorted."""
    var i = 0
    var j = 0
    var na = len(a)
    var nb = len(b)
    while i < na and j < nb:
        if a[i] < b[j]:
            return False
        elif a[i] > b[j]:
            j += 1
        else:
            i += 1
            j += 1
    return i == na


# ── is_superset ──────────────────────────────────────────────────────────────


def is_superset(a: List[Int], b: List[Int]) -> Bool:
    """Check if a ⊇ b (a contains every element of b). Both sorted."""
    return is_subset(b, a)


# ── set_equals ───────────────────────────────────────────────────────────────


def set_equals(a: List[Int], b: List[Int]) -> Bool:
    """Check if two sorted sets are equal."""
    var na = len(a)
    var nb = len(b)
    if na != nb:
        return False
    for i in range(na):
        if a[i] != b[i]:
            return False
    return True


# ── power_set_size ───────────────────────────────────────────────────────────


def power_set_size(n: Int) -> Int:
    """Size of power set: 2^n. Uses bit shift."""
    if n < 0:
        return 0
    if n >= 63:
        return -1  # overflow sentinel
    return 1 << n


# ── jaccard_index ────────────────────────────────────────────────────────────


def jaccard_index(a: List[Int], b: List[Int]) -> Float64:
    """|A∩B| / |A∪B|. Returns 1.0 for two empty sets."""
    var inter = set_intersection(a, b)
    var uni = set_union(a, b)
    var nu = len(uni)
    if nu == 0:
        return 1.0
    return Float64(len(inter)) / Float64(nu)


# ── to_set ───────────────────────────────────────────────────────────────────


def to_set(data: List[Int]) -> List[Int]:
    """Sort and deduplicate a list of ints (insertion sort for simplicity)."""
    var n = len(data)
    if n == 0:
        return List[Int]()
    # Copy
    var arr = List[Int]()
    for i in range(n):
        arr.append(data[i])
    # Insertion sort
    for i in range(1, n):
        var key = arr[i]
        var j = i - 1
        while j >= 0 and arr[j] > key:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = key
    # Deduplicate
    var result = List[Int]()
    result.append(arr[0])
    for i in range(1, n):
        if arr[i] != arr[i - 1]:
            result.append(arr[i])
    return result^


# ── set_contains ─────────────────────────────────────────────────────────────


def set_contains(s: List[Int], element: Int) -> Bool:
    """Binary search membership test on sorted list."""
    var lo = 0
    var hi = len(s) - 1
    while lo <= hi:
        var mid = lo + (hi - lo) // 2
        if s[mid] == element:
            return True
        elif s[mid] < element:
            lo = mid + 1
        else:
            hi = mid - 1
    return False


# ── set_cardinality ──────────────────────────────────────────────────────────


def set_cardinality(s: List[Int]) -> Int:
    """Number of elements in the set."""
    return len(s)
