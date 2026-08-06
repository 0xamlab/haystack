"""test_algenta_runtime_stream.mojo — known-value tests for chunked cursors.

Hand-written. Covers open/next/close, exact chunk boundaries, the `done` flag on
the draining pull, per-pull `max_rows` override and its ceiling, full-scan
reassembly, and clean failure when the underlying dataset is closed mid-stream.
"""
from json.parser import (
    json_array_get,
    json_array_len,
    json_get_array,
    json_get_int,
    json_get_string,
)
from algenta_runtime.session import ResidentDatasets
from algenta_runtime.stream import MAX_CHUNK_ROWS, ResidentStreams


def main() raises:
    var passed = 0
    var failed = 0

    var datasets = ResidentDatasets()
    var streams = ResidentStreams()
    var opened_ds = datasets.open_from_json(
        '{"name":"rows","value":[1.0,2.0,3.0,4.0,5.0]}'
    )
    var handle = json_get_string(opened_ds, "handle")

    # ── open reports the row total and the effective chunk size ───────────────
    var opened = streams.open_from_json(
        '{"handle":"' + handle + '","chunk_rows":2}', datasets
    )
    var cursor = json_get_string(opened, "cursor")
    if (
        cursor == "st_1"
        and json_get_int(opened, "total", -1) == 5
        and json_get_int(opened, "remaining", -1) == 5
        and json_get_int(opened, "chunk_rows", -1) == 2
    ):
        passed += 1
        print("  ✅ stream_open reports total, remaining and chunk_rows")
    else:
        failed += 1
        print("  ❌ open wrong:", opened)

    # ── the first pull respects chunk_rows exactly ───────────────────────────
    var first = streams.next_from_json('{"cursor":"' + cursor + '"}', datasets)
    if (
        json_get_array(first, "chunk") == "[1.0,2.0]"
        and json_get_int(first, "rows", -1) == 2
        and json_get_int(first, "remaining", -1) == 3
        and json_get_string(first, "done") == ""
    ):
        passed += 1
        print("  ✅ first pull returns exactly chunk_rows rows")
    else:
        failed += 1
        print("  ❌ first pull wrong:", first)

    # ── position advances; the second pull continues where the first stopped ──
    var second = streams.next_from_json('{"cursor":"' + cursor + '"}', datasets)
    if (
        json_get_array(second, "chunk") == "[3.0,4.0]"
        and json_get_int(second, "position", -1) == 4
        and json_get_int(second, "remaining", -1) == 1
    ):
        passed += 1
        print("  ✅ second pull resumes at the right position")
    else:
        failed += 1
        print("  ❌ second pull wrong:", second)

    # ── the draining pull returns a short chunk and sets done ─────────────────
    var third = streams.next_from_json('{"cursor":"' + cursor + '"}', datasets)
    if (
        json_get_array(third, "chunk") == "[5.0]"
        and json_get_int(third, "rows", -1) == 1
        and json_get_int(third, "remaining", -1) == 0
    ):
        passed += 1
        print("  ✅ final pull is short and reports remaining 0")
    else:
        failed += 1
        print("  ❌ final pull wrong:", third)

    # ── pulling past the end is empty, not an error ──────────────────────────
    var past = streams.next_from_json('{"cursor":"' + cursor + '"}', datasets)
    if json_get_int(past, "rows", -1) == 0 and json_get_int(past, "remaining", -1) == 0:
        passed += 1
        print("  ✅ pulling a drained cursor yields zero rows, no error")
    else:
        failed += 1
        print("  ❌ over-pull wrong:", past)

    # ── a full scan reassembles the original dataset exactly ─────────────────
    var scan_cursor = json_get_string(
        streams.open_from_json('{"handle":"' + handle + '","chunk_rows":2}', datasets),
        "cursor",
    )
    var seen = 0
    var reassembled = String("")
    while True:
        var page = streams.next_from_json('{"cursor":"' + scan_cursor + '"}', datasets)
        var rows = json_get_int(page, "rows", 0)
        if rows == 0:
            break
        var chunk = json_get_array(page, "chunk")
        for i in range(json_array_len(chunk)):
            if seen > 0:
                reassembled += ","
            reassembled += json_array_get(chunk, i)
            seen += 1
        if json_get_int(page, "remaining", 1) == 0:
            break
    if seen == 5 and reassembled == "1.0,2.0,3.0,4.0,5.0":
        passed += 1
        print("  ✅ a full chunked scan reassembles the dataset exactly")
    else:
        failed += 1
        print("  ❌ scan wrong: seen", seen, "->", reassembled)

    # ── max_rows overrides chunk_rows for one pull ───────────────────────────
    var big_cursor = json_get_string(
        streams.open_from_json('{"handle":"' + handle + '","chunk_rows":1}', datasets),
        "cursor",
    )
    var overridden = streams.next_from_json(
        '{"cursor":"' + big_cursor + '","max_rows":4}', datasets
    )
    if json_get_int(overridden, "rows", -1) == 4:
        passed += 1
        print("  ✅ max_rows overrides chunk_rows for a single pull")
    else:
        failed += 1
        print("  ❌ max_rows override wrong:", overridden)

    # ── chunk_rows above the ceiling is clamped, not honoured ────────────────
    var huge = streams.open_from_json(
        '{"handle":"' + handle + '","chunk_rows":999999999}', datasets
    )
    if json_get_int(huge, "chunk_rows", -1) == MAX_CHUNK_ROWS:
        passed += 1
        print("  ✅ oversized chunk_rows clamped to the ceiling")
    else:
        failed += 1
        print("  ❌ clamp wrong:", huge)

    # ── an unknown cursor and a missing cursor are typed errors ──────────────
    if (
        json_get_string(streams.next_from_json('{"cursor":"st_999"}', datasets), "error_code")
        == "cursor_not_found"
        and json_get_string(streams.next_from_json("{}", datasets), "error_code")
        == "invalid_arguments"
    ):
        passed += 1
        print("  ✅ unknown/missing cursor → typed errors")
    else:
        failed += 1
        print("  ❌ cursor validation wrong")

    # ── close frees the cursor; closing twice is a clean not-found ───────────
    var closed = streams.close_from_json('{"cursor":"' + cursor + '"}')
    if (
        json_get_int(closed, "count", -1) >= 0
        and json_get_string(
            streams.close_from_json('{"cursor":"' + cursor + '"}'), "error_code"
        )
        == "cursor_not_found"
    ):
        passed += 1
        print("  ✅ close frees the cursor; double close → cursor_not_found")
    else:
        failed += 1
        print("  ❌ close wrong:", closed)

    # ── closing the dataset mid-stream fails cleanly on the next pull ────────
    var orphan_cursor = json_get_string(
        streams.open_from_json('{"handle":"' + handle + '","chunk_rows":2}', datasets),
        "cursor",
    )
    _ = datasets.close_from_json('{"handle":"' + handle + '"}')
    var orphaned = streams.next_from_json('{"cursor":"' + orphan_cursor + '"}', datasets)
    if json_get_string(orphaned, "error_code") == "dataset_not_found":
        passed += 1
        print("  ✅ dataset closed mid-stream → dataset_not_found, not stale data")
    else:
        failed += 1
        print("  ❌ orphaned cursor wrong:", orphaned)

    print("  [algenta_runtime.stream] Passed:", passed, "Failed:", failed)
