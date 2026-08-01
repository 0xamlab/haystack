"""
columnar.array — typed nullable columns. Zero Python.

A column is values plus a validity bitmap, so presence is independent of value and
`0.0` no longer has to mean "missing". Each array keeps its own dtype, so an integer
id stays an integer instead of becoming a float the way `data/dataframe.mojo` forces.

Slicing is offset+length over the *shared* values list. That makes a slice O(1) in
rows rather than a copy — the property that lets an executor pass windows of a large
column between operators without duplicating it. The validity bitmap is re-aligned on
slice, because bit offsets are not byte offsets: only a multiple-of-8 offset could be
shared, and depending on that would be a trap.

Reading a null returns the type's zero *and* `False` from `is_valid`. The zero is
never meaningful; callers must consult validity. That is the whole reason validity
exists, and every reduction in `numeric.reduce` takes the mask for exactly this
reason.
"""
from std.memory import ArcPointer

from columnar.dtype import (
    DTYPE_BOOL,
    DTYPE_FLOAT64,
    DTYPE_INT64,
    DTYPE_STRING,
    dtype_name,
)
from columnar.validity import (
    count_null,
    count_valid,
    is_valid,
    new_all_null,
    new_all_valid,
    set_null,
    set_valid,
    slice_bitmap,
)


struct Float64Array(Copyable, Movable):
    """Nullable Float64 column. `offset`/`length` make a slice O(1) in rows."""

    var values: ArcPointer[List[Float64]]
    var validity: List[UInt8]
    var offset: Int
    var length: Int

    fn __init__(out self, var values: ArcPointer[List[Float64]], var validity: List[UInt8], offset: Int, length: Int):
        self.values = values^
        self.validity = validity^
        self.offset = offset
        self.length = length

    fn dtype(self) -> Int:
        return DTYPE_FLOAT64

    fn is_valid_at(self, index: Int) -> Bool:
        if index < 0 or index >= self.length:
            return False
        return is_valid(self.validity, index)

    fn get(self, index: Int) -> Float64:
        """The value at `index`, or 0.0 when absent or out of range.

        The 0.0 is not a value — check `is_valid_at` first. Returning it rather than
        raising keeps the hot path branch-free for callers that already hold the mask.
        """
        if not self.is_valid_at(index):
            return 0.0
        return self.values[][self.offset + index]

    fn null_count(self) -> Int:
        return count_null(self.validity, self.length)

    fn valid_count(self) -> Int:
        return count_valid(self.validity, self.length)

    fn slice(self, start: Int, count: Int) -> Float64Array:
        """A window over the same values — no element copy.

        Out-of-range requests clamp rather than raise: a slice past the end is an
        empty slice, which composes; an exception there would force every caller to
        bounds-check before every window.
        """
        var begin = start
        if begin < 0:
            begin = 0
        if begin > self.length:
            begin = self.length
        var take = count
        if take < 0:
            take = 0
        if begin + take > self.length:
            take = self.length - begin
        return Float64Array(
            self.values,
            slice_bitmap(self.validity, begin, take),
            self.offset + begin,
            take,
        )

    fn values_list(self) -> List[Float64]:
        """This window's values, for `numeric.reduce`. Pair with `mask_list`."""
        var out = List[Float64]()
        for i in range(self.length):
            out.append(self.values[][self.offset + i])
        return out^

    fn mask_list(self) -> List[Bool]:
        """This window's validity as a Bool mask, aligned to `values_list`."""
        var out = List[Bool]()
        for i in range(self.length):
            out.append(is_valid(self.validity, i))
        return out^


fn float64_from_list(var values: List[Float64]) -> Float64Array:
    """A column with every slot present — the no-nulls case."""
    var n = len(values)
    return Float64Array(ArcPointer(values^), new_all_valid(n), 0, n)


fn float64_with_nulls(var values: List[Float64], mask: List[Bool]) -> Float64Array:
    """A column whose presence comes from `mask`. Missing mask entries are absent."""
    var n = len(values)
    var bitmap = new_all_null(n)
    for i in range(n):
        if i < len(mask) and mask[i]:
            set_valid(bitmap, i)
    return Float64Array(ArcPointer(values^), bitmap^, 0, n)


