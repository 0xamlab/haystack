from __future__ import annotations

import json
import socket
import struct
import subprocess
import time
from pathlib import Path

import pytest

from apps.runtime.mojo_library_runner import (
    build_runtime_library_worker_request,
    parse_runtime_library_worker_response,
)


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


def _start_test_server() -> tuple[subprocess.Popen[str], Path]:
    binary = Path("mojo_build/simulate")
    if not binary.exists():
        pytest.skip("mojo_build/simulate not present")

    socket_path = Path("/tmp/algenta-library-dispatch-test.sock")
    if socket_path.exists():
        socket_path.unlink()

    proc = subprocess.Popen(  # noqa: S603
        [str(binary), "--server", str(socket_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 5.0
    while not socket_path.exists():
        if proc.poll() is not None:
            stderr_output = proc.stderr.read() if proc.stderr is not None else ""
            pytest.skip(
                "Mojo library dispatch server mode unavailable for current binary: "
                f"{stderr_output.strip() or 'server exited before opening socket'}"
            )
        if time.monotonic() >= deadline:
            raise TimeoutError("timed out waiting for Mojo library dispatch socket")
        time.sleep(0.01)
    return proc, socket_path


def _stop_test_server(proc: subprocess.Popen[str], socket_path: Path) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=1.0)
    if socket_path.exists():
        socket_path.unlink()


@pytest.fixture(scope="module")
def llm_dispatch_server() -> tuple[subprocess.Popen[str], Path]:
    proc, socket_path = _start_test_server()
    try:
        yield proc, socket_path
    finally:
        _stop_test_server(proc, socket_path)


def test_mojo_server_dispatches_runtime_library_execute_requests() -> None:
    proc, socket_path = _start_test_server()
    try:
        _, payload = build_runtime_library_worker_request(
            "elevator",
            "annual_energy_consumption",
            [0.5, 0.5, 0.5, 0.5],
        )

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(str(socket_path))
            assert _recv_frame(sock) == {"status": "ready"}

            response = _send_frame(sock, payload)
            assert "error" not in response
            assert isinstance(response.get("result"), float)

            assert _send_frame(sock, {"type": "shutdown"}) == {"status": "bye"}

        proc.wait(timeout=5.0)
        assert proc.returncode == 0
    finally:
        _stop_test_server(proc, socket_path)


LLM_ROLLOUT_FIXTURE = (
    '{"query":{"name":"unit_price","role_hint":"unit_measure","source":"POS"},'
    '"candidates":[{"source":"POS","name":"unit_price"}],"top_k":1}'
)
LLM_TABLE_FIXTURE = (
    '[{"id":1,"source":"POS","role":"unit_measure","name":"unit_price"},'
    '{"id":2,"source":"BACKLOG","role":"derived_measure","name":"extended_price"},'
    '{"id":3,"source":"INVOICE","role":"derived_measure","name":"invoice_total"}]'
)


def _dispatch_runtime_call(
    socket_path: Path,
    module_name: str,
    function_name: str,
    args: list[object],
) -> object:
    function_spec, payload = build_runtime_library_worker_request(module_name, function_name, args)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(str(socket_path))
        assert _recv_frame(sock) == {"status": "ready"}
        response = _send_frame(sock, payload)
    assert "error" not in response
    return parse_runtime_library_worker_response(
        module_name,
        function_name,
        response,
        function_spec=function_spec,
    )


def test_mojo_server_dispatches_llm_rollout_representative_requests(
    llm_dispatch_server: tuple[subprocess.Popen[str], Path],
) -> None:
    _, socket_path = llm_dispatch_server

    assert _dispatch_runtime_call(
        socket_path,
        "text.tokenizer",
        "word_tokenize",
        ["Alpha beta."],
    ) == ["alpha", "beta"]

    ranked = _dispatch_runtime_call(
        socket_path,
        "vector_kernels.ranker",
        "run_column_rank_v2",
        [LLM_ROLLOUT_FIXTURE],
    )
    assert isinstance(ranked, str)
    assert '"matches"' in ranked

    build_query = _dispatch_runtime_call(
        socket_path,
        "vector_kernels.table",
        "build_query",
        ["unit_price", 1, 1, 2],
    )
    assert isinstance(build_query, dict)
    assert build_query["source_id"] == 1
    assert build_query["role_id"] == 1
    assert build_query["top_k"] == 2
    assert len(build_query["query_vec"]["data"]) == 64
    assert build_query["query_norm_inv"] > 0.0

    table = _dispatch_runtime_call(
        socket_path,
        "vector_kernels.table",
        "build_table_json",
        [LLM_TABLE_FIXTURE],
    )
    assert isinstance(table, dict)
    assert len(table["entries"]) == 3
    assert table["entries"][0]["column_id"] == 1
    assert table["entries"][0]["source_id"] == 1
    assert table["entries"][0]["role_id"] == 1


@pytest.mark.parametrize(
    ("function_name", "args", "expected"),
    [
        ("precision_at_k", [[1, 0, 1], 3], 2.0 / 3.0),
        ("recall_at_k", [[1, 0, 1], 4, 3], 0.5),
        ("hit_rate_at_k", [[0, 0, 1], 3], 1.0),
        ("mrr_at_k", [[0, 1, 0], 3], 0.5),
        ("map_at_k", [[1, 0, 1], 3], (1.0 + 2.0 / 3.0) / 2.0),
        ("ndcg_at_k", [[3.0, 2.0], [3.0, 2.0], 2], 1.0),
        ("pairwise_margin_accuracy", [[0.9, 0.7], [0.1, 0.4], 0.2], 1.0),
        ("score_separation", [[0.8, 0.6], [0.3, 0.1]], 0.5),
        ("latency_weighted_quality", [0.9, 50.0, 100.0], 0.6),
    ],
)
def test_mojo_server_dispatches_rerank_eval_kernel_functions(
    llm_dispatch_server: tuple[subprocess.Popen[str], Path],
    function_name: str,
    args: list[object],
    expected: float,
) -> None:
    _, socket_path = llm_dispatch_server
    result = _dispatch_runtime_call(socket_path, "rerank_eval", function_name, args)
    assert result == pytest.approx(expected)


@pytest.mark.parametrize(
    ("function_name", "args", "expected"),
    [
        ("prompt_token_estimate", [100, 4.0], 25),
        ("completion_token_estimate", [45, 4.0], 12),
        ("kv_cache_bytes", [2, 128, 4, 256, 2], 1048576.0),
        ("attention_flops", [2, 128, 4, 8, 64], 268435456.0),
        ("prefill_latency_estimate", [1000, 500.0, 20.0], 2020.0),
        ("decode_latency_estimate", [250, 250.0, 15.0], 1015.0),
        ("request_cost_estimate", [1000, 500, 0.002, 0.006], 0.005),
        ("cost_latency_frontier_score", [0.01, 100.0, 2.0, 0.01], 1.0 / 2.02),
        ("batch_efficiency_estimate", [4, 8], 0.5),
        ("queue_delay_estimate", [10, 5.0, 2], 1000.0),
        ("speculative_decode_gain_estimate", [0.5, 4, 100.0, 200.0], 0.5),
    ],
)
def test_mojo_server_dispatches_inference_cost_latency_kernel_functions(
    llm_dispatch_server: tuple[subprocess.Popen[str], Path],
    function_name: str,
    args: list[object],
    expected: float | int,
) -> None:
    _, socket_path = llm_dispatch_server
    result = _dispatch_runtime_call(socket_path, "inference_cost_latency", function_name, args)
    if isinstance(expected, int):
        assert result == expected
    else:
        assert result == pytest.approx(expected)
