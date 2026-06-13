#!/usr/bin/env python3
"""agent_bakeoff.py — run several coding agents on the SAME repo-fix task in
isolated sandboxes and compare wall-time, tokens, cost, and whether the fix
actually verifies.

Each competitor is an *Adapter* (how to invoke it headlessly + how to read its
token usage). Built-in adapters: ``algenta`` (the agent-core sidecar — the home
agent), ``codex`` (OpenAI), ``gemini`` (Google). Add ``cursor`` / ``chatgpt`` /
``aider`` by registering one more Adapter in ADAPTERS — nothing else changes.

Fairness: every agent gets its own fresh ``git clone`` of the repo, the identical
prompt, and the same ``--verify`` command run afterward to decide pass/fail. Token
parsing is best-effort per CLI (the JSON shapes differ and drift); wall-time and
verification are always exact.

Example:
  python scripts/agent_bakeoff.py \
      --repo /path/to/buggy-repo \
      --prompt "Fix the failing test in src/foo.py; keep the public API stable." \
      --verify "pytest -q" \
      --agents algenta,codex,gemini \
      --out build/bakeoff

  # algenta adapter needs the agent-core sidecar running (built + published by escrypto-labs/codna):
  #   docker run -p 8787:8787 ghcr.io/escrypto-labs/codna/sidecar:latest   # serves :8787
  # then: --algenta-url http://127.0.0.1:8787
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable

# Token-usage keys seen across CLIs/providers — scanned recursively, best-effort.
_IN_KEYS = ("input_tokens", "prompt_tokens", "tokens_in_uncached", "promptTokenCount",
            "input", "prompt")
_OUT_KEYS = ("output_tokens", "completion_tokens", "tokens_out", "candidatesTokenCount",
             "output", "candidates")
_CACHE_KEYS = ("cache_read_tokens", "cached_input_tokens", "cachedContentTokenCount")
_COST_KEYS = ("total_cost", "cost_usd", "totalCostUsd")


def _scan_usage(blob: Any, acc: dict[str, float]) -> None:
    """Recursively pull the LAST-seen token/cost counters out of arbitrary JSON.

    CLIs report usage in different shapes (a final ``usage`` object, a ``token_count``
    event, nested ``stats``); we walk everything and keep the largest numeric hit per
    bucket so a cumulative final tally wins over per-step deltas.
    """
    if isinstance(blob, dict):
        for key, value in blob.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                kl = str(key)
                if kl in _IN_KEYS:
                    acc["tokens_in"] = max(acc.get("tokens_in", 0), float(value))
                elif kl in _OUT_KEYS:
                    acc["tokens_out"] = max(acc.get("tokens_out", 0), float(value))
                elif kl in _CACHE_KEYS:
                    acc["cache_tokens"] = max(acc.get("cache_tokens", 0), float(value))
                elif kl in _COST_KEYS:
                    acc["cost_usd"] = max(acc.get("cost_usd", 0.0), float(value))
            else:
                _scan_usage(value, acc)
    elif isinstance(blob, list):
        for item in blob:
            _scan_usage(item, acc)


def _scan_text_for_usage(text: str) -> dict[str, float]:
    """Parse JSON / JSONL stdout for usage. Tolerant of mixed text + JSON lines."""
    acc: dict[str, float] = {}
    # whole-blob JSON first
    try:
        _scan_usage(json.loads(text), acc)
        if acc:
            return acc
    except (ValueError, TypeError):
        pass
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] not in "{[":
            continue
        try:
            _scan_usage(json.loads(line), acc)
        except (ValueError, TypeError):
            continue
    return acc


@dataclass
class RunResult:
    agent: str
    available: bool
    wall_seconds: float | None = None
    tokens_in: float | None = None
    tokens_out: float | None = None
    cache_tokens: float | None = None
    cost_usd: float | None = None
    files_changed: int | None = None
    verified: bool | None = None
    exit_code: int | None = None
    error: str | None = None
    log_path: str | None = None


@dataclass
class Adapter:
    name: str
    # bin that must be on PATH for a CLI adapter (None for the http adapter).
    requires_bin: str | None
    # run(workdir, prompt, model, timeout) -> (exit_code, stdout, stderr)
    run: Callable[..., tuple[int, str, str]]
    extra_available: Callable[[argparse.Namespace], bool] = lambda args: True

    def is_available(self, args: argparse.Namespace) -> bool:
        if self.requires_bin and shutil.which(self.requires_bin) is None:
            return False
        return self.extra_available(args)


# ── adapters ──────────────────────────────────────────────────────────────────

def _run_codex(workdir: Path, prompt: str, model: str | None, timeout: int):
    cmd = ["codex", "exec", "--full-auto", "--json", "-C", str(workdir)]
    if model:
        cmd += ["-m", model]
    cmd.append(prompt)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def _run_gemini(workdir: Path, prompt: str, model: str | None, timeout: int):
    cmd = ["gemini", "-p", prompt, "--approval-mode", "yolo",
           "-o", "json", "--skip-trust"]
    if model:
        cmd += ["-m", model]
    proc = subprocess.run(cmd, cwd=str(workdir), capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def _algenta_url(args: argparse.Namespace) -> str:
    return (
        getattr(args, "algenta_url", None)
        or os.environ.get("ALGENTA_AGENT_CORE_URL")
        or "http://127.0.0.1:8787"
    )


def _algenta_available(args: argparse.Namespace) -> bool:
    base = _algenta_url(args)
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=2) as resp:
            return resp.status == 200
    except Exception:
        return False


def _make_algenta_runner(args: argparse.Namespace):
    base = _algenta_url(args)

    def _run(workdir: Path, prompt: str, model: str | None, timeout: int):
        payload = {"working_dir": str(workdir), "prompt": prompt}
        if model:
            payload["model"] = model
        req = urllib.request.Request(
            f"{base}/run",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
        # NDJSON; the final frame carries telemetry.
        return 0, body, ""

    return _run


ADAPTERS: dict[str, Adapter] = {
    "algenta": Adapter("algenta", None, lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bound at runtime")),
                       extra_available=_algenta_available),
    "codex": Adapter("codex", "codex", _run_codex),
    "gemini": Adapter("gemini", "gemini", _run_gemini),
    # To add Cursor / ChatGPT / aider: register Adapter("cursor", "cursor-agent", _run_cursor) here.
}


# ── sandbox + verification ──────────────────────────────────────────────────

def _prepare_checkout(repo: str, dest: Path) -> None:
    """Fresh, isolated checkout per agent. Local paths clone via file:// (fast,
    hardlinked); remote URLs clone shallow."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if Path(repo).exists():
        subprocess.run(["git", "clone", "--quiet", "--local", str(Path(repo).resolve()), str(dest)],
                       check=True, capture_output=True, text=True)
    else:
        subprocess.run(["git", "clone", "--quiet", "--depth", "1", repo, str(dest)],
                       check=True, capture_output=True, text=True)
    # JS/TS repos: bring the source's node_modules into the checkout (symlink) so
    # the agent + verify run tests without a per-checkout npm install. git clone
    # never copies node_modules (gitignored), so this is safe + fast.
    if Path(repo).exists():
        src_nm = Path(repo).resolve() / "node_modules"
        dest_nm = dest / "node_modules"
        if src_nm.is_dir() and not dest_nm.exists():
            try:
                dest_nm.symlink_to(src_nm, target_is_directory=True)
            except OSError:
                pass


