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

`Int64HashIndex`: keying without the Float64 detour (round 4, int64-columnar-fidelity)
----------------------------------------------------------------------------------------
`HashIndex` above is `Float64 -> Int`, which is exactly right for a Float64 key column
and silently wrong for an Int64 one: two DISTINCT Int64 values above 2^53 can share one
IEEE-754 double (`9007199254740992` and `9007199254740993` both round to the same bit
pattern), so any caller who first widens an Int64 key to Float64 and then probes
`HashIndex` has already lost the distinction before this module sees it —
`test_columnar_hash_index.mojo` proves that collision directly, and
`test_query_aggregate.mojo` proves it turns into a silently-merged group (count and sum
both double) through the real aggregate path.

`Int64HashIndex` is the fix: `Int -> Int`, keyed and compared on the Int the whole way
through, with no Float64 anywhere in the type. It needs neither of `HashIndex`'s
normalizations — an Int64 has no signed zero and no NaN — so it hashes the key's zigzag
encoding (`canonical.encode.zigzag`, frozen, reused rather than re-derived per rule 3 of
`docs/mojo/new-kernel-package-rules.md`) directly.
"""
from std.memory import bitcast

from canonical.encode import zigzag

comptime EMPTY_SLOT: Int = -1
comptime DEFAULT_CAPACITY: Int = 64
comptime MAX_LOAD: Float64 = 0.7

# One quiet NaN, so every NaN lands in one group instead of one group per row.
comptime CANONICAL_NAN_BITS: UInt64 = 0x7FF8000000000000

comptime FNV_OFFSET_BASIS: UInt64 = 0xCBF29CE484222325
"""The FNV-1a starting state. Public (round 3) so a batched hasher can run the
fold itself: `fnv_fold(FNV_OFFSET_BASIS, bits)` for one element, then further
`fnv_fold` calls for the rest of a composite key. Was `_FNV_OFFSET`; same value,
same uses — only the visibility changed."""
comptime _FNV_PRIME: UInt64 = 0x100000001B3


@always_inline
fn fnv_fold(h0: UInt64, bits: UInt64) -> UInt64:
    """Fold eight bytes into a running FNV-1a state, low byte first.

    This is THE byte loop `hash_bits`, `hash_composite` and `hash_indices` have
    always run — hoisted so a caller that hashes rows in blocks (the batched
    key hasher in `query.aggregate`) provably runs the same fold the tables
    probe with. `hash_bits(b) == fnv_fold(FNV_OFFSET_BASIS, b)` by definition,
    and a width-N composite hash is N chained folds over normalized elements.
    """
    var h = h0
    var remaining = bits
    for _ in range(8):
        h = h ^ (remaining & 0xFF)
        h = h * _FNV_PRIME
        remaining = remaining >> 8
    return h


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
    return fnv_fold(FNV_OFFSET_BASIS, bits)


fn hash_float(value: Float64) -> UInt64:
    return hash_bits(normalize_bits(value))


fn hash_composite(key: List[Float64], width: Int) -> UInt64:
    """One FNV-1a hash over a `width`-wide key tuple, elements normalized.

    This is THE hash `CompositeKeyIndex` probes with — its `_hash_key` delegates
    here — exported so a caller that routes rows by hash (the radix-partitioned
    aggregate path) provably uses the same function the table it later probes
    uses. Two implementations of "the key's hash" would let a row land in one
    partition and be looked up under another, which is a lost group, silently.

    For `width == 1` this equals `hash_float(key[0])`: same normalization, same
    FNV fold over the same eight bytes — so `HashIndex` (which probes with
    `hash_bits(normalize_bits(k))`) and a width-1 `CompositeKeyIndex` route
    identically. A position past `len(key)` hashes as 0.0, matching
    `CompositeKeyIndex._keys_equal`'s treatment of a short key.
    """
    var h = FNV_OFFSET_BASIS
    for i in range(width):
        h = fnv_fold(h, normalize_bits(key[i] if i < len(key) else 0.0))
    return h


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

    fn get_or_assign_bits(mut self, bits: UInt64, h: UInt64, next_slot: Int) -> Int:
        """`get_or_assign` for a caller that already normalized and hashed.

        `bits` MUST be `normalize_bits(key)` and `h` MUST be `hash_bits(bits)`;
        the batched hasher in `query.aggregate` computes both in a block loop
        and probes here without re-deriving either. A mismatched pair would
        probe one chain and compare another — the suite pins this entry
        slot-for-slot against `get_or_assign` over the same key stream,
        including -0.0 and NaN, which is what makes the split shippable.
        """
        var pos = Int(h) & self.mask
        while self.slots[pos] != EMPTY_SLOT:
            if self.slot_keys[pos] == bits:
                return self.slots[pos]
            pos = (pos + 1) & self.mask
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
    var h = FNV_OFFSET_BASIS
    for i in range(len(indices)):
        var index = indices[i]
        if index < 0 or index >= len(values):
            continue
        h = fnv_fold(h, normalize_bits(values[index]))
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
        # Delegates to the module-level `hash_composite` so the table and any
        # hash-router (the radix aggregate path) cannot disagree about a key's hash.
        return hash_composite(key, self.key_width)

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
        return self.get_or_assign_hashed(key, self._hash_key(key), next_slot)

    fn get_or_assign_hashed(mut self, key: List[Float64], h: UInt64, next_slot: Int) -> Int:
        """`get_or_assign` for a caller that already ran `hash_composite`.

        `h` MUST be `hash_composite(key, self.key_width)` — the batched hasher
        and the radix scatter in `query.aggregate` compute it once per row and
        probe here without recomputing. Equality still compares the FULL key
        tuple, so a wrong `h` cannot merge two different keys; it can only
        split one key across slots, and the suite pins this entry
        slot-for-slot against `get_or_assign` to rule that out.
        """
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


fn hash_int64(key: Int) -> UInt64:
    """FNV-1a over `key`'s zigzag encoding — `Int64HashIndex`'s probe hash.

    `zigzag` (from `canonical.encode`, frozen) is the one signed-Int-to-UInt64 mapping
    this tree already committed to as a value's canonical identity, including at
    `Int.MIN`: `zigzag` computes `-(value + 1)` for a negative value, and
    `Int.MIN + 1` is one more than `Int.MIN`, so it is representable, and its negation
    (`Int.MAX`) is too — no overflow at the one Int a naive `-value` would trap on.
    Reusing it rather than a second bit-reinterpretation means a key's hash here can
    never disagree with what `canonical.hash` would compute for the same Int, and rule
    3 of `docs/mojo/new-kernel-package-rules.md` is exactly this: call the frozen
    encoding, do not re-derive it.
    """
    return fnv_fold(FNV_OFFSET_BASIS, zigzag(key))


struct Int64HashIndex(Copyable, Movable):
    """`Int -> Int` slot lookup — `HashIndex`'s exact-Int64 analog.

    Built for `query.aggregate.group_by_int64`: a group-by whose key column is a real
    Int64 (`columnar.array.Int64Array`) must never coerce that key to Float64, because
    `HashIndex` (Float64-keyed) cannot distinguish `9007199254740992` from
    `9007199254740993` — both share one double. This table hashes and compares the Int
    itself, at every position `slots`/`slot_keys` mirror `HashIndex`'s, so two distinct
    Int64 keys stay two groups at every magnitude the type can hold, no matter how
    close together or how far from zero.

    No `-0.0`/NaN normalization: an Int64 key has neither, so `HashIndex`'s two
    normalizations do not apply and are not reproduced here.
    """

    var slots: List[Int]
    var slot_keys: List[Int]
    var mask: Int
    var count: Int

    fn __init__(out self, initial_capacity: Int = DEFAULT_CAPACITY):
        var cap = _next_power_of_two(initial_capacity if initial_capacity > 4 else 4)
        self.slots = List[Int]()
        self.slot_keys = List[Int]()
        for _ in range(cap):
            self.slots.append(EMPTY_SLOT)
            self.slot_keys.append(0)
        self.mask = cap - 1
        self.count = 0

    fn capacity(self) -> Int:
        return len(self.slots)

    fn size(self) -> Int:
        return self.count

    fn _probe(self, key: Int, h: UInt64) -> Int:
        """Table position holding `key`, or the first empty position for it.

        One function for lookup and insert, same reason as `HashIndex._probe`: the two
        must never walk different probe sequences.
        """
        var pos = Int(h) & self.mask
        while self.slots[pos] != EMPTY_SLOT:
            if self.slot_keys[pos] == key:
                return pos
            pos = (pos + 1) & self.mask
        return pos

    fn find(self, key: Int) -> Int:
        """Slot for `key`, or -1. Never inserts."""
        var pos = self._probe(key, hash_int64(key))
        if self.slots[pos] == EMPTY_SLOT:
            return -1
        return self.slots[pos]

    fn contains(self, key: Int) -> Bool:
        return self.find(key) >= 0

    fn _grow(mut self):
        """Double and rehash. Every live key is reinserted, none dropped."""
        var old_slots = self.slots.copy()
        var old_keys = self.slot_keys.copy()
        var new_cap = len(old_slots) << 1
        self.slots = List[Int]()
        self.slot_keys = List[Int]()
        for _ in range(new_cap):
            self.slots.append(EMPTY_SLOT)
            self.slot_keys.append(0)
        self.mask = new_cap - 1
        for i in range(len(old_slots)):
            if old_slots[i] == EMPTY_SLOT:
                continue
            var pos = Int(hash_int64(old_keys[i])) & self.mask
            while self.slots[pos] != EMPTY_SLOT:
                pos = (pos + 1) & self.mask
            self.slots[pos] = old_slots[i]
            self.slot_keys[pos] = old_keys[i]

    fn get_or_assign(mut self, key: Int, next_slot: Int) -> Int:
        """The existing slot for `key`, or `next_slot` after assigning it.

        Same contract as `HashIndex.get_or_assign`: the caller supplies the slot
        number, so the index and the caller's accumulator array cannot drift.
        """
        var pos = self._probe(key, hash_int64(key))
        if self.slots[pos] != EMPTY_SLOT:
            return self.slots[pos]
        self.slots[pos] = next_slot
        self.slot_keys[pos] = key
        self.count += 1
        if Float64(self.count) > MAX_LOAD * Float64(len(self.slots)):
            self._grow()
        return next_slot
