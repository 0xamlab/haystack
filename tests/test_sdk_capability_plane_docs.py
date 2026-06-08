from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

_DOC_EXPECTATIONS: dict[str, tuple[str, ...]] = {
    "apps/docs/docs/sdks/python.md": (
        "## Unified capability plane",
        "customer-agnostic",
        "client.list_capability_providers()",
        "client.route_capabilities(",
        "client.execute_capability(",
        "client.list_skills()",
        "client.list_mcp_providers()",
        "start_capability_authorization(...)",
        "`client_managed` capabilities",
        "`algenta_managed` capabilities remain",
    ),
    "apps/docs/docs/sdks/typescript.md": (
        "## Unified capability plane",
        "customer-agnostic",
        "client.listCapabilityProviders()",
        "client.routeCapabilities(",
        "client.executeCapability(",
        "client.listSkills()",
        "client.listMcpProviders()",
        "startCapabilityAuthorization(...)",
        "`client_managed` capabilities",
        "`algenta_managed` capabilities remain",
    ),
}


@pytest.mark.parametrize(
    ("relative_path", "required_snippets"),
    list(_DOC_EXPECTATIONS.items()),
)
def test_sdk_docs_cover_unified_capability_plane_surface(
    relative_path: str,
    required_snippets: tuple[str, ...],
) -> None:
    text = (ROOT / relative_path).read_text()
    for snippet in required_snippets:
        assert snippet in text
