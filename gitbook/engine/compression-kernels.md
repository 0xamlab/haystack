---
icon: file-zipper
description: Delta, Huffman, LZ77 and run-length encoding as compiled kernels — four classic lossless algorithms, each matched to one specific shape of redundancy.
---

# Compression kernels

Four kernel modules for lossless compression, none of them general-purpose. Delta encoding wins
on sequences that drift slowly instead of jumping around — timestamps, sensor readings, anything
sampled at a roughly constant rate. Huffman coding wins on skewed symbol frequencies — a handful
of values that dominate the stream. LZ77 wins on repeated substrings — the same run of bytes
showing up more than once within a sliding window. Run-length encoding wins on long runs of one
identical value. Pick the wrong one and it does nothing for you; each module ships its own
`compression_ratio` (or `compression_savings`) helper precisely so a caller can measure whether it
helped before committing to it, rather than assuming compression happened because an encoder ran.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("compression.rle", "rle_encode_string", ["AAABBC"])["result"]
# "3A2B1C" — three A's, two B's, one C, as digit-then-character pairs

runtime.execute("compression.delta", "delta_encode", [[100, 102, 101, 105, 110, 108]])["result"]
# [100, 2, -1, 4, 5, -2] — first value as-is, then each successive difference
```

## The modules

| Module | What it does |
| --- | --- |
| `compression.delta` | delta, XOR-delta, zigzag-delta and double-delta encoding for integer and float sequences, plus a `compression_savings` ratio helper |
| `compression.huffman` | frequency counting, Huffman tree construction, code generation, bit-level encode/decode, and `compression_ratio_huffman`/`avg_code_length` |
| `compression.lz77` | sliding-window LZ77 encoding and decoding, byte↔string conversion, and a `compression_ratio` helper |
| `compression.rle` | run-length encoding/decoding at both the byte level and the string level, plus a `compression_ratio` helper |

## Delta encoding: four codings of "how much did it change"

`delta_encode` stores the first value as-is, then each successive difference; `delta_decode`
reverses it with a running sum. On `[100, 102, 101, 105, 110, 108]` that is:

```python
runtime.execute("compression.delta", "delta_encode", [[100, 102, 101, 105, 110, 108]])["result"]
# [100, 2, -1, 4, 5, -2]
```

The other three variants encode that same difference differently:

- **`xor_delta_encode`/`xor_delta_decode`** XOR each value with its predecessor instead of
  subtracting — `[100, 2, -1, 4, 5, -2]`'s XOR equivalent is `[100, 2, 3, 12, 7, 2]`. XOR delta
  is exact under any bit pattern (subtraction can overflow; XOR cannot) and is cheap to reverse
  with a running XOR.
- **`zigzag_delta_encode`/`zigzag_delta_decode`** delta-encodes first, then maps each *signed*
  delta to a small *unsigned* one (`v -> 2v` for `v >= 0`, `v -> -2v-1` for `v < 0`) so a
  downstream varint encoder — which is efficient on small non-negative integers and bad at
  negative ones — never sees a negative number. The same input becomes `[200, 4, 1, 8, 10, 3]`:
  note that the zigzag mapping is applied to the *entire* delta-encoded list, including its
  leading raw value (`100 -> 200`), not just the differences after it.
- **`double_delta_encode`/`double_delta_decode`** delta-encodes twice. On a perfectly linear
  sequence — constant step size, as a fixed sampling rate produces — this collapses almost
  everything to zero. For `[100, 110, 120, 130, 140]` (step 10), the first delta pass gives
  `[100, 10, 10, 10, 10]`; the second pass gives `[100, -90, 0, 0, 0]`. Only the first two
  entries carry information (the starting value and one correction term); every entry after
  that is exactly `0`, because a constant step has a constant first-order delta and *that* has
  a zero second-order delta.

All four encode/decode pairs return an empty list on empty input rather than special-casing it
as an error, and all four satisfy `decode(encode(x)) == x` exactly — there is no lossy step
anywhere in this module, only different arrangements of the same information.

Floats go through the same machinery indirectly: `delta_encode_float(data, precision)` multiplies
each value by `precision`, truncates to `Int`, and delta-encodes the integers; `delta_decode_float`
reverses it and divides back down. With the default `precision = 1000` on `[0.5, 0.6, 0.7, 0.4,
0.3]`, the quantized values are exactly `[500, 600, 700, 400, 300]` (no rounding drift at this
precision) and the delta-encoded result is `[500, 100, 100, -300, -100]`; dequantizing after
decode reproduces `[0.5, 0.6, 0.7, 0.4, 0.3]` exactly. Higher `precision` reduces quantization
error at the cost of larger integers to delta-encode.

`compression_savings(original_bits, compressed_bits)` returns `1 - compressed/original` in
`[0, 1]` — and clamps to `0.0` rather than going negative — in two cases: `original_bits <= 0`
(nothing to compare against) and `compressed_bits > original_bits` (the encoding expanded the
data, which is a real possibility for any of these codecs on adversarial input, and is reported
as "no savings" rather than a negative number a caller would have to remember to floor).

## Huffman coding: shorter codes for more frequent symbols

`frequency_count(data)` counts each distinct value and returns `[[symbol, count], ...]` sorted by
count **ascending** — that ordering is what lets `build_huffman_tree` repeatedly merge the two
lowest-frequency nodes by scanning for the two smallest remaining frequencies, the standard greedy
Huffman construction, without a real priority queue. Tracing the actual algorithm on nine symbols
with frequencies `a`×5, `b`×2, `c`×1, `d`×1 (as integers `0,1,2,3`):

```python
data = [0, 0, 0, 0, 0, 1, 1, 2, 3]   # a x5, b x2, c x1, d x1

