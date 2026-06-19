from __future__ import annotations

import uuid

import pytest

from apps.api_server.routers import jobs


@pytest.mark.anyio
async def test_test_webhook_uses_webhook_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    auth_context = {"org_id": uuid.uuid4()}

    def _fake_build_webhook_payload(**kwargs: object) -> dict[str, object]:
        captured["built"] = kwargs
        return {"event": kwargs["event"], "result": kwargs["result"]}

    async def _fake_deliver_webhook(
        callback_url: str,
        payload: dict[str, object],
        max_retries: int,
        audit_context: object | None = None,
    ) -> tuple[bool, int, str]:
        captured["delivery"] = {
            "callback_url": callback_url,
            "payload": payload,
            "max_retries": max_retries,
            "audit_context": audit_context,
        }
        return True, 202, "accepted"

    monkeypatch.setattr(jobs, "build_webhook_payload", _fake_build_webhook_payload)
    monkeypatch.setattr(jobs, "deliver_webhook", _fake_deliver_webhook)

    response = await jobs.test_webhook(
        jobs.WebhookTestRequest(callback_url="https://example.com/webhook"),
        auth=auth_context,  # type: ignore[arg-type]
    )

    assert response.success is True
    assert response.status_code == 202
    assert response.message == "accepted"
    delivery = captured["delivery"]
    assert isinstance(delivery, dict)
    assert delivery["callback_url"] == "https://example.com/webhook"
    assert delivery["payload"] == {
        "event": "webhook.test",
        "result": {"message": "This is a test webhook from the Algenta API."},
    }
    assert delivery["max_retries"] == 0
    audit_context = delivery["audit_context"]
    assert audit_context is not None
    assert getattr(audit_context, "org_id", None) == auth_context["org_id"]
