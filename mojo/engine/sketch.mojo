"""
sketch.mojo — Probabilistic sketches. Zero Python imports.

Replaces datasketch with pure Mojo implementations of Count-Min Sketch
and HyperLogLog for approximate counting and cardinality estimation.

Public API:
  CountMinSketch            — Struct for CMS
  create_cms                — Create empty Count-Min Sketch
  cms_add                   — Add item to sketch
  cms_query                 — Query estimated count
  cms_hash                  — Hash function for CMS
  HyperLogLog               — Struct for HLL
  create_hll                — Create HyperLogLog
  hll_add                   — Add item to HLL
  hll_count                 — Estimate cardinality
  hll_hash                  — Hash function for HLL
  leading_zeros             — Count leading zeros in binary
"""
from std.math import log, sqrt, pow


# ── CountMinSketch ───────────────────────────────────────────────────────────


struct CountMinSketch(Copyable, Movable):
    """Count-Min Sketch for approximate frequency estimation."""

    var table: List[List[Int]]
    var width: Int
    var depth: Int
    var hash_seeds: List[Int]

    fn __init__(
        out self,
        table: List[List[Int]],
        width: Int,
        depth: Int,
        hash_seeds: List[Int],
    ):
        self.table = table.copy()
        self.width = width
        self.depth = depth
        self.hash_seeds = hash_seeds.copy()


fn create_cms(width: Int, depth: Int) -> CountMinSketch:
    """Create an empty Count-Min Sketch with given dimensions.

    Args:
        width: Number of columns (larger = more accurate).
        depth: Number of hash functions (rows).

    Returns:
        Initialized CountMinSketch with zeroed table.
    """
    var table = List[List[Int]]()
    var seeds = List[Int]()
    for d in range(depth):
        var row = List[Int]()
        for _ in range(width):
            row.append(0)
        table.append(row^)
        seeds.append(d * 1000003 + 7)
    return CountMinSketch(table^, width, depth, seeds^)


fn cms_hash(item: Int, seed: Int, width: Int) -> Int:
    """Hash function for Count-Min Sketch.

    Computes ((item * seed + 17) % 1000003) % width.

    Args:
        item:  The item to hash.
        seed:  Hash function seed.
        width: Hash range (number of columns).

    Returns:
        Hash value in [0, width).
    """
    var val = item * seed + 17
    # Handle negative values
    if val < 0:
        val = -val
    val = val % 1000003
    return val % width


fn cms_add(mut sketch: CountMinSketch, item: Int, count: Int = 1):
    """Add item to Count-Min Sketch.

    Increments all hash-indexed counters by count.

    Args:
        sketch: The CMS to update.
        item:   The item to add.
        count:  Number of occurrences to add (default 1).
    """
    for d in range(sketch.depth):
        var h = cms_hash(item, sketch.hash_seeds[d], sketch.width)
        sketch.table[d][h] += count


fn cms_query(sketch: CountMinSketch, item: Int) -> Int:
    """Query estimated count of an item (minimum across all hash functions).

    The CMS never underestimates; it may overestimate due to collisions.

    Args:
        sketch: The CMS to query.
        item:   The item to look up.

    Returns:
        Estimated count (>= true count).
    """
    var min_count = sketch.table[0][cms_hash(item, sketch.hash_seeds[0], sketch.width)]
    for d in range(1, sketch.depth):
        var h = cms_hash(item, sketch.hash_seeds[d], sketch.width)
        var c = sketch.table[d][h]
        if c < min_count:
            min_count = c
    return min_count


# ── HyperLogLog ─────────────────────────────────────────────────────────────


struct HyperLogLog(Copyable, Movable):
    """HyperLogLog for approximate cardinality estimation."""

    var registers: List[Int]
    var m: Int
    var p: Int

    fn __init__(out self, registers: List[Int], m: Int, p: Int):
        self.registers = registers.copy()
        self.m = m
        self.p = p


fn create_hll(precision: Int = 10) -> HyperLogLog:
    """Create HyperLogLog with 2^precision registers.

    Args:
        precision: Number of bits for register index (default 10 → 1024 regs).

    Returns:
        Initialized HyperLogLog with zeroed registers.
    """
    var m = 1 << precision  # 2^precision
    var regs = List[Int]()
    for _ in range(m):
        regs.append(0)
    return HyperLogLog(regs^, m, precision)


fn hll_hash(item: Int) -> Int:
    """Hash for HLL using murmur-style bit mixing (32-bit).

    Produces well-distributed 31-bit hash values.

    Args:
        item: The item to hash.

    Returns:
        31-bit positive hash value.
    """
    var h = item & 0xFFFFFFFF
    h = (((h >> 16) ^ h) * 0x45D9F3B) & 0xFFFFFFFF
    h = (((h >> 16) ^ h) * 0x45D9F3B) & 0xFFFFFFFF
    h = ((h >> 16) ^ h) & 0x7FFFFFFF
    return h


fn leading_zeros(value: Int, max_bits: Int = 32) -> Int:
    """Count leading zeros in binary representation.

    Args:
        value:    The integer value.
        max_bits: Maximum number of bits to consider (default 32).

    Returns:
        Number of leading zeros (max_bits if value == 0).
    """
    if value == 0:
        return max_bits
    var count = 0
    var mask = 1 << (max_bits - 1)
    var v = value
    # Mask to max_bits
    var full_mask = (1 << max_bits) - 1
    v = v & full_mask
    while mask > 0:
        if (v & mask) != 0:
            return count
        count += 1
        mask >>= 1
    return count


fn hll_add(mut hll: HyperLogLog, item: Int):
    """Add item to HyperLogLog.

    Hashes item, extracts register index from top p bits,
    counts leading zeros of remaining bits + 1.

    Args:
        hll:  The HLL to update.
        item: The item to add.
    """
    var h = hll_hash(item)
    # Extract register index from top p bits
    var idx = (h >> (31 - hll.p)) & (hll.m - 1)
    # Remaining bits (mask out top p bits)
    var remaining_bits = 31 - hll.p
    var w = h & ((1 << remaining_bits) - 1)
    var zeros = leading_zeros(w, remaining_bits) + 1
    if zeros > hll.registers[idx]:
        hll.registers[idx] = zeros


fn hll_count(hll: HyperLogLog) -> Float64:
    """Estimate cardinality using harmonic mean of registers.

    Uses the standard HLL formula:
      E = alpha_m * m^2 / sum(2^(-register[j]))

    Includes small-range and large-range corrections.

    Args:
        hll: The HLL to query.

    Returns:
        Estimated number of distinct items.
    """
    var m = Float64(hll.m)

    # Alpha_m correction factor
    var alpha: Float64
    if hll.m == 16:
        alpha = 0.673
    elif hll.m == 32:
        alpha = 0.697
    elif hll.m == 64:
        alpha = 0.709
    else:
        alpha = 0.7213 / (1.0 + 1.079 / m)

    # Harmonic mean
    var sum_inv: Float64 = 0.0
    var zeros_count = 0
    for j in range(hll.m):
        sum_inv += pow(2.0, -Float64(hll.registers[j]))
        if hll.registers[j] == 0:
            zeros_count += 1

    var estimate = alpha * m * m / sum_inv

    # Small range correction
    if estimate <= 2.5 * m and zeros_count > 0:
        estimate = m * log(m / Float64(zeros_count))

    return estimate
