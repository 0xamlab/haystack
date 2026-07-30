"""
columnar.hash_index — group-slot lookup for the aggregate path. Zero Python.

Why this is not `structs/hashmap.mojo`
--------------------------------------
That map is `String -> Float64` with open addressing and FNV-1a, and it is frozen and
correct for what it does. An aggregate needs `Float64 -> Int`: a *slot number* into a
parallel array of accumulators, not a value. Going through the frozen map would mean
formatting every key to a String on every row and then reading a Float64 back to use
as an index — a conversion per row plus a lossy round trip through the float
formatter. So this is a separate structure, and `structs/hashmap.mojo` is untouched.

Keying on bits, not on the float
--------------------------------
The key is hashed and compared as its IEEE-754 bit pattern, with two normalizations
applied first:

  * `-0.0` collapses to `+0.0`. They compare equal under `==` but have different bit
    patterns, so hashing the raw bits would put them in different groups while the
    equality check said they were the same group — a split that depends on how the
    number was produced.
  * every NaN collapses to one quiet NaN. NaN != NaN, so a bit-pattern index would
    otherwise create a fresh group for every NaN row and never find any of them
    again. One NaN group is a defensible answer; unboundedly many is not.

This matches `canonical/encode.mojo`, which normalizes the same two cases for the same
reason — a hash that disagrees with the canonical encoder about identity would let two
plans with the same canonical hash produce different groupings.

Composite keys
--------------
`CompositeKeyIndex` hashes N columns per row without concatenating strings: the row's
values are folded into one 64-bit hash and the full key tuple is kept for the equality
check. Multi-column group-by therefore costs no allocation per row, which is what
string concatenation would cost.

Growth
------
Open addressing, linear probing, power-of-two capacity, resize at 0.7 load. Linear
probing rather than quadratic because group counts are small enough that cache
locality beats clustering resistance, and the probe sequence stays trivially correct.
"""
from std.memory import bitcast

comptime EMPTY_SLOT: Int = -1
comptime DEFAULT_CAPACITY: Int = 64
comptime MAX_LOAD: Float64 = 0.7

# One quiet NaN, so every NaN lands in one group instead of one group per row.
comptime CANONICAL_NAN_BITS: UInt64 = 0x7FF8000000000000

comptime _FNV_OFFSET: UInt64 = 0xCBF29CE484222325
comptime _FNV_PRIME: UInt64 = 0x100000001B3


fn normalize_bits(value: Float64) -> UInt64:
    """The bit pattern used for hashing and equality, `-0.0` and NaN normalized."""
    if value != value:
        return CANONICAL_NAN_BITS
    if value == 0.0:
        # Catches -0.0, whose bits differ from +0.0 while comparing equal to it.
        return bitcast[DType.uint64](Float64(0.0))
    return bitcast[DType.uint64](value)


fn hash_bits(bits: UInt64) -> UInt64:
    """FNV-1a over the eight bytes of a normalized bit pattern.

    FNV-1a rather than a multiply-shift mixer to stay consistent with
    `structs/hashmap.mojo` and `determinism/streams.mojo`, which both use it — one
    hash family across the tree means a stream id and a group slot cannot silently
    disagree about what "the same key" means.
    """
    var h = _FNV_OFFSET
    var remaining = bits
    for _ in range(8):
        h = h ^ (remaining & 0xFF)
        h = h * _FNV_PRIME
        remaining = remaining >> 8
    return h


fn hash_float(value: Float64) -> UInt64:
    return hash_bits(normalize_bits(value))


fn _next_power_of_two(n: Int) -> Int:
    var cap = 1
    while cap < n:
        cap = cap << 1
    return cap


