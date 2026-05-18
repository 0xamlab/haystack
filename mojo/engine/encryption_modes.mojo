"""
encryption_modes.mojo — Block Cipher Mode Operations Library. Zero Python imports.

Provides functions for computing block cipher mode parameters including
block counts, IV/nonce sizes, padding, ciphertext lengths, AEAD overhead,
AES key schedule rounds, throughput estimates, and security margins.

Public API:
  ecb_block_count          — Blocks = ceil(data/block)
  cbc_iv_required          — Returns True (CBC always needs IV)
  ctr_nonce_size           — Nonce = block_size / 2
  gcm_tag_length_default   — Returns 16 (128-bit tag)
  padding_pkcs7_bytes      — Pad = block - (data % block)
  ciphertext_length_cbc    — CT = (ceil(PT/block) + 1) * block (with IV)
  ciphertext_length_gcm    — CT = PT + tag
  aead_overhead            — Overhead = tag + nonce
  key_schedule_rounds_aes  — Rounds: 128=10, 192=12, 256=14
  throughput_estimate       — Throughput = block*blocks/1e6 (MB/s)
  parallel_blocks_ctr      — All blocks parallelizable = ceil(data/block)
  security_margin_bits     — Margin = key - reduction
"""

from std.math import log as _log


# ── helpers ──────────────────────────────────────────────────────────────────


fn _ceil_div(a: Int, b: Int) -> Int:
    """Integer ceiling division."""
    if b == 0:
        return 0
    return (a + b - 1) // b


# ── public API ───────────────────────────────────────────────────────────────


fn ecb_block_count(data_length: Int, block_size: Int) -> Int:
    """Number of blocks needed in ECB mode = ceil(data_length / block_size)."""
    if block_size <= 0:
        return 0
    return _ceil_div(data_length, block_size)


fn cbc_iv_required() -> Bool:
    """CBC mode always requires an initialisation vector. Returns True."""
    return True


fn ctr_nonce_size(block_size: Int) -> Int:
    """CTR nonce size = block_size / 2 (bytes)."""
    if block_size <= 0:
        return 0
    return block_size // 2


fn gcm_tag_length_default() -> Int:
    """Default GCM authentication tag length = 16 bytes (128 bits)."""
    return 16


fn padding_pkcs7_bytes(data_length: Int, block_size: Int) -> Int:
    """PKCS#7 padding bytes needed = block_size - (data_length % block_size).
    If data_length is already a multiple of block_size, a full padding block is added.
    """
    if block_size <= 0:
        return 0
    var rem = data_length % block_size
    return block_size - rem


fn ciphertext_length_cbc(plaintext_length: Int, block_size: Int) -> Int:
    """Ciphertext length for CBC = (ceil(PT/block) + 1) * block.
    The extra block accounts for the prepended IV.
    """
    if block_size <= 0:
        return 0
    var padded_blocks = _ceil_div(plaintext_length, block_size)
    # PKCS7 adds a full block when plaintext is already aligned
    if plaintext_length % block_size == 0 and plaintext_length > 0:
        padded_blocks += 1
    return (padded_blocks + 1) * block_size


fn ciphertext_length_gcm(plaintext_length: Int, tag_length: Int) -> Int:
    """Ciphertext length for GCM = plaintext_length + tag_length."""
    return plaintext_length + tag_length


fn aead_overhead(tag_size: Int, nonce_size: Int) -> Int:
    """AEAD overhead in bytes = tag_size + nonce_size."""
    return tag_size + nonce_size


fn key_schedule_rounds_aes(key_bits: Int) -> Int:
    """AES key schedule rounds: 128→10, 192→12, 256→14. Returns 0 for invalid."""
    if key_bits == 128:
        return 10
    if key_bits == 192:
        return 12
    if key_bits == 256:
        return 14
    return 0


fn throughput_estimate(block_size: Int, blocks_per_sec: Float64) -> Float64:
    """Estimated throughput in MB/s = block_size * blocks_per_sec / 1e6."""
    return Float64(block_size) * blocks_per_sec / 1e6


fn parallel_blocks_ctr(data_length: Int, block_size: Int) -> Int:
    """All CTR blocks are independently parallelizable = ceil(data/block)."""
    if block_size <= 0:
        return 0
    return _ceil_div(data_length, block_size)


fn security_margin_bits(key_bits: Int, known_attack_reduction: Int) -> Int:
    """Effective security margin = key_bits - known_attack_reduction."""
    return key_bits - known_attack_reduction
