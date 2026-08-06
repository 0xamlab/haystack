"""
columnar.dictionary — dictionary encoding for a nullable string column. Zero Python.

What it is
----------
A low-cardinality string column stores every distinct value ONCE in a dictionary and
one integer code per row. `columnar.array.StringArray` keeps one `String` per row, so a
column of 20 000 rows over 5 twenty-byte labels carries those label bytes 20 000 times
instead of 5.

MEASURED, not asserted. `footprint` prices both sides in Arrow's layout and
`test_columnar_dictionary.mojo` prints what it returns:

  20 000 rows / 5 distinct 16-20 byte labels : 466 504 B plain -> 22 620 B coded, 20.6x
   1 000 rows / 1 000 distinct short values  :   7 019 B plain ->  9 019 B coded, 0.78x

The second line is the point of reporting a ratio rather than claiming one. A dictionary
of all-distinct values is the original bytes PLUS a code per row, so it is strictly
larger — this is an encoding, not a compressor, and `footprint` says which way it went
for the column in front of it.

The codes are also what makes a string column groupable by `columnar.hash_index`, which
keys on `Float64`: a code is a small exact integer, so `encode_to_float64_column` hands
the existing aggregate path a key it can hash without formatting a String per row.

Reuse, not a second hash table
------------------------------
The value -> code lookup IS `columnar.hash_index.HashIndex`, the open-addressed
`Float64 -> Int` table already built for group slots. Nothing here re-implements
probing, growth or load factor. Two consequences of borrowing it, both handled rather
than hoped about:

  * its key is a `Float64`, so a string is folded to a 64-bit hash (`string_key`) and
    that hash's BITS are bitcast to a Float64 key. `HashIndex` normalizes its key
    through `normalize_bits`, which collapses every NaN bit pattern to one and `-0.0`
    to `+0.0` — so ~1 string in 2048 (any hash whose exponent field is all ones) shares
    a table entry with every other such string. That is a bucket collision, not a wrong
    answer, because
  * the table entry holds a BUCKET id, not a code. Each bucket owns a chain of codes
    (`bucket_head` / `next_in_bucket`) and membership is decided by full String
    equality. A 64-bit hash collision, and the NaN-pattern collapse above, therefore
    cost one extra comparison and never merge two distinct values — merging is the
    failure that cannot be recovered from once rows have been coded.

`test_columnar_dictionary.mojo` pins two literal witnesses whose keys really are NaN
patterns and asserts they get distinct codes, so the collapse is covered by a test
rather than by this paragraph.

Absence
-------
A null row is NOT the empty string. `""` is a legitimate value that takes a code like
any other; a null row carries `NULL_CODE` (-1) and a cleared validity bit, and its
value is never entered into the dictionary. Collapsing the two is silent — a decoded
column of empty strings looks exactly like a decoded column of nulls to anything that
does not consult validity — so `decode_strings` restores the null as a null and the
suite asserts that specifically.

Refusal
-------
A code that indexes past the dictionary is not a value. Reading `dictionary[code]` for
such a code is an UNCATCHABLE abort that ends the worker process and every resident
dataset with it (rules 1 and 1c of docs/mojo/new-kernel-package-rules.md), so
`decode_strings` validates every code BEFORE it materialises anything and returns
`DICT_CODE_OUT_OF_RANGE` with an EMPTY column — not a partially decoded one, and not a
column with "" where the bad code was.

Count relations, in prose because a block here would reach nothing
-----------------------------------------------------------------
`columnar/` is in `mojo_inventory._SKIP_RUNTIME_DIRS`, so this module is invisible to
both the runtime contract and `build_capability_manifest`. A `@capability` block would
therefore be parsed by nothing and checked by nothing — decoration that reads as
machine-verified. The relations are stated here instead, in the same
`<expr> <= <expr>` style so they stay greppable if the manifest ever covers this
package:

  encode_strings:  n_rows is DERIVED as len(values); there is no count to lie about.
                   A `mask` shorter than `values` leaves those rows absent, matching
                   `array.float64_with_nulls`.
  decode_strings:  n_rows <= len(codes)                        [kernel_validated]
                   bytes_for_bits(n_rows) <= len(validity)     [kernel_validated]
                   0 <= codes[i] < len(dictionary) for every present row
                                                               [kernel_validated]
  footprint:       n_rows <= len(codes)                        [kernel_validated]

Status codes
------------
`columnar/` allocates 300-309 to this module and 310-329 to `columnar/arrow_wire.mojo`
(rule 4e: one integer must not mean two things inside one package).
"""
from std.memory import ArcPointer, bitcast