struct Int64Array(Copyable, Movable):
    """Nullable Int64 column. Kept distinct from Float64 so ids stay exact."""

    var values: ArcPointer[List[Int]]
    var validity: List[UInt8]
    var offset: Int
    var length: Int

    fn __init__(out self, var values: ArcPointer[List[Int]], var validity: List[UInt8], offset: Int, length: Int):
        self.values = values^
        self.validity = validity^
        self.offset = offset
        self.length = length

    fn dtype(self) -> Int:
        return DTYPE_INT64

    fn is_valid_at(self, index: Int) -> Bool:
        if index < 0 or index >= self.length:
            return False
        return is_valid(self.validity, index)

    fn get(self, index: Int) -> Int:
        if not self.is_valid_at(index):
            return 0
        return self.values[][self.offset + index]

    fn null_count(self) -> Int:
        return count_null(self.validity, self.length)

    fn slice(self, start: Int, count: Int) -> Int64Array:
        var begin = start
        if begin < 0:
            begin = 0
        if begin > self.length:
            begin = self.length
        var take = count
        if take < 0:
            take = 0
        if begin + take > self.length:
            take = self.length - begin
        return Int64Array(
            self.values,
            slice_bitmap(self.validity, begin, take),
            self.offset + begin,
            take,
        )

    fn to_float64(self) -> Float64Array:
        """Widen to Float64. Lossy above 2^53 — `dtype.promotion_loses_precision`
        reports that, and this is the operation it is warning about."""
        var widened = List[Float64]()
        for i in range(self.length):
            widened.append(Float64(self.values[][self.offset + i]))
        var n = self.length
        return Float64Array(ArcPointer(widened^), slice_bitmap(self.validity, 0, n), 0, n)


fn int64_from_list(var values: List[Int]) -> Int64Array:
    var n = len(values)
    return Int64Array(ArcPointer(values^), new_all_valid(n), 0, n)


fn int64_with_nulls(var values: List[Int], mask: List[Bool]) -> Int64Array:
    """An Int64 column whose presence comes from `mask` — `float64_with_nulls`'s
    exact analog, added for `query.aggregate.group_by_int64` (int64-columnar-fidelity):
    that function needs a nullable Int64 key column to keep `group_by`'s null-key
    policy, and there was previously no way to build one without hand-assembling a
    validity bitmap outside `columnar.validity`."""
    var n = len(values)
    var bitmap = new_all_null(n)
    for i in range(n):
        if i < len(mask) and mask[i]:
            set_valid(bitmap, i)
    return Int64Array(ArcPointer(values^), bitmap^, 0, n)


struct BoolArray(Copyable, Movable):
    """Nullable boolean column — a filter mask with three states, not two.

    A predicate over nullable data yields present-true, present-false, or unknown.
    Collapsing unknown into false is how a filter silently drops rows that should
    have been reported as indeterminate.
    """

    var values: ArcPointer[List[Bool]]
    var validity: List[UInt8]
    var offset: Int
    var length: Int

    fn __init__(out self, var values: ArcPointer[List[Bool]], var validity: List[UInt8], offset: Int, length: Int):
        self.values = values^
        self.validity = validity^
        self.offset = offset
        self.length = length

    fn dtype(self) -> Int:
        return DTYPE_BOOL

    fn is_valid_at(self, index: Int) -> Bool:
        if index < 0 or index >= self.length:
            return False
        return is_valid(self.validity, index)

    fn get(self, index: Int) -> Bool:
        if not self.is_valid_at(index):
            return False
        return self.values[][self.offset + index]

    fn true_count(self) -> Int:
        """Present-and-true slots — the row count a filter would keep."""
        var n = 0
        for i in range(self.length):
            if self.is_valid_at(i) and self.values[][self.offset + i]:
                n += 1
        return n


fn bool_from_list(var values: List[Bool]) -> BoolArray:
    var n = len(values)
    return BoolArray(ArcPointer(values^), new_all_valid(n), 0, n)


struct StringArray(Copyable, Movable):
    """Nullable string column, stored as a values list rather than offsets+bytes.

    A list of Strings rather than the Arrow offsets+bytes layout: the executor's
    string work here is grouping and equality, both of which want whole strings, and
    the offset layout only starts paying off once there is a zero-copy consumer to
    hand buffers to. Noted as the natural upgrade when `arrow_wire` lands.
    """

    var values: ArcPointer[List[String]]
    var validity: List[UInt8]
    var offset: Int
    var length: Int

    fn __init__(out self, var values: ArcPointer[List[String]], var validity: List[UInt8], offset: Int, length: Int):
        self.values = values^
        self.validity = validity^
        self.offset = offset
        self.length = length

    fn dtype(self) -> Int:
        return DTYPE_STRING

    fn is_valid_at(self, index: Int) -> Bool:
        if index < 0 or index >= self.length:
            return False
        return is_valid(self.validity, index)

    fn get(self, index: Int) -> String:
        """The value, or "" when absent. Empty string is a legitimate value, so
        callers must distinguish it from absent via `is_valid_at`."""
        if not self.is_valid_at(index):
            return ""
        return self.values[][self.offset + index]

    fn null_count(self) -> Int:
        return count_null(self.validity, self.length)


fn string_from_list(var values: List[String]) -> StringArray:
    var n = len(values)
    return StringArray(ArcPointer(values^), new_all_valid(n), 0, n)


fn describe(dtype: Int, length: Int, nulls: Int) -> String:
    """A one-line column summary, for lineage and error messages."""
    return (
        dtype_name(dtype)
        + "["
        + String(length)
        + "]"
        + (" nulls=" + String(nulls) if nulls > 0 else "")
    )