def _files_changed(workdir: Path) -> int:
    proc = subprocess.run(["git", "-C", str(workdir), "status", "--porcelain"],
                          capture_output=True, text=True)
    return len([ln for ln in proc.stdout.splitlines() if ln.strip()])


def _verify(workdir: Path, cmd: str, timeout: int) -> tuple[bool, str]:
    try:
        proc = subprocess.run(cmd, cwd=str(workdir), shell=True, capture_output=True,
                              text=True, timeout=timeout)
        return proc.returncode == 0, proc.stdout[-4000:] + proc.stderr[-4000:]
    except subprocess.TimeoutExpired:
        return False, "verify command timed out"


def _run_one(agent: str, adapter: Adapter, args: argparse.Namespace,
             prompt: str, out_dir: Path) -> RunResult:
    if not adapter.is_available(args):
        return RunResult(agent=agent, available=False,
                         error=f"{agent} not available "
                               f"(missing {adapter.requires_bin or 'sidecar'})")
    workdir = out_dir / f"checkout_{agent}"
    log_path = out_dir / f"{agent}.log"
    try:
        _prepare_checkout(args.repo, workdir)
    except subprocess.CalledProcessError as exc:
        return RunResult(agent=agent, available=True,
                         error=f"checkout failed: {exc.stderr or exc}")

    runner = _make_algenta_runner(args) if agent == "algenta" else adapter.run
    started = time.perf_counter()
    try:
        exit_code, stdout, stderr = runner(workdir, prompt, args.model, args.timeout)
    except subprocess.TimeoutExpired:
        return RunResult(agent=agent, available=True, wall_seconds=float(args.timeout),
                         error="agent run timed out", verified=False,
                         files_changed=_files_changed(workdir))
    except Exception as exc:  # noqa: BLE001 — one agent's failure must not abort the bake-off
        return RunResult(agent=agent, available=True, error=f"agent run error: {exc}")
    wall = time.perf_counter() - started

    log_path.write_text(f"$ {agent}\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}\n",
                        encoding="utf-8")
    usage = _scan_text_for_usage(stdout) or _scan_text_for_usage(stderr)
    verified, _ = _verify(workdir, args.verify, args.verify_timeout) if args.verify else (None, "")

    return RunResult(
        agent=agent, available=True, wall_seconds=round(wall, 3),
        tokens_in=usage.get("tokens_in"), tokens_out=usage.get("tokens_out"),
        cache_tokens=usage.get("cache_tokens"), cost_usd=usage.get("cost_usd"),
        files_changed=_files_changed(workdir), verified=verified,
        exit_code=exit_code, log_path=str(log_path),
    )


