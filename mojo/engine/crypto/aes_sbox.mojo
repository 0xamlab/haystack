"""
aes_sbox.mojo — AES S-Box and core transformations. Zero Python imports.

Replaces the cryptography library's AES core with pure Mojo implementations
of the S-Box lookup, SubBytes, ShiftRows, and AddRoundKey operations.

Public API:
  aes_sbox       — Forward S-Box lookup
  aes_inv_sbox   — Inverse S-Box lookup
  sub_bytes      — Apply S-Box to 16-byte state
  inv_sub_bytes  — Apply inverse S-Box to 16-byte state
  shift_rows     — AES ShiftRows on 4×4 state
  inv_shift_rows — Inverse ShiftRows
  xor_bytes      — XOR two byte lists element-wise
  add_round_key  — XOR state with round key
"""


# ── AES Forward S-Box (256 entries) ──────────────────────────────────────────


fn _build_sbox() -> List[Int]:
    """Build the standard AES forward S-Box table."""
    var s = List[Int](capacity=256)
    s.append(0x63); s.append(0x7C); s.append(0x77); s.append(0x7B)
    s.append(0xF2); s.append(0x6B); s.append(0x6F); s.append(0xC5)
    s.append(0x30); s.append(0x01); s.append(0x67); s.append(0x2B)
    s.append(0xFE); s.append(0xD7); s.append(0xAB); s.append(0x76)
    s.append(0xCA); s.append(0x82); s.append(0xC9); s.append(0x7D)
    s.append(0xFA); s.append(0x59); s.append(0x47); s.append(0xF0)
    s.append(0xAD); s.append(0xD4); s.append(0xA2); s.append(0xAF)
    s.append(0x9C); s.append(0xA4); s.append(0x72); s.append(0xC0)
    s.append(0xB7); s.append(0xFD); s.append(0x93); s.append(0x26)
    s.append(0x36); s.append(0x3F); s.append(0xF7); s.append(0xCC)
    s.append(0x34); s.append(0xA5); s.append(0xE5); s.append(0xF1)
    s.append(0x71); s.append(0xD8); s.append(0x31); s.append(0x15)
    s.append(0x04); s.append(0xC7); s.append(0x23); s.append(0xC3)
    s.append(0x18); s.append(0x96); s.append(0x05); s.append(0x9A)
    s.append(0x07); s.append(0x12); s.append(0x80); s.append(0xE2)
    s.append(0xEB); s.append(0x27); s.append(0xB2); s.append(0x75)
    s.append(0x09); s.append(0x83); s.append(0x2C); s.append(0x1A)
    s.append(0x1B); s.append(0x6E); s.append(0x5A); s.append(0xA0)
    s.append(0x52); s.append(0x3B); s.append(0xD6); s.append(0xB3)
    s.append(0x29); s.append(0xE3); s.append(0x2F); s.append(0x84)
    s.append(0x53); s.append(0xD1); s.append(0x00); s.append(0xED)
    s.append(0x20); s.append(0xFC); s.append(0xB1); s.append(0x5B)
    s.append(0x6A); s.append(0xCB); s.append(0xBE); s.append(0x39)
    s.append(0x4A); s.append(0x4C); s.append(0x58); s.append(0xCF)
    s.append(0xD0); s.append(0xEF); s.append(0xAA); s.append(0xFB)
    s.append(0x43); s.append(0x4D); s.append(0x33); s.append(0x85)
    s.append(0x45); s.append(0xF9); s.append(0x02); s.append(0x7F)
    s.append(0x50); s.append(0x3C); s.append(0x9F); s.append(0xA8)
    s.append(0x51); s.append(0xA3); s.append(0x40); s.append(0x8F)
    s.append(0x92); s.append(0x9D); s.append(0x38); s.append(0xF5)
    s.append(0xBC); s.append(0xB6); s.append(0xDA); s.append(0x21)
    s.append(0x10); s.append(0xFF); s.append(0xF3); s.append(0xD2)
    s.append(0xCD); s.append(0x0C); s.append(0x13); s.append(0xEC)
    s.append(0x5F); s.append(0x97); s.append(0x44); s.append(0x17)
    s.append(0xC4); s.append(0xA7); s.append(0x7E); s.append(0x3D)
    s.append(0x64); s.append(0x5D); s.append(0x19); s.append(0x73)
    s.append(0x60); s.append(0x81); s.append(0x4F); s.append(0xDC)
    s.append(0x22); s.append(0x2A); s.append(0x90); s.append(0x88)
    s.append(0x46); s.append(0xEE); s.append(0xB8); s.append(0x14)
    s.append(0xDE); s.append(0x5E); s.append(0x0B); s.append(0xDB)
    s.append(0xE0); s.append(0x32); s.append(0x3A); s.append(0x0A)
    s.append(0x49); s.append(0x06); s.append(0x24); s.append(0x5C)
    s.append(0xC2); s.append(0xD3); s.append(0xAC); s.append(0x62)
    s.append(0x91); s.append(0x95); s.append(0xE4); s.append(0x79)
    s.append(0xE7); s.append(0xC8); s.append(0x37); s.append(0x6D)
    s.append(0x8D); s.append(0xD5); s.append(0x4E); s.append(0xA9)
    s.append(0x6C); s.append(0x56); s.append(0xF4); s.append(0xEA)
    s.append(0x65); s.append(0x7A); s.append(0xAE); s.append(0x08)
    s.append(0xBA); s.append(0x78); s.append(0x25); s.append(0x2E)
    s.append(0x1C); s.append(0xA6); s.append(0xB4); s.append(0xC6)
    s.append(0xE8); s.append(0xDD); s.append(0x74); s.append(0x1F)
    s.append(0x4B); s.append(0xBD); s.append(0x8B); s.append(0x8A)
    s.append(0x70); s.append(0x3E); s.append(0xB5); s.append(0x66)
    s.append(0x48); s.append(0x03); s.append(0xF6); s.append(0x0E)
    s.append(0x61); s.append(0x35); s.append(0x57); s.append(0xB9)
    s.append(0x86); s.append(0xC1); s.append(0x1D); s.append(0x9E)
    s.append(0xE1); s.append(0xF8); s.append(0x98); s.append(0x11)
    s.append(0x69); s.append(0xD9); s.append(0x8E); s.append(0x94)
    s.append(0x9B); s.append(0x1E); s.append(0x87); s.append(0xE9)
    s.append(0xCE); s.append(0x55); s.append(0x28); s.append(0xDF)
    s.append(0x8C); s.append(0xA1); s.append(0x89); s.append(0x0D)
    s.append(0xBF); s.append(0xE6); s.append(0x42); s.append(0x68)
    s.append(0x41); s.append(0x99); s.append(0x2D); s.append(0x0F)
    s.append(0xB0); s.append(0x54); s.append(0xBB); s.append(0x16)
    return s^