from columnar.array import Float64Array, StringArray, float64_with_nulls
from columnar.hash_index import HashIndex, hash_bits
from columnar.validity import bytes_for_bits, is_valid, new_all_null, set_valid

# ── status codes: columnar.dictionary owns 300-309 ────────────────────────────
comptime DICT_OK: Int = 300
comptime DICT_ROW_LIMIT_EXCEEDED: Int = 301
comptime DICT_CODES_TOO_SHORT: Int = 302
comptime DICT_VALIDITY_TOO_SHORT: Int = 303
comptime DICT_CODE_OUT_OF_RANGE: Int = 304
comptime DICT_OUTPUT_BUDGET_EXCEEDED: Int = 305
comptime DICT_NO_RATIO: Int = 306
comptime DICT_INVALID_ROW_COUNT: Int = 307

comptime NULL_CODE: Int = -1

# Row ceiling. `encode_strings` derives its row count from the payload, so this only
# binds `decode_strings`, whose row count is a caller-supplied Int.
#
# Allocation arithmetic per decoded row: one `String` (24-byte header here, plus the
# value bytes) and one `Bool`. The value bytes are the part that is not bounded by the
# code array — a dictionary holding one 1 MiB value and 2^24 rows all coding it is a
# ~16 TiB answer from a 128 MiB payload — so the row ceiling is NOT the operative bound
# and `decode_strings` also charges the exact decoded byte total against
# `max_output_bytes` before allocating anything.
comptime MAX_DICT_ROWS: Int = 1 << 24

# 512 MiB, the resident-dataset budget one object is allowed (see
# sparse_numerics.csr.MAX_CSR_DIM's justification). The caller may ask for less; it
# cannot ask for more.
comptime MAX_OUTPUT_BYTES: Int = 512 * 1024 * 1024

# Arrow's utf8 layout carries one offset per value plus a terminator. 4 bytes each, the
# width Arrow's 32-bit `Utf8` type uses — the number `footprint` charges both sides.
comptime OFFSET_BYTES: Int = 4


def _saturating_add(a: Int, b: Int) -> Int:
    """`a + b`, clamped instead of wrapped.

    A wrapped sum compares SMALL, so a budget check on it passes and the allocation it
    was supposed to refuse goes ahead. Same reason `query.plan._saturating_product`
    exists; this is the additive case, over byte totals.
    """
    comptime CEILING: Int = 1 << 62
    if a < 0 or b < 0:
        return 0
    if a > CEILING - b:
        return CEILING
    return a + b


def string_key(value: String) -> UInt64:
    """A 64-bit key for `value`, folded through `hash_index.hash_bits`.

    `hash_bits` is the package's one FNV-1a mixer, over the eight bytes of a UInt64.
    This feeds it the string eight bytes at a time — one FNV round per byte, the same
    cost as hashing the bytes directly — rather than declaring a second hash family in
    the package (rule 3). The byte length is mixed in as the seed so `"a"` and `"a\\0"`
    do not fold to the same chunk sequence.

    Byte-oriented, not code-point oriented: `as_bytes()` is the UTF-8 encoding, so a
    non-ASCII value hashes by its exact bytes and two spellings that differ in any byte
    get different keys.
    """
    var bytes = value.as_bytes()
    var n = len(bytes)
    var acc = UInt64(n)
    var i = 0
    while i + 8 <= n:
        var chunk = UInt64(0)
        for k in range(8):
            chunk = chunk | (UInt64(bytes[i + k]) << UInt64(8 * k))
        acc = hash_bits(chunk ^ acc)
        i += 8
    if i < n:
        var tail = UInt64(0)
        var k = 0
        while i + k < n:
            tail = tail | (UInt64(bytes[i + k]) << UInt64(8 * k))
            k += 1
        acc = hash_bits(tail ^ acc)
    return acc


