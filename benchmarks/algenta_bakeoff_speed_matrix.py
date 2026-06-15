"""Tier-1 algenta repo-intelligence speed/accuracy benchmark.

Drives the deterministic Mojo repo-intelligence pipeline (snapshot -> triage ->
graph/seed-plan) over real public GitHub repos across many languages, recording
per-repo wall time and ecosystem-detection correctness. This path uses ZERO LLM
tokens (it is deterministic), which is the headline contrast against codex/gemini
agent loops that must read files (huge token spend) just to understand a repo.

Usage:
    PYTHONPATH=. python3 -m benchmarks.algenta_bakeoff_speed_matrix \
        --target 120 --out build/algenta_benchmark/tier1_results.jsonl
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import benchmarks.repository_intelligence_public_repo_matrix as m

# Top mainstream languages to prioritise (catalog language slugs).
TOP30 = [
    "python", "javascript", "typescript", "java", "c", "cpp", "cs", "go",
    "rust", "ruby", "php", "swift", "kotlin", "scala", "dart", "r",
    "objective-c", "perl", "lua", "haskell", "elixir", "clojure", "julia",
    "shell", "bash", "sql", "groovy", "powershell", "matlab", "html", "css",
]


def select_cases(target: int) -> list:
    cases = list(m.DEFAULT_PUBLIC_REPOSITORY_CASES)
    by_lang: dict[str, list] = {}
    for c in cases:
        by_lang.setdefault(c.language, []).append(c)
    ordered: list = []
    # 1) one per top-30 language first
    for lang in TOP30:
        if lang in by_lang:
            ordered.append(by_lang[lang].pop(0))
    # 2) breadth: round-robin the rest until we hit target
    remaining = [c for lst in by_lang.values() for c in lst]
    remaining.sort(key=lambda c: c.language)
    for c in remaining:
        if len(ordered) >= target:
            break
        ordered.append(c)
    return ordered[:target]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=120)
    ap.add_argument("--out", type=Path, default=Path("build/algenta_benchmark/tier1_results.jsonl"))
    ap.add_argument("--checkout-root", type=Path, default=m.DEFAULT_CHECKOUT_ROOT)
    ap.add_argument("--runtime-root", type=Path,
                    default=Path("build/algenta_benchmark/tier1_runtime"))
    ap.add_argument("--case-timeout-seconds", type=int, default=180)
    args = ap.parse_args()

    cases = select_cases(args.target)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.runtime_root.mkdir(parents=True, exist_ok=True)
    print(f"selected {len(cases)} cases across {len({c.language for c in cases})} languages")

    results = []
    with args.out.open("w", encoding="utf-8") as fh:
        for i, case in enumerate(cases, 1):
            rec: dict = {
                "i": i, "language": case.language,
                "repo": case.repository_url,
                "expected_ecosystem": case.expected_primary_ecosystem,
            }
            t_clone0 = time.perf_counter()
            try:
                # checkout (clone or cached) then probe; time engine work separately
                with m._public_repository_checkout_context(  # noqa: SLF001
                    case, checkout_root=args.checkout_root, refresh=False
                ) as repo_path:
                    rec["clone_or_cache_s"] = round(time.perf_counter() - t_clone0, 3)
                    m.prime_public_repository_probe_runtime()
                    t0 = time.perf_counter()
                    res = m._run_public_repository_probe_for_checkout(  # noqa: SLF001
                        case, repo_path=repo_path, runtime_root=args.runtime_root,
                    )
                    rec["engine_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                    rec["llm_tokens"] = 0  # deterministic path
                    rec["snapshot_files"] = res.get("snapshot_file_count")
                    rec["connected_files"] = res.get("connected_file_count")
                    rec["detected_ecosystem"] = res.get("primary_ecosystem")
                    rec["ecosystem_correct"] = bool(res.get("primary_match"))
                    rec["status"] = "ok"
            except Exception as exc:  # noqa: BLE001
                rec["status"] = "error"
                rec["error"] = f"{exc.__class__.__name__}: {exc}"[:200]
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            results.append(rec)
            ms = rec.get("engine_ms")
            print(f"[{i:3d}/{len(cases)}] {case.language:14s} "
                  f"{(case.repository_url or '').split('/')[-1][:30]:30s} "
                  f"{rec['status']:5s} engine={ms}ms files={rec.get('snapshot_files')} "
                  f"eco_ok={rec.get('ecosystem_correct')}")

    ok = [r for r in results if r["status"] == "ok"]
    times = sorted(r["engine_ms"] for r in ok)
    def pct(p):
        return times[min(len(times) - 1, int(len(times) * p))] if times else None
    summary = {
        "cases": len(results), "ok": len(ok),
        "languages": len({r["language"] for r in results}),
        "ecosystem_accuracy": round(sum(r.get("ecosystem_correct", False) for r in ok) / max(1, len(ok)), 3),
        "engine_ms_p50": pct(0.5), "engine_ms_p90": pct(0.9), "engine_ms_max": (times[-1] if times else None),
        "total_llm_tokens": 0,
    }
    (args.out.parent / "tier1_summary.json").write_text(json.dumps(summary, indent=2))
    print("\nSUMMARY:", json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
