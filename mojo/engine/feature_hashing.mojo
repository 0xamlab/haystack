"""
feature_hashing.mojo — Hashing trick for categorical/text features. Zero
Python imports.

Replaces sklearn.feature_extraction.FeatureHasher (and the hashing side of
sklearn HashingVectorizer): maps arbitrary feature names/tokens into a fixed
number of buckets via seeded 64-bit FNV-1a, with a hash-derived sign so
collisions cancel in expectation (Weinberger et al. hashing trick).

Public API:
  hash_feature            — bucket index in [0, n_buckets) for a feature name
  hash_sign               — +1 / -1 hashing-trick sign for a feature name
  hash_features_row       — dense row: signed accumulation of values by bucket
  collision_rate_estimate — birthday-bound P(any bucket collision)
"""
from std.math import exp


# ── _fnv1a64 ─────────────────────────────────────────────────────────────────


fn _fnv1a64(name: String, seed: Int) -> UInt64:
    """Seeded 64-bit FNV-1a hash of a feature name.

    The seed is folded in first as 8 little-endian bytes through the same
    FNV-1a absorb step, then the UTF-8 bytes of the name. seed=0 folds eight
    zero bytes, so results still differ from unseeded textbook FNV-1a but
    remain fully deterministic. Negative seeds are mapped to their magnitude
    (same convention as model_selection's seeded RNG).
    """
    var h: UInt64 = 0xCBF29CE484222325  # FNV-1a 64-bit offset basis
    var prime: UInt64 = 0x100000001B3  # FNV-1a 64-bit prime
    var sv: UInt64
    if seed < 0:
        sv = UInt64(-(seed + 1)) + 1
    else:
        sv = UInt64(seed)
    for k in range(8):
        var b = (sv >> UInt64(8 * k)) & UInt64(0xFF)
        h = (h ^ b) * prime
    var bs = name.as_bytes()
    for i in range(len(bs)):
        h = (h ^ UInt64(bs[i])) * prime
    return h


# ── hash_feature ─────────────────────────────────────────────────────────────


fn hash_feature(name: String, n_buckets: Int, seed: Int) -> Int:
    """Bucket index in [0, n_buckets) for a feature name (hashing trick).

    Deterministic: the same (name, n_buckets, seed) always yields the same
    bucket. Different seeds re-partition the feature space (use one fixed
    seed per trained model). Empty names hash like any other string.
    n_buckets <= 0 returns 0 (degenerate config, no valid bucket exists).
    """
    if n_buckets <= 0:
        return 0
    return Int(_fnv1a64(name, seed) % UInt64(n_buckets))


# ── hash_sign ────────────────────────────────────────────────────────────────


fn hash_sign(name: String, seed: Int) -> Int:
    """Hashing-trick sign (+1 or -1) for a feature name.

    Uses bit 63 of the same seeded FNV-1a hash that drives hash_feature, so
    one hash evaluation determines (bucket, sign). The sign makes colliding
    features cancel in expectation instead of biasing the bucket upward
    (Weinberger et al. 2009).
    """
    if (_fnv1a64(name, seed) >> 63) == UInt64(1):
        return -1
    return 1


# ── hash_features_row ────────────────────────────────────────────────────────


fn hash_features_row(
    names: List[String], values: List[Float64], n_buckets: Int, seed: Int
) -> List[Float64]:
    """Dense hashed feature row: signed accumulation of values by bucket.

    Returns a length-n_buckets row initialised to 0.0 where, for each pair
    (names[i], values[i]):
      row[hash_feature(names[i])] += hash_sign(names[i]) * values[i].
    Pairs beyond min(len(names), len(values)) are ignored. For a bare
    categorical/token presence feature pass value 1.0. n_buckets <= 0
    returns an empty list.
    """
    var row = List[Float64]()
    if n_buckets <= 0:
        return row^
    for _ in range(n_buckets):
        row.append(0.0)
    var n = min(len(names), len(values))
    for i in range(n):
        var h = _fnv1a64(names[i], seed)
        var bucket = Int(h % UInt64(n_buckets))
        var sgn: Float64 = 1.0
        if (h >> 63) == UInt64(1):
            sgn = -1.0
        row[bucket] += sgn * values[i]
    return row^


# ── collision_rate_estimate ──────────────────────────────────────────────────


fn collision_rate_estimate(n_features: Int, n_buckets: Int) -> Float64:
    """Birthday-bound estimate of P(at least one bucket collision).

    Approximates the probability that any two of n_features distinct feature
    names land in the same of n_buckets buckets under a uniform hash:
      1 - exp(-n * (n - 1) / (2 * m)).
    n_features <= 1 returns 0.0 (nothing to collide). n_features > n_buckets
    (including n_buckets <= 0) returns 1.0 (pigeonhole certainty).
    """
    if n_features <= 1:
        return 0.0
    if n_features > n_buckets:
        return 1.0
    var n = Float64(n_features)
    var m = Float64(n_buckets)
    return 1.0 - exp(-n * (n - 1.0) / (2.0 * m))
