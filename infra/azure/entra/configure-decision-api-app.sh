#!/usr/bin/env bash
#
# configure-decision-api-app.sh — idempotently expose the Algenta Decision API on an Entra
# app registration AND wire it for Office / Teams / Copilot single sign-on (SSO).
#
# What it does (all additive — it never changes signInAudience, so an app that also serves
# consumer sign-in keeps working):
#   * Application ID URI      -> api://<APP_ID>               (the audience the gateway requires)
#   * requestedAccessTokenVersion -> 2                        (the gateway accepts v2 tokens only)
#   * delegated scope         -> Decisions.Run                (signed-in employees; admin+user consent)
#   * delegated scope         -> access_as_user               (REQUIRED literal name for Office/Teams SSO;
#                                                              this is the scope Excel/Teams/Copilot request)
#   * app role (Application)  -> Decisions.Service            (service / managed identities)
#   * preAuthorizedApplications -> the well-known Microsoft first-party client GUIDs (Office, Teams,
#       Microsoft 365 app, Outlook, and the Copilot enterprise token store) — so those clients get a
#       Decision-API token via SSO WITHOUT a consent prompt. Each is pre-authorized for both delegated
#       scopes (access_as_user + Decisions.Run).
#
# Idempotent: re-running is a no-op once each piece is present (scopes/roles matched by value not id;
# pre-authorized apps matched by appId; scope ids are preserved once created).
#
# Prereqs: az CLI logged in as an OWNER of the app (and a Global/Application/Cloud-App Admin to
# grant tenant-wide admin consent). python3 is used only to merge JSON.
#
# Usage:
#   ./configure-decision-api-app.sh                 # defaults to the Thyn Accounts app below
#   APP_ID=<guid> ./configure-decision-api-app.sh   # a different app registration
#   CONSENT=1 ./configure-decision-api-app.sh        # also grant tenant-wide admin consent
#
# After it runs it prints the exact ALGENTA_ENTRA_AUDIENCE / ALGENTA_ENTRA_TENANT_ID to set on the
# gateway (see entra-sso.md "Configure the gateway's Entra settings"). NOTE the tenant: the gateway
# must validate the tenant where THIS app + its users live — not necessarily the Azure subscription's
# home tenant. Confirm the topology before flipping the gateway's Entra settings on.
#
# Microsoft references for the pre-authorized client GUIDs (verified 2026-07):
#   Office add-in SSO:  https://learn.microsoft.com/office/dev/add-ins/develop/register-sso-add-in-aad-v2
#   Teams tab SSO:      https://learn.microsoft.com/microsoftteams/platform/tabs/how-to/authentication/tab-sso-register-aad
#   Copilot API plugin: https://learn.microsoft.com/microsoft-365/copilot/extensibility/api-plugin-authentication
set -euo pipefail

APP_ID="${APP_ID:-3983990d-e9b5-4866-9a43-d52d6e0c20c3}"   # Thyn Accounts Sign-In (Decision API app)
SCOPE_NAME="${SCOPE_NAME:-Decisions.Run}"                  # delegated (employee) scope
SSO_SCOPE_NAME="${SSO_SCOPE_NAME:-access_as_user}"         # delegated scope Office/Teams/Copilot request
ROLE_NAME="${ROLE_NAME:-Decisions.Service}"                # app role (service/managed identities)
CONSENT="${CONSENT:-0}"

command -v az >/dev/null || { echo "az CLI not found" >&2; exit 127; }
command -v python3 >/dev/null || { echo "python3 not found" >&2; exit 127; }

AUDIENCE="api://${APP_ID}"
OBJ_ID="$(az ad app show --id "$APP_ID" --query id -o tsv)"
TENANT_ID="$(az account show --query tenantId -o tsv)"
echo "app=$APP_ID objectId=$OBJ_ID tenant=$TENANT_ID audience=$AUDIENCE"

CURRENT="$(az ad app show --id "$APP_ID" -o json)"

# Merge the desired API surface into the current app object (additive; stable ids preserved).
# (Bodies are written to temp files rather than $(...heredoc...) — the latter breaks on macOS bash 3.2
#  when several appear in one script.)
PATCH1="$(mktemp)"; PATCH2="$(mktemp)"; PATCH3="$(mktemp)"
trap 'rm -f "$PATCH1" "$PATCH2" "$PATCH3"' EXIT
APP_ID="$APP_ID" AUDIENCE="$AUDIENCE" SCOPE_NAME="$SCOPE_NAME" \
  SSO_SCOPE_NAME="$SSO_SCOPE_NAME" ROLE_NAME="$ROLE_NAME" \
  python3 - "$CURRENT" > "$PATCH1" <<'PY'