struct HashIndex(Copyable, Movable):
    """`Float64 -> Int` slot lookup. O(1) expected, replacing a linear probe.

    `slots` is the open-addressed table holding slot numbers; `keys` holds the
    normalized bit pattern per table entry so equality never touches the float again.
    """

    var slots: List[Int]
    var slot_keys: List[UInt64]
    var mask: Int
    var count: Int

    fn __init__(out self, initial_capacity: Int = DEFAULT_CAPACITY):
        var cap = _next_power_of_two(initial_capacity if initial_capacity > 4 else 4)
        self.slots = List[Int]()
        self.slot_keys = List[UInt64]()
        for _ in range(cap):
            self.slots.append(EMPTY_SLOT)
            self.slot_keys.append(0)
        self.mask = cap - 1
        self.count = 0

    fn capacity(self) -> Int:
        return len(self.slots)

    fn size(self) -> Int:
        return self.count

    fn _probe(self, bits: UInt64) -> Int:
        """Table position holding `bits`, or the first empty position for it.

        One function for lookup and insert so the two can never walk different probe
        sequences — the classic way an open-addressed table starts losing keys.
        """
        var pos = Int(hash_bits(bits)) & self.mask
        while self.slots[pos] != EMPTY_SLOT:
            if self.slot_keys[pos] == bits:
                return pos
            pos = (pos + 1) & self.mask
        return pos

    fn find(self, key: Float64) -> Int:
        """Slot for `key`, or -1. Never inserts."""
        var bits = normalize_bits(key)
        var pos = self._probe(bits)
        if self.slots[pos] == EMPTY_SLOT:
            return -1
        return self.slots[pos]

    fn contains(self, key: Float64) -> Bool:
        return self.find(key) >= 0

    fn _grow(mut self):
        """Double and rehash. Every live key is reinserted, none dropped."""
        var old_slots = self.slots.copy()
        var old_keys = self.slot_keys.copy()
        var new_cap = len(old_slots) << 1
        self.slots = List[Int]()
        self.slot_keys = List[UInt64]()
        for _ in range(new_cap):
            self.slots.append(EMPTY_SLOT)
            self.slot_keys.append(0)
        self.mask = new_cap - 1
        for i in range(len(old_slots)):
            if old_slots[i] == EMPTY_SLOT:
                continue
            var pos = Int(hash_bits(old_keys[i])) & self.mask
            while self.slots[pos] != EMPTY_SLOT:
                pos = (pos + 1) & self.mask
            self.slots[pos] = old_slots[i]
            self.slot_keys[pos] = old_keys[i]

    fn get_or_assign(mut self, key: Float64, next_slot: Int) -> Int:
        """The existing slot for `key`, or `next_slot` after assigning it.

        The caller supplies the slot number rather than the index generating one, so
        the index and the caller's accumulator array cannot drift: the caller appends
        an accumulator exactly when this returns the value it passed in.
        """
        var bits = normalize_bits(key)
        var pos = self._probe(bits)
        if self.slots[pos] != EMPTY_SLOT:
            return self.slots[pos]
        self.slots[pos] = next_slot
        self.slot_keys[pos] = bits
        self.count += 1
        if Float64(self.count) > MAX_LOAD * Float64(len(self.slots)):
            self._grow()
        return next_slot


fn hash_indices(values: List[Float64], indices: List[Int]) -> UInt64:
    """One hash over several positions of a flat list — a composite key, no concat.

    `indices` are ABSOLUTE positions into `values`. For a column-major buffer where
    column `c` of row `r` lives at `c * n_rows + r`, the caller computes those
    positions itself; use `row_indices` to build them.

    This replaced an earlier `hash_row(values, columns, row)` whose `row` parameter was
    never read — every call hashed row 0 whatever row was asked for, and the test only
    ever passed row 0 so it never noticed. A parameter that silently does nothing is
    worse than an absent one, because the caller believes it worked.

    An out-of-range index is skipped rather than read: reading past the end of a List
    is an uncatchable crash, not an exception.
    """
    var h = _FNV_OFFSET
    for i in range(len(indices)):
        var index = indices[i]
        if index < 0 or index >= len(values):
            continue
        var bits = normalize_bits(values[index])
        var remaining = bits
        for _ in range(8):
            h = h ^ (remaining & 0xFF)
            h = h * _FNV_PRIME
            remaining = remaining >> 8
    return h


fn row_indices(columns: List[Int], row: Int, n_rows: Int) -> List[Int]:
    """Absolute positions of `row`'s cells for `columns`, in a column-major buffer.

    Pairs with `hash_indices`. Split out so the row arithmetic is visible and testable
    on its own rather than buried in a hash that might ignore it.
    """
    var out = List[Int]()
    if n_rows <= 0 or row < 0 or row >= n_rows:
        return out^
    for i in range(len(columns)):
        out.append(columns[i] * n_rows + row)
    return out^


