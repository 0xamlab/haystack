"""
chacha20.mojo — ChaCha20 Stream Cipher Core. Zero Python imports.

Replaces cryptography.hazmat with pure Mojo implementations of ChaCha20
quarter round, block generation, and XOR-based encrypt/decrypt.

Public API:
  rotl32             — 32-bit left rotation
  quarter_round      — ChaCha20 quarter round on state words
  chacha20_init_state — Initialize 16-word state
  add_states         — Element-wise addition mod 2^32
  xor_states         — Element-wise XOR
  chacha20_block     — Generate one 64-byte keystream block
  chacha20_encrypt   — Encrypt plaintext bytes via XOR with keystream
  chacha20_decrypt   — Decrypt (same as encrypt for XOR cipher)
"""


# ── Constants ────────────────────────────────────────────────────────────────


comptime MASK32: Int = 0xFFFFFFFF
comptime CONST0: Int = 0x61707865
comptime CONST1: Int = 0x3320646E
comptime CONST2: Int = 0x79622D32
comptime CONST3: Int = 0x6B206574


# ── rotl32 ───────────────────────────────────────────────────────────────────


fn rotl32(value: Int, shift: Int) -> Int:
    """32-bit left rotation."""
    var v = value & MASK32
    var s = shift & 31
    return ((v << s) | (v >> (32 - s))) & MASK32


# ── quarter_round ────────────────────────────────────────────────────────────


fn quarter_round(mut state: List[Int], a: Int, b: Int, c: Int, d: Int):
    """ChaCha20 quarter round on 32-bit state words."""
    state[a] = (state[a] + state[b]) & MASK32
    state[d] = rotl32(state[d] ^ state[a], 16)
    state[c] = (state[c] + state[d]) & MASK32
    state[b] = rotl32(state[b] ^ state[c], 12)
    state[a] = (state[a] + state[b]) & MASK32
    state[d] = rotl32(state[d] ^ state[a], 8)
    state[c] = (state[c] + state[d]) & MASK32
    state[b] = rotl32(state[b] ^ state[c], 7)


# ── chacha20_init_state ──────────────────────────────────────────────────────


fn chacha20_init_state(key: List[Int], counter: Int, nonce: List[Int]) -> List[Int]:
    """Initialize 16-word state with constants, key, counter, nonce.
    key = 8 words, nonce = 3 words."""
    # Fixed-size readers below: key must supply 8 words, nonce 3.
    if len(key) < 8 or len(nonce) < 3:
        return List[Int]()
    var state = List[Int](capacity=16)
    state.append(CONST0)
    state.append(CONST1)
    state.append(CONST2)
    state.append(CONST3)
    for i in range(8):
        state.append(key[i] & MASK32)
    state.append(counter & MASK32)
    for i in range(3):
        state.append(nonce[i] & MASK32)
    return state^


# ── add_states ───────────────────────────────────────────────────────────────


fn add_states(a: List[Int], b: List[Int]) -> List[Int]:
    """Element-wise addition mod 2^32."""
    var n = len(a)
    if len(b) != n:
        return List[Int]()
    var result = List[Int](capacity=n)
    for i in range(n):
        result.append((a[i] + b[i]) & MASK32)
    return result^


# ── xor_states ───────────────────────────────────────────────────────────────


fn xor_states(a: List[Int], b: List[Int]) -> List[Int]:
    """Element-wise XOR."""
    var n = len(a)
    if len(b) != n:
        return List[Int]()
    var result = List[Int](capacity=n)
    for i in range(n):
        result.append((a[i] ^ b[i]) & MASK32)
    return result^


# ── chacha20_block ───────────────────────────────────────────────────────────


fn chacha20_block(key: List[Int], counter: Int, nonce: List[Int]) -> List[Int]:
    """Generate one 64-byte keystream block. key=8 words, nonce=3 words.
    Returns 16 words of keystream."""
    if len(key) < 8 or len(nonce) < 3:
        return List[Int]()
    var initial = chacha20_init_state(key, counter, nonce)
    var state = List[Int](capacity=16)
    for i in range(16):
        state.append(initial[i])

    for round_i in range(10):
        quarter_round(state, 0, 4, 8, 12)
        quarter_round(state, 1, 5, 9, 13)
        quarter_round(state, 2, 6, 10, 14)
        quarter_round(state, 3, 7, 11, 15)
        quarter_round(state, 0, 5, 10, 15)
        quarter_round(state, 1, 6, 11, 12)
        quarter_round(state, 2, 7, 8, 13)
        quarter_round(state, 3, 4, 9, 14)

    return add_states(state, initial)


# ── _words_to_bytes ──────────────────────────────────────────────────────────


fn _words_to_bytes(words: List[Int]) -> List[Int]:
    """Convert list of 32-bit words to list of bytes (little-endian)."""
    var result = List[Int](capacity=len(words) * 4)
    for i in range(len(words)):
        var w = words[i] & MASK32
        result.append(w & 0xFF)
        result.append((w >> 8) & 0xFF)
        result.append((w >> 16) & 0xFF)
        result.append((w >> 24) & 0xFF)
    return result^


# ── chacha20_encrypt ─────────────────────────────────────────────────────────


fn chacha20_encrypt(plaintext: List[Int], key: List[Int], nonce: List[Int]) -> List[Int]:
    """Encrypt plaintext bytes by XOR with keystream."""
    # Bad key/nonce would yield empty blocks and spin the loop below forever.
    if len(key) < 8 or len(nonce) < 3:
        return List[Int]()
    var n = len(plaintext)
    var result = List[Int](capacity=n)
    var counter = 0
    var pos = 0

    while pos < n:
        var block = chacha20_block(key, counter, nonce)
        var keystream = _words_to_bytes(block^)
        var ks_len = len(keystream)
        for i in range(ks_len):
            if pos >= n:
                break
            result.append((plaintext[pos] ^ keystream[i]) & 0xFF)
            pos += 1
        counter += 1

    return result^


# ── chacha20_decrypt ─────────────────────────────────────────────────────────


fn chacha20_decrypt(ciphertext: List[Int], key: List[Int], nonce: List[Int]) -> List[Int]:
    """Decrypt (same as encrypt for XOR cipher)."""
    return chacha20_encrypt(ciphertext, key, nonce)
