"""
Async Decision Engine API client for use with asyncio.

Usage:
    import asyncio
    from decision_engine import AsyncDecisionEngineClient

    async def main():
        async with AsyncDecisionEngineClient(api_key="de_live_...") as client:
            result = await client.simulate(
                mode="auto",
                scenario={
                    "variables": {"revenue": {"low": 80000, "high": 200000}},
                    "objective": "maximize_net_value",
                },
            )
            print(result.recommended_action)

    asyncio.run(main())
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from .client import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    _build_explain_result,
    _merge_request_payload,
    _normalize_compare_request,
    _normalize_recommend_request,
    _normalize_simulation_request,
    _normalize_source_registration_request,
)
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


class AsyncDecisionEngineClient:
    """Async HTTP client for the Decision Engine API."""

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
            raise ValueError("API key required. Pass api_key= or set ALGENTA_API_KEY env var.")
        self._api_key = resolved_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": "decision-engine-python/0.1.0",
            },
            timeout=timeout,
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.request(method, path, **kwargs)
                return self._handle_response(response)
            except (AuthenticationError, ValidationError, NotFoundError):
                raise
            except RateLimitError as exc:
                if attempt >= self._max_retries:
                    raise
                await asyncio.sleep(exc.retry_after or (2**attempt * 5))
                last_exc = exc
            except (ServerError, httpx.HTTPError) as exc:
                if attempt >= self._max_retries:
                    raise
                await asyncio.sleep(2**attempt)
                last_exc = exc
        raise last_exc or DecisionEngineError("Request failed after retries")

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        try:
            body: dict[str, Any] = response.json()
        except Exception:
            body = {}
        if response.status_code in (200, 201, 202, 204):
            return body
        elif response.status_code == 401:
            raise AuthenticationError(
                body.get("error", {}).get("message", "Auth failed"),
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

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> AsyncDecisionEngineClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()

    async def simulate(self, **kwargs: Any) -> DecisionEnvelope:
        data = await self._request(
            "POST", "/v1/simulate", json=_normalize_simulation_request(kwargs)
        )
        return DecisionEnvelope.model_validate(data)

    async def resolve(
        self, request: dict[str, Any] | None = None, **kwargs: Any
    ) -> ResolveResult:
        data = await self._request(
            "POST", "/v1/resolve", json=_merge_request_payload(request, kwargs)
        )
        return ResolveResult.model_validate(data)

    async def query(self, request: dict[str, Any] | None = None, **kwargs: Any) -> QueryResult:
        data = await self._request(
            "POST", "/v1/query", json=_merge_request_payload(request, kwargs)
        )
        return QueryResult.model_validate(data)

    async def verify(self, request: dict[str, Any] | None = None, **kwargs: Any) -> VerifyResult:
        data = await self._request(
            "POST", "/v1/verify", json=_merge_request_payload(request, kwargs)
        )
        return VerifyResult.model_validate(data)

    async def register_source(
        self,
        source: dict[str, Any] | None = None,
        *,
        description: str | None = None,
        **kwargs: Any,
    ) -> SourceRegistrationResult:
        payload = _normalize_source_registration_request(
            source,
            description=description,
            extra=kwargs,
        )
        data = await self._request("POST", "/v1/sources/register", json=payload)
        return SourceRegistrationResult.model_validate(data)

    async def refresh_source(self, dataset_id: str) -> SourceRegistrationResult:
        data = await self._request("POST", f"/v1/data/{dataset_id}/refresh")
        return SourceRegistrationResult.model_validate(data)

    async def explain(self, request: dict[str, Any] | None = None, **kwargs: Any) -> ExplainResult:
        merged_request = _merge_request_payload(request, kwargs)
        result = await self.query(merged_request)
        return _build_explain_result(merged_request, result)

    async def recommend(self, actions: Any, **kwargs: Any) -> dict[str, Any]:
        return await self._request(
            "POST", "/v1/recommend", json=_normalize_recommend_request(actions, **kwargs)
        )

    async def score(
        self, request: dict[str, Any], scoring_weights: dict[str, float] | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"request": request}
        if scoring_weights:
            body["scoring_weights"] = scoring_weights
        return await self._request("POST", "/v1/score", json=body)

    async def batch(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        data = await self._request(
            "POST",
            "/v1/batch",
            json={"items": [_normalize_simulation_request(item) for item in items]},
        )
        return data.get("results", [])

    async def compare(self, scenarios: Any, **kwargs: Any) -> dict[str, Any]:
        return await self._request(
            "POST", "/v1/compare", json=_normalize_compare_request(scenarios, **kwargs)
        )

    async def submit_job(
        self, request: dict[str, Any], callback_url: str | None = None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"request": _normalize_simulation_request(request)}
        if callback_url:
            body["callback_url"] = callback_url
        return await self._request("POST", "/v1/jobs", json=body)

    async def get_job(self, job_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/v1/jobs/{job_id}")

    async def get_job_result(self, job_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/v1/jobs/{job_id}/result")

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/v1/jobs/{job_id}/cancel")

    async def poll_job(
        self, job_id: str, timeout: float = 300.0, poll_interval: float = 2.0
    ) -> dict[str, Any]:
        import time

        deadline = time.time() + timeout
        while time.time() < deadline:
            status = await self.get_job(job_id)
            if status["status"] == "completed":
                return await self.get_job_result(job_id)
            elif status["status"] in ("failed", "cancelled"):
                error_message = status.get("error_message")
                raise DecisionEngineError(
                    f"Job {job_id} ended with status '{status['status']}': "
                    f"{error_message}"
                )
            await asyncio.sleep(poll_interval)
        raise DecisionEngineError(f"Job {job_id} timed out after {timeout}s")

    async def me(self) -> dict[str, Any]:
        return await self._request("GET", "/v1/me")

    async def usage(self) -> UsageInfo:
        data = await self._request("GET", "/v1/usage")
        return UsageInfo.model_validate(data)

    async def limits(self) -> dict[str, Any]:
        return await self._request("GET", "/v1/limits")

    async def list_api_keys(self) -> list[APIKeyInfo]:
        data = await self._request("GET", "/v1/api-keys")
        return [APIKeyInfo.model_validate(k) for k in data]

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/v1/health")

    async def version(self) -> dict[str, Any]:
        return await self._request("GET", "/v1/version")
