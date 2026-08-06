"""
Pure Mojo SHA-256 (FIPS 180-4). Zero Python imports.

Replaces the hashlib.sha256() call in output.mojo with a native Mojo
implementation.  Called once per request — not in the hot simulation loop.

Public API:
  sha256_hex(data: String) -> String       — one-shot convenience function
  SHA256 struct with update() / hexdigest() — incremental API
"""


# ── Core bitwise helpers (FIPS 180-4 §4.1.2) ─────────────────────────────────

@always_inline
def _rotr(x: UInt32, n: Int) -> UInt32:
    """Right-rotate x by n bits."""
    return (x >> UInt32(n)) | (x << UInt32(32 - n))


@always_inline
def _ch(x: UInt32, y: UInt32, z: UInt32) -> UInt32:
    """Ch(x,y,z) = (x AND y) XOR (NOT x AND z)."""
    return (x & y) ^ (~x & z)


@always_inline
def _maj(x: UInt32, y: UInt32, z: UInt32) -> UInt32:
    """Maj(x,y,z) = (x AND y) XOR (x AND z) XOR (y AND z)."""
    return (x & y) ^ (x & z) ^ (y & z)


@always_inline
def _big_sigma0(x: UInt32) -> UInt32:
    """Σ0(x) = ROTR²(x) XOR ROTR¹³(x) XOR ROTR²²(x)."""
    return _rotr(x, 2) ^ _rotr(x, 13) ^ _rotr(x, 22)


@always_inline
def _big_sigma1(x: UInt32) -> UInt32:
    """Σ1(x) = ROTR⁶(x) XOR ROTR¹¹(x) XOR ROTR²⁵(x)."""
    return _rotr(x, 6) ^ _rotr(x, 11) ^ _rotr(x, 25)


@always_inline
def _small_sigma0(x: UInt32) -> UInt32:
    """σ0(x) = ROTR⁷(x) XOR ROTR¹⁸(x) XOR SHR³(x)."""
    return _rotr(x, 7) ^ _rotr(x, 18) ^ (x >> UInt32(3))


@always_inline
def _small_sigma1(x: UInt32) -> UInt32:
    """σ1(x) = ROTR¹⁷(x) XOR ROTR¹⁹(x) XOR SHR¹⁰(x)."""
    return _rotr(x, 17) ^ _rotr(x, 19) ^ (x >> UInt32(10))


# ── Hex encoding helpers ──────────────────────────────────────────────────────

@always_inline
def _nibble_hex(n: Int) -> String:
    """Convert a 4-bit nibble (0-15) to a single lowercase hex character."""
    if n < 10:
        return chr(48 + n)   # ord("0") = 48
    return chr(87 + n)       # ord("a") - 10 = 87


def _u32_hex(v: UInt32) -> String:
    """Convert a UInt32 to an 8-character lowercase hex string (big-endian)."""
    var s = String("")
    for i in range(8):
        var shift = UInt32((7 - i) * 4)
        s += _nibble_hex(Int((v >> shift) & 0xF))
    return s


# ── Round constants (FIPS 180-4 §4.2.2) ──────────────────────────────────────
# First 32 bits of the fractional parts of the cube roots of the first 64 primes.

def _k_constants() -> List[UInt32]:
    var k = List[UInt32](capacity=64)
    k.append(0x428a2f98); k.append(0x71374491); k.append(0xb5c0fbcf); k.append(0xe9b5dba5)
    k.append(0x3956c25b); k.append(0x59f111f1); k.append(0x923f82a4); k.append(0xab1c5ed5)
    k.append(0xd807aa98); k.append(0x12835b01); k.append(0x243185be); k.append(0x550c7dc3)
    k.append(0x72be5d74); k.append(0x80deb1fe); k.append(0x9bdc06a7); k.append(0xc19bf174)
    k.append(0xe49b69c1); k.append(0xefbe4786); k.append(0x0fc19dc6); k.append(0x240ca1cc)
    k.append(0x2de92c6f); k.append(0x4a7484aa); k.append(0x5cb0a9dc); k.append(0x76f988da)
    k.append(0x983e5152); k.append(0xa831c66d); k.append(0xb00327c8); k.append(0xbf597fc7)
    k.append(0xc6e00bf3); k.append(0xd5a79147); k.append(0x06ca6351); k.append(0x14292967)
    k.append(0x27b70a85); k.append(0x2e1b2138); k.append(0x4d2c6dfc); k.append(0x53380d13)
    k.append(0x650a7354); k.append(0x766a0abb); k.append(0x81c2c92e); k.append(0x92722c85)
    k.append(0xa2bfe8a1); k.append(0xa81a664b); k.append(0xc24b8b70); k.append(0xc76c51a3)
    k.append(0xd192e819); k.append(0xd6990624); k.append(0xf40e3585); k.append(0x106aa070)
    k.append(0x19a4c116); k.append(0x1e376c08); k.append(0x2748774c); k.append(0x34b0bcb5)
    k.append(0x391c0cb3); k.append(0x4ed8aa4a); k.append(0x5b9cca4f); k.append(0x682e6ff3)
    k.append(0x748f82ee); k.append(0x78a5636f); k.append(0x84c87814); k.append(0x8cc70208)
    k.append(0x90befffa); k.append(0xa4506ceb); k.append(0xbef9a3f7); k.append(0xc67178f2)
    return k^


# ── Block compression (FIPS 180-4 §6.2.2) ────────────────────────────────────

