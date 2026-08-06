"""
runtime.batch — execute N runtime-library requests in ONE frame. Zero Python.

Why
---
`library_execute` carries exactly one call per frame. Frame I/O dominates a small
kernel call, so a workflow of N kernels pays N round trips plus N encode/decode
cycles even when every call is sub-microsecond of actual compute. `batch_execute`
amortises that: one frame in, one frame out, N kernel invocations in between.

Existing kernels are untouched. Each item is handed to the generated
`dispatch_runtime_library` verbatim, so a batched call and a single call take the
same path and produce the same result.

Wire format
-----------
Request:
    {"type":"batch_execute",
     "requests":[{"module":"stats","function":"compute_mean","args":[[1.0,2.0]]},
                 {"module":"stats","function":"compute_variance","args":[[1.0,2.0]]}],
     "partial_ok":true}

Response:
    {"results":[{"result":1.5},{"result":0.25}],
     "count":2,"ok":2,"failed":0,"stopped_early":false}

`results[i]` is the untouched response for `requests[i]` — either `{"result":...}`
or `{"error":...,"error_code":...,"error_message":...}`, exactly as a single
`library_execute` would return. Ordering is positional and always preserved.

`partial_ok` (default true) runs every item and reports per-item outcomes. When
false, execution stops after the first failing item; `stopped_early` is then true
and `results` holds only the items attempted, so the caller can tell exactly how
far the batch got.
"""
from json.parser import json_array_tokens, json_get_array, json_get_bool, json_get_string

from algenta_runtime.resources import budget_exceeded_json, parse_budget
from algenta_runtime.session import (
    ResidentDatasets,
    dataset_reference_handle,
    is_dataset_reference,
)

# The dispatcher is a generic callable parameter rather than a direct import of
# `runtime_library_dispatch_generated`. Two reasons: this module stays independent
# of the ~100k-line generated table (importing it would make every test that
# touches batching JIT-compile the whole thing), and the batching contract becomes
# testable against a stub. main.mojo binds the real dispatcher. (Mojo 1.x form: the
# signature constraint lives on the generic parameter, not on a function-type alias.)


def _batch_error(code: String, message: String) -> String:
    """Frame-level failure: the batch envelope itself was unusable."""
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


def bind_dataset_references(
    request: String,
    datasets: ResidentDatasets,
) raises -> String:
    """Replace `@handle` args in one request with their resident values.

    Returns the request unchanged when it holds no references, so the common case
    costs one scan and no rebuild. An unknown handle raises rather than binding
    nothing, matching the pipeline: a typo must fail, not silently feed a kernel an
    empty list.
    """
    var args_json = json_get_array(request, "args")
    if len(args_json) == 0:
        return request

    var tokens = json_array_tokens(args_json)
    var found = False
    for i in range(len(tokens)):
        if is_dataset_reference(tokens[i]):
            found = True
            break
    if not found:
        return request

    var bound = String("[")
    for i in range(len(tokens)):
        if i > 0:
            bound += ","
        if is_dataset_reference(tokens[i]):
            var handle = dataset_reference_handle(tokens[i])
            var value = datasets.lookup(handle)
            if len(value) == 0:
                raise Error("unknown dataset handle " + handle)
            bound += value
        else:
            bound += tokens[i]
    bound += "]"

    return (
        '{"module":"'
        + json_get_string(request, "module")
        + '","function":"'
        + json_get_string(request, "function")
        + '","args":'
        + bound
        + "}"
    )


def response_is_error(response: String) -> Bool:
    """True when a dispatch response carries an error_code.

    Keyed on `error_code` rather than a prefix check so it stays correct if the
    generated envelope ever reorders its keys.
    """
    return len(json_get_string(response, "error_code")) > 0


def run_batch_execute[DispatchT: def(String) raises -> String](
    dispatch: DispatchT,
    raw: String,
    datasets: ResidentDatasets,
) raises -> String:
    """Execute every request in `raw` and return one combined envelope."""
    var requests_json = json_get_array(raw, "requests")
    if len(requests_json) == 0:
        return _batch_error(
            "invalid_arguments",
            "batch_execute requires a non-empty requests array.",
        )

    var tokens: List[String]
    try:
        tokens = json_array_tokens(requests_json)
    except:
        return _batch_error(
            "invalid_arguments",
            "batch_execute requests array is malformed.",
        )

    var partial_ok = json_get_bool(raw, "partial_ok", True)
    var budget = parse_budget(raw)

    var results = String("[")
    var count = 0
    var ok = 0
    var failed = 0
    var stopped_early = False

    for i in range(len(tokens)):
        # Checked before starting the item, so a budget is never blamed for work
        # it did not authorise.
        var exhausted = budget.exceeded()
        if len(exhausted) > 0:
            return budget_exceeded_json(
                exhausted,
                results + "]",
                budget.consumed_json(),
            )

        var response: String
        try:
            response = dispatch(bind_dataset_references(tokens[i], datasets))
        except:
            response = _batch_error(
                "mojo_library_execution_failed",
                "batch item " + String(i) + " could not bind its arguments or raised "
                "during dispatch.",
            )

        if count > 0:
            results += ","
        results += response
        count += 1
        budget.record(len(response))

        if response_is_error(response):
            failed += 1
            if not partial_ok:
                stopped_early = True
                break
        else:
            ok += 1

    results += "]"

    var stopped_json = "true" if stopped_early else "false"
    return (
        '{"results":'
        + results
        + ',"count":'
        + String(count)
        + ',"ok":'
        + String(ok)
        + ',"failed":'
        + String(failed)
        + ',"stopped_early":'
        + stopped_json
        + "}"
    )
