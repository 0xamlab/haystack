"""Tests for repository_intelligence_real_repo_probe: parse_repository.

Extracted from tests/test_repository_intelligence_real_repo_probe.py during modularization.
"""
from __future__ import annotations

from tests._repository_intelligence_real_repo_probe_helpers import *  # noqa: F401,F403


def test_parse_repository_diagnostics_reads_typescript_tsc_output(tmp_path: Path) -> None:
    repo_path = tmp_path / "routing-engine"
    (repo_path / "services" / "execution-service" / "src").mkdir(parents=True)
    target = repo_path / "services" / "execution-service" / "src" / "index.ts"
    target.write_text("export const value = 1;\n", encoding="utf-8")

    output = (
        f"{target}(12,5): error TS6059: File is not under 'rootDir' "
        "'/tmp/service'. 'rootDir' is expected to contain all source files.\n"
    )
    diagnostics = parse_repository_diagnostics(repo_path=repo_path, output=output)

    assert len(diagnostics) == 1
    assert diagnostics[0].path == "services/execution-service/src/index.ts"
    assert diagnostics[0].line == 12
    assert diagnostics[0].code == "TS6059"
    assert "rootDir" in diagnostics[0].message


def test_parse_repository_diagnostics_uses_nested_base_path(tmp_path: Path) -> None:
    repo_path = tmp_path / "routing-engine"
    (repo_path / "services" / "execution-service" / "src").mkdir(parents=True)
    target = repo_path / "services" / "execution-service" / "src" / "index.ts"
    target.write_text("export const value = 1;\n", encoding="utf-8")

    diagnostics = parse_repository_diagnostics(
        repo_path=repo_path,
        output="src/index.ts(12,5): error TS6059: File is not under 'rootDir'.\n",
        base_path=repo_path / "services" / "execution-service",
    )

    assert diagnostics[0].path == "services/execution-service/src/index.ts"


def test_parse_repository_diagnostics_reads_python_traceback_frames(tmp_path: Path) -> None:
    repo_path = tmp_path / "python-repo"
    (repo_path / "app").mkdir(parents=True)
    target = repo_path / "app" / "worker.py"
    target.write_text("def run() -> None:\n    raise RuntimeError('boom')\n", encoding="utf-8")

    diagnostics = parse_repository_diagnostics(
        repo_path=repo_path,
        output=f'  File "{target}", line 2, in run\n',
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].path == "app/worker.py"
    assert diagnostics[0].line == 2
    assert diagnostics[0].message == "Python traceback frame in run"


def test_parse_repository_diagnostics_reads_node_stack_frames(tmp_path: Path) -> None:
    repo_path = tmp_path / "node-repo"
    (repo_path / "src").mkdir(parents=True)
    target = repo_path / "src" / "server.ts"
    target.write_text("throw new Error('boom');\n", encoding="utf-8")

    diagnostics = parse_repository_diagnostics(
        repo_path=repo_path,
        output=f"    at startServer ({target}:17:9)\n",
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].path == "src/server.ts"
    assert diagnostics[0].line == 17
    assert diagnostics[0].message == "JavaScript stack frame in startServer"


def test_parse_repository_diagnostics_reads_rust_spans(tmp_path: Path) -> None:
    repo_path = tmp_path / "rust-repo"
    (repo_path / "src").mkdir(parents=True)
    target = repo_path / "src" / "main.rs"
    target.write_text("fn main() {}\n", encoding="utf-8")

    diagnostics = parse_repository_diagnostics(
        repo_path=repo_path,
        output=" --> src/main.rs:12:5\n",
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].path == "src/main.rs"
    assert diagnostics[0].line == 12
    assert diagnostics[0].message == "Rust compiler span"


