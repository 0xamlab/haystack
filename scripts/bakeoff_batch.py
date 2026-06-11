#!/usr/bin/env python3
"""Run a batch of planted-bug bake-offs across several public-repo-matrix repos
and aggregate a win/loss rate (algenta vs codex/gemini on tokens + time).

For each case: clone@pin -> plant one bug -> validate the oracle FAILS -> run
codex+gemini (scripts/agent_bakeoff.py) + algenta (scripts/bakeoff_algenta_run.py)
-> verify each fix -> collect. Results are written incrementally so one slow/failed
case never loses the rest. Reuses already-validated fixtures + targets.

Prereqs: the Cline sidecar up (ALGENTA_AGENT_CORE_URL) for algenta; node/npm for
JS/TS cases; .env sourced. Run in the background — it is long (codex/gemini explore
the whole repo each run).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYBIN = "/Users/angel/Developer/decision-engine/mojo_env/.pixi/envs/default/bin/python"
OUT = ROOT / "build" / "bakeoff_batch"
SHARED = ROOT / "build" / "bakeoff_batch" / "src"

# Each case: a repo+pin, one planted bug (old->new string in a file), the focused
# oracle, and the triage signal (diag path/line) algenta gets from the failure.
CASES = [
    {
        "name": "click/make_default_short_help",
        "url": "https://github.com/pallets/click.git", "pin": "8.4.1",
        "lang": "python", "focus": "src",
        "bug_file": "src/click/utils.py",
        "old": "        total_length += len(word) + (i > 0)\n",
        "new": "        total_length += len(word)\n",
        "verify": "PYTHONPATH=src {py} -m pytest tests/test_utils.py -k make_default_short_help -p no:randomly -q",
        "diag_path": "src/click/utils.py", "diag_line": 86,
        "issue": "test_make_default_short_help fails: truncation budget is wrong",
    },
    {
        "name": "click/split_arg_string",
        "url": "https://github.com/pallets/click.git", "pin": "8.4.1",
        "lang": "python", "focus": "src",
        "bug_file": "src/click/shell_completion.py",
        "old": "        out.append(lex.token)\n",
        "new": "        pass\n",
        "verify": "PYTHONPATH=src {py} -m pytest tests/test_parser.py -k split_arg_string -p no:randomly -q",
        "diag_path": "src/click/shell_completion.py", "diag_line": 513,
        "issue": "test_split_arg_string fails: incomplete-quote partial token is dropped",
    },
    {
        "name": "click/_expand_args",
        "url": "https://github.com/pallets/click.git", "pin": "8.4.1",
        "lang": "python", "focus": "src",
        "bug_file": "src/click/utils.py",
        "old": "            arg = os.path.expandvars(arg)\n",
        "new": "            pass\n",
        "verify": "PYTHONPATH=src {py} -m pytest tests/test_utils.py -k expand_args -p no:randomly -q",
        "diag_path": "src/click/utils.py", "diag_line": 629,
        "issue": "test_expand_args fails: env-var expansion ($VAR) no longer happens",
    },
    {
        "name": "click/_split_opt",
        "url": "https://github.com/pallets/click.git", "pin": "8.4.1",
        "lang": "python", "focus": "src",
        "bug_file": "src/click/parser.py",
        "old": "        return opt[:2], opt[2:]\n",
        "new": "        return opt[:1], opt[2:]\n",
        "verify": "PYTHONPATH=src {py} -m pytest tests/test_options.py -p no:randomly -q",
        "diag_path": "src/click/parser.py", "diag_line": 116,
        "issue": "long-option parsing broken: '--opt' prefix split is wrong",
    },
    {
        "name": "ky/prefix-baseUrl",
        "url": "https://github.com/sindresorhus/ky.git", "pin": "v2.0.2",
        "lang": "node", "focus": "source",
        "bug_file": "source/core/Ky.ts",
        "old": "\t\t\t\tconst normalizedInput = this.#input.replace(/^\\/+/, '');\n",
        "new": "\t\t\t\tconst normalizedInput = this.#input;\n",
        "verify": "npx ava test/base-url.ts",
        "diag_path": "source/core/Ky.ts", "diag_line": 392,
        "issue": "test/base-url.ts fails: prefix/baseUrl input normalization is wrong",
    },
]


def sh(cmd, cwd=None, timeout=900, env=None):
    return subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True,
                          text=True, timeout=timeout, env=env)


def prep(case) -> Path | None:
    dest = SHARED / case["name"].replace("/", "_")
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = sh(["git", "clone", "--quiet", "--depth", "1", "--branch", case["pin"], case["url"], str(dest)])
    if r.returncode != 0:
        print(f"  [{case['name']}] clone failed: {r.stderr[:200]}", flush=True)
        return None
    target = dest / case["bug_file"]
    text = target.read_text(encoding="utf-8")
    if case["old"] not in text:
        print(f"  [{case['name']}] bug anchor not found — skip", flush=True)
        return None
    target.write_text(text.replace(case["old"], case["new"], 1), encoding="utf-8")
    sh(["git", "-C", str(dest), "-c", "user.email=b@b", "-c", "user.name=b", "commit", "-aqm", "bug"])
    if case["lang"] == "node":
        print(f"  [{case['name']}] npm install…", flush=True)
        if sh(["npm", "install", "--no-audit", "--no-fund", "--silent"], cwd=str(dest), timeout=600).returncode != 0:
            print(f"  [{case['name']}] npm install failed — skip", flush=True)
            return None
    verify = case["verify"].format(py=PYBIN)
    res = sh(verify, cwd=str(dest), timeout=300)
    if res.returncode == 0:
        print(f"  [{case['name']}] planted bug did NOT break the oracle — skip", flush=True)
        return None
    print(f"  [{case['name']}] fixture ready (oracle fails as expected).", flush=True)
    return dest


def verify_patch(case, src: Path, patch: str) -> bool:
    if not patch.strip():
        return False
    co = OUT / (case["name"].replace("/", "_") + "_verify")
    if co.exists():
        shutil.rmtree(co)
    if sh(["git", "clone", "-q", str(src), str(co)]).returncode != 0:
        return False
    nm = src / "node_modules"
    if nm.is_dir():
        try:
            (co / "node_modules").symlink_to(nm, target_is_directory=True)
        except OSError:
            pass
    (OUT / "p.patch").write_text(patch, encoding="utf-8")
    if sh(["git", "apply", str(OUT / "p.patch")], cwd=str(co)).returncode != 0:
        return False
    return sh(case["verify"].format(py=PYBIN), cwd=str(co), timeout=300).returncode == 0


def run_case(case) -> dict | None:
    print(f"\n=== {case['name']} ===", flush=True)
    src = prep(case)
    if src is None:
        return None
    case_out = OUT / case["name"].replace("/", "_")
    case_out.mkdir(parents=True, exist_ok=True)
    prompt = (f"A unit test in this repository is failing. Reproduce it, find the single "
              f"bug in the source that causes it, and fix it. Keep the public API and all "
              f"other behavior unchanged. Do not modify any tests.")
    result = {"case": case["name"], "lang": case["lang"], "agents": {}}

    # codex + gemini
    sh([sys.executable, str(ROOT / "scripts/agent_bakeoff.py"),
        "--repo", str(src), "--prompt", prompt,
        "--verify", case["verify"].format(py=PYBIN),
        "--agents", "codex,gemini", "--timeout", "600", "--verify-timeout", "240",
        "--out", str(case_out)], timeout=2400)
    rep = case_out / "bakeoff_report.json"
    if rep.exists():
        for r in json.loads(rep.read_text()).get("results", []):
            result["agents"][r["agent"]] = {"tokens_in": r.get("tokens_in"),
                "tokens_out": r.get("tokens_out"), "wall": r.get("wall_seconds"),
                "verified": r.get("verified")}

    # algenta
    aout = case_out / "algenta.json"
    sh([str(ROOT / "scripts/run_repo_python.sh"), str(ROOT / "scripts/bakeoff_algenta_run.py"),
        "--repo", str(src), "--focus", case["focus"],
        "--diag-path", case["diag_path"], "--diag-line", str(case["diag_line"]),
        "--issue", case["issue"], "--agent-timeout", "300", "--out", str(aout)], timeout=600)
    if aout.exists():
        a = json.loads(aout.read_text())
        result["agents"]["algenta"] = {"tokens_in": a.get("tokens_in"),
            "tokens_out": a.get("tokens_out"), "wall": a.get("wall_s"),
            "verified": verify_patch(case, src, a.get("patch_diff", "")),
            "error": a.get("error")}

    # incremental write
    (OUT / "batch_results.jsonl").open("a", encoding="utf-8").write(json.dumps(result) + "\n")
    return result


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "batch_results.jsonl").write_text("", encoding="utf-8")
    results = [r for r in (run_case(c) for c in CASES) if r]

    print("\n\n================ BATCH SUMMARY ================")
    wins = 0
    for r in results:
        a = r["agents"].get("algenta", {})
        cands = [r["agents"].get(x, {}).get("tokens_in") for x in ("codex", "gemini")]
        cands = [c for c in cands if c]
        best = min(cands) if cands else None
        algt = a.get("tokens_in")
        win = (algt is not None and best is not None and algt < best)
        wins += 1 if win else 0
        ratio = f"{best/algt:.2f}x" if (algt and best) else "—"
        print(f"{r['case']:32} algenta={algt} (v={a.get('verified')}) "
              f"codex={r['agents'].get('codex',{}).get('tokens_in')} "
              f"gemini={r['agents'].get('gemini',{}).get('tokens_in')}  "
              f"win={win} ({ratio} fewer tokens)")
    print(f"\nalgenta token wins: {wins}/{len(results)}")
    (OUT / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
