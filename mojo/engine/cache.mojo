"""
cache.mojo — Advanced Caching utilities. Zero Python imports.

Replaces cachetools with pure Mojo TTL (Time-To-Live) cache supporting
put/get, expiration, capacity eviction, hit-rate tracking, and contains.

Public API:
  TTLCacheEntry       — Single cache entry with key, value, expiry
  TTLCache            — TTL cache with entries, max_size, ttl, hits, misses
  create_ttl_cache    — Create empty TTL cache
  cache_put           — Insert/update entry (evict oldest if over capacity)
  cache_get           — Retrieve value (sentinel on miss/expired)
  cache_evict_expired — Remove all expired entries
  cache_size          — Current number of entries
  cache_hit_rate      — Hit rate = hits / (hits + misses)
  cache_clear         — Remove all entries, reset stats
  cache_contains      — Check existence without updating stats
"""


# ── TTLCacheEntry ────────────────────────────────────────────────────────────


struct TTLCacheEntry(Copyable, Movable):
    """A single cache entry with key, value, and expiration time."""

    var key: Int
    var value: Float64
    var expires_at: Float64

    def __init__(out self, key: Int, value: Float64, expires_at: Float64):
        self.key = key
        self.value = value
        self.expires_at = expires_at


# ── TTLCache ─────────────────────────────────────────────────────────────────


struct TTLCache(Copyable, Movable):
    """TTL cache with entries list, capacity, TTL, and hit/miss counters."""

    var entries: List[TTLCacheEntry]
    var max_size: Int
    var ttl: Float64
    var hits: Int
    var misses: Int

    def __init__(
        out self,
        entries: List[TTLCacheEntry],
        max_size: Int,
        ttl: Float64,
        hits: Int,
        misses: Int,
    ):
        self.entries = entries.copy()
        self.max_size = max_size
        self.ttl = ttl
        self.hits = hits
        self.misses = misses


# ── create_ttl_cache ─────────────────────────────────────────────────────────


def create_ttl_cache(max_size: Int, ttl: Float64) -> TTLCache:
    """Create an empty TTL cache.

    Args:
        max_size: Maximum number of entries.
        ttl:      Time-to-live for each entry (seconds).

    Returns:
        Empty TTLCache.
    """
    return TTLCache(
        entries=List[TTLCacheEntry](),
        max_size=max_size,
        ttl=ttl,
        hits=0,
        misses=0,
    )


# ── cache_put ────────────────────────────────────────────────────────────────


def cache_put(
    mut cache: TTLCache, key: Int, value: Float64, current_time: Float64
):
    """Put value into cache. Updates existing key or inserts new entry.

    If at capacity and inserting new key, evicts the oldest entry (index 0,
    LRU-like). Sets expiry to current_time + ttl.

    Args:
        cache:        The cache to modify.
        key:          Integer key.
        value:        Float64 value.
        current_time: Current timestamp.
    """
    var expires = current_time + cache.ttl

    # Check if key already exists — update in place
    for i in range(len(cache.entries)):
        if cache.entries[i].key == key:
            cache.entries[i] = TTLCacheEntry(key, value, expires)
            return

    # Evict oldest if at capacity
    if len(cache.entries) >= cache.max_size:
        var new_entries = List[TTLCacheEntry]()
        for i in range(1, len(cache.entries)):
            new_entries.append(cache.entries[i].copy())
        cache.entries = new_entries^

    cache.entries.append(TTLCacheEntry(key, value, expires))


# ── cache_get ────────────────────────────────────────────────────────────────


def cache_get(
    mut cache: TTLCache, key: Int, current_time: Float64
) -> Float64:
    """Get value if present and not expired.

    Returns -999999.0 sentinel on miss or expiration. Updates hits/misses.

    Args:
        cache:        The cache to query.
        key:          Integer key to look up.
        current_time: Current timestamp for expiry check.

    Returns:
        The cached value, or -999999.0 if not found / expired.
    """
    for i in range(len(cache.entries)):
        if cache.entries[i].key == key:
            if cache.entries[i].expires_at > current_time:
                cache.hits += 1
                return cache.entries[i].value
            else:
                # Expired — count as miss
                cache.misses += 1
                return -999999.0
    cache.misses += 1
    return -999999.0


# ── cache_evict_expired ──────────────────────────────────────────────────────


def cache_evict_expired(mut cache: TTLCache, current_time: Float64) -> Int:
    """Remove all expired entries.

    Args:
        cache:        The cache to clean.
        current_time: Current timestamp.

    Returns:
        Number of entries removed.
    """
    var kept = List[TTLCacheEntry]()
    var removed = 0
    for i in range(len(cache.entries)):
        if cache.entries[i].expires_at > current_time:
            kept.append(cache.entries[i].copy())
        else:
            removed += 1
    cache.entries = kept^
    return removed


# ── cache_size ───────────────────────────────────────────────────────────────


def cache_size(cache: TTLCache) -> Int:
    """Current number of entries in cache."""
    return len(cache.entries)


# ── cache_hit_rate ───────────────────────────────────────────────────────────


def cache_hit_rate(cache: TTLCache) -> Float64:
    """Hit rate = hits / (hits + misses). Returns 0.0 if no lookups."""
    var total = cache.hits + cache.misses
    if total == 0:
        return 0.0
    return Float64(cache.hits) / Float64(total)


# ── cache_clear ──────────────────────────────────────────────────────────────


def cache_clear(mut cache: TTLCache):
    """Remove all entries and reset hit/miss counters."""
    cache.entries = List[TTLCacheEntry]()
    cache.hits = 0
    cache.misses = 0


# ── cache_contains ───────────────────────────────────────────────────────────


def cache_contains(cache: TTLCache, key: Int, current_time: Float64) -> Bool:
    """Check if key exists and is not expired (without updating stats).

    Args:
        cache:        The cache to check.
        key:          Integer key.
        current_time: Current timestamp.

    Returns:
        True if key is present and not expired.
    """
    for i in range(len(cache.entries)):
        if cache.entries[i].key == key:
            return cache.entries[i].expires_at > current_time
    return False
