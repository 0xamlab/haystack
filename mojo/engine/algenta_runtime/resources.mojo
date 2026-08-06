"""
algenta_runtime.resources — in-request execution budgets. Zero Python.

Why in-request
--------------
The worker's server loop accepts one connection and reads frames sequentially
(main.mojo `run_server_loop`). While a kernel computes, nothing is reading the
socket — so an out-of-band "cancel" frame would just sit in the buffer until the
work it was meant to stop had already finished. Cancellation therefore cannot be
a separate message; the budget has to travel with the request and be checked from
inside the work.

Today the only backstop is the client-side socket deadline, which on the pool path
marks the worker unhealthy and replaces it. That kills a process to stop a
computation, and the Mojo side is never told to stop. A `Budget` gives the coarse
entry points a cooperative alternative: they check at item and node boundaries and
return a typed `budget_exceeded` envelope naming what ran out, with whatever
partial work completed.

Budgets are advisory-but-enforced: a kernel already running is never interrupted
mid-call (nothing here can preempt it), so granularity is one item or one node.
That is the right granularity for the coarse layer, where the pathological case is
"a 10,000-item batch" rather than "one pathological kernel".

Wire format
-----------
Any coarse request may carry a `budget` object; every field is optional and an
absent or non-positive field means unlimited:

    {"type":"batch_execute","requests":[...],
     "budget":{"deadline_ms":250,"max_ops":100,"max_result_bytes":1048576}}

`deadline_ms` is a duration from the moment the budget is created, not a wall-clock
instant, so no clock synchronisation between caller and worker is required.
"""
from std.time import perf_counter_ns

from json.parser import json_get_int, json_get_object

alias NS_PER_MS = 1_000_000


struct Budget(Copyable, Movable):
    """Execution limits for one coarse request, with the clock already started.

    Zero means unlimited for each dimension. `started_ns` is captured at
    construction, so `deadline_ms` measures from when the worker began the request.
    """

    var deadline_ns: Int
    var max_ops: Int
    var max_result_bytes: Int
    var started_ns: Int
    var ops_used: Int
    var result_bytes_used: Int

    def __init__(out self):
        self.deadline_ns = 0
        self.max_ops = 0
        self.max_result_bytes = 0
        self.started_ns = Int(perf_counter_ns())
        self.ops_used = 0
        self.result_bytes_used = 0

    def elapsed_ns(self) -> Int:
        return Int(perf_counter_ns()) - self.started_ns

    def record(mut self, result_bytes: Int):
        """Account for one completed operation."""
        self.ops_used += 1
        self.result_bytes_used += result_bytes

    def exceeded(self) -> String:
        """Name of the exhausted dimension, or "" while the budget still holds.

        Checked *before* starting the next item, so a budget can never be blamed
        for work it did not authorise.
        """
        if self.deadline_ns > 0 and self.elapsed_ns() >= self.deadline_ns:
            return "deadline_ms"
        if self.max_ops > 0 and self.ops_used >= self.max_ops:
            return "max_ops"
        if self.max_result_bytes > 0 and self.result_bytes_used >= self.max_result_bytes:
            return "max_result_bytes"
        return ""

    def consumed_json(self) -> String:
        """What this budget actually spent, for the caller to inspect."""
        return (
            '{"elapsed_ms":'
            + String(self.elapsed_ns() // NS_PER_MS)
            + ',"ops":'
            + String(self.ops_used)
            + ',"result_bytes":'
            + String(self.result_bytes_used)
            + "}"
        )


def parse_budget(raw: String) -> Budget:
    """Read a `budget` object from a coarse request. Absent means unlimited."""
    var budget = Budget()
    var spec = json_get_object(raw, "budget")
    if len(spec) == 0:
        return budget^

    var deadline_ms = json_get_int(spec, "deadline_ms", 0)
    if deadline_ms > 0:
        budget.deadline_ns = deadline_ms * NS_PER_MS

    var max_ops = json_get_int(spec, "max_ops", 0)
    if max_ops > 0:
        budget.max_ops = max_ops

    var max_result_bytes = json_get_int(spec, "max_result_bytes", 0)
    if max_result_bytes > 0:
        budget.max_result_bytes = max_result_bytes

    return budget^


def budget_exceeded_json(
    dimension: String,
    partial: String,
    consumed: String,
) -> String:
    """Typed envelope for a stopped-early request, including the partial work.

    The partial result is returned rather than discarded: a caller that asked for
    250 ms of work should get the 250 ms of work, not just an error.
    """
    return (
        '{"error":"budget_exceeded: '
        + dimension
        + ' exhausted","error_code":"budget_exceeded","error_message":"'
        + dimension
        + ' exhausted","exceeded":"'
        + dimension
        + '","partial":'
        + partial
        + ',"consumed":'
        + consumed
        + "}"
    )