def key_as_float(key: UInt64) -> Float64:
    """The Float64 `HashIndex` is keyed on. Bit pattern, not a numeric value."""
    return bitcast[DType.float64](key)


struct StringDictionary(Copyable, Movable):
    """Distinct strings in first-appearance order, with O(1) expected lookup.

    `values` is the dictionary. `index` maps a key's bits to a BUCKET id;
    `bucket_head[bucket]` is the first code in that bucket and `next_in_bucket[code]`
    chains the rest, so equality is always decided by comparing whole Strings. See the
    module docstring for why the extra indirection is load-bearing rather than
    defensive.
    """

    var values: List[String]
    var index: HashIndex
    var bucket_head: List[Int]
    var next_in_bucket: List[Int]

    def __init__(out self, initial_capacity: Int = 64):
        self.values = List[String]()
        self.index = HashIndex(initial_capacity)
        self.bucket_head = List[Int]()
        self.next_in_bucket = List[Int]()

    def size(self) -> Int:
        return len(self.values)

    def find(self, value: String) -> Int:
        """`value`'s code, or `NULL_CODE` if it is not in the dictionary. No insert."""
        var bucket = self.index.find(key_as_float(string_key(value)))
        if bucket < 0 or bucket >= len(self.bucket_head):
            return NULL_CODE
        var code = self.bucket_head[bucket]
        while code >= 0:
            if self.values[code] == value:
                return code
            code = self.next_in_bucket[code]
        return NULL_CODE

    def contains(self, value: String) -> Bool:
        return self.find(value) >= 0

    def get_or_add(mut self, value: String) -> Int:
        """`value`'s existing code, or a fresh one after appending it.

        Codes are handed out in first-appearance order, so the dictionary is a
        deterministic function of the column's row order — two runs over the same
        column produce byte-identical codes, which is what lets a test compare them.
        """
        var bucket = self.index.get_or_assign(
            key_as_float(string_key(value)), len(self.bucket_head)
        )
        if bucket == len(self.bucket_head):
            self.bucket_head.append(NULL_CODE)  # a fresh, empty bucket
        var code = self.bucket_head[bucket]
        while code >= 0:
            if self.values[code] == value:
                return code
            code = self.next_in_bucket[code]
        var fresh = len(self.values)
        self.values.append(value)
        self.next_in_bucket.append(self.bucket_head[bucket])
        self.bucket_head[bucket] = fresh
        return fresh

    def value_at(self, code: Int) -> String:
        """The value for `code`, or "" when the code names nothing.

        The "" is NOT a value — it is what a caller gets for asking a question with no
        answer, and the reason `decode_strings` refuses such a code outright instead of
        going through here (rule 4).
        """
        if code < 0 or code >= len(self.values):
            return ""
        return self.values[code]


@fieldwise_init
struct DictEncoded(Copyable, Movable):
    """A coded column: the dictionary, one code per row, and a validity bitmap.

    `codes[i]` is `NULL_CODE` exactly where the validity bit is clear. Both are kept
    because either one alone forces a caller to treat -1 as data.
    """

    var status: Int
    var dictionary: List[String]
    var codes: List[Int]
    var validity: List[UInt8]
    var n_rows: Int
    var n_distinct: Int


