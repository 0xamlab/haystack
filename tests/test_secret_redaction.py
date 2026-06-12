"""B10 PR9: defense-in-depth secret redaction for persisted artifacts + logs.

Two halves matter equally: (1) credential-shaped keys ARE redacted before an artifact/log is
written (incl. the compound keys the anchored cline_proof_common pattern misses, and the per-tenant
key shapes PR10/PR11 introduce); (2) the redactor must NOT corrupt the repository-intelligence
manifest count fields (token_estimate / raw_repo_token_estimate / token_count) — a bare `token`
substring match would, which is exactly why those are excluded."""

from __future__ import annotations

import json

import pytest

from apps.api_server.main import _redact_log_secrets
from apps.api_server.services import repository_intelligence_object_store as obj
from apps.api_server.services.secret_redaction import REDACTED, redact_secret_fields


# --- must redact -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key",
    [
        "api_key",
        "x-api-key",
        "x_api_key",
        "engine_api_key",
        "provider_api_key",
        "authorization",
        "authorization_header",
        "access_token",
        "provider_token",
        "refresh_token",
        "client_secret",
        "password",
        "passphrase",
        "private_key",
        "cookie",
        "credential",
    ],
)
def test_secret_keys_are_redacted(key):
    out = redact_secret_fields({key: "sensitive-value", "keep": 1})
    assert out[key] == REDACTED
    assert out["keep"] == 1


def test_redaction_recurses_into_nested_dicts_and_lists():
    payload = {
        "engine": {"api_key": "k", "model": "m"},
        "runs": [{"authorization": "Bearer t", "n": 3}],
    }
    out = redact_secret_fields(payload)
    assert out["engine"]["api_key"] == REDACTED
    assert out["engine"]["model"] == "m"
    assert out["runs"][0]["authorization"] == REDACTED
    assert out["runs"][0]["n"] == 3


# --- must NOT corrupt (the manifest count fields + benign keys) --------------------------------


@pytest.mark.parametrize(
    "key",
    [
        "token_estimate",
        "raw_repo_token_estimate",
        "evidence_bundle_token_count",
        "token_count",
        "session_id",
        "runtime_kind",
        "runtime_model",
        "decision_plan_id",
        "snapshot_id",
        "agent_run_id",
        "model_id",
    ],
)
def test_benign_keys_are_not_redacted(key):
    out = redact_secret_fields({key: 1234})
    assert out[key] == 1234


def test_redactor_is_pure_does_not_mutate_input():
    payload = {"api_key": "k", "n": 1}
    _ = redact_secret_fields(payload)
    assert payload["api_key"] == "k"  # original untouched


# --- wired into the object store + structlog ---------------------------------------------------


def test_object_store_put_json_redacts_before_write(tmp_path):
    store = obj.LocalFsBackend(tmp_path / "store")
    key = obj.artifact_key(org_id="o", repository_id="r", kind="snapshots", artifact_id="s1")
    store.put_json(key, {"engine_api_key": "secret", "token_estimate": 999, "snapshot_id": "s1"})
    persisted = store.get_json(key)
    assert persisted["engine_api_key"] == REDACTED
    assert persisted["token_estimate"] == 999  # count field survives
    assert persisted["snapshot_id"] == "s1"
    # and the raw bytes on disk never contain the secret value
    raw = store._path(key).read_bytes().decode()
    assert "secret" not in raw


def test_structlog_processor_redacts_event_dict():
    event = {"event": "agent_call", "authorization": "Bearer xyz", "x_api_key": "k", "latency_ms": 5}
    out = _redact_log_secrets(None, "info", event)
    assert out["authorization"] == REDACTED
    assert out["x_api_key"] == REDACTED
    assert out["latency_ms"] == 5
    assert out["event"] == "agent_call"
