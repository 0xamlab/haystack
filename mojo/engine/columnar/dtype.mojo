"""
columnar.dtype — the type tags a column can carry. Zero Python.

`data/dataframe.mojo` and `database.mojo` are Float64-only, so an integer id, a
boolean flag and a category label all become floats. That is lossy in ways that bite
later: 2^53+1 stops round-tripping, `true` and `1.0` become indistinguishable, and a
category has to be dictionary-coded by the caller or not at all.

Promotion is explicit here rather than implicit. Mixing an Int64 column with a
Float64 one is a decision with a precision consequence, so it is named
(`promote`) rather than happening silently at the point of use.
"""

comptime DTYPE_NULL: Int = 0
comptime DTYPE_BOOL: Int = 1
comptime DTYPE_INT64: Int = 2
comptime DTYPE_FLOAT64: Int = 3
comptime DTYPE_STRING: Int = 4

comptime DTYPE_INVALID: Int = -1


def dtype_name(dtype: Int) -> String:
    if dtype == DTYPE_NULL:
        return "null"
    if dtype == DTYPE_BOOL:
        return "bool"
    if dtype == DTYPE_INT64:
        return "int64"
    if dtype == DTYPE_FLOAT64:
        return "float64"
    if dtype == DTYPE_STRING:
        return "string"
    return "invalid"


def dtype_from_name(name: String) -> Int:
    if name == "null":
        return DTYPE_NULL
    if name == "bool":
        return DTYPE_BOOL
    if name == "int64":
        return DTYPE_INT64
    if name == "float64":
        return DTYPE_FLOAT64
    if name == "string":
        return DTYPE_STRING
    return DTYPE_INVALID


def is_numeric(dtype: Int) -> Bool:
    """True for types a value aggregation accepts.

    Bool is deliberately excluded. Treating `true` as 1 is exactly how the existing
    Python path silently averages booleans; making it require an explicit cast keeps
    that from happening by accident.
    """
    return dtype == DTYPE_INT64 or dtype == DTYPE_FLOAT64


def byte_width(dtype: Int) -> Int:
    """Fixed width per slot, or 0 for variable-width types."""
    if dtype == DTYPE_BOOL:
        return 1
    if dtype == DTYPE_INT64:
        return 8
    if dtype == DTYPE_FLOAT64:
        return 8
    return 0  # string is offsets + bytes; null carries no data at all


def is_fixed_width(dtype: Int) -> Bool:
    return byte_width(dtype) > 0


def promote(a: Int, b: Int) -> Int:
    """The type that holds both, or `DTYPE_INVALID` if none does.

    NULL promotes to whatever it meets: an all-null column has no type of its own, so
    it takes its counterpart's. Int64 with Float64 gives Float64 and loses precision
    above 2^53 — real, and the reason this is a named operation rather than a silent
    coercion at the call site. Nothing promotes across the numeric/string boundary;
    that is a cast, and a cast can fail.
    """
    if a == b:
        return a
    if a == DTYPE_NULL:
        return b
    if b == DTYPE_NULL:
        return a
    if (a == DTYPE_INT64 and b == DTYPE_FLOAT64) or (a == DTYPE_FLOAT64 and b == DTYPE_INT64):
        return DTYPE_FLOAT64
    return DTYPE_INVALID


def can_promote(a: Int, b: Int) -> Bool:
    return promote(a, b) != DTYPE_INVALID


def promotion_loses_precision(a: Int, b: Int) -> Bool:
    """True when promoting would silently lose precision, so callers can warn."""
    return (a == DTYPE_INT64 and b == DTYPE_FLOAT64) or (
        a == DTYPE_FLOAT64 and b == DTYPE_INT64
    )
