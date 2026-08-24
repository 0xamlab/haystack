"""gemma3_race_client.py — the C=50 open-loop aggregate race client (gemma3 lane).

Replicates the MAX sonnet cell's traffic shape against any OpenAI-compatible endpoint:
`num_prompts` requests, `max_concurrency` in flight (request_rate = inf: the next request
starts the instant a slot frees — the harness's max_concurrency semantics), streaming
chat completions, greedy. Reports:

  * aggregate output tok/s  = sum(output_tokens) / wall(run)        (THE race metric)
  * request throughput req/s = num_prompts / wall(run)               (MAX's headline)
  * TTFT p50/mean (client-observed, first SSE content chunk)
  * TPOT p50/mean ((e2e - ttft) / (out_tokens - 1))

Stdlib only (threads + http.client); no third-party deps. Designed for the vLLM /
llama-server / algenta-shim cells of the gemma3 27B lane.

Usage:
  python3 gemma3_race_client.py --base-url http://127.0.0.1:8005 \
      --prompts-dir /tmp/g3race500 --count 500 --concurrency 50 \
      --max-tokens 256 --model gemma3-27b --out /tmp/g3race_vllm_c50.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


def _percentile(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, int(round((p / 100.0) * (len(xs) - 1)))))
    return xs[k]


def run_request(base_url: str, model: str, text: str, max_tokens: int,
                timeout_s: float) -> dict:
    """One streaming chat completion; returns per-request metrics."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": text}],
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "stream": True,
    }).encode()
    req = urllib.request.Request(
        base_url.rstrip("/") + "/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t_start = time.monotonic()
    ttft_ms = None
    n_chunks = 0
    completion_tokens = None
    got_content = False
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        pending = b""
        while True:
            chunk = resp.read(1024)
            if not chunk:
                break
            pending += chunk
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                line = line.strip()
                if not line.startswith(b"data:"):
                    continue
                payload = line[5:].strip()
                if payload == b"[DONE]":
                    continue
                try:
                    obj = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                usage = obj.get("usage")
                if usage and usage.get("completion_tokens") is not None:
                    completion_tokens = int(usage["completion_tokens"])
                choices = obj.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    got_content = True
                    n_chunks += 1
                    if ttft_ms is None:
                        ttft_ms = (time.monotonic() - t_start) * 1000.0
    t_end = time.monotonic()
    out_tokens = completion_tokens if completion_tokens is not None else n_chunks
    return {
        "ok": got_content,
        "out_tokens": out_tokens,
        "ttft_ms": ttft_ms if ttft_ms is not None else (t_end - t_start) * 1000.0,
        "e2e_ms": (t_end - t_start) * 1000.0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--prompts-dir", required=True,
                    help="dir with prompt_NNNN.text files")
    ap.add_argument("--count", type=int, default=500)
    ap.add_argument("--concurrency", type=int, default=50)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--model", default="gemma3-27b")
    ap.add_argument("--timeout", type=float, default=3600.0)
    ap.add_argument("--out", default=None, help="write full JSON results here")
    args = ap.parse_args()

    pdir = Path(args.prompts_dir)
    texts: list[str] = []
    for i in range(args.count):
        p = pdir / f"prompt_{i:04d}.text"
        texts.append(p.read_text())
    print(f"[client] {args.count} prompts loaded | C={args.concurrency} "
          f"| max_tokens={args.max_tokens} | {args.base_url}", flush=True)

    results: list[dict | None] = [None] * args.count
    errors: list[str] = []
    sem = threading.Semaphore(args.concurrency)
    next_idx = [0]
    idx_lock = threading.Lock()
    t_wall_start = time.monotonic()

    def worker() -> None:
        while True:
            with idx_lock:
                i = next_idx[0]
                next_idx[0] += 1
            if i >= args.count:
                return
            with sem:
                try:
                    r = run_request(args.base_url, args.model, texts[i],
                                    args.max_tokens, args.timeout)
                    r["idx"] = i
                    results[i] = r
                    if not r["ok"]:
                        errors.append(f"req {i}: no content")
                except Exception as e:  # noqa: BLE001 — record, keep the cell running
                    errors.append(f"req {i}: {type(e).__name__}: {e}")
                    results[i] = {"ok": False, "idx": i, "out_tokens": 0,
                                  "ttft_ms": None, "e2e_ms": None}

    threads = [threading.Thread(target=worker) for _ in range(args.concurrency)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    t_wall_end = time.monotonic()

    wall_s = t_wall_end - t_wall_start
    ok = [r for r in results if r and r.get("ok")]
    total_out = sum(r["out_tokens"] for r in ok)
    ttfts = [r["ttft_ms"] for r in ok if r.get("ttft_ms") is not None]
    tpots = [(r["e2e_ms"] - r["ttft_ms"]) / (r["out_tokens"] - 1)
             for r in ok
             if r.get("ttft_ms") is not None and r["out_tokens"] > 1]
    summary = {
        "num_prompts": args.count,
        "concurrency": args.concurrency,
        "max_tokens": args.max_tokens,
        "ok_requests": len(ok),
        "errors": len(errors),
        "wall_s": round(wall_s, 3),
        "agg_out_tok_s": round(total_out / wall_s, 2) if wall_s > 0 else 0.0,
        "req_s": round(args.count / wall_s, 3) if wall_s > 0 else 0.0,
        "total_out_tokens": total_out,
        "ttft_ms_p50": round(_percentile(ttfts, 50), 2),
        "ttft_ms_mean": round(statistics.fmean(ttfts), 2) if ttfts else 0.0,
        "tpot_ms_p50": round(_percentile(tpots, 50), 2) if tpots else 0.0,
        "tpot_ms_mean": round(statistics.fmean(tpots), 2) if tpots else 0.0,
        "error_sample": errors[:5],
    }
    print("[client] RESULT:", json.dumps(summary))
    if args.out:
        Path(args.out).write_text(json.dumps(
            {"summary": summary, "results": results}, indent=1))
        print(f"[client] wrote {args.out}")


if __name__ == "__main__":
    main()
