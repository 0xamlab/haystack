"""
containers.mojo — Advanced data structures. Zero Python imports.

Replaces Python's collections and heapq with pure Mojo implementations.

Public API:
  struct MinHeap     — binary min-heap for priority queues
  struct RingBuffer  — fixed-size circular buffer for streaming data
  struct SortedList  — maintains sorted order on insert
  fn counter()       — frequency count (like Counter)
  fn unique()        — unique values sorted
"""


# ── MinHeap ──────────────────────────────────────────────────────────────────


struct MinHeap(Copyable, Movable):
    """Binary min-heap. Smallest element is always at the top."""

    var _data: List[Float64]

    fn __init__(out self):
        self._data = List[Float64]()

    fn size(self) -> Int:
        """Return the number of elements in the heap."""
        return len(self._data)

    fn peek(self) -> Float64:
        """Return the minimum element without removing it.
        Returns 0.0 if heap is empty.
        """
        if len(self._data) == 0:
            return 0.0
        return self._data[0]

    fn push(mut self, value: Float64):
        """Insert a value into the heap, maintaining the heap property."""
        self._data.append(value)
        self._sift_up(len(self._data) - 1)

    fn pop(mut self) -> Float64:
        """Remove and return the minimum element.
        Returns 0.0 if heap is empty.
        """
        var n = len(self._data)
        if n == 0:
            return 0.0
        if n == 1:
            var val = self._data[0]
            self._data = List[Float64]()
            return val
        var result = self._data[0]
        # Move last element to root
        self._data[0] = self._data[n - 1]
        # Remove the last element
        var new_data = List[Float64]()
        for i in range(n - 1):
            new_data.append(self._data[i])
        self._data = new_data^
        self._sift_down(0)
        return result

    fn _sift_up(mut self, idx: Int):
        """Bubble element at idx up to restore heap property."""
        var i = idx
        while i > 0:
            var parent = (i - 1) // 2
            if self._data[i] < self._data[parent]:
                var tmp = self._data[i]
                self._data[i] = self._data[parent]
                self._data[parent] = tmp
                i = parent
            else:
                break

    fn _sift_down(mut self, idx: Int):
        """Push element at idx down to restore heap property."""
        var n = len(self._data)
        var i = idx
        while True:
            var left = 2 * i + 1
            var right = 2 * i + 2
            var smallest = i
            if left < n and self._data[left] < self._data[smallest]:
                smallest = left
            if right < n and self._data[right] < self._data[smallest]:
                smallest = right
            if smallest != i:
                var tmp = self._data[i]
                self._data[i] = self._data[smallest]
                self._data[smallest] = tmp
                i = smallest
            else:
                break


# ── RingBuffer ───────────────────────────────────────────────────────────────


struct RingBuffer(Copyable, Movable):
    """Fixed-size circular buffer for streaming data (e.g., rolling window stats)."""

    var _data: List[Float64]
    var _capacity: Int
    var _head: Int      # next write position
    var _count: Int     # current number of elements

    fn __init__(out self, capacity: Int):
        self._capacity = capacity
        self._head = 0
        self._count = 0
        self._data = List[Float64]()
        for _ in range(capacity):
            self._data.append(0.0)

    fn push(mut self, value: Float64):
        """Insert a value. If full, overwrites the oldest element."""
        self._data[self._head] = value
        self._head = (self._head + 1) % self._capacity
        if self._count < self._capacity:
            self._count += 1

    fn get(self, index: Int) -> Float64:
        """Get element by logical index (0 = oldest).
        Returns 0.0 if index is out of range.
        """
        if index < 0 or index >= self._count:
            return 0.0
        # Oldest element is at (_head - _count + _capacity) % _capacity
        var start = (self._head - self._count + self._capacity) % self._capacity
        var actual = (start + index) % self._capacity
        return self._data[actual]

    fn mean(self) -> Float64:
        """Compute the arithmetic mean of elements in the buffer.
        Returns 0.0 if empty.
        """
        if self._count == 0:
            return 0.0
        var total: Float64 = 0.0
        var start = (self._head - self._count + self._capacity) % self._capacity
        for i in range(self._count):
            var idx = (start + i) % self._capacity
            total += self._data[idx]
        return total / Float64(self._count)

    fn is_full(self) -> Bool:
        """Return True if the buffer has reached capacity."""
        return self._count == self._capacity

    fn size(self) -> Int:
        """Return the current number of elements."""
        return self._count


