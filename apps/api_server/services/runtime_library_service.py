from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from apps.api_server.compute.mojo_errors import MojoEngineError
from apps.api_server.compute.mojo_pool import get_pool_sync, invoke_via_pool
from apps.runtime.mojo_library_runner import (
    MojoLibraryError,
    build_runtime_library_worker_request,
    library_runtime_available,
    parse_runtime_library_worker_response,
    runtime_library_modules,
)


@dataclass(frozen=True)
class RuntimeLibraryDescriptor:
    name: str
    engine: str
    functions: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeLibraryHealth:
    status: str
    engine: str
    module_count: int
    runtime_available: bool


@dataclass(frozen=True)
class RuntimeLibraryExecutionResult:
    module: str
    function: str
    result: Any
    latency_ms: float
    engine_used: str
    request_id: str | None


def _runtime_engine() -> str:
    return "mojo" if _runtime_worker_available() else "unavailable"


def _runtime_worker_available() -> bool:
    if not library_runtime_available():
        return False
    try:
        return get_pool_sync().running
    except Exception:
        return False


def _matches_query(descriptor: RuntimeLibraryDescriptor, query: str | None) -> bool:
    if query is None:
        return True
    normalized_query = query.strip().lower()
    if not normalized_query:
        return True
    if normalized_query in descriptor.name.lower():
        return True
    return any(normalized_query in function.lower() for function in descriptor.functions)


def list_public_runtime_library_descriptors(
    *,
    query: str | None = None,
) -> tuple[RuntimeLibraryDescriptor, ...]:
    engine = _runtime_engine()
    descriptors = []
    for module in runtime_library_modules():
        descriptor = RuntimeLibraryDescriptor(
            name=str(module.import_path),
            engine=engine,
            functions=tuple(sorted(function.name for function in module.functions)),
        )
        if _matches_query(descriptor, query):
            descriptors.append(descriptor)
    descriptors.sort(key=lambda item: item.name)
    return tuple(descriptors)


def get_public_runtime_library_health() -> RuntimeLibraryHealth:
    descriptors = list_public_runtime_library_descriptors()
    runtime_available = _runtime_engine() == "mojo"
    return RuntimeLibraryHealth(
        status="ok" if runtime_available else "unavailable",
        engine="mojo" if runtime_available else "unavailable",
        module_count=len(descriptors),
        runtime_available=runtime_available,
    )


async def execute_public_runtime_library(
    *,
    module: str,
    function: str,
    args: Any = None,
    request_id: str | None = None,
) -> RuntimeLibraryExecutionResult:
    started = time.monotonic()
    function_spec, payload = build_runtime_library_worker_request(module, function, args)
    try:
        raw = await invoke_via_pool(payload)
    except MojoEngineError as exc:
        raise MojoLibraryError(
            "compute_runtime_unavailable",
            (
                f"Compiled Mojo worker execution is unavailable for {module}.{function}. "
                "Start the API server with a compiled Mojo worker pool."
            ),
            {"module": module, "function": function, "cause": exc.code},
        ) from exc
    result = parse_runtime_library_worker_response(
        module,
        function,
        raw,
        function_spec=function_spec,
    )
    latency_ms = round((time.monotonic() - started) * 1000, 2)
    return RuntimeLibraryExecutionResult(
        module=module,
        function=function,
        result=result,
        latency_ms=latency_ms,
        engine_used="mojo",
        request_id=request_id,
    )