def _print_table(results: list[RunResult]) -> None:
    def cell(v: Any) -> str:
        if v is None:
            return "—"
        if isinstance(v, bool):
            return "✅" if v else "❌"
        if isinstance(v, float):
            return f"{v:,.0f}" if v >= 100 else f"{v:.2f}"
        return str(v)

    cols = [("agent", "agent"), ("wall_seconds", "wall_s"), ("tokens_in", "tok_in"),
            ("tokens_out", "tok_out"), ("cache_tokens", "cache"), ("cost_usd", "cost$"),
            ("files_changed", "files"), ("verified", "verified")]
    rows = [[cell(getattr(r, key)) for key, _ in cols] for r in results]
    widths = [max(len(h), *(len(row[i]) for row in rows)) for i, (_, h) in enumerate(cols)]
    line = "  ".join(h.ljust(widths[i]) for i, (_, h) in enumerate(cols))
    print("\n" + line)
    print("  ".join("-" * widths[i] for i in range(len(cols))))
    for row in rows:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(cols))))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True, help="Local path or git URL of the repo to fix.")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt", help="Task instruction given to every agent.")
    g.add_argument("--prompt-file", help="File containing the task instruction.")
    parser.add_argument("--verify", default="", help="Shell command run in the checkout to "
                        "decide pass/fail (e.g. 'pytest -q'). Empty = skip verification.")
    parser.add_argument("--agents", default="algenta,codex,gemini",
                        help=f"Comma list. Known: {','.join(ADAPTERS)}")
    parser.add_argument("--model", default=None, help="Optional model override (per-agent CLIs).")
    parser.add_argument("--algenta-url", default=None, help="agent-core sidecar base URL.")
    parser.add_argument("--timeout", type=int, default=900, help="Per-agent run timeout (s).")
    parser.add_argument("--verify-timeout", type=int, default=300)
    parser.add_argument("--out", default="build/bakeoff", help="Output directory.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only report adapter availability + the resolved plan; run nothing.")
    args = parser.parse_args()

    prompt = args.prompt or Path(args.prompt_file).read_text(encoding="utf-8")
    requested = [a.strip() for a in args.agents.split(",") if a.strip()]
    unknown = [a for a in requested if a not in ADAPTERS]
    if unknown:
        parser.error(f"unknown agents: {unknown}. Known: {list(ADAPTERS)}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        print(f"repo={args.repo}  verify={args.verify or '(none)'}")
        for a in requested:
            print(f"  {a}: {'available' if ADAPTERS[a].is_available(args) else 'UNAVAILABLE'}")
        return 0

    results: list[RunResult] = []
    for a in requested:
        print(f"▶ running {a} …", flush=True)
        results.append(_run_one(a, ADAPTERS[a], args, prompt, out_dir))

    report = {
        "repo": args.repo,
        "prompt": prompt,
        "verify": args.verify,
        "results": [asdict(r) for r in results],
    }
    report_path = out_dir / "bakeoff_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _print_table(results)
    print(f"\nreport: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