import json, os, sys, uuid
cur = json.loads(sys.argv[1])
audience = os.environ["AUDIENCE"]
scope_name, sso_scope_name = os.environ["SCOPE_NAME"], os.environ["SSO_SCOPE_NAME"]
role_name = os.environ["ROLE_NAME"]

api = cur.get("api") or {}
scopes = list(api.get("oauth2PermissionScopes") or [])

def ensure_scope(value, admin_dn, admin_desc, user_dn, user_desc):
    for s in scopes:
        if s.get("value") == value:
            return s["id"]                       # keep the existing (stable) id
    sid = str(uuid.uuid4())
    scopes.append({
        "id": sid,
        "value": value,
        "type": "User",                          # admin + user consentable
        "isEnabled": True,
        "adminConsentDisplayName": admin_dn,
        "adminConsentDescription": admin_desc,
        "userConsentDisplayName": user_dn,
        "userConsentDescription": user_desc,
    })
    return sid

run_id = ensure_scope(
    scope_name,
    f"Access the Algenta Decision API ({scope_name})",
    "Allow the app to call the Algenta Decision API on behalf of the signed-in user.",
    "Access the Algenta Decision API",
    "Allow this app to make decisions on your behalf via the Algenta Decision API.",
)
# access_as_user — the literal scope name Office/Teams/Copilot SSO request. Its display strings are
# what the (rare) consent prompt would show; pre-authorization normally suppresses that prompt.
sso_id = ensure_scope(
    sso_scope_name,
    "Access the Algenta Decision API as the signed-in user",
    "Allow Office, Teams, and Copilot to call the Algenta Decision API as the signed-in user.",
    "Access the Algenta Decision API on your behalf",
    "Allow Office, Teams, and Copilot to make decisions on your behalf via the Algenta Decision API.",
)
api["oauth2PermissionScopes"] = scopes
api["requestedAccessTokenVersion"] = 2

# Pre-authorize the well-known Microsoft first-party clients for BOTH delegated scopes so SSO is
# consent-free. GUIDs are Microsoft-published (see the doc links in the header comment).
FIRST_PARTY_CLIENTS = [
    "ea5a67f6-b6f3-4338-b240-c655ddc3cc8e",  # Microsoft Office (umbrella: all Office endpoints)
    "d3590ed6-52b3-4102-aeff-aad2292ab01c",  # Microsoft 365 mobile / Office / Outlook desktop
    "93d53678-613d-4013-afc1-62e9e444a0a5",  # Office on the web
    "bc59ab01-8403-45c6-8796-ac3ef710b3e3",  # Outlook on the web
    "27922004-5251-4030-b22d-91ecd9a37ea4",  # Outlook mobile
    "4765445b-32c6-49b0-83e6-1d93765276ca",  # Microsoft 365 web
    "0ec893e0-5785-4de6-99da-4ed124e5296c",  # Microsoft 365 desktop
    "1fec8e78-bce4-4aaf-ab1b-5451cc387264",  # Microsoft Teams desktop + mobile
    "5e3ce6c0-2b1f-4285-8d4b-75ee78787346",  # Microsoft Teams web
    "ab3be6b7-f5df-413d-ac2d-abf1e3fd9c0b",  # Copilot / Microsoft enterprise token store (declarative-agent API plugin)
]
# NOTE: preAuthorizedApplications is applied in a SECOND PATCH below — Graph rejects pre-auth entries
# whose delegatedPermissionIds reference scopes that aren't ALREADY stored (the scopes added in this
# same PATCH don't count), so scopes must land first. FIRST_PARTY_CLIENTS is consumed there.
_ = FIRST_PARTY_CLIENTS  # referenced in phase 2 (below), kept here as the single source of truth

roles = list(cur.get("appRoles") or [])
if not any((r.get("value") == role_name) for r in roles):
    roles.append({
        "id": str(uuid.uuid4()),
        "value": role_name,
        "allowedMemberTypes": ["Application"],  # service principals / managed identities
        "isEnabled": True,
        "displayName": "Call the Algenta Decision API (service identity)",
        "description": "Allow an application or managed identity to call the Algenta Decision API app-only.",
    })

# Application ID URI — add ours if absent (never drop an existing one).
uris = list(cur.get("identifierUris") or [])
if audience not in uris:
    uris.append(audience)

print(json.dumps({"identifierUris": uris, "api": api, "appRoles": roles}))
PY
az rest --method PATCH \
  --url "https://graph.microsoft.com/v1.0/applications/${OBJ_ID}" \
  --headers "Content-Type=application/json" \
  --body @"$PATCH1" >/dev/null
echo "patched (phase 1): identifierUris + api(v2, ${SCOPE_NAME} + ${SSO_SCOPE_NAME}) + appRole(${ROLE_NAME})"

