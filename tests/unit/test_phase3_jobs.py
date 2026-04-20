"""Unit tests for Phase 3 — job state machine and webhook service."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import uuid

from apps.api_server.models.job import (
    JobStatus,
    is_terminal,
    is_valid_transition,
)
from apps.api_server.services.webhook_service import (
    _sign_payload,
    build_webhook_payload,
    verify_webhook_signature,
)


class TestJobStateMachine:
    """Tests for the job lifecycle state machine transitions."""

    def test_queued_can_go_to_validating(self) -> None:
        assert is_valid_transition(JobStatus.QUEUED, JobStatus.VALIDATING)

    def test_queued_can_be_cancelled(self) -> None:
        assert is_valid_transition(JobStatus.QUEUED, JobStatus.CANCELLED)

    def test_queued_cannot_go_to_completed(self) -> None:
        assert not is_valid_transition(JobStatus.QUEUED, JobStatus.COMPLETED)

    def test_validating_can_go_to_running(self) -> None:
        assert is_valid_transition(JobStatus.VALIDATING, JobStatus.RUNNING)

    def test_validating_can_fail(self) -> None:
        assert is_valid_transition(JobStatus.VALIDATING, JobStatus.FAILED)

    def test_running_can_complete(self) -> None:
        assert is_valid_transition(JobStatus.RUNNING, JobStatus.COMPLETED)

    def test_running_can_fail(self) -> None:
        assert is_valid_transition(JobStatus.RUNNING, JobStatus.FAILED)

    def test_running_can_be_cancelled(self) -> None:
        assert is_valid_transition(JobStatus.RUNNING, JobStatus.CANCELLED)

    def test_completed_can_expire(self) -> None:
        assert is_valid_transition(JobStatus.COMPLETED, JobStatus.EXPIRED)

    def test_completed_cannot_go_to_running(self) -> None:
        assert not is_valid_transition(JobStatus.COMPLETED, JobStatus.RUNNING)

    def test_failed_has_no_valid_transitions(self) -> None:
        for status in JobStatus:
            assert not is_valid_transition(JobStatus.FAILED, status)

    def test_cancelled_has_no_valid_transitions(self) -> None:
        for status in JobStatus:
            assert not is_valid_transition(JobStatus.CANCELLED, status)

    def test_expired_has_no_valid_transitions(self) -> None:
        for status in JobStatus:
            assert not is_valid_transition(JobStatus.EXPIRED, status)


class TestTerminalStates:
    def test_completed_is_terminal(self) -> None:
        assert is_terminal(JobStatus.COMPLETED)

    def test_failed_is_terminal(self) -> None:
        assert is_terminal(JobStatus.FAILED)

    def test_cancelled_is_terminal(self) -> None:
        assert is_terminal(JobStatus.CANCELLED)

    def test_expired_is_terminal(self) -> None:
        assert is_terminal(JobStatus.EXPIRED)

    def test_queued_is_not_terminal(self) -> None:
        assert not is_terminal(JobStatus.QUEUED)

    def test_running_is_not_terminal(self) -> None:
        assert not is_terminal(JobStatus.RUNNING)

    def test_validating_is_not_terminal(self) -> None:
        assert not is_terminal(JobStatus.VALIDATING)


class TestWebhookSignature:
    def test_sign_payload_produces_hex_string(self) -> None:
        payload = b'{"event": "job.completed"}'
        signature = _sign_payload(payload, "test-secret")
        assert len(signature) == 64  # SHA-256 hex digest
        int(signature, 16)  # Must be valid hex

    def test_same_payload_same_secret_same_signature(self) -> None:
        payload = b'{"event": "job.completed"}'
        s1 = _sign_payload(payload, "my-secret")
        s2 = _sign_payload(payload, "my-secret")
        assert s1 == s2

    def test_different_secret_different_signature(self) -> None:
        payload = b'{"event": "job.completed"}'
        s1 = _sign_payload(payload, "secret-1")
        s2 = _sign_payload(payload, "secret-2")
        assert s1 != s2

    def test_different_payload_different_signature(self) -> None:
        s1 = _sign_payload(b'payload-1', "secret")
        s2 = _sign_payload(b'payload-2', "secret")
        assert s1 != s2

    def test_verify_signature_valid(self) -> None:
        payload = b'{"event": "job.completed"}'
        secret = "my-webhook-secret"
        signature = _sign_payload(payload, secret)
        assert verify_webhook_signature(payload, f"sha256={signature}", secret)

    def test_verify_signature_invalid_secret(self) -> None:
        payload = b'{"event": "job.completed"}'
        signature = _sign_payload(payload, "correct-secret")
        assert not verify_webhook_signature(payload, f"sha256={signature}", "wrong-secret")

    def test_verify_signature_tampered_payload(self) -> None:
        payload = b'{"event": "job.completed"}'
        signature = _sign_payload(payload, "my-secret")
        tampered = b'{"event": "job.failed"}'
        assert not verify_webhook_signature(tampered, f"sha256={signature}", "my-secret")

    def test_verify_signature_missing_prefix(self) -> None:
        payload = b'test'
        signature = _sign_payload(payload, "secret")
        # Without sha256= prefix → invalid
        assert not verify_webhook_signature(payload, signature, "secret")


class TestBuildWebhookPayload:
    def test_required_fields_present(self) -> None:
        job_id = uuid.uuid4()
        run_id = uuid.uuid4()
        org_id = uuid.uuid4()
        payload = build_webhook_payload("job.completed", job_id, run_id, org_id)
        assert payload["event"] == "job.completed"
        assert payload["job_id"] == str(job_id)
        assert payload["run_id"] == str(run_id)
        assert payload["org_id"] == str(org_id)
        assert "timestamp" in payload

    def test_result_included_when_provided(self) -> None:
        result = {"expected_value": 50000, "probability_of_loss": 0.1}
        payload = build_webhook_payload(
            "job.completed",
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            result=result,
        )
        assert payload["result"]["expected_value"] == 50000

    def test_error_included_when_provided(self) -> None:
        payload = build_webhook_payload(
            "job.failed",
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
            error="Engine timeout",
        )
        assert payload["error"] == "Engine timeout"

    def test_no_result_no_error_by_default(self) -> None:
        payload = build_webhook_payload(
            "webhook.test",
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        )
        assert "result" not in payload
        assert "error" not in payload
