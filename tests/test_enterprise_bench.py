"""Tests for benchmarks/llm_smoke/nvidia_race/enterprise_bench.py — the stdlib enterprise
serving benchmark harness (TTFT/TPOT/ITL percentiles, closed-loop concurrency + open-loop
Poisson sweeps, OpenAI-compatible SSE adapter + JSON-lines driver protocol)."""

from __future__ import annotations

import importlib.util
import json
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_HARNESS_PATH = ROOT / "benchmarks" / "llm_smoke" / "nvidia_race" / "enterprise_bench.py"


def _load_harness():
    spec = importlib.util.spec_from_file_location("enterprise_bench_under_test", _HARNESS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


eb = _load_harness()


# ── percentile math ──


def test_percentile_known_vectors() -> None:
    values = [float(i) for i in range(1, 11)]  # 1..10
    assert eb.percentile(values, 50) == pytest.approx(5.5)
    assert eb.percentile(values, 90) == pytest.approx(9.1)
    assert eb.percentile(values, 99) == pytest.approx(9.91)
    assert eb.percentile(values, 0) == pytest.approx(1.0)
    assert eb.percentile(values, 100) == pytest.approx(10.0)


def test_percentile_edge_cases() -> None:
    assert eb.percentile([], 50) == 0.0
    assert eb.percentile([7.0], 99) == pytest.approx(7.0)
    assert eb.percentile([5.0, 1.0, 3.0, 2.0, 4.0], 50) == pytest.approx(3.0)  # sorts internally


# ── Poisson arrivals ──


def test_poisson_arrivals_deterministic() -> None:
    a = eb.poisson_arrivals(64, 8.0, 1234)
    b = eb.poisson_arrivals(64, 8.0, 1234)
    assert a == b
    assert eb.poisson_arrivals(64, 8.0, 4321) != a


def test_poisson_arrivals_rate_and_monotonic() -> None:
    rate = 50.0
    arrivals = eb.poisson_arrivals(20000, rate, 7)
    assert len(arrivals) == 20000
    assert all(x < y for x, y in zip(arrivals, arrivals[1:], strict=False))
    mean_gap = arrivals[-1] / len(arrivals)
    assert mean_gap == pytest.approx(1.0 / rate, rel=0.05)


# ── SSE parsing ──


def test_iter_lines_chunks_split_mid_line() -> None:
    chunks = [b'data: {"a"', b": 1}\r\ndata: [DON", b"E]\n"]
    assert list(eb.iter_lines(chunks)) == ['data: {"a": 1}', "data: [DONE]"]


def test_iter_lines_trailing_remainder_without_newline() -> None:
    assert list(eb.iter_lines([b"data: tail"])) == ["data: tail"]


def test_sse_data_payloads_canned_stream() -> None:
    stream = (
        b": keepalive comment\n\n"
        b'event: x\ndata: {"choices":[{"delta":{"content":"He"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":"llo"}}],"usage":null}\n'
        b'data: {"choices":[],"usage":{"completion_tokens":2}}\n'
        b"data: [DONE]\n"
        b'data: {"must":"never appear"}\n'
    )
    # Fed one byte at a time: the harshest possible chunking.
    payloads = list(eb.sse_data_payloads(eb.iter_lines(bytes([b]) for b in stream)))
    assert len(payloads) == 3
    assert json.loads(payloads[0])["choices"][0]["delta"]["content"] == "He"
    assert json.loads(payloads[2])["usage"]["completion_tokens"] == 2


def test_extract_sse_fields_chat_completions_usage() -> None:
    content, usage = eb.extract_sse_fields({"choices": [{"delta": {"content": "tok"}}]})
    assert (content, usage) == ("tok", None)
    content, usage = eb.extract_sse_fields({"choices": [{"text": "tok"}]})
    assert (content, usage) == ("tok", None)
    content, usage = eb.extract_sse_fields({"choices": [], "usage": {"completion_tokens": 9}})
    assert (content, usage) == (None, 9)
    content, usage = eb.extract_sse_fields({})
    assert (content, usage) == (None, None)


class _FakeResp:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def read1(self, n):  # noqa: ARG002 - mirrors http.client.HTTPResponse.read1
        return self._chunks.pop(0) if self._chunks else b""


def test_read_chunks_incremental_until_eof() -> None:
    resp = _FakeResp([b"a", b"bc", b""])
    assert list(eb.read_chunks(resp)) == [b"a", b"bc"]


# ── metrics + emitters ──


def _ok_sample(ttft, tpot, n_tokens, out_tok_s=10.0):
    return eb.make_sample(
        ttft_ms=ttft,
        tpot_ms=tpot,
        itl_ms=[tpot] * (n_tokens - 1),
        n_tokens=n_tokens,
        text="x" * n_tokens,
        out_tok_s=out_tok_s,
    )


def test_cell_metrics_known_values() -> None:
    samples = [
        _ok_sample(10.0, 2.0, 5),
        _ok_sample(20.0, 4.0, 5),
        _ok_sample(30.0, 6.0, 10),
        eb.make_sample(error="boom"),
    ]
    m = eb.cell_metrics(samples, 10.0)
    assert m["requests"] == 4
    assert m["completed"] == 3
    assert m["errors"] == 1
    assert m["error_rate"] == pytest.approx(0.25)
    assert m["total_tokens"] == 20
    assert m["agg_tok_s"] == pytest.approx(2.0)
    assert m["req_per_s"] == pytest.approx(0.3)
    assert m["ttft_ms_p50"] == pytest.approx(20.0)
    assert m["tpot_ms_p99"] == pytest.approx(5.96)  # [2,4,6]: 4 + 0.98 * 2
    assert m["itl_ms_p50"] == pytest.approx(6.0)  # pooled: 4x2, 4x4, 9x6 -> sorted idx 8


def test_cell_metrics_empty_cell() -> None:
    m = eb.cell_metrics([], 1.0)
    assert m["requests"] == 0
    assert m["error_rate"] == 0.0
    assert m["ttft_ms_p50"] is None
    assert m["tpot_ms_p99"] is None
    assert m["agg_tok_s"] == 0.0


def test_render_markdown_spec_sheet() -> None:
    metrics = eb.cell_metrics([_ok_sample(10.0, 2.0, 5)] * 4, 2.0)
    report = {
        "config": {"target": "http://127.0.0.1:8000/v1/chat/completions", "mix": "chat", "seed": 1},
        "concurrency": [{"concurrency": 8, **metrics}],
        "rate": [],
    }
    md = eb.render_markdown(report)
    assert "# Enterprise serving benchmark" in md
    assert "| C |" in md
    assert "| 8 |" in md
    assert "http://127.0.0.1:8000/v1/chat/completions" in md
    assert "TTFT p50 ms" in md and "agg tok/s" in md


def test_render_markdown_rate_sweep() -> None:
    metrics = eb.cell_metrics([_ok_sample(10.0, 2.0, 5)], 1.0)
    report = {"config": {}, "concurrency": [], "rate": [{"rate": 0.5, **metrics}]}
    md = eb.render_markdown(report)
    assert "| rate req/s |" in md
    assert "| 0.5 |" in md


# ── mixes and prompt synthesis ──


def test_mix_specs_shapes() -> None:
    assert eb.MIX_SPECS["chat"] == {"in_tokens": 1024, "out_tokens": 256}
    assert eb.MIX_SPECS["rag"] == {"in_tokens": 4096, "out_tokens": 512}
    assert eb.MIX_SPECS["summar"] == {"in_tokens": 8192, "out_tokens": 1024}


def test_sharegpt_synthetic_weights_and_determinism() -> None:
    total = sum(w for _, _, w in eb.SHAREGPT_SYNTHETIC)
    assert total == pytest.approx(1.0)
    table = {(a, b) for a, b, _ in eb.SHAREGPT_SYNTHETIC}
    shapes = {eb.mix_shape("sharegpt", i, 99) for i in range(200)}
    assert shapes <= table
    assert len(shapes) >= 3  # real spread across the table
    assert eb.mix_shape("sharegpt", 5, 99) == eb.mix_shape("sharegpt", 5, 99)


def test_fixed_mix_shape_ignores_index() -> None:
    assert eb.mix_shape("chat", 0, 1) == (1024, 256)
    assert eb.mix_shape("rag", 7, 1) == (4096, 512)


def test_synthesize_prompt_deterministic_sized_distinct() -> None:
    a = eb.synthesize_prompt(3, 1024, 42)
    b = eb.synthesize_prompt(3, 1024, 42)
    assert a == b
    assert eb.approx_tokens(a) >= 1024
    assert eb.synthesize_prompt(4, 1024, 42) != a
    assert eb.synthesize_prompt(3, 1024, 43) != a  # seed changes the corpus rotation


def test_approx_tokens_floor() -> None:
    assert eb.approx_tokens("") == 1
    assert eb.approx_tokens("abcd") == 1
    assert eb.approx_tokens("abcde") == 2


def test_build_request_specs_synthetic() -> None:
    specs = eb.build_request_specs("chat", None, 4, seed=5)
    assert len(specs) == 4
    assert all(s["max_tokens"] == 256 for s in specs)
    assert all(s["prompt_tokens_approx"] >= 1024 for s in specs)
    assert specs == eb.build_request_specs("chat", None, 4, seed=5)


def test_build_request_specs_cycles_prompts_file(tmp_path) -> None:
    p = tmp_path / "prompts.jsonl"
    p.write_text(
        json.dumps({"prompt": "hello world", "max_tokens": 7})
        + "\n"
        + json.dumps({"prompt": "second prompt", "expect_prefix": "sec"})
        + "\n"
    )
    specs = eb.build_request_specs("chat", str(p), 5, seed=1)
    assert len(specs) == 5
    assert specs[0]["prompt"] == "hello world"
    assert specs[0]["max_tokens"] == 7
    assert specs[1]["max_tokens"] == eb.MIX_SPECS["chat"]["out_tokens"]  # default fill
    assert specs[1]["expect_prefix"] == "sec"
    assert specs[2]["prompt"] == "hello world"  # cycles
    assert specs[2]["prompt_tokens_approx"] == eb.approx_tokens("hello world")


def test_check_prefix_flags_violations_and_skips_errors() -> None:
    specs = [{}, {}, {}]
    samples = [
        eb.make_sample(n_tokens=2, text="  The answer is 42"),
        eb.make_sample(n_tokens=2, text="wrong"),
        eb.make_sample(error="boom", text="whatever"),
    ]
    violations = eb.check_prefix(samples, specs, "The answer")
    assert len(violations) == 1
    assert violations[0]["index"] == 1


# ── HTTP adapter (payload shapes + URL handling, no network) ──


def test_http_adapter_chat_payload() -> None:
    adapter = eb.HttpAdapter("http://127.0.0.1:8000", "auto", "m", None, 5.0, True)
    assert adapter.path == "/v1/chat/completions"
    assert adapter.endpoint == "chat"
    p = adapter.build_payload("hi", 16)
    assert p["stream"] is True
    assert p["max_tokens"] == 16
    assert p["temperature"] == 0.0
    assert p["messages"] == [{"role": "user", "content": "hi"}]
    assert p["stream_options"] == {"include_usage": True}


def test_http_adapter_completions_payload_no_usage() -> None:
    adapter = eb.HttpAdapter("http://h:9000", "completions", "m", None, 5.0, False)
    assert adapter.path == "/v1/completions"
    p = adapter.build_payload("hi", 8)
    assert p["prompt"] == "hi"
    assert "messages" not in p
    assert "stream_options" not in p


def test_http_adapter_url_handling() -> None:
    a = eb.HttpAdapter("http://127.0.0.1:8000/v1", "auto", "m", None, 5.0, True)
    assert a.path == "/v1/chat/completions"
    b = eb.HttpAdapter("http://h:9000/serving/v1", "completions", "m", None, 5.0, True)
    assert b.path == "/serving/v1/completions"
    c = eb.HttpAdapter("http://h:9000/custom/chat/completions", "auto", "m", None, 5.0, True)
    assert c.path == "/custom/chat/completions"
    assert c.endpoint == "chat"
    d = eb.HttpAdapter("localhost:8000", "auto", "m", None, 5.0, True)
    assert d.scheme == "http" and d.host == "localhost" and d.port == 8000


# ── schedulers ──


class _FakeAdapter:
    def __init__(self):
        self.calls = []
        self._lock = threading.Lock()

    def send(self, spec):
        with self._lock:
            self.calls.append(spec["tag"])
        return eb.make_sample(
            ttft_ms=1.0, tpot_ms=1.0, itl_ms=[1.0], n_tokens=2, text="ok", out_tok_s=1.0
        )


def test_run_closed_loop_issues_each_request_once() -> None:
    adapter = _FakeAdapter()
    specs = [{"tag": i} for i in range(9)]
    samples, wall = eb.run_closed_loop(adapter, specs, 4)
    assert sorted(adapter.calls) == list(range(9))
    assert len(samples) == 9
    assert all(s["error"] is None for s in samples)
    assert wall > 0


def test_run_open_loop_issues_all_requests() -> None:
    adapter = _FakeAdapter()
    specs = [{"tag": i} for i in range(5)]
    samples, wall = eb.run_open_loop(adapter, specs, rate=1000.0, seed=5)
    assert sorted(adapter.calls) == list(range(5))
    assert len(samples) == 5
    assert wall > 0


def test_warmup_cell_sends_first_n() -> None:
    adapter = _FakeAdapter()
    specs = [{"tag": i} for i in range(8)]
    eb.warmup_cell(adapter, specs, 3, concurrency=2)
    assert sorted(adapter.calls) == [0, 1, 2]


# ── JSON-lines driver protocol (real subprocess) ──


_ECHO_DRIVER = """\
import json, sys

for line in sys.stdin:
    req = json.loads(line)
    assert set(req) >= {"id", "prompt", "prompt_tokens_approx", "max_tokens", "stream"}
    assert req["stream"] is True
    resp = {
        "id": req["id"],
        "ttft_ms": 12.5,
        "tpot_ms": 2.0,
        "output_tokens": req["max_tokens"],
        "tokens": ["tok"] * req["max_tokens"],
    }
    sys.stdout.write(json.dumps(resp) + "\\n")
    sys.stdout.flush()
"""


def test_jsonl_driver_round_trip_and_demux(tmp_path) -> None:
    script = tmp_path / "driver.py"
    script.write_text(_ECHO_DRIVER)
    adapter = eb.JsonlDriverAdapter([sys.executable, str(script)], timeout=30.0)
    try:
        spec = {"prompt": "p", "prompt_tokens_approx": 4, "max_tokens": 3}
        # Concurrent sends: responses are demuxed by id, not by arrival order.
        results = [None] * 4
        threads = []
        for i in range(4):
            t = threading.Thread(target=lambda idx=i: results.__setitem__(idx, adapter.send(spec)))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
    finally:
        adapter.close()
    assert all(s["error"] is None for s in results)
    s = results[0]
    assert s["ttft_ms"] == 12.5
    assert s["tpot_ms"] == 2.0
    assert s["n_tokens"] == 3
    assert s["text"] == "toktoktok"
    assert s["itl_ms"] == [2.0, 2.0]
    assert s["out_tok_s"] == pytest.approx(3 / ((12.5 + 2.0 * 2) / 1000.0))


def test_jsonl_driver_error_response(tmp_path) -> None:
    script = tmp_path / "driver.py"
    script.write_text(
        "import json, sys\n"
        "for line in sys.stdin:\n"
        "    req = json.loads(line)\n"
        "    sys.stdout.write(json.dumps({'id': req['id'], 'error': 'oom'}) + '\\n')\n"
        "    sys.stdout.flush()\n"
    )
    adapter = eb.JsonlDriverAdapter([sys.executable, str(script)], timeout=30.0)
    try:
        sample = adapter.send({"prompt": "p", "prompt_tokens_approx": 4, "max_tokens": 3})
    finally:
        adapter.close()
    assert sample["error"] is not None
    assert "oom" in sample["error"]
