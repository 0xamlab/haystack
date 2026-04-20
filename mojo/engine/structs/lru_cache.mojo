"""
lru_cache.mojo — LRU Cache with String keys and Float64 values. Zero Python imports.

Replaces Python's functools.lru_cache. Fixed-capacity key-value cache with
least-recently-used eviction. Uses a simple array-based approach where elements
are shifted on access/evict to maintain LRU order.

Public API:
  struct LRUCache(Copyable, Movable)
    fn __init__(out self, capacity: Int)
    fn put(mut self, key: String, value: Float64)
    fn get(mut self, key: String, default: Float64 = 0.0) -> Float64
    fn contains(self, key: String) -> Bool
    fn size(self) -> Int
    fn hit_rate(self) -> Float64
    fn clear(mut self)
"""


# ── LRUCache ─────────────────────────────────────────────────────────────────


struct LRUCache(Copyable, Movable):
    """Fixed-capacity key-value cache with LRU eviction.

    Uses parallel arrays for keys and values, with index 0 being the LRU end
    and index (size-1) being the MRU end. On access, the accessed element is
    moved to the MRU position by shifting.
    """

    var _capacity: Int
    var _size: Int
    var _keys: List[String]
    var _values: List[Float64]
    var _hits: Int
    var _misses: Int

    fn __init__(out self, capacity: Int):
        """Create a new LRU cache with the given maximum capacity.

        Args:
            capacity: Maximum number of entries in the cache (must be >= 1).
        """
        var cap = capacity
        if cap < 1:
            cap = 1
        self._capacity = cap
        self._size = 0
        self._keys = List[String]()
        self._values = List[Float64]()
        self._hits = 0
        self._misses = 0

    fn _find_index(self, key: String) -> Int:
        """Find the index of a key in the cache. Returns -1 if not found."""
        for i in range(self._size):
            if self._keys[i] == key:
                return i
        return -1

    fn _move_to_mru(mut self, idx: Int):
        """Move element at idx to the MRU position (end of list)."""
        if idx == self._size - 1:
            return  # Already at MRU position

        var key = self._keys[idx]
        var value = self._values[idx]

        # Shift elements left to fill the gap
        for i in range(idx, self._size - 1):
            self._keys[i] = self._keys[i + 1]
            self._values[i] = self._values[i + 1]

        # Place at the end (MRU position)
        self._keys[self._size - 1] = key
        self._values[self._size - 1] = value

    fn put(mut self, key: String, value: Float64):
        """Insert or update a key-value pair. Evicts LRU entry if at capacity.

        Args:
            key: The key to insert.
            value: The value to associate with the key.
        """
        # Check if key already exists
        var idx = self._find_index(key)
        if idx >= 0:
            # Update existing entry and move to MRU
            self._values[idx] = value
            self._move_to_mru(idx)
            return

        # Need to insert new entry
        if self._size >= self._capacity:
            # Evict LRU (index 0)
            # Shift everything left by 1
            for i in range(self._size - 1):
                self._keys[i] = self._keys[i + 1]
                self._values[i] = self._values[i + 1]
            # Overwrite last position
            self._keys[self._size - 1] = key
            self._values[self._size - 1] = value
        else:
            # Append at MRU end
            self._keys.append(key)
            self._values.append(value)
            self._size += 1

    fn get(mut self, key: String, default: Float64 = 0.0) -> Float64:
        """Get value for key and move it to MRU position.

        Args:
            key: The key to look up.
            default: Value returned if key is not found.

        Returns:
            The cached value, or default if not found.
        """
        var idx = self._find_index(key)
        if idx < 0:
            self._misses += 1
            return default

        self._hits += 1
        var value = self._values[idx]
        self._move_to_mru(idx)
        return value

    fn contains(self, key: String) -> Bool:
        """Check if key exists in the cache (does NOT affect LRU order).

        Args:
            key: The key to check.

        Returns:
            True if the key is in the cache.
        """
        return self._find_index(key) >= 0

    fn size(self) -> Int:
        """Return the number of entries currently in the cache."""
        return self._size

    fn hit_rate(self) -> Float64:
        """Return the cache hit rate as hits / (hits + misses).

        Returns 0.0 if no lookups have been made.
        """
        var total = self._hits + self._misses
        if total == 0:
            return 0.0
        return Float64(self._hits) / Float64(total)

    fn clear(mut self):
        """Remove all entries from the cache and reset hit/miss counters."""
        self._keys = List[String]()
        self._values = List[Float64]()
        self._size = 0
        self._hits = 0
        self._misses = 0