# ── SortedList ───────────────────────────────────────────────────────────────


struct SortedList(Copyable, Movable):
    """Maintains elements in sorted (ascending) order on insert."""

    var _data: List[Float64]

    fn __init__(out self):
        self._data = List[Float64]()

    fn insert(mut self, value: Float64):
        """Insert value in sorted position using binary search."""
        var n = len(self._data)
        # Binary search for insertion point
        var lo = 0
        var hi = n
        while lo < hi:
            var mid = (lo + hi) // 2
            if self._data[mid] < value:
                lo = mid + 1
            else:
                hi = mid
        # Insert at position lo
        # Build new list with insertion
        var new_data = List[Float64]()
        for i in range(lo):
            new_data.append(self._data[i])
        new_data.append(value)
        for i in range(lo, n):
            new_data.append(self._data[i])
        self._data = new_data^

    fn get(self, index: Int) -> Float64:
        """Get element at index. Returns 0.0 if out of range."""
        if index < 0 or index >= len(self._data):
            return 0.0
        return self._data[index]

    fn median(self) -> Float64:
        """Return the median value. Returns 0.0 if empty."""
        var n = len(self._data)
        if n == 0:
            return 0.0
        if n % 2 == 1:
            return self._data[n // 2]
        return (self._data[n // 2 - 1] + self._data[n // 2]) / 2.0

    fn remove(mut self, index: Int):
        """Remove element at index. No-op if out of range."""
        var n = len(self._data)
        if index < 0 or index >= n:
            return
        var new_data = List[Float64]()
        for i in range(n):
            if i != index:
                new_data.append(self._data[i])
        self._data = new_data^

    fn size(self) -> Int:
        """Return the number of elements."""
        return len(self._data)


# ── counter ──────────────────────────────────────────────────────────────────


fn counter(data: List[Float64], bins: Int) -> List[Int]:
    """Frequency count: divide the range [min, max] into `bins` equal bins.
    Returns a list of counts per bin. Like a histogram / Counter.
    """
    var n = len(data)
    var result = List[Int]()
    if n == 0 or bins <= 0:
        for _ in range(bins):
            result.append(0)
        return result^

    # Find min/max
    var lo = data[0]
    var hi = data[0]
    for i in range(1, n):
        if data[i] < lo:
            lo = data[i]
        if data[i] > hi:
            hi = data[i]

    for _ in range(bins):
        result.append(0)

    var span = hi - lo
    if span == 0.0:
        # All values are the same — put them all in first bin
        result[0] = n
        return result^

    for i in range(n):
        var bin_idx = Int((data[i] - lo) / span * Float64(bins))
        if bin_idx >= bins:
            bin_idx = bins - 1
        if bin_idx < 0:
            bin_idx = 0
        result[bin_idx] = result[bin_idx] + 1

    return result^


# ── unique ───────────────────────────────────────────────────────────────────


fn unique(data: List[Float64]) -> List[Float64]:
    """Return unique values from data, sorted in ascending order."""
    var n = len(data)
    if n == 0:
        return List[Float64]()

    # Copy and sort (simple insertion sort — fine for typical sizes)
    var sorted_data = List[Float64]()
    for i in range(n):
        sorted_data.append(data[i])

    # Insertion sort
    for i in range(1, n):
        var key = sorted_data[i]
        var j = i - 1
        while j >= 0 and sorted_data[j] > key:
            sorted_data[j + 1] = sorted_data[j]
            j -= 1
        sorted_data[j + 1] = key

    # Deduplicate
    var result = List[Float64]()
    result.append(sorted_data[0])
    for i in range(1, n):
        if sorted_data[i] != result[len(result) - 1]:
            result.append(sorted_data[i])

    return result^
