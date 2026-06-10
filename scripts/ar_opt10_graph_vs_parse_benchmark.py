"""AR-OPT-10 ROI probe: measure graph_build_ms vs snapshot_parse_ms at scale.

AR-OPT-10 (true incremental dependency graph) only pays off if rebuilding the
graph is an expensive fraction of a snapshot. The graph stage is in-memory record
assembly over already-parsed symbols/references, so the hypothesis is that it is
small next to parsing. This script generates synthetic repos at several scales,
runs a real cold snapshot inside an AR-OPT-0 telemetry scope, and prints each
span plus graph_build as a share of total measured work.

Usage:
    .venv/bin/python scripts/ar_opt10_graph_vs_parse_benchmark.py [n1 n2 ...]
Defaults to 200 800 2000 files. Not a pytest module (it shells out to git and
writes large temp trees); it is a manual ROI probe.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace

from apps.api_server.schemas.repositories import RepositorySnapshotCreateRequest
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services import repository_intelligence_telemetry as telemetry

_FUNCS_PER_FILE = 8


def _connector_for_repo(repo_path: Path) -> SimpleNamespace:
    import json

    return SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        owner_key_id=None,
        connector_type=SimpleNamespace(value="local_repo"),
        config_json=json.dumps({"path": str(repo_path)}),
    )


def _generate_repo(root: Path, n_files: int) -> None:
    """Write n_files Python modules with intra- and cross-file symbol references."""
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)
    for i in range(n_files):
        lines: list[str] = []
        if i > 0:
            # Cross-file dependency + reference (drives dependency/reference edges).
            lines.append(f"from src.mod_{i - 1} import f_{i - 1}_0")
        lines.append(f"def f_{i}_0(x):")
        lines.append(f"    return ({f'f_{i - 1}_0(x) + ' if i > 0 else ''}1)")
        for j in range(1, _FUNCS_PER_FILE):
            lines.append(f"def f_{i}_{j}(x):")
            # Intra-file reference to the previous function in this module.
            lines.append(f"    return f_{i}_{j - 1}(x) * {j + 1}")
        (src / f"mod_{i}.py").write_text("\n".join(lines) + "\n")


def _init_git(repo_path: Path) -> None:
    run = lambda *a: subprocess.run(a, check=True, capture_output=True)
    run("git", "init", "-q", str(repo_path))
    run("git", "-C", str(repo_path), "config", "user.name", "Bench")
    run("git", "-C", str(repo_path), "config", "user.email", "bench@example.com")
    run("git", "-C", str(repo_path), "add", "-A")
    run("git", "-C", str(repo_path), "commit", "-q", "-m", "init")


_SPAN_ORDER = (
    "snapshot_file_discovery_ms",
    "snapshot_parse_ms",
    "graph_build_ms",
    "parquet_write_ms",
    "tar_write_ms",
    "manifest_write_ms",
)


def _bench_one(n_files: int) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        runtime_dir = tmp / "runtime"
        runtime_dir.mkdir()
        import os

        os.environ["ALGENTA_RUNTIME_DIR"] = str(runtime_dir)
        repo = tmp / "repo"
        _generate_repo(repo, n_files)
        _init_git(repo)
        connector = _connector_for_repo(repo)

        with telemetry.collect() as data:
            snapshot = repository_service.create_repository_snapshot(
                connector=connector, request=RepositorySnapshotCreateRequest()
            )
        spans = data["spans_ms"]
        total = sum(spans.values())
        graph = spans.get("graph_build_ms", 0.0)
        parse = spans.get("snapshot_parse_ms", 0.0)

        print(f"\n=== {n_files} files | {snapshot.file_count} parsed | total spans {total:8.1f} ms ===")
        for name in _SPAN_ORDER:
            if name in spans:
                pct = 100.0 * spans[name] / total if total else 0.0
                print(f"  {name:28s} {spans[name]:9.1f} ms  ({pct:4.1f}%)")
        for name, value in spans.items():
            if name not in _SPAN_ORDER:
                print(f"  {name:28s} {value:9.1f} ms  (other)")
        ratio = (parse / graph) if graph else float("inf")
        print(f"  -> graph_build is {100.0 * graph / total if total else 0:.1f}% of total; "
              f"parse is {ratio:.0f}x graph_build")


def main() -> None:
    scales = [int(a) for a in sys.argv[1:]] or [200, 800, 2000]
    print("AR-OPT-10 ROI probe: graph_build_ms vs snapshot_parse_ms (cold snapshots)")
    for n in scales:
        _bench_one(n)


if __name__ == "__main__":
    main()
