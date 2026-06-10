"""
persistence.mojo — Data persistence helpers. Zero Python imports.

Replaces shelve/dbm with an in-memory key-value store using parallel lists
(since Mojo doesn't have Dict yet).

Public API:
  KVStore           — Struct with parallel keys/values lists
  kv_create         — Create empty store
  kv_put            — Insert or update
  kv_get            — Get value (sentinel on miss)
  kv_delete         — Delete key
  kv_contains       — Check if key exists
  kv_size           — Number of entries
  kv_keys           — All keys
  kv_values         — All values
  kv_clear          — Remove all entries
  snapshot          — Serialize to List[List[Float64]]
  restore           — Restore from snapshot
"""


# ── Sentinel ─────────────────────────────────────────────────────────────────

comptime KV_MISS: Float64 = -999999.0


# ── KVStore Struct ───────────────────────────────────────────────────────────


@fieldwise_init
struct KVStore(Copyable, Movable):
    """In-memory key-value store using parallel lists."""

    var keys: List[Int]
    var values: List[Float64]
    var size: Int

    fn __init__(out self):
        self.keys = List[Int]()
        self.values = List[Float64]()
        self.size = 0


# ── Helper: find index of key ────────────────────────────────────────────────


fn _find_index(store: KVStore, key: Int) -> Int:
    """Return index of key or -1 if not found."""
    for i in range(store.size):
        if store.keys[i] == key:
            return i
    return -1


# ── Public API ───────────────────────────────────────────────────────────────


fn kv_create() -> KVStore:
    """Create an empty key-value store."""
    return KVStore()


fn kv_put(mut store: KVStore, key: Int, value: Float64):
    """Insert or update a key-value pair."""
    var idx = _find_index(store, key)
    if idx >= 0:
        store.values[idx] = value
    else:
        store.keys.append(key)
        store.values.append(value)
        store.size += 1


fn kv_get(store: KVStore, key: Int) -> Float64:
    """Get value for key. Returns KV_MISS (-999999.0) on miss."""
    var idx = _find_index(store, key)
    if idx >= 0:
        return store.values[idx]
    return KV_MISS


fn kv_delete(mut store: KVStore, key: Int) -> Bool:
    """Delete key from store. Returns True if found and deleted."""
    var idx = _find_index(store, key)
    if idx < 0:
        return False
    # Swap with last element and pop
    var last = store.size - 1
    if idx != last:
        store.keys[idx] = store.keys[last]
        store.values[idx] = store.values[last]
    _ = store.keys.pop()
    _ = store.values.pop()
    store.size -= 1
    return True


fn kv_contains(store: KVStore, key: Int) -> Bool:
    """Check if key exists in store."""
    return _find_index(store, key) >= 0


fn kv_size(store: KVStore) -> Int:
    """Return number of entries in store."""
    return store.size


fn kv_keys(store: KVStore) -> List[Int]:
    """Return all keys."""
    var result = List[Int]()
    for i in range(store.size):
        result.append(store.keys[i])
    return result^


fn kv_values(store: KVStore) -> List[Float64]:
    """Return all values."""
    var result = List[Float64]()
    for i in range(store.size):
        result.append(store.values[i])
    return result^


fn kv_clear(mut store: KVStore):
    """Remove all entries."""
    store.keys = List[Int]()
    store.values = List[Float64]()
    store.size = 0


fn snapshot(store: KVStore) -> List[List[Float64]]:
    """Serialize store to [[key_as_float, value], ...] for persistence."""
    var result = List[List[Float64]]()
    for i in range(store.size):
        var pair = List[Float64]()
        pair.append(Float64(store.keys[i]))
        pair.append(store.values[i])
        result.append(pair^)
    return result^


fn restore(data: List[List[Float64]]) -> KVStore:
    """Restore a KVStore from snapshot data."""
    var store = KVStore()
    for i in range(len(data)):
        var key = Int(data[i][0])
        var value = data[i][1]
        store.keys.append(key)
        store.values.append(value)
        store.size += 1
    return store^
