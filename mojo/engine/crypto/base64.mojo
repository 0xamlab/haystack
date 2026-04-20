"""
base64.mojo — RFC 4648 Base64 encoding/decoding. Zero Python imports.

Provides standard and URL-safe Base64 encoding/decoding using only
byte manipulation. No Python imports.

Public API:
  b64_encode(data)       — standard Base64 encode with '=' padding
  b64_decode(encoded)    — standard Base64 decode
  b64_url_encode(data)   — URL-safe Base64 encode (no padding)
  b64_url_decode(encoded) — URL-safe Base64 decode
"""


# ── Base64 alphabet ──────────────────────────────────────────────────────────

comptime _B64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


# ── Encoding helpers ─────────────────────────────────────────────────────────

@always_inline
fn _b64_char_at(idx: Int) -> String:
    """Return the Base64 character at the given index (0–63)."""
    return chr(Int(_B64_ALPHABET.as_bytes()[idx]))


@always_inline
fn _b64_decode_byte(b: UInt8) -> Int:
    """Decode a single Base64 byte to its 6-bit value. Returns -1 on invalid."""
    var o = Int(b)
    if o >= 65 and o <= 90:    # A-Z
        return o - 65
    if o >= 97 and o <= 122:   # a-z
        return o - 71
    if o >= 48 and o <= 57:    # 0-9
        return o + 4
    if o == 43:                # +
        return 62
    if o == 47:                # /
        return 63
    if o == 45:                # - (URL-safe +)
        return 62
    if o == 95:                # _ (URL-safe /)
        return 63
    return -1


# ── Standard Base64 ─────────────────────────────────────────────────────────

fn b64_encode(data: String) -> String:
    """Encode a string to Base64 (RFC 4648). Returns the encoded string with '=' padding."""
    var n = len(data)
    if n == 0:
        return ""

    var result = String("")
    var bspan = data.as_bytes()
    var i = 0

    # Process 3 bytes at a time → 4 Base64 chars
    while i + 3 <= n:
        var b0 = Int(bspan[i])
        var b1 = Int(bspan[i + 1])
        var b2 = Int(bspan[i + 2])

        result += _b64_char_at((b0 >> 2) & 0x3F)
        result += _b64_char_at(((b0 & 0x03) << 4) | ((b1 >> 4) & 0x0F))
        result += _b64_char_at(((b1 & 0x0F) << 2) | ((b2 >> 6) & 0x03))
        result += _b64_char_at(b2 & 0x3F)
        i += 3

    # Handle remaining 1 or 2 bytes with padding
    var remaining = n - i
    if remaining == 1:
        var b0 = Int(bspan[i])
        result += _b64_char_at((b0 >> 2) & 0x3F)
        result += _b64_char_at((b0 & 0x03) << 4)
        result += "=="
    elif remaining == 2:
        var b0 = Int(bspan[i])
        var b1 = Int(bspan[i + 1])
        result += _b64_char_at((b0 >> 2) & 0x3F)
        result += _b64_char_at(((b0 & 0x03) << 4) | ((b1 >> 4) & 0x0F))
        result += _b64_char_at((b1 & 0x0F) << 2)
        result += "="

    return result


fn b64_decode(encoded: String) -> String:
    """Decode a Base64 string (RFC 4648). Returns the decoded string."""
    var n = len(encoded)
    if n == 0:
        return ""

    var enc_bytes = encoded.as_bytes()

    # Strip trailing padding
    var end = n
    while end > 0 and enc_bytes[end - 1] == UInt8(61):  # '='
        end -= 1

    var result = String("")
    var buf = 0
    var bits = 0

    for i in range(end):
        var val = _b64_decode_byte(enc_bytes[i])
        if val < 0:
            continue  # skip whitespace / invalid chars
        buf = (buf << 6) | val
        bits += 6
        if bits >= 8:
            bits -= 8
            result += chr((buf >> bits) & 0xFF)

    return result


# ── URL-safe Base64 ──────────────────────────────────────────────────────────

fn b64_url_encode(data: String) -> String:
    """URL-safe Base64 encode (+ → -, / → _, no padding). RFC 4648 §5."""
    var standard = b64_encode(data)
    var result = String("")
    var sb = standard.as_bytes()
    for i in range(len(standard)):
        var b = sb[i]
        if b == UInt8(43):       # '+'
            result += "-"
        elif b == UInt8(47):     # '/'
            result += "_"
        elif b == UInt8(61):     # '='
            pass  # strip padding
        else:
            result += chr(Int(b))
    return result


fn b64_url_decode(encoded: String) -> String:
    """URL-safe Base64 decode. RFC 4648 §5."""
    # Convert URL-safe chars back to standard, then decode
    var standard = String("")
    var eb = encoded.as_bytes()
    for i in range(len(encoded)):
        var b = eb[i]
        if b == UInt8(45):       # '-'
            standard += "+"
        elif b == UInt8(95):     # '_'
            standard += "/"
        else:
            standard += chr(Int(b))

    # Add padding if needed
    var pad = len(standard) % 4
    if pad == 2:
        standard += "=="
    elif pad == 3:
        standard += "="

    return b64_decode(standard)
