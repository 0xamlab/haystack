"""Real public-repo validation for the security-analyses reachability engine.

Clones a real public GitHub library, builds a REAL snapshot manifest with the engine's actual
indexing pipeline (real files/symbols/dependencies/symbol_references), and runs the four-outcome
reachability classifier on findings selected FROM THE REAL GRAPH:

  * a non-entrypoint file reachable from a production entrypoint -> production-reachable
  * a file with no path from any entrypoint                      -> unreachable / unknown

This proves the engine discriminates honestly on real code, not just hand-built fixtures. It is a
benchmark (network + minutes), not a unit test — run it directly:

    python3 benchmarks/repository_intelligence_security_analysis_real_repo.py
    REAL_REPO_URL=https://github.com/pallets/click python3 benchmarks/...real_repo.py

Validated against pallets/flask: 84 files / 1554 symbols / 601 deps / 2467 symbol-refs ->
src/flask/logging.py = production-reachable, src/flask/__init__.py = unreachable.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import benchmarks.repository_intelligence_real_repo_probe as probe_module
from apps.api_server.schemas.repositories import (
    RepositorySnapshotCreateRequest,
    SecurityFinding,
    SecurityFindingLocation,
)
from apps.api_server.services import repository_intelligence as repository_service
from apps.api_server.services.repository_intelligence_graph import (
    _snapshot_file_graph_neighbors,
)
from apps.api_server.services.repository_intelligence_security_analysis_workflow import (
    analyze_findings,
    discover_entrypoints,
)


def _backward_reaches_entrypoint(
    start: str, inbound: dict[str, set[str]], entry_files: set[str]
) -> bool:
    if start in entry_files:
        return True
    seen, stack = {start}, [start]
    while stack:
        node = stack.pop()
        for caller in inbound.get(node, ()):
            if caller in entry_files:
                return True
            if caller not in seen:
                seen.add(caller)
                stack.append(caller)
    return False


def run_real_repo_security_analysis(repo_url: str, *, max_files: int = 150) -> dict:
    runtime = tempfile.mkdtemp(prefix="secanalysis-runtime-")
    os.environ["ALGENTA_RUNTIME_DIR"] = runtime
    clone_dir = Path(tempfile.mkdtemp(prefix="secanalysis-repo-")) / "repo"
    subprocess.run(  # noqa: S603 — benchmark clones a caller-provided public repo URL
        ["git", "clone", "--depth", "1", "-q", repo_url, str(clone_dir)],  # noqa: S607
        check=True,
    )

    connector = probe_module._repository_connector(clone_dir)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector,
        request=RepositorySnapshotCreateRequest(
            include_patterns=["src/**", "tests/**", "**/*.py"],
            exclude_patterns=["**/__pycache__/**"],
            max_files=max_files,
            max_file_size_bytes=200_000,
        ),
    )
    manifest = repository_service._load_snapshot_manifest(
        org_id=str(connector.org_id),
        repository_id=str(connector.id),
        snapshot_id=snapshot.snapshot_id,
    )
    files = [
        str(f["file_path"])
        for f in manifest.get("files", [])
        if str(f["file_path"]).endswith(".py")
    ]
    inbound, _ = _snapshot_file_graph_neighbors(manifest)
    entrypoints = discover_entrypoints(manifest)
    entry_files = set(entrypoints)

    reachable = next(
        (
            p
            for p in files
            if p not in entry_files and _backward_reaches_entrypoint(p, inbound, entry_files)
        ),
        None,
    )
    unreachable = next(
        (
            p
            for p in files
            if p not in entry_files and not _backward_reaches_entrypoint(p, inbound, entry_files)
        ),
        None,
    )

    def _f(uri: str) -> SecurityFinding:
        return SecurityFinding(
            canonical_id="sha256:" + uri,
            rule_id="py/sqli",
            finding_kind="taint",
            severity="critical",
            primary_location=SecurityFindingLocation(uri=uri, start_line=1),
        )

    targets = [p for p in (reachable, unreachable) if p]
    proofs = {
        f.primary_location.uri: p
        for f, p in zip(
            map(_f, targets), analyze_findings([_f(t) for t in targets], manifest), strict=False
        )
    }
    return {
        "repo_url": repo_url,
        "file_count": len(manifest.get("files", [])),
        "entrypoints": len(entry_files),
        "reachable_file": reachable,
        "unreachable_file": unreachable,
        "verdicts": {uri: p.classification for uri, p in proofs.items()},
    }


def main() -> None:
    result = run_real_repo_security_analysis(
        os.environ.get("REAL_REPO_URL", "https://github.com/pallets/flask")
    )
    print(result)
    valid = {"exploitable", "production-reachable", "unreachable", "unknown"}
    assert all(v in valid for v in result["verdicts"].values())
    if result["reachable_file"]:
        assert result["verdicts"][result["reachable_file"]] == "production-reachable"
    if result["unreachable_file"]:
        assert result["verdicts"][result["unreachable_file"]] in {"unreachable", "unknown"}
    print("REAL-REPO VALIDATION PASSED")


if __name__ == "__main__":
    main()
