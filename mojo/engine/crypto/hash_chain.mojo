"""
hash_chain.mojo — Hash chains & Merkle trees. Zero Python imports.

Uses simple integer hashing (FNV-1a style) for demonstration.

Public API:
  def simple_hash(data)                 — FNV-1a-like hash → 32-bit int
  def hash_chain_build(items)           — Build hash chain
  def hash_chain_verify(items, chain)   — Verify hash chain integrity
  def merkle_root(leaves)               — Compute Merkle root
  def merkle_proof(leaves, index)       — Generate Merkle proof
  def merkle_verify(leaf, proof, idx, root) — Verify Merkle proof
  def combine_hashes(a, b)              — Combine two hashes
  def int_to_bytes(value)               — Int → 4 big-endian bytes
  def hash_single(value)                — Hash a single integer
"""


# ── FNV-1a Constants (32-bit) ────────────────────────────────────────────────

comptime FNV_OFFSET: Int = 2166136261
comptime FNV_PRIME: Int = 16777619
comptime MASK_32: Int = 0xFFFFFFFF


# ── Core Hash Functions ──────────────────────────────────────────────────────


def simple_hash(data: List[Int]) -> Int:
    """FNV-1a-like hash of a byte list → 32-bit integer."""
    var h = FNV_OFFSET
    for i in range(len(data)):
        h = h ^ (data[i] & 0xFF)
        h = (h * FNV_PRIME) & MASK_32
    return h


def int_to_bytes(value: Int) -> List[Int]:
    """Convert int to 4 big-endian bytes."""
    var result = List[Int]()
    var v = value & MASK_32
    result.append((v >> 24) & 0xFF)
    result.append((v >> 16) & 0xFF)
    result.append((v >> 8) & 0xFF)
    result.append(v & 0xFF)
    return result^


def hash_single(value: Int) -> Int:
    """Hash a single integer."""
    return simple_hash(int_to_bytes(value))


def combine_hashes(a: Int, b: Int) -> Int:
    """Combine two hashes by hashing their concatenated bytes."""
    var data = List[Int]()
    var a_bytes = int_to_bytes(a)
    var b_bytes = int_to_bytes(b)
    for i in range(len(a_bytes)):
        data.append(a_bytes[i])
    for i in range(len(b_bytes)):
        data.append(b_bytes[i])
    return simple_hash(data)


# ── Hash Chain ───────────────────────────────────────────────────────────────


def hash_chain_build(items: List[List[Int]]) -> List[Int]:
    """Build hash chain: h[0]=hash(items[0]),
    h[i]=hash(h[i-1]_bytes || items[i]).
    Returns chain of hashes."""
    var chain = List[Int]()
    if len(items) == 0:
        return chain^
    chain.append(simple_hash(items[0]))
    for i in range(1, len(items)):
        var prev_bytes = int_to_bytes(chain[i - 1])
        var combined = List[Int]()
        for j in range(len(prev_bytes)):
            combined.append(prev_bytes[j])
        for j in range(len(items[i])):
            combined.append(items[i][j])
        chain.append(simple_hash(combined))
    return chain^


def hash_chain_verify(items: List[List[Int]], chain: List[Int]) -> Bool:
    """Verify hash chain integrity. Recomputes and compares."""
    if len(items) != len(chain):
        return False
    if len(items) == 0:
        return True
    var expected = simple_hash(items[0])
    if expected != chain[0]:
        return False
    for i in range(1, len(items)):
        var prev_bytes = int_to_bytes(chain[i - 1])
        var combined = List[Int]()
        for j in range(len(prev_bytes)):
            combined.append(prev_bytes[j])
        for j in range(len(items[i])):
            combined.append(items[i][j])
        expected = simple_hash(combined)
        if expected != chain[i]:
            return False
    return True


# ── Merkle Tree ──────────────────────────────────────────────────────────────


def _next_level(level: List[Int]) -> List[Int]:
    """Compute next level of Merkle tree by pairing and combining."""
    var result = List[Int]()
    var padded = List[Int]()
    for i in range(len(level)):
        padded.append(level[i])
    # Pad with last element if odd
    if len(padded) % 2 == 1:
        padded.append(padded[len(padded) - 1])
    var i = 0
    while i < len(padded):
        result.append(combine_hashes(padded[i], padded[i + 1]))
        i += 2
    return result^


def merkle_root(leaves: List[Int]) -> Int:
    """Compute Merkle root from leaf hashes.
    Pads with last leaf if odd number."""
    if len(leaves) == 0:
        return 0
    if len(leaves) == 1:
        return leaves[0]
    var current = List[Int]()
    for i in range(len(leaves)):
        current.append(leaves[i])
    while len(current) > 1:
        current = _next_level(current)
    return current[0]


def merkle_proof(leaves: List[Int], index: Int) -> List[Int]:
    """Generate Merkle proof (sibling hashes) for leaf at index."""
    var proof = List[Int]()
    if index < 0 or index >= len(leaves):
        return proof^
    if len(leaves) <= 1:
        return proof^
    var current = List[Int]()
    for i in range(len(leaves)):
        current.append(leaves[i])
    var idx = index
    while len(current) > 1:
        # Pad if odd
        if len(current) % 2 == 1:
            current.append(current[len(current) - 1])
        # Find sibling
        if idx % 2 == 0:
            proof.append(current[idx + 1])
        else:
            proof.append(current[idx - 1])
        # Move to next level
        var next_level = List[Int]()
        var i = 0
        while i < len(current):
            next_level.append(combine_hashes(current[i], current[i + 1]))
            i += 2
        current = next_level^
        idx = idx // 2
    return proof^


def merkle_verify(
    leaf_hash: Int, proof: List[Int], index: Int, root: Int
) -> Bool:
    """Verify a Merkle proof against a known root."""
    var current = leaf_hash
    var idx = index
    for i in range(len(proof)):
        if idx % 2 == 0:
            current = combine_hashes(current, proof[i])
        else:
            current = combine_hashes(proof[i], current)
        idx = idx // 2
    return current == root
