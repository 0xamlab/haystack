"""test_algenta_runtime_pipeline.mojo — known-value tests for algenta_runtime.pipeline.

Hand-written. Covers what the pipeline layer owns: `$k` reference binding, result
threading, plan-hash stability, lineage, fail-fast vs continue_on_error, and
rejection of invalid plans before anything executes.

Runs against a stub dispatcher, so it tests the DAG contract rather than kernel
maths and avoids JIT-compiling the ~100k-line generated table.
"""
from json.parser import (
    json_array_get,
    json_array_len,
    json_get_array,
    json_get_int,
    json_get_string,
)
from algenta_runtime.session import ResidentDatasets
from algenta_runtime.pipeline import (
    extract_result_json,
    plan_hash,
    run_pipeline_execute,
)


def _stub_dispatch(raw: String) raises -> String:
    """Echo the bound args so tests can prove substitution happened.

    `__boom__` fails, `double` returns 2x its first numeric arg, everything else
    returns the raw args array it received.
    """
    var function = json_get_string(raw, "function")
    if function == "__boom__":
        return (
            '{"error":"function_not_registered: nope","error_code":'
            + '"function_not_registered","error_message":"nope"}'
        )
    var args = json_get_array(raw, "args")
    if function == "double":
        var first = json_array_get(args, 0)
        return '{"result":[' + first + "," + first + "]}"
    return '{"result":' + args + "}"


def _node(function: String, args: String) -> String:
    return '{"module":"stub","function":"' + function + '","args":' + args + "}"


