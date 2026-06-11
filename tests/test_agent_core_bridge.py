"""Offline-contract bridge test: Python verified_agentic planner <-> stub agent-core.

Boots the quarantined stub sidecar directly, drives it through
``_generate_verified_agentic_repository_patch_plan`` over a fake materialized
checkout, and asserts the Python-authoritative diff reflects the sidecar's edit.

This proves the loopback contract + shared-filesystem mutation + diff capture
without a model. The real runtime boot path is covered separately.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from apps.api_server.services import (
    repository_intelligence_agent_core_client as agent_core_client,
)
from apps.api_server.services import (
    repository_intelligence_planner_generation as planner_generation,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_RUN_SERVER = _REPO_ROOT / "agent-core" / "run-server.stub.mjs"

_SNAPSHOT_MANIFEST = {"snapshot_id": "snap_bridge", "resolved_revision": "cafe", "files": []}
_TRIAGE_MANIFEST = {
    "snapshot_id": "snap_bridge",
    "evidence_items": [],
    "suspect_files": ["foo.py"],
    "suspect_symbols": ["greet"],
    "signals": {"issue_text": "greet is wrong"},
    "raw_repo_token_estimate": 4000,
    "evidence_bundle_token_count": 500,
    "reduction_ratio": 8.0,
}

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or not _RUN_SERVER.exists(),
    reason="node and agent-core/run-server.stub.mjs are required for the bridge test",
)


@contextlib.contextmanager
def _agent_core_sidecar():
    """Start the Node sidecar on an ephemeral port; yield its base_url."""
    node_bin = shutil.which("node")
    assert node_bin is not None
    proc = subprocess.Popen(
        [node_bin, str(_RUN_SERVER)],
        cwd=str(_RUN_SERVER.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "AGENT_CORE_PORT": "0"},
    )
    try:
        port = None
        deadline = time.monotonic() + 15.0
        assert proc.stdout is not None
        while time.monotonic() < deadline:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    raise RuntimeError("agent-core sidecar exited before becoming ready")
                continue
            if line.startswith("AGENT_CORE_LISTENING "):
                port = int(line.strip().split()[1])
                break
        if port is None:
            raise RuntimeError("agent-core sidecar did not report a listening port")
        yield f"http://127.0.0.1:{port}"
    finally:
        proc.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=5)
        if proc.poll() is None:
            proc.kill()


def _patch_materialized(monkeypatch, tmp_path: Path) -> None:
    @contextlib.contextmanager
    def _fake(snapshot_manifest):  # noqa: ARG001
        (tmp_path / "foo.py").write_text('def greet():\n    return "bye"\n', encoding="utf-8")
        yield tmp_path

    monkeypatch.setattr(
        planner_generation.repository_storage, "materialized_snapshot", _fake
    )


def test_python_to_node_sidecar_round_trip(monkeypatch, tmp_path):
    _patch_materialized(monkeypatch, tmp_path)

    with _agent_core_sidecar() as base_url:
        run_agent = agent_core_client.make_sidecar_run_agent(base_url)
        result = asyncio.run(
            planner_generation._generate_verified_agentic_repository_patch_plan(
                model_id="repository.verified_agentic_v1",
                snapshot_manifest=_SNAPSHOT_MANIFEST,
                triage_manifest=_TRIAGE_MANIFEST,
                run_agent=run_agent,
            )
        )

    # The sidecar mutated foo.py over loopback; Python recomputed the authoritative diff.
    assert result["planner_execution_mode"] == "verified_agentic"
    assert result["planner_engine"] == "cline_fork"
    assert str(result["agent_run_id"]).startswith("stub_")
    assert "foo.py" in result["patch_diff"]
    assert "agent-core stub edit" in result["patch_diff"]


def test_sidecar_health_returns_no_change_without_suspects(monkeypatch, tmp_path):
    """No suspect files => stub makes no edit => planner raises no_change (422)."""
    from apps.api_server.services.repository_intelligence_contracts import (
        RepositoryIntelligenceError,
    )

    _patch_materialized(monkeypatch, tmp_path)
    triage_no_suspects = {**_TRIAGE_MANIFEST, "suspect_files": []}

    with _agent_core_sidecar() as base_url:
        run_agent = agent_core_client.make_sidecar_run_agent(base_url)
        with pytest.raises(RepositoryIntelligenceError) as exc:
            asyncio.run(
                planner_generation._generate_verified_agentic_repository_patch_plan(
                    model_id="repository.verified_agentic_v1",
                    snapshot_manifest=_SNAPSHOT_MANIFEST,
                    triage_manifest=triage_no_suspects,
                    run_agent=run_agent,
                )
            )
    assert exc.value.code == "repository_agent_no_change"
