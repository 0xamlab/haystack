from __future__ import annotations

import contextlib
import subprocess
import tempfile
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RepositoryPipelineFixture:
    root_path: Path
    connector_request: dict[str, Any]
    snapshot_request: dict[str, Any]
    signals: dict[str, Any]

    def pipeline_request(self, *, model_id: str) -> dict[str, Any]:
        return {
            "snapshot": self.snapshot_request,
            "signals": self.signals,
            "model": model_id,
            "runs": 1_000,
            "seed": 42,
        }


@dataclass(frozen=True)
class WarmCacheTask:
    name: str
    files: dict[str, str]
    prompt: str
    injected_context: str


WARM_CACHE_TASKS = (
    WarmCacheTask(
        name="greet_literal",
        files={"greet.py": 'def greet():\n    return "bye"\n'},
        prompt=(
            'Fix this issue: greet() returns "bye" but must return "hi". '
            "Make the minimal change with your file tools, then stop."
        ),
        injected_context=(
            'Issue: greet() returns "bye" but must return "hi".\n'
            "Suspect files: greet.py\n\n"
            '=== greet.py ===\n'
            'def greet():\n'
            '    return "bye"\n'
        ),
    ),
    WarmCacheTask(
        name="sum_returns_zero",
        files={"calc.py": "def total(items):\n    return 0  # BUG: should sum items\n"},
        prompt=(
            "Fix this issue: total(items) always returns 0; it must return the sum of items. "
            "Make the minimal change with your file tools, then stop."
        ),
        injected_context=(
            "Issue: total(items) always returns 0; it must return the sum of items.\n"
            "Suspect files: calc.py\n\n"
            "=== calc.py ===\n"
            "def total(items):\n"
            "    return 0  # BUG: should sum items\n"
        ),
    ),
)


def _init_git_repository(root_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root_path)], check=True)
    subprocess.run(
        ["git", "-C", str(root_path), "config", "user.name", "Cline Competitive Fixture"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(root_path),
            "config",
            "user.email",
            "cline-competitive-fixture@example.com",
        ],
        check=True,
    )
    subprocess.run(["git", "-C", str(root_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root_path), "commit", "-m", "Initial commit"], check=True)


@contextlib.contextmanager
def repository_pipeline_fixture(prefix: str) -> Iterator[RepositoryPipelineFixture]:
    with tempfile.TemporaryDirectory(prefix=f"cline-competitive-{prefix}-") as temp_dir:
        root_path = Path(temp_dir) / "customer-repo"
        (root_path / "src").mkdir(parents=True, exist_ok=True)
        (root_path / "tests").mkdir(parents=True, exist_ok=True)
        (root_path / "src" / "service.py").write_text(
            "def normalize_status(status: str) -> str:\n"
            "    lowered = status.strip().lower()\n"
            '    if lowered == "open":\n'
            '        return "closed"\n'
            "    return lowered\n",
            encoding="utf-8",
        )
        (root_path / "tests" / "test_service.py").write_text(
            "from src.service import normalize_status\n\n\n"
            "def test_normalize_status_open() -> None:\n"
            '    assert normalize_status("OPEN") == "open"\n',
            encoding="utf-8",
        )
        (root_path / "README.md").write_text(
            "# Competitive Repository Fixture\n\n"
            "This fixture exercises the verified-agentic repository pipeline.\n",
            encoding="utf-8",
        )
        _init_git_repository(root_path)
        yield RepositoryPipelineFixture(
            root_path=root_path,
            connector_request={
                "name": f"{prefix}-repository-{time.time_ns()}",
                "connector_type": "local_repo",
                "description": "Cline competitive repository pipeline fixture.",
                "config": {"path": str(root_path)},
            },
            snapshot_request={
                "include_patterns": ["src/**", "tests/**", "README.md"],
                "exclude_patterns": ["**/__pycache__/**"],
                "max_files": 128,
                "max_file_size_bytes": 100_000,
            },
            signals={
                "issue_text": (
                    "Production regression: normalize_status returns closed for OPEN "
                    "inputs after the latest deploy."
                ),
                "diagnostics": [
                    {
                        "path": "src/service.py",
                        "line": 4,
                        "severity": "error",
                        "message": (
                            "normalize_status('OPEN') returns 'closed' instead of 'open'."
                        ),
                    }
                ],
                "failing_tests": ["tests/test_service.py::test_normalize_status_open"],
                "changed_files": ["src/service.py"],
                "workspace_context": [
                    "incident/normalize-status-regression",
                    "jira/REPO-1842",
                ],
            },
        )


@contextlib.contextmanager
def warm_cache_fixture(task: WarmCacheTask) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="cline-warm-cache-") as temp_dir:
        repo_dir = Path(temp_dir)
        for relative_path, content in task.files.items():
            file_path = repo_dir / relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
        _init_git_repository(repo_dir)
        yield repo_dir


def reset_warm_cache_fixture(repo_dir: Path, task: WarmCacheTask) -> None:
    for path in sorted(repo_dir.iterdir()):
        if path.name == ".git":
            continue
        if path.is_dir():
            for nested in sorted(path.rglob("*"), reverse=True):
                if nested.is_file() or nested.is_symlink():
                    nested.unlink(missing_ok=True)
            for nested_dir in sorted(path.rglob("*"), reverse=True):
                if nested_dir.is_dir():
                    nested_dir.rmdir()
            path.rmdir()
            continue
        path.unlink(missing_ok=True)
    for relative_path, content in task.files.items():
        file_path = repo_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
