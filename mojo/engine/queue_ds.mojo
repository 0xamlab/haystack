"""
queue_ds.mojo — Queue data structures. Zero Python imports.

Replaces queue/heapq/collections.deque with pure Mojo implementations
of a min-heap priority queue and a fixed-size circular buffer.

Public API:
  PriorityQueueEntry    — Struct with priority and value fields
  PriorityQueue         — Min-heap based priority queue
  pq_create             — Create empty priority queue
  pq_push               — Insert with priority (lower = higher priority)
  pq_pop                — Remove and return minimum priority entry
  pq_peek               — View minimum without removing
  pq_size               — Current size
  pq_is_empty           — Check if empty
  CircularBuffer        — Fixed-size circular buffer
  cb_create             — Create circular buffer with given capacity
  cb_push               — Push value (overwrites oldest if full)
  cb_pop                — Pop oldest value
  cb_size               — Current number of elements
  cb_is_full            — Check if at capacity
  cb_peek               — View oldest without removing
"""


# ── PriorityQueueEntry ───────────────────────────────────────────────────────


struct PriorityQueueEntry(Copyable, Movable):
    """Entry with priority and integer value."""
    var priority: Float64
    var value: Int

    fn __init__(out self, priority: Float64, value: Int):
        self.priority = priority
        self.value = value


# ── PriorityQueue ────────────────────────────────────────────────────────────


@fieldwise_init
struct PriorityQueue(Copyable, Movable):
    """Min-heap based priority queue using parallel lists."""
    var priorities: List[Float64]
    var values: List[Int]

    fn __init__(out self):
        self.priorities = List[Float64]()
        self.values = List[Int]()


# ── pq_create ────────────────────────────────────────────────────────────────


fn pq_create() -> PriorityQueue:
    """Create empty priority queue."""
    return PriorityQueue()


# ── pq_size ──────────────────────────────────────────────────────────────────


fn pq_size(pq: PriorityQueue) -> Int:
    """Current size of priority queue."""
    return len(pq.priorities)


# ── pq_is_empty ──────────────────────────────────────────────────────────────


fn pq_is_empty(pq: PriorityQueue) -> Bool:
    """Check if priority queue is empty."""
    return len(pq.priorities) == 0


# ── pq_push ──────────────────────────────────────────────────────────────────


fn pq_push(mut pq: PriorityQueue, priority: Float64, value: Int):
    """Insert with priority (lower = higher priority). Bubble up."""
    pq.priorities.append(priority)
    pq.values.append(value)
    # Bubble up
    var idx = len(pq.priorities) - 1
    while idx > 0:
        var parent = (idx - 1) // 2
        if pq.priorities[idx] < pq.priorities[parent]:
            # Swap priorities
            var tmp_p = pq.priorities[idx]
            pq.priorities[idx] = pq.priorities[parent]
            pq.priorities[parent] = tmp_p
            # Swap values
            var tmp_v = pq.values[idx]
            pq.values[idx] = pq.values[parent]
            pq.values[parent] = tmp_v
            idx = parent
        else:
            break


# ── pq_peek ──────────────────────────────────────────────────────────────────


fn pq_peek(pq: PriorityQueue) -> PriorityQueueEntry:
    """View minimum priority entry without removing. Returns sentinel if empty."""
    if len(pq.priorities) == 0:
        return PriorityQueueEntry(-999999.0, -1)
    return PriorityQueueEntry(pq.priorities[0], pq.values[0])


# ── pq_pop ───────────────────────────────────────────────────────────────────


fn pq_pop(mut pq: PriorityQueue) -> PriorityQueueEntry:
    """Remove and return minimum priority entry. Bubble down."""
    if len(pq.priorities) == 0:
        return PriorityQueueEntry(-999999.0, -1)
    var result = PriorityQueueEntry(pq.priorities[0], pq.values[0])
    var n = len(pq.priorities) - 1
    # Move last to root
    pq.priorities[0] = pq.priorities[n]
    pq.values[0] = pq.values[n]
    # Remove last element
    var new_p = List[Float64]()
    var new_v = List[Int]()
    for i in range(n):
        new_p.append(pq.priorities[i])
        new_v.append(pq.values[i])
    pq.priorities = new_p^
    pq.values = new_v^
    # Bubble down
    var idx = 0
    var size = len(pq.priorities)
    while True:
        var left = 2 * idx + 1
        var right = 2 * idx + 2
        var smallest = idx
        if left < size and pq.priorities[left] < pq.priorities[smallest]:
            smallest = left
        if right < size and pq.priorities[right] < pq.priorities[smallest]:
            smallest = right
        if smallest != idx:
            var tmp_p = pq.priorities[idx]
            pq.priorities[idx] = pq.priorities[smallest]
            pq.priorities[smallest] = tmp_p
            var tmp_v = pq.values[idx]
            pq.values[idx] = pq.values[smallest]
            pq.values[smallest] = tmp_v
            idx = smallest
        else:
            break
    return result^


# ── CircularBuffer ───────────────────────────────────────────────────────────


@fieldwise_init
struct CircularBuffer(Copyable, Movable):
    """Fixed-size circular buffer using List[Float64]."""
    var data: List[Float64]
    var capacity: Int
    var head: Int   # index of oldest element
    var count: Int  # number of elements currently stored

    fn __init__(out self, capacity: Int):
        self.capacity = capacity
        self.head = 0
        self.count = 0
        self.data = List[Float64]()
        for i in range(capacity):
            self.data.append(0.0)


# ── cb_create ────────────────────────────────────────────────────────────────


fn cb_create(capacity: Int) -> CircularBuffer:
    """Create circular buffer with given capacity."""
    return CircularBuffer(capacity)


# ── cb_size ──────────────────────────────────────────────────────────────────


fn cb_size(buf: CircularBuffer) -> Int:
    """Current number of elements in circular buffer."""
    return buf.count


# ── cb_is_full ───────────────────────────────────────────────────────────────


fn cb_is_full(buf: CircularBuffer) -> Bool:
    """Check if circular buffer is at capacity."""
    return buf.count == buf.capacity


# ── cb_push ──────────────────────────────────────────────────────────────────


fn cb_push(mut buf: CircularBuffer, value: Float64):
    """Push value. Overwrites oldest if full."""
    var tail = (buf.head + buf.count) % buf.capacity
    if buf.count == buf.capacity:
        # Overwrite oldest: write at head, advance head
        buf.data[buf.head] = value
        buf.head = (buf.head + 1) % buf.capacity
    else:
        buf.data[tail] = value
        buf.count += 1


# ── cb_pop ───────────────────────────────────────────────────────────────────


fn cb_pop(mut buf: CircularBuffer) -> Float64:
    """Pop oldest value. Returns -999999 sentinel if empty."""
    if buf.count == 0:
        return -999999.0
    var val = buf.data[buf.head]
    buf.head = (buf.head + 1) % buf.capacity
    buf.count -= 1
    return val


# ── cb_peek ──────────────────────────────────────────────────────────────────


fn cb_peek(buf: CircularBuffer) -> Float64:
    """View oldest value without removing. Returns -999999 sentinel if empty."""
    if buf.count == 0:
        return -999999.0
    return buf.data[buf.head]
