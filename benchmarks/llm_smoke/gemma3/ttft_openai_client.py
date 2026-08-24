"""ttft_openai_client.py — streaming TTFT probe for an OpenAI-compatible endpoint.

Sends the same prompt N times (sequentially) to /v1/completions with stream=true and
records wall time to the first content-bearing SSE chunk = TTFT. max_tokens=2 keeps the
decode tail out of the measurement window.

Usage:
  python3 ttft_openai_client.py --base-url http://localhost:8091/v1 \
      --model <model name> --prompt-file /tmp/g3pf_gate/prompts_race/prompt_550.text --n 3
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request


def one_request(base_url: str, model: str, prompt: str) -> tuple[float, float, str]:
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "max_tokens": 2,
        "temperature": 0.0,
        "stream": True,
    }).encode()
    req = urllib.request.Request(
        base_url.rstrip("/") + "/completions",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    ttft = -1.0
    text = ""
    with urllib.request.urlopen(req, timeout=600) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue
            choices = obj.get("choices") or []
            if choices:
                delta = choices[0].get("text", "")
                if delta and ttft < 0:
                    ttft = time.perf_counter() - t0
                text += delta
    total = time.perf_counter() - t0
    return ttft, total, text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt-file", required=True)
    ap.add_argument("--n", type=int, default=3)
    args = ap.parse_args()

    prompt = open(args.prompt_file).read()
    ttfts = []
    for i in range(args.n):
        ttft, total, text = one_request(args.base_url, args.model, prompt)
        ttfts.append(ttft)
        print(f"rep {i + 1}: ttft_ms={ttft * 1000:.1f} total_ms={total * 1000:.1f} "
              f"first={text[:24]!r}")
    ttfts.sort()
    print(f"MEDIAN_ttft_ms={ttfts[len(ttfts) // 2] * 1000:.1f}")


if __name__ == "__main__":
    main()
