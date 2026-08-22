#!/usr/bin/env python3
"""token_identity_probe.py — cross-driver token-identity diff over the JSONL protocol.

Runs the SAME deterministic request set through two serve drivers (one at a time, each in
its own subprocess, closed-loop C=1 so queueing cannot contaminate the streams) and diffs
the generated token streams request by request. The campaign gate form for a lever that
changes the compute path (e.g. packed3 decode weights): the pre-change driver is the
reference, the levered driver is the candidate; a razor-thin quantized-argmax flip shows up
here as a divergence at the exact position.

Usage:
    python3 token_identity_probe.py \
        --ref "$HOME/leverpush/serve_base /tmp/qwen3smoke" \
        --cand "$HOME/leverpush/serve_full /tmp/qwen3smoke"

Requests: 5 mixed prompts (the selftest's first five shapes — lengths 3/17/64/129/256,
max_tokens 64/33/17/8/5, deterministic byte-window ids), sent one per driver process,
serially. Exit code 0 = token-identical on all requests; 1 = divergences (reported with
first-divergence position per request); 2 = protocol error.
"""

import argparse
import json
import subprocess
import sys


def build_requests() -> list[dict]:
    lens = (3, 17, 64, 129, 256)
    max_toks = (64, 33, 17, 8, 5)
    reqs = []
    for p, (n, mt) in enumerate(zip(lens, max_toks)):
        # deterministic id stream, printable-ASCII range: the JSONL tokenizer contract is
        # token i = decoded byte at index 4*i, and ids >= 128 would encode as multi-byte
        # UTF-8 and break the 4-byte alignment — ASCII keeps one byte per id.
        ids = [(n * 31 + i * 7 + p * 13 + 5) % 96 + 32 for i in range(n)]
        # build a prompt whose decoded bytes ARE the ids (4 bytes per token: id + 'aaa')
        prompt = "".join(chr(i) + "aaa" for i in ids)
        reqs.append(
            {
                "id": p,
                "prompt": prompt,
                "prompt_tokens_approx": n,
                "max_tokens": mt,
                "stream": True,
            }
        )
    return reqs


def run_driver(cmd: str, reqs: list[dict]) -> list[dict]:
    proc = subprocess.Popen(
        cmd.split(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    resps = {}
    try:
        for r in reqs:
            proc.stdin.write(json.dumps(r) + "\n")
            proc.stdin.flush()
            while True:
                line = proc.stdout.readline()
                if not line:
                    raise RuntimeError("driver closed stdout")
                try:
                    resp = json.loads(line)
                except json.JSONDecodeError:
                    continue  # diagnostic lines are legal
                if resp.get("id") == r["id"]:
                    break
            if "error" in resp:
                raise RuntimeError(f"driver error on id {r['id']}: {resp['error']}")
            resps[r["id"]] = resp
    finally:
        proc.stdin.close()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    return [resps[r["id"]] for r in reqs]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True, help="reference driver command (pre-change)")
    ap.add_argument("--cand", required=True, help="candidate driver command (levered)")
    args = ap.parse_args()

    reqs = build_requests()
    print(f"running {len(reqs)} mixed prompts through REF: {args.ref}")
    ref_resps = run_driver(args.ref, reqs)
    print(f"running {len(reqs)} mixed prompts through CAND: {args.cand}")
    cand_resps = run_driver(args.cand, reqs)

    diverged = 0
    total_tokens = 0
    flipped_tokens = 0
    for i, (rr, cr) in enumerate(zip(ref_resps, cand_resps)):
        rt = rr["tokens"]
        ct = cr["tokens"]
        total_tokens += max(len(rt), len(ct))
        n_flip = sum(1 for a, b in zip(rt, ct) if a != b) + abs(len(rt) - len(ct))
        flipped_tokens += n_flip
        if rt == ct:
            print(f"  req {i}: IDENTICAL ({len(rt)} tokens)")
        else:
            diverged += 1
            pos = next((k for k in range(min(len(rt), len(ct))) if rt[k] != ct[k]),
                       min(len(rt), len(ct)))
            print(f"  req {i}: DIVERGED at token {pos} (ref len {len(rt)}, "
                  f"cand len {len(ct)}, {n_flip} differing); ref[{pos}:{pos+4}]="
                  f"{rt[pos:pos+4]} cand[{pos}:{pos+4}]={ct[pos:pos+4]}")
    print(f"RESULT: {'IDENTICAL' if diverged == 0 else 'DIVERGED'} — "
          f"{len(reqs) - diverged}/{len(reqs)} requests token-identical, "
          f"{flipped_tokens} differing tokens of {total_tokens}")
    return 0 if diverged == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
