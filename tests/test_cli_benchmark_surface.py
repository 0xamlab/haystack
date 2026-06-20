from __future__ import annotations

import json
from pathlib import Path

from apps.cli import main as cli_main


def _summary_payload(*, n_libraries: int, total_functions: int, median_speedup: float, max_speedup: float):
    return {
        "n_libraries": n_libraries,
        "n_iterations": 10_000,
        "total_functions_compared": total_functions,
        "median_speedup_x": median_speedup,
        "max_speedup_x": max_speedup,
        "timestamp": "2026-05-21T00:00:00+00:00",
        "libraries": [
            {"lib": "bpe_tokenizer", "speedup_x": 12.5},
            {"lib": "vector_search", "speedup_x": 87.0},
        ],
    }


def test_load_benchmark_summary_prefers_rollout_artifact(tmp_path: Path) -> None:
    build_dir = tmp_path / "build"
    benchmarks_dir = tmp_path / "benchmarks"
    build_dir.mkdir()
    benchmarks_dir.mkdir()

    (build_dir / "llm_rollout_parity_benchmark.json").write_text(
        '{"n_libraries": 16, "libraries": []}',
        encoding="utf-8",
    )
    (benchmarks_dir / "summary.json").write_text(
        '{"n_libraries": 3, "libraries": []}',
        encoding="utf-8",
    )

    payload, source = cli_main._load_benchmark_summary(tmp_path)

    assert payload is not None
    assert payload["n_libraries"] == 16
    assert source == build_dir / "llm_rollout_parity_benchmark.json"


def test_cmd_benchmark_reports_rollout_artifact_scope(
    monkeypatch,
    capsys,
) -> None:
    rollout_summary = _summary_payload(
        n_libraries=22,
        total_functions=209,
        median_speedup=115.58,
        max_speedup=433.19,
    )

    monkeypatch.setattr(
        cli_main,
        "_load_benchmark_summary",
        lambda root: (rollout_summary, Path("/tmp/build/llm_rollout_parity_benchmark.json")),
    )

    cli_main.cmd_benchmark()
    output = capsys.readouterr().out

    assert "209 public runtime functions" in output
    assert "22-library LLM rollout parity proof." in output
    assert "llm_rollout_parity_benchmark.json" in output
    assert "115.58×" in output
    assert "433.19×" in output


def test_format_speedup_value_trims_trailing_zeroes() -> None:
    assert cli_main._format_speedup_value(63.5) == "63.5"
    assert cli_main._format_speedup_value(130.23) == "130.23"
    assert cli_main._format_speedup_value(64.0) == "64"


def test_cmd_benchmark_matches_current_rollout_artifact(capsys) -> None:
    payload = json.loads(Path("build/llm_rollout_parity_benchmark.json").read_text())

    cli_main.cmd_benchmark()
    output = capsys.readouterr().out

    assert f"{payload['n_libraries']} Mojo libraries vs Python" in output
    assert output.count("public runtime functions") == 1
    assert f"{payload['total_functions_compared']} public runtime functions" in output
    assert f"{cli_main._format_speedup_value(float(payload['median_speedup_x']))}×" in output
    assert f"{cli_main._format_speedup_value(float(payload['max_speedup_x']))}×" in output
    assert f"{str(payload['timestamp'])[:10]}" in output
    assert "Source: build/llm_rollout_parity_benchmark.json" in output
    assert f"Scope: {payload['n_libraries']}-library LLM rollout parity proof." in output


def test_cmd_benchmark_private_profile_uses_self_hosted_guidance(
    monkeypatch,
    capsys,
) -> None:
    rollout_summary = _summary_payload(
        n_libraries=22,
        total_functions=209,
        median_speedup=115.58,
        max_speedup=433.19,
    )
    monkeypatch.setattr(
        cli_main,
        "_load_benchmark_summary",
        lambda root: (rollout_summary, Path("/tmp/build/llm_rollout_parity_benchmark.json")),
    )
    monkeypatch.setattr(cli_main, "_private_profile_enabled", lambda: True)
    monkeypatch.setattr(cli_main, "_get_dashboard_url", lambda: "http://localhost:8000/dashboard")

    cli_main.cmd_benchmark()
    output = capsys.readouterr().out

    assert "Configured deployment:" in output
    assert "http://localhost:8000/dashboard" in output
    assert "Free tier: 500 simulations/month" not in output
    assert "algenta.ai/dashboard" not in output


def test_cmd_benchmark_cloud_managed_mentions_free_tier(
    monkeypatch,
    capsys,
) -> None:
    rollout_summary = _summary_payload(
        n_libraries=22,
        total_functions=209,
        median_speedup=115.58,
        max_speedup=433.19,
    )
    monkeypatch.setattr(
        cli_main,
        "_load_benchmark_summary",
        lambda root: (rollout_summary, Path("/tmp/build/llm_rollout_parity_benchmark.json")),
    )
    monkeypatch.setattr(cli_main, "_private_profile_enabled", lambda: False)
    monkeypatch.setattr(cli_main, "_get_dashboard_url", lambda: "https://app.algenta.ai/dashboard")

    cli_main.cmd_benchmark()
    output = capsys.readouterr().out

    assert "Free tier: 500 simulations/month" in output
    assert "https://app.algenta.ai/dashboard" in output