freqs = runtime.execute("compression.huffman", "frequency_count", [data])["result"]
# [[2, 1], [3, 1], [1, 2], [0, 5]] — sorted ascending by count: c, d, b, a

bits = runtime.execute("compression.huffman", "huffman_encode", [data])["result"]
# [1,1,1,1,1, 0,0, 0,0,0, 0,1,1] — 15 bits total
```

The tree this builds assigns symbol `0` (`a`, the most frequent) the 1-bit code `1`; symbol `1`
(`b`) the 2-bit code `00`; and symbols `2` and `3` (`c` and `d`, the two least-frequent, tied)
each a 3-bit code (`010` and `011`) — exactly the classic Huffman shape, shorter codes for more
frequent symbols. `avg_code_length(freqs, generate_codes(tree))` on this tree is
`(5·1 + 2·2 + 1·3 + 1·3) / 9 = 1.6667` bits/symbol, and `compression_ratio_huffman(9, 15)` — 9
original one-byte symbols against the 15 encoded bits above — is `9·8 / 15 = 4.8`. Decoding those
15 bits against the same tree reproduces `[0, 0, 0, 0, 0, 1, 1, 2, 3]` exactly: `huffman_decode`
walks the tree from the root on each bit (`0` → left child, `1` → right child) and emits a symbol
whenever it lands on a leaf, resetting to the root each time.

Two edge cases are handled explicitly rather than left to fall out of the general case:

- **Zero symbols** (`build_huffman_tree` on an empty frequency list) returns an empty tree —
  nothing to encode, nothing to build.
- **One distinct symbol** gets a degenerate two-node tree: the symbol as a leaf, plus a root
  pointing at it, so a single-symbol stream still has a valid tree to decode against rather than
  a special "no tree" case propagating downstream. `huffman_decode` recognizes this shape
  (`n <= 2` and the first node already a leaf) and replays that one symbol once per input bit
  instead of walking a tree that has no branch to take.

## LZ77: back-references into a sliding window

An `LZ77Token` is `(offset, length, next_char)`: `offset` is how far back in the already-seen
window a match starts, `length` is how many bytes matched, and `next_char` is the literal byte
that follows the match (`-1` at the end of the stream). `find_longest_match` searches the window
behind the current position for the longest match `lz77_encode` can extend into a token, then
advances past `length + 1` bytes (the match plus the literal that follows it) each step.

Tracing the real algorithm on `"abababab"` (as byte values, `window_size=256`,
`lookahead_size=16`, both defaults): position 0 has nothing behind it to match, so it emits a
zero-length token carrying the literal `'a'`; the same at position 1 for `'b'`; then, from
position 2 onward, everything left in the stream is one repeating `"ab"` pattern:

```
tokens = [(0, 0, 97), (0, 0, 98), (2, 6, -1)]
#          'a' literal   'b' literal   copy 6 bytes from 2 back, no trailing literal
```

That third token's `offset` (`2`) is *shorter than* its `length` (`6`) — it is copying from
bytes that do not exist yet when the copy starts, which only works because `lz77_decode` appends
byte-by-byte as it copies, so each newly-appended byte becomes available as a source for the next
one in the same token. This self-referential case is exactly how LZ77 represents a repeating
pattern with a single token instead of one token per repetition, and it round-trips: decoding
those three tokens reproduces `"abababab"` exactly.

{% hint style="warning" %}
**Two inputs are refused rather than mishandled.** `ints_to_string` checks every value against
the valid Unicode range (`0` to `0x10FFFF`) before converting, and returns an empty string if any
value is out of range — the alternative, calling `chr()` on an invalid codepoint, aborts the
worker process, uncatchably. `lz77_decode` similarly guards a back-reference whose computed index
falls before the start of the buffer built so far: a token that decodes to a negative index (the
kind a corrupted or hand-crafted token stream can produce) gets a `0` byte instead of a negative
list subscript, which is the same class of uncatchable abort.
{% endhint %}

`compression_ratio(original_size, n_tokens)` approximates the ratio as
`original_size / (n_tokens * 3)` — each token costs roughly three values (`offset`, `length`,
`next_char`) — and returns `0.0` when there are no tokens rather than dividing by zero.

## Run-length encoding: byte pairs, string digits, and a 255 ceiling

The byte-level codec (`rle_encode`/`rle_decode`) represents each run as a `(count, value)` pair
of `UInt8`s. Because `count` is itself a byte, a single pair can only represent a run up to 255
long — a run of exactly 300 identical bytes (`0x41` = `'A'`) splits into two pairs rather than
overflowing or truncating:

```
300 x 0x41  ->  [255, 0x41, 45, 0x41]     # 255 + 45 = 300
```

The string-level codec (`rle_encode_string`/`rle_decode_string`) has no such ceiling — it writes
the run length as decimal digits followed by the literal character, so `rle_encode_string`
on `"AAABBC"` produces `"3A2B1C"` and `rle_decode_string("3A2B1C")` reproduces `"AAABBC"` exactly;
a run of 300 would just write `"300A"`. The two codecs are not interchangeable formats — one is a
fixed-width byte pair, the other a variable-width digit string — and mixing an encoder from one
with a decoder from the other does not round-trip.

`compression_ratio(original_size, compressed_size)` is the plain `original_size / compressed_size`
and, like the other three modules' ratio helpers, returns `0.0` instead of dividing by zero when
`compressed_size` is `0`.

## Verification

`mojo/tests/libs/test_compression_delta.mojo`, `test_compression_huffman.mojo`,
`test_compression_lz77.mojo` and `test_compression_rle.mojo` are auto-generated smoke tests: each
calls every public function once against fixture lists shared across the whole `tests/libs`
directory (`[1,2,3,4,5]`, `[0.5,0.6,0.7,0.4,0.3]`, the literal string `"test"`) and asserts the
result is finite and/or a well-formed list — proof that the function runs to completion and
returns a sane shape on one representative input, not a pinned numeric answer. They do not, for
example, assert what `delta_encode([1,2,3,4,5])` actually returns.

The worked numbers on this page instead come from tracing each function's real algorithm in
`mojo/engine/compression/*.mojo` by hand — the same technique
[attention kernels](attention-kernels.md) uses to independently verify `sdpa_forward_flat`'s
softmax weights — and every encode/decode pair above was additionally confirmed to satisfy
`decode(encode(x)) == x` on its worked example, which is the property that actually matters for a
lossless codec: an encoder that produces a plausible-looking but non-invertible result is a worse
failure than one that visibly crashes, because nothing about its output says so.

**Next:** see [Data integrity and encoding](data-integrity-and-encoding.md) for the checksum and
keyed-hash side of encoding, or browse the [engine catalog](catalog.md) for every kernel family.
