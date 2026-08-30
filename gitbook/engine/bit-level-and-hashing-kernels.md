---
icon: fingerprint
description: Bit-twiddling primitives, non-cryptographic checksums and check digits, a counting Bloom filter, counter-based Philox4x64-10 random draws, and perceptual image hashing for near-duplicate detection.
---

# Bit-level and hashing kernels

Five modules that each operate close to the bit, but on five unrelated problems: `bitops` is raw
integer manipulation (popcount, rotation, single-bit set/clear/test); `checksum` is legacy
error-detection and check-digit arithmetic (Adler-32, Luhn, ISBN, Verhoeff — not cryptographic
hashing); `bloom_counting` is an approximate-membership sketch that can forget an item as well as
remember one; `counter_rng` is a pseudo-random generator addressed by coordinates instead of by
mutating state; and `perceptual_hash` collapses an image into a 64-bit fingerprint two near-duplicate
photos will share almost all of. None of the five imports another — this is a thematic grouping (bit
widths, hash-style mixing, fixed-size fingerprints), not a shared-code family, the same honest
disclosure the [Mixture-of-experts and routing kernels](mixture-of-experts-and-routing-kernels.md)
page makes about its own five modules.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("checksum", "luhn_check", [[7, 9, 9, 2, 7, 3, 9, 8, 7, 1, 3]])["result"]
# True -- 79927398713, the textbook valid Luhn number

