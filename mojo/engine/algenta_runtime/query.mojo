"""
algenta_runtime.query — bind a query plan to resident session state. Zero Python.

A thin adapter, and thin on purpose. `query/` knows about columns and operators and
nothing about sessions; `algenta_runtime/` owns the resident registries. Putting the
dataset lookup here rather than in `query/plan.mojo` keeps the dependency pointing one
way: the query plane can be tested, benchmarked and reasoned about without a worker
loop or a session.

What this adds over `query_execute` with inline rows
---------------------------------------------------
    {"type":"query_execute","dataset":"@ds_1","columns":[...],"ops":[...]}

The rows come from a handle opened earlier by `dataset_open`, so a plan that runs
twenty times against the same table ships the table once. Combined with
`pipeline_execute`, per-op payload becomes O(1) in rows regardless of table size — the
property that makes repeated analysis over a resident table cheap without a
zero-copy ABI.

A missing or expired handle is an error naming the handle, never an empty result. An
empty result would be a correct-looking answer to a query over no data.

Side tables
-----------
A `tables` entry may name a handle too — `{"name":"regions","columns":[...],
"dataset":"@ds_2"}` — so a dimension table joined by twenty plans is shipped once. The
walk is positional: `query.plan.table_dataset_handles` returns one handle per entry in
DOCUMENT order (empty for an inline table), each non-empty one is resolved here through
the same `lookup` + `_rows_from_resident` the main dataset uses, and the resolved rows go
back positionally. `query/` therefore still knows nothing about sessions, and the two
passes cannot disagree about which entry is which because both index the same array.

The handle form is a payload optimisation, never the op's spelling. Handles are
connection-scoped and the TS daemon opens a fresh connection per call, so a join whose
right side were spelled as a handle would be unreachable from one of the two SDKs. The op
only ever says `"table":"<name>"`.
"""
from json.parser import json_get_array, json_get_string

from algenta_runtime.session import ResidentDatasets
from columnar.batch import RecordBatch
from query.plan import (
    build_batch,
    json_raw_array,
    ops_validation_error,
    run_query_execute_on_batch,
    run_query_execute_with_tables,
    substring,
    table_dataset_handles,
    table_names,
)


def _query_error(code: String, message: String) -> String:
    return (
        '{"error":"'
        + code
        + ": "
        + message
        + '","error_code":"'
        + code
        + '","error_message":"'
        + message
        + '"}'
    )


def _rows_from_resident(value: String) -> String:
    """The row array inside a resident dataset value.

    Accepts either a bare `[[...],[...]]` array — what `dataset_open` stores when the
    caller opened raw rows — or a `{"columns":[...],"rows":[[...]]}` object, which is
    the shape `query_execute` itself returns. The second form matters because it lets a
    query's OUTPUT be reopened as a dataset and queried again without reshaping it.
    """
    if value.byte_length() == 0:
        return ""
    var bytes = value.as_bytes()
    var index = 0
    while index < len(bytes) and (
        bytes[index] == 32 or bytes[index] == 10 or bytes[index] == 13 or bytes[index] == 9
    ):
        index += 1
    if index < len(bytes) and bytes[index] == 91:  # '['
        return value
    return json_get_array(value, "rows")


def run_query(raw: String, mut datasets: ResidentDatasets) -> String:
    """Run a query plan, sourcing rows from `dataset` when present, else `rows`.

    `dataset` takes precedence when both are given, and that is stated rather than left
    to whichever branch happens to run first: a caller that sends both almost certainly
    meant the handle, and silently querying a stale inline copy is the wrong failure.
    """
    # Side tables first, so a bad handle is reported before any row is transposed.
    var handles = table_dataset_handles(raw)
    var names = table_names(raw)
    var table_rows = List[String]()
    var table_headers = List[String]()
    for i in range(len(handles)):
        var table_name = names[i] if i < len(names) else String("")
        if handles[i].byte_length() == 0:
            # An inline table. Nothing to resolve; the empty slot keeps the positions
            # aligned with the `tables` array, which is what parse_named_tables indexes.
            table_rows.append("")
            table_headers.append("")
            continue
        var handle = handles[i]
        var value = datasets.lookup(handle)
        if value.byte_length() == 0:
            # Same code and message shape as the main dataset's miss, extended with the
            # table it belongs to.
            return _query_error(
                "unknown_dataset",
                "no resident dataset '"
                + handle
                + "' for table '"
                + table_name
                + "'; open one with dataset_open first (handles are connection-scoped)",
            )
        var table_row_json = _rows_from_resident(value)
        if table_row_json.byte_length() == 0:
            return _query_error(
                "dataset_has_no_rows",
                "resident dataset '"
                + handle
                + "' for table '"
                + table_name
                + "' holds no 'rows' array; store either a row array or an object with a"
                " 'rows' key",
            )
        table_rows.append(table_row_json)
        # The resident header, when the value is the object form query_execute returns.
        # "" for a bare row array. plan.mojo compares it against the entry's declared
        # `columns`, because parse_rows PADS a short row with nulls, so a mismatch would
        # otherwise yield all-null columns under a success status.
        table_headers.append(json_raw_array(value, "columns"))

    var reference = json_get_string(raw, "dataset")
    if reference.byte_length() == 0:
        return run_query_execute_with_tables(
            raw, json_get_array(raw, "rows"), table_rows, table_headers
        )

    # A leading '@' is the same convention batch/pipeline arguments use, but it is
    # optional here because `dataset` is unambiguously a handle field.
    var handle = reference
    if handle.byte_length() > 1 and handle.as_bytes()[0] == 64:  # '@'
        handle = substring(handle, 1, handle.byte_length())

    var value = datasets.lookup(handle)
    if value.byte_length() == 0:
        return _query_error(
            "unknown_dataset",
            "no resident dataset '"
            + handle
            + "'; open one with dataset_open first (handles are connection-scoped)",
        )

    var rows = _rows_from_resident(value)
    if rows.byte_length() == 0:
        return _query_error(
            "dataset_has_no_rows",
            "resident dataset '"
            + handle
            + "' holds no 'rows' array; store either a row array or an object with a"
            " 'rows' key",
        )

    # Checked before touching the batch, in either branch below, so a request that is
    # invalid both in `ops` and in its rows still fails with the SAME error
    # `run_query_execute_with_tables` has always returned (the ops one) rather than
    # whichever branch happened to run first. See `ops_validation_error`.
    var ops_error = ops_validation_error(raw)
    if ops_error.byte_length() > 0:
        return ops_error

    # The resident dataset's PARSED form is cached by handle + exact `columns` text
    # (see `algenta_runtime.session`'s module docstring): a plan run twice against the
    # same open handle with the same header reuses the parse instead of re-tokenizing
    # `rows` from scratch. Profiling found this reparse, not compute, dominating a
    # `query_execute` against an already-open handle (~2.2s/900k rows, O(rows),
    # repeating identically on every call) — this is what removes it from every call
    # after the first for a given handle+header.
    var signature = json_raw_array(raw, "columns")
    if datasets.has_cached_batch(handle, signature):
        return run_query_execute_on_batch(
            raw, datasets.cached_batch(handle), table_rows, table_headers
        )

    var batch: RecordBatch
    try:
        batch = build_batch(raw, rows)
    except e:
        return _query_error("invalid_arguments", String(e))
    datasets.cache_batch(handle, signature, batch.copy())
    return run_query_execute_on_batch(raw, batch^, table_rows, table_headers)
