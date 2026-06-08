from __future__ import annotations

import io
import os
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager

_KNOWN_CPU_INFO_NEEDLE = "arrow/util/cpu_info.cc:"
_KNOWN_CPU_INFO_DETAIL = "IOError: sysctlbyname failed for 'hw."
_KNOWN_CPU_INFO_PERMISSION = "Operation not permitted"

_STDERR_FILTER_LOCK = threading.RLock()
_PARQUET_INIT_LOCK = threading.Lock()
_PARQUET_RUNTIME_READY = False


def _is_known_pyarrow_cpu_info_warning(line: str) -> bool:
    return (
        _KNOWN_CPU_INFO_NEEDLE in line
        and _KNOWN_CPU_INFO_DETAIL in line
        and _KNOWN_CPU_INFO_PERMISSION in line
    )


def _filter_known_pyarrow_cpu_info_warnings(text: str) -> str:
    if not text:
        return ""
    return "".join(
        line
        for line in text.splitlines(keepends=True)
        if not _is_known_pyarrow_cpu_info_warning(line)
    )


@contextmanager
def suppress_known_pyarrow_cpu_info_warnings() -> Iterator[None]:
    """
    Capture stderr temporarily and drop only the known Arrow CPU-info noise.

    This is intentionally narrow: any other stderr output is replayed unchanged.
    """
    if os.name != "posix":
        yield
        return

    sys.stderr.flush()
    with _STDERR_FILTER_LOCK:
        read_fd, write_fd = os.pipe()
        saved_stderr_fd = os.dup(2)
        try:
            os.dup2(write_fd, 2)
            os.close(write_fd)
            yield
        finally:
            sys.stderr.flush()
            os.dup2(saved_stderr_fd, 2)
            os.close(saved_stderr_fd)

            chunks: list[bytes] = []
            while True:
                chunk = os.read(read_fd, 65536)
                if not chunk:
                    break
                chunks.append(chunk)
            os.close(read_fd)

            if chunks:
                filtered = _filter_known_pyarrow_cpu_info_warnings(
                    b"".join(chunks).decode(errors="replace")
                )
                if filtered:
                    os.write(2, filtered.encode())


def _prime_pyarrow_parquet_runtime() -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    buffer = io.BytesIO()
    pq.write_table(pa.table({"_algenta_init": [1]}), buffer)
    buffer.seek(0)
    pq.read_table(buffer)


def initialize_pyarrow_parquet_runtime() -> None:
    """
    Trigger Arrow parquet runtime initialization once under filtered stderr.

    On some macOS sandboxed environments Arrow emits a burst of benign
    `cpu_info.cc` sysctl warnings during the first parquet read. Prime that
    initialization once and keep all subsequent parquet reads warning-free.
    """
    global _PARQUET_RUNTIME_READY

    if _PARQUET_RUNTIME_READY:
        return

    with _PARQUET_INIT_LOCK:
        if _PARQUET_RUNTIME_READY:
            return
        with suppress_known_pyarrow_cpu_info_warnings():
            _prime_pyarrow_parquet_runtime()
        _PARQUET_RUNTIME_READY = True
