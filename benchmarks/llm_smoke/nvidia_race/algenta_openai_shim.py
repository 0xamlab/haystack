"""algenta_openai_shim.py — thin OpenAI-compatible HTTP front for algenta's JSONL CUDA driver.

Purpose: let Modular's official `max benchmark` harness (and any OpenAI-compatible client)
drive algenta's batched CUDA serve driver, which speaks JSON-lines over stdin/stdout rather
than HTTP.

Protocol translated (see qwen3_serve_batched_cuda.mojo header):
  request  -> stdin  {"id": int, "prompt": str, "prompt_tokens_approx": int,
                      "max_tokens": int, "stream": true}
  response <- stdout {"id": int, "ttft_ms": float, "tpot_ms": float,
                      "output_tokens": int, "tokens": [str, ...]}
             or      {"id": int, "error": str}
The driver accepts "stream" but has NO incremental deltas (batched protocol), so every
completion arrives as one stdout line. Honesty consequence, documented in the results:
HTTP-observed TTFT equals end-to-end latency for this engine; the driver's own
ttft_ms/tpot_ms (measured inside the engine) are recorded per request in a sidecar
JSONL (--metrics-out) and are the latency metrics reported for algenta cells.

Endpoints: GET /health, GET /v1/models, POST /v1/chat/completions, POST /v1/completions,
POST /reset_prefix_cache (no-op, so `max benchmark` prefix-cache flush paths don't 404).

Usage:
    python3 algenta_openai_shim.py --port 8010 \
        --driver "$HOME/algenta_nv/serve_s4_l7 /tmp/qwen3smoke" \
        --model-name algenta-qwen3-0.6b \
        --metrics-out /tmp/maxbench/algenta_driver_metrics.jsonl

Stdlib only (http.server + threading); no third-party deps.
"""

from __future__ import annotations

