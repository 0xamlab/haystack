"""B8 byte-slice: the generated patch ``.diff`` through the durable object store.

The .diff was node-local, but APPLY reads it via `_patch_text_for_plan` from the manifest's
`patch_path` — so a plan generated on one replica could not be applied on another (404). Now the
decision-plan workflow mirrors the .diff on write and apply recovers it from the object store by
identity (the filename stem is the deterministic patch_artifact_id). The patch-impact + triage
Parquet sidecars stay node-local on purpose — they are redundant with their self-contained,
already-mirrored manifests."""

from __future__ import annotations

import pytest

from apps.api_server.services import repository_intelligence_decision_plan_workflow as dp
from apps.api_server.services import repository_intelligence_execution_workflow as ex
from apps.api_server.services import repository_intelligence_object_store as obj
from apps.api_server.services.repository_intelligence_contracts import RepositoryIntelligenceError

_DIFF = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-old\n+new\n"
_PID = "patch-abc123"


def _use_s3(monkeypatch, tmp_path):
    store = obj.LocalFsBackend(tmp_path / "store")
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: store)
    return store


def test_mirror_patch_diff_is_noop_in_local_mode(monkeypatch):
    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)
    assert (
        dp._mirror_patch_diff_to_object_store(
            org_id="o", repository_id="r", patch_artifact_id=_PID, patch_diff=_DIFF
        )
        is None
    )


def test_mirror_then_recover_round_trip_in_s3(monkeypatch, tmp_path):
    store = _use_s3(monkeypatch, tmp_path)
    key = dp._mirror_patch_diff_to_object_store(
        org_id="o", repository_id="r", patch_artifact_id=_PID, patch_diff=_DIFF
    )
    assert key == obj.artifact_key(org_id="o", repository_id="r", kind="patches", artifact_id=_PID)
    assert store.get_bytes(key).decode("utf-8") == _DIFF
    assert (
        ex._recover_patch_diff_from_object_store(
            org_id="o", repository_id="r", patch_artifact_id=_PID
        )
        == _DIFF
    )


def test_recover_is_none_on_local_mode_and_genuine_miss(monkeypatch, tmp_path):
    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)
    assert (
        ex._recover_patch_diff_from_object_store(org_id="o", repository_id="r", patch_artifact_id=_PID)
        is None
    )
    _use_s3(monkeypatch, tmp_path)
    assert (
        ex._recover_patch_diff_from_object_store(
            org_id="o", repository_id="r", patch_artifact_id="absent"
        )
        is None
    )


def test_patch_text_for_plan_serves_local_file_when_present(tmp_path):
    patch_path = tmp_path / f"{_PID}.diff"
    patch_path.write_text(_DIFF, encoding="utf-8")
    assert (
        ex._patch_text_for_plan(
            org_id="o", repository_id="r", decision_plan_manifest={"patch_path": str(patch_path)}
        )
        == _DIFF
    )


def test_patch_text_for_plan_recovers_cross_replica_when_local_missing(monkeypatch, tmp_path):
    _use_s3(monkeypatch, tmp_path)
    dp._mirror_patch_diff_to_object_store(
        org_id="o", repository_id="r", patch_artifact_id=_PID, patch_diff=_DIFF
    )
    # the manifest points at a patch_path that does NOT exist on this node (generated on a sibling)
    manifest = {"patch_path": str(tmp_path / "nonexistent" / f"{_PID}.diff")}
    assert (
        ex._patch_text_for_plan(org_id="o", repository_id="r", decision_plan_manifest=manifest)
        == _DIFF
    )


def test_patch_text_for_plan_404_when_absent_everywhere(monkeypatch, tmp_path):
    _use_s3(monkeypatch, tmp_path)  # s3 enabled but nothing mirrored
    manifest = {"patch_path": str(tmp_path / "nope" / f"{_PID}.diff")}
    with pytest.raises(RepositoryIntelligenceError) as exc:
        ex._patch_text_for_plan(org_id="o", repository_id="r", decision_plan_manifest=manifest)
    assert exc.value.status_code == 404
