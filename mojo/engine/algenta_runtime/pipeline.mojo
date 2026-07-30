"""
algenta_runtime.pipeline — run a whole kernel DAG in ONE frame. Zero Python.

Why
---
`batch_execute` removes the per-call frame cost but the calls stay independent:
anything that feeds one kernel's output into the next must still round-trip, and
every intermediate value gets encoded, shipped, decoded and re-encoded. A
forecast-then-simulate-then-evaluate workflow is mostly that. `pipeline_execute`
keeps intermediates inside the worker: N chained kernels, one frame, and the
values never leave Mojo.

No kernel changes. Each node is handed to the same dispatcher `library_execute`
uses, so a node and a standalone call are the same code path.

Wire format
-----------
    {"type":"pipeline_execute",
     "nodes":[
       {"module":"stats","function":"sort_values","args":[[3.0,1.0,2.0],3]},
       {"module":"stats","function":"median","args":["$0",3]}
     ]}

A string argument of the form `"$<index>"` is replaced by the result of the node
at that index — that substitution is the whole point, and it is why the chain
costs one frame instead of N. References must point backwards; a forward or
self-reference is rejected before anything executes.

Response
--------
    {"result":<final node's result>,
     "lineage":[{"index":0,"module":"stats","function":"sort_values","ok":true}, ...],
     "results":[<result of each node>],
     "plan_hash":"<64-hex>","nodes":2,"ok":2,"failed":0}

`plan_hash` is SHA-256 over the node list with every `$k` reference intact and no
results mixed in, so the same plan hashes identically across runs, machines and
languages — it identifies the computation, not the data.

`continue_on_error` (default false) is fail-fast: a DAG's later nodes usually
consume earlier ones, so continuing past a failure normally just produces more
failures. Set it true to attempt every node regardless.
"""
from json.parser import (
    json_array_get,
    json_array_len,
    json_array_tokens,
    json_get_array,
    json_get_bool,
    json_get_string,
)
from sha256 import sha256_hex

from canonical.from_json import transcode
from canonical.hash import hash_canonical_bytes

from algenta_runtime.session import (
    ResidentDatasets,
    dataset_reference_handle,
    is_dataset_reference,
)

# Bound on nodes per plan. Generous for real workflows, but stops a malformed or
# hostile frame from pinning the single-threaded worker loop.
alias MAX_PIPELINE_NODES = 512

alias Dispatcher = fn (String) raises -> String


fn _pipeline_error(code: String, message: String) -> String:
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


alias _QUOTE: UInt8 = 34  # "
alias _DOLLAR: UInt8 = 36  # $
alias _ZERO: UInt8 = 48  # 0
alias _NINE: UInt8 = 57  # 9
alias _BRACE_CLOSE: UInt8 = 125  # }


fn _is_reference(token: String) -> Bool:
    """True for a `"$<digits>"` argument token (quoted, at least one digit)."""
    if len(token) < 4:
        return False
    var bytes = token.as_bytes()
    if bytes[0] != _QUOTE or bytes[len(token) - 1] != _QUOTE:
        return False
    if bytes[1] != _DOLLAR:
        return False
    for i in range(2, len(token) - 1):
        if bytes[i] < _ZERO or bytes[i] > _NINE:
            return False
    return True


fn _reference_index(token: String) -> Int:
    """Index from a validated `"$<digits>"` token."""
    var bytes = token.as_bytes()
    var value = 0
    for i in range(2, len(token) - 1):
        value = value * 10 + Int(bytes[i] - _ZERO)
    return value


fn extract_result_json(response: String) -> String:
    """The raw JSON of a dispatch response's `result` field.

    The envelope is always `{"result":<value>}` for a success, so slicing after
    the known prefix preserves the value's exact JSON form — numbers keep their
    formatting, lists and objects stay nested. Going through a typed accessor
    would force a lossy round-trip through one concrete Mojo type.
    """
    var marker = String('"result":')
    var start = response.find(marker)
    if start < 0:
        return "null"
    var value_start = start + len(marker)
    var bytes = response.as_bytes()
    var value_end = len(response)
    # Trim back to (and then past) the envelope's closing brace.
    while value_end > value_start and bytes[value_end - 1] != _BRACE_CLOSE:
        value_end -= 1
    if value_end > value_start:
        value_end -= 1
    if value_end <= value_start:
        return "null"
    # Byte-by-byte accumulation, matching json/parser.mojo's substring convention.
    var value = String("")
    for i in range(value_start, value_end):
        value += chr(Int(bytes[i]))
    return value


fn _bind_args(
    args_json: String,
    results: List[String],
    datasets: ResidentDatasets,
) raises -> String:
    """Substitute references in an args array.

    `$k` becomes node k's result; `@handle` becomes a resident dataset. An unknown
    handle raises rather than binding null, so a typo fails loudly instead of
    silently feeding a kernel nothing.
    """
    var tokens = json_array_tokens(args_json)
    var bound = String("[")
    for i in range(len(tokens)):
        if i > 0:
            bound += ","
        var token = tokens[i]
        if _is_reference(token):
            bound += results[_reference_index(token)]
        elif is_dataset_reference(token):
            var value = datasets.lookup(dataset_reference_handle(token))
            if len(value) == 0:
                raise Error("unknown dataset handle " + dataset_reference_handle(token))
            bound += value
        else:
            bound += token
    bound += "]"
    return bound