import argparse
import itertools
import json
import shlex
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Driver:
    """Manages the JSONL driver subprocess; demuxes responses by id."""

    def __init__(self, argv: list[str], metrics_path: str | None):
        self.argv = argv
        self.metrics_path = metrics_path
        self._lock = threading.Lock()  # serializes stdin writes
        self._pending: dict[int, threading.Event] = {}
        self._results: dict[int, dict] = {}
        self._ids = itertools.count(1)
        self._metrics_lock = threading.Lock()
        self.proc = subprocess.Popen(  # noqa: S603 - explicit argv from the operator
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            line = line.strip()
            if not line or not line.startswith("{"):
                continue  # non-JSON diagnostic lines are allowed per protocol
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            rid = obj.get("id")
            ev = self._pending.get(rid)
            if ev is None:
                continue
            self._results[rid] = obj
            ev.set()

    def generate(self, prompt: str, max_tokens: int, http_start_s: float,
                 timeout_s: float) -> dict:
        rid = next(self._ids)
        ev = threading.Event()
        self._pending[rid] = ev
        req = {"id": rid, "prompt": prompt,
               "prompt_tokens_approx": max(1, len(prompt) // 4),
               "max_tokens": max_tokens, "stream": True}
        try:
            with self._lock:
                assert self.proc.stdin is not None
                self.proc.stdin.write(json.dumps(req) + "\n")
                self.proc.stdin.flush()
            if not ev.wait(timeout_s):
                res = {"id": rid, "error": f"driver timeout after {timeout_s}s"}
            else:
                res = self._results.pop(rid, {"id": rid, "error": "lost response"})
        finally:
            self._pending.pop(rid, None)
        if self.metrics_path is not None:
            rec = {
                "id": rid,
                "http_e2e_ms": (time.monotonic() - http_start_s) * 1000.0,
                "driver_ttft_ms": res.get("ttft_ms"),
                "driver_tpot_ms": res.get("tpot_ms"),
                "output_tokens": res.get("output_tokens", 0),
                "prompt_chars": len(prompt),
                "error": res.get("error"),
            }
            with self._metrics_lock:
                with open(self.metrics_path, "a") as f:
                    f.write(json.dumps(rec) + "\n")
        return res

    def close(self) -> None:
        with self._lock:
            if self.proc.stdin:
                self.proc.stdin.close()
        self.proc.wait(timeout=30)


class State:
    driver: Driver
    model_name: str
    timeout_s: float


def _extract_prompt(body: dict, path: str) -> str:
    if path.endswith("/v1/completions"):
        p = body.get("prompt", "")
        return p if isinstance(p, str) else " ".join(map(str, p))
    msgs = body.get("messages") or []
    # Sonnet workload: the harness already chat-templates into the last user message.
    for m in reversed(msgs):
        if m.get("role") == "user":
            c = m.get("content", "")
            if isinstance(c, str):
                return c
            if isinstance(c, list):  # content-parts form
                return "".join(
                    part.get("text", "") for part in c if isinstance(part, dict)
                )
    return ""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:  # silence per-request logs
        pass

    def _send_json(self, code: int, obj: dict) -> None:
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/health", "/v1/health"):
            self._send_json(200, {"status": "ok"})
        elif self.path == "/v1/models":
            self._send_json(200, {"object": "list", "data": [
                {"id": State.model_name, "object": "model"}]})
        else:
            self._send_json(404, {"error": {"message": f"no route {self.path}"}})

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/reset_prefix_cache":
            self._send_json(200, {"status": "ok"})
            return
        if not (self.path.endswith("/v1/chat/completions")
                or self.path.endswith("/v1/completions")):
            self._send_json(404, {"error": {"message": f"no route {self.path}"}})
            return
        n = int(self.headers.get("Content-Length", "0"))
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": {"message": "bad JSON body"}})
            return
        prompt = _extract_prompt(body, self.path)
        max_tokens = int(body.get("max_tokens") or 256)
        stream = bool(body.get("stream", False))
        start = time.monotonic()
        res = State.driver.generate(prompt, max_tokens, start, State.timeout_s)
        if "error" in res:
            self._send_json(500, {"error": {"message": str(res["error"])}})
            return
        tokens = res.get("tokens") or []
        text = "".join(tokens)
        cid = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        prompt_tokens = max(1, len(prompt) // 4)
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": int(res.get("output_tokens", len(tokens))),
            "total_tokens": prompt_tokens
            + int(res.get("output_tokens", len(tokens))),
        }
        if not stream:
            self._send_json(200, {
                "id": cid, "object": "chat.completion", "created": created,
                "model": State.model_name,
                "choices": [{"index": 0, "finish_reason": "length",
                             "message": {"role": "assistant", "content": text}}],
                "usage": usage})
            return
        # SSE: batched protocol — chunks are emitted when the completion arrives.
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        def chunk(payload: dict) -> None:
            data = f"data: {json.dumps(payload)}\n\n".encode()
            self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")

        base = {"id": cid, "object": "chat.completion.chunk", "created": created,
                "model": State.model_name}
        chunk({**base, "choices": [{"index": 0, "delta": {"role": "assistant"},
                                     "finish_reason": None}]})
        for tok in tokens:
            chunk({**base, "choices": [{"index": 0, "delta": {"content": tok},
                                         "finish_reason": None}]})
        chunk({**base, "choices": [{"index": 0, "delta": {},
                                     "finish_reason": "length"}]})
        if (body.get("stream_options") or {}).get("include_usage"):
            chunk({**base, "choices": [], "usage": usage})
        done = b"data: [DONE]\n\n"
        self.wfile.write(f"{len(done):x}\r\n".encode() + done + b"\r\n")
        self.wfile.write(b"0\r\n\r\n")


class _Server(ThreadingHTTPServer):
    # The official sonnet cell submits 500 requests at inf rate -> ~500 fresh TCP
    # connections in one burst (the harness opens one ClientSession per request);
    # the stock TCPServer listen backlog of 5 overflows and the kernel RSTs
    # connections (measured: Connection reset by peer on the L9 saturation cell).
    request_queue_size = 1024
    daemon_threads = True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8010)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--driver", required=True,
                    help="driver command line, e.g. 'serve_s4_l7 /tmp/qwen3smoke'")
    ap.add_argument("--model-name", default="algenta")
    ap.add_argument("--timeout", type=float, default=3600.0)
    ap.add_argument("--metrics-out", default=None,
                    help="append per-request driver-metric JSONL here")
    args = ap.parse_args()

    State.driver = Driver(shlex.split(args.driver), args.metrics_out)
    State.model_name = args.model_name
    State.timeout_s = args.timeout

    server = _Server((args.host, args.port), Handler)
    print(f"[shim] model={State.model_name} driver={args.driver!r} "
          f"listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        State.driver.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
