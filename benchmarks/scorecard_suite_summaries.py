from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_vector_resolver_hospitality import (  # noqa: E402
    _HOSP_SCHEMA,
    TestHospitalityBatch,
)

OUTPUT_PATH = PROJECT_ROOT / "build" / "scorecard_suite_summaries.json"
HOSPITALITY_SUITE = ("tests/test_vector_resolver_hospitality.py",)
JOIN_PATH_SUITE = ("tests/test_query_join_path.py",)
IMPORT_PLANNER_SUITE = (
    "tests/unit/test_connectors.py",
    "tests/test_auto_planner.py",
    "tests/test_vector_resolver.py",
    "tests/test_query_join_path.py",
)


@dataclass(frozen=True)
class PytestSummary:
    passed: int
    failed: int
    skipped: int
    total: int

    def to_dict(self) -> dict[str, int]:
        return {
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "total": self.total,
        }


def _parse_pytest_summary(output: str) -> PytestSummary:
    summary_line = next(
        (
            line.strip()
            for line in reversed(output.splitlines())
            if " in " in line and re.search(r"\b(passed|failed|skipped|error|errors)\b", line)
        ),
        "",
    )
    if not summary_line:
        raise ValueError("pytest output did not contain a terminal summary line")

    counts = {"passed": 0, "failed": 0, "skipped": 0}
    for value, label in re.findall(r"(\d+)\s+(passed|failed|skipped|error|errors)", summary_line):
        normalized = "failed" if label in {"error", "errors"} else label
        counts[normalized] += int(value)

    total = counts["passed"] + counts["failed"] + counts["skipped"]
    return PytestSummary(
        passed=counts["passed"],
        failed=counts["failed"],
        skipped=counts["skipped"],
        total=total,
    )


def _run_pytest_suite(paths: tuple[str, ...]) -> PytestSummary:
    command = [sys.executable, "-m", "pytest", "-q", *paths]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part.strip())
    summary = _parse_pytest_summary(output)
    if completed.returncode not in {0, 1}:
        raise RuntimeError(f"pytest exited with unexpected code {completed.returncode}\n{output}")
    return summary


def _compute_hospitality_accuracy() -> dict[str, float | int]:
    from mojo.engine.vector_kernels.resolver import ColumnVectorResolver

    resolver = ColumnVectorResolver(_HOSP_SCHEMA)
    correct = 0
    total = len(TestHospitalityBatch._QUERIES)
    for hint, src, role, expected_column, expected_source in TestHospitalityBatch._QUERIES:
        result = resolver.resolve(hint, preferred_source=src, role_hint=role)
        if result is None:
            continue
        if result.column == expected_column and (src is None or result.source == expected_source):
            correct += 1

    percentage = round((correct / total) * 100, 1) if total > 0 else 0.0
    return {"correct": correct, "total": total, "percentage": percentage}


def build_suite_summaries() -> dict[str, object]:
    hospitality_suite = _run_pytest_suite(HOSPITALITY_SUITE)
    join_path_suite = _run_pytest_suite(JOIN_PATH_SUITE)
    import_planner_suite = _run_pytest_suite(IMPORT_PLANNER_SUITE)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "narrow_resolver_regression": {
            "accuracy": _compute_hospitality_accuracy(),
            "regression_suite": hospitality_suite.to_dict(),
        },
        "join_path_correctness": join_path_suite.to_dict(),
        "import_planner_regression_suite": import_planner_suite.to_dict(),
    }


def main() -> int:
    payload = build_suite_summaries()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote scorecard suite summaries to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
