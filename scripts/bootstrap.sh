#!/usr/bin/env bash
# Idempotent bootstrap of the codna Fly stack: 2 apps + Fly Managed Postgres + Upstash Redis +
# Tigris Object Storage + the engine volume + the api cert. Safe to re-run (validate + update).
# Requires: flyctl (authenticated via FLY_API_TOKEN), and the account/billing set up in the console.
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_deploy_common.sh"
need flyctl

log "1/8 Fly apps"
for app in "$CODNA_API_APP" "$CODNA_ENGINE_APP"; do
  if fly_app_exists "$app"; then log "  app $app exists"; else fly apps create "$app" --org "${FLY_ORG:-personal}"; fi
done

log "2/8 region default = $FLY_REGION (set per-machine at deploy)"

log "3/8 Fly Managed Postgres ($CODNA_API_APP, $CODNA_ENGINE_APP)"
# codna-pg is the PRODUCTION database of codna-api and codna-engine (api_keys, users, organizations,
# subscriptions, usage, audit, device grants). Because DATABASE_URL is set as a plain secret rather than
# through `fly mpg attach`, `fly mpg list` shows it with "<no attached apps>" -- that column is NOT
# evidence that the cluster is unused. Never delete or downsize it from a console listing; compare the
# apps' DATABASE_URL secret digests and inspect the data first (2026-09-21, after a near-miss).
if fly_app_exists "${PG_APP:-codna-pg}"; then
  log "  pg ${PG_APP:-codna-pg} exists"
else
  fly postgres create --name "${PG_APP:-codna-pg}" --region "$FLY_REGION" --org "${FLY_ORG:-personal}" \
    --initial-cluster-size 1 --vm-size shared-cpu-1x --volume-size 10 || \
    log "  (if 'fly postgres' is unavailable, provision Managed Postgres in the console + set DATABASE_URL secrets)"
fi
fly postgres attach "${PG_APP:-codna-pg}" -a "$CODNA_API_APP"    || log "  pg already attached to api"
fly postgres attach "${PG_APP:-codna-pg}" -a "$CODNA_ENGINE_APP" || log "  pg already attached to engine"
log "  NOTE: ensure DATABASE_URL is async (postgresql+asyncpg://) and set DATABASE_URL_SYNC (psycopg)."

log "4/8 Upstash Redis"
if fly redis list 2>/dev/null | grep -q "${REDIS_NAME:-codna-redis}"; then
  log "  redis ${REDIS_NAME:-codna-redis} exists"
else
  fly redis create --name "${REDIS_NAME:-codna-redis}" --region "$FLY_REGION" --org "${FLY_ORG:-personal}" \
    || log "  (create Upstash Redis in the console + set REDIS_URL on both apps)"
fi
log "  set REDIS_URL on both apps to the Upstash connection string (fly redis status <name>)."

log "5/8 Tigris object storage → remap to S3_* the engine expects"
fly storage create -a "$CODNA_API_APP" --name "${TIGRIS_BUCKET:-codna-artifacts}" 2>/dev/null \
  || log "  (tigris bucket exists or create in console)"
log "  Fly/Tigris injects AWS_* + BUCKET_NAME. Re-map to S3_* on BOTH apps:"
log "    S3_ENDPOINT_URL=\$AWS_ENDPOINT_URL_S3  S3_ACCESS_KEY_ID=\$AWS_ACCESS_KEY_ID"
log "    S3_SECRET_ACCESS_KEY=\$AWS_SECRET_ACCESS_KEY  S3_BUCKET_NAME=\$BUCKET_NAME  S3_REGION=auto"

log "6/8 engine shared-working-dir volume"
if fly volumes list -a "$CODNA_ENGINE_APP" 2>/dev/null | grep -q "$ENGINE_VOLUME"; then
  log "  volume $ENGINE_VOLUME exists"
else
  fly volumes create "$ENGINE_VOLUME" -a "$CODNA_ENGINE_APP" --region "$FLY_REGION" --size "$ENGINE_VOLUME_SIZE_GB" --yes
fi

log "7/8 api cert for $API_HOSTNAME (issue BEFORE Cloudflare Full-Strict/orange — see DEPLOY.md)"
fly certs add "$API_HOSTNAME" -a "$CODNA_API_APP" 2>/dev/null || log "  cert already requested; check 'fly certs show $API_HOSTNAME -a $CODNA_API_APP'"

log "8/8 required secrets check"
"${_here}/status.sh" --secrets-only || true
log "bootstrap complete. Next: set secrets (DEPLOY.md), then 'make deploy-fly' and 'make deploy-cloudflare'."