def _compress(block: List[UInt8], offset: Int, mut h: List[UInt32]):
    """
    Process one 512-bit (64-byte) block starting at `offset` in `block`.
    Mutates the 8-word hash state `h` in place.
    """
    var k = _k_constants()

    # 1. Prepare the message schedule W[0..63]
    var w = List[UInt32](capacity=64)
    for i in range(16):
        var base = offset + i * 4
        var word = (UInt32(block[base]) << UInt32(24)) | (UInt32(block[base + 1]) << UInt32(16)) | (UInt32(block[base + 2]) << UInt32(8)) | UInt32(block[base + 3])
        w.append(word)
    for i in range(16, 64):
        var s0 = _small_sigma0(w[i - 15])
        var s1 = _small_sigma1(w[i - 2])
        w.append(w[i - 16] + s0 + w[i - 7] + s1)

    # 2. Initialize working variables
    var a = h[0]; var b = h[1]; var c = h[2]; var d = h[3]
    var e = h[4]; var f = h[5]; var g = h[6]; var hh = h[7]

    # 3. Compression — 64 rounds
    for i in range(64):
        var t1 = hh + _big_sigma1(e) + _ch(e, f, g) + k[i] + w[i]
        var t2 = _big_sigma0(a) + _maj(a, b, c)
        hh = g; g = f; f = e; e = d + t1
        d = c; c = b; b = a; a = t1 + t2

    # 4. Update hash state
    h[0] += a; h[1] += b; h[2] += c; h[3] += d
    h[4] += e; h[5] += f; h[6] += g; h[7] += hh


# ── SHA256 struct — incremental API ───────────────────────────────────────────

struct SHA256:
    """
    Incremental SHA-256 hasher.  Call update() one or more times, then
    hexdigest() to retrieve the 64-char lowercase hex digest.
    """
    var _h: List[UInt32]
    var _buf: List[UInt8]
    var _total: Int

    def __init__(out self):
        """Initialise with the FIPS 180-4 initial hash values (H0–H7)."""
        self._h = List[UInt32](capacity=8)
        self._h.append(0x6a09e667)
        self._h.append(0xbb67ae85)
        self._h.append(0x3c6ef372)
        self._h.append(0xa54ff53a)
        self._h.append(0x510e527f)
        self._h.append(0x9b05688c)
        self._h.append(0x1f83d9ab)
        self._h.append(0x5be0cd19)
        self._buf = List[UInt8](capacity=64)
        self._total = 0

    def update(mut self, data: String):
        """Feed data into the hasher.  May be called multiple times."""
        var bspan = data.as_bytes()
        var data_len = len(data)
        self._total += data_len
        var pos = 0

        # Try to complete a partial buffered block first
        if len(self._buf) > 0:
            var space = 64 - len(self._buf)
            var to_copy = min(space, data_len)
            for i in range(to_copy):
                self._buf.append(UInt8(bspan[i]))
            pos = to_copy
            if len(self._buf) == 64:
                _compress(self._buf, 0, self._h)
                self._buf.clear()

        # Process complete 64-byte blocks directly
        while pos + 64 <= data_len:
            var block = List[UInt8](capacity=64)
            for i in range(64):
                block.append(UInt8(bspan[pos + i]))
            _compress(block, 0, self._h)
            pos += 64

        # Buffer any remaining bytes
        while pos < data_len:
            self._buf.append(UInt8(bspan[pos]))
            pos += 1

    def hexdigest(self) -> String:
        """
        Finalise the hash and return the 64-character lowercase hex digest.
        Does NOT mutate self — safe to call multiple times.
        """
        # Copy state so we don't mutate the struct
        var h = List[UInt32](capacity=8)
        for i in range(8):
            h.append(self._h[i])
        var buf = List[UInt8](capacity=128)
        for i in range(len(self._buf)):
            buf.append(self._buf[i])

        # ── Padding (FIPS 180-4 §5.1.1) ──
        var msg_len = self._total
        # Append the 0x80 byte
        buf.append(0x80)
        # Pad with zeros until length ≡ 56 (mod 64)
        while len(buf) % 64 != 56:
            buf.append(0)
        # Append original message length in bits as 64-bit big-endian
        var bit_len = UInt64(msg_len) * 8
        buf.append(UInt8(Int((bit_len >> 56) & 0xFF)))
        buf.append(UInt8(Int((bit_len >> 48) & 0xFF)))
        buf.append(UInt8(Int((bit_len >> 40) & 0xFF)))
        buf.append(UInt8(Int((bit_len >> 32) & 0xFF)))
        buf.append(UInt8(Int((bit_len >> 24) & 0xFF)))
        buf.append(UInt8(Int((bit_len >> 16) & 0xFF)))
        buf.append(UInt8(Int((bit_len >> 8) & 0xFF)))
        buf.append(UInt8(Int(bit_len & 0xFF)))

        # ── Process remaining padded blocks ──
        var off = 0
        while off < len(buf):
            _compress(buf, off, h)
            off += 64

        # ── Produce 64-char hex digest ──
        var out = String("")
        for i in range(8):
            out += _u32_hex(h[i])
        return out


# ── Convenience one-shot API ──────────────────────────────────────────────────

def sha256_hex(data: String) -> String:
    """
    Compute the SHA-256 digest of `data` and return a 64-character
    lowercase hex string.  Pure Mojo — no Python imports.
    """
    var hasher = SHA256()
    hasher.update(data)
    return hasher.hexdigest()
