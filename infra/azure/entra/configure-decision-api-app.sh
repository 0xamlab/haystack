#!/usr/bin/env bash
#
# configure-decision-api-app.sh — idempotently expose the Algenta Decision API on an Entra
# app registration, matching gitbook/integrations/microsoft/entra-sso.md.
#
# What it does (all additive — it never changes signInAudience, so an app that also serves
# consumer sign-in keeps working):
#   * Application ID URI      -> api://<APP_ID>               (the audience the gateway requires)
#   * requestedAccessTokenVersion -> 2                        (the gateway accepts v2 tokens only)
#   * delegated scope         -> Decisions.Run                (signed-in employees; admin+user consent)
#   * app role (Application)  -> Decisions.Service            (service / managed identities)
#
# Idempotent: re-running is a no-op once each piece is present (matched by value, not by id).
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
set -euo pipefail

APP_ID="${APP_ID:-3983990d-e9b5-4866-9a43-d52d6e0c20c3}"   # Thyn Accounts Sign-In (Decision API app)
SCOPE_NAME="${SCOPE_NAME:-Decisions.Run}"                  # delegated (employee) scope
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
PATCH_BODY="$(APP_ID="$APP_ID" AUDIENCE="$AUDIENCE" SCOPE_NAME="$SCOPE_NAME" ROLE_NAME="$ROLE_NAME" \
  python3 - "$CURRENT" <<'PY'
import json, os, sys, uuid
cur = json.loads(sys.argv[1])
audience, scope_name, role_name = os.environ["AUDIENCE"], os.environ["SCOPE_NAME"], os.environ["ROLE_NAME"]

api = cur.get("api") or {}
scopes = list(api.get("oauth2PermissionScopes") or [])
if not any((s.get("value") == scope_name) for s in scopes):
    scopes.append({
        "id": str(uuid.uuid4()),
        "value": scope_name,
        "type": "User",  # admin + user consentable
        "isEnabled": True,
        "adminConsentDisplayName": f"Access the Algenta Decision API ({scope_name})",
        "adminConsentDescription": "Allow the app to call the Algenta Decision API on behalf of the signed-in user.",
        "userConsentDisplayName": "Access the Algenta Decision API",
        "userConsentDescription": "Allow this app to make decisions on your behalf via the Algenta Decision API.",
    })
api["oauth2PermissionScopes"] = scopes
api["requestedAccessTokenVersion"] = 2

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
)"

echo "$PATCH_BODY" | az rest --method PATCH \
  --url "https://graph.microsoft.com/v1.0/applications/${OBJ_ID}" \
  --headers "Content-Type=application/json" \
  --body @- >/dev/null
echo "patched: identifierUris + api(v2, ${SCOPE_NAME}) + appRole(${ROLE_NAME})"

# Ensure a service principal exists (required before app roles can be assigned / consented).
az ad sp show --id "$APP_ID" >/dev/null 2>&1 || az ad sp create --id "$APP_ID" >/dev/null
echo "service principal present"

if [ "$CONSENT" = "1" ]; then
  # Tenant-wide admin consent for THIS app's exposed permissions. (Client apps — Copilot/Teams/Excel/
  # Foundry — separately request Decisions.Run / Decisions.Service; consent those on the client side.)
  az ad app permission admin-consent --id "$APP_ID" >/dev/null 2>&1 \
    && echo "admin consent granted" \
    || echo "admin consent skipped (no client grants to consent yet, or insufficient role)"
fi

cat <<EOF

── set these on the Decision gateway (dark until BOTH are set) ─────────────────
ALGENTA_ENTRA_AUDIENCE="${AUDIENCE}"
ALGENTA_ENTRA_TENANT_ID="${TENANT_ID}"
# Optional: ALGENTA_ENTRA_ALLOWED_TENANTS="<other customer tenants, comma-sep>"
# Optional: ALGENTA_ENTRA_ALLOWED_CLIENT_APPS="<client app ids, comma-sep>"
────────────────────────────────────────────────────────────────────────────────
EOF