fn _build_inv_sbox() -> List[Int]:
    """Build the AES inverse S-Box by inverting the forward S-Box."""
    var fwd = _build_sbox()
    var inv = List[Int](capacity=256)
    for _ in range(256):
        inv.append(0)
    for i in range(256):
        inv[fwd[i]] = i
    return inv^


# ── Public API ───────────────────────────────────────────────────────────────


fn aes_sbox(byte: Int) -> Int:
    """AES forward S-Box lookup for a single byte (0–255)."""
    var table = _build_sbox()
    var idx = byte & 0xFF
    return table[idx]


fn aes_inv_sbox(byte: Int) -> Int:
    """AES inverse S-Box lookup for a single byte (0–255)."""
    var table = _build_inv_sbox()
    var idx = byte & 0xFF
    return table[idx]


fn sub_bytes(state: List[Int]) -> List[Int]:
    """Apply forward S-Box to each byte of a 16-byte state."""
    var table = _build_sbox()
    var out = List[Int](capacity=len(state))
    for i in range(len(state)):
        out.append(table[state[i] & 0xFF])
    return out^


fn inv_sub_bytes(state: List[Int]) -> List[Int]:
    """Apply inverse S-Box to each byte of a 16-byte state."""
    var table = _build_inv_sbox()
    var out = List[Int](capacity=len(state))
    for i in range(len(state)):
        out.append(table[state[i] & 0xFF])
    return out^


fn shift_rows(state: List[Int]) -> List[Int]:
    """AES ShiftRows on 4×4 state (row-major, 16 bytes).

    Row 0: no shift
    Row 1: shift left by 1
    Row 2: shift left by 2
    Row 3: shift left by 3
    """
    var out = List[Int](capacity=16)
    for _ in range(16):
        out.append(0)
    # Row 0: indices 0,1,2,3 → no shift
    out[0] = state[0]; out[1] = state[1]; out[2] = state[2]; out[3] = state[3]
    # Row 1: indices 4,5,6,7 → shift left by 1
    out[4] = state[5]; out[5] = state[6]; out[6] = state[7]; out[7] = state[4]
    # Row 2: indices 8,9,10,11 → shift left by 2
    out[8] = state[10]; out[9] = state[11]; out[10] = state[8]; out[11] = state[9]
    # Row 3: indices 12,13,14,15 → shift left by 3
    out[12] = state[15]; out[13] = state[12]; out[14] = state[13]; out[15] = state[14]
    return out^


fn inv_shift_rows(state: List[Int]) -> List[Int]:
    """Inverse ShiftRows on 4×4 state (row-major, 16 bytes).

    Row 0: no shift
    Row 1: shift right by 1
    Row 2: shift right by 2
    Row 3: shift right by 3
    """
    var out = List[Int](capacity=16)
    for _ in range(16):
        out.append(0)
    # Row 0: no shift
    out[0] = state[0]; out[1] = state[1]; out[2] = state[2]; out[3] = state[3]
    # Row 1: shift right by 1 (undo left by 1)
    out[4] = state[7]; out[5] = state[4]; out[6] = state[5]; out[7] = state[6]
    # Row 2: shift right by 2
    out[8] = state[10]; out[9] = state[11]; out[10] = state[8]; out[11] = state[9]
    # Row 3: shift right by 3 (= shift left by 1)
    out[12] = state[13]; out[13] = state[14]; out[14] = state[15]; out[15] = state[12]
    return out^


fn xor_bytes(a: List[Int], b: List[Int]) -> List[Int]:
    """XOR two byte lists element-wise."""
    var n = len(a)
    if len(b) < n:
        n = len(b)
    var out = List[Int](capacity=n)
    for i in range(n):
        out.append((a[i] ^ b[i]) & 0xFF)
    return out^


fn add_round_key(state: List[Int], key: List[Int]) -> List[Int]:
    """XOR state with round key (same as xor_bytes for AES)."""
    return xor_bytes(state, key)
