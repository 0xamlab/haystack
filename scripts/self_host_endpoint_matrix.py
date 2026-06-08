#!/usr/bin/env python3
"""Self-hosted endpoint matrix for a running Algenta service."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

from apps.operator_http.privacy import validate_operator_api_base_url


class MatrixCheckError(RuntimeError):
    """Structured failure raised by endpoint matrix checks."""


@dataclass
class CheckResult:
    name: str
    status: str
    details: str


@dataclass
class MatrixSummary:
    total: int
    passed: int
    failed: int
    skipped: int
    checks: list[CheckResult]


class APIClient:
    """Small stdlib HTTP client with JSON decoding and structured errors."""

    def __init__(self, base_url: str) -> None:
        self.base_url = validate_operator_api_base_url(
            base_url,
            surface="Self-host endpoint matrix",
            require_self_hosted=True,
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        expected_status: int = 200,
        timeout: float = 20.0,
    ) -> tuple[int, Any, dict[str, str]]:
        request_headers = {"Accept": "application/json"}
        if headers:
            request_headers.update(headers)
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")

        req = urllib.request.Request(  # noqa: S310 - operator-provided self-host base URL
            f"{self.base_url}{path}",
            data=data,
            headers=request_headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(  # noqa: S310 - operator-provided self-host base URL
                req,
                timeout=timeout,
            ) as resp:
                raw = resp.read()
                parsed = self._decode_response(raw, resp.headers.get("Content-Type"))
                if resp.status != expected_status:
                    raise MatrixCheckError(
                        f"{method} {path} returned {resp.status}, "
                        f"expected {expected_status}: {parsed!r}"
                    )
                return resp.status, parsed, dict(resp.headers.items())
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            parsed = self._decode_response(raw, exc.headers.get("Content-Type"))
            if exc.code != expected_status:
                raise MatrixCheckError(
                    f"{method} {path} returned {exc.code}, expected {expected_status}: {parsed!r}"
                ) from exc
            return exc.code, parsed, dict(exc.headers.items())

    @staticmethod
    def _decode_response(raw: bytes, content_type: str | None) -> Any:
        if not raw:
            return None
        text = raw.decode("utf-8")
        if content_type and "json" in content_type.lower():
            return json.loads(text)
        stripped = text.lstrip()
        if (
            stripped.startswith("{")
            or stripped.startswith("[")
            or stripped in {"null", "true", "false"}
        ):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        return text


class EndpointMatrixRunner:
    """Run the self-host-safe endpoint matrix against a live API."""

    def __init__(
        self,
        client: APIClient,
        *,
        api_key: str,
        bootstrap_email: str,
        bootstrap_password: str,
    ) -> None:
        self.client = client
        self.api_key = api_key
        self.bootstrap_email = bootstrap_email
        self.bootstrap_password = bootstrap_password
        self.created_api_key_id: str | None = None
        self.created_api_key_raw_key: str | None = None
        self.created_api_key_prefix: str | None = None
        self.created_api_key_expires_at: str | None = None
        self.simulate_run_id: str | None = None
        self.dataset_id: str | None = None
        self.results: list[CheckResult] = []

    def run(self) -> MatrixSummary:
        self._run_check("GET /v1/health", self._check_health)
        self._run_check("GET /v1/version", self._check_version)
        self._run_check("POST /auth/login", self._check_login)

        self._run_check("GET /v1/me (API key)", self._check_me_with_api_key)
        self._run_check("PATCH /v1/me", self._check_patch_me)
        self._run_check("GET /v1/limits", self._check_limits)
        self._run_check("GET /v1/usage", self._check_usage)
        self._run_check("GET /v1/distributions", self._check_distributions)
        self._run_check("GET /v1/templates", self._check_templates)
        self._run_check("POST /v1/api-keys", self._check_api_key_create)
        self._run_check("GET /v1/api-keys", self._check_api_key_list_contains_created)
        self._run_check("GET /v1/me (new X-API-Key)", self._check_new_api_key_auth)
        self._run_check("DELETE /v1/api-keys/{id}", self._check_api_key_delete)
        self._run_check("GET /v1/me (deleted X-API-Key)", self._check_deleted_api_key_auth_rejected)
        self._run_check("GET /v1/api-keys after delete", self._check_api_key_deleted_absent)

        self._run_check("GET /v1/engines", self._check_engines)
        self._run_check("GET /v1/engines/tiers", self._check_engine_tiers)
        self._run_check("GET /v1/engines/decision", self._check_engine_detail)

        self._run_check("GET /v1/execution/policy", self._check_execution_policy_get)
        self._run_check("PATCH /v1/execution/policy", self._check_execution_policy_patch)

        self._run_check("POST /v1/simulate", self._check_simulate)
        self._run_check("POST /v1/recommend", self._check_recommend)
        self._run_check("POST /v1/score", self._check_score)
        self._run_check("POST /v1/compare", self._check_compare)
        self._run_check("POST /v1/batch", self._check_batch)
        self._run_check("GET /v1/runs", self._check_runs)
        self._run_check("GET /v1/runs/{run_id}", self._check_run_detail)
        self._run_check("GET /v1/analytics", self._check_analytics)

        self._run_check("POST /v1/data/connect", self._check_data_connect)
        self._run_check("GET /v1/data", self._check_data_list_contains_dataset)
        self._run_check("GET /v1/data/{dataset_id}", self._check_data_get)
        self._run_check("POST /v1/query", self._check_query)
        self._run_check("DELETE /v1/data/{dataset_id}", self._check_data_delete)
        self._run_check("GET /v1/data after delete", self._check_data_deleted_absent)

        self._run_check("GET /v1/team", self._check_team)
        self._run_check("GET /v1/connectors", self._check_connectors)
        self._run_check("GET /v1/connectors/types", self._check_connector_types)
        self._run_check("GET /v1/deployments", self._check_deployments)
        self._run_check("GET /v1/deployments/regions", self._check_deployment_regions)
        self._run_check("GET /v1/billing/info", self._check_billing_info)

        self._skip(
            "POST /v1/billing/checkout",
            "Requires live Stripe configuration.",
        )
        self._skip(
            "POST /v1/billing/portal",
            "Requires a created Stripe billing account.",
        )
        self._skip(
            "POST /v1/billing/webhook",
            "Requires Stripe signatures and external billing events.",
        )
        self._skip(
            "POST /v1/connectors/{id}/test and /v1/connectors/fetch",
            "Require external connector credentials or third-party systems.",
        )
        self._skip(
            "POST /v1/deployments and DELETE /v1/deployments/{id}",
            "Provision real cloud infrastructure outside the self-host baseline.",
        )
        self._skip(
            "GET /v1/logs",
            "Long-lived SSE stream; excluded from deterministic smoke coverage.",
        )

        total = len(self.results)
        passed = sum(1 for result in self.results if result.status == "passed")
        failed = sum(1 for result in self.results if result.status == "failed")
        skipped = sum(1 for result in self.results if result.status == "skipped")
        return MatrixSummary(
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            checks=self.results,
        )

    def _run_check(self, name: str, fn: Any) -> None:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            details = str(exc) or exc.__class__.__name__
            self.results.append(CheckResult(name=name, status="failed", details=details))
            print(f"[FAIL] {name}: {details}")
            return
        self.results.append(CheckResult(name=name, status="passed", details="ok"))
        print(f"[PASS] {name}")

    def _skip(self, name: str, reason: str) -> None:
        self.results.append(CheckResult(name=name, status="skipped", details=reason))
        print(f"[SKIP] {name}: {reason}")

    def _api_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        expected_status: int = 200,
        timeout: float = 20.0,
    ) -> Any:
        _, parsed, _ = self.client.request(
            method,
            path,
            body=body,
            headers=headers,
            expected_status=expected_status,
            timeout=timeout,
        )
        return parsed

    def _check_health(self) -> None:
        body = self._request_json("GET", "/v1/health")
        self._require(isinstance(body, dict), "Health response must be a JSON object.")
        self._require(body.get("status") == "ok", f"Unexpected health payload: {body!r}")

    def _check_version(self) -> None:
        body = self._request_json("GET", "/v1/version")
        self._require(isinstance(body, dict), "Version response must be a JSON object.")
        for field in ("api_version", "engine_version", "environment"):
            self._require(field in body, f"Missing version field '{field}'.")

    def _check_login(self) -> None:
        body = self._request_json(
            "POST",
            "/auth/login",
            body={
                "email": self.bootstrap_email,
                "password": self.bootstrap_password,
            },
        )
        self._require(isinstance(body, dict), "Login response must be a JSON object.")
        token = body.get("access_token")
        self._require(isinstance(token, str) and token, f"Missing access token: {body!r}")
        self._require(body.get("token_type") == "bearer", f"Unexpected token type: {body!r}")
        expires_in = body.get("expires_in")
        self._require(
            isinstance(expires_in, int) and expires_in > 0,
            f"Unexpected expires_in: {body!r}",
        )

    def _check_me_with_api_key(self) -> None:
        body = self._request_json("GET", "/v1/me", headers=self._api_headers())
        self._validate_me_payload(body)

    def _check_patch_me(self) -> None:
        body = self._request_json(
            "PATCH",
            "/v1/me",
            body={"org_name": "Self Hosted Matrix Org"},
            headers=self._api_headers(),
        )
        self._validate_me_payload(body)
        org = body.get("org") if isinstance(body, dict) else None
        self._require(
            isinstance(org, dict),
            f"PATCH /v1/me missing org payload: {body!r}",
        )
        self._require(
            org.get("name") == "Self Hosted Matrix Org",
            f"Org name was not updated: {body!r}",
        )

    def _check_limits(self) -> None:
        body = self._request_json("GET", "/v1/limits", headers=self._api_headers())
        self._require(isinstance(body, dict), "Limits response must be a JSON object.")
        for field in (
            "plan",
            "max_simulations_per_month",
            "max_runs_per_simulation",
            "rate_limit_per_minute",
        ):
            self._require(field in body, f"Missing limits field '{field}'.")

    def _check_usage(self) -> None:
        body = self._request_json("GET", "/v1/usage", headers=self._api_headers())
        self._require(isinstance(body, dict), "Usage response must be a JSON object.")
        self._require("simulations_run" in body, f"Missing simulations_run: {body!r}")

    def _check_distributions(self) -> None:
        body = self._request_json("GET", "/v1/distributions", headers=self._api_headers())
        items = self._extract_items(body, "distributions")
        self._require(len(items) > 0, "No distributions returned.")

    def _check_templates(self) -> None:
        body = self._request_json("GET", "/v1/templates", headers=self._api_headers())
        items = self._extract_items(body, "templates")
        self._require(len(items) > 0, "No templates returned.")

    def _check_api_key_create(self) -> None:
        expires_at = "2028-05-19T00:00:00Z"
        body = self._request_json(
            "POST",
            "/v1/api-keys",
            body={"label": "self-host-matrix-key", "expires_at": expires_at},
            headers=self._api_headers(),
            expected_status=201,
        )
        self._require(isinstance(body, dict), "API key create response must be a JSON object.")
        key_id = body.get("id")
        raw_key = body.get("raw_key")
        key_prefix = body.get("key_prefix")
        returned_expires_at = body.get("expires_at")
        self._require(isinstance(key_id, str) and key_id, f"Missing API key id: {body!r}")
        self._require(
            isinstance(raw_key, str) and raw_key.startswith("de_"),
            f"Missing raw API key: {body!r}",
        )
        self._require(
            isinstance(key_prefix, str) and key_prefix and raw_key.startswith(key_prefix),
            f"Missing or mismatched API key prefix: {body!r}",
        )
        self._require(
            returned_expires_at == expires_at,
            f"API key create expires_at mismatch: {body!r}",
        )
        self.created_api_key_id = key_id
        self.created_api_key_raw_key = raw_key
        self.created_api_key_prefix = key_prefix
        self.created_api_key_expires_at = returned_expires_at

    def _check_api_key_list_contains_created(self) -> None:
        body = self._request_json("GET", "/v1/api-keys", headers=self._api_headers())
        items = self._extract_items(body, "api_keys")
        matching_item = next(
            (
                item
                for item in items
                if isinstance(item, dict)
                and str(item.get("id") or item.get("key_id")) == self.created_api_key_id
            ),
            None,
        )
        self._require(
            isinstance(matching_item, dict),
            f"Created API key {self.created_api_key_id!r} missing from list: {items!r}",
        )
        self._require(
            matching_item.get("expires_at") == self.created_api_key_expires_at,
            f"Created API key expires_at missing from list: {matching_item!r}",
        )
        self._require(
            matching_item.get("key_prefix") == self.created_api_key_prefix,
            f"Created API key prefix missing from list: {matching_item!r}",
        )
        self._require(
            "raw_key" not in matching_item and "key" not in matching_item,
            f"API key list leaked one-time secret material: {matching_item!r}",
        )

    def _check_new_api_key_auth(self) -> None:
        self._require(
            self.created_api_key_raw_key is not None,
            "Created API key raw secret is not available.",
        )
        body = self._request_json(
            "GET",
            "/v1/me",
            headers={"X-API-Key": self.created_api_key_raw_key},
        )
        self._validate_me_payload(body)

    def _check_api_key_delete(self) -> None:
        self._require(self.created_api_key_id is not None, "Created API key id is not available.")
        self._request_json(
            "DELETE",
            f"/v1/api-keys/{self.created_api_key_id}",
            headers=self._api_headers(),
            expected_status=204,
        )

    def _check_deleted_api_key_auth_rejected(self) -> None:
        self._require(
            self.created_api_key_raw_key is not None,
            "Created API key raw secret is not available.",
        )
        body = self._request_json(
            "GET",
            "/v1/me",
            headers={"X-API-Key": self.created_api_key_raw_key},
            expected_status=401,
        )
        self._require(isinstance(body, dict), f"Unexpected revoked-key payload: {body!r}")
        error = body.get("error") or body.get("detail", {}).get("error")
        self._require(
            isinstance(error, dict) and error.get("code") == "invalid_api_key",
            f"Revoked key did not fail closed with invalid_api_key: {body!r}",
        )

    def _check_api_key_deleted_absent(self) -> None:
        body = self._request_json("GET", "/v1/api-keys", headers=self._api_headers())
        items = self._extract_items(body, "api_keys")
        ids = {
            str(item.get("id") or item.get("key_id")) for item in items if isinstance(item, dict)
        }
        self._require(
            self.created_api_key_id not in ids,
            f"Deleted API key {self.created_api_key_id!r} still present: {sorted(ids)!r}",
        )

    def _check_engines(self) -> None:
        body = self._request_json("GET", "/v1/engines", headers=self._api_headers())
        self._require(isinstance(body, dict), "Engines response must be a JSON object.")
        engines = body.get("engines")
        self._require(
            isinstance(engines, list) and len(engines) > 0,
            f"Invalid engines payload: {body!r}",
        )
        self._require(body.get("count") == len(engines), f"Engine count mismatch: {body!r}")

    def _check_engine_tiers(self) -> None:
        body = self._request_json("GET", "/v1/engines/tiers", headers=self._api_headers())
        self._require(isinstance(body, dict), "Engine tiers response must be a JSON object.")
        for field in ("core", "advanced", "platform"):
            self._require(
                field in body and isinstance(body[field], list),
                f"Missing engine tier '{field}'.",
            )

    def _check_engine_detail(self) -> None:
        body = self._request_json("GET", "/v1/engines/decision", headers=self._api_headers())
        self._require(isinstance(body, dict), "Engine detail response must be a JSON object.")
        self._require(body.get("slug") == "decision", f"Unexpected engine detail: {body!r}")
        self._require(isinstance(body.get("mojo_libs"), list), f"Missing mojo_libs: {body!r}")

    def _check_execution_policy_get(self) -> None:
        body = self._request_json("GET", "/v1/execution/policy", headers=self._api_headers())
        self._validate_execution_policy(body)

    def _check_execution_policy_patch(self) -> None:
        body = self._request_json(
            "PATCH",
            "/v1/execution/policy",
            body={"min_confidence": 0.61},
            headers=self._api_headers(),
        )
        self._validate_execution_policy(body)
        self._require(
            math.isclose(
                float(body.get("min_confidence", 0.0)),
                0.61,
                rel_tol=0.0,
                abs_tol=1e-9,
            ),
            f"Execution policy patch did not persist: {body!r}",
        )

    def _check_simulate(self) -> None:
        body = self._request_json(
            "POST",
            "/v1/simulate",
            body=self._simulation_request("Self-hosted matrix simulate", runs=1000),
            headers=self._api_headers(),
        )
        self._require(isinstance(body, dict), "Simulate response must be a JSON object.")
        run_id = body.get("run_id")
        self._require(isinstance(run_id, str) and run_id, f"Missing run_id: {body!r}")
        self._require(body.get("status") == "completed", f"Unexpected simulate status: {body!r}")
        self.simulate_run_id = run_id

    def _check_recommend(self) -> None:
        body = self._request_json(
            "POST",
            "/v1/recommend",
            body={
                "actions": [
                    {
                        "name": "Plan A",
                        "request": self._simulation_request(
                            "Plan A",
                            low=100000,
                            high=180000,
                            runs=300,
                        ),
                    },
                    {
                        "name": "Plan B",
                        "request": self._simulation_request(
                            "Plan B",
                            low=80000,
                            high=150000,
                            runs=300,
                        ),
                    },
                ]
            },
            headers=self._api_headers(),
            timeout=30.0,
        )
        self._require(isinstance(body, dict), "Recommend response must be a JSON object.")
        self._require(
            isinstance(body.get("recommended_action"), str),
            f"Missing recommended_action: {body!r}",
        )

    def _check_score(self) -> None:
        body = self._request_json(
            "POST",
            "/v1/score",
            body={
                "request": self._simulation_request("Score request", runs=300),
                "scoring_weights": {
                    "expected_value": 0.7,
                    "downside_risk": 0.3,
                },
            },
            headers=self._api_headers(),
            timeout=30.0,
        )
        self._require(isinstance(body, dict), "Score response must be a JSON object.")
        self._require("score" in body, f"Missing score field: {body!r}")

    def _check_compare(self) -> None:
        body = self._request_json(
            "POST",
            "/v1/compare",
            body={
                "scenarios": [
                    {
                        "name": "Base",
                        "request": self._simulation_request("Base scenario", runs=300),
                    },
                    {
                        "name": "Aggressive",
                        "request": self._simulation_request(
                            "Aggressive scenario",
                            low=90000,
                            high=220000,
                            runs=300,
                        ),
                    },
                ]
            },
            headers=self._api_headers(),
            timeout=30.0,
        )
        self._require(isinstance(body, dict), "Compare response must be a JSON object.")
        self._require(isinstance(body.get("winner"), str), f"Missing winner: {body!r}")

    def _check_batch(self) -> None:
        body = self._request_json(
            "POST",
            "/v1/batch",
            body={
                "items": [
                    self._simulation_request("Batch 1", runs=200),
                    self._simulation_request("Batch 2", low=90000, high=190000, runs=200),
                ]
            },
            headers=self._api_headers(),
            timeout=30.0,
        )
        self._require(isinstance(body, dict), "Batch response must be a JSON object.")
        self._require(body.get("total") == 2, f"Unexpected batch total: {body!r}")
        self._require(body.get("succeeded") == 2, f"Unexpected batch success count: {body!r}")

    def _check_runs(self) -> None:
        def _predicate(body: Any) -> bool:
            return (
                isinstance(body, dict)
                and isinstance(body.get("runs"), list)
                and any(
                    isinstance(run, dict) and run.get("run_id") == self.simulate_run_id
                    for run in body["runs"]
                )
            )

        body = self._poll_json("GET", "/v1/runs", headers=self._api_headers(), predicate=_predicate)
        self._require(isinstance(body, dict), f"Unexpected runs payload: {body!r}")

    def _check_run_detail(self) -> None:
        self._require(self.simulate_run_id is not None, "Simulate run id is not available.")
        body = self._poll_json(
            "GET",
            f"/v1/runs/{self.simulate_run_id}",
            headers=self._api_headers(),
        )
        self._require(isinstance(body, dict), "Run detail response must be a JSON object.")
        self._require(
            body.get("run_id") == self.simulate_run_id,
            f"Unexpected run detail: {body!r}",
        )

    def _check_analytics(self) -> None:
        body = self._poll_json(
            "GET",
            "/v1/analytics",
            headers=self._api_headers(),
            predicate=(
                lambda payload: isinstance(payload, dict) and int(payload.get("total_runs", 0)) >= 1
            ),
        )
        self._require(isinstance(body, dict), "Analytics response must be a JSON object.")

    def _check_data_connect(self) -> None:
        body = self._request_json(
            "POST",
            "/v1/data/connect",
            body={
                "connection_type": "file_upload",
                "dataset_name": "SelfHostMatrixDataset",
                "description": "Self-host endpoint matrix fixture",
                "csv": (
                    "product_line,revenue,cost\nElectronics,100,40\nApparel,200,80\nHome,300,100\n"
                ),
            },
            headers=self._api_headers(),
            timeout=30.0,
        )
        self._require(isinstance(body, dict), "Data connect response must be a JSON object.")
        self._require(body.get("status") == "ready", f"Unexpected data connect status: {body!r}")
        dataset_id = body.get("dataset_id")
        self._require(isinstance(dataset_id, str) and dataset_id, f"Missing dataset_id: {body!r}")
        self.dataset_id = dataset_id

    def _check_data_list_contains_dataset(self) -> None:
        body = self._request_json("GET", "/v1/data", headers=self._api_headers())
        self._require(isinstance(body, dict), "Data list response must be a JSON object.")
        datasets = body.get("datasets")
        self._require(isinstance(datasets, list), f"Missing datasets list: {body!r}")
        ids = {str(dataset.get("dataset_id")) for dataset in datasets if isinstance(dataset, dict)}
        self._require(
            self.dataset_id in ids,
            f"Dataset {self.dataset_id!r} missing from data list: {sorted(ids)!r}",
        )

    def _check_data_get(self) -> None:
        self._require(self.dataset_id is not None, "Dataset id is not available.")
        body = self._request_json(
            "GET",
            f"/v1/data/{self.dataset_id}",
            headers=self._api_headers(),
        )
        self._require(isinstance(body, dict), "Dataset detail response must be a JSON object.")
        dataset = body.get("dataset")
        schema = body.get("schema")
        self._require(isinstance(dataset, dict), f"Missing dataset object: {body!r}")
        self._require(isinstance(schema, dict), f"Missing schema object: {body!r}")
        self._require(
            dataset.get("dataset_id") == self.dataset_id,
            f"Unexpected dataset detail: {body!r}",
        )

    def _check_query(self) -> None:
        self._require(self.dataset_id is not None, "Dataset id is not available.")
        body = self._request_json(
            "POST",
            "/v1/query",
            body={
                "dataset_id": self.dataset_id,
                "metric_column": "revenue",
                "aggregation": "sum",
            },
            headers=self._api_headers(),
            timeout=30.0,
        )
        actual = self._extract_result_value(body)
        self._require(
            math.isclose(actual, 600.0, rel_tol=0.0, abs_tol=1e-9),
            f"Unexpected query result: {body!r}",
        )

    def _check_data_delete(self) -> None:
        self._require(self.dataset_id is not None, "Dataset id is not available.")
        body = self._request_json(
            "DELETE",
            f"/v1/data/{self.dataset_id}",
            headers=self._api_headers(),
        )
        self._require(isinstance(body, dict), "Dataset delete response must be a JSON object.")
        self._require(body.get("status") == "deleted", f"Unexpected delete response: {body!r}")

    def _check_data_deleted_absent(self) -> None:
        body = self._request_json("GET", "/v1/data", headers=self._api_headers())
        self._require(isinstance(body, dict), "Data list response must be a JSON object.")
        datasets = body.get("datasets")
        self._require(isinstance(datasets, list), f"Missing datasets list: {body!r}")
        ids = {str(dataset.get("dataset_id")) for dataset in datasets if isinstance(dataset, dict)}
        self._require(
            self.dataset_id not in ids,
            f"Deleted dataset {self.dataset_id!r} still present: {sorted(ids)!r}",
        )

    def _check_team(self) -> None:
        body = self._request_json("GET", "/v1/team", headers=self._api_headers())
        items = self._extract_items(body, "members")
        self._require(
            any(
                isinstance(member, dict) and member.get("email") == self.bootstrap_email
                for member in items
            ),
            f"Bootstrap user {self.bootstrap_email!r} missing from team list: {body!r}",
        )

    def _check_connectors(self) -> None:
        body = self._request_json("GET", "/v1/connectors", headers=self._api_headers())
        if isinstance(body, list):
            return
        self._require(
            isinstance(body, dict) and isinstance(body.get("connectors"), list),
            f"Unexpected connectors payload: {body!r}",
        )

    def _check_connector_types(self) -> None:
        body = self._request_json("GET", "/v1/connectors/types", headers=self._api_headers())
        self._require(isinstance(body, dict), "Connector types response must be a JSON object.")
        self._require(
            isinstance(body.get("types"), list),
            f"Unexpected connector types payload: {body!r}",
        )

    def _check_deployments(self) -> None:
        body = self._request_json("GET", "/v1/deployments", headers=self._api_headers())
        self._require(
            body is None or isinstance(body, dict),
            f"Unexpected deployments payload: {body!r}",
        )

    def _check_deployment_regions(self) -> None:
        body = self._request_json("GET", "/v1/deployments/regions", headers=self._api_headers())
        self._require(isinstance(body, dict), "Deployment regions response must be a JSON object.")
        providers = body.get("providers")
        self._require(
            isinstance(providers, list) and len(providers) > 0,
            f"Unexpected deployment regions payload: {body!r}",
        )

    def _check_billing_info(self) -> None:
        body = self._request_json("GET", "/v1/billing/info", headers=self._api_headers())
        self._require(isinstance(body, dict), "Billing info response must be a JSON object.")
        self._require("plan" in body, f"Missing billing plan field: {body!r}")

    def _poll_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        expected_status: int = 200,
        timeout: float = 20.0,
        predicate: Any | None = None,
        wait_seconds: int = 20,
        interval_seconds: float = 1.0,
    ) -> Any:
        last_payload: Any = None
        attempts = max(1, int(wait_seconds / interval_seconds))
        for _ in range(attempts):
            last_payload = self._request_json(
                method,
                path,
                body=body,
                headers=headers,
                expected_status=expected_status,
                timeout=timeout,
            )
            if predicate is None or predicate(last_payload):
                return last_payload
            time.sleep(interval_seconds)
        raise MatrixCheckError(
            f"{method} {path} did not satisfy readiness predicate: {last_payload!r}"
        )

    @staticmethod
    def _extract_items(body: Any, key: str) -> list[Any]:
        if isinstance(body, list):
            return body
        if isinstance(body, dict):
            items = body.get(key)
            if isinstance(items, list):
                return items
        raise MatrixCheckError(f"Expected list or '{key}' envelope, got: {body!r}")

    @staticmethod
    def _extract_result_value(body: Any) -> float:
        if isinstance(body, dict):
            result = body.get("result")
            if isinstance(result, dict) and "value" in result:
                return float(result["value"])
            if isinstance(result, (int, float)):
                return float(result)
        raise MatrixCheckError(
            f"Could not extract numeric result value from query response: {body!r}"
        )

    @staticmethod
    def _validate_me_payload(body: Any) -> None:
        if not isinstance(body, dict):
            raise MatrixCheckError(f"Expected me response to be an object, got: {body!r}")
        user = body.get("user")
        org = body.get("org")
        if not isinstance(user, dict) or not isinstance(org, dict):
            raise MatrixCheckError(f"Missing user/org payload in me response: {body!r}")
        for field in ("email", "name", "role"):
            if field not in user:
                raise MatrixCheckError(f"Missing user field '{field}' in me response: {body!r}")
        for field in ("id", "name", "slug", "plan"):
            if field not in org:
                raise MatrixCheckError(f"Missing org field '{field}' in me response: {body!r}")

    @staticmethod
    def _validate_execution_policy(body: Any) -> None:
        if not isinstance(body, dict):
            raise MatrixCheckError(
                f"Expected execution policy response to be an object, got: {body!r}"
            )
        for field in (
            "org_id",
            "min_confidence",
            "require_calibration",
            "allow_reexecution",
            "updated_at",
        ):
            if field not in body:
                raise MatrixCheckError(f"Missing execution policy field '{field}': {body!r}")

    @staticmethod
    def _simulation_request(
        scenario_name: str,
        *,
        low: int = 80000,
        high: int = 200000,
        runs: int = 500,
    ) -> dict[str, Any]:
        return {
            "mode": "auto",
            "scenario": {
                "name": scenario_name,
                "variables": {
                    "revenue": {"low": low, "high": high},
                    "cost": {"low": 30000, "high": 90000},
                },
                "objective": "maximize_net_value",
            },
            "runs": runs,
            "seed": 42,
        }

    @staticmethod
    def _require(condition: bool, message: str) -> None:
        if not condition:
            raise MatrixCheckError(message)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        required=True,
        help="Base API URL, e.g. http://localhost:18020",
    )
    parser.add_argument(
        "--api-key",
        required=True,
        help="Operator API key. Prefer a rotated bounded-lifetime key.",
    )
    parser.add_argument("--bootstrap-email", required=True, help="Bootstrap owner email.")
    parser.add_argument(
        "--bootstrap-password",
        required=True,
        help="Bootstrap owner password.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    runner = EndpointMatrixRunner(
        APIClient(args.base_url),
        api_key=args.api_key,
        bootstrap_email=args.bootstrap_email,
        bootstrap_password=args.bootstrap_password,
    )
    summary = runner.run()
    print(json.dumps(asdict(summary), indent=2))
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
