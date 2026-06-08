from __future__ import annotations

import time
from typing import Any

from apps.api_server.services.egress_guard import (
    EgressPolicyDeniedError,
    async_http_request,
    audit_context_from_config,
)
from .tester_common import (
    ConnectorTestOutcome,
    elapsed_ms,
    failure_outcome,
    success_outcome,
)


async def test_file_connector(config: dict[str, Any]) -> ConnectorTestOutcome:
    """Test local/inline file connectivity by parsing the configured payload."""
    from apps.api_server.connectors.file_connector import FileConnector

    started_at = time.perf_counter()
    try:
        connector = FileConnector(config)
        data = await connector.fetch_data()
        source = config.get("file_path") or "inline payload"
        return success_outcome(
            f"File connector parsed {len(data)} records from {source}",
            elapsed_ms(started_at),
        )
    except Exception as exc:
        return failure_outcome(
            message=f"File connector failed: {exc}",
            latency_ms=elapsed_ms(started_at),
            exception=exc,
        )


async def test_rest_api_connector(config: dict[str, Any]) -> ConnectorTestOutcome:
    """Test REST API reachability via httpx."""
    base_url = config.get("base_url") or config.get("url", "")
    if not base_url:
        return failure_outcome(
            message="REST API: 'base_url' is required in connector config",
            latency_ms=0,
            error_type="invalid_config",
            recoverable=True,
        )

    auth_type = str(config.get("auth_type", "none") or "none")
    headers: dict[str, str] = {}

    if auth_type == "bearer":
        token = str(config.get("api_key") or config.get("token") or "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
    elif auth_type == "api_key":
        header_name = str(config.get("api_key_header", "X-API-Key") or "X-API-Key")
        api_key = str(config.get("api_key") or "")
        if api_key:
            headers[header_name] = api_key
    elif auth_type == "basic":
        import base64

        user = str(config.get("username") or "")
        password = str(config.get("password") or "")
        encoded = base64.b64encode(f"{user}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"

    health_path = str(config.get("health_path", "") or "")
    test_url = base_url.rstrip("/") + ("/" + health_path.lstrip("/") if health_path else "")

    started_at = time.perf_counter()
    try:
        response = await async_http_request(
            method="GET",
            url=test_url,
            surface="connector_rest_test",
            explicit_configured=True,
            egress_class="customer_connector",
            audit_context=audit_context_from_config(config),
            client_kwargs={"timeout": 8, "follow_redirects": True},
            headers=headers,
        )
        if 200 <= response.status_code < 300:
            return success_outcome(
                f"REST API reachable ({response.status_code}) — {test_url}",
                elapsed_ms(started_at),
            )
        return failure_outcome(
            message=f"REST API returned {response.status_code}: {test_url}",
            latency_ms=elapsed_ms(started_at),
            status_code=response.status_code,
        )
    except EgressPolicyDeniedError as exc:
        return failure_outcome(
            message=f"REST API blocked by privacy policy: {exc.decision.reason}",
            latency_ms=elapsed_ms(started_at),
            error_type=exc.code,
            recoverable=False,
        )
    except Exception as exc:
        return failure_outcome(
            message=f"REST API unreachable: {exc}",
            latency_ms=elapsed_ms(started_at),
            exception=exc,
        )