def encode_strings(values: List[String], mask: List[Bool]) -> DictEncoded:
    """Dictionary-encode a nullable string column. `n_rows` is `len(values)`.

    The row count is DERIVED from the payload rather than accepted as an argument
    (rule 1c): a caller cannot declare a count the data does not support, so there is
    nothing to bounds-check and nothing to abort on.

    A row is present when `mask[i]` is true; an index past the end of `mask` is absent,
    the same convention `array.float64_with_nulls` uses, so the two cannot disagree
    about a short mask. An absent row contributes NOTHING to the dictionary — that is
    the null/"" distinction, and it is why the dictionary of an all-null column is
    empty rather than holding one "".
    """
    var n_rows = len(values)
    var out = DictEncoded(
        DICT_OK, List[String](), List[Int](), List[UInt8](), 0, 0
    )
    if n_rows > MAX_DICT_ROWS:
        out.status = DICT_ROW_LIMIT_EXCEEDED
        return out^

    var dictionary = StringDictionary(64)
    var codes = List[Int]()
    var validity = new_all_null(n_rows)
    for i in range(n_rows):
        var present = i < len(mask) and mask[i]
        if not present:
            codes.append(NULL_CODE)
            continue
        codes.append(dictionary.get_or_add(values[i]))
        set_valid(validity, i)

    out.dictionary = dictionary.values.copy()
    out.codes = codes^
    out.validity = validity^
    out.n_rows = n_rows
    out.n_distinct = dictionary.size()
    return out^


def encode_all_present(values: List[String]) -> DictEncoded:
    """`encode_strings` for a column with no nulls."""
    var mask = List[Bool]()
    for _ in range(len(values)):
        mask.append(True)
    return encode_strings(values, mask)


@fieldwise_init
struct DictDecoded(Copyable, Movable):
    """A decoded column, or an ABSENT one with the reason in `status`.

    On any refusal `values` and `mask` are EMPTY and `n_rows` is 0. A partially
    decoded column, or one with "" substituted for a code that named nothing, would be
    indistinguishable from a real answer (rule 4).
    """

    var status: Int
    var values: List[String]
    var mask: List[Bool]
    var n_rows: Int


def decoded_bytes_required(
    dictionary: List[String], codes: List[Int], validity: List[UInt8], n_rows: Int
) -> Int:
    """Value bytes `decode_strings` would materialise, saturating on overflow.

    Charged BEFORE anything is allocated, because the output size is a function of the
    dictionary's value lengths, not of the payload: 2^24 rows coding one 1 MiB value is
    a 16 TiB answer to a 128 MiB request.

    `validity` participates so the count is EXACT rather than merely safe. An absent row
    decodes to no bytes whatever its code says, so counting it would over-charge a
    hand-built payload whose absent rows carry in-range codes and refuse a decode that
    was going to be fine — a false refusal is still a wrong answer (rule 4).

    A row whose code names nothing is skipped rather than read: reading past the
    dictionary end here would be the very abort this function exists to prevent.
    `decode_strings` refuses such a row separately, before calling this.
    """
    var total = 0
    var rows = n_rows if n_rows < len(codes) else len(codes)
    for i in range(rows):
        if not is_valid(validity, i):
            continue
        var code = codes[i]
        if code < 0 or code >= len(dictionary):
            continue
        total = _saturating_add(total, len(dictionary[code].as_bytes()))
    return total


