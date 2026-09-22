#!/usr/bin/env python3
"""Stage 5 release-mechanics probe on a published kernel repository: upgrade, rollback and
interrupted publication, measured as observable loader behaviour (plan v3, Stage 5).

Cases (all on the pinned `kernels` loader):
  1. new process + empty cache      : move branch v1 from B back to A; a fresh cache loads A.
  2. new process + populated cache  : a cache that already holds B; after the move, a new process loads A
                                       (no stale mixing) or keeps B (recorded either way).
  3. running process, libraries loaded: get_kernel again in the same process after the move; the
                                       loader keeps the loaded module (restart required) or reloads.
  4. umbrella pin                   : an umbrella that pins A keeps loading A while v1 points at B.
Branch v1 is restored to B at the end (always, also on failure). A and B must both be known-good
revisions of the repository (the probe never publishes content).

    scripts/hf_kernels/rollback_probe.py --repo thyn-ai/algenta-stats --older <sha A> --current <sha B> [--umbrella thyn-ai/algenta] --out probe.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _token() -> str:
    if os.environ.get("HF_TOKEN"):
        return os.environ["HF_TOKEN"]
    m = re.search(r"^HF_API_KEY=(.+)$", (ROOT / ".env").read_text(), re.M)
    return m.group(1).strip().strip('"').strip("'")


def _api():
    from huggingface_hub import HfApi, constants

    if "kernel" not in constants.REPO_TYPES:
        constants.REPO_TYPES.append("kernel")
    return HfApi(token=_token())


def move_branch(api, repo: str, branch: str, revision: str) -> str:
    api.delete_branch(repo, branch=branch, repo_type="kernel")
    api.create_branch(repo, branch=branch, revision=revision, repo_type="kernel")
    return api.repo_info(repo, repo_type="kernel", revision=branch).sha


def load_in_subprocess(repo: str, hf_home: str, umbrella: str | None = None) -> dict:
    trust = [repo] + ([umbrella] if umbrella else [])
    code = f"""
import json, os, sys
os.environ["HF_HOME"] = {hf_home!r}
from kernels import get_kernel
k = get_kernel({(umbrella or repo)!r}, version=1, backend="cpu", trust_remote_code={trust!r})
mod = k if {umbrella is None!r} else getattr(k, {repo.split('/')[-1].replace('algenta-', '')!r})
print(json.dumps({{"variant": mod.__file__.split("/build/")[1].split("/")[0], "id": sys.modules[mod.__name__].__spec__.name if hasattr(sys.modules[mod.__name__], "__spec__") else None,
                  "snapshot": mod.__file__.split("/snapshots/")[1].split("/")[0] if "/snapshots/" in mod.__file__ else None, "modules": len(mod.modules)}}))
"""
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        return {"error": r.stderr.strip().splitlines()[-1][:300] if r.stderr.strip() else f"exit {r.returncode}"}
    return json.loads(r.stdout.strip().splitlines()[-1])


def running_process_case(repo: str, hf_home: str, api, older: str, current: str) -> dict:
    code = f"""
import json, os
os.environ["HF_HOME"] = {hf_home!r}
from kernels import get_kernel
from huggingface_hub import HfApi, constants
constants.REPO_TYPES.append("kernel")
api = HfApi(token=os.environ["HF_TOKEN"])
k1 = get_kernel({repo!r}, version=1, backend="cpu", trust_remote_code=[{repo!r}])
s1 = k1.__file__.split("/snapshots/")[1].split("/")[0]
api.delete_branch({repo!r}, branch="v1", repo_type="kernel"); api.create_branch({repo!r}, branch="v1", revision={older!r}, repo_type="kernel")
k2 = get_kernel({repo!r}, version=1, backend="cpu", trust_remote_code=[{repo!r}])
s2 = k2.__file__.split("/snapshots/")[1].split("/")[0]
print(json.dumps({{"before": s1, "after": s2, "same_object": k1 is k2}}))
"""
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=900,
                       env={**os.environ, "HF_TOKEN": _token()})
    move_branch(api, repo, "v1", current)  # restore no matter what the child did
    if r.returncode != 0:
        return {"error": r.stderr.strip().splitlines()[-1][:300] if r.stderr.strip() else f"exit {r.returncode}"}
    return json.loads(r.stdout.strip().splitlines()[-1])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--older", required=True, help="revision A (40-hex), a known-good earlier v1 head")
    ap.add_argument("--current", required=True, help="revision B (40-hex), the current v1 head")
    ap.add_argument("--umbrella", help="umbrella repo whose kernel-depends pin revision A of --repo")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    api = _api()
    head = api.repo_info(a.repo, repo_type="kernel", revision="v1").sha
    if head != a.current:
        raise SystemExit(f"v1 is at {head[:8]}, not --current {a.current[:8]}; refusing to run")
    report: dict = {"repo": a.repo, "older": a.older, "current": a.current, "cases": {}}
    empty_cache = tempfile.mkdtemp(prefix="hf-rollback-empty-")
    warm_cache = tempfile.mkdtemp(prefix="hf-rollback-warm-")
    try:
        report["cases"]["baseline_current"] = load_in_subprocess(a.repo, warm_cache)
        moved = move_branch(api, a.repo, "v1", a.older)
        report["moved_v1_to"] = moved
        report["cases"]["1_new_process_empty_cache"] = load_in_subprocess(a.repo, empty_cache)
        report["cases"]["2_new_process_populated_cache"] = load_in_subprocess(a.repo, warm_cache)
        if a.umbrella:
            report["cases"]["4_umbrella_pin_keeps_pinned_revision"] = load_in_subprocess(a.repo, tempfile.mkdtemp(prefix="hf-rollback-umb-"), umbrella=a.umbrella)
        move_branch(api, a.repo, "v1", a.current)
        report["cases"]["3_running_process"] = running_process_case(a.repo, tempfile.mkdtemp(prefix="hf-rollback-run-"), api, a.older, a.current)
        report["cases"]["upgrade_back_to_current"] = load_in_subprocess(a.repo, empty_cache)
    finally:
        restored = move_branch(api, a.repo, "v1", a.current)
        report["restored_v1_to"] = restored
    for k, v in report["cases"].items():
        print(f"{k:40s} {json.dumps(v)}")
    print(f"v1 restored to {report['restored_v1_to'][:8]}")
    if a.out:
        a.out.write_text(json.dumps(report, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