# ── phase 2: pre-authorize the Microsoft first-party clients (now that the scopes are stored) ──────
# (Graph rejects preAuthorizedApplications referencing scope ids not yet persisted, so this is a
#  separate PATCH after phase 1. Re-read the app so we bind the real, stored scope ids.)
CURRENT2="$(az ad app show --id "$APP_ID" -o json)"
SSO_SCOPE_NAME="$SSO_SCOPE_NAME" SCOPE_NAME="$SCOPE_NAME" python3 - "$CURRENT2" > "$PATCH2" <<'PY'
import json, os, sys
cur = json.loads(sys.argv[1]); api = cur.get("api") or {}
ids = {s["value"]: s["id"] for s in api.get("oauth2PermissionScopes") or []}
want = sorted({ids[os.environ["SCOPE_NAME"]], ids[os.environ["SSO_SCOPE_NAME"]]})
FIRST_PARTY_CLIENTS = [
    "ea5a67f6-b6f3-4338-b240-c655ddc3cc8e", "d3590ed6-52b3-4102-aeff-aad2292ab01c",
    "93d53678-613d-4013-afc1-62e9e444a0a5", "bc59ab01-8403-45c6-8796-ac3ef710b3e3",
    "27922004-5251-4030-b22d-91ecd9a37ea4", "4765445b-32c6-49b0-83e6-1d93765276ca",
    "0ec893e0-5785-4de6-99da-4ed124e5296c", "1fec8e78-bce4-4aaf-ab1b-5451cc387264",
    "5e3ce6c0-2b1f-4285-8d4b-75ee78787346", "ab3be6b7-f5df-413d-ac2d-abf1e3fd9c0b",
]
pa = {p.get("appId"): set(p.get("delegatedPermissionIds") or [])
      for p in (api.get("preAuthorizedApplications") or [])}
for c in FIRST_PARTY_CLIENTS:
    pa.setdefault(c, set()).update(want)
print(json.dumps({"api": {"preAuthorizedApplications":
    [{"appId": c, "delegatedPermissionIds": sorted(v)} for c, v in pa.items()]}}))
PY
az rest --method PATCH \
  --url "https://graph.microsoft.com/v1.0/applications/${OBJ_ID}" \
  --headers "Content-Type=application/json" --body @"$PATCH2" >/dev/null
echo "patched (phase 2): preAuthorizedApplications (10 Microsoft first-party clients)"

# ── phase 3: Teams SSO consent redirect (additive; required by the Copilot API-plugin OAuth flow) ──
CURRENT_WEB="$(az ad app show --id "$APP_ID" --query 'web.redirectUris' -o json)"
python3 - "$CURRENT_WEB" > "$PATCH3" <<'PY'
import json, sys
uris = set(json.loads(sys.argv[1] or "[]"))
uris.add("https://teams.microsoft.com/api/platform/v1.0/oAuthConsentRedirect")
print(json.dumps({"web": {"redirectUris": sorted(uris)}}))
PY
az rest --method PATCH \
  --url "https://graph.microsoft.com/v1.0/applications/${OBJ_ID}" \
  --headers "Content-Type=application/json" --body @"$PATCH3" >/dev/null
echo "patched (phase 3): Teams SSO consent web redirect"

# Ensure a service principal exists (required before app roles can be assigned / consented).
az ad sp show --id "$APP_ID" >/dev/null 2>&1 || az ad sp create --id "$APP_ID" >/dev/null
echo "service principal present"

if [ "$CONSENT" = "1" ]; then
  # Tenant-wide admin consent for any Graph permissions THIS app requests (e.g. profile/openid for OBO).
  # Note: SSO for the pre-authorized first-party clients above does NOT need this — pre-authorization is
  # what makes those clients consent-free. This step only matters if the API itself calls Graph.
  az ad app permission admin-consent --id "$APP_ID" >/dev/null 2>&1 \
    && echo "admin consent granted" \
    || echo "admin consent skipped (no client grants to consent yet, or insufficient role)"
fi

cat <<EOF

── set these on the Decision gateway (dark until BOTH are set) ─────────────────
ALGENTA_ENTRA_AUDIENCE="${AUDIENCE}"
ALGENTA_ENTRA_TENANT_ID="${TENANT_ID}"
# If the Excel add-in / Teams tab uses a domain-qualified App ID URI (api://<host>/<app-id>),
# add it comma-separated (the gateway accepts multiple audiences):
#   ALGENTA_ENTRA_AUDIENCE="${AUDIENCE},api://<addin-host>/${APP_ID}"
# Optional: ALGENTA_ENTRA_ALLOWED_TENANTS="<other customer tenants, comma-sep>"
# Optional: ALGENTA_ENTRA_ALLOWED_CLIENT_APPS="<client app ids, comma-sep>"  # if set, include the
#   first-party GUIDs above or SSO callers are rejected by the azp/appid allowlist.
────────────────────────────────────────────────────────────────────────────────
EOF