def decode_strings(
    dictionary: List[String],
    codes: List[Int],
    validity: List[UInt8],
    n_rows: Int,
    max_output_bytes: Int = MAX_OUTPUT_BYTES,
) -> DictDecoded:
    """Rebuild the original column. Every code is validated before any read.

    Order matters and is deliberate:

      1. shape — `n_rows` against `len(codes)` and `len(validity)`, so no read can be
         past an end;
      2. codes — every PRESENT row's code must be in `[0, len(dictionary))`. An absent
         row's code is ignored, because it names nothing by construction;
      3. budget — the exact decoded byte total against `max_output_bytes`, clamped to
         `MAX_OUTPUT_BYTES`;
      4. only then, materialise.

    A refusal at any step returns an empty column and a status. `max_output_bytes` is a
    parameter rather than only a constant so the refusal is reachable in a test without
    allocating half a gigabyte.
    """
    var out = DictDecoded(DICT_OK, List[String](), List[Bool](), 0)
    if n_rows < 0:
        out.status = DICT_INVALID_ROW_COUNT
        return out^
    if n_rows > MAX_DICT_ROWS:
        out.status = DICT_ROW_LIMIT_EXCEEDED
        return out^
    if n_rows > len(codes):
        out.status = DICT_CODES_TOO_SHORT
        return out^
    if bytes_for_bits(n_rows) > len(validity):
        out.status = DICT_VALIDITY_TOO_SHORT
        return out^

    for i in range(n_rows):
        if not is_valid(validity, i):
            continue
        var code = codes[i]
        if code < 0 or code >= len(dictionary):
            out.status = DICT_CODE_OUT_OF_RANGE
            return out^

    var budget = max_output_bytes
    if budget > MAX_OUTPUT_BYTES:
        budget = MAX_OUTPUT_BYTES
    if budget < 0:
        budget = 0
    if decoded_bytes_required(dictionary, codes, validity, n_rows) > budget:
        out.status = DICT_OUTPUT_BUDGET_EXCEEDED
        return out^

    var values = List[String]()
    var mask = List[Bool]()
    for i in range(n_rows):
        if not is_valid(validity, i):
            values.append("")  # never read: the mask says absent
            mask.append(False)
            continue
        values.append(dictionary[codes[i]])
        mask.append(True)
    out.values = values^
    out.mask = mask^
    out.n_rows = n_rows
    return out^


def decode_to_array(
    dictionary: List[String],
    codes: List[Int],
    validity: List[UInt8],
    n_rows: Int,
    max_output_bytes: Int = MAX_OUTPUT_BYTES,
) -> StringArray:
    """`decode_strings` as a `columnar.array.StringArray`.

    A refusal yields an EMPTY array, which is why the flat form exists too: an empty
    array cannot carry the reason. Callers that need the reason call `decode_strings`.
    """
    var decoded = decode_strings(
        dictionary, codes, validity, n_rows, max_output_bytes
    )
    return strings_to_array(decoded.values, decoded.mask)


def strings_to_array(values: List[String], mask: List[Bool]) -> StringArray:
    """A nullable `StringArray`. `array.string_from_list` is the all-present case."""
    var n = len(values)
    var bitmap = new_all_null(n)
    for i in range(n):
        if i < len(mask) and mask[i]:
            set_valid(bitmap, i)
    var owned = values.copy()
    return StringArray(ArcPointer(owned^), bitmap^, 0, n)


def encode_to_float64_column(values: List[String], mask: List[Bool]) -> Float64Array:
    """The codes as a `Float64Array`, so `hash_index` can group a string column.

    A code is a small non-negative integer, exact in Float64 well past any dictionary
    this package can hold, so the conversion is lossless. A null row stays null rather
    than becoming code 0 — which would silently merge every missing label into whatever
    label happens to hold code 0.
    """
    var encoded = encode_strings(values, mask)
    var numbers = List[Float64]()
    var present = List[Bool]()
    for i in range(encoded.n_rows):
        var code = encoded.codes[i]
        if code == NULL_CODE:
            numbers.append(0.0)
            present.append(False)
        else:
            numbers.append(Float64(code))
            present.append(True)
    return float64_with_nulls(numbers^, present)


def code_byte_width(n_distinct: Int) -> Int:
    """Narrowest integer width that can name `n_distinct` codes: 1, 2, 4 or 8 bytes.

    What a wire format would actually spend per row. `footprint` charges this rather
    than Mojo's 8-byte `Int`, because "dictionary encoding shrinks the column" is a
    claim about the encoding, not about this language's native integer width.
    """
    if n_distinct <= 0:
        return 1
    if n_distinct <= 256:
        return 1
    if n_distinct <= 65536:
        return 2
    if n_distinct <= 4294967296:
        return 4
    return 8


