"""Batched kernel execution over the local bundled runtime.

`execute(module, function, args)` carries one call per frame. Frame I/O dominates
a small kernel call, so a workflow of N kernels pays N round trips even when the
compute is sub-microsecond. `execute_batch` sends them together.

Shard routing is the wrinkle. The runtime is shipped as module-routed shards
(`runtime-shards.json`), and a worker only contains its own modules — so a batch
is only valid within one shard. Requests are therefore grouped by owning worker,
one frame per group, then reassembled into the caller's original order. For the
common case of a workflow over related modules that is a single frame; in the
worst case it degrades to one frame per shard, never worse than unbatched.

Argument validation and result decoding go through the same
`runtime_library_transport` helpers as the unary path, so a batched call and a
single call agree by construction.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any

__all__ = ["BatchItem", "execute_batch"]


class BatchItem(dict):
    """One request in a batch: module, function, and args.

    A plain dict subclass so callers can pass literals
    (`{"module": "stats", "function": "median", "args": [[1.0], 1]}`) or this
    class interchangeably.
    """

    def __init__(self, module: str, function: str, args: Any = None) -> None:
        super().__init__(module=module, function=function, args=args)


def _routing_worker(
    module: str,
    *,
    require_verified: bool,
    memo: dict[str, str],
) -> str:
    """Filesystem path of the worker that owns `module`, memoised per batch.

    Resolution is not free — it re-reads and re-validates the shard map — and a
    batch is usually many calls into a handful of modules. Resolving per item made
    routing cost more than the frames the batch was saving.
    """
    cached = memo.get(module)
    if cached is not None:
        return cached
    from algenta.native import worker

    resolved = str(
        worker.require_worker(module_name=module, require_verified=require_verified).path
    )
    memo[module] = resolved
    return resolved


def _failure(code: str, message: str, latency_ms: float) -> dict[str, Any]:
    return {
        "result": None,
        "success": False,
        "error": message,
        "error_code": code,
        "latency_ms": latency_ms,
    }


def execute_batch(
    items: list[dict[str, Any]],
    *,
    timeout: float = 60.0,
    partial_ok: bool = True,
    require_verified: bool = False,
) -> dict[str, Any]:
    """Execute every item, returning results in the caller's order.

    Returns `{"results": [...], "count": n, "ok": k, "failed": m,
    "frames": f, "latency_ms": t}` where each entry mirrors the unary
    `execute()` envelope, so per-item failures never sink their neighbours.

    `partial_ok=False` stops a shard group at its first failing item; items never
    attempted are reported with `not_executed`.
    """
    from algenta.native import worker
    from algenta.runtime_library_contract import RuntimeLibraryContractError
    from algenta.runtime_library_transport import build_worker_request, parse_worker_response

    started = perf_counter()
    if not items:
        return {
            "results": [],
            "count": 0,
            "ok": 0,
            "failed": 0,
            "frames": 0,
            "latency_ms": 0.0,
        }

    results: list[dict[str, Any] | None] = [None] * len(items)
    # worker path -> [(original index, request, module_spec, function_spec)]
    groups: dict[str, list[tuple[int, dict[str, Any], Any, Any]]] = {}
    route_memo: dict[str, str] = {}

    for index, item in enumerate(items):
        module = str(item.get("module", ""))
        function = str(item.get("function", ""))
        try:
            module_spec, function_spec, request = build_worker_request(
                module, function, item.get("args")
            )
        except RuntimeLibraryContractError as exc:
            # Contract violations are decided locally; they never reach a worker.
            results[index] = _failure(exc.code, str(exc), 0.0)
            continue

        try:
            route = _routing_worker(
                module, require_verified=require_verified, memo=route_memo
            )
        except worker.NativeWorkerUnavailable as exc:
            results[index] = _failure("compute_runtime_unavailable", str(exc), 0.0)
            continue

        groups.setdefault(route, []).append((index, request, module_spec, function_spec))

    frames = 0
    for entries in groups.values():
        frame = {
            "type": "batch_execute",
            "engine_type": "batch_execute",
            "requests": [request for _index, request, _m, _f in entries],
            "partial_ok": partial_ok,
        }
        routing_module = str(entries[0][1].get("module", ""))
        try:
            envelope = worker.execute(
                frame,
                timeout=timeout,
                require_verified=require_verified,
                module_name=routing_module,
            )
            frames += 1
        except worker.NativeWorkerUnavailable as exc:
            for index, _request, _m, _f in entries:
                results[index] = _failure("compute_runtime_unavailable", str(exc), 0.0)
            continue

        raw_results = envelope.get("results")
        if not isinstance(raw_results, list):
            message = str(envelope.get("error_message") or envelope.get("error") or envelope)
            code = str(envelope.get("error_code") or "mojo_library_execution_failed")
            for index, _request, _m, _f in entries:
                results[index] = _failure(code, message, 0.0)
            continue

        for position, (index, _request, module_spec, function_spec) in enumerate(entries):
            if position >= len(raw_results):
                results[index] = _failure(
                    "not_executed",
                    "Batch stopped before this item ran (partial_ok=False).",
                    0.0,
                )
                continue
            item_response = raw_results[position]
            if not isinstance(item_response, dict):
                results[index] = _failure(
                    "mojo_result_parse_failed",
                    f"Malformed batch item response: {item_response!r}",
                    0.0,
                )
                continue
            error_code = item_response.get("error_code")
            if isinstance(error_code, str) and error_code:
                results[index] = _failure(
                    error_code,
                    str(item_response.get("error_message") or item_response.get("error") or ""),
                    0.0,
                )
                continue
            try:
                results[index] = {
                    "result": parse_worker_response(module_spec, function_spec, item_response),
                    "success": True,
                    "error": "",
                    "latency_ms": 0.0,
                }
            except RuntimeLibraryContractError as exc:
                results[index] = _failure(exc.code, str(exc), 0.0)

    # Any slot still unset means the worker returned fewer entries than requested.
    for index, entry in enumerate(results):
        if entry is None:
            results[index] = _failure(
                "not_executed",
                "Worker returned no response for this item.",
                0.0,
            )

    resolved = [entry for entry in results if entry is not None]
    ok = sum(1 for entry in resolved if entry.get("success"))
    return {
        "results": resolved,
        "count": len(resolved),
        "ok": ok,
        "failed": len(resolved) - ok,
        "frames": frames,
        "latency_ms": round((perf_counter() - started) * 1000, 3),
    }
