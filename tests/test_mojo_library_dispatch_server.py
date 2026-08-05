from __future__ import annotations

import json
import os
import socket
import struct
import subprocess
import time
from pathlib import Path

import pytest

from apps.runtime.mojo_binary_freshness import inspect_mojo_binary_freshness
from apps.runtime.mojo_library_runner import (
    build_runtime_library_worker_request,
    parse_runtime_library_worker_response,
)


def _resolve_test_binary() -> Path:
    return Path(os.environ.get("DE_TEST_MOJO_BINARY", "mojo_build/simulate"))


def _resolve_test_source_paths() -> tuple[Path, ...] | None:
    raw = os.environ.get("DE_TEST_MOJO_SOURCES", "").strip()
    if not raw:
        return None
    return tuple(Path(entry) for entry in raw.split(os.pathsep) if entry)


def test_resolve_test_binary_uses_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DE_TEST_MOJO_BINARY", "/tmp/custom-simulate")
    assert _resolve_test_binary() == Path("/tmp/custom-simulate")


def test_resolve_test_source_paths_uses_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DE_TEST_MOJO_SOURCES",
        os.pathsep.join(("/tmp/main.mojo", "/tmp/runtime_library_dispatch_generated.mojo")),
    )
    assert _resolve_test_source_paths() == (
        Path("/tmp/main.mojo"),
        Path("/tmp/runtime_library_dispatch_generated.mojo"),
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
    binary = _resolve_test_binary()
    source_paths = _resolve_test_source_paths()
    if source_paths is None:
        freshness = inspect_mojo_binary_freshness(binary)
    else:
        freshness = inspect_mojo_binary_freshness(binary, source_paths=source_paths)
    if not freshness.exists:
        pytest.skip(f"{binary} not present")
    if not freshness.is_fresh:
        pytest.fail(freshness.failure_message())

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


def test_mojo_server_dispatches_vector_dot_runtime_library_request() -> None:
    proc, socket_path = _start_test_server()
    try:
        left = [1.0, 2.0, 3.0] + [0.0] * 61
        right = [3.0, 2.0, 2.0] + [0.0] * 61
        _, payload = build_runtime_library_worker_request(
            "vector_kernels.dot",
            "dot64_f32",
            [left, right],
        )

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(str(socket_path))
            assert _recv_frame(sock) == {"status": "ready"}

            response = _send_frame(sock, payload)
            assert "error" not in response
            assert response.get("result") == pytest.approx(13.0)

            assert _send_frame(sock, {"type": "shutdown"}) == {"status": "bye"}

        proc.wait(timeout=5.0)
        assert proc.returncode == 0
    finally:
        _stop_test_server(proc, socket_path)


def test_mojo_server_wire_grammar_keeps_float_lists_element_aligned() -> None:
    """Pin the frozen wire grammar for the worker-side JSON tokenizer.

    Two forms Python's own ``json`` module emits must survive the worker's tokenizer
    with their element COUNT and position intact: scientific notation
    (``json.dumps(1e-05) == "1e-05"``) and bare non-finite words
    (``json.dumps(float("nan")) == "NaN"``). A tokenizer that splits ``1e-05`` into
    ``1e`` + ``-05`` shifts every later element; one that refuses ``NaN`` rejects what
    the frozen grammar decodes to 0.0. ``dot64_f32`` makes both observable: the result
    is right only if both 64-element lists arrive element-aligned.
    """
    proc, socket_path = _start_test_server()
    try:
        payload: dict[str, object] = {
            "type": "library_execute",
            "engine_type": "library_execute",
            "module": "vector_kernels.dot",
            "function": "dot64_f32",
            # json serializes 1e-05 as "1e-05": scientific notation must stay ONE element.
            "args": [[1e-05, 2.0, 3.0] + [0.0] * 61, [1.0, 1.0, 1.0] + [0.0] * 61],
        }

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(str(socket_path))
            assert _recv_frame(sock) == {"status": "ready"}

            response = _send_frame(sock, payload)
            assert "error" not in response
            assert response.get("result") == pytest.approx(5.00001)

            # A bare "NaN" decodes to 0.0 under the frozen grammar: never refused, and it
            # must not shift its neighbours.
            payload["args"] = [[1.0, float("nan"), 3.0] + [0.0] * 61, [1.0, 1.0, 1.0] + [0.0] * 61]
            response = _send_frame(sock, payload)
            assert "error" not in response
            assert response.get("result") == pytest.approx(4.0)

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
COLORCHECK_RGB_2X2 = [
    200.0, 20.0, 20.0,
    200.0, 20.0, 20.0,
    200.0, 20.0, 20.0,
    20.0, 20.0, 200.0,
]
VIDEO_THREE_FRAMES_4X4 = (
    [10.0] * 16
    + [200.0 if i < 4 else 10.0 for i in range(16)]
    + [200.0] * 16
)
VIDEO_RGB_THREE_FRAMES_2X2 = (
    [200.0, 20.0, 20.0] * 4
    + [200.0, 20.0, 20.0] * 3
    + [20.0, 20.0, 200.0]
    + [20.0, 20.0, 200.0] * 4
)
VIDEO_ACCESSIBILITY_THREE_FRAMES_2X2 = (
    [20.0, 20.0, 20.0] * 4
    + [
        20.0,
        20.0,
        20.0,
        20.0,
        20.0,
        20.0,
        20.0,
        20.0,
        20.0,
        220.0,
        220.0,
        220.0,
    ]
    + [220.0, 220.0, 220.0] * 4
)
DOC_MASK_8X8 = [
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    255.0,
    255.0,
    255.0,
    255.0,
    255.0,
    255.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    255.0,
    255.0,
    255.0,
    255.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
]
BLOCK_5X5 = [
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    255.0,
    255.0,
    255.0,
    0.0,
    0.0,
    255.0,
    255.0,
    255.0,
    0.0,
    0.0,
    255.0,
    255.0,
    255.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
]
DOC_COLUMNS_8X8 = [
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 255.0, 255.0, 0.0, 0.0, 255.0, 255.0, 0.0,
    0.0, 255.0, 255.0, 0.0, 0.0, 255.0, 255.0, 0.0,
    0.0, 255.0, 255.0, 0.0, 0.0, 255.0, 255.0, 0.0,
    0.0, 255.0, 255.0, 0.0, 0.0, 255.0, 255.0, 0.0,
    0.0, 255.0, 255.0, 0.0, 0.0, 255.0, 255.0, 0.0,
    0.0, 255.0, 255.0, 0.0, 0.0, 255.0, 255.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
]
VIDEO_MOTION_3X5X5 = (
    [10.0] * 25
    + [
        200.0 if 1 <= (index // 5) <= 2 and 1 <= (index % 5) <= 2 else 10.0
        for index in range(25)
    ]
    + [
        200.0
        if (
            (1 <= (index // 5) <= 2 and 1 <= (index % 5) <= 2)
            or ((index // 5) == 4 and (index % 5) == 4)
        )
        else 10.0
        for index in range(25)
    ]
)
VIDEO_SIMILAR_3X4X4_ALT = (
    [12.0] * 16
    + [188.0 if index < 4 else 12.0 for index in range(16)]
    + [192.0] * 16
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


@pytest.mark.parametrize(
    ("module_name", "function_name", "args", "expected"),
    [
        ("color_science", "rgb_to_luminance", [1.0, 1.0, 1.0], 1.0),
        ("color_science", "contrast_ratio", [0.0, 1.0], 21.0),
        ("color_check", "preferred_text_color_hex", ["#336699"], "#FFFFFF"),
        (
            "color_check",
            "preferred_text_color_for_image",
            [COLORCHECK_RGB_2X2, 2, 2, 4],
            "#FFFFFF",
        ),
        ("image_palette", "palette_size_estimate", [COLORCHECK_RGB_2X2, 2, 2, 4, 0.2], 2),
        ("image_palette", "warm_color_ratio_rgb255", [COLORCHECK_RGB_2X2, 2, 2, 0.25], 0.75),
        ("image_palette", "accent_color_hex", [COLORCHECK_RGB_2X2, 2, 2, 4], "#C81414"),
        ("image_ops", "mean_pixel", [[[0.0, 255.0], [255.0, 0.0]]], 127.5),
        ("image_features", "histogram_intersection", [[0.5, 0.5], [1.0, 0.0]], 0.5),
        ("image_resize", "reshape_to_grid", [[1.0, 2.0, 3.0, 4.0], 2, 2], [[1.0, 2.0], [3.0, 4.0]]),
        ("image_quality", "brightness_flat", [[0.0, 255.0, 255.0, 0.0], 2, 2], 127.5),
        ("image_morphology", "foreground_area_ratio_flat", [BLOCK_5X5, 5, 5, 128.0], 9.0 / 25.0),
        (
            "document_vision",
            "horizontal_projection",
            [DOC_MASK_8X8, 8, 8, 128.0],
            [0.0, 0.0, 6.0, 0.0, 0.0, 4.0, 0.0, 0.0],
        ),
        ("document_layout", "line_count_flat", [DOC_MASK_8X8, 8, 8, 128.0, 1], 2),
        ("document_layout", "column_count_flat", [DOC_COLUMNS_8X8, 8, 8, 128.0, 2], 2),
        (
            "image_similarity",
            "mean_squared_error_flat",
            [[0.0, 10.0, 20.0, 30.0], [0.0, 10.0, 30.0, 30.0], 2, 2],
            25.0,
        ),
        ("image_regions", "box_iou", [[0, 0, 2, 2], [1, 1, 3, 3]], 4.0 / 14.0),
        ("perceptual_hash", "hamming_distance", [0, 3], 2),
        ("vision_gate", "route_image_request", [120.0, 128.0, 4.0, 0.2, False, 0], 5),
    ],
)
def test_mojo_server_dispatches_image_runtime_library_requests(
    llm_dispatch_server: tuple[subprocess.Popen[str], Path],
    module_name: str,
    function_name: str,
    args: list[object],
    expected: object,
) -> None:
    _, socket_path = llm_dispatch_server
    result = _dispatch_runtime_call(socket_path, module_name, function_name, args)
    if isinstance(expected, float):
        assert result == pytest.approx(expected)
    else:
        assert result == expected


@pytest.mark.parametrize(
    ("module_name", "function_name", "args", "expected"),
    [
        (
            "video_ops",
            "frame_count_from_flat",
            [VIDEO_THREE_FRAMES_4X4, 4, 4, 1],
            3,
        ),
        (
            "video_features",
            "scene_cut_count",
            [VIDEO_THREE_FRAMES_4X4, 4, 4, 1, 0.4],
            1,
        ),
        (
            "video_storyboard",
            "scene_start_indices",
            [VIDEO_THREE_FRAMES_4X4, 4, 4, 1, 0.4],
            [0, 2],
        ),
        (
            "video_storyboard",
            "storyboard_frame_indices",
            [VIDEO_THREE_FRAMES_4X4, 4, 4, 1, 0.4, 2],
            [0, 2],
        ),
        (
            "video_storyboard",
            "longest_scene_index",
            [VIDEO_THREE_FRAMES_4X4, 4, 4, 1, 0.4],
            0,
        ),
        (
            "video_color",
            "frame_mean_rgb255",
            [VIDEO_RGB_THREE_FRAMES_2X2, 2, 2, 3, 1],
            [155.0, 20.0, 65.0],
        ),
        (
            "video_color",
            "clip_mean_rgb255",
            [VIDEO_RGB_THREE_FRAMES_2X2, 2, 2, 3],
            [125.0, 20.0, 95.0],
        ),
        (
            "video_color",
            "dominant_clip_color_rgb255",
            [VIDEO_RGB_THREE_FRAMES_2X2, 2, 2, 3, 4, 3],
            [200.0, 20.0, 20.0, 7.0 / 12.0],
        ),
        (
            "video_color",
            "clip_mean_saturation_rgb255",
            [VIDEO_RGB_THREE_FRAMES_2X2, 2, 2, 3],
            0.9,
        ),
        (
            "video_color",
            "warm_frame_ratio_rgb255",
            [VIDEO_RGB_THREE_FRAMES_2X2, 2, 2, 3, 0.25],
            2.0 / 3.0,
        ),
        (
            "video_color",
            "preferred_text_color_for_video",
            [VIDEO_RGB_THREE_FRAMES_2X2, 2, 2, 3, 4, 3],
            "#FFFFFF",
        ),
        (
            "video_accessibility",
            "frame_min_preferred_text_contrast_for_video",
            [VIDEO_ACCESSIBILITY_THREE_FRAMES_2X2, 2, 2, 3, 1],
            1.3713058806238527,
        ),
        (
            "video_accessibility",
            "frame_preferred_text_color_for_video",
            [VIDEO_ACCESSIBILITY_THREE_FRAMES_2X2, 2, 2, 3, 1],
            "#FFFFFF",
        ),
        (
            "video_accessibility",
            "sampled_video_min_text_contrast",
            [VIDEO_ACCESSIBILITY_THREE_FRAMES_2X2, 2, 2, 3, 3],
            1.3713058806238527,
        ),
        (
            "video_accessibility",
            "sampled_video_wcag_safe_ratio",
            [VIDEO_ACCESSIBILITY_THREE_FRAMES_2X2, 2, 2, 3, 3, 16.0, False],
            2.0 / 3.0,
        ),
        (
            "video_accessibility",
            "needs_text_backplate_for_video",
            [VIDEO_ACCESSIBILITY_THREE_FRAMES_2X2, 2, 2, 3, 3, 16.0, False],
            True,
        ),
        (
            "video_accessibility",
            "subtitle_band_min_preferred_text_contrast_for_video",
            [VIDEO_ACCESSIBILITY_THREE_FRAMES_2X2, 2, 2, 3, 3, 1],
            1.3713058806238527,
        ),
        (
            "video_accessibility",
            "subtitle_band_preferred_text_color_for_video",
            [VIDEO_ACCESSIBILITY_THREE_FRAMES_2X2, 2, 2, 3, 3, 1],
            "#FFFFFF",
        ),
        (
            "video_accessibility",
            "sampled_subtitle_band_wcag_safe_ratio",
            [VIDEO_ACCESSIBILITY_THREE_FRAMES_2X2, 2, 2, 3, 3, 1, 16.0, False],
            2.0 / 3.0,
        ),
        (
            "video_accessibility",
            "subtitle_band_needs_backplate_for_video",
            [VIDEO_ACCESSIBILITY_THREE_FRAMES_2X2, 2, 2, 3, 3, 1, 16.0, False],
            True,
        ),
        (
            "video_quality",
            "brightness_flicker_score",
            [VIDEO_THREE_FRAMES_4X4, 4, 4, 1],
            95.0,
        ),
        (
            "video_gate",
            "route_video_request",
            [0.8, 40.0, 0.1, 10.0, 0.05, False, 0],
            5,
        ),
        (
            "video_regions",
            "largest_motion_box_between_frames",
            [VIDEO_MOTION_3X5X5, 5, 5, 1, 1, 2, 50.0],
            [4, 4, 4, 4, 1],
        ),
        (
            "video_regions",
            "motion_coverage_ratio_flat",
            [VIDEO_MOTION_3X5X5, 5, 5, 1, 50.0],
            0.2,
        ),
        (
            "video_similarity",
            "clip_duplicate_score_flat",
            [VIDEO_THREE_FRAMES_4X4,
             VIDEO_THREE_FRAMES_4X4,
             4,
             4,
             1],
            1.0,
        ),
        (
            "video_similarity",
            "average_frame_hash_hamming",
            [VIDEO_THREE_FRAMES_4X4,
             VIDEO_THREE_FRAMES_4X4,
             4,
             4,
             1],
            0.0,
        ),
    ],
)
def test_mojo_server_dispatches_video_runtime_library_requests(
    llm_dispatch_server: tuple[subprocess.Popen[str], Path],
    module_name: str,
    function_name: str,
    args: list[object],
    expected: object,
) -> None:
    _, socket_path = llm_dispatch_server
    result = _dispatch_runtime_call(socket_path, module_name, function_name, args)
    if isinstance(expected, float):
        assert result == pytest.approx(expected)
    else:
        assert result == expected
