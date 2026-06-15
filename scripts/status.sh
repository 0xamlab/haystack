#!/usr/bin/env bash
# Health snapshot of the codna deployment: Fly app status + the public health endpoint, plus a
# required-secrets check. `--secrets-only` prints just the missing-secret report (used by bootstrap).
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_deploy_common.sh"
need flyctl

REQUIRED_API_SECRETS=(DATABASE_URL DATABASE_URL_SYNC REDIS_URL S3_ENDPOINT_URL S3_ACCESS_KEY_ID
  S3_SECRET_ACCESS_KEY S3_BUCKET_NAME ALGENTA_CONFIG_ENCRYPTION_KEY GITHUB_APP_ID
  GITHUB_APP_PRIVATE_KEY GITHUB_APP_WEBHOOK_SECRET GITHUB_APP_CLIENT_ID GITHUB_APP_CLIENT_SECRET
  GITHUB_APP_SLUG ALGENTA_AGENT_CORE_TOKEN)
REQUIRED_ENGINE_SECRETS=(DATABASE_URL DATABASE_URL_SYNC REDIS_URL S3_ENDPOINT_URL S3_ACCESS_KEY_ID
  S3_SECRET_ACCESS_KEY S3_BUCKET_NAME ALGENTA_CONFIG_ENCRYPTION_KEY GITHUB_APP_ID
  GITHUB_APP_PRIVATE_KEY AGENT_CORE_AUTH_TOKEN ALGENTA_AGENT_CORE_TOKEN ANTHROPIC_API_KEY)

check_secrets() {
  local app="$1"; shift
  local present; present="$(fly secrets list -a "$app" 2>/dev/null | awk 'NR>1{print $1}')"
  local missing=()
  for s in "$@"; do echo "$present" | grep -qx "$s" || missing+=("$s"); done
  if [ "${#missing[@]}" -eq 0 ]; then log "  $app: all required secrets present"; else
    log "  $app: MISSING ${missing[*]}"; fi
}

log "required secrets"
check_secrets "$CODNA_API_APP"    "${REQUIRED_API_SECRETS[@]}"
check_secrets "$CODNA_ENGINE_APP" "${REQUIRED_ENGINE_SECRETS[@]}"
[ "${1:-}" = "--secrets-only" ] && exit 0

log "fly status"
fly status -a "$CODNA_API_APP"    || true
fly status -a "$CODNA_ENGINE_APP" || true

log "public health (https://${API_HOSTNAME}/v1/health)"
curl -fsS -m 10 "https://${API_HOSTNAME}/v1/health" && echo || log "  health check failed (DNS/cert/app not ready?)"
