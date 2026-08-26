"""Tests for infra/ci/az_orchestrator.py's org-wide multi-repo scoping.

Verifies the conversion from a single hardcoded REPO to an org-level runner pool that
serves every repo in SERVED_REPOS: queued_jobs() must aggregate across all served repos
(not just the first), runner_names()/the warm-pool busy check must query the org-level
runners endpoint (not a repo-scoped one), and the cloud-init templates must embed the org
URL + runner group rather than a single repo URL.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "infra" / "ci" / "az_orchestrator.py"


def _load_orchestrator(monkeypatch, **env):
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("AZURE_TENANT_ID", "00000000-0000-0000-0000-000000000000")
    monkeypatch.setenv("GITHUB_CI_TOKEN", "test-token")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    spec = importlib.util.spec_from_file_location("az_orchestrator_org_wide_under_test", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    with patch("os.makedirs"):
        spec.loader.exec_module(mod)
    return mod


def test_served_repos_honors_an_explicit_pin_without_calling_the_api(monkeypatch):
    mod = _load_orchestrator(monkeypatch, GITHUB_REPOS="thyn-ai/algenta, thyn-ai/codna")
    monkeypatch.setattr(mod, "gh", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should not call gh()")))
    assert mod.served_repos() == ["thyn-ai/algenta", "thyn-ai/codna"]


def test_served_repos_auto_discovers_every_org_repo_when_unpinned(monkeypatch):
    # No GITHUB_REPOS pin -- the default is "every repo in the org", matching how
    # GitHub-hosted/Blacksmith runners need no per-repo registration step.
    mod = _load_orchestrator(monkeypatch)
    monkeypatch.setattr(mod, "log", lambda *a, **kw: None)  # writes to a VM-only real path
    calls = []

    def fake_gh(path, method="GET", body=None):
        calls.append(path)
        if "page=1" in path:
            return [
                {"full_name": "thyn-ai/algenta", "archived": False},
                {"full_name": "thyn-ai/codna", "archived": False},
                {"full_name": "thyn-ai/old-retired-thing", "archived": True},
            ]
        return []

    monkeypatch.setattr(mod, "gh", fake_gh)
    repos = mod.served_repos()

    assert repos == ["thyn-ai/algenta", "thyn-ai/codna"]  # archived repos excluded
    assert any("orgs/thyn-ai/repos" in c for c in calls)


def test_served_repos_caches_between_calls_within_the_ttl(monkeypatch):
    mod = _load_orchestrator(monkeypatch)
    monkeypatch.setattr(mod, "log", lambda *a, **kw: None)  # writes to a VM-only real path
    calls = []

    def fake_gh(path, method="GET", body=None):
        calls.append(path)
        return [{"full_name": "thyn-ai/algenta", "archived": False}] if "page=1" in path else []

    monkeypatch.setattr(mod, "gh", fake_gh)
    monkeypatch.setattr(mod.time, "time", lambda: 1000.0)

    first = mod.served_repos()
    second = mod.served_repos()  # same fake "now" -- must hit the cache, not gh() again

    assert first == second == ["thyn-ai/algenta"]
    assert len(calls) == 1


def test_served_repos_falls_back_to_stale_cache_on_a_transient_api_error(monkeypatch):
    mod = _load_orchestrator(monkeypatch)
    monkeypatch.setattr(mod, "log", lambda *a, **kw: None)
    mod._repo_cache["value"] = ["thyn-ai/algenta"]
    mod._repo_cache["exp"] = 0  # force a refresh attempt

    def failing_gh(path, method="GET", body=None):
        raise RuntimeError("network blip")

    monkeypatch.setattr(mod, "gh", failing_gh)

    # A transient scan failure must keep serving the last-known repo list, not go dark.
    assert mod.served_repos() == ["thyn-ai/algenta"]


def test_queued_jobs_aggregates_across_every_served_repo(monkeypatch):
    mod = _load_orchestrator(monkeypatch, GITHUB_REPOS="thyn-ai/algenta,thyn-ai/codna")
    calls = []

    def fake_gh(path, method="GET", body=None):
        calls.append(path)
        if path.endswith("actions/runs?status=queued&per_page=30"):
            repo = path[len("repos/") : path.index("/actions/runs")]
            return {"workflow_runs": [{"id": f"{repo.replace('/', '_')}-run"}]}
        if "jobs?per_page=50" in path:
            run_id = path.split("/")[-2]
            return {
                "jobs": [
                    {"id": f"{run_id}-job", "status": "queued", "labels": ["self-hosted", "az-ephemeral"]}
                ]
            }
        return {}

    monkeypatch.setattr(mod, "gh", fake_gh)
    jobs = mod.queued_jobs()

    # Both repos' queued-runs endpoints were hit, not just the first in the list.
    assert any(c.startswith("repos/thyn-ai/algenta/actions/runs?") for c in calls)
    assert any(c.startswith("repos/thyn-ai/codna/actions/runs?") for c in calls)
    assert {j["id"] for j in jobs} == {"thyn-ai_algenta-run-job", "thyn-ai_codna-run-job"}


def test_runner_names_queries_the_org_endpoint_not_a_repo_endpoint(monkeypatch):
    mod = _load_orchestrator(monkeypatch, GITHUB_REPOS="thyn-ai/algenta,thyn-ai/codna")
    seen = {}

    def fake_gh(path, method="GET", body=None):
        seen["path"] = path
        return {"runners": [{"name": "ci-az-1"}]}

    monkeypatch.setattr(mod, "gh", fake_gh)
    names = mod.runner_names()

    # This test's subject is WHICH endpoint is queried -- org-level, never per-repo. The query
    # string is deliberately matched by prefix rather than exact equality: the listing is
    # paginated (`&page=N`, see all_runners()), and pinning the full string would fail on a
    # pagination change that is entirely orthogonal to what this test is about. The negative
    # assertion below is the one carrying the actual guarantee.
    assert seen["path"].startswith("orgs/thyn-ai/actions/runners?per_page=100")
    assert not seen["path"].startswith("repos/"), (
        f"runner discovery must not be per-repo: {seen['path']}")
    assert names == {"ci-az-1"}


def test_cloud_init_registers_at_org_level_with_runner_group_not_a_single_repo(monkeypatch, tmp_path):
    mod = _load_orchestrator(
        monkeypatch, GITHUB_REPOS="thyn-ai/algenta,thyn-ai/codna", AZ_ORCH_RUNNER_GROUP="az-ephemeral-pool"
    )
    mod.SSH_PUB = "ssh-ed25519 AAAAfake"
    mod.STATE = str(tmp_path)  # STATE defaults to a root-only real path; redirect to a writable tmp dir
    mod.write_ci_file("ci-az-test-1")
    with open(tmp_path / "ci-az-test-1.yml") as f:
        content = f.read()

    assert "https://api.github.com/orgs/thyn-ai/actions/runners/registration-token" in content
    assert "--url https://github.com/thyn-ai " in content
    assert "--runnergroup 'az-ephemeral-pool'" in content
    # No leftover single-repo target anywhere in the rendered file.
    assert "thyn-ai/algenta" not in content
    assert "thyn-ai/codna" not in content
