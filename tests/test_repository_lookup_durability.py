"""Wave-C durability guard (s3 mode): a shared lookup is PUBLISHED only when the artifact it points
to is durably mirrored to the object store in the same call, so a cold sibling never serves a
snapshot/triage/simulation it cannot recover. Deterministic-but-non-durable states (a manifest that
exists locally but predates the object store / a backfill) must NOT be advertised cross-replica.
Simulation sharing additionally requires an explicit seed AND runs (a runs=None adaptive run is not
reproducible cross-replica).

These run in s3 mode against a local-fs object store + spies on mirror_lookup. (The existing service
suites run in local mode, where mirror_lookup is a no-op — they prove the gating doesn't regress the
single-replica path.)"""

from __future__ import annotations

from types import SimpleNamespace

from apps.api_server.services import repository_intelligence_execution_workflow as exec_wf
from apps.api_server.services import repository_intelligence_graph_workflow as graph_wf
from apps.api_server.services import repository_intelligence_object_store as obj
from apps.api_server.services import repository_intelligence_snapshot_workflow as snap_wf
from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403


def _s3_with_spies(monkeypatch, tmp_path):
    """Enable s3 mode against a local-fs store and record every mirror_lookup(kind) call."""
    store = obj.LocalFsBackend(tmp_path / "objstore")
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: store)
    calls: list[str] = []

    def _spy(module):
        real = module.mirror_lookup

        def _rec(*, org_id, repository_id, kind, lookup_key, payload):
            calls.append(kind)
            return real(
                org_id=org_id, repository_id=repository_id, kind=kind,
                lookup_key=lookup_key, payload=payload,
            )

        monkeypatch.setattr(module, "mirror_lookup", _rec)

    _spy(snap_wf)
    _spy(graph_wf)
    _spy(exec_wf)
    return store, calls


def _purge_shared(store, kind: str) -> None:
    for path in store._root.rglob("*"):
        if path.is_file() and kind in str(path):
            path.unlink()


def test_snapshot_lookup_published_only_on_durable_cold_create(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    store, calls = _s3_with_spies(monkeypatch, tmp_path)
    connector = _connector_for_repo(_sample_repo(tmp_path))
    org, rid = str(connector.org_id), str(connector.id)

    repository_service.create_repository_snapshot(
        connector=connector, request=RepositorySnapshotCreateRequest()
    )
    assert calls.count("snapshot_lookup") == 1, "cold-create must publish the shared lookup"

    # Force the manifest-exists branch: drop the node-local + shared lookup, KEEP the local manifest.
    import shutil

    shutil.rmtree(snap_wf.repository_runtime._snapshot_lookup_dir(org, rid), ignore_errors=True)
    _purge_shared(store, "snapshot_lookup")

    repository_service.create_repository_snapshot(
        connector=connector, request=RepositorySnapshotCreateRequest()
    )
    assert calls.count("snapshot_lookup") == 1, (
        "the manifest-exists branch must NOT advertise a snapshot whose object-store durability is "
        "unknown (it would 503 a cold sibling on hydration)"
    )


def test_triage_lookup_published_only_when_manifest_freshly_mirrored(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    store, calls = _s3_with_spies(monkeypatch, tmp_path)
    connector = _connector_for_repo(_sample_repo(tmp_path))
    org, rid = str(connector.org_id), str(connector.id)
    snapshot = repository_service.create_repository_snapshot(
        connector=connector, request=RepositorySnapshotCreateRequest()
    )
    request = RepositoryTriageRequest(
        snapshot_id=snapshot.snapshot_id,
        signals={
            "issue_text": "handle_request crashes when user is null",
            "diagnostics": [
                {"path": "src/service.py", "line": 2, "severity": "error", "message": "AttributeError"}
            ],
        },
    )
    repository_service.triage_repository(connector=connector, request=request)
    assert calls.count("triage_lookup") == 1, "cold triage must publish the shared lookup"

    # Drop the node-local + shared triage lookup, KEEP the triage manifest (triage_path).
    import shutil

    shutil.rmtree(graph_wf._triage_lookup_dir(org, rid), ignore_errors=True)
    _purge_shared(store, "triage_lookup")

    repository_service.triage_repository(connector=connector, request=request)
    assert calls.count("triage_lookup") == 1, (
        "a triage whose manifest already existed (mirror skipped) must NOT be advertised — a cold "
        "sibling's plan stage would 404 on the un-mirrored triage manifest"
    )


@pytest.mark.anyio
async def test_simulation_lookup_requires_explicit_seed_and_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    store, calls = _s3_with_spies(monkeypatch, tmp_path)
    connector = _connector_for_repo(_literal_mismatch_repo(tmp_path))
    snapshot = repository_service.create_repository_snapshot(
        connector=connector, request=RepositorySnapshotCreateRequest()
    )
    triage = repository_service.triage_repository(
        connector=connector,
        request=RepositoryTriageRequest(
            snapshot_id=snapshot.snapshot_id,
            signals={
                "issue_text": (
                    "Production regression: normalize_status returns closed for OPEN inputs."
                ),
                "diagnostics": [
                    {
                        "path": "src/service.py",
                        "line": 4,
                        "severity": "error",
                        "message": "normalize_status('OPEN') returns 'closed' instead of 'open'.",
                    }
                ],
            },
        ),
    )

    async def _fake_run_simulation_fast(*args, **kwargs):
        return _decision_envelope(), {"execution_ms": 11}

    monkeypatch.setattr(repository_service, "run_simulation_fast", _fake_run_simulation_fast)
    monkeypatch.setattr(
        repository_service, "get_policy",
        lambda _org: SimpleNamespace(snapshot_id="policy-1", min_confidence=0.8, risk_floor=20.0),
    )
    plan = await repository_service.create_repository_decision_plan(
        connector=connector,
        request=RepositoryDecisionPlanCreateRequest(
            snapshot_id=snapshot.snapshot_id,
            workspace_evidence_bundle_ref=triage.workspace_evidence_bundle_ref,
            model=repository_service._DETERMINISTIC_LOCAL_REPOSITORY_MODEL_ID,
        ),
    )

    # runs=None (the adaptive/env-influenced default) is NOT reproducible cross-replica -> not shared.
    await repository_service.simulate_repository_decision(
        connector=connector,
        request=RepositorySimulationRequest(
            snapshot_id=snapshot.snapshot_id, decision_plan_id=plan.decision_plan_id, seed=42,
        ),
    )
    assert calls.count("simulation_lookup") == 0, "runs=None must NOT be shared cross-replica"

    # explicit seed + runs, cold -> deterministic + durably mirrored -> published.
    await repository_service.simulate_repository_decision(
        connector=connector,
        request=RepositorySimulationRequest(
            snapshot_id=snapshot.snapshot_id, decision_plan_id=plan.decision_plan_id,
            seed=42, runs=5000,
        ),
    )
    assert calls.count("simulation_lookup") == 1, "an explicit-seed+runs cold simulation must publish"
