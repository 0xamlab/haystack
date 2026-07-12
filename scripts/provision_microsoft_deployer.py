#!/usr/bin/env python3
"""One-time bootstrap: create + admin-consent the Algenta "deployer" public-client app.

The turnkey deployer (``deploy_microsoft_turnkey.py``) signs in interactively (device code)
as this dedicated Entra public-client app. The az CLI's own Graph token can NOT publish to
the org app catalog (its scope set is fixed and lacks ``AppCatalog.ReadWrite.All``), so we
stand up a separate app whose delegated scopes ARE pre-consented — then the runtime sign-in
never hits a consent wall, it just authenticates.

Run this ONCE. It uses the existing az delegated Graph token (which holds
Application.ReadWrite.All + AppRoleAssignment.ReadWrite.All + DelegatedPermissionGrant.ReadWrite.All)::

    az login   # as a Global/Cloud Application Administrator in the thyn.ai tenant
    python scripts/provision_microsoft_deployer.py

It prints the deployer client id; export it for the deployer::

    export ALGENTA_MS_DEPLOYER_CLIENT_ID=<printed id>

Idempotent: re-running reuses the existing app/SP (matched by displayName) and re-asserts the
admin-consent grant.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Optional

import requests

GRAPH = "https://graph.microsoft.com/v1.0"
GRAPH_APP_ID = "00000003-0000-0000-c000-000000000000"  # Microsoft Graph resource
DEFAULT_DISPLAY_NAME = "Algenta Microsoft Deployer"

# Delegated Graph scopes the deployer needs, granted + admin-consented here.
#   AppCatalog.ReadWrite.All           publish/update/list org-catalog Teams+Copilot apps (admin-consent required)
#   TeamsAppInstallation.ReadWriteForUser  install the app for the signed-in user's own scope
#   User.Read                          resolve the signed-in user (/me) for the per-user install
# Least-privilege: the deployer never calls Graph /applications, so Application.ReadWrite.All is
# deliberately NOT granted (the OAuth-vault path uses a separate Teams Developer Portal token).
DEPLOYER_SCOPES = [
    "AppCatalog.ReadWrite.All",
    "TeamsAppInstallation.ReadWriteForUser",
    "User.Read",
]


def az_graph_token() -> str:
    try:
        out = subprocess.run(
            ["az", "account", "get-access-token", "--resource", "https://graph.microsoft.com", "-o", "json"],
            check=True, capture_output=True, text=True,
        )
    except FileNotFoundError:
        sys.exit("az CLI not found — install it and `az login` first.")
    except subprocess.CalledProcessError as e:
        sys.exit(f"az account get-access-token failed:\n{e.stderr}")
    return json.loads(out.stdout)["accessToken"]


class Graph:
    def __init__(self, token: str):
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})

    def req(self, method: str, path: str, ok=(200, 201, 204), **kw):
        url = path if path.startswith("http") else f"{GRAPH}{path}"
        r = self.s.request(method, url, **kw)
        if r.status_code not in ok:
            raise SystemExit(f"{method} {path} -> {r.status_code}: {r.text}")
        return r.json() if r.content and r.status_code != 204 else {}


def resolve_graph_sp_and_scope_ids(g: Graph) -> tuple[str, list[dict]]:
    """Return (graph service-principal id, [{'id','type':'Scope'}...]) for DEPLOYER_SCOPES."""
    sp = g.req("GET", f"/servicePrincipals?$filter=appId eq '{GRAPH_APP_ID}'")
    sp_list = sp.get("value", [])
    if not sp_list:
        raise SystemExit("Microsoft Graph service principal not found in tenant.")
    graph_sp = sp_list[0]
    by_value = {s["value"]: s["id"] for s in graph_sp.get("oauth2PermissionScopes", [])}
    resources = []
    for name in DEPLOYER_SCOPES:
        if name not in by_value:
            raise SystemExit(f"Delegated scope '{name}' not found on Microsoft Graph — check the name.")
        resources.append({"id": by_value[name], "type": "Scope"})
    return graph_sp["id"], resources


def find_app(g: Graph, display_name: str) -> Optional[dict]:
    res = g.req("GET", f"/applications?$filter=displayName eq '{display_name}'")
    vals = res.get("value", [])
    return vals[0] if vals else None


def find_sp(g: Graph, app_id: str) -> Optional[dict]:
    res = g.req("GET", f"/servicePrincipals?$filter=appId eq '{app_id}'")
    vals = res.get("value", [])
    return vals[0] if vals else None


def main() -> int:
    ap = argparse.ArgumentParser(description="Provision + admin-consent the Algenta deployer app.")
    ap.add_argument("--display-name", default=DEFAULT_DISPLAY_NAME)
    args = ap.parse_args()

    g = Graph(az_graph_token())
    graph_sp_id, resources = resolve_graph_sp_and_scope_ids(g)

    required_resource_access = [{"resourceAppId": GRAPH_APP_ID, "resourceAccess": resources}]

    app = find_app(g, args.display_name)
    if app:
        print(f"reusing existing app '{args.display_name}' (appId={app['appId']})")
        g.req("PATCH", f"/applications/{app['id']}", json={
            "isFallbackPublicClient": True,
            "publicClient": {"redirectUris": ["http://localhost"]},
            "requiredResourceAccess": required_resource_access,
        })
    else:
        app = g.req("POST", "/applications", json={
            "displayName": args.display_name,
            "signInAudience": "AzureADMyOrg",
            "isFallbackPublicClient": True,  # "Allow public client flows" — required for device-code
            "publicClient": {"redirectUris": ["http://localhost"]},  # only needed for interactive-browser
            "requiredResourceAccess": required_resource_access,
        })
        print(f"created app '{args.display_name}' (appId={app['appId']})")

    app_client_id = app["appId"]

    sp = find_sp(g, app_client_id)
    if not sp:
        sp = g.req("POST", "/servicePrincipals", json={"appId": app_client_id})
        print(f"created service principal (id={sp['id']})")
    else:
        print(f"reusing service principal (id={sp['id']})")

    # Admin consent = a tenant-wide (AllPrincipals) delegated grant for the scopes.
    existing = g.req(
        "GET",
        f"/oauth2PermissionGrants?$filter=clientId eq '{sp['id']}' and resourceId eq '{graph_sp_id}'",
    ).get("value", [])
    scope_str = " ".join(DEPLOYER_SCOPES)
    if existing:
        g.req("PATCH", f"/oauth2PermissionGrants/{existing[0]['id']}", json={"scope": scope_str})
        print("updated admin-consent grant")
    else:
        g.req("POST", "/oauth2PermissionGrants", json={
            "clientId": sp["id"],
            "consentType": "AllPrincipals",
            "resourceId": graph_sp_id,
            "scope": scope_str,
        })
        print("granted admin consent (AllPrincipals)")

    print("\nDeployer app ready. Scopes admin-consented:")
    for s in DEPLOYER_SCOPES:
        print(f"  - {s}")
    print("\nNext:")
    print(f"  export ALGENTA_MS_DEPLOYER_CLIENT_ID={app_client_id}")
    print("  python scripts/deploy_microsoft_turnkey.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
