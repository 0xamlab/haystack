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
"""
from json.parser import json_get_array, json_get_string

from algenta_runtime.session import ResidentDatasets
from query.plan import run_query_execute, substring


fn _query_error(code: String, message: String) -> String:
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


fn _rows_from_resident(value: String) -> String:
    """The row array inside a resident dataset value.

    Accepts either a bare `[[...],[...]]` array — what `dataset_open` stores when the
    caller opened raw rows — or a `{"columns":[...],"rows":[[...]]}` object, which is
    the shape `query_execute` itself returns. The second form matters because it lets a
    query's OUTPUT be reopened as a dataset and queried again without reshaping it.
    """
    if len(value) == 0:
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


fn run_query(raw: String, datasets: ResidentDatasets) -> String:
    """Run a query plan, sourcing rows from `dataset` when present, else `rows`.

    `dataset` takes precedence when both are given, and that is stated rather than left
    to whichever branch happens to run first: a caller that sends both almost certainly
    meant the handle, and silently querying a stale inline copy is the wrong failure.
    """
    var reference = json_get_string(raw, "dataset")
    if len(reference) == 0:
        return run_query_execute(raw, json_get_array(raw, "rows"))

    # A leading '@' is the same convention batch/pipeline arguments use, but it is
    # optional here because `dataset` is unambiguously a handle field.
    var handle = reference
    if len(handle) > 1 and handle.as_bytes()[0] == 64:  # '@'
        handle = substring(handle, 1, len(handle))

    var value = datasets.lookup(handle)
    if len(value) == 0:
        return _query_error(
            "unknown_dataset",
            "no resident dataset '"
            + handle
            + "'; open one with dataset_open first (handles are connection-scoped)",
        )

    var rows = _rows_from_resident(value)
    if len(rows) == 0:
        return _query_error(
            "dataset_has_no_rows",
            "resident dataset '"
            + handle
            + "' holds no 'rows' array; store either a row array or an object with a"
            " 'rows' key",
        )
    return run_query_execute(raw, rows)
