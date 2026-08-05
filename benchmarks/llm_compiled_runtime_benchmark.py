from __future__ import annotations

import argparse
import importlib
import json
import os
import socket
import statistics
import struct
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if TYPE_CHECKING:
    from apps.runtime.mojo_inventory import RuntimeFunctionSpec

_MOJO_INVENTORY = importlib.import_module("apps.runtime.mojo_inventory")
discover_runtime_library_modules = _MOJO_INVENTORY.discover_runtime_library_modules
RuntimeFunctionSpec = _MOJO_INVENTORY.RuntimeFunctionSpec
_MOJO_LIBRARY_RUNNER = importlib.import_module("apps.runtime.mojo_library_runner")
build_runtime_library_worker_request = _MOJO_LIBRARY_RUNNER.build_runtime_library_worker_request
parse_runtime_library_worker_response = _MOJO_LIBRARY_RUNNER.parse_runtime_library_worker_response

DEFAULT_OUTPUT = PROJECT_ROOT / "build" / "llm_compiled_runtime_benchmark.json"


def _resolve_mojo_binary() -> Path:
    for env_name in ("ALGENTA_NATIVE_WORKER", "ALGENTA_RUNTIME_WORKER", "ALGENTA_MOJO_BINARY"):
        configured = os.environ.get(env_name, "").strip()
        if configured:
            return Path(configured).expanduser()
    return PROJECT_ROOT / "mojo_build" / "simulate"


MOJO_BINARY = _resolve_mojo_binary()
# Single source of truth lives in the prod-shipped core module so apps/ never imports
# benchmarks/ (which isn't packaged into the api/worker/engine images).
_RUNTIME_MODULE_ORDER = importlib.import_module("apps.runtime_manifest._module_order")
TARGET_MODULES = _RUNTIME_MODULE_ORDER.LLM_ROLLOUT_MODULE_ORDER
_VECTOR_RANKER_FIXTURE = (
    '{"query":{"name":"unit_price","role_hint":"unit_measure","source":"POS"},'
    '"candidates":[{"source":"POS","name":"unit_price"},'
    '{"source":"POS","name":"extended_price"},'
    '{"source":"INVOICE","name":"invoice_total"}],"top_k":2}'
)
_VECTOR_TABLE_FIXTURE = (
    '[{"id":1,"source":"POS","role":"unit_measure","name":"unit_price"},'
    '{"id":2,"source":"BACKLOG","role":"derived_measure","name":"extended_price"},'
    '{"id":3,"source":"INVOICE","role":"derived_measure","name":"invoice_total"}]'
)
_ARG_OVERRIDES: dict[tuple[str, str], list[Any]] = {
    ("text.tokenizer", "char_ngrams"): ["alpha beta", 3],
    ("text.tokenizer", "word_ngrams"): [["alpha", "beta", "gamma"], 2],
    ("text.tokenizer", "pad_sequence"): [["alpha", "beta"], 5, "<pad>"],
    (
        "embeddings",
        "k_nearest_neighbors",
    ): [[0.5, 0.6, 0.7], [[0.5, 0.6, 0.7], [0.2, 0.1, 0.0]], 2],
    ("vector_search", "recall_at_k"): [2.0, 5.0, 4.0],
    ("vector_kernels.ranker", "run_column_rank_v2"): [_VECTOR_RANKER_FIXTURE],
    ("vector_kernels.table", "build_query"): ["unit_price", 1, 1, 2],
    ("vector_kernels.table", "source_id_of"): ["POS"],
    ("vector_kernels.table", "role_id_of"): ["unit_measure"],
    ("vector_kernels.table", "build_table_json"): [_VECTOR_TABLE_FIXTURE],
    ("sparse_vector", "sv_dot"): [[0, 2], [0.5, 0.25], [0, 2], [0.1, 0.2]],
    ("sparse_vector", "sv_add"): [[0, 2], [0.5, 0.25], [0, 2], [0.1, 0.2]],
    ("sparse_vector", "sv_cosine"): [[0, 2], [0.5, 0.25], [0, 2], [0.1, 0.2]],
    ("sparse_vector", "sv_to_dense"): [[0, 2], [0.5, 0.25], 4],
    ("rlhf_dpo", "orpo_ratio"): [-0.2, -1.2, 5.0, 5.0, 0.1],
}


