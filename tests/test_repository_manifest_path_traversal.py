"""Cross-tenant isolation: the local-FS manifest loaders join a client-supplied artifact id into a
path, so an unvalidated ``..``/``/`` could traverse out of the org's directory into another
tenant's. Every loader must reject a malformed id (matching the object-store ``_KEY_SEGMENT`` guard
that the s3 branch already enforces) BEFORE touching the filesystem.
"""

from __future__ import annotations

import pytest

from apps.api_server.services import repository_intelligence_storage as st
from apps.api_server.services.repository_intelligence_contracts import RepositoryIntelligenceError

_TRAVERSAL_IDS = [
    "../../../etc/passwd",
    "../other-org-id/repo/snapshots/s",
    "..",
    "a/b",
    "foo/../../bar",
    "x\\y",
    "with space",
    "",
]

# (loader, kwarg-name) for each client-id manifest loader.
_LOADERS = [
    (st._load_snapshot_manifest, "snapshot_id"),
    (st._load_triage_manifest, "evidence_bundle_ref"),
    (st._load_decision_plan_manifest, "decision_plan_id"),
    (st._load_patch_impact_manifest, "patch_impact_report_id"),
    (st._load_simulation_manifest, "simulation_id"),
]


@pytest.mark.parametrize("loader,kw", _LOADERS)
@pytest.mark.parametrize("bad", _TRAVERSAL_IDS)
def test_loader_rejects_traversal_id_before_fs_access(loader, kw, bad):
    with pytest.raises(RepositoryIntelligenceError) as exc:
        loader(org_id="o", repository_id="r", **{kw: bad})
    assert exc.value.code == "invalid_artifact_id"
    assert exc.value.status_code == 422


def test_snapshot_paths_rejects_traversal():
    with pytest.raises(RepositoryIntelligenceError) as exc:
        st._snapshot_paths("o", "r", "../../../victim/snap")
    assert exc.value.code == "invalid_artifact_id"


@pytest.mark.parametrize("loader,kw", _LOADERS)
def test_valid_id_passes_the_guard_then_normal_recover(monkeypatch, loader, kw):
    # A well-formed id must NOT be rejected by the guard — it falls through to the normal
    # local-miss -> object-store recover path (stubbed here to a sentinel so we don't hit s3/fs).
    def _sentinel(**_kwargs):
        raise RepositoryIntelligenceError(code="reached_recover", message="ok", status_code=404)

    monkeypatch.setattr(st, "_recover_manifest_from_object_store", _sentinel)
    with pytest.raises(RepositoryIntelligenceError) as exc:
        loader(org_id="o", repository_id="r", **{kw: "valid-id_123:abc"})
    assert exc.value.code == "reached_recover"  # guard passed; reached the normal recover path
