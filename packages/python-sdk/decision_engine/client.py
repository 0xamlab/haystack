"""
Synchronous Decision Engine API client.

Usage:
    from decision_engine import DecisionEngineClient

    client = DecisionEngineClient(api_key="de_live_...")
    result = client.simulate(
        mode="auto",
        scenario={
            "variables": {"revenue": {"low": 80000, "high": 200000}},
            "objective": "maximize_net_value",
        },
    )
    print(result.recommended_action, result.confidence)
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from ._contract import DEFAULT_BASE_URL
from .exceptions import (
    AuthenticationError,
    DecisionEngineError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from .models import (
    APIKeyInfo,
    DecisionEnvelope,
    ExplainResult,
    QueryResult,
    ResolveResult,
    SourceRegistrationResult,
    UsageInfo,
    VerifyResult,
)

DEFAULT_TIMEOUT = 120.0
DEFAULT_MAX_RETRIES = 3


def _strip_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def _normalize_expert_variable(variable: dict[str, Any]) -> dict[str, Any]:
    if "params" in variable and isinstance(variable["params"], dict):
        params = dict(variable["params"])
    else:
        params = _strip_none(
            {
                "mean": variable.get("mean"),
                "std": variable.get("std") or variable.get("std_dev"),
                "low": variable.get("low"),
                "mode": variable.get("mode"),
                "high": variable.get("high"),
                "value": variable.get("value"),
                "min": variable.get("min"),
                "max": variable.get("max"),
                "p": variable.get("p"),
                "shape": variable.get("shape"),
                "scale": variable.get("scale"),
            }
        )
    return {
        "name": variable.get("name", "value"),
        "distribution": variable.get("distribution", "fixed"),
        "params": params,
    }


def _normalize_simulation_request(payload: dict[str, Any]) -> dict[str, Any]:
    if "scenario" in payload or "simulation" in payload:
        return payload

    variables = payload.get("variables")
    if isinstance(variables, dict):
        normalized = {
            "mode": "auto",
            "scenario": {
                "variables": variables,
                "objective": payload.get("objective", "maximize_net_value"),
            },
            "runs": payload.get("runs", 10_000),
        }
        if payload.get("seed") is not None:
            normalized["seed"] = payload["seed"]
        if payload.get("simulation_model") is not None:
            normalized["simulation_model"] = payload["simulation_model"]
        return normalized

    if isinstance(variables, list):
        variable_names = [v.get("name", "value") for v in variables if isinstance(v, dict)]
        objective = (
            payload.get("objective_function")
            or payload.get("objective")
            or " + ".join(variable_names)
            or "value"
        )
        normalized = {
            "mode": "expert",
            "simulation": {
                "variables": [
                    _normalize_expert_variable(v) for v in variables if isinstance(v, dict)
                ],
                "objective_function": objective,
                "scoring": payload.get("scoring", {"expected_value": 0.6, "downside_risk": 0.4}),
            },
            "runs": payload.get("runs", 10_000),
        }
        if payload.get("seed") is not None:
            normalized["seed"] = payload["seed"]
        if payload.get("simulation_model") is not None:
            normalized["simulation_model"] = payload["simulation_model"]
        return normalized

    return payload


def _normalize_recommend_request(actions: Any, **kwargs: Any) -> dict[str, Any]:
    if isinstance(actions, dict):
        payload = dict(actions)
        if "actions" in payload:
            return payload
        if "options" in payload:
            normalized_actions = []
            for idx, option in enumerate(payload.get("options", []), start=1):
                name = option.get("label") or option.get("name") or f"option_{idx}"
                expected_value = float(option.get("expected_value", 0.0) or 0.0)
                risk = max(float(option.get("risk", 0.1) or 0.1), 0.05)
                spread = max(abs(expected_value) * risk, 1.0)
                normalized_actions.append(
                    {
                        "name": name,
                        "request": {
                            "mode": "expert",
                            "simulation": {
                                "variables": [
                                    {
                                        "name": "outcome",
                                        "distribution": "triangular",
                                        "params": {
                                            "low": expected_value - spread,
                                            "mode": expected_value,
                                            "high": expected_value + spread,
                                        },
                                    }
                                ],
                                "objective_function": "outcome",
                                "scoring": {"expected_value": 0.6, "downside_risk": 0.4},
                            },
                            "runs": payload.get("runs", 1000),
                        },
                    }
                )
            return {"actions": normalized_actions, "runs": payload.get("runs", 1000)}
        return payload

    return {"actions": actions, **kwargs}


def _normalize_compare_request(scenarios: Any, **kwargs: Any) -> dict[str, Any]:
    if isinstance(scenarios, dict):
        payload = dict(scenarios)
        if "scenarios" in payload:
            scenarios = payload["scenarios"]
            kwargs = {k: v for k, v in payload.items() if k != "scenarios"}
        else:
            return payload

    normalized = []
    for idx, scenario in enumerate(scenarios, start=1):
        if isinstance(scenario, dict) and "request" in scenario and "name" in scenario:
            normalized.append(scenario)
            continue
        if isinstance(scenario, dict):
            name = scenario.get("label") or scenario.get("name") or f"scenario_{idx}"
            request = _normalize_simulation_request(
                {k: v for k, v in scenario.items() if k not in {"label", "name"}}
            )
            normalized.append({"name": name, "request": request})
    return {"scenarios": normalized, **kwargs}


def _merge_request_payload(
    payload: dict[str, Any] | None, kwargs: dict[str, Any]
) -> dict[str, Any]:
    merged = dict(payload or {})
    merged.update(kwargs)
    return merged


def _normalize_source_registration_request(
    source: dict[str, Any] | None,
    *,
    description: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    remainder = dict(extra or {})
    if source is None:
        embedded_source = remainder.pop("source", None)
        payload = {"source": embedded_source if isinstance(embedded_source, dict) else remainder}
        remainder = {}
    elif isinstance(source.get("source"), dict):
        payload = dict(source)
    else:
        payload = {"source": dict(source)}

    payload.update(remainder)
    if description is not None:
        payload["description"] = description
    return payload


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _request_source_set(request: dict[str, Any]) -> list[str]:
    values: list[str] = []

    source_name = request.get("source_name")
    if isinstance(source_name, str):
        values.append(source_name)

    join_source_name = request.get("join_source_name")
    if isinstance(join_source_name, str):
        values.append(join_source_name)

    sources = request.get("sources")
    if isinstance(sources, list):
        values.extend(
            source.get("name", "")
            for source in sources
            if isinstance(source, dict) and isinstance(source.get("name"), str)
        )

    join_path = request.get("join_path")
    if isinstance(join_path, dict):
        for key in ("base_source", "group_source"):
            value = join_path.get(key)
            if isinstance(value, str):
                values.append(value)
        edges = join_path.get("edges")
        if isinstance(edges, list):
            for edge in edges:
                if not isinstance(edge, dict):
                    continue
                for key in ("left_source", "right_source"):
                    value = edge.get(key)
                    if isinstance(value, str):
                        values.append(value)

    return _dedupe_strings(values)


def _split_resolved_sources(resolved_source: str | None) -> list[str]:
    if not resolved_source:
        return []
    return _dedupe_strings([part.strip() for part in resolved_source.split("⋈")])


def _build_explain_result(request: dict[str, Any], result: QueryResult) -> ExplainResult:
    join_path_payload = request.get("join_path")
    join_path: list[dict[str, Any]] = list(result.join_path)
    if isinstance(join_path_payload, dict):
        edges = join_path_payload.get("edges")
        if not join_path and isinstance(edges, list):
            join_path = [dict(edge) for edge in edges if isinstance(edge, dict)]

    source_set = (
        result.source_set
        or _split_resolved_sources(result.resolved_source)
        or _request_source_set(request)
    )
    if not join_path and len(source_set) > 1:
        join_path = [
            {"left_source": source_set[index], "right_source": source_set[index + 1]}
            for index in range(len(source_set) - 1)
        ]

    planner_mode = result.planner_mode or (
        "exact_spec" if result.exact_spec else result.decision_path
    )
    return ExplainResult.model_validate(
        {
            "source_set": source_set,
            "join_path": join_path,
            "planner_mode": planner_mode,
            "decision_path": result.decision_path,
            "plan_hash": result.plan_hash,
            "schema_revision": result.schema_revision,
            "validated": result.validated,
            "clarification_required": result.clarification_required,
            "rejection_reason": result.rejection_reason,
            "resolved_source": result.resolved_source,
            "resolved_column": result.resolved_column,
            "resolved_role": result.resolved_role,
            "confidence": result.confidence,
            "confidence_source": result.confidence_source,
            "deterministic_scope": result.deterministic_scope,
            "plan": result.plan,
            "explanation": result.explanation,
            "request_id": result.request_id,
        }
    )


class DecisionEngineClient:
    """
    Synchronous HTTP client for the Decision Engine API.

    Args:
        api_key: Your API key (de_live_... or de_test_...).
                 Falls back to ALGENTA_API_KEY or DE_API_KEY environment variable.
        base_url: API base URL. Override for self-hosted deployments.
        timeout: Request timeout in seconds.
        max_retries: Maximum retries on 429 and 5xx responses.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        resolved_key = (
            api_key or os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")
        )
        if not resolved_key:
            raise ValueError(
                "API key required. Pass api_key= or set ALGENTA_API_KEY environment variable."
            )
        self._api_key = resolved_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": "algenta-python/1.0.0",
            },
            timeout=timeout,
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Make HTTP request with retry logic."""
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.request(method, path, **kwargs)
                return self._handle_response(response)
            except (AuthenticationError, ValidationError, NotFoundError):
                raise
            except RateLimitError as exc:
                if attempt >= self._max_retries:
                    raise
                wait = exc.retry_after or (2**attempt * 5)
                time.sleep(wait)
                last_exc = exc
            except (ServerError, httpx.HTTPError) as exc:
                if attempt >= self._max_retries:
                    raise
                time.sleep(2**attempt)
                last_exc = exc
        raise last_exc or DecisionEngineError("Request failed after retries")

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Parse response and raise typed exceptions on errors."""
        try:
            body: dict[str, Any] = response.json()
        except Exception:
            body = {}

        if response.status_code in (200, 201, 202, 204):
            return body
        elif response.status_code == 401:
            raise AuthenticationError(
                body.get("error", {}).get("message", "Authentication failed"),
                status_code=401,
                response_body=body,
            )
        elif response.status_code == 404:
            raise NotFoundError(
                body.get("error", {}).get("message", "Not found"),
                status_code=404,
                response_body=body,
            )
        elif response.status_code == 422:
            raise ValidationError(
                body.get("error", {}).get("message", "Validation error"),
                status_code=422,
                response_body=body,
            )
        elif response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            raise RateLimitError(
                body.get("error", {}).get("message", "Rate limit exceeded"),
                retry_after=retry_after,
                status_code=429,
                response_body=body,
            )
        elif response.status_code >= 500:
            raise ServerError(
                body.get("error", {}).get("message", "Server error"),
                status_code=response.status_code,
                response_body=body,
            )
        else:
            raise DecisionEngineError(
                f"Unexpected status {response.status_code}",
                status_code=response.status_code,
                response_body=body,
            )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> DecisionEngineClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ─── Simulation Endpoints ─────────────────────────────────────────────────

    def simulate(self, **kwargs: Any) -> DecisionEnvelope:
        """
        Run a simulation and return a decision envelope.

        Args:
            mode: "auto" or "expert"
            scenario: For auto mode — {variables: {...}, objective: "..."}
            simulation: For expert mode — full simulation spec
            runs: Number of Monte Carlo iterations (default: 10000)
            seed: Random seed for reproducibility

        Returns:
            DecisionEnvelope with recommended_action, confidence, metrics, percentiles
        """
        data = self._request("POST", "/v1/simulate", json=_normalize_simulation_request(kwargs))
        return DecisionEnvelope.model_validate(data)

    def resolve(self, request: dict[str, Any] | None = None, **kwargs: Any) -> ResolveResult:
        """Resolve structured intent into an exact executable plan."""
        data = self._request("POST", "/v1/resolve", json=_merge_request_payload(request, kwargs))
        return ResolveResult.model_validate(data)

    def query(self, request: dict[str, Any] | None = None, **kwargs: Any) -> QueryResult:
        """Execute a deterministic query against registered or inline data sources."""
        data = self._request("POST", "/v1/query", json=_merge_request_payload(request, kwargs))
        return QueryResult.model_validate(data)

    def verify(self, request: dict[str, Any] | None = None, **kwargs: Any) -> VerifyResult:
        """Verify a structured query plan before execution."""
        data = self._request("POST", "/v1/verify", json=_merge_request_payload(request, kwargs))
        return VerifyResult.model_validate(data)

    def register_source(
        self,
        source: dict[str, Any] | None = None,
        *,
        description: str | None = None,
        **kwargs: Any,
    ) -> SourceRegistrationResult:
        """Register a source in the Decision Intelligence Layer."""
        payload = _normalize_source_registration_request(
            source,
            description=description,
            extra=kwargs,
        )
        data = self._request("POST", "/v1/sources/register", json=payload)
        return SourceRegistrationResult.model_validate(data)

    def refresh_source(self, dataset_id: str) -> SourceRegistrationResult:
        """Refresh a refreshable registered dataset from its saved origin."""
        data = self._request("POST", f"/v1/data/{dataset_id}/refresh")
        return SourceRegistrationResult.model_validate(data)

    def explain(self, request: dict[str, Any] | None = None, **kwargs: Any) -> ExplainResult:
        """Return a structured explanation of the planned deterministic query path."""
        merged_request = _merge_request_payload(request, kwargs)
        result = self.query(merged_request)
        return _build_explain_result(merged_request, result)

    def recommend(self, actions: Any, **kwargs: Any) -> dict[str, Any]:
        """Compare named actions and return a ranked recommendation."""
        return self._request(
            "POST", "/v1/recommend", json=_normalize_recommend_request(actions, **kwargs)
        )

    def score(
        self, request: dict[str, Any], scoring_weights: dict[str, float] | None = None
    ) -> dict[str, Any]:
        """Score a simulation with optional custom weights."""
        body: dict[str, Any] = {"request": request}
        if scoring_weights:
            body["scoring_weights"] = scoring_weights
        return self._request("POST", "/v1/score", json=body)

    def batch(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Run multiple simulations in one request."""
        data = self._request(
            "POST",
            "/v1/batch",
            json={"items": [_normalize_simulation_request(item) for item in items]},
        )
        return data.get("results", [])

    def compare(self, scenarios: Any, **kwargs: Any) -> dict[str, Any]:
        """Compare named scenarios side by side."""
        return self._request(
            "POST", "/v1/compare", json=_normalize_compare_request(scenarios, **kwargs)
        )

    # ─── Async Jobs ───────────────────────────────────────────────────────────

    def submit_job(
        self, request: dict[str, Any], callback_url: str | None = None
    ) -> dict[str, Any]:
        """Submit a simulation as an async job."""
        body: dict[str, Any] = {"request": _normalize_simulation_request(request)}
        if callback_url:
            body["callback_url"] = callback_url
        return self._request("POST", "/v1/jobs", json=body)

    def get_job(self, job_id: str) -> dict[str, Any]:
        """Poll job status."""
        return self._request("GET", f"/v1/jobs/{job_id}")

    def get_job_result(self, job_id: str) -> dict[str, Any]:
        """Get job result (returns dict — may include full DecisionEnvelope)."""
        return self._request("GET", f"/v1/jobs/{job_id}/result")

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        """Cancel a queued or running job."""
        return self._request("POST", f"/v1/jobs/{job_id}/cancel")

    def poll_job(
        self, job_id: str, timeout: float = 300.0, poll_interval: float = 2.0
    ) -> dict[str, Any]:
        """
        Poll a job until it completes or times out.

        Args:
            job_id: The job ID to poll.
            timeout: Maximum seconds to wait (default: 300).
            poll_interval: Seconds between polls (default: 2).

        Returns:
            Job result dict when completed.

        Raises:
            DecisionEngineError: If job fails or times out.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            status = self.get_job(job_id)
            if status["status"] == "completed":
                return self.get_job_result(job_id)
            elif status["status"] in ("failed", "cancelled"):
                error_message = status.get("error_message")
                raise DecisionEngineError(
                    f"Job {job_id} ended with status '{status['status']}': "
                    f"{error_message}"
                )
            time.sleep(poll_interval)
        raise DecisionEngineError(f"Job {job_id} did not complete within {timeout} seconds")

    # ─── Account Endpoints ────────────────────────────────────────────────────

    def me(self) -> dict[str, Any]:
        """Get current user and organization info."""
        return self._request("GET", "/v1/me")

    def usage(self) -> UsageInfo:
        """Get usage summary for current billing period."""
        data = self._request("GET", "/v1/usage")
        return UsageInfo.model_validate(data)

    def limits(self) -> dict[str, Any]:
        """Get plan-based limits."""
        return self._request("GET", "/v1/limits")

    def list_api_keys(self) -> list[APIKeyInfo]:
        """List all active API keys."""
        data = self._request("GET", "/v1/api-keys")
        return [APIKeyInfo.model_validate(k) for k in data]

    def create_api_key(
        self, label: str | None = None, *, name: str | None = None
    ) -> dict[str, Any]:
        """Create a new API key. Raw key shown once in response."""
        resolved_label = label or name
        if not resolved_label:
            raise ValueError("create_api_key() requires label= or name=")
        return self._request("POST", "/v1/api-keys", json={"label": resolved_label})

    def revoke_api_key(self, key_id: str) -> dict[str, Any]:
        """Revoke an API key."""
        return self._request("DELETE", f"/v1/api-keys/{key_id}")

    def distributions(self) -> list[dict[str, Any]]:
        """List supported distribution types."""
        return self._request("GET", "/v1/distributions")  # type: ignore[return-value]

    def templates(self) -> list[dict[str, Any]]:
        """List built-in simulation templates."""
        return self._request("GET", "/v1/templates")  # type: ignore[return-value]

    def health(self) -> dict[str, Any]:
        """Check API health."""
        return self._request("GET", "/v1/health")

    def version(self) -> dict[str, Any]:
        """Get API and engine version."""
        return self._request("GET", "/v1/version")
