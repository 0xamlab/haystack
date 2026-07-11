#!/usr/bin/env python3
"""Decision-evaluation harness for Azure AI Foundry (Workstream K-eval).

Runs Algenta's decision-specific evaluators over a set of decision results and checks each case
against its expected verdict. This is the "top Foundry differentiator": unlike generic
language-quality evals, these check that a *governed decision* is defensible — no hard-constraint
violation, every narrative figure traces to engine output, provenance present, infeasible runs
never fabricate a recommendation, units in range, and free text can't move the numbers.

The evaluators are the SAME ones the engine runs in-process
(`apps.api_server.services.decision_service.evaluators`) — this harness just wraps them so
Foundry (or CI, or an owner) can score decision outputs offline.

Usage:
    python infra/azure/foundry/evaluations/run_evals.py [cases.json]

Exit code 0 iff every case's verdict matches its `expect` ("pass" = no evaluator failed).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make the repo importable when run directly from anywhere.
# infra/azure/foundry/evaluations/run_evals.py -> repo root is 4 parents up.
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from apps.api_server.services.decision_service.evaluators import (  # noqa: E402
    EvalContext,
    evaluate_decision,
)

HERE = Path(__file__).resolve().parent
SAMPLE_DIR = HERE.parent / "sample-data"


def _load(name: str) -> dict:
    return json.loads((SAMPLE_DIR / name).read_text())


def run_case(case: dict) -> dict:
    """Run the evaluator suite for one case and return a structured verdict."""
    result = _load(case["result"])
    recommendation = _load(case["recommendation"]) if case.get("recommendation") else None
    report = evaluate_decision(EvalContext(result=result, recommendation=recommendation))
    verdict = "pass" if report.passed else "fail"
    return {
        "name": case["name"],
        "expect": case.get("expect", "pass"),
        "verdict": verdict,
        "matched": verdict == case.get("expect", "pass"),
        "counts": report.counts(),
        "failed": [{"name": o.name, "severity": o.severity, "detail": o.detail}
                   for o in report.failed],
    }


def main(argv: list[str]) -> int:
    manifest = Path(argv[1]) if len(argv) > 1 else HERE / "cases.json"
    cases = json.loads(manifest.read_text())["cases"]
    all_matched = True
    for case in cases:
        r = run_case(case)
        all_matched &= r["matched"]
        mark = "OK " if r["matched"] else "!! "
        print(f"{mark}{r['name']:28s} verdict={r['verdict']:4s} expect={r['expect']:4s} "
              f"{r['counts']}")
        for f in r["failed"]:
            print(f"     - [{f['severity']}] {f['name']}: {f['detail']}")
    print()
    print("RESULT:", "all cases matched expectations" if all_matched
          else "MISMATCH — an evaluator verdict did not match its expectation")
    return 0 if all_matched else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