def main() raises:
    # Empty registry: these suites exercise the DAG/batch contract, not residency.
    var _datasets = ResidentDatasets()
    var passed = 0
    var failed = 0

    # ── extract_result_json keeps the value's exact JSON form ────────────────
    if (
        extract_result_json('{"result":2.5}') == "2.5"
        and extract_result_json('{"result":[1,2,3]}') == "[1,2,3]"
        and extract_result_json('{"result":{"a":1}}') == '{"a":1}'
        and extract_result_json('{"error":"x"}') == "null"
    ):
        passed += 1
        print("  ✅ extract_result_json preserves scalars, lists, objects")
    else:
        failed += 1
        print("  ❌ extract_result_json wrong:", extract_result_json('{"result":[1,2,3]}'))

    # ── a $k reference is substituted with the earlier node's result ─────────
    var chain = (
        '{"type":"pipeline_execute","nodes":['
        + _node("first", "[7]")
        + ","
        + _node("second", '["$0"]')
        + "]}"
    )
    var out = run_pipeline_execute(_stub_dispatch, chain, _datasets)
    # node 0 returns [7]; node 1 receives [[7]] because $0 == [7].
    if json_get_int(out, "ok", -1) == 2 and json_get_string(out, "result") == "":
        # result is a list, so json_get_string is empty — check the array instead.
        var final = json_get_array(out, "result")
        if final == "[[7]]":
            passed += 1
            print("  ✅ $0 substituted with node 0's result")
        else:
            failed += 1
            print("  ❌ substitution wrong, final =", final)
    else:
        failed += 1
        print("  ❌ chain failed:", out)

    # ── results array records every node, in order ───────────────────────────
    var results = json_get_array(out, "results")
    if json_array_len(results) == 2 and json_array_get(results, 0) == "[7]":
        passed += 1
        print("  ✅ per-node results recorded in order")
    else:
        failed += 1
        print("  ❌ results array wrong:", results)

    # ── lineage names each node and its outcome ──────────────────────────────
    var lineage = json_get_array(out, "lineage")
    if (
        json_array_len(lineage) == 2
        and json_get_string(json_array_get(lineage, 0), "function") == "first"
        and json_get_string(json_array_get(lineage, 1), "function") == "second"
        and json_get_int(json_array_get(lineage, 0), "index", -1) == 0
    ):
        passed += 1
        print("  ✅ lineage records index/module/function per node")
    else:
        failed += 1
        print("  ❌ lineage wrong:", lineage)

    # ── plan hash is stable for the same plan, different for a changed one ───
    var again = run_pipeline_execute(_stub_dispatch, chain, _datasets)
    var hash_a = json_get_string(out, "plan_hash")
    var hash_b = json_get_string(again, "plan_hash")
    var other = run_pipeline_execute(_stub_dispatch, '{"type":"pipeline_execute","nodes":[' + _node("first", "[8]") + "]}", _datasets)
    var hash_c = json_get_string(other, "plan_hash")
    if len(hash_a) == 64 and hash_a == hash_b and hash_a != hash_c:
        passed += 1
        print("  ✅ plan_hash stable for the same plan, differs for another")
    else:
        failed += 1
        print("  ❌ plan_hash wrong:", hash_a, hash_b, hash_c)

    # ── plan_hash ignores results: it identifies the computation ─────────────
    var plan_x = "[" + _node("f", "[1]") + "]"
    var plan_y = "[" + _node("g", "[1]") + "]"
    # Reordered keys and added whitespace: the same plan, differently serialised.
    var plan_x_reordered = '[{"function":"f", "module":"stub",  "args":[1]}]'
    if (
        plan_hash(plan_x) == plan_hash(plan_x)
        and plan_hash(plan_x) != plan_hash(plan_y)
        and plan_hash(plan_x) == plan_hash(plan_x_reordered)
    ):
        passed += 1
        print("  ✅ plan_hash identifies the plan, not its key order or whitespace")
    else:
        failed += 1
        print("  ❌ plan_hash not deterministic")

    # ── fail-fast is the default, and it reports where it stopped ────────────
    var failing = (
        '{"type":"pipeline_execute","nodes":['
        + _node("first", "[1]")
        + ","
        + _node("__boom__", "[]")
        + ","
        + _node("never", "[]")
        + "]}"
    )
    var out_fail = run_pipeline_execute(_stub_dispatch, failing, _datasets)
    if (
        json_get_string(out_fail, "error_code") == "pipeline_node_failed"
        and json_get_int(out_fail, "failed_index", -1) == 1
        and json_get_int(out_fail, "ok", -1) == 1
        and json_array_len(json_get_array(out_fail, "lineage")) == 2
    ):
        passed += 1
        print("  ✅ fail-fast stops at node 1 and reports failed_index")
    else:
        failed += 1
        print("  ❌ fail-fast wrong:", out_fail)

    # ── continue_on_error attempts every node ───────────────────────────────
    var lenient = (
        '{"type":"pipeline_execute","continue_on_error":true,"nodes":['
        + _node("first", "[1]")
        + ","
        + _node("__boom__", "[]")
        + ","
        + _node("third", "[3]")
        + "]}"
    )
    var out_lenient = run_pipeline_execute(_stub_dispatch, lenient, _datasets)
    if (
        json_get_int(out_lenient, "ok", -1) == 2
        and json_get_int(out_lenient, "failed", -1) == 1
        and json_get_int(out_lenient, "nodes", -1) == 3
    ):
        passed += 1
        print("  ✅ continue_on_error runs all three nodes")
    else:
        failed += 1
        print("  ❌ continue_on_error wrong:", out_lenient)

    # ── a forward reference is rejected before anything runs ────────────────
    var forward = (
        '{"type":"pipeline_execute","nodes":['
        + _node("first", '["$1"]')
        + ","
        + _node("second", "[2]")
        + "]}"
    )
    var out_forward = run_pipeline_execute(_stub_dispatch, forward, _datasets)
    if json_get_string(out_forward, "error_code") == "invalid_arguments":
        passed += 1
        print("  ✅ forward reference rejected up front")
    else:
        failed += 1
        print("  ❌ forward reference not rejected:", out_forward)

    # ── a self reference is rejected too ────────────────────────────────────
    var selfref = '{"type":"pipeline_execute","nodes":[' + _node("first", '["$0"]') + "]}"
    if json_get_string(run_pipeline_execute(_stub_dispatch, selfref, _datasets), "error_code") == (
        "invalid_arguments"
    ):
        passed += 1
        print("  ✅ self reference rejected")
    else:
        failed += 1
        print("  ❌ self reference not rejected")

    # ── empty plan is a typed error ─────────────────────────────────────────
    if json_get_string(
        run_pipeline_execute(_stub_dispatch, '{"type":"pipeline_execute"}', _datasets), "error_code"
    ) == "invalid_arguments":
        passed += 1
        print("  ✅ missing nodes array → typed error")
    else:
        failed += 1
        print("  ❌ missing nodes array not rejected")

    # ── a literal that merely looks like a reference is left alone ───────────
    var literal = '{"type":"pipeline_execute","nodes":[' + _node("first", '["$notanindex"]') + "]}"
    var out_literal = run_pipeline_execute(_stub_dispatch, literal, _datasets)
    if json_get_int(out_literal, "ok", -1) == 1:
        passed += 1
        print('  ✅ "$notanindex" treated as a literal string, not a reference')
    else:
        failed += 1
        print("  ❌ literal misparsed as reference:", out_literal)

    # ── a resident dataset binds by @handle, so the payload stays O(1) ────────
    var live = ResidentDatasets()
    var opened = live.open_from_json('{"name":"rows","value":[10.0,20.0,30.0]}')
    var handle = json_get_string(opened, "handle")
    var with_dataset = (
        '{"type":"pipeline_execute","nodes":['
        + _node("consume", '["@' + handle + '"]')
        + "]}"
    )
    var out_ds = run_pipeline_execute(_stub_dispatch, with_dataset, live)
    # The stub echoes its bound args, so the resident value must appear in them.
    if json_get_array(out_ds, "result") == "[[10.0,20.0,30.0]]":
        passed += 1
        print("  ✅ @handle binds the resident dataset into the node's args")
    else:
        failed += 1
        print("  ❌ @handle not bound:", out_ds)

    # ── an unknown handle fails loudly rather than binding nothing ────────────
    var bad_handle = (
        '{"type":"pipeline_execute","nodes":[' + _node("consume", '["@ds_404"]') + "]}"
    )
    var out_bad = run_pipeline_execute(_stub_dispatch, bad_handle, live)
    if len(json_get_string(out_bad, "error_code")) > 0:
        passed += 1
        print("  ✅ unknown @handle is an error, not a silent null")
    else:
        failed += 1
        print("  ❌ unknown handle silently accepted:", out_bad)

    print("  [algenta_runtime.pipeline] Passed:", passed, "Failed:", failed)
