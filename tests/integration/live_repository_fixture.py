from __future__ import annotations

import contextlib
import subprocess
import tempfile
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_LOCAL_REPOSITORY_HOSTS = {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True)
class LiveRepositoryFixture:
    root_path: Path
    connector_request: dict[str, Any]
    snapshot_request: dict[str, Any]
    primary_file: str = "src/service.py"
    failing_test: str = "tests/test_service.py::test_normalize_status_open"
    suspected_symbol: str = "normalize_status"

    def triage_request(self, snapshot_id: str) -> dict[str, Any]:
        return {
            "snapshot_id": snapshot_id,
            "signals": {
                "issue_text": (
                    "Production regression: normalize_status returns closed for OPEN "
                    "inputs after the latest deploy."
                ),
                "diagnostics": [
                    {
                        "path": self.primary_file,
                        "line": 4,
                        "severity": "error",
                        "message": (
                            "normalize_status('OPEN') returns 'closed' instead of 'open'."
                        ),
                    }
                ],
                "failing_tests": [self.failing_test],
                "changed_files": [self.primary_file],
                "workspace_context": [
                    "incident/normalize-status-regression",
                    "jira/REPO-1842",
                ],
            },
        }

    @staticmethod
    def decision_plan_request(
        snapshot_id: str | None, workspace_evidence_bundle_ref: str
    ) -> dict[str, Any]:
        payload = {"workspace_evidence_bundle_ref": workspace_evidence_bundle_ref}
        if snapshot_id is not None:
            payload["snapshot_id"] = snapshot_id
        return payload

    @staticmethod
    def simulation_request(snapshot_id: str | None, decision_plan_id: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "decision_plan_id": decision_plan_id,
            "runs": 1_000,
            "seed": 42,
        }
        if snapshot_id is not None:
            payload["snapshot_id"] = snapshot_id
        return payload

    @staticmethod
    def apply_request(
        snapshot_id: str | None,
        decision_plan_id: str,
        simulation_id: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "snapshot_id": snapshot_id,
            "decision_plan_id": decision_plan_id,
            "simulation_id": simulation_id,
            "mode": "patch_only",
        }
        if snapshot_id is None:
            payload.pop("snapshot_id")
        return payload

    @staticmethod
    def apply_local_branch_request(
        snapshot_id: str | None,
        decision_plan_id: str,
        simulation_id: str,
        *,
        branch_name: str = "algenta/live-repository-fix",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "decision_plan_id": decision_plan_id,
            "simulation_id": simulation_id,
            "mode": "local_branch",
            "write_permission": True,
            "branch_name": branch_name,
        }
        if snapshot_id is not None:
            payload["snapshot_id"] = snapshot_id
        return payload

    def graph_query_request(
        self,
        snapshot_id: str | None,
        workspace_evidence_bundle_ref: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "file_path": self.primary_file,
            "symbol_name": self.suspected_symbol,
            "direction": "both",
            "max_depth": 2,
            "max_nodes": 64,
        }
        if snapshot_id is not None:
            payload["snapshot_id"] = snapshot_id
        if workspace_evidence_bundle_ref:
            payload["workspace_evidence_bundle_ref"] = workspace_evidence_bundle_ref
        return payload

    def assert_local_branch_applied(
        self,
        *,
        branch_name: str,
        checkout_path: str | None,
    ) -> None:
        if checkout_path is not None:
            assert Path(checkout_path).resolve() == self.root_path.resolve()
        current_branch = subprocess.check_output(
            ["git", "-C", str(self.root_path), "rev-parse", "--abbrev-ref", "HEAD"],
            text=True,
        ).strip()
        assert current_branch == branch_name
        assert (self.root_path / ".git").exists()


def assert_repository_intelligence_capabilities_payload(
    payload: Any,
    *,
    required_language: str = "python",
) -> None:
    if isinstance(payload, dict):
        supported_languages = payload.get("supported_languages")
        support_progress = payload.get("support_progress")
    else:
        supported_languages = getattr(payload, "supported_languages", None)
        support_progress = getattr(payload, "support_progress", None)

    assert isinstance(supported_languages, list), payload
    assert supported_languages, payload
    assert all(isinstance(language, str) and language for language in supported_languages), payload
    assert len(set(supported_languages)) == len(supported_languages), payload
    assert required_language in supported_languages, payload

    if isinstance(support_progress, dict):
        supported_real_language_count = support_progress.get("supported_real_language_count")
        ranked_target_language_count = support_progress.get("ranked_target_language_count")
        progress_fraction = support_progress.get("progress_fraction")
        progress_label = support_progress.get("progress_label")
    else:
        supported_real_language_count = getattr(
            support_progress, "supported_real_language_count", None
        )
        ranked_target_language_count = getattr(
            support_progress, "ranked_target_language_count", None
        )
        progress_fraction = getattr(support_progress, "progress_fraction", None)
        progress_label = getattr(support_progress, "progress_label", None)

    assert isinstance(supported_real_language_count, int), payload
    assert isinstance(ranked_target_language_count, int), payload
    assert isinstance(progress_fraction, int | float), payload
    assert isinstance(progress_label, str) and progress_label, payload
    assert supported_real_language_count == len(supported_languages), payload
    assert ranked_target_language_count >= supported_real_language_count >= 1, payload
    assert progress_label == (
        f"{supported_real_language_count} / {ranked_target_language_count}"
    ), payload
    assert abs(
        float(progress_fraction)
        - (supported_real_language_count / ranked_target_language_count)
    ) < 1e-9, payload


def _init_git_repo(root_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root_path)], check=True)
    subprocess.run(
        ["git", "-C", str(root_path), "config", "user.name", "Repository Fixture"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(root_path), "config", "user.email", "repository-fixture@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(root_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root_path), "commit", "-m", "Initial commit"], check=True)


def local_repository_live_support_reason(base_url: str) -> str | None:
    hostname = (urlparse(base_url).hostname or "").strip().lower()
    if hostname in _LOCAL_REPOSITORY_HOSTS:
        return None
    return (
        "repository live checks require a local API base URL because local_repo "
        "connectors resolve server-side filesystem paths."
    )


@contextlib.contextmanager
def live_repository_fixture(prefix: str) -> Iterator[LiveRepositoryFixture]:
    with tempfile.TemporaryDirectory(prefix=f"{prefix}-repo-") as temp_dir:
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
            "# Customer Repository\n\n"
            "This fixture exercises Algenta Repository Intelligence against a "
            "deterministic local repository source.\n",
            encoding="utf-8",
        )
        _init_git_repo(root_path)
        connector_request = {
            "name": f"{prefix}-repository-{time.time_ns()}",
            "connector_type": "local_repo",
            "description": "Live Repository Intelligence local repository check.",
            "config": {
                "path": str(root_path),
            },
        }
        snapshot_request = {
            "include_patterns": ["src/**", "tests/**", "README.md"],
            "exclude_patterns": ["**/__pycache__/**"],
            "max_files": 128,
            "max_file_size_bytes": 100_000,
        }
        yield LiveRepositoryFixture(
            root_path=root_path,
            connector_request=connector_request,
            snapshot_request=snapshot_request,
        )
