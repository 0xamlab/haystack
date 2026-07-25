---
icon: bolt
description: Seeded FNV-1a feature hashing for fixed-width vectorization of unbounded feature names.
---

# Feature hashing (the hashing trick)

`feature_hashing` maps arbitrary feature names/tokens into a fixed number
of buckets in pure Mojo with zero Python imports — replacing
`sklearn.feature_extraction.FeatureHasher` (and the hashing side of
sklearn's `HashingVectorizer`). Hashing is seeded 64-bit FNV-1a with a
hash-derived sign, so colliding features cancel in expectation instead of
biasing a bucket upward (Weinberger et al. 2009 hashing trick).

## Functions

| Function | What it does |
|---|---|
| `hash_feature(name, n_buckets, seed)` | Bucket index in `[0, n_buckets)` for a feature name. `n_buckets <= 0` returns 0 (degenerate config). |
| `hash_sign(name, seed)` | +1 / −1 hashing-trick sign, taken from bit 63 of the same seeded hash — one hash evaluation determines (bucket, sign). |
| `hash_features_row(names, values, n_buckets, seed)` | Dense length-`n_buckets` row: `row[bucket] += sign * value` per pair. Pass value 1.0 for bare categorical/token presence. |
| `collision_rate_estimate(n_features, n_buckets)` | Birthday-bound estimate of P(any bucket collision): `1 − exp(−n(n−1)/2m)`; pigeonhole cases return 1.0. |

## Determinism and seeding

- **Fully deterministic**: the same (name, n_buckets, seed) always yields
  the same bucket and sign — the tests assert repeated calls are
  identical (e.g. `"sym=SPY"` at seed 42, m = 1000 is always bucket 281,
  sign −1).
- Different seeds re-partition the feature space; use **one fixed seed
  per trained model**. Seed 0 folds eight zero bytes, so results still
  differ from unseeded textbook FNV-1a but remain fully deterministic;
  negative seeds map to their magnitude.
- Edge behavior never traps: `n_buckets <= 0` gives bucket 0 / an empty
  row; mismatched `names`/`values` lengths process
  `min(len(names), len(values))`; empty names hash like any other string.

## Verification

Expected buckets and signs in the tests were hand-computed with an
independent reference implementation of seeded 64-bit FNV-1a:

- Reference hashes pinned exactly: h64("price", seed 42) =
  15582674013810968360 → bucket 360 at m = 1000 ("volume" → 49,
  "side=buy" → 17), and a 2³² modulus pins the low 32 bits
  ("price" → 2078918440).
- Reference signs: "price" → −1, "volume" → +1 at seed 42; row output
  is asserted consistent with the `hash_feature` + `hash_sign`
  composition.
- Exact cancellation: at seed 7, m = 4, "volume" (sign −1) and
  "side=buy" (sign +1) share bucket 0, and equal values cancel to
  exactly 0 — the property that makes the trick unbiased.
- `collision_rate_estimate` matches the birthday formula to 1e-12:
  (23, 365) → 0.5000017521827107 and (100, 1000) → 0.9929165910709479,
  with pigeonhole cases (n_features > n_buckets) returning exactly 1.0.

**Next:** promote what you trained with [statistical model comparison](ml-model-comparison.md), or browse the [engine catalog](catalog.md).
