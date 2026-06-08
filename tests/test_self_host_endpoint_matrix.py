from __future__ import annotations

from typing import Any

import pytest

from scripts.self_host_endpoint_matrix import APIClient, EndpointMatrixRunner, MatrixCheckError


class _FakeAPIClient(APIClient):
    def __init__(self) -> None:
        super().__init__("http://localhost:18020")
        self.org_name = "Self Hosted Org"
        self.policy_min_confidence = 0.5
        self.created_key_id = "key-1"
        self.created_key_raw = "de_test_secondary_key"
        self.created_key_prefix = "de_test_seco"
        self.created_key_expires_at = "2028-05-19T00:00:00Z"
        self.key_deleted = False
        self.run_id = "run-1"
        self.dataset_id = "dataset-1"
        self.dataset_deleted = False

    def request(  # type: ignore[override]
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        expected_status: int = 200,
        timeout: float = 20.0,
    ) -> tuple[int, Any, dict[str, str]]:
        _ = timeout

        if method == "GET" and path == "/v1/health":
            return 200, {"status": "ok", "timestamp": "2026-05-01T00:00:00Z"}, {}
        if method == "GET" and path == "/v1/version":
            return (
                200,
                {"api_version": "1.0.0", "engine_version": "0.1.0", "environment": "production"},
                {},
            )
        if method == "POST" and path == "/auth/login":
            if body != {"email": "owner@selfhost.algenta.ai", "password": "stub-password-123"}:
                raise MatrixCheckError(f"unexpected login body: {body!r}")
            return (
                200,
                {"access_token": "jwt-token", "token_type": "bearer", "expires_in": 3600},
                {},
            )
        if method == "GET" and path == "/v1/me":
            if headers and headers.get("X-API-Key") == self.created_key_raw:
                if self.key_deleted:
                    return (
                        401,
                        {"error": {"code": "invalid_api_key", "message": "Invalid API key."}},
                        {},
                    )
                return 200, self._me_payload(), {}
            return 200, self._me_payload(), {}
        if method == "PATCH" and path == "/v1/me":
            self.org_name = str(body["org_name"])
            return 200, self._me_payload(), {}
        if method == "GET" and path == "/v1/limits":
            return (
                200,
                {
                    "plan": "free",
                    "max_simulations_per_month": 500,
                    "max_runs_per_simulation": 10000,
                    "rate_limit_per_minute": 60,
                },
                {},
            )
        if method == "GET" and path == "/v1/usage":
            return 200, {"simulations_run": 3, "quota_limit": 500, "quota_used_pct": 0.6}, {}
        if method == "GET" and path == "/v1/distributions":
            return 200, [{"name": "normal"}], {}
        if method == "GET" and path == "/v1/templates":
            return 200, [{"id": "pricing", "name": "Pricing"}], {}
        if method == "POST" and path == "/v1/api-keys":
            if body != {
                "label": "self-host-matrix-key",
                "expires_at": self.created_key_expires_at,
            }:
                raise MatrixCheckError(f"unexpected api key create body: {body!r}")
            return (
                201,
                {
                    "id": self.created_key_id,
                    "raw_key": self.created_key_raw,
                    "key_prefix": self.created_key_prefix,
                    "label": "self-host-matrix-key",
                    "expires_at": self.created_key_expires_at,
                },
                {},
            )
        if method == "GET" and path == "/v1/api-keys":
            keys = (
                []
                if self.key_deleted
                else [
                    {
                        "id": self.created_key_id,
                        "label": "self-host-matrix-key",
                        "key_prefix": self.created_key_prefix,
                        "expires_at": self.created_key_expires_at,
                    }
                ]
            )
            return 200, {"api_keys": keys}, {}
        if method == "DELETE" and path == f"/v1/api-keys/{self.created_key_id}":
            self.key_deleted = True
            return 204, None, {}
        if method == "GET" and path == "/v1/engines":
            return 200, {"count": 1, "engines": [{"slug": "decision"}]}, {}
        if method == "GET" and path == "/v1/engines/tiers":
            return 200, {"core": [], "advanced": [], "platform": []}, {}
        if method == "GET" and path == "/v1/engines/decision":
            return 200, {"slug": "decision", "name": "Decision", "mojo_libs": ["a", "b", "c"]}, {}
        if method == "GET" and path == "/v1/execution/policy":
            return 200, self._execution_policy_payload(), {}
        if method == "PATCH" and path == "/v1/execution/policy":
            self.policy_min_confidence = float(body["min_confidence"])
            return 200, self._execution_policy_payload(), {}
        if method == "POST" and path == "/v1/simulate":
            return (
                200,
                {
                    "run_id": self.run_id,
                    "status": "completed",
                    "recommended_action": "proceed",
                },
                {},
            )
        if method == "POST" and path == "/v1/recommend":
            return 200, {"recommended_action": "Plan A"}, {}
        if method == "POST" and path == "/v1/score":
            return 200, {"score": 0.91}, {}
        if method == "POST" and path == "/v1/compare":
            return 200, {"winner": "Aggressive"}, {}
        if method == "POST" and path == "/v1/batch":
            return 200, {"total": 2, "succeeded": 2}, {}
        if method == "GET" and path == "/v1/runs":
            return 200, {"runs": [{"run_id": self.run_id}]}, {}
        if method == "GET" and path == f"/v1/runs/{self.run_id}":
            return 200, {"run_id": self.run_id, "status": "completed"}, {}
        if method == "GET" and path == "/v1/analytics":
            return 200, {"total_runs": 1}, {}
        if method == "POST" and path == "/v1/data/connect":
            return 200, {"status": "ready", "dataset_id": self.dataset_id}, {}
        if method == "GET" and path == "/v1/data":
            datasets = [] if self.dataset_deleted else [{"dataset_id": self.dataset_id}]
            return 200, {"datasets": datasets}, {}
        if method == "GET" and path == f"/v1/data/{self.dataset_id}":
            return (
                200,
                {
                    "dataset": {"dataset_id": self.dataset_id},
                    "schema": {"columns": [{"name": "revenue"}]},
                },
                {},
            )
        if method == "POST" and path == "/v1/query":
            return 200, {"result": {"value": 600}}, {}
        if method == "DELETE" and path == f"/v1/data/{self.dataset_id}":
            self.dataset_deleted = True
            return 200, {"status": "deleted"}, {}
        if method == "GET" and path == "/v1/team":
            return 200, [{"email": "owner@selfhost.algenta.ai"}], {}
        if method == "GET" and path == "/v1/connectors":
            return 200, {"connectors": []}, {}
        if method == "GET" and path == "/v1/connectors/types":
            return 200, {"types": ["file", "sql", "rest_api"]}, {}
        if method == "GET" and path == "/v1/deployments":
            return 200, None, {}
        if method == "GET" and path == "/v1/deployments/regions":
            return 200, {"providers": [{"id": "algenta_shared"}]}, {}
        if method == "GET" and path == "/v1/billing/info":
            return 200, {"plan": "free"}, {}

        raise MatrixCheckError(f"unexpected request: {method} {path} body={body!r}")

    def _me_payload(self) -> dict[str, Any]:
        return {
            "user": {
                "email": "owner@selfhost.algenta.ai",
                "name": "Owner",
                "role": "owner",
            },
            "org": {
                "id": "org-1",
                "name": self.org_name,
                "slug": "self-hosted-org",
                "plan": "free",
            },
        }

    def _execution_policy_payload(self) -> dict[str, Any]:
        return {
            "org_id": "org-1",
            "min_confidence": self.policy_min_confidence,
            "risk_floor": None,
            "require_calibration": False,
            "allow_reexecution": False,
            "updated_at": "2026-05-01T00:00:00Z",
        }


def test_self_host_endpoint_matrix_runner_happy_path() -> None:
    runner = EndpointMatrixRunner(
        _FakeAPIClient(),
        api_key="de_test_primary_key",
        bootstrap_email="owner@selfhost.algenta.ai",
        bootstrap_password="stub-password-123",
    )

    summary = runner.run()

    assert summary.failed == 0
    assert summary.passed > 20
    assert summary.skipped >= 5
    assert any(
        result.name == "POST /v1/query" and result.status == "passed" for result in summary.checks
    )
    assert any(
        result.name == "GET /v1/me (deleted X-API-Key)" and result.status == "passed"
        for result in summary.checks
    )
    assert any(
        result.name == "POST /v1/billing/checkout" and result.status == "skipped"
        for result in summary.checks
    )


def test_self_host_endpoint_matrix_rejects_algenta_cloud_base_url() -> None:
    with pytest.raises(ValueError, match="cannot target Algenta-owned cloud URLs"):
        APIClient("https://api.algenta.ai")