runtime.execute("counter_rng", "philox_word", [1, 2, 3, 4, 5, 4, 0])["result"]
# 5544217767837969664 -- the exact word every call with these seven coordinates
# (master_seed=1, scenario=2, replication=3, lap=4, car=5, process=4, draw=0)
# has ever produced; pinned as a known-answer vector in the real test suite
```

## The modules

| Module | What it does |
| --- | --- |
| `bitops` | Bit-twiddling over 64-bit `Int` (and `UInt32` for rotate/reverse): popcount, leading/trailing zero counts, power-of-2 tests, single-bit set/clear/test/toggle, and a 64-bit FNV-1a string hash. |
| `checksum` | Non-cryptographic checksums and check digits: Adler-32, Fletcher-16, the 16-bit Internet checksum, XOR/modular/parity sums, and the Luhn, ISBN-10, ISBN-13, and Verhoeff check-digit algorithms. |
| `bloom_counting` | A counting Bloom filter (`CountingBloom`): per-bucket counters instead of single bits, so `cb_remove` can un-add an item, plus the theoretical false-positive-rate and optimal-hash-count formulas used to size one. |
| `counter_rng` | Stateless, counter-based (Philox4x64-10) random draws: every value is a pure function of its coordinates, so replaying the same coordinates reproduces the same draw regardless of what else drew numbers first. |
| `perceptual_hash` | aHash / dHash / pHash 64-bit image fingerprints plus Hamming-distance comparison, for near-duplicate detection ahead of a full vision-model call. |

## `bitops`: 64-bit primitives, and a correction of a comment in a different module

`popcount`, `leading_zeros`, and `trailing_zeros` all treat `Int` as a 64-bit word (`leading_zeros(0)`
and `trailing_zeros(0)` both return `64`, the "no bits at all" convention rather than an error).
`next_power_of_2`/`is_power_of_2` and the `bit_set`/`bit_clear`/`bit_test`/`bit_toggle` family round
out the integer side; `reverse_bits`, `rotate_left`, and `rotate_right` operate on `UInt32` instead,
and `fnv1a_hash` is the one string-input function, folding a 64-bit FNV-1a hash and masking off the
sign bit so the result is always non-negative.

Hand-written assertions in `tests/mojo/test_wave11.mojo` pin: `popcount(0b1011) == 3`,
`popcount(255) == 8`; `is_power_of_2(64)` true, `is_power_of_2(63)` and `is_power_of_2(0)` false;
`next_power_of_2(5) == 8`, `next_power_of_2(8) == 8` (already a power of 2), `next_power_of_2(1) == 1`;
`bit_test(0b1010, 1)` true, `bit_test(0b1010, 0)` false; `bit_set(0, 3) == 8`;
`bit_clear(0b1111, 2) == 0b1011`; `bit_toggle(0b1010, 0) == 0b1011` and `bit_toggle(0b1010, 1) ==
0b1000`; `trailing_zeros(8) == 3`, `trailing_zeros(0) == 64`; and `rotate_right(rotate_left(1, 4), 4)
== 1` — the two are exact inverses, as a 32-bit rotation must be.

**`popcount` actually does handle the sign bit correctly — a comment elsewhere in the corpus says
otherwise.** `popcount`'s loop right-shifts with `(n >> 1) & 0x7FFFFFFFFFFFFFFF` on every iteration,
which clears whatever an arithmetic shift's sign-extension put in bit 63, turning the shift into a
logical one for the rest of the loop. Re-deriving this by hand for the sign-bit cases that would
expose a bug: `popcount(-1)` (all 64 bits set) returns `64`, and `popcount(-9223372036854775808)`
(the minimum representable 64-bit signed value, only bit 63 set) returns `1` — both correct,
full-width answers. Despite that, `mojo/engine/perceptual_hash.mojo`
defines its own `_popcount_u64` helper with the comment *"Count set bits across all 64 bits (bitops.
popcount drops bit 63)"* — that comment's claim doesn't hold up against `bitops.popcount`'s own
behavior. The dedicated helper is still the right call, just for a narrower reason than the comment
gives: `popcount` takes `Int`, not `UInt64`, so `perceptual_hash` (which hashes into `UInt64`) needs
its own copy regardless of whether the sign-bit concern is real.

## `checksum`: legacy error detection, not CRC-32 and not cryptographic hashing

None of these eleven functions is a cryptographic hash or an actual CRC. The real IEEE CRC-32 lives
in a different module — `crypto.crc32`, documented in
[Data integrity and encoding](data-integrity-and-encoding.md) — and this module's job is older,
simpler error-detection arithmetic plus check-digit validation: Adler-32 and Fletcher-16 (both
rolling-sum checksums), a simplified 16-bit Internet checksum, XOR/modular/parity sums, and four
check-digit algorithms (Luhn, ISBN-10, ISBN-13, Verhoeff).

Hand-written assertions in `tests/mojo/test_wave45.mojo` pin: `adler32([0]) == 65537`,
`adler32([1]) == 131074` (`a=2, b=2` → `(2<<16)|2`), `adler32([]) == 1`; `fletcher16([1, 2]) == 1027`;
`internet_checksum([0x00, 0x01, 0x00, 0x02]) == 65532` (two 16-bit words `1` and `2` sum to `3`,
ones'-complemented to `0xFFFC`); `xor_checksum([0xFF, 0xFF]) == 0`, `xor_checksum([0xAA, 0x55]) ==
0xFF`; `modular_sum([1, 2, 3], 256) == 6`, `modular_sum([200, 100], 256) == 44` (`300 mod 256`);
`parity_bit([1, 0, 1, 1]) == 1` (odd count of ones), `parity_bit([1, 0, 1, 0]) == 0`; `79927398713`
passes `luhn_check` and altering its last digit to `79927398714` fails it; `luhn_checksum` on
`7992739871` (the same number with its check digit removed) returns `3`, reconstructing the original;
`0306406152` passes `isbn10_check` and `0306406153` fails; `9780306406157` passes `isbn13_check` and
`9780306406158` fails; and `verhoeff_check([0, 1])` is valid while `verhoeff_check([0, 2])` and an
empty digit list are both invalid.

## `bloom_counting`: membership *and* multiplicity, with deletion

A classic Bloom filter's buckets are single bits: an insert sets them, and there is no way to undo
one insert without risking false negatives for every other item hashed into the same bucket. `cb_add`
increments an `Int` counter at each of `n_hashes` positions instead, so `cb_remove` can decrement the
same positions back down — clamped at `0`, never going negative — and `cb_count_estimate` reports the
minimum counter across an item's positions as its estimated insert count. `cb_contains` is unchanged
in spirit: true only if every one of the item's positions is non-zero.

Pinned in `tests/mojo/test_wave43.mojo`: `cb_create(100, 3)` allocates `100` counters, all zero;
adding item `7` three times and reading `cb_count_estimate(bloom, 7)` back gives `3`, then two more
adds bring it to `5`; removing an item that was never added leaves every counter at `0` (the
underflow clamp verified directly); and after `cb_reset`, every counter reads `0` and `cb_contains`
returns false for a previously-added item. `cb_hash` mixes `item ^ seed` through an FNV-1a-style
multiply-xor-shift fold (the same shape as `bitops.fnv1a_hash`, but a separate implementation) and
reduces `mod size` — the real test only pins the *range* of that result (`0 <= h < size`), not an
exact value, since the fold depends on Mojo's 64-bit signed-overflow arithmetic; this page follows
that same standard rather than asserting a specific hash integer unverified against source.

The two formulas that size a filter are independently checkable by hand: `cb_false_positive_rate(m,
k, n) = (1 - e^(-kn/m))^k`, so `cb_false_positive_rate(1000, 3, 10) ≈ 2.581 × 10⁻⁵` (`inner =
1 - e^{-0.03} ≈ 0.029554`, cubed). `cb_optimal_hashes(m, n) = ⌊(m/n)·ln 2⌋`, so
`cb_optimal_hashes(1000, 100) = ⌊10 × 0.693147...⌋ = 6` — matching the real test's own comment
(`m/n=10, optimal k ≈ 10·ln(2) ≈ 6.93 → 6`), which asserts a `[5, 8]` range rather than the exact
value. The `CountingBloom` struct itself is four fields: `counters: List[Int]`, `size: Int`,
`n_hashes: Int`, and `hash_seeds: List[Int]` — the seeds are generated once by `cb_create` from a
golden-ratio constant (`i * 2654435761 + 131` for hash index `i`), not re-derived on every hash call.

{% hint style="warning" %}
**`cb_create` isn't unique to this module.** A completely unrelated module, `queue_ds`, also exports
a `cb_create` — for a `CircularBuffer`, taking one argument (`capacity`) instead of this module's two
(`size`, `n_hashes`). `runtime.execute("queue_ds", "cb_create", ...)` and
`runtime.execute("bloom_counting", "cb_create", ...)` are registered as separate runtime modules and
never collide in practice, but grepping the codebase for `cb_` or reading a snippet without its
module argument can. See
[Data structures and algorithms kernels](data-structures-and-algorithms-kernels.md) for the
`CircularBuffer` side of that name.
{% endhint %}

## `counter_rng`: Philox4x64-10 addressed by (scenario, replication, lap, car, process, draw)

Every function here takes the same seven leading coordinates — `master_seed`, `scenario_id`,
`replication_id`, `lap_id`, `car_id`, `process_id`, `draw_index` — packed into a Philox4x64-10
counter/key: `c0 = replication_id`, `c1 = (lap_id << 32) | (car_id << 16) | process_id`, `c2 =
draw_index >> 2`, `k0 = master_seed`, `k1 = scenario_id`. Because every draw is computed from scratch
from these coordinates alone, drawing more or fewer unrelated numbers beforehand can never change a
later draw — the property the module's own docstring calls "valid common random numbers," and the
one `tests/mojo/test_counter_rng.mojo` (a *hand-written* file, unlike its auto-generated siblings in
the same `mojo/tests/libs/` directory) tests directly: 20 lap-noise draws for car 5 come back
bit-identical whether they're drawn back-to-back or with a trajectory-dependent number of unrelated
draws burned in between.

Every distribution consumes a **fixed** number of draws — one for `rng_uniform`, `rng_uniform_left_open`,
`rng_bernoulli`, `rng_exponential`; two for `rng_normal` / `rng_normal_scaled` (Box-Muller, cosine
branch only — the sine companion is computed and discarded, never cached, so consumption never
depends on call parity). Re-deriving the pinned known-answer vector (`master_seed=1, scenario=2,
replication=3, lap=4, car=5, process=4`) by hand from the source formulas:

```python
runtime.execute("counter_rng", "philox_word", [1, 2, 3, 4, 5, 4, 0])["result"]
# 5544217767837969664
runtime.execute("counter_rng", "rng_uniform", [1, 2, 3, 4, 5, 4, 0])["result"]
# 0.30055264743113297 -- (5544217767837969664 >> 11) * 2**-53
runtime.execute("counter_rng", "rng_normal", [1, 2, 3, 4, 5, 4, 0])["result"]
# 0.9158255540782856 -- Box-Muller from draws 0 and 1 (words 5544217767837969664, 2756644627510874722)
```

`philox_block`/`PhiloxBlock` (fields `w0`..`w3`) exist purely as a performance shortcut: a 10-round
Philox mix produces all four output words in one pass, so reading two words that fall in the same
block (as `rng_normal`'s two draws usually do) only needs one invocation instead of two —
`philox_word(..., draw_index)` and `philox_block(..., draw_index >> 2).word(draw_index & 3)` are the
same number by construction, just computed with or without the redundant second pass. The three
zero-argument probes — `rng_version() == "philox4x64-10/v1"`, `rng_global_sentinel() == 0xFFFF`
(the `car_id` value reserved for exogenous, non-per-car processes like a safety car), and
`rng_selftest()` (a fold of 64 words from fixed coordinates into one `UInt64`, pinned at
`13066461341573311292`) — exist as one-call fingerprints of the generator itself: any future change
to the layout, constants, or word-selection changes all three, on purpose.

{% hint style="info" %}
**A second, generalized copy of this exact generator exists, but it isn't this module.**
`mojo/engine/determinism/counter_rng.mojo` implements the identical Philox4x64-10 math with the same
counter/key layout, under renamed, domain-neutral parameters (`dim0`, `dim1`, `stream_id` in place of
`lap_id`, `car_id`, `process_id`). It is not in the runtime contract and cannot be reached through
`runtime.execute` — it exists so other kernels can key their own common-random-number draws off this
generator as a library dependency rather than a domain-specific one. [Forecasting](forecasting.md)'s
`forecasting.bagging` names it directly, keying its moving-block-bootstrap resample draws by
`(master_seed, series_id, replicate_id, stream, block index)` through it. The identical
`rng_version() == "philox4x64-10/v1"` string also surfaces from
[Optimization heuristics](optimization-heuristics.md) and
[Discrete-event simulation](discrete-event-simulation.md) results, though those two pages don't name
the module directly — consistent with the same shared generator sitting underneath, not proof by
itself. The two files aren't just similar — `mojo/tests/libs/test_determinism_counter_rng.mojo` pins the *exact same* known-answer
vectors (`EXPECT_0` through `EXPECT_7`, `EXPECT_SELFTEST`) as this module's own test, which is
possible only because renaming `lap_id`/`car_id`/`process_id` to `dim0`/`dim1`/`stream_id` changes
nothing about the arithmetic — the bit-packing formula for `c1` is textually identical either way.
{% endhint %}

## `perceptual_hash`: 64-bit fingerprints for near-duplicate images

Three hashers, all built on `image_resize`'s box-average downscaling (see
[Image transform and morphology kernels](image-transform-and-morphology-kernels.md) for
`resize_for_hash`/`resize_for_dhash` themselves): `ahash` downscales to 8×8 and sets a bit wherever a
cell is at or above the grid's own mean; `dhash` downscales to 9×8 and sets a bit wherever a cell
differs from its right-hand neighbor in a fixed direction; `phash` downscales to 32×32, runs an
unnormalized 8×8 DCT-II, drops the DC (average-brightness) coefficient, and sets a bit wherever a
remaining AC coefficient exceeds the median of the other 63. `hamming_distance` counts differing bits
between two hashes (`popcount(a ^ b)`, `0..64`) and `is_duplicate` is `hamming_distance <=
max_distance`. The `_flat` variants reshape a row-major flat pixel buffer through
`image_resize.reshape_to_grid` first, for callers sending pixels over the runtime socket instead of a
nested grid.

Hand-verified against the real formulas (only the auto-generated smoke test,
`mojo/tests/libs/test_perceptual_hash.mojo`, exercises this module — no pinned numeric suite exists
in `tests/mojo/test_wave*.mojo`, unlike `bitops`, `checksum`, and `bloom_counting`):

```python
# 8x8 grid, top 4 rows = 255.0, bottom 4 rows = 0.0 -> mean 127.5
runtime.execute("perceptual_hash", "ahash_flat", [[255.0]*32 + [0.0]*32, 8, 8])["result"]
# 18446744069414584320  (0xFFFFFFFF00000000) -- the top half sets all 32 leading bits

