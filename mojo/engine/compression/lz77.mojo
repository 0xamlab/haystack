"""
lz77.mojo — LZ77 compression algorithm. Zero Python imports.

Replaces basic zlib with pure Mojo implementations for LZ77 sliding-window
compression and decompression with token-based encoding.

Public API:
  LZ77Token            — Token with offset, length, next_char
  lz77_encode          — LZ77 encoding of byte stream
  lz77_decode          — Decode LZ77 tokens back to bytes
  bytes_to_ints        — Convert string to list of byte values
  ints_to_string       — Convert byte values back to string
  compression_ratio    — Approximate compression ratio
  find_longest_match   — Find longest match in sliding window
"""


# ── LZ77Token struct ────────────────────────────────────────────────────────


struct LZ77Token(Copyable, Movable):
    """LZ77 token: (offset, length, next_char).

    offset: distance back in the window to start of match
    length: number of matching bytes
    next_char: next byte value after match (-1 if end of data)
    """

    var offset: Int
    var length: Int
    var next_char: Int

    fn __init__(out self, offset: Int, length: Int, next_char: Int):
        self.offset = offset
        self.length = length
        self.next_char = next_char


# ── String/byte conversion ──────────────────────────────────────────────────


fn bytes_to_ints(s: String) -> List[Int]:
    """Convert string to list of byte values (0-255)."""
    var result = List[Int]()
    var bs = s.as_bytes()
    for i in range(len(bs)):
        result.append(Int(bs[i]))
    return result^


fn ints_to_string(data: List[Int]) -> String:
    """Convert list of byte values back to string."""
    # A value outside the Unicode range has no character; chr() aborts the worker on it
    # (uncatchable), so refuse the whole input with an empty string.
    for i in range(len(data)):
        if data[i] < 0 or data[i] > 0x10FFFF:
            return String("")
    var result = String("")
    for i in range(len(data)):
        result += chr(data[i])
    return result


# ── find_longest_match ──────────────────────────────────────────────────────


fn find_longest_match(
    data: List[Int], pos: Int, window_size: Int, lookahead_size: Int
) -> List[Int]:
    """Find longest match in the sliding window.

    Returns [offset, length] where offset is distance back from pos
    and length is number of matching bytes.
    """
    var best_offset = 0
    var best_length = 0

    var search_start = pos - window_size
    if search_start < 0:
        search_start = 0

    var lookahead_end = pos + lookahead_size
    if lookahead_end > len(data):
        lookahead_end = len(data)

    var max_match = lookahead_end - pos

    var s = search_start
    while s < pos:
        var match_len = 0
        while match_len < max_match and s + match_len < pos + match_len + 1:
            # Allow matching into the lookahead (for repeated patterns)
            var src_idx = s + match_len
            # Wrap around for repeating patterns: if src goes past pos,
            # we use the already-decoded data
            if src_idx >= pos:
                # Use the already matched portion cyclically
                var _ = src_idx - s
                var ref_idx = s + (match_len % (pos - s))
                if ref_idx < len(data) and pos + match_len < len(data) and data[ref_idx] == data[pos + match_len]:
                    match_len += 1
                else:
                    break
            elif pos + match_len < len(data) and data[src_idx] == data[pos + match_len]:
                match_len += 1
            else:
                break

        if match_len > best_length:
            best_length = match_len
            best_offset = pos - s
        s += 1

    var result = List[Int]()
    result.append(best_offset)
    result.append(best_length)
    return result^


# ── lz77_encode ─────────────────────────────────────────────────────────────


fn lz77_encode(
    data: List[Int], window_size: Int = 256, lookahead_size: Int = 16
) -> List[LZ77Token]:
    """LZ77 encoding. data is list of byte values (0-255).

    Returns list of (offset, length, next_char) tokens.
    """
    var tokens = List[LZ77Token]()
    var n = len(data)
    var pos = 0

    while pos < n:
        var found = find_longest_match(data, pos, window_size, lookahead_size)
        var offset = found[0]
        var length = found[1]

        var next_char = -1
        if pos + length < n:
            next_char = data[pos + length]

        tokens.append(LZ77Token(offset, length, next_char))
        pos += length + 1

    return tokens^


# ── lz77_decode ─────────────────────────────────────────────────────────────


fn lz77_decode(tokens: List[LZ77Token]) -> List[Int]:
    """Decode LZ77 tokens back to original byte stream."""
    var result = List[Int]()

    for i in range(len(tokens)):
        var token = tokens[i].copy()
        if token.length > 0 and token.offset > 0:
            var start = len(result) - token.offset
            for j in range(token.length):
                # Handle repeating patterns (offset < length)
                var idx = start + j
                # A back-reference past the start of the stream has no byte to copy; the
                # old `< len(result)` test alone admitted negative idx and the negative
                # subscript aborted the worker.
                if idx >= 0 and idx < len(result):
                    result.append(result[idx])
                else:
                    # Should not happen in valid tokens, but safe fallback
                    result.append(0)
        if token.next_char >= 0:
            result.append(token.next_char)

    return result^


# ── compression_ratio ───────────────────────────────────────────────────────


fn compression_ratio(original_size: Int, n_tokens: Int) -> Float64:
    """Approximate compression ratio: original_size / (n_tokens * 3).

    Each token is approximately 3 values (offset, length, next_char).
    """
    var compressed = n_tokens * 3
    if compressed == 0:
        return 0.0
    return Float64(original_size) / Float64(compressed)
