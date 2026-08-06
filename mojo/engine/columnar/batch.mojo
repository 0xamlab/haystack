"""
columnar.batch — a schema and a set of equal-length columns. Zero Python.

A `RecordBatch` is the unit operators pass to each other: named, typed columns that
all agree on row count. Row count lives on the batch rather than being inferred from
whichever column happens to be first, so a ragged batch is detectable instead of
producing a silently truncated result.

Only Float64 columns are carried here. That is a deliberate first cut rather than an
oversight: the executor's aggregate/filter path is numeric, and adding Int64/String
columns to the batch means either a sum type or four parallel lists, both of which are
better decided once there is a consumer that needs them. `columnar.array` already has
the other types, so nothing is blocked.

`take` is the primitive filtering and sorting share. Both are "produce a new batch
from these row indices", so expressing them once means a filter and a sort cannot
disagree about null handling or bounds.
"""
from columnar.array import Float64Array, float64_with_nulls
from columnar.dtype import DTYPE_FLOAT64, dtype_name
from columnar.validity import is_valid


struct Schema(Copyable, Movable):
    """Column names and types. Names are positional — index is the identity."""

    var names: List[String]
    var dtypes: List[Int]

    def __init__(out self, var names: List[String], var dtypes: List[Int]):
        self.names = names^
        self.dtypes = dtypes^

    def width(self) -> Int:
        return len(self.names)

    def index_of(self, name: String) -> Int:
        """Column index for `name`, or -1.

        Linear: schemas are a handful of columns, and a map would cost more to build
        than the scans it saves.
        """
        for i in range(len(self.names)):
            if self.names[i] == name:
                return i
        return -1

    def has(self, name: String) -> Bool:
        return self.index_of(name) >= 0

    def name_at(self, index: Int) -> String:
        if index < 0 or index >= len(self.names):
            return ""
        return self.names[index]

    def dtype_at(self, index: Int) -> Int:
        if index < 0 or index >= len(self.dtypes):
            return DTYPE_FLOAT64
        return self.dtypes[index]

    def describe(self) -> String:
        var out = String("")
        for i in range(len(self.names)):
            if i > 0:
                out += ", "
            out += self.names[i] + ":" + dtype_name(self.dtypes[i])
        return out


def schema_of(var names: List[String]) -> Schema:
    """A schema of all-Float64 columns — the common case for now."""
    var dtypes = List[Int]()
    for _ in range(len(names)):
        dtypes.append(DTYPE_FLOAT64)
    return Schema(names^, dtypes^)


struct RecordBatch(Copyable, Movable):
    """Equal-length named columns. `n_rows` is authoritative, not inferred."""

    var schema: Schema
    var columns: List[Float64Array]
    var n_rows: Int

    def __init__(out self, var schema: Schema, var columns: List[Float64Array], n_rows: Int):
        self.schema = schema^
        self.columns = columns^
        self.n_rows = n_rows

    def width(self) -> Int:
        return len(self.columns)

    def is_consistent(self) -> Bool:
        """True when every column is exactly `n_rows` long and the schema matches.

        Checked rather than assumed: a ragged batch otherwise yields results computed
        over whichever prefix happened to be shortest, which looks like a plausible
        answer.
        """
        if len(self.columns) != self.schema.width():
            return False
        for i in range(len(self.columns)):
            if self.columns[i].length != self.n_rows:
                return False
        return True

    def column_index(self, name: String) -> Int:
        return self.schema.index_of(name)

    def column(self, index: Int) -> Float64Array:
        """Column by position. An out-of-range index yields an empty column.

        Empty rather than raising so an executor can report a missing column by name
        at plan time instead of unwinding mid-scan.
        """
        if index < 0 or index >= len(self.columns):
            var empty_values = List[Float64]()
            var empty_mask = List[Bool]()
            return float64_with_nulls(empty_values^, empty_mask)
        return self.columns[index].copy()

    def column_by_name(self, name: String) -> Float64Array:
        return self.column(self.schema.index_of(name))

    def slice(self, start: Int, count: Int) -> RecordBatch:
        """A row window across every column — the chunking primitive."""
        var begin = start
        if begin < 0:
            begin = 0
        if begin > self.n_rows:
            begin = self.n_rows
        var take_n = count
        if take_n < 0:
            take_n = 0
        if begin + take_n > self.n_rows:
            take_n = self.n_rows - begin

        var sliced = List[Float64Array]()
        for i in range(len(self.columns)):
            sliced.append(self.columns[i].slice(begin, take_n))
        var names = List[String]()
        var dtypes = List[Int]()
        for i in range(self.schema.width()):
            names.append(self.schema.names[i])
            dtypes.append(self.schema.dtypes[i])
        return RecordBatch(Schema(names^, dtypes^), sliced^, take_n)

    def describe(self) -> String:
        return (
            "RecordBatch("
            + String(self.n_rows)
            + " rows, "
            + String(self.width())
            + " cols: "
            + self.schema.describe()
            + ")"
        )


def take_column(source: Float64Array, indices: List[Int]) -> Float64Array:
    """Gather rows by index. An out-of-range index yields a null, not a zero.

    Null rather than 0.0 because "this row does not exist" is an absence, and 0.0
    would enter an aggregate as real data. Callers that consider an out-of-range
    index a bug should validate before calling; those doing an outer join want
    exactly this behaviour.

    The `else` branch reads via `get_unchecked` rather than `get`: the `if` just
    above it already ran `is_valid_at(index)` to decide which branch to take, and
    `get` would re-run that identical bounds-check-plus-bitmap-test a second time on
    every present cell — i.e. on almost the whole output of a gather, which this is.
    `get_unchecked` skips straight to the read the `if` already proved safe.
    """
    var values = List[Float64]()
    var mask = List[Bool]()
    for i in range(len(indices)):
        var index = indices[i]
        if index < 0 or index >= source.length or not source.is_valid_at(index):
            values.append(0.0)
            mask.append(False)
        else:
            values.append(source.get_unchecked(index))
            mask.append(True)
    return float64_with_nulls(values^, mask)


def take(batch: RecordBatch, indices: List[Int]) -> RecordBatch:
    """A new batch of the given rows, in the given order.

    The one primitive behind both filter and sort: a filter passes the surviving
    indices, a sort passes the permuted ones. Sharing it means they cannot diverge on
    null or bounds handling.
    """
    var taken = List[Float64Array]()
    for i in range(batch.width()):
        taken.append(take_column(batch.columns[i], indices))
    var names = List[String]()
    var dtypes = List[Int]()
    for i in range(batch.schema.width()):
        names.append(batch.schema.names[i])
        dtypes.append(batch.schema.dtypes[i])
    return RecordBatch(Schema(names^, dtypes^), taken^, len(indices))


def indices_where(mask: List[Bool]) -> List[Int]:
    """Row indices where `mask` is true — a filter's selection vector."""
    var out = List[Int]()
    for i in range(len(mask)):
        if mask[i]:
            out.append(i)
    return out^


def filter_batch(batch: RecordBatch, mask: List[Bool]) -> RecordBatch:
    """Keep the rows where `mask` is true, via `take`."""
    return take(batch, indices_where(mask))


def valid_mask(source: Float64Array) -> List[Bool]:
    """A column's validity as a Bool mask — for `filter_batch(b, valid_mask(c))`."""
    var out = List[Bool]()
    for i in range(source.length):
        out.append(is_valid(source.validity, i))
    return out^
