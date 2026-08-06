"""
bloom_filter.mojo — Probabilistic set membership filter. Zero Python imports.

Useful for dedup, caching decisions, and fast "definitely not in set" checks.
Uses FNV-1a hash with k different seeds to simulate k independent hash functions.

Public API:
  struct BloomFilter(Copyable, Movable)
    def __init__(out self, expected_items: Int, false_positive_rate: Float64 = 0.01)
    def add(mut self, item: String)
    def might_contain(self, item: String) -> Bool
    def false_positive_rate(self) -> Float64
    def count(self) -> Int
"""

from std.math import log, ceil


# ── FNV-1a seeded hash ───────────────────────────────────────────────────────


def _fnv1a_seeded(data: String, seed: Int) -> Int:
    """FNV-1a 64-bit hash with a seed mixed into the offset basis."""
    var hash_val: Int = -3750763034362895579  # 0xcbf29ce484222325 as signed
    # Mix seed into offset basis
    hash_val = hash_val ^ seed
    var prime: Int = 1099511628211
    var bytes = data.as_bytes()
    for i in range(len(bytes)):
        hash_val = hash_val ^ Int(bytes[i])
        hash_val = hash_val * prime
    return hash_val & 0x7FFFFFFFFFFFFFFF


# ── BloomFilter ──────────────────────────────────────────────────────────────


struct BloomFilter(Copyable, Movable):
    """Bloom filter — probabilistic set membership.

    Reports either "possibly in set" or "definitely not in set".
    False positives are possible; false negatives are not.
    """

    var _bits: List[Bool]
    var _num_bits: Int
    var _num_hashes: Int
    var _count: Int
    var _target_fpr: Float64

    def __init__(out self, expected_items: Int, false_positive_rate: Float64 = 0.01):
        """Create a Bloom filter sized for the expected number of items.

        Args:
            expected_items: Expected number of items to be added.
            false_positive_rate: Target false positive rate (default 1%).
        """
        self._target_fpr = false_positive_rate
        self._count = 0

        # Compute optimal bit array size: m = -n*ln(p) / (ln(2))^2
        var n = Float64(expected_items)
        if n < 1.0:
            n = 1.0
        var p = false_positive_rate
        if p <= 0.0:
            p = 0.001
        if p >= 1.0:
            p = 0.5

        var ln2 = 0.6931471805599453
        var ln2_sq = ln2 * ln2
        var m_float = -(n * log(p)) / ln2_sq
        var m = Int(ceil(m_float))
        if m < 64:
            m = 64

        # Compute optimal number of hash functions: k = (m/n) * ln(2)
        var k_float = (Float64(m) / n) * ln2
        var k = Int(ceil(k_float))
        if k < 1:
            k = 1
        if k > 20:
            k = 20

        self._num_bits = m
        self._num_hashes = k

        # Initialize bit array to all False
        self._bits = List[Bool]()
        for _ in range(m):
            self._bits.append(False)

    def add(mut self, item: String):
        """Add an item to the Bloom filter.

        Args:
            item: The string item to add.
        """
        for i in range(self._num_hashes):
            var h = _fnv1a_seeded(item, i * 0x9E3779B97F4A7C15 + i)
            var idx = h % self._num_bits
            self._bits[idx] = True
        self._count += 1

    def might_contain(self, item: String) -> Bool:
        """Check if an item might be in the set.

        Returns True if the item is possibly present (may be false positive).
        Returns False if the item is definitely absent.

        Args:
            item: The string item to check.

        Returns:
            True if possibly present, False if definitely absent.
        """
        for i in range(self._num_hashes):
            var h = _fnv1a_seeded(item, i * 0x9E3779B97F4A7C15 + i)
            var idx = h % self._num_bits
            if not self._bits[idx]:
                return False
        return True

    def false_positive_rate(self) -> Float64:
        """Estimate the current false positive rate based on fill ratio.

        Uses the formula: (1 - e^(-kn/m))^k

        Returns:
            Estimated false positive rate.
        """
        if self._count == 0:
            return 0.0
        var k = Float64(self._num_hashes)
        var n = Float64(self._count)
        var m = Float64(self._num_bits)

        # Count actual set bits for more accurate estimate
        var set_bits = 0
        for i in range(self._num_bits):
            if self._bits[i]:
                set_bits += 1

        var fill_ratio = Float64(set_bits) / m
        # FPR ≈ fill_ratio ^ k
        var fpr = 1.0
        for _ in range(self._num_hashes):
            fpr = fpr * fill_ratio
        return fpr

    def count(self) -> Int:
        """Return the approximate count of items added.

        Note: This is the exact count of add() calls, not a cardinality estimate.

        Returns:
            Number of items added to the filter.
        """
        return self._count