@fieldwise_init
struct DictFootprint(Copyable, Movable):
    """Measured bytes for the plain column and the coded column, and the ratio.

    Both sides are priced in Arrow's layout, which is the only comparison that means
    anything:

      plain   = validity bitmap + (n_rows + 1) 4-byte offsets + every present row's
                value bytes
      encoded = validity bitmap + n_rows x `code_byte_width` + the dictionary in the
                same utf8 layout ((n_distinct + 1) offsets + distinct value bytes)

    `ratio` is plain / encoded, so > 1 means the encoding shrank the column. It is
    ABSENT (`has_ratio = False`, status `DICT_NO_RATIO`) when `encoded_bytes` is 0,
    because a ratio against nothing does not exist (rule 4) and 0.0 would read as
    "infinitely worse".
    """

    var status: Int
    var n_rows: Int
    var n_distinct: Int
    var plain_bytes: Int
    var dictionary_bytes: Int
    var code_bytes: Int
    var validity_bytes: Int
    var encoded_bytes: Int
    var has_ratio: Bool
    var ratio: Float64


def footprint(values: List[String], mask: List[Bool]) -> DictFootprint:
    """Measure the plain and coded footprints of a column. No estimate, a count.

    Every byte total below is summed from the actual values, so the number this returns
    is the number, for this column. It is not a projection to other data and must not
    be reported as one.
    """
    var encoded = encode_strings(values, mask)
    var out = DictFootprint(
        encoded.status, encoded.n_rows, encoded.n_distinct, 0, 0, 0, 0, 0, False, 0.0
    )
    if encoded.status != DICT_OK:
        return out^

    var n_rows = encoded.n_rows
    var validity_bytes = bytes_for_bits(n_rows)

    var present_value_bytes = 0
    for i in range(n_rows):
        if encoded.codes[i] != NULL_CODE:
            present_value_bytes = _saturating_add(
                present_value_bytes, len(values[i].as_bytes())
            )
    var plain = _saturating_add(validity_bytes, (n_rows + 1) * OFFSET_BYTES)
    plain = _saturating_add(plain, present_value_bytes)

    var distinct_value_bytes = 0
    for i in range(len(encoded.dictionary)):
        distinct_value_bytes = _saturating_add(
            distinct_value_bytes, len(encoded.dictionary[i].as_bytes())
        )
    var dictionary_bytes = _saturating_add(
        (encoded.n_distinct + 1) * OFFSET_BYTES, distinct_value_bytes
    )
    var code_bytes = n_rows * code_byte_width(encoded.n_distinct)
    var encoded_bytes = _saturating_add(validity_bytes, code_bytes)
    encoded_bytes = _saturating_add(encoded_bytes, dictionary_bytes)

    out.plain_bytes = plain
    out.dictionary_bytes = dictionary_bytes
    out.code_bytes = code_bytes
    out.validity_bytes = validity_bytes
    out.encoded_bytes = encoded_bytes
    if encoded_bytes <= 0:
        out.status = DICT_NO_RATIO
        return out^
    out.has_ratio = True
    out.ratio = Float64(plain) / Float64(encoded_bytes)
    return out^


def dict_status_name(status: Int) -> String:
    """The vocabulary for 300-309. See rule 4e on per-package ranges."""
    if status == DICT_OK:
        return "ok"
    if status == DICT_ROW_LIMIT_EXCEEDED:
        return "row_limit_exceeded"
    if status == DICT_CODES_TOO_SHORT:
        return "codes_too_short"
    if status == DICT_VALIDITY_TOO_SHORT:
        return "validity_too_short"
    if status == DICT_CODE_OUT_OF_RANGE:
        return "code_out_of_range"
    if status == DICT_OUTPUT_BUDGET_EXCEEDED:
        return "output_budget_exceeded"
    if status == DICT_NO_RATIO:
        return "no_ratio"
    if status == DICT_INVALID_ROW_COUNT:
        return "invalid_row_count"
    return "unknown"