def _recv_frame(sock: socket.socket) -> dict[str, object]:
    header = sock.recv(4)
    if len(header) < 4:
        raise RuntimeError("short frame header from Mojo server")
    frame_len = struct.unpack(">I", header)[0]
    payload = bytearray()
    while len(payload) < frame_len:
        chunk = sock.recv(frame_len - len(payload))
        if not chunk:
            raise RuntimeError("unexpected EOF from Mojo server")
        payload.extend(chunk)
    return json.loads(payload.decode("utf-8"))


def _send_frame(sock: socket.socket, payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    sock.sendall(struct.pack(">I", len(body)) + body)
    return _recv_frame(sock)


def _start_server() -> tuple[subprocess.Popen[str], Path]:
    if not MOJO_BINARY.exists():
        raise FileNotFoundError(f"Compiled Mojo binary not found: {MOJO_BINARY}")

    socket_dir = Path(tempfile.mkdtemp(prefix="algenta-llm-bench-"))
    socket_path = socket_dir / "runtime.sock"
    proc = subprocess.Popen(  # noqa: S603
        [str(MOJO_BINARY), "--server", str(socket_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 10.0
    while not socket_path.exists():
        if proc.poll() is not None:
            stderr_output = proc.stderr.read() if proc.stderr is not None else ""
            raise RuntimeError(
                "Mojo compiled runtime failed to start: "
                f"{stderr_output.strip() or 'server exited before opening socket'}"
            )
        if time.monotonic() >= deadline:
            proc.terminate()
            raise TimeoutError("timed out waiting for Mojo runtime benchmark socket")
        time.sleep(0.01)
    return proc, socket_path


def _stop_server(proc: subprocess.Popen[str], socket_path: Path) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=1.0)
    try:
        socket_path.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        socket_path.parent.rmdir()
    except OSError:
        pass


def _median_ms(samples: Iterable[float]) -> float:
    ordered = list(samples)
    if not ordered:
        return 0.0
    return float(statistics.median(ordered))


def _default_scalar_value(type_name: str) -> Any:
    if type_name == "Bool":
        return True
    if type_name == "String":
        return "alpha beta gamma"
    if type_name == "Int":
        return 5
    if type_name in {"UInt8", "UInt16", "UInt32", "UInt64"}:
        return 3
    if type_name in {"Float32", "Float64"}:
        return 5.0
    raise ValueError(f"Unsupported scalar runtime type {type_name!r}")


def _default_flat_list(inner: str) -> list[Any] | None:
    """The default flat List[inner] value, or None if `inner` has no flat default.

    This is the single source of truth `_default_value`'s nested-list branch
    rotates from, so a function mixing List[T] and List[List[T]] parameters --
    e.g. a query vector and a list of candidate vectors that must share one
    dimension -- always gets a dimensionally consistent default for both,
    without a second, independently-hardcoded literal that could silently
    drift out of sync with this one.
    """
    if inner in ("Float64", "Float32"):
        return [0.5, 0.6, 0.7, 0.4, 0.3]
    if inner == "Int":
        return [1, 0, 1, 1, 0]
    if inner == "Bool":
        return [True, False, True]
    if inner == "String":
        return ["alpha", "beta", "gamma"]
    return None


def _default_nested_list(inner: str, n_rows: int = 3) -> list[Any]:
    """n_rows of List[inner]'s own flat default, each row a rotation of it (so
    rows aren't literally identical -- a degenerate all-candidates-the-same
    fixture would hide a real bug in code that's supposed to distinguish
    between candidates) -- but every row is exactly the same length as
    List[inner]'s own default, by construction, not by two hardcoded
    literals that happen to agree today.
    """
    base = _default_flat_list(inner)
    if base is None:
        raise ValueError(f"Unsupported nested runtime type List[List[{inner}]]")
    return [base[i:] + base[:i] for i in range(n_rows)]


def _default_value(type_name: str) -> Any:
    if type_name.startswith("List[") and type_name.endswith("]"):
        inner = type_name[5:-1]
        if inner.startswith("List[") and inner.endswith("]"):
            return _default_nested_list(inner[5:-1])
        flat = _default_flat_list(inner)
        if flat is not None:
            return flat
        raise ValueError(f"Unsupported nested runtime type {type_name!r}")
    return _default_scalar_value(type_name)


def _build_args(module_name: str, function_spec: RuntimeFunctionSpec) -> list[Any]:
    override = _ARG_OVERRIDES.get((module_name, function_spec.name))
    if override is not None:
        return list(override)
    return [_default_value(param.typ) for param in function_spec.params]


def _call_function(
    socket_path: Path,
    module_name: str,
    function_spec: RuntimeFunctionSpec,
    args: list[Any],
) -> Any:
    resolved_spec, payload = build_runtime_library_worker_request(
        module_name,
        function_spec.name,
        args,
    )
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(str(socket_path))
        ready = _recv_frame(sock)
        if ready != {"status": "ready"}:
            raise RuntimeError(f"Unexpected Mojo server handshake: {ready!r}")
        response = _send_frame(sock, payload)
    return parse_runtime_library_worker_response(
        module_name,
        function_spec.name,
        response,
        function_spec=resolved_spec,
    )


def _benchmark_function(
    socket_path: Path,
    module_name: str,
    function_spec: RuntimeFunctionSpec,
    *,
    warm_iterations: int,
    hot_iterations: int,
) -> dict[str, Any]:
    args = _build_args(module_name, function_spec)
    started = time.perf_counter()
    result = _call_function(socket_path, module_name, function_spec, args)
    cold_ms = (time.perf_counter() - started) * 1000.0

    warm_samples: list[float] = []
    for _ in range(max(warm_iterations, 1)):
        started = time.perf_counter()
        _call_function(socket_path, module_name, function_spec, args)
        warm_samples.append((time.perf_counter() - started) * 1000.0)

    hot_samples: list[float] = []
    for _ in range(max(hot_iterations, 1)):
        started = time.perf_counter()
        _call_function(socket_path, module_name, function_spec, args)
        hot_samples.append((time.perf_counter() - started) * 1000.0)

    return {
        "engine_used": "mojo",
        "cold_ms": cold_ms,
        "warm_ms": _median_ms(warm_samples),
        "hot_ms": _median_ms(hot_samples),
        "return_type": function_spec.return_type,
        "args": args,
        "sample_result": result,
    }


def collect_target_modules() -> dict[str, tuple[RuntimeFunctionSpec, ...]]:
    modules = {
        module.import_path: module
        for module in discover_runtime_library_modules(executable_only=True)
    }
    resolved: dict[str, tuple[RuntimeFunctionSpec, ...]] = {}
    for module_name in TARGET_MODULES:
        module = modules.get(module_name)
        if module is None:
            raise RuntimeError(f"Runtime-executable target module missing: {module_name}")
        resolved[module_name] = module.functions
    return resolved


def run_benchmark(*, warm_iterations: int = 5, hot_iterations: int = 20) -> dict[str, Any]:
    target_modules = collect_target_modules()
    proc, socket_path = _start_server()
    failures: list[dict[str, Any]] = []
    modules_payload: dict[str, Any] = {}
    try:
        for module_name in TARGET_MODULES:
            function_payloads: dict[str, Any] = {}
            for function_spec in target_modules[module_name]:
                try:
                    function_payloads[function_spec.name] = _benchmark_function(
                        socket_path,
                        module_name,
                        function_spec,
                        warm_iterations=warm_iterations,
                        hot_iterations=hot_iterations,
                    )
                except Exception as exc:  # noqa: BLE001
                    error_payload = {
                        "module": module_name,
                        "function": function_spec.name,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                    failures.append(error_payload)
                    function_payloads[function_spec.name] = {"error": error_payload}
            modules_payload[module_name] = {
                "function_count": len(target_modules[module_name]),
                "functions": function_payloads,
            }
    finally:
        _stop_server(proc, socket_path)

    total_functions = sum(len(functions) for functions in target_modules.values())
    return {
        "benchmark": "llm_compiled_runtime_benchmark",
        "transport": "compiled_worker",
        "module_count": len(target_modules),
        "function_count": total_functions,
        "warm_iterations": warm_iterations,
        "hot_iterations": hot_iterations,
        "modules": modules_payload,
        "failures": failures,
        "failed_function_count": len(failures),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark compiled Mojo runtime for LLM kernels.")
    parser.add_argument(
        "--warm-iterations",
        type=int,
        default=5,
        help="Warm samples per function.",
    )
    parser.add_argument(
        "--hot-iterations",
        type=int,
        default=20,
        help="Hot samples per function.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Where to write the benchmark JSON artifact.",
    )
    args = parser.parse_args()

    results = run_benchmark(
        warm_iterations=args.warm_iterations,
        hot_iterations=args.hot_iterations,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
