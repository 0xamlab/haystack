from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_DOC_EXPECTATIONS: dict[str, tuple[str, ...]] = {
    "apps/docs/docs/index.md": (
        "/v1/capabilities/route",
        "`algenta_managed` routes can execute through Algenta",
        "`client_managed` routes",
    ),
    "apps/docs/docs/api-reference/index.md": (
        "Cloud Managed",
        "`self_hosted` and `air_gapped`",
        "Private profiles do not silently fall back to Algenta cloud.",
        "self-hosted operator",
    ),
    "apps/docs/docs/api-reference/simulate.md": (
        "This curl example is the Cloud Managed path.",
        "`self_hosted`",
        "`air_gapped`",
        "self-hosted operator",
        'ALGENTA_API_KEY="${ALGENTA_API_KEY:-${DE_API_KEY:-}}"',
        'ALGENTA_BASE_URL="${ALGENTA_BASE_URL:-${DE_BASE_URL:-${ALGENTA_API_URL:-https://api.algenta.ai}}}"',
    ),
    "apps/docs/docs/api-reference/multi-hop-joins.md": (
        "Cloud Managed defaults",
        "`self_hosted`",
        "`base_url` / `baseUrl`",
        "self-hosted operator",
        'ALGENTA_API_KEY="${ALGENTA_API_KEY:-${DE_API_KEY:-}}"',
        'ALGENTA_BASE_URL="${ALGENTA_BASE_URL:-${DE_BASE_URL:-${ALGENTA_API_URL:-https://api.algenta.ai}}}"',
    ),
    "apps/docs/docs/api-reference/capability-plane.md": (
        "Cloud Managed",
        "`self_hosted` and `air_gapped`",
        "Private profiles do not silently fall back to Algenta cloud.",
        "/v1/capabilities/route",
        "/v1/capabilities/execute",
        "examples/capability-plane/README.md",
        "examples/langgraph/capability_router.py",
    ),
    "apps/docs/docs/direct-api-client.md": (
        "Cloud Managed",
        "`self_hosted` and `air_gapped`",
        "Private profiles fail closed and do not silently fall back to Algenta cloud.",
        "self-hosted operator",
        'AlgentaClient(api_key=..., base_url="http://localhost:8000")',
        'new AlgentaClient({ apiKey: ..., baseUrl:',
        "client.route_capabilities(...)",
        "client.routeCapabilities({ ... })",
        "examples/capability-plane/",
    ),
    "apps/docs/docs/connect-register-sources.md": (
        "This API-mode example is the Cloud Managed path.",
        "`self_hosted`",
        "`air_gapped`",
        "private profiles fail closed",
        'Runtime(mode="api", api_key=..., base_url="http://localhost:8000")',
    ),
    "apps/docs/docs/resolve.md": (
        "This API-mode snippet is the Cloud Managed path.",
        "`self_hosted`",
        "`air_gapped`",
        "fail closed",
    ),
    "apps/docs/docs/integrations/langgraph.md": (
        "Cloud Managed",
        "`self_hosted` and `air_gapped`",
        "Private profiles do not silently fall back to Algenta cloud.",
        "The direct-client snippet above is the Cloud Managed path.",
        'AlgentaClient(api_key=..., base_url="http://localhost:8000")',
        "client.route_capabilities(",
        "route_capability_for_incident",
        "examples/langgraph/capability_router.py",
    ),
}


@pytest.mark.parametrize(
    ("relative_path", "required_snippets"),
    list(_DOC_EXPECTATIONS.items()),
)
def test_service_docs_call_out_cloud_managed_and_private_profile_boundaries(
    relative_path: str,
    required_snippets: tuple[str, ...],
) -> None:
    text = (ROOT / relative_path).read_text()
    for snippet in required_snippets:
        assert snippet in text
