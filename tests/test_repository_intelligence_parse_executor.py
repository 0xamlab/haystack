"""AR-OPT-3: parse-executor parity + helper coverage.

The ProcessPool parser (ALGENTA_REPOSITORY_PARSE_EXECUTOR=process) must produce
byte-identical symbol/dependency output to the default thread path. Parity is
proven end-to-end on a real multi-file snapshot parsed once per executor, using
separate runtime dirs so the process run actually parses instead of hitting the
thread run's file-analysis cache. The default ("thread") reproduces prior behavior.
"""
from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import pyarrow.parquet as pq

from apps.api_server.schemas.repositories import RepositorySnapshotCreateRequest
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import (
    repository_intelligence_analysis_workflow as analysis_workflow,
)
from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime


def _connector_for_repo(repo_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        owner_key_id=None,
        connector_type=SimpleNamespace(value="local_repo"),
        config_json=json.dumps({"path": str(repo_path)}),
    )


def _init_git_repo(repo_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo_path)], check=True)
    subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "Repo Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_path), "config", "user.email", "repo-test@example.com"], check=True
    )
    subprocess.run(["git", "-C", str(repo_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo_path), "commit", "-qm", "init"], check=True)


def _build_repo(root: Path) -> None:
    pkg = root / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "util.py").write_text("def helper(value):\n    return value + 1\n", encoding="utf-8")
    for index in range(4):
        (pkg / f"mod{index}.py").write_text(
            f"from pkg.util import helper\n\n\ndef run{index}(value):\n"
            f"    return helper(value) + {index}\n",
            encoding="utf-8",
        )
    _init_git_repo(root)


def _symbol_and_dependency_rows(snapshot) -> tuple[list, list]:
    initialize_pyarrow_parquet_runtime()
    symbols = pq.read_table(snapshot.symbol_graph_artifact.storage_path).to_pylist()
    dependencies = pq.read_table(snapshot.dependency_graph_artifact.storage_path).to_pylist()
    symbol_rows = sorted(
        (
            str(r["file_path"]),
            str(r["symbol_name"]),
            str(r["symbol_kind"]),
            int(r["start_line"]),
            int(r["end_line"]),
        )
        for r in symbols
    )
    dependency_rows = sorted(
        (
            str(r["source_file"]),
            str(r["target_file"] or ""),
            str(r["target_symbol"] or ""),
            str(r["dependency_type"]),
        )
        for r in dependencies
    )
    return symbol_rows, dependency_rows


def _make_snapshot(repo_root: Path):
    return repository_service.create_repository_snapshot(
        connector=_connector_for_repo(repo_root),
        request=RepositorySnapshotCreateRequest(
            focus_paths=["pkg"], include_patterns=["**/*.py", "*.py"]
        ),
    )


def test_process_executor_matches_thread_output(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    _build_repo(repo)
    # Bound worker fan-out so the test spawns few processes while still distributing
    # multiple batches across workers (exercises batch ordering + flatten).
    monkeypatch.setattr(analysis_workflow, "_PROCESS_WORKER_CAP", 2)

    # Thread path (default) — its own runtime dir / cache.
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "rt_thread"))
    monkeypatch.setenv("ALGENTA_REPOSITORY_PARSE_EXECUTOR", "thread")
    thread_symbols, thread_deps = _symbol_and_dependency_rows(_make_snapshot(repo))

    # Process path — separate runtime dir so it parses fresh (no cache cross-hit).
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "rt_process"))
    monkeypatch.setenv("ALGENTA_REPOSITORY_PARSE_EXECUTOR", "process")
    process_symbols, process_deps = _symbol_and_dependency_rows(_make_snapshot(repo))

    assert thread_symbols, "fixture should produce symbols (sanity: actually parsed)"
    assert process_symbols == thread_symbols
    assert process_deps == thread_deps
    # The cross-file import must survive process-mode parsing.
    assert any(target == "pkg/util.py" for _, target, _, _ in process_deps)


def test_parse_executor_mode_defaults_and_validates(monkeypatch) -> None:
    monkeypatch.delenv("ALGENTA_REPOSITORY_PARSE_EXECUTOR", raising=False)
    assert analysis_workflow._parse_executor_mode() == "thread"
    monkeypatch.setenv("ALGENTA_REPOSITORY_PARSE_EXECUTOR", "process")
    assert analysis_workflow._parse_executor_mode() == "process"
    monkeypatch.setenv("ALGENTA_REPOSITORY_PARSE_EXECUTOR", "SEQUENTIAL")
    assert analysis_workflow._parse_executor_mode() == "sequential"
    monkeypatch.setenv("ALGENTA_REPOSITORY_PARSE_EXECUTOR", "bogus")
    assert analysis_workflow._parse_executor_mode() == "thread"


def test_chunk_paths_preserves_order_and_covers_all() -> None:
    paths = [Path(f"f{index}.py") for index in range(10)]
    chunks = analysis_workflow._chunk_paths(paths, 3)
    assert [p for chunk in chunks for p in chunk] == paths
    assert all(len(chunk) <= 3 for chunk in chunks)


def test_process_batch_size_clamps() -> None:
    assert analysis_workflow._process_batch_size(1) >= 1
    assert analysis_workflow._process_batch_size(10_000_000) <= 256
