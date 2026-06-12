"""Real-backend s3 smoke: exercise the ACTUAL S3Backend (boto3 → MinIO), not a LocalFsBackend mock.

Every other object-store test monkeypatches the backend to LocalFsBackend, so the real boto3 /
endpoint / egress-guard / bucket-create path is otherwise untested. This runs only when an operator
(or CI) has provisioned MinIO: ALGENTA_RI_OBJECT_STORE=s3 + S3_ENDPOINT_URL set + the endpoint
reachable. It skips cleanly otherwise (mirroring how the multi-replica chaos suite skips without a
real Redis), so it's a no-op locally and a genuine integration check in CI."""

from __future__ import annotations

import os
import socket
import uuid
from urllib.parse import urlparse

import pytest

from apps.api_server.services import repository_intelligence_object_store as obj


def _minio_reachable() -> bool:
    endpoint = os.environ.get("S3_ENDPOINT_URL")
    if not endpoint or obj.object_store_mode() != "s3":
        return False
    parsed = urlparse(endpoint)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


@pytest.fixture
def s3_store():
    if not _minio_reachable():
        pytest.skip(
            "real s3/MinIO not configured — set ALGENTA_RI_OBJECT_STORE=s3 + S3_ENDPOINT_URL and run MinIO"
        )
    store = obj.get_object_store()
    assert store.name == "s3", f"expected the real S3Backend, got {store.name}"
    return store


def _key(kind: str) -> str:
    return obj.artifact_key(
        org_id="smoke", repository_id="repo", kind=kind, artifact_id=f"it-{uuid.uuid4().hex}"
    )


def test_s3_backend_json_round_trip(s3_store):
    key = _key("snapshots")
    payload = {"hello": "minio", "n": 7, "resolved_revision": "abc123", "nested": {"a": [1, 2]}}
    s3_store.put_json(key, payload)
    assert s3_store.get_json(key) == payload
    assert s3_store.exists(key) is True


def test_s3_backend_genuine_miss_returns_none(s3_store):
    # A genuine miss must be None (NOT an availability fault) — the recovery loaders depend on this.
    assert s3_store.get_json(_key("snapshots")) is None
    assert s3_store.get_bytes(_key("archives")) is None
    assert s3_store.exists(_key("snapshots")) is False


def test_s3_backend_bytes_round_trip(s3_store):
    key = _key("symbol_graph_parquet")
    blob = b"\x00\x01PARQUET-ish\xff" * 64
    s3_store.put_bytes(key, blob, content_type="application/vnd.apache.parquet")
    assert s3_store.get_bytes(key) == blob


def test_mirror_helper_writes_through_real_s3(s3_store):
    # The snapshot manifest mirror helper must persist through the real boto3/MinIO path and be
    # readable back under the identity-derived key (the B8 cross-replica contract).
    from apps.api_server.services.repository_intelligence_snapshot_workflow import (
        _mirror_snapshot_manifest_to_object_store,
    )

    snapshot_id = f"snap-{uuid.uuid4().hex}"
    manifest = {"repository_id": "repo", "snapshot_id": snapshot_id, "manifest_version": 2, "files": []}
    key = _mirror_snapshot_manifest_to_object_store(
        org_id="smoke", repository_id="repo", snapshot_id=snapshot_id, manifest=manifest
    )
    assert key is not None
    assert s3_store.get_json(key) == manifest