fn hash_row(
    values: List[Float64], columns: List[Int], row: Int, n_rows: Int
) -> UInt64:
    """Composite hash of one row of a column-major buffer. Now actually uses `row`."""
    return hash_indices(values, row_indices(columns, row, n_rows))


struct CompositeKeyIndex(Copyable, Movable):
    """Multi-column group lookup. Keys are kept whole for the equality check.

    Hash collisions are resolved by comparing the full key tuple, so two different
    tuples that hash alike get different slots rather than being merged — which a
    hash-only comparison would do silently, and which is unrecoverable once the
    aggregate has folded them together.
    """

    var slots: List[Int]
    var slot_hashes: List[UInt64]
    var key_width: Int
    var key_store: List[Float64]
    var mask: Int
    var count: Int

    fn __init__(out self, key_width: Int, initial_capacity: Int = DEFAULT_CAPACITY):
        var cap = _next_power_of_two(initial_capacity if initial_capacity > 4 else 4)
        self.slots = List[Int]()
        self.slot_hashes = List[UInt64]()
        for _ in range(cap):
            self.slots.append(EMPTY_SLOT)
            self.slot_hashes.append(0)
        self.key_width = key_width if key_width > 0 else 1
        self.key_store = List[Float64]()
        self.mask = cap - 1
        self.count = 0

    fn size(self) -> Int:
        return self.count

    fn capacity(self) -> Int:
        return len(self.slots)

    fn _hash_key(self, key: List[Float64]) -> UInt64:
        var h = _FNV_OFFSET
        for i in range(self.key_width):
            var bits = normalize_bits(key[i] if i < len(key) else 0.0)
            var remaining = bits
            for _ in range(8):
                h = h ^ (remaining & 0xFF)
                h = h * _FNV_PRIME
                remaining = remaining >> 8
        return h

    fn _keys_equal(self, slot: Int, key: List[Float64]) -> Bool:
        var base = slot * self.key_width
        for i in range(self.key_width):
            var stored = self.key_store[base + i]
            var probe = key[i] if i < len(key) else 0.0
            if normalize_bits(stored) != normalize_bits(probe):
                return False
        return True

    fn find(self, key: List[Float64]) -> Int:
        var h = self._hash_key(key)
        var pos = Int(h) & self.mask
        while self.slots[pos] != EMPTY_SLOT:
            if self.slot_hashes[pos] == h and self._keys_equal(self.slots[pos], key):
                return self.slots[pos]
            pos = (pos + 1) & self.mask
        return -1

    fn _grow(mut self):
        var old_slots = self.slots.copy()
        var old_hashes = self.slot_hashes.copy()
        var new_cap = len(old_slots) << 1
        self.slots = List[Int]()
        self.slot_hashes = List[UInt64]()
        for _ in range(new_cap):
            self.slots.append(EMPTY_SLOT)
            self.slot_hashes.append(0)
        self.mask = new_cap - 1
        for i in range(len(old_slots)):
            if old_slots[i] == EMPTY_SLOT:
                continue
            var pos = Int(old_hashes[i]) & self.mask
            while self.slots[pos] != EMPTY_SLOT:
                pos = (pos + 1) & self.mask
            self.slots[pos] = old_slots[i]
            self.slot_hashes[pos] = old_hashes[i]

    fn get_or_assign(mut self, key: List[Float64], next_slot: Int) -> Int:
        var h = self._hash_key(key)
        var pos = Int(h) & self.mask
        while self.slots[pos] != EMPTY_SLOT:
            if self.slot_hashes[pos] == h and self._keys_equal(self.slots[pos], key):
                return self.slots[pos]
            pos = (pos + 1) & self.mask
        self.slots[pos] = next_slot
        self.slot_hashes[pos] = h
        for i in range(self.key_width):
            self.key_store.append(key[i] if i < len(key) else 0.0)
        self.count += 1
        if Float64(self.count) > MAX_LOAD * Float64(len(self.slots)):
            self._grow()
        return next_slot

    fn key_at(self, slot: Int) -> List[Float64]:
        """The key tuple for a slot — how a result names its groups."""
        var out = List[Float64]()
        if slot < 0:
            return out^
        var base = slot * self.key_width
        for i in range(self.key_width):
            if base + i < len(self.key_store):
                out.append(self.key_store[base + i])
        return out^
