"""B9: mirror an agent run's proof bundle to the durable object store (cross-replica recovery).

Best-effort by design — proof archival must never fail the agent run. s3 mode only; the sidecar's
canonical (already-redacted) artifacts are mirrored under kind="proofs", and put_json re-applies
credential-field redaction defense-in-depth."""

from __future__ import annotations

import json

from apps.api_server.services import repository_intelligence_object_store as obj
from apps.api_server.services import repository_intelligence_proof_store as ps

_BUNDLE = {
    "run_id": "r1",
    "artifacts": {
        "gate.json": {"terminal_state": "succeeded", "apply_allowed": True},
        "messages.json": {"sensitive": True, "messages": [{"role": "user"}], "api_key": "sk-LEAK"},
        "events.ndjson": [{"event": "a"}, {"event": "b"}],
    },
}


def _use_s3(monkeypatch, tmp_path):
    store = obj.LocalFsBackend(tmp_path / "store")
    monkeypatch.setattr(obj, "object_store_mode", lambda: "s3")
    monkeypatch.setattr(obj, "get_object_store", lambda: store)
    return store


def _key(name: str) -> str:
    return obj.artifact_key(org_id="o", repository_id="r", kind="proofs", artifact_id=f"r1:{name}")


async def test_mirror_is_noop_in_local_mode(monkeypatch):
    monkeypatch.delenv("ALGENTA_RI_OBJECT_STORE", raising=False)
    assert await ps.mirror_proof_artifacts(org_id="o", repository_id="r", agent_run_id="r1") == 0


async def test_mirror_is_noop_when_no_agent_run(monkeypatch, tmp_path):
    _use_s3(monkeypatch, tmp_path)
    assert await ps.mirror_proof_artifacts(org_id="o", repository_id="r", agent_run_id=None) == 0


async def test_mirror_writes_bundle_and_redacts_secrets(monkeypatch, tmp_path):
    store = _use_s3(monkeypatch, tmp_path)

    async def _fake_fetch(_run_id):
        return _BUNDLE

    monkeypatch.setattr(ps, "_fetch_proof_bundle", _fake_fetch)

    mirrored = await ps.mirror_proof_artifacts(org_id="o", repository_id="r", agent_run_id="r1")
    assert mirrored == 3

    gate = store.get_json(_key("gate.json"))
    assert gate["terminal_state"] == "succeeded"
    # JSON artifacts go through put_json -> credential-shaped fields are redacted (defense-in-depth)
    messages = store.get_json(_key("messages.json"))
    assert "sk-LEAK" not in json.dumps(messages), "the api_key value must be redacted before persisting"
    # events.ndjson decodes to a list, persisted as a JSON document via put_bytes
    events = json.loads(store.get_bytes(_key("events.ndjson")))
    assert events == [{"event": "a"}, {"event": "b"}]


async def test_mirror_is_best_effort_on_fetch_failure(monkeypatch, tmp_path):
    _use_s3(monkeypatch, tmp_path)

    async def _boom(_run_id):
        raise ConnectionError("sidecar unreachable")

    monkeypatch.setattr(ps, "_fetch_proof_bundle", _boom)
    # must NOT raise — proof archival never fails the run
    assert await ps.mirror_proof_artifacts(org_id="o", repository_id="r", agent_run_id="r1") == 0


async def test_mirror_skips_a_bad_artifact_but_keeps_the_rest(monkeypatch, tmp_path):
    store = _use_s3(monkeypatch, tmp_path)

    async def _fetch(_run_id):
        return {"artifacts": {"gate.json": {"ok": True}, "events.ndjson": [{"event": "x"}]}}

    monkeypatch.setattr(ps, "_fetch_proof_bundle", _fetch)
    # a put that raises on one artifact must not abort the others
    real_put_json = store.put_json
    calls = {"n": 0}

    def _flaky_put_json(key, payload):
        calls["n"] += 1
        if "gate.json" in key:
            raise RuntimeError("transient")
        return real_put_json(key, payload)

    monkeypatch.setattr(store, "put_json", _flaky_put_json)
    mirrored = await ps.mirror_proof_artifacts(org_id="o", repository_id="r", agent_run_id="r1")
    assert mirrored == 1  # events.ndjson still mirrored despite gate.json failing
    assert json.loads(store.get_bytes(_key("events.ndjson"))) == [{"event": "x"}]
