"""Tests for infra/ci/az_orchestrator.py's workflow_job webhook receiver.

Covers the security-critical piece (HMAC verification must fail closed, including with no
secret configured), delivery dedup (GitHub retries a delivery verbatim on any non-2xx/timeout
response), and an end-to-end run of the real HTTP handler over a loopback socket -- proving the
actual wire-level parsing + label/repo filtering + dispatch call works, not just isolated units.
"""
from __future__ import annotations

import hashlib
import hmac as hmac_module
import http.client
import importlib.util
import json
import threading
import time
from http.server import HTTPServer
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
    spec = importlib.util.spec_from_file_location("az_orchestrator_webhook_under_test", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    with patch("os.makedirs"):
        spec.loader.exec_module(mod)
    return mod


def _sign(secret, body):
    return "sha256=" + hmac_module.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_verify_signature_accepts_a_correctly_signed_body(monkeypatch):
    mod = _load_orchestrator(monkeypatch)
    body = b'{"action":"queued"}'
    assert mod._verify_signature("s3cr3t", body, _sign("s3cr3t", body)) is True


def test_verify_signature_rejects_a_wrong_secret(monkeypatch):
    mod = _load_orchestrator(monkeypatch)
    body = b'{"action":"queued"}'
    assert mod._verify_signature("s3cr3t", body, _sign("wrong-secret", body)) is False


def test_verify_signature_rejects_a_tampered_body(monkeypatch):
    mod = _load_orchestrator(monkeypatch)
    sig = _sign("s3cr3t", b'{"action":"queued"}')
    assert mod._verify_signature("s3cr3t", b'{"action":"tampered"}', sig) is False


def test_verify_signature_fails_closed_with_no_secret_configured(monkeypatch):
    mod = _load_orchestrator(monkeypatch)
    body = b'{"action":"queued"}'
    # Even a correctly-formed signature against an EMPTY secret must not verify -- an unset
    # WEBHOOK_SECRET must never silently accept every request.
    assert mod._verify_signature("", body, _sign("", body)) is False


def test_delivery_dedup_rejects_a_repeated_delivery_id(monkeypatch):
    mod = _load_orchestrator(monkeypatch)
    assert mod._delivery_dedup("abc-123") is False  # first sighting: not a dup
    assert mod._delivery_dedup("abc-123") is True  # same id again: dup, GitHub's own retry


def test_delivery_dedup_expires_after_the_ttl(monkeypatch):
    mod = _load_orchestrator(monkeypatch)
    fake_now = [1000.0]
    monkeypatch.setattr(mod.time, "time", lambda: fake_now[0])
    assert mod._delivery_dedup("abc-123") is False
    fake_now[0] += mod._DELIVERY_TTL_S + 1
    assert mod._delivery_dedup("abc-123") is False  # TTL passed -- treated as fresh again


class _LiveServer:
    """Runs the real _WebhookHandler over a loopback socket on an OS-assigned port."""

    def __init__(self, mod):
        self.mod = mod
        self.server = HTTPServer(("127.0.0.1", 0), mod._WebhookHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def post(self, body: bytes, headers: dict) -> int:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/", body=body, headers=headers)
        status = conn.getresponse().status
        conn.close()
        return status

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def _wire(mod, monkeypatch, *, secret="s3cr3t", served=("thyn-ai/algenta",)):
    monkeypatch.setattr(mod, "WEBHOOK_SECRET", secret)
    monkeypatch.setattr(mod, "log", lambda *a, **kw: None)
    monkeypatch.setattr(mod, "served_repos", lambda: list(served))
    monkeypatch.setattr(mod, "live_vms", lambda: [])
    dispatched = []
    monkeypatch.setattr(mod, "_dispatch_job", lambda job, vms: dispatched.append(job) or True)
    prewarmed = []
    monkeypatch.setattr(mod, "_prewarm", lambda reason: prewarmed.append(reason) or True)
    return dispatched, prewarmed


def test_live_handler_dispatches_a_correctly_signed_queued_az_ephemeral_job(monkeypatch):
    mod = _load_orchestrator(monkeypatch)
    dispatched, _ = _wire(mod, monkeypatch)
    srv = _LiveServer(mod)
    try:
        payload = {
            "action": "queued",
            "repository": {"full_name": "thyn-ai/algenta"},
            "workflow_job": {"id": 42, "run_id": 99, "labels": ["self-hosted", "az-ephemeral"]},
        }
        body = json.dumps(payload).encode()
        status = srv.post(
            body,
            {
                "X-Hub-Signature-256": _sign("s3cr3t", body),
                "X-GitHub-Delivery": "delivery-1",
                "X-GitHub-Event": "workflow_job",
                "Content-Type": "application/json",
            },
        )
        assert status == 202
        deadline = time.time() + 2
        while not dispatched and time.time() < deadline:
            time.sleep(0.01)
        assert len(dispatched) == 1
        assert dispatched[0]["id"] == 42
    finally:
        srv.close()


def test_live_handler_rejects_a_bad_signature_and_never_dispatches(monkeypatch):
    mod = _load_orchestrator(monkeypatch)
    dispatched, _ = _wire(mod, monkeypatch)
    srv = _LiveServer(mod)
    try:
        payload = {
            "action": "queued",
            "repository": {"full_name": "thyn-ai/algenta"},
            "workflow_job": {"id": 42, "run_id": 99, "labels": ["self-hosted", "az-ephemeral"]},
        }
        body = json.dumps(payload).encode()
        status = srv.post(
            body,
            {
                "X-Hub-Signature-256": _sign("WRONG-secret", body),
                "X-GitHub-Delivery": "delivery-2",
                "X-GitHub-Event": "workflow_job",
                "Content-Type": "application/json",
            },
        )
        assert status == 401
        time.sleep(0.1)
        assert dispatched == []
    finally:
        srv.close()


def test_live_handler_ignores_a_job_without_the_az_ephemeral_label(monkeypatch):
    mod = _load_orchestrator(monkeypatch)
    dispatched, _ = _wire(mod, monkeypatch)
    srv = _LiveServer(mod)
    try:
        payload = {
            "action": "queued",
            "repository": {"full_name": "thyn-ai/algenta"},
            "workflow_job": {"id": 7, "run_id": 1, "labels": ["ubuntu-latest"]},
        }
        body = json.dumps(payload).encode()
        status = srv.post(
            body,
            {
                "X-Hub-Signature-256": _sign("s3cr3t", body),
                "X-GitHub-Delivery": "delivery-3",
                "X-GitHub-Event": "workflow_job",
                "Content-Type": "application/json",
            },
        )
        assert status == 202  # acked -- just not acted on
        time.sleep(0.1)
        assert dispatched == []
    finally:
        srv.close()


def test_live_handler_ignores_a_repo_outside_served_repos(monkeypatch):
    mod = _load_orchestrator(monkeypatch)
    dispatched, _ = _wire(mod, monkeypatch, served=("thyn-ai/algenta",))
    srv = _LiveServer(mod)
    try:
        payload = {
            "action": "queued",
            "repository": {"full_name": "thyn-ai/some-unrelated-repo"},
            "workflow_job": {"id": 8, "run_id": 2, "labels": ["self-hosted", "az-ephemeral"]},
        }
        body = json.dumps(payload).encode()
        status = srv.post(
            body,
            {
                "X-Hub-Signature-256": _sign("s3cr3t", body),
                "X-GitHub-Delivery": "delivery-4",
                "X-GitHub-Event": "workflow_job",
                "Content-Type": "application/json",
            },
        )
        assert status == 202
        time.sleep(0.1)
        assert dispatched == []
    finally:
        srv.close()


def test_live_handler_ignores_a_duplicate_delivery(monkeypatch):
    mod = _load_orchestrator(monkeypatch)
    dispatched, _ = _wire(mod, monkeypatch)
    srv = _LiveServer(mod)
    try:
        payload = {
            "action": "queued",
            "repository": {"full_name": "thyn-ai/algenta"},
            "workflow_job": {"id": 9, "run_id": 3, "labels": ["self-hosted", "az-ephemeral"]},
        }
        body = json.dumps(payload).encode()
        headers = {
            "X-Hub-Signature-256": _sign("s3cr3t", body),
            "X-GitHub-Delivery": "delivery-5",
            "X-GitHub-Event": "workflow_job",
            "Content-Type": "application/json",
        }
        srv.post(body, headers)
        time.sleep(0.1)
        srv.post(body, headers)  # GitHub's own retry: identical delivery id
        time.sleep(0.1)
        assert len(dispatched) == 1
    finally:
        srv.close()


def test_live_handler_prewarms_on_pull_request_opened(monkeypatch):
    mod = _load_orchestrator(monkeypatch)
    dispatched, prewarmed = _wire(mod, monkeypatch)
    srv = _LiveServer(mod)
    try:
        payload = {"action": "opened", "repository": {"full_name": "thyn-ai/algenta"}}
        body = json.dumps(payload).encode()
        status = srv.post(
            body,
            {
                "X-Hub-Signature-256": _sign("s3cr3t", body),
                "X-GitHub-Delivery": "delivery-pr-1",
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
        assert status == 202
        time.sleep(0.1)
        assert len(prewarmed) == 1
        assert dispatched == []  # pre-warm only -- never claims/dispatches a job itself
    finally:
        srv.close()


def test_live_handler_prewarms_on_pull_request_synchronize_but_not_on_closed(monkeypatch):
    mod = _load_orchestrator(monkeypatch)
    _dispatched, prewarmed = _wire(mod, monkeypatch)
    srv = _LiveServer(mod)
    try:
        for action, delivery in (("synchronize", "delivery-pr-2"), ("closed", "delivery-pr-3")):
            payload = {"action": action, "repository": {"full_name": "thyn-ai/algenta"}}
            body = json.dumps(payload).encode()
            srv.post(
                body,
                {
                    "X-Hub-Signature-256": _sign("s3cr3t", body),
                    "X-GitHub-Delivery": delivery,
                    "X-GitHub-Event": "pull_request",
                    "Content-Type": "application/json",
                },
            )
        time.sleep(0.1)
        assert len(prewarmed) == 1  # only "synchronize" triggered a pre-warm, not "closed"
    finally:
        srv.close()


def test_live_handler_ignores_pull_request_for_a_repo_outside_served_repos(monkeypatch):
    mod = _load_orchestrator(monkeypatch)
    _dispatched, prewarmed = _wire(mod, monkeypatch, served=("thyn-ai/algenta",))
    srv = _LiveServer(mod)
    try:
        payload = {"action": "opened", "repository": {"full_name": "thyn-ai/unrelated"}}
        body = json.dumps(payload).encode()
        srv.post(
            body,
            {
                "X-Hub-Signature-256": _sign("s3cr3t", body),
                "X-GitHub-Delivery": "delivery-pr-4",
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
        time.sleep(0.1)
        assert prewarmed == []
    finally:
        srv.close()


def test_live_handler_prewarms_on_push_to_a_ci_triggering_branch(monkeypatch):
    mod = _load_orchestrator(monkeypatch, AZ_ORCH_PREWARM_BRANCHES="main,develop")
    _dispatched, prewarmed = _wire(mod, monkeypatch)
    srv = _LiveServer(mod)
    try:
        payload = {"ref": "refs/heads/develop", "repository": {"full_name": "thyn-ai/algenta"}}
        body = json.dumps(payload).encode()
        status = srv.post(
            body,
            {
                "X-Hub-Signature-256": _sign("s3cr3t", body),
                "X-GitHub-Delivery": "delivery-push-1",
                "X-GitHub-Event": "push",
                "Content-Type": "application/json",
            },
        )
        assert status == 202
        time.sleep(0.1)
        assert len(prewarmed) == 1
    finally:
        srv.close()


def test_live_handler_ignores_push_to_a_non_ci_triggering_branch(monkeypatch):
    # Default PREWARM_PUSH_BRANCHES is just "main" -- a push to a random feature branch
    # never queues a workflow_job in the first place, so pre-warming for it would just waste
    # an Azure VM for nothing.
    mod = _load_orchestrator(monkeypatch)
    _dispatched, prewarmed = _wire(mod, monkeypatch)
    srv = _LiveServer(mod)
    try:
        payload = {
            "ref": "refs/heads/some-feature-branch",
            "repository": {"full_name": "thyn-ai/algenta"},
        }
        body = json.dumps(payload).encode()
        srv.post(
            body,
            {
                "X-Hub-Signature-256": _sign("s3cr3t", body),
                "X-GitHub-Delivery": "delivery-push-2",
                "X-GitHub-Event": "push",
                "Content-Type": "application/json",
            },
        )
        time.sleep(0.1)
        assert prewarmed == []
    finally:
        srv.close()


def test_live_handler_ignores_a_subscribed_but_unhandled_event_type(monkeypatch):
    # An org's webhook UI can default to subscribing to more than what this receiver acts on
    # (confirmed live: creating the real hook also subscribed "push" -- handled above -- plus
    # whatever else the org default includes). Anything truly unhandled must still ack cleanly.
    mod = _load_orchestrator(monkeypatch)
    dispatched, prewarmed = _wire(mod, monkeypatch)
    srv = _LiveServer(mod)
    try:
        body = json.dumps({"zen": "Speak like a human."}).encode()
        status = srv.post(
            body,
            {
                "X-Hub-Signature-256": _sign("s3cr3t", body),
                "X-GitHub-Delivery": "delivery-ping-1",
                "X-GitHub-Event": "ping",
                "Content-Type": "application/json",
            },
        )
        assert status == 202
        time.sleep(0.1)
        assert dispatched == []
        assert prewarmed == []
    finally:
        srv.close()