# 8 rows x 9 cols, each row ascending 0..8 -> every cell < its right neighbor
runtime.execute("perceptual_hash", "dhash_flat", [[0.0,1.0,2.0,3.0,4.0,5.0,6.0,7.0,8.0]*8, 9, 8])["result"]
# 18446744073709551615  (0xFFFFFFFFFFFFFFFF, all 64 bits set)

runtime.execute("perceptual_hash", "hamming_distance", [0xFF, 0x0F])["result"]
# 4  -- popcount(0xFF ^ 0x0F) = popcount(0xF0)
runtime.execute("perceptual_hash", "is_duplicate", [0xFF, 0x0F, 4])["result"]
# True   (4 <= 4)
runtime.execute("perceptual_hash", "is_duplicate", [0xFF, 0x0F, 3])["result"]
# False  (4 > 3)
```

Two things worth flagging, both found by re-deriving the algorithm independently rather than trusting
the inline comments:

* **`dhash`'s comment names the opposite polarity from its own comparison.** The docstring reads *"bit
  set where a cell is brighter than its right neighbor,"* but the code sets the bit when
  `g[r][c] < g[r][c + 1]` — that is, when the current cell is *dimmer* than its right neighbor, the
  reverse of what the comment says. This doesn't affect near-duplicate detection (Hamming distance is
  symmetric regardless of which polarity convention a hasher picks, as long as it's consistent with
  itself), but a caller comparing this module's raw bit pattern against an external dHash
  implementation using the classic "left brighter than right" convention would see every bit
  inverted from what they'd expect.
* **`phash` on a perfectly flat (constant-color) image has its bit pattern decided by floating-point
  noise, not by the image.** The DCT-II basis functions this module uses sum to exactly zero over a
  full 32-point period at every non-zero frequency (a standard trigonometric identity, confirmed
  numerically to `~1e-15`), so for a constant image the 63 AC coefficients that survive dropping the
  DC term are, in exact arithmetic, all identically `0.0`. In `Float64` they instead land at
  `~10⁻¹²` magnitude — real rounding noise, not signal — and since the median-threshold comparison
  is a strict `>`, which of those 63 near-zero coefficients reads above versus below their own
  (also near-zero) median is effectively arbitrary. A flat test-color image is therefore a poor
  synthetic fixture for hand-verifying `phash`'s bit pattern; a real photo's AC energy is orders of
  magnitude above this noise floor and doesn't have this problem.

`perceptual_hash.dhash_flat` is a real, already-shipped consumer of this module from outside it:
[Video quality and accessibility kernels](video-quality-and-accessibility-kernels.md)'s
`video_similarity.frame_hash_hamming_series` calls it once per paired video frame as one of three
signals (alongside SSIM/NCC and a temporal-motion term) feeding `clip_duplicate_score_flat`.

## Edge-case behavior

* **`leading_zeros(0)` and `trailing_zeros(0)` both return `64`**, not an error or a sentinel like
  `-1` — "no bits set" is treated as "every possible position is a leading/trailing zero."
* **`is_power_of_2(0)` is `False`** — the function requires `x > 0` explicitly, so zero is excluded
  even though `0 & (0 - 1) == 0` would otherwise pass the bitwise test alone.
* **`cb_remove` never underflows** — decrementing a counter already at `0` is a no-op per position,
  verified directly by the real test (removing a never-added item leaves every counter at `0`).
* **Empty input across `checksum`**: `adler32([])` returns `1` (the algorithm's own identity state,
  `a=1, b=0` packed), not `0` or an error.
* **`ahash`/`dhash`/`phash` all guard on grid size** — if the resized grid comes back smaller than the
  hash needs (8×8 for aHash, 8×9 for dHash, 32×32 for pHash), each function returns `UInt64(0)`
  rather than indexing out of bounds.

## Verification

`bitops`, `checksum`, and `bloom_counting` each have two test files: an auto-generated smoke test in
`mojo/tests/libs/` (one call per function, checked only for not raising / being finite) and a real
hand-written suite in `tests/mojo/` (`test_wave11.mojo`, `test_wave45.mojo`, `test_wave43.mojo`
respectively) that pins the exact values quoted above. `counter_rng` is the exception to that
split — its file inside `mojo/tests/libs/` (`test_counter_rng.mojo`) is itself hand-written, not
machine-generated, and its known-answer vectors are cross-validated against an independent
spec-faithful Python Philox4x64-10 and, under a documented offset, against numpy's own Philox bit
generator (`scripts/timing/validate_rng.py`), per the module's own docstring. `perceptual_hash` has
only the auto-generated smoke test — every number in this page's `perceptual_hash` section was
derived and independently checked against `mojo/engine/perceptual_hash.mojo`'s real formulas, not
copied from any pinned assertion, which is exactly how the `dhash` polarity note and the `phash`
floating-point-noise finding above were found.

**Next:** [Data integrity and encoding](data-integrity-and-encoding.md) for the cryptographic-grade
counterpart to this page's checksums (`crypto.crc32`, `crypto.hash_chain`), or
[Video quality and accessibility kernels](video-quality-and-accessibility-kernels.md) for a real
downstream consumer of `perceptual_hash`.
