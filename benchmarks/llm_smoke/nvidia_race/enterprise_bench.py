"""enterprise_bench.py — enterprise serving benchmark harness for LLM inference endpoints.

Measures TTFT, TPOT/ITL percentiles (p50/p90/p99), output tok/s per request, aggregate tok/s,
request throughput, and error rate — across closed-loop concurrency points and open-loop
Poisson request-rate sweeps. stdlib only; greedy decoding (temperature 0) throughout; warmup
requests per cell are untimed and excluded.

Targets
-------
(a) Any OpenAI-compatible HTTP endpoint with SSE streaming (vLLM, TensorRT-LLM serve,
    llama-server, SGLang). Requests:

        POST {base}/v1/chat/completions   (or /v1/completions with --endpoint completions)
        {"model": M, "stream": true, "max_tokens": N, "temperature": 0.0,
         "messages": [{"role": "user", "content": P}] | "prompt": P,
         "stream_options": {"include_usage": true}}

    Responses are parsed as SSE (`data: {...}` lines terminated by `data: [DONE]`) with
    incremental http.client reads (read1): keep-alive connections are reused per worker
    thread, and events split mid-chunk are reassembled. Pass --no-usage if a server rejects
    stream_options. A --base-url whose path already ends in /completions is used verbatim.

(b) A JSON-lines subprocess driver — the protocol for algenta's own CUDA serving driver.
    The harness spawns the driver and writes one JSON request per stdin line:

        {"id": int, "prompt": str, "prompt_tokens_approx": int,
         "max_tokens": int, "stream": true}

    The driver writes one JSON response per stdout line, any order (demuxed by id):

        {"id": int, "ttft_ms": float, "tpot_ms": float,
         "output_tokens": int, "tokens": [str, ...]}

    or {"id": int, "error": str} on failure.

Metric definitions
------------------
TTFT  = request write -> first streamed content delta.
ITL   = gaps between consecutive content deltas, pooled across the cell's requests.
TPOT  = (last delta - first delta) / (deltas - 1), per request.
tok/request = usage.completion_tokens when the server reports it, else the delta count;
per-request out tok/s = tok / decode window. Aggregate tok/s = completed tokens / cell wall;
request throughput = completed requests / cell wall. For the JSON-lines driver, ITL samples
are the driver-reported tpot_ms repeated per gap.

Determinism
-----------
Integer seed only (str hashing is salted per process): prompts are synthesized from a fixed
factual corpus via random.Random(seed * STRIDE + index), Poisson arrivals via
random.Random(cell seed). Same seed + shape => byte-identical workload. Token counts are
char/4 approximations unless --prompts JSONL supplies real prompts. The sharegpt mix is an
embedded SYNTHETIC shape distribution, not the ShareGPT dataset.

Usage:
    python3 benchmarks/llm_smoke/nvidia_race/enterprise_bench.py \
        --base-url http://127.0.0.1:8000 --mix chat \
        --concurrency 1,8,16,32,64 --rate-sweep 0.5,1,2,4 --requests 32 --out ~/bench_out
    python3 benchmarks/llm_smoke/nvidia_race/enterprise_bench.py \
        --jsonl-driver "build/algenta-cuda-driver --checkpoint /models/qwen3" --mix rag

Exit codes: 0 ok; 1 correctness violation (--expect-prefix); 2 zero completed requests.
"""

from __future__ import annotations

import argparse
import contextlib
import http.client
import json
import math
import random
import shlex
import shutil
import signal
import statistics
import subprocess
import tempfile
import threading
import time
from collections import deque
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

HARNESS_VERSION = "1.0"
SEED_STRIDE = 1_000_003  # per-index seed derivation; integer-only for cross-process determinism

PROMPT_FACTS = (
    "The capital of France is Paris.",
    "The largest planet in the solar system is Jupiter.",
    "Water boils at 100 degrees Celsius at sea level.",
    "The speed of light in vacuum is 299792458 meters per second.",
    "DNA carries the genetic instructions for living organisms.",
    "The Amazon is the largest river by discharge volume in the world.",
    "Mount Everest is the highest mountain above sea level.",
    "The human heart pumps blood through the circulatory system.",
)

# Request shapes (approximate prompt tokens / max output tokens) per mix.
MIX_SPECS = {
    "chat": {"in_tokens": 1024, "out_tokens": 256},
    "rag": {"in_tokens": 4096, "out_tokens": 512},
    "summar": {"in_tokens": 8192, "out_tokens": 1024},
}

