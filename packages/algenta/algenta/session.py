"""Resident datasets and chunked cursors on the local runtime.

Sending a large input with every call is the cost batching cannot remove: a
100k-row array handed to twenty kernels crosses the boundary twenty times. Open it
once, reference it by handle, and per-call payload becomes O(1) in rows.

    handle = runtime.open_dataset([1.0, 2.0, 3.0], name="sales")
    runtime.execute_batch([
        {"module": "stats", "function": "median", "args": [f"@{handle}", 3]},
    ])
    for chunk in runtime.stream(handle, chunk_rows=1000):
        ...
    runtime.close_dataset(handle)

Handles and cursors are scoped to the worker connection and are never reused after
a close, so a stale reference fails cleanly instead of reading whatever took its
place.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

__all__ = ["DatasetError", "close_dataset", "list_datasets", "open_dataset", "stream_chunks"]


class DatasetError(RuntimeError):
    """A dataset or cursor operation failed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _send(
    frame: dict[str, Any],
    *,
    module_name: str,
    timeout: float,
    require_verified: bool,
) -> dict[str, Any]:
    from algenta.native import worker

    try:
        response = worker.execute(
            frame,
            timeout=timeout,
            require_verified=require_verified,
            module_name=module_name,
        )
    except worker.NativeWorkerUnavailable as exc:
        raise DatasetError("compute_runtime_unavailable", str(exc)) from exc

    code = response.get("error_code")
    if isinstance(code, str) and code:
        raise DatasetError(code, str(response.get("error_message") or response.get("error") or ""))
    return response


def open_dataset(
    value: Any,
    *,
    name: str = "",
    routing_module: str,
    timeout: float,
    require_verified: bool,
) -> str:
    """Make `value` resident in the worker and return its handle.

    `routing_module` picks the shard the dataset lives in. A handle is only valid
    for that worker, so it must be a module the later calls also use.
    """
    response = _send(
        {"type": "dataset_open", "engine_type": "dataset_open", "name": name, "value": value},
        module_name=routing_module,
        timeout=timeout,
        require_verified=require_verified,
    )
    handle = response.get("handle")
    if not isinstance(handle, str) or not handle:
        raise DatasetError("mojo_result_parse_failed", f"dataset_open returned {response!r}")
    return handle


def close_dataset(
    handle: str,
    *,
    routing_module: str,
    timeout: float,
    require_verified: bool,
) -> bool:
    response = _send(
        {"type": "dataset_close", "engine_type": "dataset_close", "handle": handle},
        module_name=routing_module,
        timeout=timeout,
        require_verified=require_verified,
    )
    return bool(response.get("closed"))


def list_datasets(
    *,
    routing_module: str,
    timeout: float,
    require_verified: bool,
) -> dict[str, Any]:
    return _send(
        {"type": "dataset_list", "engine_type": "dataset_list"},
        module_name=routing_module,
        timeout=timeout,
        require_verified=require_verified,
    )


def stream_chunks(
    handle: str,
    *,
    routing_module: str,
    timeout: float,
    require_verified: bool,
    chunk_rows: int | None = None,
) -> Iterator[list[Any]]:
    """Yield the dataset in chunks, pulling the next one only when asked.

    A generator, deliberately: the caller's next iteration is the credit, so an
    early `break` leaves the remainder unencoded. The cursor is closed on exit —
    including on an early break or an exception — so it cannot leak.
    """
    open_frame: dict[str, Any] = {
        "type": "stream_open",
        "engine_type": "stream_open",
        "handle": handle,
    }
    if chunk_rows is not None:
        open_frame["chunk_rows"] = chunk_rows
    opened = _send(
        open_frame,
        module_name=routing_module,
        timeout=timeout,
        require_verified=require_verified,
    )
    cursor = opened.get("cursor")
    if not isinstance(cursor, str) or not cursor:
        raise DatasetError("mojo_result_parse_failed", f"stream_open returned {opened!r}")

    try:
        while True:
            page = _send(
                {"type": "stream_next", "engine_type": "stream_next", "cursor": cursor},
                module_name=routing_module,
                timeout=timeout,
                require_verified=require_verified,
            )
            chunk = page.get("chunk") or []
            if not chunk:
                return
            yield list(chunk)
            if page.get("done"):
                return
    finally:
        try:
            _send(
                {"type": "stream_close", "engine_type": "stream_close", "cursor": cursor},
                module_name=routing_module,
                timeout=timeout,
                require_verified=require_verified,
            )
        except DatasetError:
            # The connection may already be gone; a leaked cursor dies with it.
            pass