fn plan_hash(nodes_json: String) -> String:
    """Stable identity of a plan: its nodes, references intact, no results.

    Hashes the plan's *canonical* form, not its JSON text. Hashing the text made the
    identity depend on key order and whitespace, so two SDKs that serialise the same
    plan differently produced different hashes — exactly the disagreement a plan hash
    exists to rule out. Transcoding first removes text from the equation.

    Falls back to hashing the raw text if the plan will not parse. A malformed plan
    is about to be rejected by the caller anyway, and a hash is more useful than an
    exception on the way there.
    """
    try:
        return hash_canonical_bytes(transcode(nodes_json))
    except:
        return sha256_hex(nodes_json)


fn run_pipeline_execute[dispatch: Dispatcher](
    raw: String,
    datasets: ResidentDatasets,
) raises -> String:
    """Execute every node in order, threading results through `$k` references."""
    var nodes_json = json_get_array(raw, "nodes")
    if len(nodes_json) == 0:
        return _pipeline_error(
            "invalid_arguments", "pipeline_execute requires a non-empty nodes array."
        )

    var nodes: List[String]
    try:
        nodes = json_array_tokens(nodes_json)
    except:
        return _pipeline_error("invalid_arguments", "pipeline_execute nodes array is malformed.")

    if len(nodes) > MAX_PIPELINE_NODES:
        return _pipeline_error(
            "invalid_arguments",
            "pipeline_execute accepts at most " + String(MAX_PIPELINE_NODES) + " nodes.",
        )

    # Validate every reference before running anything: a plan that cannot bind is
    # rejected whole rather than half-executed.
    for i in range(len(nodes)):
        var args_json = json_get_array(nodes[i], "args")
        if len(args_json) == 0:
            continue
        var tokens: List[String]
        try:
            tokens = json_array_tokens(args_json)
        except:
            return _pipeline_error(
                "invalid_arguments", "node " + String(i) + " has a malformed args array."
            )
        for t in range(len(tokens)):
            if not _is_reference(tokens[t]):
                continue
            var target = _reference_index(tokens[t])
            if target >= i:
                return _pipeline_error(
                    "invalid_arguments",
                    "node "
                    + String(i)
                    + " references node "
                    + String(target)
                    + "; references must point to an earlier node.",
                )

    var results = List[String]()
    var lineage = String("[")
    var ok = 0
    var failed = 0
    var continue_on_error = json_get_bool(raw, "continue_on_error", False)
    var last_result = String("null")

    for i in range(len(nodes)):
        var module_name = json_get_string(nodes[i], "module")
        var function_name = json_get_string(nodes[i], "function")
        var args_json = json_get_array(nodes[i], "args")
        if len(args_json) == 0:
            args_json = "[]"

        var node_ok = True
        var bound = String("[]")
        try:
            bound = _bind_args(args_json, results, datasets)
        except:
            node_ok = False

        var response = String("")
        if node_ok:
            var request = (
                '{"module":"'
                + module_name
                + '","function":"'
                + function_name
                + '","args":'
                + bound
                + "}"
            )
            try:
                response = dispatch(request)
            except:
                response = _pipeline_error(
                    "mojo_library_execution_failed",
                    "node " + String(i) + " raised during dispatch.",
                )
            if len(json_get_string(response, "error_code")) > 0:
                node_ok = False
        else:
            response = _pipeline_error(
                "invalid_arguments", "node " + String(i) + " could not bind its arguments."
            )

        if i > 0:
            lineage += ","
        lineage += (
            '{"index":'
            + String(i)
            + ',"module":"'
            + module_name
            + '","function":"'
            + function_name
            + '","ok":'
            + ("true" if node_ok else "false")
            + "}"
        )

        if node_ok:
            var value = extract_result_json(response)
            results.append(value)
            last_result = value
            ok += 1
        else:
            # Keep positions aligned so later `$k` references stay meaningful.
            results.append("null")
            failed += 1
            if not continue_on_error:
                lineage += "]"
                return (
                    '{"error":"pipeline_node_failed: node '
                    + String(i)
                    + ' failed","error_code":"pipeline_node_failed"'
                    + ',"error_message":'
                    + '"node '
                    + String(i)
                    + " ("
                    + module_name
                    + "."
                    + function_name
                    + ') failed","failed_index":'
                    + String(i)
                    + ',"node_response":'
                    + response
                    + ',"lineage":'
                    + lineage
                    + ',"plan_hash":"'
                    + plan_hash(nodes_json)
                    + '","nodes":'
                    + String(len(nodes))
                    + ',"ok":'
                    + String(ok)
                    + ',"failed":'
                    + String(failed)
                    + "}"
                )

    lineage += "]"

    var results_json = String("[")
    for i in range(len(results)):
        if i > 0:
            results_json += ","
        results_json += results[i]
    results_json += "]"

    return (
        '{"result":'
        + last_result
        + ',"results":'
        + results_json
        + ',"lineage":'
        + lineage
        + ',"plan_hash":"'
        + plan_hash(nodes_json)
        + '","nodes":'
        + String(len(nodes))
        + ',"ok":'
        + String(ok)
        + ',"failed":'
        + String(failed)
        + "}"
    )