# SYNTHETIC ShareGPT-style shape distribution (not the ShareGPT dataset):
# (prompt tokens, completion tokens, weight).
SHAREGPT_SYNTHETIC = (
    (128, 64, 0.20),
    (256, 128, 0.25),
    (512, 256, 0.25),
    (1024, 256, 0.15),
    (2048, 512, 0.10),
    (4096, 1024, 0.05),
)


def log(msg: str) -> None:
    print(f"[enterprise_bench {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile (pct in [0,100]); 0.0 for empty input."""
    if not values:
        return 0.0
    s = sorted(values)
    pos = (len(s) - 1) * (pct / 100.0)
    lo = int(pos)
    if lo >= len(s) - 1:
        return float(s[-1])
    frac = pos - lo
    return float(s[lo] + frac * (s[lo + 1] - s[lo]))


def poisson_arrivals(n: int, rate: float, seed: int) -> list[float]:
    """Deterministic Poisson arrival offsets (seconds) for n requests at rate req/s."""
    rng = random.Random(seed)
    t = 0.0
    out: list[float] = []
    for _ in range(n):
        t += rng.expovariate(rate)
        out.append(t)
    return out


def approx_tokens(text: str) -> int:
    """char/4 token approximation (stdlib harness carries no tokenizer)."""
    return max(1, math.ceil(len(text) / 4))


def synthesize_prompt(index: int, target_tokens: int, seed: int) -> str:
    """Deterministic real-text prompt of ~target_tokens for request `index`; the seed picks
    the sentence sequence (not a corpus rotation, which integer cycle lengths would erase)."""
    rng = random.Random(seed * SEED_STRIDE + index)
    parts = [f"Request {index}."]
    text = parts[0]
    while approx_tokens(text) < target_tokens:
        parts.append(rng.choice(PROMPT_FACTS))
        text = " ".join(parts)
    return text


def mix_shape(mix: str, index: int, seed: int) -> tuple[int, int]:
    """(in_tokens, out_tokens) for one request of the mix; sharegpt samples the table."""
    if mix != "sharegpt":
        spec = MIX_SPECS[mix]
        return spec["in_tokens"], spec["out_tokens"]
    rng = random.Random(seed * SEED_STRIDE + index)
    total = sum(w for _, _, w in SHAREGPT_SYNTHETIC)
    x = rng.random() * total
    acc = 0.0
    for n_in, n_out, w in SHAREGPT_SYNTHETIC:
        acc += w
        if x <= acc:
            return n_in, n_out
    n_in, n_out, _ = SHAREGPT_SYNTHETIC[-1]
    return n_in, n_out


def default_out_tokens(mix: str) -> int:
    return MIX_SPECS[mix]["out_tokens"] if mix in MIX_SPECS else 256


def load_prompts_jsonl(path: str) -> list[dict]:
    """JSONL prompts: {"prompt"|"text": str, "max_tokens": int?, "expect_prefix": str?}."""
    entries: list[dict] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        prompt = obj.get("prompt") or obj.get("text")
        if not prompt:
            raise ValueError(f"prompts JSONL line missing 'prompt'/'text': {line[:120]}")
        entry: dict = {"prompt": prompt, "expect_prefix": obj.get("expect_prefix")}
        if obj.get("max_tokens"):
            entry["max_tokens"] = int(obj["max_tokens"])
        entries.append(entry)
    if not entries:
        raise ValueError(f"prompts JSONL is empty: {path}")
    return entries


def build_request_specs(mix: str, prompts_file: str | None, n: int, seed: int) -> list[dict]:
    """n deterministic request specs; --prompts JSONL entries cycle when provided."""
    specs: list[dict] = []
    if prompts_file:
        entries = load_prompts_jsonl(prompts_file)
        for i in range(n):
            e = entries[i % len(entries)]
            prompt = e["prompt"]
            specs.append(
                {
                    "prompt": prompt,
                    "prompt_tokens_approx": approx_tokens(prompt),
                    "max_tokens": e.get("max_tokens") or default_out_tokens(mix),
                    "expect_prefix": e.get("expect_prefix"),
                }
            )
        return specs
    for i in range(n):
        n_in, n_out = mix_shape(mix, i, seed)
        prompt = synthesize_prompt(i, n_in, seed)
        specs.append(
            {
                "prompt": prompt,
                "prompt_tokens_approx": approx_tokens(prompt),
                "max_tokens": n_out,
                "expect_prefix": None,
            }
        )
    return specs


# ── SSE parsing (pure functions over byte chunks: unit-testable with canned streams) ──


def iter_lines(chunks) -> Iterator[str]:
    """Yield text lines from byte chunks; carries remainders across chunk boundaries."""
    buf = b""
    for chunk in chunks:
        if not chunk:
            continue
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            yield line.rstrip(b"\r").decode("utf-8", "replace")
    if buf:
        yield buf.rstrip(b"\r").decode("utf-8", "replace")


def sse_data_payloads(lines) -> Iterator[str]:
    """Yield JSON payload strings of SSE `data:` lines; stop at `data: [DONE]`."""
    for line in lines:
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        if not payload:
            continue
        if payload == "[DONE]":
            return
        yield payload


def extract_sse_fields(obj: dict) -> tuple[str | None, int | None]:
    """(content, usage completion_tokens) from one streamed OpenAI-compatible chunk."""
    usage = obj.get("usage") or {}
    usage_tokens = usage.get("completion_tokens")
    content = None
    choices = obj.get("choices") or []
    if choices:
        choice = choices[0]
        delta = choice.get("delta") or {}
        content = delta.get("content") or choice.get("text")
    return content, usage_tokens


def read_chunks(resp, size: int = 65536):
    """Incremental body reads: read1 returns as soon as any bytes arrive (chunk-safe),
    unlike read(n) which blocks until n bytes accumulate."""
    while True:
        chunk = resp.read1(size)
        if not chunk:
            break
        yield chunk


# ── samples ──


def make_sample(
    error: str | None = None,
    ttft_ms: float | None = None,
    tpot_ms: float | None = None,
    itl_ms=(),
    n_tokens: int = 0,
    text: str = "",
    out_tok_s: float | None = None,
) -> dict:
    return {
        "error": error,
        "ttft_ms": ttft_ms,
        "tpot_ms": tpot_ms,
        "itl_ms": list(itl_ms),
        "n_tokens": n_tokens,
        "text": text,
        "out_tok_s": out_tok_s,
    }


# ── adapters ──


class HttpAdapter:
    """OpenAI-compatible SSE endpoint; one keep-alive http.client connection per thread."""

    def __init__(
        self,
        base_url: str,
        endpoint: str,
        model: str,
        api_key: str | None,
        timeout: float,
        include_usage: bool,
    ):
        if "://" not in base_url:
            base_url = "http://" + base_url
        parsed = urlparse(base_url)
        self.scheme = parsed.scheme or "http"
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or (443 if self.scheme == "https" else 80)
        path = parsed.path.rstrip("/")
        if path.endswith(("/chat/completions", "/completions")):
            # Full endpoint path given verbatim; it decides the payload shape.
            self.path = path
            self.endpoint = "chat" if path.endswith("/chat/completions") else "completions"
        else:
            if path.endswith("/v1"):
                path = path[:-3]
            self.endpoint = "completions" if endpoint == "completions" else "chat"
            suffix = "/v1/chat/completions" if self.endpoint == "chat" else "/v1/completions"
            self.path = path + suffix
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.include_usage = include_usage
        self._tls = threading.local()

    @property
    def label(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}{self.path}"

    def _connect(self):
        cls = http.client.HTTPSConnection if self.scheme == "https" else http.client.HTTPConnection
        return cls(self.host, self.port, timeout=self.timeout)

    def _conn(self):
        conn = getattr(self._tls, "conn", None)
        if conn is None:
            conn = self._connect()
            self._tls.conn = conn
        return conn

    def _drop_conn(self) -> None:
        conn = getattr(self._tls, "conn", None)
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.close()
        self._tls.conn = None

    def build_payload(self, prompt: str, max_tokens: int) -> dict:
        payload: dict = {
            "model": self.model,
            "stream": True,
            "max_tokens": max_tokens,
            "temperature": 0.0,
        }
        if self.include_usage:
            payload["stream_options"] = {"include_usage": True}
        if self.endpoint == "chat":
            payload["messages"] = [{"role": "user", "content": prompt}]
        else:
            payload["prompt"] = prompt
        return payload

    def send(self, spec: dict) -> dict:
        body = json.dumps(self.build_payload(spec["prompt"], spec["max_tokens"])).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            return self._stream(self._conn(), body, headers)
        except (http.client.HTTPException, OSError):
            # Keep-alive may have been closed server-side: reconnect once, then give up.
            self._drop_conn()
            try:
                return self._stream(self._conn(), body, headers)
            except (http.client.HTTPException, OSError) as exc:
                return make_sample(error=f"http: {exc.__class__.__name__}: {exc}")

    def _stream(self, conn, body: bytes, headers: dict) -> dict:
        t0 = time.perf_counter()
        conn.request("POST", self.path, body=body, headers=headers)
        resp = conn.getresponse()
        try:
            if resp.status != 200:
                detail = resp.read(512).decode("utf-8", "replace")
                return make_sample(error=f"http {resp.status}: {detail[:200]}")
            first = None
            times: list[float] = []
            parts: list[str] = []
            usage_tokens = None
            for payload in sse_data_payloads(iter_lines(read_chunks(resp))):
                try:
                    obj = json.loads(payload)
                except ValueError:
                    continue
                content, usage = extract_sse_fields(obj)
                if usage is not None:
                    usage_tokens = usage
                if content:
                    now = time.perf_counter()
                    if first is None:
                        first = now
                    times.append(now)
                    parts.append(content)
            end = time.perf_counter()
        finally:
            with contextlib.suppress(Exception):
                resp.read()  # drain so the keep-alive connection is reusable
            resp.close()
        if first is None:
            return make_sample(error="stream completed with zero content deltas")
        itl_ms = [(b - a) * 1000.0 for a, b in zip(times, times[1:], strict=False)]
        tpot_ms = statistics.fmean(itl_ms) if itl_ms else None
        n_tokens = usage_tokens if usage_tokens else len(times)
        window = (times[-1] - first) if len(times) >= 2 else (end - first)
        out_tok_s = n_tokens / window if window > 0 else None
        return make_sample(
            ttft_ms=(first - t0) * 1000.0,
            tpot_ms=tpot_ms,
            itl_ms=itl_ms,
            n_tokens=n_tokens,
            text="".join(parts),
            out_tok_s=out_tok_s,
        )


class JsonlDriverAdapter:
    """JSON-lines subprocess driver: one request object per stdin line, one response per
    stdout line (any order, demuxed by id). See the module docstring for the protocol."""

    def __init__(self, argv: list[str], timeout: float):
        self.argv = argv
        self.timeout = timeout
        self.proc = subprocess.Popen(  # noqa: S603 - explicit argv from the operator
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._write_lock = threading.Lock()
        self._pending: dict[int, dict] = {}
        self._next_id = 0
        self._dead: str | None = None
        self._stderr_tail = ""
        threading.Thread(target=self._read_loop, daemon=True).start()
        threading.Thread(target=self._err_loop, daemon=True).start()

    @property
    def label(self) -> str:
        return " ".join(self.argv)

    def _read_loop(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            rid = obj.get("id")
            if not isinstance(rid, int):
                continue
            with self._cv:
                self._pending[rid] = obj
                self._cv.notify_all()
        with self._cv:
            self._dead = f"driver exited (rc={self.proc.poll()}): {self._stderr_tail[-200:]}"
            self._cv.notify_all()

    def _err_loop(self) -> None:
        assert self.proc.stderr is not None
        for line in self.proc.stderr:
            self._stderr_tail = (self._stderr_tail + line)[-400:]

    def send(self, spec: dict) -> dict:
        with self._cv:
            rid = self._next_id
            self._next_id += 1
        req = {
            "id": rid,
            "prompt": spec["prompt"],
            "prompt_tokens_approx": spec["prompt_tokens_approx"],
            "max_tokens": spec["max_tokens"],
            "stream": True,
        }
        try:
            # Writers serialize on their OWN lock, never on the condition's lock. The
            # write below blocks while the driver's stdin pipe is full — for a batch-1
            # driver that is the whole duration of the request it is computing (minutes
            # at rag shapes). Holding self._lock across that wait freezes every thread
            # that needs it: _read_loop cannot store the responses it has already read,
            # and no worker can reach its deadline check (the check lives inside
            # `with self._cv`). Those two freezes chain into a permanent four-way wait
            # once the driver's stdout pipe fills — the rag C=32 deadlock (reproduced:
            # every worker parked in send(), the lock holder parked in stdin.write()).
            # With a writer-private lock a blocked writer stalls only the other writers;
            # responses keep flowing, deadlines keep running, and the driver's stdout
            # pipe keeps draining, so the driver always returns to read its stdin.
            with self._write_lock:
                if self.proc.poll() is not None:
                    raise RuntimeError(f"driver exited rc={self.proc.returncode}")
                assert self.proc.stdin is not None
                self.proc.stdin.write(json.dumps(req) + "\n")
                self.proc.stdin.flush()
        except (RuntimeError, OSError, ValueError) as exc:
            return make_sample(error=f"driver: {exc}")
        deadline = time.perf_counter() + self.timeout
        with self._cv:
            while rid not in self._pending:
                if self._dead:
                    return make_sample(error=f"driver: {self._dead}")
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    return make_sample(error="driver: response timeout")
                self._cv.wait(timeout=min(remaining, 1.0))
            resp = self._pending.pop(rid)
        if resp.get("error"):
            return make_sample(error=f"driver: {resp['error']}")
        try:
            ttft_ms = float(resp["ttft_ms"])
            tpot_ms = float(resp["tpot_ms"])
            n_tokens = int(resp["output_tokens"])
        except (KeyError, TypeError, ValueError) as exc:
            return make_sample(error=f"driver: malformed response: {exc}")
        text = "".join(str(t) for t in resp.get("tokens") or [])
        itl_ms = [tpot_ms] * max(0, n_tokens - 1)
        total_ms = ttft_ms + tpot_ms * max(0, n_tokens - 1)
        out_tok_s = n_tokens / (total_ms / 1000.0) if total_ms > 0 else None
        return make_sample(
            ttft_ms=ttft_ms,
            tpot_ms=tpot_ms,
            itl_ms=itl_ms,
            n_tokens=n_tokens,
            text=text,
            out_tok_s=out_tok_s,
        )

    def close(self) -> None:
        with contextlib.suppress(Exception):
            if self.proc.stdin:
                self.proc.stdin.close()
        with contextlib.suppress(Exception):
            self.proc.terminate()
            self.proc.wait(timeout=5)


# ── schedulers ──


def warmup_cell(adapter, specs: list[dict], count: int, concurrency: int) -> None:
    """Untimed warmup burst at the cell's shape (session warmth + DVFS ramp)."""
    if count <= 0 or not specs:
        return
    burst = specs[:count]
    queue = deque(burst)
    lock = threading.Lock()

    def worker() -> None:
        while True:
            with lock:
                spec = queue.popleft() if queue else None
            if spec is None:
                return
            adapter.send(spec)

    threads = []
    for _ in range(min(concurrency, len(burst))):
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()


def run_closed_loop(adapter, specs: list[dict], concurrency: int) -> tuple[list[dict], float]:
    """C workers pulling from a shared queue until n requests are done; returns (samples, wall)."""
    results: list[dict | None] = [None] * len(specs)
    queue = deque(range(len(specs)))
    lock = threading.Lock()

    def worker() -> None:
        while True:
            with lock:
                i = queue.popleft() if queue else None
            if i is None:
                return
            results[i] = adapter.send(specs[i])

    t0 = time.perf_counter()
    threads = []
    for _ in range(min(concurrency, len(specs))):
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return results, time.perf_counter() - t0  # type: ignore[return-value]


def run_open_loop(adapter, specs: list[dict], rate: float, seed: int) -> tuple[list[dict], float]:
    """Poisson arrivals at `rate` req/s regardless of completion; returns (samples, wall)."""
    arrivals = poisson_arrivals(len(specs), rate, seed)
    results: list[dict | None] = [None] * len(specs)
    threads = []
    t0 = time.perf_counter()
    for i, t_arr in enumerate(arrivals):
        delay = (t0 + t_arr) - time.perf_counter()
        if delay > 0:
            time.sleep(delay)

        def runner(idx: int = i) -> None:
            results[idx] = adapter.send(specs[idx])

        t = threading.Thread(target=runner, daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return results, time.perf_counter() - t0  # type: ignore[return-value]


# ── aggregation + emitters ──


def cell_metrics(samples: list[dict], wall_s: float) -> dict:
    total = len(samples)
    ok = [s for s in samples if s is not None and s["error"] is None]
    errors = total - len(ok)
    ttft = [s["ttft_ms"] for s in ok if s["ttft_ms"] is not None]
    tpot = [s["tpot_ms"] for s in ok if s["tpot_ms"] is not None]
    itl = [gap for s in ok for gap in s["itl_ms"]]
    tps = [s["out_tok_s"] for s in ok if s["out_tok_s"] is not None]
    tokens = sum(s["n_tokens"] for s in ok)

    def pct(vals: list[float], p: float) -> float | None:
        return percentile(vals, p) if vals else None

    return {
        "requests": total,
        "completed": len(ok),
        "errors": errors,
        "error_rate": errors / total if total else 0.0,
        "wall_s": wall_s,
        "ttft_ms_p50": pct(ttft, 50),
        "ttft_ms_p90": pct(ttft, 90),
        "ttft_ms_p99": pct(ttft, 99),
        "tpot_ms_p50": pct(tpot, 50),
        "tpot_ms_p90": pct(tpot, 90),
        "tpot_ms_p99": pct(tpot, 99),
        "itl_ms_p50": pct(itl, 50),
        "itl_ms_p90": pct(itl, 90),
        "itl_ms_p99": pct(itl, 99),
        "out_tok_s_p50": pct(tps, 50),
        "total_tokens": tokens,
        "agg_tok_s": tokens / wall_s if wall_s > 0 else 0.0,
        "req_per_s": len(ok) / wall_s if wall_s > 0 else 0.0,
    }


def check_prefix(samples: list[dict], specs: list[dict], global_prefix: str | None) -> list[dict]:
    """Correctness hook: completions must start with the per-spec or global expected prefix."""
    violations = []
    for i, (sample, spec) in enumerate(zip(samples, specs, strict=True)):
        if sample is None or sample["error"] is not None:
            continue
        expected = spec.get("expect_prefix") or global_prefix
        if not expected:
            continue
        text = sample["text"].strip()
        if not text.startswith(expected.strip()):
            violations.append({"index": i, "expected": expected, "got": text[:80]})
    return violations


def fmt(x: float | None, nd: int = 1) -> str:
    return "—" if x is None else f"{x:.{nd}f}"


_METRIC_COLUMNS = (
    "reqs",
    "ok",
    "err %",
    "TTFT p50 ms",
    "TTFT p90 ms",
    "TTFT p99 ms",
    "TPOT p50 ms",
    "TPOT p90 ms",
    "TPOT p99 ms",
    "ITL p50 ms",
    "ITL p90 ms",
    "ITL p99 ms",
    "out tok/s p50",
    "agg tok/s",
    "req/s",
)


def _metric_row(m: dict) -> str:
    return " | ".join(
        (
            str(m["requests"]),
            str(m["completed"]),
            f"{m['error_rate'] * 100:.2f}",
            fmt(m["ttft_ms_p50"]),
            fmt(m["ttft_ms_p90"]),
            fmt(m["ttft_ms_p99"]),
            fmt(m["tpot_ms_p50"]),
            fmt(m["tpot_ms_p90"]),
            fmt(m["tpot_ms_p99"]),
            fmt(m["itl_ms_p50"]),
            fmt(m["itl_ms_p90"]),
            fmt(m["itl_ms_p99"]),
            fmt(m["out_tok_s_p50"]),
            fmt(m["agg_tok_s"]),
            fmt(m["req_per_s"], 2),
        )
    )


def render_markdown(report: dict) -> str:
    """Spec-sheet markdown: configuration + numbers only."""
    lines = ["# Enterprise serving benchmark", "", "## Configuration", ""]
    lines += ["| key | value |", "|---|---|"]
    for key, value in report["config"].items():
        lines.append(f"| {key} | {value} |")
    if report["concurrency"]:
        lines += ["", "## Concurrency sweep (closed loop)", ""]
        lines.append("| C | " + " | ".join(_METRIC_COLUMNS) + " |")
        lines.append("|---" * (len(_METRIC_COLUMNS) + 1) + "|")
        for row in report["concurrency"]:
            lines.append(f"| {row['concurrency']} | {_metric_row(row)} |")
    if report["rate"]:
        lines += ["", "## Rate sweep (open-loop Poisson)", ""]
        lines.append("| rate req/s | " + " | ".join(_METRIC_COLUMNS) + " |")
        lines.append("|---" * (len(_METRIC_COLUMNS) + 1) + "|")
        for row in report["rate"]:
            lines.append(f"| {row['rate']:g} | {_metric_row(row)} |")
    return "\n".join(lines) + "\n"


# ── GPU evidence ──


def gpu_name() -> str | None:
    if shutil.which("nvidia-smi") is None:
        return None
    try:
        out = (
            subprocess.run(
                [  # noqa: S607 - system tool, presence checked via shutil.which
                    "nvidia-smi",
                    "--query-gpu=name,driver_version,memory.total",
                    "--format=csv,noheader",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            .stdout.strip()
            .splitlines()
        )
        return out[0] if out else None
    except (OSError, subprocess.SubprocessError):
        return None


class ClockSampler:
    """nvidia-smi --query-gpu at 500 ms; clock/power/thermal evidence for the run."""

    def __init__(self, out_path: Path):
        self.out_path = Path(out_path)
        self.proc = None
        self._handle = None

    def start(self) -> None:
        if shutil.which("nvidia-smi") is None:
            return
        self._handle = self.out_path.open("w")
        self.proc = subprocess.Popen(
            [  # noqa: S607 - system tool, presence checked via shutil.which
                "nvidia-smi",
                "--query-gpu=clocks.sm,clocks.mem,temperature.gpu,power.draw,utilization.gpu",
                "--format=csv,noheader,nounits",
                "-lms",
                "500",
            ],
            stdout=self._handle,
            stderr=subprocess.DEVNULL,
        )

    def stop(self) -> dict:
        if self.proc is None:
            return {"clocks_present": False}
        with contextlib.suppress(Exception):
            self.proc.send_signal(signal.SIGINT)
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        if self._handle is not None:
            self._handle.close()
        sm_clocks: list[int] = []
        temps: list[int] = []
        powers: list[float] = []
        for line in self.out_path.read_text().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                try:
                    sm_clocks.append(int(parts[0]))
                    temps.append(int(parts[2]))
                    powers.append(float(parts[3]))
                except ValueError:
                    continue
        if not sm_clocks:
            return {"clocks_present": True, "clock_samples": 0}
        return {
            "clocks_present": True,
            "clock_samples": len(sm_clocks),
            "sm_clock_mhz_min": min(sm_clocks),
            "sm_clock_mhz_max": max(sm_clocks),
            "temp_c_max": max(temps),
            "power_w_max": max(powers),
        }


# ── main ──


def _parse_csv_ints(raw: str) -> list[int]:
    return [int(x) for x in raw.split(",") if x.strip()]


def _parse_csv_floats(raw: str) -> list[float]:
    return [float(x) for x in raw.split(",") if x.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--base-url", default=None, help="OpenAI-compatible endpoint base URL")
    ap.add_argument("--api-key", default=None, help="bearer token for the endpoint")
    ap.add_argument(
        "--endpoint",
        choices=("auto", "chat", "completions"),
        default="auto",
        help="payload shape; auto = chat",
    )
    ap.add_argument("--model", default="default", help="model name sent in the payload")
    ap.add_argument(
        "--no-usage",
        action="store_true",
        help="omit stream_options.include_usage (servers that reject unknown fields)",
    )
    ap.add_argument(
        "--jsonl-driver", default=None, help="JSON-lines driver command (see module docstring)"
    )
    ap.add_argument("--mix", choices=("chat", "rag", "summar", "sharegpt"), default="chat")
    ap.add_argument("--prompts", default=None, help="JSONL prompt file overriding synthesis")
    ap.add_argument("--concurrency", default="1,8,16,32,64", help="closed-loop levels")
    ap.add_argument("--rate-sweep", default="", help="open-loop Poisson rates, req/s")
    ap.add_argument("--requests", type=int, default=32, help="requests per sweep point")
    ap.add_argument("--warmup", type=int, default=2, help="untimed warmup requests per cell")
    ap.add_argument("--seed", type=int, default=20260820, help="workload seed")
    ap.add_argument(
        "--expect-prefix",
        default=None,
        help="correctness hook: every completion must start with this text",
    )
    ap.add_argument("--timeout", type=float, default=600.0, help="per-request timeout, s")
    ap.add_argument("--out", default=None, help="output dir (JSON + markdown + clocks.csv)")
    args = ap.parse_args()

    if bool(args.base_url) == bool(args.jsonl_driver):
        ap.error("exactly one of --base-url or --jsonl-driver is required")
    concurrency = _parse_csv_ints(args.concurrency)
    rates = _parse_csv_floats(args.rate_sweep)
    if not concurrency and not rates:
        ap.error("nothing to run: --concurrency and --rate-sweep are both empty")
    if args.requests <= 0:
        ap.error("--requests must be positive")

    if args.jsonl_driver:
        adapter = JsonlDriverAdapter(shlex.split(args.jsonl_driver), args.timeout)
        target_label = adapter.label
    else:
        adapter = HttpAdapter(
            args.base_url,
            args.endpoint,
            args.model,
            args.api_key,
            args.timeout,
            include_usage=not args.no_usage,
        )
        target_label = adapter.label
    log(f"target: {target_label}")
    log(f"mix={args.mix} requests/point={args.requests} warmup={args.warmup} seed={args.seed}")

    persist = args.out is not None
    out_dir = (
        Path(args.out).expanduser() if persist else Path(tempfile.mkdtemp("enterprise_bench."))
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    sampler = ClockSampler(out_dir / "clocks.csv")
    sampler.start()
    started = time.time()
    conc_rows: list[dict] = []
    rate_rows: list[dict] = []
    violations: list[dict] = []
    total_completed = 0
    try:
        for c in concurrency:
            cell_seed = args.seed * 7919 + c
            specs = build_request_specs(args.mix, args.prompts, args.requests, cell_seed)
            log(f"[C={c}] warmup {args.warmup} + {len(specs)} requests")
            warmup_cell(adapter, specs, args.warmup, c)
            samples, wall = run_closed_loop(adapter, specs, c)
            violations += check_prefix(samples, specs, args.expect_prefix)
            row = {"concurrency": c, **cell_metrics(samples, wall)}
            total_completed += row["completed"]
            conc_rows.append(row)
            log(
                f"[C={c}] ok={row['completed']}/{row['requests']} "
                f"ttft p50={fmt(row['ttft_ms_p50'])} ms tpot p50={fmt(row['tpot_ms_p50'])} ms "
                f"agg={fmt(row['agg_tok_s'])} tok/s req/s={fmt(row['req_per_s'], 2)}"
            )
        for r in rates:
            cell_seed = args.seed * 7919 + int(round(r * 1000))
            specs = build_request_specs(args.mix, args.prompts, args.requests, cell_seed)
            log(f"[rate={r:g} req/s] warmup {args.warmup} + {len(specs)} requests (open loop)")
            warmup_cell(adapter, specs, args.warmup, max(1, args.warmup))
            samples, wall = run_open_loop(adapter, specs, r, cell_seed)
            violations += check_prefix(samples, specs, args.expect_prefix)
            row = {"rate": r, **cell_metrics(samples, wall)}
            total_completed += row["completed"]
            rate_rows.append(row)
            log(
                f"[rate={r:g}] ok={row['completed']}/{row['requests']} "
                f"ttft p50={fmt(row['ttft_ms_p50'])} ms agg={fmt(row['agg_tok_s'])} tok/s"
            )
    finally:
        clocks = sampler.stop()
        if isinstance(adapter, JsonlDriverAdapter):
            adapter.close()

    mix_desc = args.mix
    if args.mix in MIX_SPECS:
        spec = MIX_SPECS[args.mix]
        mix_desc = f"{args.mix} (in {spec['in_tokens']} / out {spec['out_tokens']})"
    elif args.mix == "sharegpt":
        mix_desc = "sharegpt (synthetic shape distribution, 6 shapes)"
    if args.prompts:
        mix_desc += f" + prompts file {args.prompts}"

    config = {
        "harness": f"enterprise_bench/{HARNESS_VERSION}",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "target": target_label,
        "model": None if args.jsonl_driver else args.model,
        "mix": mix_desc,
        "requests_per_point": args.requests,
        "warmup_per_cell": args.warmup,
        "seed": args.seed,
        "concurrency_points": concurrency,
        "rate_points_rps": rates,
        "expect_prefix": bool(args.expect_prefix),
        "protocol": "closed-loop concurrency + open-loop Poisson; greedy; warmup excluded",
        "gpu": gpu_name() or "n/a",
        **clocks,
        "total_wall_s": round(time.time() - started, 3),
    }
    report = {"config": config, "concurrency": conc_rows, "rate": rate_rows}
    markdown = render_markdown(report)
    print(markdown)

    if persist:
        json_path = out_dir / "enterprise_bench.json"
        md_path = out_dir / "enterprise_bench.md"
        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        md_path.write_text(markdown, encoding="utf-8")
        log(f"wrote {json_path} and {md_path}")
    else:
        print("=== JSON report ===")
        print(json.dumps(report, indent=2))

    if violations:
        for v in violations[:10]:
            log(
                f"prefix violation at request {v['index']}: expected {v['expected']!r}, "
                f"got {v['got']!r}"
            )
        log(f"CORRECTNESS FAILURE: {len(violations)} prefix violations")
        return 1
    if (conc_rows or rate_rows) and total_completed == 0:
        log("no request completed successfully")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
