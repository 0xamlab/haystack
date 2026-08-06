"""test_algenta_runtime_resources.mojo — known-value tests for execution budgets.

Hand-written. Covers parsing (absent/partial/zero fields), the accounting of each
dimension, the ordering guarantee that `exceeded()` fires only before unauthorised
work, and the shape of the typed envelope.
"""
from json.parser import json_get_int, json_get_object, json_get_string
from algenta_runtime.resources import (
    Budget,
    budget_exceeded_json,
    parse_budget,
)


def main() raises:
    var passed = 0
    var failed = 0

    # ── an absent budget means unlimited on every dimension ──────────────────
    var none_budget = parse_budget('{"type":"batch_execute","requests":[]}')
    if (
        none_budget.deadline_ns == 0
        and none_budget.max_ops == 0
        and none_budget.max_result_bytes == 0
        and none_budget.exceeded() == ""
    ):
        passed += 1
        print("  ✅ absent budget is unlimited")
    else:
        failed += 1
        print("  ❌ absent budget not unlimited")

    # ── fields are read, and ms is converted to ns ───────────────────────────
    var full = parse_budget(
        '{"budget":{"deadline_ms":250,"max_ops":7,"max_result_bytes":4096}}'
    )
    if (
        full.deadline_ns == 250_000_000
        and full.max_ops == 7
        and full.max_result_bytes == 4096
    ):
        passed += 1
        print("  ✅ deadline_ms/max_ops/max_result_bytes parsed, ms→ns converted")
    else:
        failed += 1
        print("  ❌ parse wrong:", full.deadline_ns, full.max_ops, full.max_result_bytes)

    # ── a partial budget leaves the other dimensions unlimited ───────────────
    var partial = parse_budget('{"budget":{"max_ops":3}}')
    if partial.max_ops == 3 and partial.deadline_ns == 0 and partial.max_result_bytes == 0:
        passed += 1
        print("  ✅ partial budget constrains only what it names")
    else:
        failed += 1
        print("  ❌ partial budget wrong")

    # ── zero and negative are treated as unlimited, not as "stop immediately" ─
    var zeroes = parse_budget('{"budget":{"deadline_ms":0,"max_ops":-5}}')
    if zeroes.deadline_ns == 0 and zeroes.max_ops == 0 and zeroes.exceeded() == "":
        passed += 1
        print("  ✅ zero/negative fields mean unlimited")
    else:
        failed += 1
        print("  ❌ zero/negative not unlimited:", zeroes.exceeded())

    # ── max_ops fires only once the allowance is spent ───────────────────────
    var ops = parse_budget('{"budget":{"max_ops":2}}')
    var before = ops.exceeded()
    ops.record(10)
    var after_one = ops.exceeded()
    ops.record(10)
    var after_two = ops.exceeded()
    if before == "" and after_one == "" and after_two == "max_ops":
        passed += 1
        print("  ✅ max_ops fires after the allowance is spent, not before")
    else:
        failed += 1
        print("  ❌ max_ops timing wrong:", before, after_one, after_two)

    # ── max_result_bytes accumulates across operations ───────────────────────
    var bytes_budget = parse_budget('{"budget":{"max_result_bytes":100}}')
    bytes_budget.record(60)
    var mid = bytes_budget.exceeded()
    bytes_budget.record(60)
    if mid == "" and bytes_budget.exceeded() == "max_result_bytes":
        passed += 1
        print("  ✅ max_result_bytes accumulates and then fires")
    else:
        failed += 1
        print("  ❌ byte accounting wrong:", mid, bytes_budget.exceeded())

    # ── an already-elapsed deadline is reported as the deadline dimension ────
    # Backdate the start instead of sleeping: relying on real elapsed time makes
    # the assertion depend on clock resolution, which is 0 ns between two adjacent
    # perf_counter_ns() reads on this machine.
    var expired = Budget()
    expired.deadline_ns = 1_000_000  # 1 ms
    expired.started_ns -= 5_000_000  # started 5 ms ago
    if expired.exceeded() == "deadline_ms":
        passed += 1
        print("  ✅ elapsed deadline reported as deadline_ms")
    else:
        failed += 1
        print("  ❌ deadline not detected:", expired.exceeded())

    # ── consumed_json reports what was actually spent ───────────────────────
    var spent = parse_budget('{"budget":{"max_ops":9}}')
    spent.record(42)
    spent.record(8)
    var consumed = spent.consumed_json()
    if json_get_int(consumed, "ops", -1) == 2 and json_get_int(consumed, "result_bytes", -1) == 50:
        passed += 1
        print("  ✅ consumed_json reports ops and result_bytes")
    else:
        failed += 1
        print("  ❌ consumed_json wrong:", consumed)

    # ── the typed envelope names the dimension and carries the partial work ──
    var envelope = budget_exceeded_json("max_ops", '[{"result":1}]', '{"ops":1}')
    if (
        json_get_string(envelope, "error_code") == "budget_exceeded"
        and json_get_string(envelope, "exceeded") == "max_ops"
        and len(json_get_object(envelope, "consumed")) > 0
    ):
        passed += 1
        print("  ✅ budget_exceeded envelope names the dimension and keeps partial work")
    else:
        failed += 1
        print("  ❌ envelope wrong:", envelope)

    print("  [algenta_runtime.resources] Passed:", passed, "Failed:", failed)
