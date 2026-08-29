"""RFC 9728 OAuth 2.0 Protected Resource Metadata -- for Algenta's MCP server.

Publishes the well-known discovery document a compliant OAuth-aware MCP client fetches after
receiving a ``401`` from ``POST /mcp`` (or the deprecated ``/mcp/sse`` + ``/mcp/messages`` lane):
which authorization server(s) issue tokens this gateway will actually accept for the MCP resource.
See ``apps/mcp_server/transports/http_sse.py`` for the matching ``WWW-Authenticate:
resource_metadata="..."`` challenge these routes are advertised through.

MCP is mounted at exactly one path (``/mcp``), so one metadata document covers it; it is published
at both RFC 9728 locations for client compatibility:

  * ``GET /.well-known/oauth-protected-resource``       -- the bare, origin-rooted location.
  * ``GET /.well-known/oauth-protected-resource/mcp``    -- RFC 9728 section 3.1's path-appended
    location for a protected resource whose identifier has a path component (``{base_url}/mcp``),
    which is what the ``WWW-Authenticate`` challenge on ``/mcp`` actually points at.

Honesty discipline (this repo's own "never advertise what isn't real" pattern -- see
``GET /.well-known/jwks.json`` in ``routers/license.py``, also unauthenticated and
``include_in_schema=False``): the document is served ONLY when this deployment actually has an
authorization server configured (Microsoft Entra ID and/or generic OIDC --
``services/entra_auth.py`` / ``services/oidc_auth.py``). With neither configured, both routes
404 -- there is no authorization server to discover, and this gateway's bearer-key-only posture is
unaffected.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from apps.api_server.services import entra_auth, oidc_auth
from apps.api_server.services.public_url_policy import (
    request_origin_base_url,
    resolve_api_public_base_url,
)

router = APIRouter(tags=["oauth-protected-resource"])

# The one resource this gateway's OAuth-verified bearer path actually protects today (see
# apps/mcp_server/transports/http_sse.py's tools/call challenge). Not the whole API: Entra/OIDC
# verification is wired at the API-wide auth dependency, but MCP is the surface this Track builds
# RFC 9728 discovery for.
_MCP_RESOURCE_PATH = "/mcp"
_RESOURCE_DOCUMENTATION_URL = "https://docs.algenta.ai/sdk/mcp"


def _configured_authorization_servers() -> list[str]:
    """Every issuer URL this deployment's bearer verification actually trusts, or empty."""
    servers = list(entra_auth.entra_authorization_server_issuers())
    oidc_issuer = oidc_auth.oidc_authorization_server_issuer()
    if oidc_issuer and oidc_issuer not in servers:
        servers.append(oidc_issuer)
    return servers


def _metadata_document(*, resource_url: str, authorization_servers: list[str]) -> dict[str, object]:
    return {
        "resource": resource_url,
        "authorization_servers": authorization_servers,
        # This gateway reads the bearer only from the Authorization header (never a body or query
        # parameter) on every credentialed surface -- see middleware/auth.py:get_current_org.
        "bearer_methods_supported": ["header"],
        "resource_name": "Algenta MCP Server",
        "resource_documentation": _RESOURCE_DOCUMENTATION_URL,
    }


def _resource_base_url(request: Request) -> str:
    return resolve_api_public_base_url(request_origin=request_origin_base_url(request))


@router.get("/.well-known/oauth-protected-resource", include_in_schema=False)
async def oauth_protected_resource_root(request: Request) -> JSONResponse:
    """RFC 9728 metadata for the deployment's MCP endpoint, at the bare well-known location."""
    authorization_servers = _configured_authorization_servers()
    if not authorization_servers:
        raise HTTPException(status_code=404, detail="oauth authorization server not configured")
    resource_url = f"{_resource_base_url(request)}{_MCP_RESOURCE_PATH}"
    return JSONResponse(
        _metadata_document(resource_url=resource_url, authorization_servers=authorization_servers)
    )


@router.get("/.well-known/oauth-protected-resource/mcp", include_in_schema=False)
async def oauth_protected_resource_mcp(request: Request) -> JSONResponse:
    """RFC 9728 metadata for the deployment's MCP endpoint, at its path-appended location -- the
    URL the ``WWW-Authenticate: resource_metadata="..."`` challenge on ``/mcp`` actually names."""
    authorization_servers = _configured_authorization_servers()
    if not authorization_servers:
        raise HTTPException(status_code=404, detail="oauth authorization server not configured")
    resource_url = f"{_resource_base_url(request)}{_MCP_RESOURCE_PATH}"
    return JSONResponse(
        _metadata_document(resource_url=resource_url, authorization_servers=authorization_servers)
    )
