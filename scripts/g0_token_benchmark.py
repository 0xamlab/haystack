#!/usr/bin/env python3
"""G0 token benchmark — proves the Algenta Repositories token-reduction thesis.

Runs a fixed bug suite through three arms and reports tokens / turns / wall-clock /
resolution-rate, plus the honest **expected cost = total tokens / resolution_rate**:

  A  vanilla-agentic    : agent-core sidecar, exploration ON, no injected context
  B  single-shot        : one direct LLM call -> unified diff (≈ provider_backed_chat)
  C  verified_agentic   : agent-core sidecar, exploration SUPPRESSED, evidence injected

Requirements:
  - arms A/C: a running agent-core sidecar  (ALGENTA_AGENT_CORE_URL=http://127.0.0.1:PORT)
  - arms B  : ANTHROPIC_API_KEY  (single-shot direct call)

Usage:
  ALGENTA_AGENT_CORE_URL=http://127.0.0.1:8765 ANTHROPIC_API_KEY=... \
    python3 scripts/g0_token_benchmark.py --arms A,C --reps 1

G0 go/no-go (pre-registered): C resolves within 5pp of A AND C uses <= 0.25x A's tokens.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ANTHROPIC_MODEL = os.environ.get("G0_ANTHROPIC_MODEL", "claude-sonnet-4-6")


# ── Bug suite ────────────────────────────────────────────────────────────────
def _py_check(work: Path, snippet: str) -> bool:
    r = subprocess.run(
        [sys.executable, "-c", snippet], cwd=str(work), capture_output=True, timeout=30
    )
    return r.returncode == 0


FIXTURES = [
    {
        "name": "greet_literal",
        "files": {"greet.py": 'def greet():\n    return "bye"\n'},
        "issue": 'greet() returns "bye" but must return "hi".',
        "suspect_files": ["greet.py"],
        "verify": lambda d: _py_check(d, "from greet import greet; assert greet()=='hi'"),
    },
    {
        "name": "sum_returns_zero",
        "files": {"calc.py": "def total(items):\n    return 0  # BUG: should sum items\n"},
        "issue": "total(items) always returns 0; it must return the sum of items.",
        "suspect_files": ["calc.py"],
        "verify": lambda d: _py_check(d, "from calc import total; assert total([1,2,3])==6"),
    },
]


def _materialize(fix: dict) -> Path:
    d = Path(tempfile.mkdtemp(prefix=f"g0-{fix['name']}-"))
    for rel, content in fix["files"].items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return d


def _evidence_bundle(fix: dict, work: Path) -> str:
    parts = [f"Issue: {fix['issue']}", f"Suspect files: {', '.join(fix['suspect_files'])}", ""]
    for rel in fix["suspect_files"]:
        parts.append(f"=== {rel} ===\n{(work / rel).read_text(encoding='utf-8')}")
    return "\n".join(parts)


# ── Arms ─────────────────────────────────────────────────────────────────────
def _sidecar_run(
    base_url: str,
    work: Path,
    prompt: str,
    injected: str,
    suppress: bool,
    tool_profile: str | None = None,
    max_iterations: int | None = None,
) -> dict:
    body: dict = {
        "working_dir": str(work),
        "prompt": prompt,
        "injected_context": injected,
        "suppress_exploration": suppress,
        "provider": "anthropic",
    }
    if tool_profile:
        body["tool_profile"] = tool_profile
    if max_iterations:
        body["limits"] = {"maxIterations": max_iterations}
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/run",
        data=payload,
        headers={"content-type": "application/json"},
        method="POST",
    )
    final: dict = {}
    with urllib.request.urlopen(req, timeout=400) as resp:
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if line and (frame := json.loads(line)).get("type") == "final":
                final = frame
    tel = final.get("telemetry", {})
    return {
        "status": final.get("status", "unknown"),
        "turns": tel.get("turns", 0),
        "tokens_in": tel.get("tokens_in_uncached", 0),
        "tokens_out": tel.get("tokens_out", 0),
        "cache_read": tel.get("cache_read_tokens", 0),
        "cache_write": tel.get("cache_write_tokens", 0),
        "cost": tel.get("total_cost", 0.0),
    }


def _apply_unified_diff(work: Path, diff: str) -> bool:
    diff = diff.strip()
    if diff.startswith("```"):
        diff = "\n".join(l for l in diff.splitlines() if not l.startswith("```"))
    if not diff.strip():
        return False
    diff_path = work / ".g0.patch"
    diff_path.write_text(diff + "\n", encoding="utf-8")
    for strip in ("-p1", "-p0"):
        r = subprocess.run(
            ["patch", strip, "--no-backup-if-mismatch", "-i", str(diff_path)],
            cwd=str(work),
            capture_output=True,
            timeout=30,
        )
        if r.returncode == 0:
            diff_path.unlink(missing_ok=True)
            return True
    diff_path.unlink(missing_ok=True)
    return False


_EMPTY_SHOT = {
    "turns": 0,
    "tokens_in": 0,
    "tokens_out": 0,
    "cache_read": 0,
    "cache_write": 0,
    "cost": 0.0,
}


def _single_shot(work: Path, fix: dict) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return {"status": "skipped_no_key", **_EMPTY_SHOT}
    files_text = "\n".join(
        f"=== {rel} ===\n{(work / rel).read_text(encoding='utf-8')}" for rel in fix["suspect_files"]
    )
    # AR-OPT-1: stable evidence (suspect files) goes in a cacheable system block so a
    # repeated identical call reuses the prefix; only the volatile issue stays in the
    # user turn — mirroring the production provider_backed_chat planner.
    system_block = [
        {
            "type": "text",
            "text": f"You fix bugs. Repository evidence (authoritative):\n{files_text}",
            "cache_control": {"type": "ephemeral"},
        }
    ]
    user_text = (
        f"Issue: {fix['issue']}\n\n"
        "Return ONLY a unified diff (git-style, with a/ and b/ path prefixes) that fixes it. "
        "No prose, no markdown fences."
    )

    def _call() -> dict:
        body = json.dumps(
            {
                "model": ANTHROPIC_MODEL,
                "max_tokens": 1500,
                "system": system_block,
                "messages": [{"role": "user", "content": user_text}],
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            method="POST",
            headers={
                "content-type": "application/json",
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())

    try:
        # G0_CACHE_WARMUP=1 primes the ephemeral cache with an identical cold call first,
        # so the measured call should report cache_read>0 (validates AR-OPT-1 caching).
        if os.environ.get("G0_CACHE_WARMUP") == "1":
            _call()
        data = _call()
    except Exception as exc:  # noqa: BLE001
        return {"status": f"error:{exc}", **{**_EMPTY_SHOT, "turns": 1}}
    text = "".join(b.get("text", "") for b in data.get("content", []))
    usage = data.get("usage", {})
    applied = _apply_unified_diff(work, text)
    return {
        "status": "completed" if applied else "patch_failed",
        "turns": 1,
        "tokens_in": usage.get("input_tokens", 0),
        "tokens_out": usage.get("output_tokens", 0),
        "cache_read": usage.get("cache_read_input_tokens", 0),
        "cache_write": usage.get("cache_creation_input_tokens", 0),
        "cost": 0.0,
    }


def _run_arm(arm: str, fix: dict, base_url: str | None) -> dict:
    work = _materialize(fix)
    prompt = f"Fix this issue: {fix['issue']} Make the minimal change with your file tools, then stop."
    t0 = time.monotonic()
    if arm == "A":
        if not base_url:
            return {"status": "skipped_no_sidecar"}
        res = _sidecar_run(base_url, work, prompt, injected="", suppress=False)
    elif arm == "C":
        if not base_url:
            return {"status": "skipped_no_sidecar"}
        # Calibrated profile: suppress EXPLORATION but KEEP the shell so the agent can
        # validate its patch and converge (blunt suppress_exploration caused the 11-turn
        # non-converging loop). Hard turn cap as the safety net against runaway re-billing.
        res = _sidecar_run(
            base_url,
            work,
            prompt,
            injected=_evidence_bundle(fix, work),
            suppress=True,
            tool_profile="no_exploration_local_validation",
            max_iterations=10,
        )
    elif arm == "B":
        res = _single_shot(work, fix)
    else:
        raise ValueError(arm)
    res["wall_s"] = round(time.monotonic() - t0, 1)
    try:
        res["resolved"] = bool(fix["verify"](work))
    except Exception:  # noqa: BLE001
        res["resolved"] = False
    shutil.rmtree(work, ignore_errors=True)
    return res


# ── Aggregation / report ─────────────────────────────────────────────────────
def _agg(rows: list[dict]) -> dict:
    done = [r for r in rows if "tokens_in" in r]
    if not done:
        return {"n": 0}
    n = len(done)
    resolved = sum(1 for r in done if r.get("resolved"))
    rate = resolved / n
    tot_in = [r["tokens_in"] for r in done]
    tot_out = [r["tokens_out"] for r in done]
    total_tokens = [i + o for i, o in zip(tot_in, tot_out)]
    mean_total = statistics.mean(total_tokens)
    return {
        "n": n,
        "resolution_rate": rate,
        "median_tokens_in": int(statistics.median(tot_in)),
        "median_tokens_out": int(statistics.median(tot_out)),
        "median_turns": statistics.median([r["turns"] for r in done]),
        "median_wall_s": statistics.median([r.get("wall_s", 0) for r in done]),
        "mean_total_tokens": int(mean_total),
        # AR-OPT-1 prompt-cache split (cumulative across the suite; 0 unless warmed/repeated).
        "total_cache_read": sum(r.get("cache_read", 0) for r in done),
        "total_cache_write": sum(r.get("cache_write", 0) for r in done),
        # Honest comparison: cost per *resolved* fix.
        "expected_tokens_per_fix": int(mean_total / rate) if rate else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="A,B,C")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--fixtures", default="")  # comma names; empty = all
    args = ap.parse_args()
    base_url = os.environ.get("ALGENTA_AGENT_CORE_URL")
    arms = [a.strip().upper() for a in args.arms.split(",") if a.strip()]
    fixtures = [f for f in FIXTURES if not args.fixtures or f["name"] in args.fixtures.split(",")]

    results: dict[str, list[dict]] = {a: [] for a in arms}
    for fix in fixtures:
        for rep in range(args.reps):
            for arm in arms:
                r = _run_arm(arm, fix, base_url)
                r["fixture"], r["rep"], r["arm"] = fix["name"], rep, arm
                results[arm].append(r)
                print(
                    f"[{arm}] {fix['name']} rep{rep}: status={r.get('status')} "
                    f"resolved={r.get('resolved')} turns={r.get('turns')} "
                    f"tok_in={r.get('tokens_in')} tok_out={r.get('tokens_out')} wall={r.get('wall_s')}s",
                    flush=True,
                )

    print("\n=== G0 SUMMARY (per arm) ===")
    agg = {a: _agg(results[a]) for a in arms}
    hdr = (
        f"{'arm':>3} {'n':>3} {'resolve':>8} {'med_in':>8} {'med_out':>8} "
        f"{'med_turns':>10} {'cache_r':>8} {'cache_w':>8} {'exp_tok/fix':>12}"
    )
    print(hdr)
    labels = {"A": "vanilla", "B": "1-shot", "C": "verified"}
    for a in arms:
        g = agg[a]
        if not g.get("n"):
            print(f"{a:>3}  (no data)")
            continue
        print(
            f"{a:>3} {g['n']:>3} {g['resolution_rate']*100:>6.0f}% {g['median_tokens_in']:>8} "
            f"{g['median_tokens_out']:>8} {g['median_turns']:>10} {g['total_cache_read']:>8} "
            f"{g['total_cache_write']:>8} {str(g['expected_tokens_per_fix']):>12}  ({labels.get(a,'')})"
        )

    if "A" in agg and "C" in agg and agg["A"].get("n") and agg["C"].get("n"):
        a_tok, c_tok = agg["A"]["mean_total_tokens"], agg["C"]["mean_total_tokens"]
        ratio = c_tok / a_tok if a_tok else None
        res_ok = agg["C"]["resolution_rate"] >= agg["A"]["resolution_rate"] - 0.05
        tok_ok = ratio is not None and ratio <= 0.25
        print(
            f"\nG0 verdict: C/A tokens = {ratio:.2f} (target ≤0.25 -> {'PASS' if tok_ok else 'FAIL'}); "
            f"C resolution {agg['C']['resolution_rate']*100:.0f}% vs A {agg['A']['resolution_rate']*100:.0f}% "
            f"(within 5pp -> {'PASS' if res_ok else 'FAIL'}) => "
            f"{'GO' if (tok_ok and res_ok) else 'NO-GO (small N — increase --reps/fixtures)'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
