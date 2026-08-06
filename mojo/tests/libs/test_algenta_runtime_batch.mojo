"""test_algenta_runtime_batch.mojo — known-value tests for algenta_runtime.batch (hand-written).

Covers the batch envelope contract: positional ordering, per-item error isolation,
ok/failed accounting, the partial_ok short-circuit, malformed input, and
determinism.

Runs against a stub dispatcher rather than the generated table. That keeps the
test honest about what it owns — the batching contract, not kernel maths — and
fast: importing runtime_library_dispatch_generated would JIT-compile ~100k lines
on every run.
"""
from json.parser import (
    json_array_get,
    json_array_len,
    json_get_array,
    json_get_bool,
    json_get_int,
    json_get_string,
)
from algenta_runtime.session import ResidentDatasets
from algenta_runtime.batch import (
    bind_dataset_references,
    response_is_error,
    run_batch_execute,
)


def _stub_dispatch(raw: String) raises -> String:
    """Echo the requested function, or fail for the sentinel `__boom__`.

    Mirrors the generated table's envelope shape exactly: `{"result":...}` on
    success, `{"error":...,"error_code":...,"error_message":...}` on failure.
    """
    var function = json_get_string(raw, "function")
    if function == "__boom__":
        return (
            '{"error":"function_not_registered: nope","error_code":'
            + '"function_not_registered","error_message":"nope"}'
        )
    if function == "__raise__":
        raise Error("stub dispatcher raised")
    return '{"result":"' + function + '"}'


def _req(function: String) -> String:
    return '{"module":"stub","function":"' + function + '","args":[]}'


