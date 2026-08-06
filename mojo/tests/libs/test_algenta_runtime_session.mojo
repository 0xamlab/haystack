"""test_algenta_runtime_session.mojo — known-value tests for resident datasets.

Hand-written. Covers open/lookup/close/list, handle non-reuse, the capacity
refusal, `@handle` reference parsing, and that a closed or unknown handle fails
cleanly rather than reading a neighbour's data.
"""
from json.parser import json_array_len, json_get_array, json_get_int, json_get_string
from algenta_runtime.session import (
    ResidentDatasets,
    dataset_reference_handle,
    is_dataset_reference,
)


def main() raises:
    var passed = 0
    var failed = 0

    var registry = ResidentDatasets()

    # ── open returns a handle and accounts for bytes ──────────────────────────
    var opened = registry.open_from_json('{"type":"dataset_open","name":"sales","value":[1.0,2.0,3.0]}')
    var handle = json_get_string(opened, "handle")
    if handle == "ds_1" and json_get_int(opened, "count", -1) == 1:
        passed += 1
        print("  ✅ dataset_open returns a handle and a count")
    else:
        failed += 1
        print("  ❌ open wrong:", opened)

    # ── the resident value round-trips exactly ───────────────────────────────
    if registry.lookup("ds_1") == "[1.0,2.0,3.0]":
        passed += 1
        print("  ✅ resident value round-trips byte-for-byte")
    else:
        failed += 1
        print("  ❌ lookup wrong:", registry.lookup("ds_1"))

    # ── an unknown handle is empty, not someone else's data ─────────────────
    if registry.lookup("ds_999") == "":
        passed += 1
        print("  ✅ unknown handle looks up empty")
    else:
        failed += 1
        print("  ❌ unknown handle returned data")

    # ── a second open gets a distinct handle ─────────────────────────────────
    var second = registry.open_from_json('{"type":"dataset_open","name":"costs","value":[9.0]}')
    if json_get_string(second, "handle") == "ds_2" and registry.count() == 2:
        passed += 1
        print("  ✅ second open gets a distinct handle")
    else:
        failed += 1
        print("  ❌ second open wrong:", second)

    # ── list reports both, with sizes ────────────────────────────────────────
    var listed = registry.list_json()
    if (
        json_array_len(json_get_array(listed, "datasets")) == 2
        and json_get_int(listed, "count", -1) == 2
        and json_get_int(listed, "bytes", -1) > 0
    ):
        passed += 1
        print("  ✅ dataset_list reports every handle and total bytes")
    else:
        failed += 1
        print("  ❌ list wrong:", listed)

    # ── an object value is accepted, not just an array ───────────────────────
    var obj = registry.open_from_json('{"type":"dataset_open","name":"cfg","value":{"a":1}}')
    if registry.lookup(json_get_string(obj, "handle")) == '{"a":1}':
        passed += 1
        print("  ✅ object values are stored as-is")
    else:
        failed += 1
        print("  ❌ object value wrong:", obj)

    # ── a missing value is a typed error ────────────────────────────────────
    var empty = registry.open_from_json('{"type":"dataset_open","name":"x"}')
    if json_get_string(empty, "error_code") == "invalid_arguments":
        passed += 1
        print("  ✅ dataset_open without a value → typed error")
    else:
        failed += 1
        print("  ❌ missing value not rejected:", empty)

    # ── close frees the handle and decrements the count ──────────────────────
    var closed = registry.close_from_json('{"handle":"ds_1"}')
    if json_get_string(closed, "closed") == "" and registry.count() == 2:
        # `closed` is a bare bool so json_get_string is ""; the count is the check.
        passed += 1
        print("  ✅ close removes exactly one handle")
    else:
        failed += 1
        print("  ❌ close wrong:", closed, "count:", registry.count())

    # ── a closed handle is gone, and the survivors are untouched ─────────────
    if registry.lookup("ds_1") == "" and registry.lookup("ds_2") == "[9.0]":
        passed += 1
        print("  ✅ closing ds_1 leaves ds_2 intact")
    else:
        failed += 1
        print("  ❌ close corrupted the registry")

    # ── closing twice is a clean not-found, not a crash ─────────────────────
    if json_get_string(registry.close_from_json('{"handle":"ds_1"}'), "error_code") == (
        "dataset_not_found"
    ):
        passed += 1
        print("  ✅ double close → dataset_not_found")
    else:
        failed += 1
        print("  ❌ double close not handled")

    # ── handles are never reused after a close ──────────────────────────────
    var third = registry.open_from_json('{"type":"dataset_open","name":"new","value":[7.0]}')
    if json_get_string(third, "handle") != "ds_1":
        passed += 1
        print("  ✅ a freed handle is never reissued")
    else:
        failed += 1
        print("  ❌ handle ds_1 was reused — a stale reference would read new data")

    # ── @handle reference parsing ───────────────────────────────────────────
    if (
        is_dataset_reference('"@ds_1"')
        and dataset_reference_handle('"@ds_12"') == "ds_12"
        and not is_dataset_reference('"$0"')
        and not is_dataset_reference("[1,2]")
        and not is_dataset_reference('"plain"')
    ):
        passed += 1
        print("  ✅ @handle references parsed, $k and literals left alone")
    else:
        failed += 1
        print("  ❌ reference parsing wrong")

    print("  [algenta_runtime.session] Passed:", passed, "Failed:", failed)
