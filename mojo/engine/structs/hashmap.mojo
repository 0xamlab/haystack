"""
hashmap.mojo — Hash map with String keys and Float64 values. Zero Python imports.

Replaces Python's dict for numeric lookups. Open addressing with linear probing.

Public API:
  struct HashMap(Copyable, Movable)
    fn __init__(out self, initial_capacity: Int = 64)
    fn put(mut self, key: String, value: Float64)
    fn get(self, key: String, default: Float64 = 0.0) -> Float64
    fn contains(self, key: String) -> Bool
    fn remove(mut self, key: String) -> Bool
    fn size(self) -> Int
    fn all_keys(self) -> List[String]
    fn all_values(self) -> List[Float64]
"""


# ── FNV-1a hash (inlined to avoid circular dependency) ───────────────────────


fn _fnv1a(data: String) -> Int:
    """FNV-1a 64-bit hash. Returns non-negative Int."""
    var hash_val: Int = -3750763034362895579  # 0xcbf29ce484222325 as signed
    var prime: Int = 1099511628211
    var bytes = data.as_bytes()
    for i in range(len(bytes)):
        hash_val = hash_val ^ Int(bytes[i])
        hash_val = hash_val * prime
    return hash_val & 0x7FFFFFFFFFFFFFFF


# ── Sentinel constants ────────────────────────────────────────────────────────
# We use a special marker in the occupied array:
#   0 = empty, 1 = occupied, 2 = tombstone (deleted)


# ── HashMap ───────────────────────────────────────────────────────────────────


struct HashMap(Copyable, Movable):
    """Hash map with String keys and Float64 values.

    Uses open addressing with linear probing and a load factor of 0.7
    for automatic resizing.
    """

    var _capacity: Int
    var _size: Int
    var _keys: List[String]
    var _values: List[Float64]
    var _occupied: List[Int]  # 0=empty, 1=occupied, 2=tombstone
    var _load_factor: Float64

    fn __init__(out self, initial_capacity: Int = 64):
        """Create a new HashMap with the given initial capacity."""
        self._capacity = initial_capacity
        self._size = 0
        self._load_factor = 0.7
        self._keys = List[String]()
        self._values = List[Float64]()
        self._occupied = List[Int]()
        for _ in range(initial_capacity):
            self._keys.append(String(""))
            self._values.append(0.0)
            self._occupied.append(0)

    fn _find_slot(self, key: String) -> Int:
        """Find the slot for a key. Returns the index where the key is or
        should be inserted. Uses linear probing."""
        var hash_val = _fnv1a(key)
        var idx = hash_val % self._capacity
        var first_tombstone: Int = -1

        for _ in range(self._capacity):
            var state = self._occupied[idx]
            if state == 0:
                # Empty slot — key not in map
                if first_tombstone >= 0:
                    return first_tombstone
                return idx
            elif state == 2:
                # Tombstone — remember first one for insertion
                if first_tombstone < 0:
                    first_tombstone = idx
            elif state == 1:
                # Occupied — check if key matches
                if self._keys[idx] == key:
                    return idx
            # Linear probe
            idx = (idx + 1) % self._capacity

        # Table is full (shouldn't happen with load factor resize)
        if first_tombstone >= 0:
            return first_tombstone
        return 0

    fn _should_resize(self) -> Bool:
        """Check if we need to resize based on load factor."""
        return Float64(self._size + 1) / Float64(self._capacity) > self._load_factor

    fn _resize(mut self):
        """Double the capacity and rehash all entries."""
        var old_capacity = self._capacity
        var old_keys = self._keys.copy()
        var old_values = self._values.copy()
        var old_occupied = self._occupied.copy()

        # Create new larger table
        var new_capacity = old_capacity * 2
        self._capacity = new_capacity
        self._size = 0
        self._keys = List[String]()
        self._values = List[Float64]()
        self._occupied = List[Int]()
        for _ in range(new_capacity):
            self._keys.append(String(""))
            self._values.append(0.0)
            self._occupied.append(0)

        # Rehash all existing entries
        for i in range(old_capacity):
            if old_occupied[i] == 1:
                self.put(old_keys[i], old_values[i])

    fn put(mut self, key: String, value: Float64):
        """Insert or update a key-value pair."""
        if self._should_resize():
            self._resize()

        var idx = self._find_slot(key)
        if self._occupied[idx] == 1 and self._keys[idx] == key:
            # Update existing
            self._values[idx] = value
        else:
            # Insert new
            self._keys[idx] = key
            self._values[idx] = value
            self._occupied[idx] = 1
            self._size += 1

    fn get(self, key: String, default: Float64 = 0.0) -> Float64:
        """Retrieve value for key, or return default if not found."""
        var hash_val = _fnv1a(key)
        var idx = hash_val % self._capacity

        for _ in range(self._capacity):
            var state = self._occupied[idx]
            if state == 0:
                return default
            elif state == 1 and self._keys[idx] == key:
                return self._values[idx]
            idx = (idx + 1) % self._capacity

        return default

    fn contains(self, key: String) -> Bool:
        """Check if key exists in the map."""
        var hash_val = _fnv1a(key)
        var idx = hash_val % self._capacity

        for _ in range(self._capacity):
            var state = self._occupied[idx]
            if state == 0:
                return False
            elif state == 1 and self._keys[idx] == key:
                return True
            idx = (idx + 1) % self._capacity

        return False

    fn remove(mut self, key: String) -> Bool:
        """Remove a key from the map. Returns True if the key was found."""
        var hash_val = _fnv1a(key)
        var idx = hash_val % self._capacity

        for _ in range(self._capacity):
            var state = self._occupied[idx]
            if state == 0:
                return False
            elif state == 1 and self._keys[idx] == key:
                # Mark as tombstone
                self._occupied[idx] = 2
                self._size -= 1
                return True
            idx = (idx + 1) % self._capacity

        return False

    fn size(self) -> Int:
        """Return the number of entries in the map."""
        return self._size

    fn all_keys(self) -> List[String]:
        """Return all keys in the map."""
        var result = List[String]()
        for i in range(self._capacity):
            if self._occupied[i] == 1:
                result.append(self._keys[i])
        return result^

    fn all_values(self) -> List[Float64]:
        """Return all values in the map."""
        var result = List[Float64]()
        for i in range(self._capacity):
            if self._occupied[i] == 1:
                result.append(self._values[i])
        return result^
