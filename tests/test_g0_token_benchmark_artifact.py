from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "g0_token_benchmark.py"


def test_g0_token_benchmark_writes_json_artifact_without_sidecar(tmp_path: Path) -> None:
    output_path = tmp_path / "g0.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--arms",
            "A",
            "--reps",
            "1",
            "--json-output",
            str(output_path),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )

    assert "[A] greet_literal" in completed.stdout
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "cline-g0-benchmark-results/v1"
    assert payload["benchmark_suite"] == "g0_token_benchmark"
    assert payload["benchmark_fixture_hash"]
    assert payload["provider_model_class"].startswith("anthropic:")
    assert payload["task_count"] == 2
    assert payload["usage_source"] == "runtime_accumulated_usage"
    assert payload["resolution_threshold_absolute_pp"] == 5.0
    assert payload["resolution_threshold_mode"] == "absolute_percentage_points"
    assert payload["eligibility_rules"]["benchmark_fixture_hash"] == payload["benchmark_fixture_hash"]
    assert payload["arms"] == ["A"]