def main() raises:
    # Empty registry: these suites exercise the DAG/batch contract, not residency.
    var _datasets = ResidentDatasets()
    var passed = 0
    var failed = 0

    # ── one item matches a direct dispatch byte-for-byte ─────────────────────
    var single = _req("alpha")
    var direct = _stub_dispatch(single)
    var batched = run_batch_execute(_stub_dispatch, '{"type":"batch_execute","requests":[' + single + "]}", _datasets)
    var results = json_get_array(batched, "results")
    if json_array_len(results) == 1 and json_array_get(results, 0) == direct:
        passed += 1
        print("  ✅ single item matches direct dispatch byte-for-byte")
    else:
        failed += 1
        print("  ❌ single item diverged:", json_array_get(results, 0), "vs", direct)

    if json_get_int(batched, "count", -1) == 1 and json_get_int(batched, "ok", -1) == 1:
        passed += 1
        print("  ✅ count/ok accounting for one success")
    else:
        failed += 1
        print("  ❌ accounting wrong:", batched)

    # ── ordering is positional, never reordered ─────────────────────────────
    var three = (
        '{"type":"batch_execute","requests":['
        + _req("first")
        + ","
        + _req("second")
        + ","
        + _req("third")
        + "]}"
    )
    var out3 = run_batch_execute(_stub_dispatch, three, _datasets)
    var r3 = json_get_array(out3, "results")
    if (
        json_array_len(r3) == 3
        and json_array_get(r3, 0) == '{"result":"first"}'
        and json_array_get(r3, 1) == '{"result":"second"}'
        and json_array_get(r3, 2) == '{"result":"third"}'
    ):
        passed += 1
        print("  ✅ three items preserve request order")
    else:
        failed += 1
        print("  ❌ ordering not preserved:", out3)

    # ── a failing item must not sink its neighbours (partial_ok default) ─────
    var mixed = (
        '{"type":"batch_execute","requests":['
        + _req("ok_one")
        + ","
        + _req("__boom__")
        + ","
        + _req("ok_two")
        + "]}"
    )
    var out_mixed = run_batch_execute(_stub_dispatch, mixed, _datasets)
    var rm = json_get_array(out_mixed, "results")
    if (
        json_array_len(rm) == 3
        and json_get_int(out_mixed, "ok", -1) == 2
        and json_get_int(out_mixed, "failed", -1) == 1
        and response_is_error(json_array_get(rm, 1))
        and not response_is_error(json_array_get(rm, 0))
        and not response_is_error(json_array_get(rm, 2))
    ):
        passed += 1
        print("  ✅ per-item error isolation: 2 ok, 1 failed, neighbours intact")
    else:
        failed += 1
        print("  ❌ error isolation wrong:", out_mixed)

    # ── partial_ok=false stops at the first failure ──────────────────────────
    var strict = (
        '{"type":"batch_execute","partial_ok":false,"requests":['
        + _req("ok_one")
        + ","
        + _req("__boom__")
        + ","
        + _req("never_reached")
        + "]}"
    )
    var out_strict = run_batch_execute(_stub_dispatch, strict, _datasets)
    if (
        json_array_len(json_get_array(out_strict, "results")) == 2
        and json_get_int(out_strict, "count", -1) == 2
        and json_get_int(out_strict, "failed", -1) == 1
        and json_get_bool(out_strict, "stopped_early", False)
    ):
        passed += 1
        print("  ✅ partial_ok=false stops after the failing item")
    else:
        failed += 1
        print("  ❌ short-circuit wrong:", out_strict)

    # ── partial_ok=true runs every item even when one fails ─────────────────
    if not json_get_bool(out_mixed, "stopped_early", True):
        passed += 1
        print("  ✅ partial_ok default does not short-circuit")
    else:
        failed += 1
        print("  ❌ default short-circuited:", out_mixed)

    # ── a raising dispatcher is contained as a per-item error ────────────────
    var raiser = '{"type":"batch_execute","requests":[' + _req("__raise__") + "," + _req("after") + "]}"
    var out_raise = run_batch_execute(_stub_dispatch, raiser, _datasets)
    var rr = json_get_array(out_raise, "results")
    if (
        json_array_len(rr) == 2
        and response_is_error(json_array_get(rr, 0))
        and not response_is_error(json_array_get(rr, 1))
    ):
        passed += 1
        print("  ✅ a raising item is contained, later items still run")
    else:
        failed += 1
        print("  ❌ raise not contained:", out_raise)

    # ── malformed envelope is a typed frame-level error, not a crash ─────────
    var empty = run_batch_execute(_stub_dispatch, '{"type":"batch_execute"}', _datasets)
    if response_is_error(empty):
        passed += 1
        print("  ✅ missing requests array → typed error")
    else:
        failed += 1
        print("  ❌ missing requests array not rejected:", empty)

    # ── determinism: identical input, identical envelope ─────────────────────
    if run_batch_execute(_stub_dispatch, three, _datasets) == out3:
        passed += 1
        print("  ✅ deterministic across identical invocations")
    else:
        failed += 1
        print("  ❌ non-deterministic envelope")

    # ── @handle binds a resident dataset into a batch item's args ────────────
    # Regression: batch imported the session helpers but never called them, so
    # "@ds_1" reached the kernel as a literal string.
    var live = ResidentDatasets()
    var handle = json_get_string(
        live.open_from_json('{"name":"rows","value":[10.0,20.0]}'), "handle"
    )
    var bound = bind_dataset_references(
        '{"module":"stub","function":"consume","args":["@' + handle + '",2]}', live
    )
    if bound == '{"module":"stub","function":"consume","args":[[10.0,20.0],2]}':
        passed += 1
        print("  ✅ @handle bound into a batch item's args")
    else:
        failed += 1
        print("  ❌ batch @handle binding wrong:", bound)

    # ── a request with no references is returned untouched ───────────────────
    var plain = '{"module":"stub","function":"consume","args":[1,2]}'
    if bind_dataset_references(plain, live) == plain:
        passed += 1
        print("  ✅ a reference-free request is not rebuilt")
    else:
        failed += 1
        print("  ❌ reference-free request was rewritten")

    # ── an unknown handle raises rather than binding nothing ─────────────────
    var raised = False
    try:
        _ = bind_dataset_references(
            '{"module":"stub","function":"consume","args":["@ds_404"]}', live
        )
    except:
        raised = True
    if raised:
        passed += 1
        print("  ✅ unknown @handle raises instead of binding an empty value")
    else:
        failed += 1
        print("  ❌ unknown @handle silently accepted")

    # ── end-to-end through run_batch_execute, not just the helper ────────────
    var ds_batch = run_batch_execute(_stub_dispatch, 
        '{"type":"batch_execute","requests":[{"module":"stub","function":"echo_args",'
        + '"args":["@'
        + handle
        + '"]}]}',
        live,
    )
    if json_get_int(ds_batch, "ok", -1) == 1:
        passed += 1
        print("  ✅ run_batch_execute resolves @handle for real items")
    else:
        failed += 1
        print("  ❌ batch @handle not resolved end-to-end:", ds_batch)

    print("  [algenta_runtime.batch] Passed:", passed, "Failed:", failed)
